from fastapi import FastAPI, UploadFile, File, WebSocket, WebSocketDisconnect, HTTPException, Request
from fastapi.responses import JSONResponse, FileResponse, HTMLResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Dict
from pathlib import Path
from datetime import datetime, timedelta, timezone
from contextlib import contextmanager
import json
import sqlite3
import os
import re
import asyncio
import logging
import sys
import hashlib
import csv
import io
from fastapi.staticfiles import StaticFiles

# Path setup for Haven-UI self-contained structure
# backend/ is inside Haven-UI/, which is inside Master-Haven/
BACKEND_DIR = Path(__file__).resolve().parent
HAVEN_UI_DIR = BACKEND_DIR.parent
MASTER_HAVEN_ROOT = HAVEN_UI_DIR.parent

# Add backend dir to path for local imports
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# Import path configuration (now in same folder)
try:
    from paths import haven_paths
except ImportError:
    haven_paths = None

# Import schema migration system (now in same folder)
from migrations import run_pending_migrations

# Import glyph decoder (now in same folder)
from glyph_decoder import (
    decode_glyph_to_coords,
    encode_coords_to_glyph,
    validate_glyph_code,
    format_glyph,
    is_in_core_void,
    is_phantom_star,
    get_system_classification,
    galactic_coords_to_glyph,
    GLYPH_IMAGES
)

# Import Planet Atlas wrapper for 3D planet visualization (now in same folder)
from planet_atlas_wrapper import generate_planet_html

app = FastAPI()
logger = logging.getLogger('control.room')

# Basic CORS - adjust for dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Determine Haven UI directory using centralized path config
if haven_paths:
    HAVEN_UI_DIR = haven_paths.haven_ui_dir
    PHOTOS_DIR = HAVEN_UI_DIR / 'photos'
    LOGS_DIR = haven_paths.get_logs_dir('haven-ui')
else:
    # Fallback to environment variable or default
    # Fallback: go from backend/ up to Haven-UI/
    HAVEN_UI_DIR = Path(os.getenv('HAVEN_UI_DIR', BACKEND_DIR.parent))
    PHOTOS_DIR = HAVEN_UI_DIR / 'photos'
    LOGS_DIR = HAVEN_UI_DIR / 'logs'

DATA_JSON = HAVEN_UI_DIR / 'data' / 'data.json'

# Discovery type emoji-to-slug mapping for URL routing
DISCOVERY_EMOJI_TO_SLUG = {
    '🦗': 'fauna',
    '🌿': 'flora',
    '💎': 'mineral',
    '🏛️': 'ancient',
    '📜': 'history',
    '🦴': 'bones',
    '👽': 'alien',
    '🚀': 'starship',
    '⚙️': 'multitool',
    '📖': 'lore',
    '🏠': 'base',
    '🆕': 'other',
}

# Reverse mapping: slug to emoji
DISCOVERY_SLUG_TO_EMOJI = {v: k for k, v in DISCOVERY_EMOJI_TO_SLUG.items()}

# All valid discovery type slugs
DISCOVERY_TYPE_SLUGS = list(DISCOVERY_SLUG_TO_EMOJI.keys())

# Discovery type display info (for frontend)
DISCOVERY_TYPE_INFO = {
    'fauna': {'emoji': '🦗', 'label': 'Fauna', 'color': '#22c55e'},
    'flora': {'emoji': '🌿', 'label': 'Flora', 'color': '#10b981'},
    'mineral': {'emoji': '💎', 'label': 'Mineral', 'color': '#a855f7'},
    'ancient': {'emoji': '🏛️', 'label': 'Ancient', 'color': '#eab308'},
    'history': {'emoji': '📜', 'label': 'History', 'color': '#f59e0b'},
    'bones': {'emoji': '🦴', 'label': 'Bones', 'color': '#78716c'},
    'alien': {'emoji': '👽', 'label': 'Alien', 'color': '#06b6d4'},
    'starship': {'emoji': '🚀', 'label': 'Starship', 'color': '#3b82f6'},
    'multitool': {'emoji': '⚙️', 'label': 'Multi-tool', 'color': '#f97316'},
    'lore': {'emoji': '📖', 'label': 'Lore', 'color': '#6366f1'},
    'base': {'emoji': '🏠', 'label': 'Custom Base', 'color': '#14b8a6'},
    'other': {'emoji': '🆕', 'label': 'Other', 'color': '#6b7280'},
}

# Simplified type-specific fields for discovery submissions (2-3 per type)
DISCOVERY_TYPE_FIELDS = {
    'fauna':    ['species_name', 'behavior'],
    'flora':    ['species_name', 'biome'],
    'mineral':  ['resource_type', 'deposit_richness'],
    'ancient':  ['age_era', 'associated_race'],
    'history':  ['language_status', 'author_origin'],
    'bones':    ['species_type', 'estimated_age'],
    'alien':    ['structure_type', 'operational_status'],
    'starship': ['ship_type', 'ship_class'],
    'multitool':['tool_type', 'tool_class'],
    'lore':     ['story_type'],
    'base':     ['base_type'],
    'other':    [],
}


def get_discovery_type_slug(discovery_type: str) -> str:
    """Convert discovery type emoji or text to URL-friendly slug."""
    if not discovery_type:
        return 'other'
    # Check if it's already a slug
    if discovery_type.lower() in DISCOVERY_TYPE_SLUGS:
        return discovery_type.lower()
    # Check emoji mapping
    if discovery_type in DISCOVERY_EMOJI_TO_SLUG:
        return DISCOVERY_EMOJI_TO_SLUG[discovery_type]
    # Try text-based mapping
    text_lower = discovery_type.lower()
    text_mappings = {
        'fauna': 'fauna', 'flora': 'flora', 'mineral': 'mineral',
        'ancient': 'ancient', 'history': 'history', 'bones': 'bones',
        'alien': 'alien', 'starship': 'starship', 'ship': 'starship',
        'multi-tool': 'multitool', 'multitool': 'multitool', 'tool': 'multitool',
        'lore': 'lore', 'custom base': 'base', 'base': 'base',
        'other': 'other', 'unknown': 'other',
    }
    return text_mappings.get(text_lower, 'other')


# Load galaxies reference data for validation
# Path goes from backend/ → Haven-UI/ → Master-Haven/ → NMS-Save-Watcher/
GALAXIES_JSON_PATH = MASTER_HAVEN_ROOT / 'NMS-Save-Watcher' / 'data' / 'galaxies.json'

def load_galaxies() -> dict:
    """Load galaxy reference data (all 256 NMS galaxies)."""
    try:
        if GALAXIES_JSON_PATH.exists():
            with open(GALAXIES_JSON_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        logger.warning(f"Failed to load galaxies.json: {e}")
    # Fallback to just Euclid if file not found
    return {"0": "Euclid"}

GALAXIES_DATA = load_galaxies()
GALAXY_NAMES = set(GALAXIES_DATA.values())
GALAXY_BY_INDEX = {int(k): v for k, v in GALAXIES_DATA.items()}
GALAXY_BY_NAME = {v: int(k) for k, v in GALAXIES_DATA.items()}

def validate_galaxy(galaxy: str) -> bool:
    """Validate galaxy name against known NMS galaxies."""
    return galaxy in GALAXY_NAMES

def validate_reality(reality: str) -> bool:
    """Validate reality value (Normal or Permadeath)."""
    return reality in ('Normal', 'Permadeath')

def normalize_discord_username(username: str) -> str:
    """
    Normalize a Discord username for comparison by:
    1. Converting to lowercase
    2. Stripping the #XXXX discriminator suffix if present

    Examples:
        'TurpitZz#9999' -> 'turpitzz'
        'TurpitZz' -> 'turpitzz'
        'User#1234' -> 'user'
    """
    if not username:
        return ''
    normalized = username.lower().strip()
    # Strip Discord discriminator (#0000 to #9999)
    if '#' in normalized:
        normalized = normalized.split('#')[0]
    return normalized


def get_system_glyph(glyph_code: str) -> str:
    """
    Extract the system portion of a glyph code (last 11 characters).

    In NMS, the first character is the planet/moon index (which portal you warp to).
    The remaining 11 characters represent the actual system coordinates.
    Two glyphs that only differ in the first character are the SAME system.

    Example:
        '2103CF58AC1D' -> '103CF58AC1D' (system glyph)
        '0103CF58AC1D' -> '103CF58AC1D' (same system, different portal)
    """
    if not glyph_code or len(glyph_code) < 11:
        return None
    # Return last 11 characters (the system coordinates)
    return glyph_code[-11:].upper() if len(glyph_code) >= 11 else glyph_code.upper()


def find_matching_system(cursor, glyph_code: str, galaxy: str, reality: str):
    """
    Find an existing system that matches by glyph coordinates + galaxy + reality.

    Two systems are considered the same if:
    1. Last 11 characters of glyph match (same system coordinates)
    2. Same galaxy (Euclid, Hilbert, etc.)
    3. Same reality (Normal, Permadeath)

    Returns the matching system row or None if no match found.
    """
    system_glyph = get_system_glyph(glyph_code)
    if not system_glyph:
        return None

    # Query for systems where last 11 chars of glyph match + same galaxy + reality
    cursor.execute('''
        SELECT id, name, glyph_code, glyph_planet, glyph_solar_system,
               discovered_by, discovered_at, contributors
        FROM systems
        WHERE SUBSTR(glyph_code, -11) = ?
          AND galaxy = ?
          AND reality = ?
    ''', (system_glyph, galaxy or 'Euclid', reality or 'Normal'))

    return cursor.fetchone()


# Ensure directories exist
HAVEN_UI_DIR.mkdir(parents=True, exist_ok=True)
(HAVEN_UI_DIR / 'data').mkdir(parents=True, exist_ok=True)
PHOTOS_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)

# Mount static folders (so running uvicorn directly also serves the SPA)
photos_dir = HAVEN_UI_DIR / 'photos'
if photos_dir.exists():
    app.mount('/haven-ui-photos', StaticFiles(directory=str(photos_dir)), name='haven-ui-photos')

# Mount war-media directory for war room uploaded images
war_media_dir = HAVEN_UI_DIR / 'public' / 'war-media'
war_media_dir.mkdir(parents=True, exist_ok=True)  # Ensure directory exists
app.mount('/war-media', StaticFiles(directory=str(war_media_dir)), name='war-media')

ui_static_dir = HAVEN_UI_DIR / 'static'
ui_dist_dir = HAVEN_UI_DIR / 'dist'
if ui_dist_dir.exists():
    # Prefer production build in dist over static
    dist_assets = ui_dist_dir / 'assets'
    if dist_assets.exists():
        app.mount('/haven-ui/assets', StaticFiles(directory=str(dist_assets)), name='ui-dist-assets')
    # Mount dist root at /haven-ui (production build)
    app.mount('/haven-ui', StaticFiles(directory=str(ui_dist_dir), html=True), name='ui-dist')
    # Also mount raw dist path so /haven-ui/dist/* works
    app.mount('/haven-ui/dist', StaticFiles(directory=str(ui_dist_dir)), name='ui-dist-dir')
    # Also make map-specific static paths available at '/map/static' so /map/latest loads correctly
    map_static_dir = ui_dist_dir / 'static'
    if map_static_dir.exists():
        app.mount('/map/static', StaticFiles(directory=str(map_static_dir)), name='map-static')
    map_assets_dir = ui_dist_dir / 'assets'
    if map_assets_dir.exists():
        app.mount('/map/assets', StaticFiles(directory=str(map_assets_dir)), name='map-assets')
    # Provide fallback static under a different path
    if ui_static_dir.exists():
        app.mount('/haven-ui-static', StaticFiles(directory=str(ui_static_dir)), name='haven-ui-static')
else:
    if ui_static_dir.exists():
        # Mount assets FIRST before the catch-all html=True mount
        assets_dir = ui_static_dir / 'assets'
        if assets_dir.exists():
            app.mount('/haven-ui/assets', StaticFiles(directory=str(assets_dir)), name='ui-static-assets')
        # Now mount the main UI with html=True (this catches remaining requests)
        app.mount('/haven-ui', StaticFiles(directory=str(ui_static_dir), html=True), name='ui-static')
        app.mount('/haven-ui-static', StaticFiles(directory=str(ui_static_dir)), name='haven-ui-static')

# In-memory system cache
_systems_cache: Dict[str, dict] = {}
_systems_lock = asyncio.Lock()

def load_data_json() -> dict:
    if not DATA_JSON.exists():
        return {'systems': []}
    try:
        return json.loads(DATA_JSON.read_text(encoding='utf-8'))
    except Exception as e:
        logger.error('Failed loading data.json: %s', e)
        return {'systems': []}

def save_data_json(data: dict):
    DATA_JSON.write_text(json.dumps(data, indent=2), encoding='utf-8')


def get_db_path() -> Path:
    """Get the path to the Haven database using centralized config."""
    if haven_paths and haven_paths.haven_db:
        return haven_paths.haven_db
    return HAVEN_UI_DIR / 'data' / 'haven_ui.db'


def get_db_connection():
    """Create a properly configured database connection with timeout and WAL mode.

    This ensures all connections use consistent settings to avoid database locks.
    """
    db_path = get_db_path()
    conn = sqlite3.connect(str(db_path), timeout=30.0)
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA busy_timeout=30000')
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def get_db():
    """Context manager for database connections - ensures proper cleanup even on exceptions."""
    conn = None
    try:
        conn = get_db_connection()
        yield conn
    finally:
        if conn:
            conn.close()


def parse_station_data(station_row):
    """Parse space station data from database row, handling JSON trade_goods field."""
    if not station_row:
        return None
    station = dict(station_row)
    # Parse trade_goods JSON string to list
    trade_goods = station.get('trade_goods', '[]')
    if isinstance(trade_goods, str):
        try:
            station['trade_goods'] = json.loads(trade_goods)
        except (json.JSONDecodeError, TypeError):
            station['trade_goods'] = []
    return station


def init_database():
    """Initialize the Haven database with required tables."""
    db_path = get_db_path()

    # Check if database might be corrupted and restore from backup if needed
    try:
        # Try to open and do a simple integrity check
        test_conn = sqlite3.connect(str(db_path), timeout=30.0)
        test_conn.execute('PRAGMA integrity_check')
        test_conn.close()
    except Exception as e:
        logger.exception('Database integrity check failed: %s', e)
        # Try to restore from backup
        backup_path = db_path.parent / 'haven_ui.db.backup'
        if backup_path.exists():
            logger.warning('Attempting to restore from backup: %s', backup_path)
            import shutil
            # Move corrupted database aside and restore from backup (best-effort)
            corrupted_path = db_path.parent / 'haven_ui.db.corrupted'
            try:
                if db_path.exists():
                    shutil.move(str(db_path), str(corrupted_path))
                    logger.info('Moved corrupted DB to %s', corrupted_path)
                # Restore from backup
                shutil.copy2(str(backup_path), str(db_path))
                logger.info('Database restored from backup')
            except Exception as ex:
                logger.exception('Failed to restore database from backup: %s', ex)
                # If restore fails we'll continue and allow the table creation below
                # to create a fresh database; don't raise here so startup can continue.
        else:
            logger.info('No backup available, will create a fresh database')

    conn = sqlite3.connect(str(db_path), timeout=30.0)
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA busy_timeout=30000')
    cursor = conn.cursor()

    # Create discoveries table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS discoveries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            discovery_type TEXT,
            discovery_name TEXT,
            system_id INTEGER,
            planet_id INTEGER,
            moon_id INTEGER,
            location_type TEXT,
            location_name TEXT,
            description TEXT,
            significance TEXT DEFAULT 'Notable',
            discovered_by TEXT DEFAULT 'anonymous',
            submission_timestamp TEXT,
            mystery_tier INTEGER DEFAULT 1,
            analysis_status TEXT DEFAULT 'pending',
            pattern_matches INTEGER DEFAULT 0,
            discord_user_id TEXT,
            discord_guild_id TEXT,
            photo_url TEXT,
            evidence_url TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Create systems table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS systems (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            galaxy TEXT DEFAULT 'Euclid',
            x INTEGER,
            y INTEGER,
            z INTEGER,
            star_x REAL,
            star_y REAL,
            star_z REAL,
            description TEXT,
            glyph_code TEXT,
            glyph_planet INTEGER DEFAULT 0,
            glyph_solar_system INTEGER DEFAULT 1,
            region_x INTEGER,
            region_y INTEGER,
            region_z INTEGER,
            is_phantom INTEGER DEFAULT 0,
            is_in_core INTEGER DEFAULT 0,
            classification TEXT DEFAULT 'accessible',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Create planets table (supports both coordinates and game properties)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS planets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            system_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            x REAL DEFAULT 0,
            y REAL DEFAULT 0,
            z REAL DEFAULT 0,
            climate TEXT,
            sentinel TEXT DEFAULT 'None',
            fauna TEXT DEFAULT 'N/A',
            flora TEXT DEFAULT 'N/A',
            fauna_count INTEGER DEFAULT 0,
            flora_count INTEGER DEFAULT 0,
            has_water INTEGER DEFAULT 0,
            materials TEXT,
            base_location TEXT,
            photo TEXT,
            notes TEXT,
            description TEXT,
            FOREIGN KEY (system_id) REFERENCES systems(id) ON DELETE CASCADE
        )
    ''')

    # Create moons table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS moons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            planet_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            orbit_radius REAL DEFAULT 0.5,
            orbit_speed REAL DEFAULT 0,
            climate TEXT,
            sentinel TEXT DEFAULT 'None',
            fauna TEXT DEFAULT 'N/A',
            flora TEXT DEFAULT 'N/A',
            materials TEXT,
            notes TEXT,
            description TEXT,
            photo TEXT,
            FOREIGN KEY (planet_id) REFERENCES planets(id) ON DELETE CASCADE
        )
    ''')

    # Create space_stations table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS space_stations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            system_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            race TEXT DEFAULT 'Gek',
            x REAL DEFAULT 0,
            y REAL DEFAULT 0,
            z REAL DEFAULT 0,
            sell_percent INTEGER DEFAULT 80,
            buy_percent INTEGER DEFAULT 50,
            FOREIGN KEY (system_id) REFERENCES systems(id) ON DELETE CASCADE
        )
    ''')

    # Create pending_systems table for approval queue
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS pending_systems (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            submitted_by TEXT,
            submitted_by_ip TEXT,
            submission_date TEXT,
            system_data TEXT,
            status TEXT DEFAULT 'pending',
            system_name TEXT,
            system_region TEXT,
            reviewed_by TEXT,
            review_date TEXT,
            review_notes TEXT
        )
    ''')

    # Create regions table for custom region names
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS regions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            region_x INTEGER NOT NULL,
            region_y INTEGER NOT NULL,
            region_z INTEGER NOT NULL,
            custom_name TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(region_x, region_y, region_z),
            UNIQUE(custom_name)
        )
    ''')

    # Create pending_region_names table for approval queue
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS pending_region_names (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            region_x INTEGER NOT NULL,
            region_y INTEGER NOT NULL,
            region_z INTEGER NOT NULL,
            proposed_name TEXT NOT NULL,
            submitted_by TEXT,
            submitted_by_ip TEXT,
            submission_date TEXT,
            status TEXT DEFAULT 'pending',
            reviewed_by TEXT,
            review_date TEXT,
            review_notes TEXT
        )
    ''')

    # Create api_keys table for companion app and API authentication
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS api_keys (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key_hash TEXT NOT NULL UNIQUE,
            key_prefix TEXT NOT NULL,
            name TEXT NOT NULL,
            created_at TEXT NOT NULL,
            last_used_at TEXT,
            permissions TEXT DEFAULT '["submit"]',
            rate_limit INTEGER DEFAULT 200,
            is_active INTEGER DEFAULT 1,
            created_by TEXT,
            discord_tag TEXT
        )
    ''')

    # Create activity_logs table for tracking system events
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS activity_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            event_type TEXT NOT NULL,
            message TEXT NOT NULL,
            details TEXT,
            user_name TEXT
        )
    ''')

    # Create indexes for better performance
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_planets_system_id ON planets(system_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_moons_planet_id ON moons(planet_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_space_stations_system_id ON space_stations(system_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_discoveries_system_id ON discoveries(system_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_discoveries_planet_id ON discoveries(planet_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_pending_systems_status ON pending_systems(status)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_regions_coords ON regions(region_x, region_y, region_z)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_pending_region_names_status ON pending_region_names(status)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_api_keys_hash ON api_keys(key_hash)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_api_keys_prefix ON api_keys(key_prefix)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_activity_logs_timestamp ON activity_logs(timestamp DESC)')

    # Critical indexes for systems table - needed for efficient region queries and search
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_systems_region ON systems(region_x, region_y, region_z)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_systems_glyph_code ON systems(glyph_code)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_systems_name ON systems(name)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_systems_created_at ON systems(created_at DESC)')

    # Migration: add new columns to existing planets table
    def add_column_if_missing(table, column, coltype):
        cursor.execute(f"PRAGMA table_info({table})")
        columns = [row[1] for row in cursor.fetchall()]
        if column not in columns:
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {coltype}")
            logger.info(f"Added column {column} to {table}")

    # Planets table migrations
    add_column_if_missing('planets', 'fauna', "TEXT DEFAULT 'N/A'")
    add_column_if_missing('planets', 'flora', "TEXT DEFAULT 'N/A'")
    add_column_if_missing('planets', 'materials', 'TEXT')
    add_column_if_missing('planets', 'base_location', 'TEXT')
    add_column_if_missing('planets', 'photo', 'TEXT')
    add_column_if_missing('planets', 'notes', 'TEXT')

    # Moons table migrations
    add_column_if_missing('moons', 'orbit_speed', 'REAL DEFAULT 0')
    add_column_if_missing('moons', 'fauna', "TEXT DEFAULT 'N/A'")
    add_column_if_missing('moons', 'flora', "TEXT DEFAULT 'N/A'")
    add_column_if_missing('moons', 'materials', 'TEXT')
    add_column_if_missing('moons', 'notes', 'TEXT')
    add_column_if_missing('moons', 'photo', 'TEXT')

    # Systems table migrations (for NMS Save Watcher companion app)
    add_column_if_missing('systems', 'star_type', 'TEXT')  # Yellow, Red, Green, Blue, Purple
    add_column_if_missing('systems', 'economy_type', 'TEXT')  # Trading, Mining, Technology, etc.
    add_column_if_missing('systems', 'economy_level', 'TEXT')  # Low, Medium, High
    add_column_if_missing('systems', 'conflict_level', 'TEXT')  # Low, Medium, High
    add_column_if_missing('systems', 'dominant_lifeform', 'TEXT')  # Gek, Vy'keen, Korvax, None
    add_column_if_missing('systems', 'discovered_by', 'TEXT')  # Original discoverer username
    add_column_if_missing('systems', 'discovered_at', 'TEXT')  # ISO timestamp of discovery

    # Planets table migrations (for live extraction weather data)
    add_column_if_missing('planets', 'weather', 'TEXT')  # Weather conditions from live extraction

    # Planets table migrations (for Haven Extractor v7.9.6+ complete planet data)
    add_column_if_missing('planets', 'biome', 'TEXT')  # Biome type: Lush, Toxic, Scorched, etc.
    add_column_if_missing('planets', 'biome_subtype', 'TEXT')  # Biome subtype: HugeLush, etc.
    add_column_if_missing('planets', 'planet_size', 'TEXT')  # Large, Medium, Small, Moon
    add_column_if_missing('planets', 'planet_index', 'INTEGER')  # Index in system (0-5)
    add_column_if_missing('planets', 'is_moon', 'INTEGER DEFAULT 0')  # Boolean: 1 if moon
    add_column_if_missing('planets', 'storm_frequency', 'TEXT')  # None, Low, High, Always
    add_column_if_missing('planets', 'weather_intensity', 'TEXT')  # Default, Extreme
    add_column_if_missing('planets', 'building_density', 'TEXT')  # Dead, Low, Mid, Full
    add_column_if_missing('planets', 'hazard_temperature', 'REAL DEFAULT 0')  # Temperature hazard
    add_column_if_missing('planets', 'hazard_radiation', 'REAL DEFAULT 0')  # Radiation hazard
    add_column_if_missing('planets', 'hazard_toxicity', 'REAL DEFAULT 0')  # Toxicity hazard
    add_column_if_missing('planets', 'common_resource', 'TEXT')  # Common resource ID
    add_column_if_missing('planets', 'uncommon_resource', 'TEXT')  # Uncommon resource ID
    add_column_if_missing('planets', 'rare_resource', 'TEXT')  # Rare resource ID
    add_column_if_missing('planets', 'weather_text', 'TEXT')  # Weather text description
    add_column_if_missing('planets', 'sentinels_text', 'TEXT')  # Sentinels text description
    add_column_if_missing('planets', 'flora_text', 'TEXT')  # Flora text description
    add_column_if_missing('planets', 'fauna_text', 'TEXT')  # Fauna text description

    # v10.0.0: Visit tracking - distinguish remote enumeration vs visited data
    # data_source: 'remote' (enumerated without visit), 'visited' (full detail), 'mixed' (has both)
    add_column_if_missing('systems', 'data_source', "TEXT DEFAULT 'visited'")
    add_column_if_missing('systems', 'visit_date', 'TEXT')  # ISO timestamp when fully visited
    add_column_if_missing('systems', 'is_complete', 'INTEGER DEFAULT 0')  # 1 if all planets have full data

    add_column_if_missing('planets', 'data_source', "TEXT DEFAULT 'visited'")
    add_column_if_missing('planets', 'visit_date', 'TEXT')  # ISO timestamp when fully visited

    # Pending systems table migrations (for companion app source tracking)
    add_column_if_missing('pending_systems', 'source', "TEXT DEFAULT 'manual'")  # manual, companion_app, api
    add_column_if_missing('pending_systems', 'api_key_name', 'TEXT')  # Name of API key used

    # Pending systems table migrations (for Haven Extractor API)
    add_column_if_missing('pending_systems', 'glyph_code', 'TEXT')  # Portal glyph code
    add_column_if_missing('pending_systems', 'galaxy', 'TEXT')  # Galaxy name (e.g., Euclid)
    add_column_if_missing('pending_systems', 'x', 'INTEGER')  # Voxel X coordinate
    add_column_if_missing('pending_systems', 'y', 'INTEGER')  # Voxel Y coordinate
    add_column_if_missing('pending_systems', 'z', 'INTEGER')  # Voxel Z coordinate
    add_column_if_missing('pending_systems', 'submitter_name', 'TEXT')  # Name of person who submitted
    add_column_if_missing('pending_systems', 'submission_timestamp', 'TEXT')  # ISO timestamp of submission
    add_column_if_missing('pending_systems', 'raw_json', 'TEXT')  # Full raw extraction JSON
    add_column_if_missing('pending_systems', 'rejection_reason', 'TEXT')  # Reason if rejected
    add_column_if_missing('pending_systems', 'personal_discord_username', 'TEXT')  # Discord username for personal (non-community) submissions
    add_column_if_missing('pending_systems', 'edit_system_id', 'TEXT')  # If set, this submission is an EDIT of existing system with this ID

    # API keys table migrations (for discord tag association)
    add_column_if_missing('api_keys', 'discord_tag', 'TEXT')  # Discord community tag for auto-tagging submissions

    # =========================================================================
    # Partner Login System Tables and Migrations
    # =========================================================================

    # Create partner_accounts table for multi-tenant partner login
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS partner_accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            discord_tag TEXT UNIQUE,
            display_name TEXT,
            enabled_features TEXT DEFAULT '[]',
            theme_settings TEXT DEFAULT '{}',
            region_color TEXT DEFAULT '#00C2B3',
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login_at TIMESTAMP,
            created_by TEXT
        )
    ''')

    # Create pending_edit_requests table for partner edit approval workflow
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS pending_edit_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            system_id INTEGER NOT NULL,
            partner_id INTEGER NOT NULL,
            edit_data TEXT NOT NULL,
            explanation TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            reviewed_by TEXT,
            review_date TIMESTAMP,
            review_notes TEXT,
            FOREIGN KEY (system_id) REFERENCES systems(id) ON DELETE CASCADE,
            FOREIGN KEY (partner_id) REFERENCES partner_accounts(id) ON DELETE CASCADE
        )
    ''')

    # Create indexes for partner system
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_partner_accounts_username ON partner_accounts(username)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_partner_accounts_discord_tag ON partner_accounts(discord_tag)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_pending_edit_requests_status ON pending_edit_requests(status)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_pending_edit_requests_partner ON pending_edit_requests(partner_id)')

    # Add discord_tag to systems and regions tables for partner ownership
    add_column_if_missing('systems', 'discord_tag', 'TEXT')
    add_column_if_missing('systems', 'personal_discord_username', 'TEXT')  # Discord username for personal (non-community) submissions
    add_column_if_missing('regions', 'discord_tag', 'TEXT')
    add_column_if_missing('pending_systems', 'discord_tag', 'TEXT')

    # Create indexes for discord_tag filtering
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_systems_discord_tag ON systems(discord_tag)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_regions_discord_tag ON regions(discord_tag)')

    # Add region_color to partner_accounts for custom 3D map region coloring
    add_column_if_missing('partner_accounts', 'region_color', "TEXT DEFAULT '#00C2B3'")

    # Create super_admin_settings table for storing changeable super admin password
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS super_admin_settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TEXT
        )
    ''')

    # Create data_restrictions table for partner data visibility controls
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS data_restrictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            system_id INTEGER NOT NULL,
            discord_tag TEXT NOT NULL,
            is_hidden_from_public INTEGER DEFAULT 0,
            hidden_fields TEXT DEFAULT '[]',
            map_visibility TEXT DEFAULT 'normal',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_by TEXT,
            FOREIGN KEY (system_id) REFERENCES systems(id) ON DELETE CASCADE,
            UNIQUE(system_id)
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_data_restrictions_system_id ON data_restrictions(system_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_data_restrictions_discord_tag ON data_restrictions(discord_tag)')

    # =========================================================================
    # Sub-Admin System Tables and Migrations
    # =========================================================================

    # Create sub_admin_accounts table for partner sub-administrators
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sub_admin_accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            parent_partner_id INTEGER,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            display_name TEXT,
            enabled_features TEXT DEFAULT '[]',
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login_at TIMESTAMP,
            created_by TEXT,
            FOREIGN KEY (parent_partner_id) REFERENCES partner_accounts(id) ON DELETE CASCADE
        )
    ''')

    # Create approval_audit_log table for tracking all approval/rejection actions
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS approval_audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            action TEXT NOT NULL,
            submission_type TEXT NOT NULL,
            submission_id INTEGER NOT NULL,
            submission_name TEXT,
            approver_username TEXT NOT NULL,
            approver_type TEXT NOT NULL,
            approver_account_id INTEGER,
            approver_discord_tag TEXT,
            submitter_username TEXT,
            submitter_account_id INTEGER,
            submitter_type TEXT,
            notes TEXT,
            submission_discord_tag TEXT
        )
    ''')

    # Create indexes for sub-admin system
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_sub_admin_parent ON sub_admin_accounts(parent_partner_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_sub_admin_username ON sub_admin_accounts(username)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON approval_audit_log(timestamp DESC)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_audit_approver ON approval_audit_log(approver_username)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_audit_discord_tag ON approval_audit_log(submission_discord_tag)')

    # Add submitter tracking columns to pending_systems for self-approval detection
    add_column_if_missing('pending_systems', 'submitter_account_id', 'INTEGER')
    add_column_if_missing('pending_systems', 'submitter_account_type', 'TEXT')

    # =========================================================================
    # Multi-Reality and Galaxy Tracking Migrations
    # =========================================================================

    # Add reality column to systems table (Permadeath vs Normal)
    # All existing data defaults to 'Normal' since Permadeath is a new tracking category
    add_column_if_missing('systems', 'reality', "TEXT DEFAULT 'Normal'")
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_systems_reality ON systems(reality)')

    # Add reality and galaxy columns to regions table
    # Regions are now unique per (reality, galaxy, region_x, region_y, region_z)
    add_column_if_missing('regions', 'reality', "TEXT DEFAULT 'Normal'")
    add_column_if_missing('regions', 'galaxy', "TEXT DEFAULT 'Euclid'")

    # Add reality to pending tables
    add_column_if_missing('pending_systems', 'reality', "TEXT DEFAULT 'Normal'")
    add_column_if_missing('pending_region_names', 'reality', "TEXT DEFAULT 'Normal'")
    add_column_if_missing('pending_region_names', 'galaxy', "TEXT DEFAULT 'Euclid'")
    add_column_if_missing('pending_region_names', 'discord_tag', 'TEXT')  # Community tag for routing approvals
    add_column_if_missing('pending_region_names', 'personal_discord_username', 'TEXT')  # Discord username for contact

    # Update regions unique constraint to include reality and galaxy
    cursor.execute("PRAGMA index_list(regions)")
    indexes = cursor.fetchall()
    has_new_unique = any('idx_regions_reality_galaxy_coords' in str(idx) for idx in indexes)

    if not has_new_unique:
        # Create new unique index for (reality, galaxy, region_x, region_y, region_z)
        try:
            cursor.execute('''
                CREATE UNIQUE INDEX IF NOT EXISTS idx_regions_reality_galaxy_coords
                ON regions(reality, galaxy, region_x, region_y, region_z)
            ''')
            logger.info("Created new unique index for regions (reality, galaxy, coords)")
        except Exception as e:
            logger.warning(f"Could not create regions unique index: {e}")

    # =========================================================================
    # Planet Atlas Integration - POI markers on planets
    # =========================================================================

    # Create planet_pois table for storing Points of Interest on planet surfaces
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS planet_pois (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            planet_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            poi_type TEXT DEFAULT 'custom',
            color TEXT DEFAULT '#00C2B3',
            symbol TEXT DEFAULT 'circle',
            category TEXT DEFAULT '-',
            created_by TEXT,
            discord_tag TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (planet_id) REFERENCES planets(id) ON DELETE CASCADE
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_planet_pois_planet_id ON planet_pois(planet_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_planet_pois_type ON planet_pois(poi_type)')

    conn.commit()
    conn.close()

    # Run schema migrations after base initialization
    try:
        applied_count, versions = run_pending_migrations(db_path)
        if applied_count > 0:
            logger.info(f"Applied {applied_count} migration(s): {', '.join(versions)}")
    except Exception as e:
        logger.error(f"Schema migration failed: {e}")
        # Don't raise - let the app start even if migrations fail
        # A backup was created before migration was attempted

    logger.info(f"Database initialized at {db_path}")


# NOTE: database initialization is now performed at application startup
# to avoid raising exceptions during module import (which breaks
# `python server.py` and other importers). This makes startup failures
# visible in logs and keeps import-time behavior safe for supervisors.


def _row_to_dict(row):
    if row is None:
        return None
    return {k: row[k] for k in row.keys()}


def add_activity_log(event_type: str, message: str, details: str = None, user_name: str = None):
    """Add an activity log entry to the database.

    Event types:
    - system_submitted: New system submitted for approval
    - system_approved: System approved and added to database
    - system_rejected: System submission rejected
    - system_saved: System directly saved (admin)
    - system_deleted: System deleted from database
    - system_edited: System was edited
    - region_submitted: Region name submitted for approval
    - region_approved: Region name approved
    - region_rejected: Region name rejected
    - discovery_added: New discovery added
    - map_generated: Galaxy map regenerated
    - watcher_upload: Data uploaded from NMS Save Watcher
    """
    conn = None
    try:
        db_path = get_db_path()
        if not db_path.exists():
            return
        conn = get_db_connection()
        cursor = conn.cursor()
        timestamp = datetime.now().isoformat()
        cursor.execute('''
            INSERT INTO activity_logs (timestamp, event_type, message, details, user_name)
            VALUES (?, ?, ?, ?, ?)
        ''', (timestamp, event_type, message, details, user_name))
        conn.commit()

        # Keep only the last 500 logs to prevent unbounded growth
        cursor.execute('''
            DELETE FROM activity_logs WHERE id NOT IN (
                SELECT id FROM activity_logs ORDER BY timestamp DESC LIMIT 500
            )
        ''')
        conn.commit()
    except Exception as e:
        logger.error(f"Failed to add activity log: {e}")
    finally:
        if conn:
            conn.close()


def load_systems_from_db() -> list:
    """Load systems from haven_ui.db and return nested structure (planets, moons & space stations).

    Falls back to empty list if DB does not exist or tables are missing.
    """
    db_path = get_db_path()
    if not db_path.exists():
        return []
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Read all systems with region custom names
        cursor.execute('''
            SELECT s.*, r.custom_name as region_name
            FROM systems s
            LEFT JOIN regions r ON s.region_x = r.region_x AND s.region_y = r.region_y AND s.region_z = r.region_z
        ''')
        systems_rows = cursor.fetchall()
        systems = [dict(row) for row in systems_rows]

        # Read planets and moons and nest them
        cursor.execute('SELECT * FROM planets')
        planets_rows = cursor.fetchall()
        planets = [dict(p) for p in planets_rows]

        cursor.execute('SELECT * FROM moons')
        moons_rows = cursor.fetchall()
        moons = [dict(m) for m in moons_rows]

        # Read space stations
        cursor.execute('SELECT * FROM space_stations')
        stations_rows = cursor.fetchall()
        stations = [parse_station_data(st) for st in stations_rows]

        # Index planets by system_id
        planets_by_system = {}
        for p in planets:
            planets_by_system.setdefault(p.get('system_id'), []).append(p)

        # Index moons by planet_id
        moons_by_planet = {}
        for m in moons:
            moons_by_planet.setdefault(m.get('planet_id'), []).append(m)

        # Index stations by system_id
        stations_by_system = {}
        for st in stations:
            stations_by_system[st.get('system_id')] = st

        # Build nested structure
        for s in systems:
            sys_id = s.get('id')
            sys_planets = planets_by_system.get(sys_id, [])
            for p in sys_planets:
                p['moons'] = moons_by_planet.get(p.get('id'), [])
            s['planets'] = sys_planets
            # Add space station if exists
            s['space_station'] = stations_by_system.get(sys_id)

        return systems
    except Exception as e:
        logger.error('Failed to read systems from DB: %s', e)
        return []
    finally:
        if conn:
            conn.close()


def query_discoveries_from_db(q: str = '', system_id: str = None, planet_id: int = None, moon_id: int = None) -> list:
    """Return list of discoveries from DB, optionally filtering by query across fields."""
    db_path = get_db_path()
    if not db_path.exists():
        return []
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        where_clauses = []
        params = []
        if q:
            q_pattern = f"%{q}%"
            where_clauses.append("(discovery_name LIKE ? OR description LIKE ? OR location_name LIKE ?)")
            params.extend([q_pattern, q_pattern, q_pattern])
        if system_id:
            where_clauses.append("system_id = ?")
            params.append(system_id)
        if planet_id:
            where_clauses.append("planet_id = ?")
            params.append(planet_id)
        if moon_id:
            where_clauses.append("moon_id = ?")
            params.append(moon_id)
        base_query = "SELECT * FROM discoveries"
        if where_clauses:
            base_query += " WHERE " + " AND ".join(where_clauses)
        base_query += " ORDER BY submission_timestamp DESC LIMIT 250"
        cursor.execute(base_query, params)
        rows = cursor.fetchall()
        discoveries = [dict(r) for r in rows]
        return discoveries
    except Exception as e:
        logger.error('Failed to query discoveries from DB: %s', e)
        return []
    finally:
        if conn:
            conn.close()

@app.on_event('startup')
async def on_startup():
    """Fast startup - only initialize database schema, don't preload data.

    PERFORMANCE OPTIMIZATION: Previously loaded all systems/planets/moons into
    _systems_cache on startup (12,000+ records), causing 5-10 second delays.
    Now we only initialize the DB schema and let queries hit the database directly.
    The cache is only populated on-demand for legacy JSON fallback scenarios.
    """
    # Initialize DB on startup so import-time failures are avoided.
    try:
        init_database()
    except Exception as e:
        # Log the error but continue
        logger.exception('Database initialization failed during startup: %s', e)

    # Load persisted settings into cache (fast - single row query)
    _settings_cache['personal_color'] = get_personal_color()

    # Log startup without loading all systems (count query is fast)
    try:
        db_path = get_db_path()
        if db_path.exists():
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM systems')
            count = cursor.fetchone()[0]
            conn.close()
            logger.info('Control Room API started - database has %d systems (lazy-loaded)', count)
        else:
            logger.info('Control Room API started - no database found, using JSON fallback')
    except Exception as e:
        logger.info('Control Room API started - count query failed: %s', e)

@app.get('/')
async def root():
    """Redirect root to Haven UI"""
    return RedirectResponse(url='/haven-ui/')

@app.get('/favicon.ico')
async def favicon():
    """Serve favicon from dist or return 204"""
    from fastapi.responses import FileResponse, Response
    favicon_svg = HAVEN_UI_DIR / 'dist' / 'favicon.svg'
    if favicon_svg.exists():
        return FileResponse(str(favicon_svg), media_type='image/svg+xml')
    return Response(status_code=204)

@app.get('/haven-ui/favicon.ico')
async def favicon_haven():
    """Serve favicon from dist"""
    from fastapi.responses import FileResponse, Response
    favicon_svg = HAVEN_UI_DIR / 'dist' / 'favicon.svg'
    if favicon_svg.exists():
        return FileResponse(str(favicon_svg), media_type='image/svg+xml')
    return Response(status_code=204)

@app.get('/haven-ui/icon.svg')
async def icon_svg():
    """Serve icon.svg from dist"""
    from fastapi.responses import FileResponse, Response
    icon = HAVEN_UI_DIR / 'dist' / 'icon.svg'
    if icon.exists():
        return FileResponse(str(icon), media_type='image/svg+xml')
    return Response(status_code=204)

@app.get('/workbox-{version}.js')
async def workbox(version: str):
    """Return 204 No Content for missing workbox (prevents 404 errors)"""
    from fastapi.responses import Response
    return Response(status_code=204)


@app.get('/haven-ui/workbox-{version}.js')
async def workbox_haven(version: str):
    from fastapi.responses import FileResponse, Response
    # Try to serve from dist, otherwise return 204
    dist_path = HAVEN_UI_DIR / 'dist' / f'workbox-{version}.js'
    if dist_path.exists():
        return FileResponse(str(dist_path))
    return Response(status_code=204)


@app.get('/haven-ui/sw.js')
async def sw_js():
    from fastapi.responses import FileResponse, Response
    dist_path = HAVEN_UI_DIR / 'dist' / 'sw.js'
    if dist_path.exists():
        return FileResponse(str(dist_path))
    # fallback to static sw.js if it exists
    static_sw = HAVEN_UI_DIR / 'static' / 'sw.js'
    if static_sw.exists():
        return FileResponse(str(static_sw))
    return Response(status_code=204)


@app.get('/haven-ui/registerSW.js')
async def register_sw():
    from fastapi.responses import FileResponse, Response
    dist_path = HAVEN_UI_DIR / 'dist' / 'registerSW.js'
    if dist_path.exists():
        return FileResponse(str(dist_path))
    static_path = HAVEN_UI_DIR / 'static' / 'registerSW.js'
    if static_path.exists():
        return FileResponse(str(static_path))
    return Response(status_code=204)


# -----------------------------------------------------------------------------
# SPA catch-all routes for React client-side routing
# These serve index.html for React routes so the React Router can handle them
# Must be defined BEFORE the StaticFiles mount processes these paths
# -----------------------------------------------------------------------------
async def _serve_spa_index():
    """Helper to serve the SPA index.html"""
    from fastapi.responses import FileResponse, HTMLResponse
    dist_index = HAVEN_UI_DIR / 'dist' / 'index.html'
    if dist_index.exists():
        return FileResponse(str(dist_index), media_type='text/html')
    static_index = HAVEN_UI_DIR / 'static' / 'index.html'
    if static_index.exists():
        return FileResponse(str(static_index), media_type='text/html')
    return HTMLResponse('<h1>Haven UI not found</h1>', status_code=404)

@app.get('/haven-ui/wizard')
async def spa_wizard():
    """Serve index.html for wizard route (create/edit systems)"""
    return await _serve_spa_index()

@app.get('/haven-ui/systems')
async def spa_systems():
    """Serve index.html for systems list route"""
    return await _serve_spa_index()

@app.get('/haven-ui/systems/{path:path}')
async def spa_systems_detail(path: str):
    """Serve index.html for system detail routes"""
    return await _serve_spa_index()

@app.get('/haven-ui/create')
async def spa_create():
    """Serve index.html for create route"""
    return await _serve_spa_index()

@app.get('/haven-ui/pending-approvals')
async def spa_pending_approvals():
    """Serve index.html for pending approvals route"""
    return await _serve_spa_index()

@app.get('/haven-ui/settings')
async def spa_settings():
    """Serve index.html for settings route"""
    return await _serve_spa_index()

@app.get('/haven-ui/discoveries')
async def spa_discoveries():
    """Serve index.html for discoveries route"""
    return await _serve_spa_index()

@app.get('/haven-ui/discoveries/{path:path}')
async def spa_discoveries_detail(path: str):
    """Serve index.html for discovery detail routes"""
    return await _serve_spa_index()

@app.get('/haven-ui/planet/{planet_id}')
async def spa_planet_view(planet_id: int):
    """Serve index.html for 3D planet view route"""
    return await _serve_spa_index()

@app.get('/war-room')
async def spa_war_room():
    """Serve index.html for War Room route"""
    return await _serve_spa_index()

@app.get('/war-room/admin')
async def spa_war_room_admin():
    """Serve index.html for War Room admin route"""
    return await _serve_spa_index()

@app.get('/haven-ui/war-room')
async def spa_haven_war_room():
    """Serve index.html for War Room route (haven-ui prefix)"""
    return await _serve_spa_index()

@app.get('/haven-ui/war-room/admin')
async def spa_haven_war_room_admin():
    """Serve index.html for War Room admin route (haven-ui prefix)"""
    return await _serve_spa_index()


@app.get('/api/status')
async def api_status():
    return {'status': 'ok', 'version': '1.36.0', 'api': 'Master Haven'}

@app.get('/api/stats')
async def api_stats():
    """Get system stats using efficient COUNT queries (no full data loading)."""
    conn = None
    try:
        db_path = get_db_path()
        if not db_path.exists():
            return {'total': 0, 'galaxies': [], 'discord_tags': {}}

        conn = get_db_connection()
        cursor = conn.cursor()

        # Direct COUNT query - O(1) with index, no data loading
        cursor.execute('SELECT COUNT(*) FROM systems')
        total = cursor.fetchone()[0]

        # Get distinct galaxies - O(n) but only returns unique values
        cursor.execute('SELECT DISTINCT galaxy FROM systems WHERE galaxy IS NOT NULL ORDER BY galaxy')
        galaxies = [row[0] for row in cursor.fetchall()]

        # Get discord_tag distribution to help debug filtering
        cursor.execute('''
            SELECT COALESCE(discord_tag, 'NULL/untagged') as tag, COUNT(*) as count
            FROM systems
            GROUP BY discord_tag
            ORDER BY count DESC
        ''')
        tag_counts = {row[0]: row[1] for row in cursor.fetchall()}

        return {'total': total, 'galaxies': galaxies, 'discord_tags': tag_counts}
    except Exception as e:
        logger.error(f"Stats query error: {e}")
        return {'total': 0, 'galaxies': []}
    finally:
        if conn:
            conn.close()


@app.get('/api/stats/daily_changes')
async def api_stats_daily_changes():
    """Get 24-hour change counts for dashboard stats.

    Returns the number of new systems, planets, moons, regions, and discoveries
    added in the last 24 hours. Uses activity_logs as the primary source since
    it reliably tracks all submissions regardless of table schema.
    """
    conn = None
    try:
        db_path = get_db_path()
        if not db_path.exists():
            return {'changes': {
                'systems': 0, 'planets': 0, 'moons': 0,
                'regions': 0, 'discoveries': 0
            }}

        conn = get_db_connection()
        cursor = conn.cursor()

        changes = {}

        # Use activity_logs to count approved systems in the last 24 hours
        # This is more reliable than created_at which may not exist on older databases
        cursor.execute("""
            SELECT COUNT(*) FROM activity_logs
            WHERE event_type IN ('system_approved', 'system_saved')
            AND timestamp >= datetime('now', '-1 day')
        """)
        system_changes = cursor.fetchone()[0]
        changes['systems'] = system_changes

        # For planets and moons, extract system names from activity logs
        # and count their planets/moons directly
        if system_changes > 0:
            # Get system names from recent activity logs
            # Message format is typically "System 'SystemName' approved" or similar
            cursor.execute("""
                SELECT message FROM activity_logs
                WHERE event_type IN ('system_approved', 'system_saved')
                AND timestamp >= datetime('now', '-1 day')
            """)
            messages = [row[0] for row in cursor.fetchall()]

            # Extract system names from messages and find their IDs
            # Message format: "System 'SystemName' approved and ..."
            system_ids = []
            for msg in messages:
                match = re.search(r"System '([^']+)'", msg)
                if match:
                    system_name = match.group(1).strip()
                    cursor.execute("SELECT id FROM systems WHERE name = ?", (system_name,))
                    row = cursor.fetchone()
                    if row:
                        system_ids.append(row[0])

            if system_ids:
                # Count planets for these systems
                placeholders = ','.join('?' * len(system_ids))
                cursor.execute(f"""
                    SELECT COUNT(*) FROM planets WHERE system_id IN ({placeholders})
                """, system_ids)
                changes['planets'] = cursor.fetchone()[0]

                # Count moons for these systems
                cursor.execute(f"""
                    SELECT COUNT(*) FROM moons m
                    JOIN planets p ON m.planet_id = p.id
                    WHERE p.system_id IN ({placeholders})
                """, system_ids)
                changes['moons'] = cursor.fetchone()[0]
            else:
                # Fallback: estimate based on system count
                changes['planets'] = system_changes * 3
                changes['moons'] = system_changes
        else:
            changes['planets'] = 0
            changes['moons'] = 0

        # Regions from activity_logs
        cursor.execute("""
            SELECT COUNT(*) FROM activity_logs
            WHERE event_type = 'region_approved'
            AND timestamp >= datetime('now', '-1 day')
        """)
        changes['regions'] = cursor.fetchone()[0]

        # Discoveries from activity_logs
        cursor.execute("""
            SELECT COUNT(*) FROM activity_logs
            WHERE event_type = 'discovery_added'
            AND timestamp >= datetime('now', '-1 day')
        """)
        changes['discoveries'] = cursor.fetchone()[0]

        return {'changes': changes}
    except Exception as e:
        logger.error(f"Daily changes query error: {e}")
        return {'changes': {
            'systems': 0, 'planets': 0, 'moons': 0,
            'regions': 0, 'discoveries': 0
        }}
    finally:
        if conn:
            conn.close()


@app.get('/api/map/regions-aggregated')
async def api_map_regions_aggregated(
    reality: str = None,
    galaxy: str = None
):
    """Get pre-aggregated region data for the 3D galaxy map.

    Args:
        reality: Optional filter - 'Normal' or 'Permadeath' (None for all)
        galaxy: Optional filter - galaxy name like 'Euclid' (None for all)

    Returns one data point per region with:
    - Region coordinates (region_x, region_y, region_z)
    - Display coordinates (x, y, z) from the first system
    - System count
    - Custom region name if set
    - List of galaxies present

    This is MUCH faster than loading all individual systems,
    as it uses SQL aggregation instead of Python-side processing.
    """
    conn = None
    try:
        db_path = get_db_path()
        if not db_path.exists():
            return {'regions': [], 'total_systems': 0, 'total_regions': 0}

        conn = get_db_connection()
        cursor = conn.cursor()

        # Build WHERE clause with optional filters
        where_clauses = ["s.region_x IS NOT NULL AND s.region_y IS NOT NULL AND s.region_z IS NOT NULL"]
        params = []

        if reality:
            where_clauses.append("s.reality = ?")
            params.append(reality)
        if galaxy:
            where_clauses.append("s.galaxy = ?")
            params.append(galaxy)

        where_sql = " AND ".join(where_clauses)

        # Single aggregated query - returns one row per populated region
        # Includes discord_tag info for custom region coloring
        cursor.execute(f'''
            SELECT
                s.region_x,
                s.region_y,
                s.region_z,
                r.custom_name as region_name,
                COUNT(*) as system_count,
                MIN(s.x) as display_x,
                MIN(s.y) as display_y,
                MIN(s.z) as display_z,
                GROUP_CONCAT(DISTINCT s.galaxy) as galaxies,
                GROUP_CONCAT(DISTINCT s.reality) as realities,
                GROUP_CONCAT(DISTINCT s.discord_tag) as discord_tags
            FROM systems s
            LEFT JOIN regions r ON s.region_x = r.region_x
                AND s.region_y = r.region_y AND s.region_z = r.region_z
                AND COALESCE(s.reality, 'Normal') = COALESCE(r.reality, 'Normal')
                AND COALESCE(s.galaxy, 'Euclid') = COALESCE(r.galaxy, 'Euclid')
            WHERE {where_sql}
            GROUP BY s.region_x, s.region_y, s.region_z
            ORDER BY system_count DESC
        ''', params)

        rows = cursor.fetchall()
        total_systems = 0
        regions = []

        for row in rows:
            region = dict(row)
            total_systems += region['system_count']
            # Parse galaxies string into list
            if region['galaxies']:
                region['galaxies'] = region['galaxies'].split(',')
            else:
                region['galaxies'] = ['Euclid']
            # Parse realities string into list
            if region.get('realities'):
                region['realities'] = region['realities'].split(',')
            else:
                region['realities'] = ['Normal']
            # Parse discord_tags string into list (filter out None values)
            if region.get('discord_tags'):
                tags = [t for t in region['discord_tags'].split(',') if t and t != 'None']
                region['discord_tags'] = tags
                # Set dominant_tag as the first non-null tag (most common in the region)
                region['dominant_tag'] = tags[0] if tags else None
            else:
                region['discord_tags'] = []
                region['dominant_tag'] = None
            regions.append(region)

        return {
            'regions': regions,
            'total_systems': total_systems,
            'total_regions': len(regions)
        }

    except Exception as e:
        logger.error(f"Map aggregation error: {e}")
        return {'regions': [], 'total_systems': 0, 'total_regions': 0}
    finally:
        if conn:
            conn.close()


@app.get('/api/galaxies')
async def api_galaxies():
    """Return list of all 256 NMS galaxies with indices.

    Returns:
        Dictionary with galaxies list, each containing index and name.
        Note: Index is 1-based for public display (Euclid = 1, not 0).
    """
    return {
        'galaxies': [
            {'index': idx + 1, 'name': name}
            for idx, name in sorted(GALAXY_BY_INDEX.items())
        ]
    }


@app.get('/api/realities/summary')
async def api_realities_summary():
    """Level 1 Hierarchy: Returns reality-level aggregation.

    Used by the containerized Systems page to show Normal vs Permadeath
    with counts before drilling down into galaxies.

    Returns:
        Dictionary with realities list, each containing:
        - reality: 'Normal' or 'Permadeath'
        - galaxy_count: Number of distinct galaxies with data
        - system_count: Total systems in this reality
    """
    conn = None
    try:
        db_path = get_db_path()
        if not db_path.exists():
            return {'realities': []}

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT
                COALESCE(reality, 'Normal') as reality,
                COUNT(DISTINCT galaxy) as galaxy_count,
                COUNT(*) as system_count
            FROM systems
            GROUP BY COALESCE(reality, 'Normal')
            ORDER BY system_count DESC
        ''')
        results = [dict(row) for row in cursor.fetchall()]
        return {'realities': results}
    except Exception as e:
        logger.error(f"Realities summary error: {e}")
        return {'realities': []}
    finally:
        if conn:
            conn.close()


@app.get('/api/galaxies/summary')
async def api_galaxies_summary(
    reality: str = None,
    star_type: str = None,
    economy_type: str = None,
    economy_level: str = None,
    conflict_level: str = None,
    dominant_lifeform: str = None,
    stellar_classification: str = None,
    biome: str = None,
    weather: str = None,
    sentinel_level: str = None,
    resource: str = None,
    has_moons: bool = None,
    min_planets: int = None,
    max_planets: int = None,
    is_complete: bool = None,
    discord_tag: str = None
):
    """Level 2 Hierarchy: Returns galaxy-level aggregation within a reality.

    Used by the containerized Systems page to show galaxies with counts
    after selecting a reality. Supports advanced filters to show only
    galaxies containing systems that match the filter criteria.

    Returns:
        Dictionary with galaxies list, each containing:
        - galaxy: Galaxy name (e.g., 'Euclid', 'Eissentam')
        - region_count: Number of distinct regions with data
        - system_count: Total systems in this galaxy
    """
    conn = None
    try:
        db_path = get_db_path()
        if not db_path.exists():
            return {'galaxies': []}

        conn = get_db_connection()
        cursor = conn.cursor()

        where_clauses = []
        params = []

        if reality:
            where_clauses.append("COALESCE(s.reality, 'Normal') = ?")
            params.append(reality)

        if discord_tag and discord_tag != 'all':
            if discord_tag == 'untagged':
                where_clauses.append("(s.discord_tag IS NULL OR s.discord_tag = '')")
            elif discord_tag == 'personal':
                where_clauses.append("s.discord_tag = 'personal'")
            else:
                where_clauses.append("s.discord_tag = ?")
                params.append(discord_tag)

        # Advanced filters
        _build_advanced_filter_clauses({
            'star_type': star_type,
            'economy_type': economy_type,
            'economy_level': economy_level,
            'conflict_level': conflict_level,
            'dominant_lifeform': dominant_lifeform,
            'stellar_classification': stellar_classification,
            'biome': biome,
            'weather': weather,
            'sentinel_level': sentinel_level,
            'resource': resource,
            'has_moons': has_moons,
            'min_planets': min_planets,
            'max_planets': max_planets,
            'is_complete': is_complete,
        }, where_clauses, params)

        where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

        cursor.execute(f'''
            SELECT
                COALESCE(s.galaxy, 'Euclid') as galaxy,
                COUNT(DISTINCT s.region_x || '-' || s.region_y || '-' || s.region_z) as region_count,
                COUNT(*) as system_count,
                SUM(CASE WHEN COALESCE(s.is_complete, 0) >= 85 THEN 1 ELSE 0 END) as grade_s,
                SUM(CASE WHEN COALESCE(s.is_complete, 0) >= 65 AND COALESCE(s.is_complete, 0) < 85 THEN 1 ELSE 0 END) as grade_a,
                SUM(CASE WHEN COALESCE(s.is_complete, 0) >= 40 AND COALESCE(s.is_complete, 0) < 65 THEN 1 ELSE 0 END) as grade_b,
                SUM(CASE WHEN COALESCE(s.is_complete, 0) < 40 THEN 1 ELSE 0 END) as grade_c,
                ROUND(AVG(COALESCE(s.is_complete, 0)), 1) as avg_score
            FROM systems s
            {where_sql}
            GROUP BY COALESCE(s.galaxy, 'Euclid')
            ORDER BY system_count DESC
        ''', params)

        results = [dict(row) for row in cursor.fetchall()]
        return {'galaxies': results, 'reality': reality}
    except Exception as e:
        logger.error(f"Galaxies summary error: {e}")
        return {'galaxies': [], 'reality': reality}
    finally:
        if conn:
            conn.close()


@app.get('/api/activity_logs')
async def api_activity_logs(limit: int = 50):
    """Get recent activity logs for the dashboard.

    Args:
        limit: Maximum number of logs to return (default 50, max 100)
    """
    limit = min(limit, 100)  # Cap at 100
    conn = None
    try:
        db_path = get_db_path()
        if not db_path.exists():
            return {'logs': []}
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, timestamp, event_type, message, details, user_name
            FROM activity_logs
            ORDER BY timestamp DESC
            LIMIT ?
        ''', (limit,))
        rows = cursor.fetchall()
        logs = [dict(row) for row in rows]
        return {'logs': logs}
    except Exception as e:
        logger.error(f"Failed to fetch activity logs: {e}")
        return {'logs': []}
    finally:
        if conn:
            conn.close()


@app.get('/api/systems/recent')
async def api_recent_systems(limit: int = 10):
    """Get most recently added/modified systems for dashboard display.

    This is a lightweight endpoint that returns only basic system info
    without loading planets, moons, or discoveries. Uses index on created_at.

    Args:
        limit: Maximum number of systems to return (default 10, max 50)
    """
    limit = min(limit, 50)  # Cap at 50
    conn = None
    try:
        db_path = get_db_path()
        if not db_path.exists():
            return {'systems': []}

        conn = get_db_connection()
        cursor = conn.cursor()

        # Fast query using index on created_at, returns only essential fields
        cursor.execute('''
            SELECT id, name, galaxy, glyph_code, region_x, region_y, region_z,
                   created_at, star_type,
                   (SELECT COUNT(*) FROM planets WHERE system_id = systems.id) as planet_count
            FROM systems
            ORDER BY created_at DESC NULLS LAST, id DESC
            LIMIT ?
        ''', (limit,))

        rows = cursor.fetchall()
        systems = []
        for row in rows:
            system = dict(row)
            # Add planets as empty list with just the count for display
            system['planets'] = [None] * system.get('planet_count', 0)
            systems.append(system)

        return {'systems': systems}

    except Exception as e:
        logger.error(f"Failed to fetch recent systems: {e}")
        return {'systems': []}
    finally:
        if conn:
            conn.close()


# Glyph operations
@app.post('/api/decode_glyph')
async def api_decode_glyph(payload: dict):
    """
    Decode a portal glyph to coordinates.

    Request: {"glyph": "10A4F3E7B2C1", "apply_scale": true}
    Response: {"x": -1343, "y": 115, "z": 1659, "planet": 1, ...}
    """
    glyph = payload.get('glyph', '').strip().upper()
    apply_scale = payload.get('apply_scale', False)

    if not glyph:
        raise HTTPException(status_code=400, detail="Missing glyph code")

    is_valid, error = validate_glyph_code(glyph)
    if not is_valid:
        raise HTTPException(status_code=400, detail=error)

    try:
        result = decode_glyph_to_coords(glyph, apply_scale=apply_scale)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post('/api/encode_glyph')
async def api_encode_glyph(payload: dict):
    """
    Encode coordinates to a portal glyph.

    Request: {"x": 500, "y": -50, "z": -1200, "planet": 0, "solar_system": 1}
    Response: {"glyph": "0-001-4E-350-9F4", "glyph_raw": "00014E3509F4"}
    """
    try:
        x = int(payload.get('x', 0))
        y = int(payload.get('y', 0))
        z = int(payload.get('z', 0))
        planet = int(payload.get('planet', 0))
        solar_system = int(payload.get('solar_system', 1))

        glyph = encode_coords_to_glyph(x, y, z, planet, solar_system)
        return {
            'glyph': format_glyph(glyph),
            'glyph_raw': glyph
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get('/api/glyph_images')
async def api_glyph_images():
    """
    Get mapping of hex digits to glyph image filenames.

    Response: {"0": "IMG_9202.jpg", "1": "IMG_9203.jpg", ...}
    """
    return GLYPH_IMAGES


@app.post('/api/validate_glyph')
async def api_validate_glyph(payload: dict):
    """
    Validate a glyph code without decoding.

    Request: {"glyph": "10A4F3E7B2C1"}
    Response: {"valid": true, "warning": null} or {"valid": false, "error": "..."}
    """
    glyph = payload.get('glyph', '').strip().upper()

    if not glyph:
        return {'valid': False, 'error': 'Missing glyph code'}

    is_valid, message = validate_glyph_code(glyph)

    if is_valid and message:
        # Has warnings
        return {'valid': True, 'warning': message}
    elif is_valid:
        return {'valid': True, 'warning': None}
    else:
        return {'valid': False, 'error': message}

# Settings storage (simple JSON-based)
_settings_cache = {}

@app.get('/api/settings')
async def get_settings():
    """Get current settings (theme, etc.)"""
    return _settings_cache

@app.post('/api/settings')
async def save_settings(settings: dict):
    """Save settings"""
    _settings_cache.update(settings)
    # Persist personal_color to database if provided
    if 'personal_color' in settings:
        set_personal_color(settings['personal_color'])
    return {'status': 'ok'}

# Admin authentication (session-based with cookies)
from fastapi import Response, Cookie
from typing import Optional
import secrets

# ============================================================================
# Multi-Tenant Authentication System
# ============================================================================

# Super admin credentials
SUPER_ADMIN_USERNAME = "Haven"
DEFAULT_SUPER_ADMIN_PASSWORD_HASH = hashlib.sha256("WhrStrsG".encode()).hexdigest()

def get_super_admin_password_hash() -> str:
    """Get super admin password hash from database, or return default if not set"""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM super_admin_settings WHERE key = 'password_hash'")
        row = cursor.fetchone()
        if row:
            return row['value']
    except Exception as e:
        logger.warning(f"Failed to get super admin password from DB: {e}")
    finally:
        if conn:
            conn.close()
    return DEFAULT_SUPER_ADMIN_PASSWORD_HASH

def set_super_admin_password_hash(password_hash: str) -> bool:
    """Store super admin password hash in database"""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO super_admin_settings (key, value, updated_at)
            VALUES ('password_hash', ?, ?)
        ''', (password_hash, datetime.now(timezone.utc).isoformat()))
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Failed to set super admin password: {e}")
        return False
    finally:
        if conn:
            conn.close()

# Default personal submission color (fuchsia)
DEFAULT_PERSONAL_COLOR = '#c026d3'

def get_personal_color() -> str:
    """Get personal submission color from database, or return default"""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM super_admin_settings WHERE key = 'personal_color'")
        row = cursor.fetchone()
        if row:
            return row['value']
    except Exception as e:
        logger.warning(f"Failed to get personal color from DB: {e}")
    finally:
        if conn:
            conn.close()
    return DEFAULT_PERSONAL_COLOR

def set_personal_color(color: str) -> bool:
    """Store personal submission color in database"""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO super_admin_settings (key, value, updated_at)
            VALUES ('personal_color', ?, ?)
        ''', (color, datetime.now(timezone.utc).isoformat()))
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Failed to set personal color: {e}")
        return False
    finally:
        if conn:
            conn.close()

# Session storage: session_token -> session_data
# Session data structure: {
#   'user_type': 'super_admin' | 'partner',
#   'username': str,
#   'discord_tag': str | None,  # Only for partners
#   'partner_id': int | None,   # Only for partners
#   'display_name': str | None,
#   'enabled_features': list,
#   'expires_at': datetime
# }
_sessions: Dict[str, dict] = {}

def hash_password(password: str) -> str:
    """Hash a password using SHA-256"""
    return hashlib.sha256(password.encode()).hexdigest()

def generate_session_token() -> str:
    """Generate a secure random session token"""
    return secrets.token_urlsafe(32)

def get_session(session_token: Optional[str]) -> Optional[dict]:
    """Get session data if token is valid and not expired"""
    if not session_token or session_token not in _sessions:
        return None
    session = _sessions[session_token]
    if datetime.now(timezone.utc) > session.get('expires_at', datetime.min.replace(tzinfo=timezone.utc)):
        del _sessions[session_token]
        return None
    return session

def verify_session(session_token: Optional[str]) -> bool:
    """Check if session token is valid (backward compatibility)"""
    return get_session(session_token) is not None

def is_super_admin(session_token: Optional[str]) -> bool:
    """Check if session belongs to super admin"""
    session = get_session(session_token)
    return session is not None and session.get('user_type') == 'super_admin'

def is_partner(session_token: Optional[str]) -> bool:
    """Check if session belongs to a partner"""
    session = get_session(session_token)
    return session is not None and session.get('user_type') == 'partner'

def get_partner_discord_tag(session_token: Optional[str]) -> Optional[str]:
    """Get the discord_tag for a partner session"""
    session = get_session(session_token)
    if session and session.get('user_type') == 'partner':
        return session.get('discord_tag')
    return None

def can_access_feature(session_token: Optional[str], feature: str) -> bool:
    """Check if current user can access a specific feature"""
    session = get_session(session_token)
    if not session:
        return False
    if session.get('user_type') == 'super_admin':
        return True
    enabled = session.get('enabled_features', [])
    if 'all' in enabled:
        return True
    return feature in enabled

def is_sub_admin(session_token: Optional[str]) -> bool:
    """Check if session belongs to a sub-admin"""
    session = get_session(session_token)
    return session is not None and session.get('user_type') == 'sub_admin'

def get_effective_discord_tag(session_token: Optional[str]) -> Optional[str]:
    """Get discord_tag - direct for partners, inherited for sub-admins"""
    session = get_session(session_token)
    if not session:
        return None
    if session.get('user_type') in ['partner', 'sub_admin']:
        return session.get('discord_tag')
    return None

def get_submitter_identity(session_token: Optional[str]) -> dict:
    """Get full identity info for audit and self-approval detection purposes"""
    session = get_session(session_token)
    if not session:
        return {'type': 'anonymous', 'username': None, 'account_id': None, 'discord_tag': None}

    user_type = session.get('user_type')
    account_id = None
    if user_type == 'partner':
        account_id = session.get('partner_id')
    elif user_type == 'sub_admin':
        account_id = session.get('sub_admin_id')

    return {
        'type': user_type,
        'username': session.get('username'),
        'account_id': account_id,
        'discord_tag': session.get('discord_tag')
    }

# ============================================================================
# DATA RESTRICTION HELPER FUNCTIONS
# ============================================================================

# Fields that can be restricted and what they hide
RESTRICTABLE_FIELDS = {
    'coordinates': ['x', 'y', 'z', 'region_x', 'region_y', 'region_z'],
    'glyph_code': ['glyph_code', 'glyph_planet', 'glyph_solar_system'],
    'discovered_by': ['discovered_by', 'discovered_at', 'personal_discord_username'],
    'base_location': [],  # Applied to planets
    'description': ['description'],
    'star_type': ['star_type', 'economy_type', 'economy_level', 'conflict_level'],
    'planets': [],  # Special handling - hides planet details
}

def get_restriction_for_system(system_id: int) -> Optional[dict]:
    """Get restriction settings for a system, or None if unrestricted."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, system_id, discord_tag, is_hidden_from_public, hidden_fields,
                   map_visibility, created_at, updated_at, created_by
            FROM data_restrictions WHERE system_id = ?
        ''', (system_id,))
        row = cursor.fetchone()
        if row:
            return {
                'id': row['id'],
                'system_id': row['system_id'],
                'discord_tag': row['discord_tag'],
                'is_hidden_from_public': bool(row['is_hidden_from_public']),
                'hidden_fields': json.loads(row['hidden_fields'] or '[]'),
                'map_visibility': row['map_visibility'] or 'normal',
                'created_at': row['created_at'],
                'updated_at': row['updated_at'],
                'created_by': row['created_by']
            }
        return None
    except Exception as e:
        logger.error(f"Failed to get restriction for system {system_id}: {e}")
        return None
    finally:
        if conn:
            conn.close()


def get_restrictions_batch(system_ids: list) -> dict:
    """Batch fetch restrictions for multiple systems in a single query.

    PERFORMANCE: This replaces N individual queries with 1 query, dramatically
    improving performance when filtering large lists of systems.

    Args:
        system_ids: List of system IDs to fetch restrictions for

    Returns:
        Dict mapping system_id -> restriction dict (only for systems with restrictions)
    """
    if not system_ids:
        return {}

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Use IN clause with placeholders for batch query
        placeholders = ','.join('?' * len(system_ids))
        cursor.execute(f'''
            SELECT id, system_id, discord_tag, is_hidden_from_public, hidden_fields,
                   map_visibility, created_at, updated_at, created_by
            FROM data_restrictions WHERE system_id IN ({placeholders})
        ''', system_ids)

        restrictions = {}
        for row in cursor.fetchall():
            restrictions[row['system_id']] = {
                'id': row['id'],
                'system_id': row['system_id'],
                'discord_tag': row['discord_tag'],
                'is_hidden_from_public': bool(row['is_hidden_from_public']),
                'hidden_fields': json.loads(row['hidden_fields'] or '[]'),
                'map_visibility': row['map_visibility'] or 'normal',
                'created_at': row['created_at'],
                'updated_at': row['updated_at'],
                'created_by': row['created_by']
            }
        return restrictions
    except Exception as e:
        logger.error(f"Failed to batch fetch restrictions: {e}")
        return {}
    finally:
        if conn:
            conn.close()

def get_restrictions_by_discord_tag(discord_tag: str) -> list:
    """Get all restrictions for a specific discord_tag."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT dr.*, s.name as system_name, s.galaxy
            FROM data_restrictions dr
            JOIN systems s ON dr.system_id = s.id
            WHERE dr.discord_tag = ?
            ORDER BY s.name
        ''', (discord_tag,))
        rows = cursor.fetchall()
        return [{
            'id': row['id'],
            'system_id': row['system_id'],
            'system_name': row['system_name'],
            'galaxy': row['galaxy'],
            'discord_tag': row['discord_tag'],
            'is_hidden_from_public': bool(row['is_hidden_from_public']),
            'hidden_fields': json.loads(row['hidden_fields'] or '[]'),
            'map_visibility': row['map_visibility'] or 'normal',
            'created_at': row['created_at'],
            'updated_at': row['updated_at'],
            'created_by': row['created_by']
        } for row in rows]
    except Exception as e:
        logger.error(f"Failed to get restrictions for tag {discord_tag}: {e}")
        return []
    finally:
        if conn:
            conn.close()

def can_bypass_restriction(session_data: Optional[dict], system_discord_tag: str) -> bool:
    """Check if current user can bypass restrictions for a system.

    Super admin can always bypass.
    Partners can bypass for systems with their own discord_tag.
    """
    if not session_data:
        return False
    if session_data.get('user_type') == 'super_admin':
        return True
    if session_data.get('user_type') == 'partner':
        return session_data.get('discord_tag') == system_discord_tag
    return False

def apply_field_restrictions(system: dict, hidden_fields: list) -> dict:
    """Remove restricted fields from system data. Returns a modified copy."""
    if not hidden_fields:
        return system

    result = dict(system)

    for field_group in hidden_fields:
        if field_group in RESTRICTABLE_FIELDS:
            # Remove each field in the group
            for field in RESTRICTABLE_FIELDS[field_group]:
                if field in result:
                    del result[field]

        # Special handling for planets - hide detailed info
        if field_group == 'planets' and 'planets' in result:
            # Keep only planet count, not details
            planet_count = len(result.get('planets', []))
            result['planets'] = []
            result['planet_count_only'] = planet_count

        # Special handling for base_location - remove from each planet
        if field_group == 'base_location' and 'planets' in result:
            for planet in result.get('planets', []):
                if 'base_location' in planet:
                    del planet['base_location']

    return result

def apply_data_restrictions(systems: list, session_data: Optional[dict], for_map: bool = False) -> list:
    """Filter systems based on data restrictions and viewer permissions.

    PERFORMANCE OPTIMIZED: Uses batch query to fetch all restrictions at once,
    instead of N individual queries. This dramatically improves performance
    for large system lists (e.g., 6000+ systems reduced from 6000 queries to 1).

    Args:
        systems: List of system dictionaries
        session_data: Current session data (None for public)
        for_map: If True, also filters based on map_visibility setting

    Returns:
        Filtered list with restrictions applied
    """
    if not systems:
        return systems

    # Super admin sees everything
    if session_data and session_data.get('user_type') == 'super_admin':
        return systems

    viewer_discord_tag = None
    if session_data and session_data.get('user_type') == 'partner':
        viewer_discord_tag = session_data.get('discord_tag')

    # OPTIMIZATION: Batch fetch all restrictions in ONE query instead of N queries
    system_ids = [s.get('id') for s in systems if s.get('id')]
    restrictions_map = get_restrictions_batch(system_ids) if system_ids else {}

    result = []
    for system in systems:
        system_id = system.get('id')
        system_tag = system.get('discord_tag')

        # Owner sees their own systems unrestricted
        if viewer_discord_tag and viewer_discord_tag == system_tag:
            result.append(system)
            continue

        # Check for restrictions using pre-fetched map
        restriction = restrictions_map.get(system_id) if system_id else None

        if not restriction:
            # No restrictions - include as-is
            result.append(system)
            continue

        # System is hidden from public
        if restriction.get('is_hidden_from_public'):
            continue  # Skip this system entirely

        # For map view, check map visibility
        if for_map:
            map_vis = restriction.get('map_visibility', 'normal')
            if map_vis == 'hidden':
                continue  # Don't show on map
            elif map_vis == 'point_only':
                # Strip hover/detail info - keep only position data
                filtered_system = {
                    'id': system.get('id'),
                    'name': system.get('name'),
                    'x': system.get('x'),
                    'y': system.get('y'),
                    'z': system.get('z'),
                    'star_x': system.get('star_x'),
                    'star_y': system.get('star_y'),
                    'star_z': system.get('star_z'),
                    'galaxy': system.get('galaxy'),
                    'map_visibility': 'point_only',
                    'planets': []
                }
                result.append(filtered_system)
                continue

        # Apply field restrictions
        hidden_fields = restriction.get('hidden_fields', [])
        filtered_system = apply_field_restrictions(system, hidden_fields)
        result.append(filtered_system)

    return result

def check_rate_limit(client_ip: str, limit: int = 60, window_hours: int = 1) -> tuple:
    """
    Check if IP has exceeded rate limit for system submissions.
    Returns (is_allowed, remaining_requests).
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        window_start = (datetime.now(timezone.utc) - timedelta(hours=window_hours)).isoformat()
        cursor.execute('''
            SELECT COUNT(*) FROM pending_systems
            WHERE submitted_by_ip = ? AND submission_date >= ?
        ''', (client_ip, window_start))
        count = cursor.fetchone()[0]
        return (count < limit, max(0, limit - count))
    except Exception as e:
        logger.warning(f"Rate limit check failed: {e}")
        return (True, limit)  # Fail open
    finally:
        if conn:
            conn.close()

@app.get('/api/admin/status')
async def admin_status(session: Optional[str] = Cookie(None)):
    """Check login status and return user info"""
    session_data = get_session(session)
    if not session_data:
        return {'logged_in': False}

    user_type = session_data.get('user_type')
    account_id = None
    if user_type == 'partner':
        account_id = session_data.get('partner_id')
    elif user_type == 'sub_admin':
        account_id = session_data.get('sub_admin_id')

    return {
        'logged_in': True,
        'user_type': user_type,
        'username': session_data.get('username'),
        'discord_tag': session_data.get('discord_tag'),
        'display_name': session_data.get('display_name'),
        'enabled_features': session_data.get('enabled_features', []),
        'account_id': account_id,
        'parent_display_name': session_data.get('parent_display_name'),  # For sub-admins
        'is_haven_sub_admin': session_data.get('is_haven_sub_admin', False)  # True if sub-admin under Haven
    }

@app.post('/api/admin/login')
async def admin_login(credentials: dict, response: Response):
    """Login with username/password - supports super admin, partners, and sub-admins"""
    username = credentials.get('username', '').strip()
    password = credentials.get('password', '')

    # Check super admin
    if username == SUPER_ADMIN_USERNAME:
        if hash_password(password) == get_super_admin_password_hash():
            session_token = generate_session_token()
            _sessions[session_token] = {
                'user_type': 'super_admin',
                'username': username,
                'discord_tag': None,
                'partner_id': None,
                'display_name': 'Super Admin',
                'enabled_features': ['all'],
                'expires_at': datetime.now(timezone.utc) + timedelta(minutes=10)
            }
            response.set_cookie(
                key='session',
                value=session_token,
                httponly=True,
                max_age=600,  # 10 minutes
                samesite='lax'
            )
            return {
                'status': 'ok',
                'logged_in': True,
                'user_type': 'super_admin',
                'username': username
            }
        raise HTTPException(status_code=401, detail='Invalid password')

    # Check partner accounts and sub-admin accounts
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # First check partner_accounts
        cursor.execute('''
            SELECT id, password_hash, discord_tag, display_name, enabled_features, is_active
            FROM partner_accounts WHERE username = ?
        ''', (username,))
        row = cursor.fetchone()

        if row:
            # Found a partner account
            if not row['is_active']:
                raise HTTPException(status_code=401, detail='Account is deactivated')

            if hash_password(password) != row['password_hash']:
                raise HTTPException(status_code=401, detail='Invalid username or password')

            # Update last_login_at
            cursor.execute(
                'UPDATE partner_accounts SET last_login_at = ? WHERE id = ?',
                (datetime.now(timezone.utc).isoformat(), row['id'])
            )
            conn.commit()

            enabled_features = json.loads(row['enabled_features'] or '[]')

            session_token = generate_session_token()
            _sessions[session_token] = {
                'user_type': 'partner',
                'username': username,
                'discord_tag': row['discord_tag'],
                'partner_id': row['id'],
                'display_name': row['display_name'] or username,
                'enabled_features': enabled_features,
                'expires_at': datetime.now(timezone.utc) + timedelta(minutes=10)
            }

            response.set_cookie(
                key='session',
                value=session_token,
                httponly=True,
                max_age=600,  # 10 minutes
                samesite='lax'
            )

            return {
                'status': 'ok',
                'logged_in': True,
                'user_type': 'partner',
                'username': username,
                'discord_tag': row['discord_tag'],
                'display_name': row['display_name'] or username,
                'enabled_features': enabled_features
            }

        # Not a partner - check sub_admin_accounts
        cursor.execute('''
            SELECT sa.id, sa.password_hash, sa.display_name, sa.enabled_features, sa.is_active,
                   sa.parent_partner_id, sa.additional_discord_tags, sa.can_approve_personal_uploads,
                   pa.discord_tag as parent_discord_tag, pa.display_name as parent_display_name,
                   pa.is_active as parent_is_active
            FROM sub_admin_accounts sa
            LEFT JOIN partner_accounts pa ON sa.parent_partner_id = pa.id
            WHERE sa.username = ?
        ''', (username,))
        sub_row = cursor.fetchone()

        if not sub_row:
            raise HTTPException(status_code=401, detail='Invalid username or password')

        # Check if sub-admin account is active
        if not sub_row['is_active']:
            raise HTTPException(status_code=401, detail='Account is deactivated')

        # Check if parent partner account is active (only if has a parent)
        if sub_row['parent_partner_id'] and not sub_row['parent_is_active']:
            raise HTTPException(status_code=401, detail='Parent partner account is deactivated')

        if hash_password(password) != sub_row['password_hash']:
            raise HTTPException(status_code=401, detail='Invalid username or password')

        # Update last_login_at
        cursor.execute(
            'UPDATE sub_admin_accounts SET last_login_at = ? WHERE id = ?',
            (datetime.now(timezone.utc).isoformat(), sub_row['id'])
        )
        conn.commit()

        # Sub-admin features are their own (subset of parent's, or any for Haven sub-admins)
        enabled_features = json.loads(sub_row['enabled_features'] or '[]')

        # Haven sub-admins have no parent partner
        is_haven_sub_admin = sub_row['parent_partner_id'] is None
        discord_tag = None if is_haven_sub_admin else sub_row['parent_discord_tag']
        parent_display_name = 'Haven' if is_haven_sub_admin else sub_row['parent_display_name']

        # Get additional discord tags and personal uploads permission for Haven sub-admins
        sub_row_dict = dict(sub_row)
        additional_discord_tags = json.loads(sub_row_dict.get('additional_discord_tags') or '[]') if is_haven_sub_admin else []
        can_approve_personal_uploads = bool(sub_row_dict.get('can_approve_personal_uploads', 0)) if is_haven_sub_admin else False

        session_token = generate_session_token()
        _sessions[session_token] = {
            'user_type': 'sub_admin',
            'username': username,
            'discord_tag': discord_tag,  # Inherit parent's discord_tag (None for Haven sub-admins)
            'sub_admin_id': sub_row['id'],
            'partner_id': sub_row['parent_partner_id'],  # None for Haven sub-admins
            'display_name': sub_row['display_name'] or username,
            'parent_display_name': parent_display_name,
            'enabled_features': enabled_features,
            'is_haven_sub_admin': is_haven_sub_admin,
            'additional_discord_tags': additional_discord_tags,  # Extra discord tags this Haven sub-admin can see
            'can_approve_personal_uploads': can_approve_personal_uploads,  # Permission to approve personal uploads (without discord tag)
            'expires_at': datetime.now(timezone.utc) + timedelta(minutes=10)
        }

        response.set_cookie(
            key='session',
            value=session_token,
            httponly=True,
            max_age=600,  # 10 minutes
            samesite='lax'
        )

        return {
            'status': 'ok',
            'logged_in': True,
            'user_type': 'sub_admin',
            'username': username,
            'discord_tag': discord_tag,
            'display_name': sub_row['display_name'] or username,
            'parent_display_name': parent_display_name,
            'enabled_features': enabled_features,
            'is_haven_sub_admin': is_haven_sub_admin
        }
    finally:
        if conn:
            conn.close()

@app.post('/api/admin/logout')
async def admin_logout(response: Response, session: Optional[str] = Cookie(None)):
    """Logout - clears session"""
    if session and session in _sessions:
        del _sessions[session]
    response.delete_cookie('session')
    return {'status': 'ok'}


@app.post('/api/change_password')
async def change_password(payload: dict, session: Optional[str] = Cookie(None)):
    """
    Change password for the currently logged-in user.
    Works for both super admin and partner accounts.
    Requires current password for verification.
    """
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail='Not authenticated')

    current_password = payload.get('current_password', '')
    new_password = payload.get('new_password', '')

    if not current_password:
        raise HTTPException(status_code=400, detail='Current password is required')

    if not new_password or len(new_password) < 4:
        raise HTTPException(status_code=400, detail='New password must be at least 4 characters')

    user_type = session_data.get('user_type')

    if user_type == 'super_admin':
        # Verify current password
        if hash_password(current_password) != get_super_admin_password_hash():
            raise HTTPException(status_code=401, detail='Current password is incorrect')

        # Set new password
        if set_super_admin_password_hash(hash_password(new_password)):
            logger.info("Super admin password changed successfully")
            return {'status': 'ok', 'message': 'Password changed successfully'}
        else:
            raise HTTPException(status_code=500, detail='Failed to save new password')

    elif user_type == 'partner':
        partner_id = session_data.get('partner_id')
        if not partner_id:
            raise HTTPException(status_code=400, detail='Invalid session')

        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            # Get current password hash
            cursor.execute('SELECT password_hash FROM partner_accounts WHERE id = ?', (partner_id,))
            row = cursor.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail='Account not found')

            # Verify current password
            if hash_password(current_password) != row['password_hash']:
                raise HTTPException(status_code=401, detail='Current password is incorrect')

            # Update password
            cursor.execute(
                'UPDATE partner_accounts SET password_hash = ?, updated_at = ? WHERE id = ?',
                (hash_password(new_password), datetime.now(timezone.utc).isoformat(), partner_id)
            )
            conn.commit()

            logger.info(f"Partner {session_data.get('username')} changed their password")
            return {'status': 'ok', 'message': 'Password changed successfully'}

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to change partner password: {e}")
            raise HTTPException(status_code=500, detail=f'Failed to change password: {str(e)}')
        finally:
            if conn:
                conn.close()

    elif user_type == 'sub_admin':
        sub_admin_id = session_data.get('sub_admin_id')
        if not sub_admin_id:
            raise HTTPException(status_code=400, detail='Invalid session')

        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            # Get current password hash
            cursor.execute('SELECT password_hash FROM sub_admin_accounts WHERE id = ?', (sub_admin_id,))
            row = cursor.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail='Account not found')

            # Verify current password
            if hash_password(current_password) != row['password_hash']:
                raise HTTPException(status_code=401, detail='Current password is incorrect')

            # Update password
            cursor.execute(
                'UPDATE sub_admin_accounts SET password_hash = ?, updated_at = ? WHERE id = ?',
                (hash_password(new_password), datetime.now(timezone.utc).isoformat(), sub_admin_id)
            )
            conn.commit()

            logger.info(f"Sub-admin {session_data.get('username')} changed their password")
            return {'status': 'ok', 'message': 'Password changed successfully'}

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to change sub-admin password: {e}")
            raise HTTPException(status_code=500, detail=f'Failed to change password: {str(e)}')
        finally:
            if conn:
                conn.close()

    else:
        raise HTTPException(status_code=400, detail='Unknown user type')


@app.post('/api/change_username')
async def change_username(payload: dict, session: Optional[str] = Cookie(None)):
    """
    Change username for the currently logged-in partner.
    Requires current password for verification.
    """
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail='Not authenticated')

    user_type = session_data.get('user_type')

    # Only partners can change their username via this endpoint
    if user_type != 'partner':
        raise HTTPException(status_code=403, detail='Only partner accounts can change username')

    current_password = payload.get('current_password', '')
    new_username = payload.get('new_username', '').strip()

    if not current_password:
        raise HTTPException(status_code=400, detail='Current password is required')

    if not new_username or len(new_username) < 3:
        raise HTTPException(status_code=400, detail='New username must be at least 3 characters')

    if len(new_username) > 50:
        raise HTTPException(status_code=400, detail='Username must be 50 characters or less')

    # Basic username validation - alphanumeric, underscores, hyphens
    import re
    if not re.match(r'^[a-zA-Z0-9_-]+$', new_username):
        raise HTTPException(status_code=400, detail='Username can only contain letters, numbers, underscores, and hyphens')

    partner_id = session_data.get('partner_id')
    if not partner_id:
        raise HTTPException(status_code=400, detail='Invalid session')

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Get current password hash and username
        cursor.execute('SELECT username, password_hash FROM partner_accounts WHERE id = ?', (partner_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail='Account not found')

        current_username = row['username']

        # Check if new username is same as current
        if new_username.lower() == current_username.lower():
            raise HTTPException(status_code=400, detail='New username must be different from current username')

        # Verify current password
        if hash_password(current_password) != row['password_hash']:
            raise HTTPException(status_code=401, detail='Current password is incorrect')

        # Check if new username is already taken
        cursor.execute('SELECT id FROM partner_accounts WHERE LOWER(username) = LOWER(?) AND id != ?', (new_username, partner_id))
        if cursor.fetchone():
            raise HTTPException(status_code=409, detail='Username is already taken')

        # Update username
        cursor.execute(
            'UPDATE partner_accounts SET username = ?, updated_at = ? WHERE id = ?',
            (new_username, datetime.now(timezone.utc).isoformat(), partner_id)
        )
        conn.commit()

        logger.info(f"Partner changed username from '{current_username}' to '{new_username}'")
        return {'status': 'ok', 'message': 'Username changed successfully'}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to change partner username: {e}")
        raise HTTPException(status_code=500, detail=f'Failed to change username: {str(e)}')
    finally:
        if conn:
            conn.close()


# ============================================================================
# Partner Account Management (Super Admin Only)
# ============================================================================

@app.get('/api/partners')
async def list_partners(session: Optional[str] = Cookie(None)):
    """List all partner accounts (super admin only)"""
    if not is_super_admin(session):
        raise HTTPException(status_code=403, detail='Super admin access required')

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, username, discord_tag, display_name, enabled_features,
                   theme_settings, is_active, created_at, last_login_at, created_by
            FROM partner_accounts ORDER BY created_at DESC
        ''')
        partners = [dict(row) for row in cursor.fetchall()]
        for p in partners:
            p['enabled_features'] = json.loads(p['enabled_features'] or '[]')
            p['theme_settings'] = json.loads(p['theme_settings'] or '{}')
        return {'partners': partners}
    finally:
        if conn:
            conn.close()

@app.post('/api/partners')
async def create_partner(payload: dict, session: Optional[str] = Cookie(None)):
    """Create a new partner account (super admin only)"""
    if not is_super_admin(session):
        raise HTTPException(status_code=403, detail='Super admin access required')

    username = payload.get('username', '').strip()
    password = payload.get('password', '')
    discord_tag = payload.get('discord_tag', '').strip() or None
    display_name = payload.get('display_name', '').strip() or username
    enabled_features = payload.get('enabled_features', [])

    if not username or len(username) < 3:
        raise HTTPException(status_code=400, detail='Username must be at least 3 characters')
    if not password or len(password) < 4:
        raise HTTPException(status_code=400, detail='Password must be at least 4 characters')
    if username.lower() == 'haven':
        raise HTTPException(status_code=400, detail='Username "Haven" is reserved')

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Check for duplicate username
        cursor.execute('SELECT id FROM partner_accounts WHERE username = ?', (username,))
        if cursor.fetchone():
            raise HTTPException(status_code=400, detail='Username already exists')

        # Check for duplicate discord_tag
        if discord_tag:
            cursor.execute('SELECT id FROM partner_accounts WHERE discord_tag = ?', (discord_tag,))
            if cursor.fetchone():
                raise HTTPException(status_code=400, detail='Discord tag already in use')

        cursor.execute('''
            INSERT INTO partner_accounts (username, password_hash, discord_tag, display_name, enabled_features, created_by)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (username, hash_password(password), discord_tag, display_name, json.dumps(enabled_features), 'super_admin'))

        conn.commit()
        return {'status': 'ok', 'partner_id': cursor.lastrowid, 'username': username}
    finally:
        if conn:
            conn.close()

@app.put('/api/partners/{partner_id}')
async def update_partner(partner_id: int, payload: dict, session: Optional[str] = Cookie(None)):
    """Update a partner account (super admin only)"""
    if not is_super_admin(session):
        raise HTTPException(status_code=403, detail='Super admin access required')

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Check partner exists
        cursor.execute('SELECT id FROM partner_accounts WHERE id = ?', (partner_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail='Partner not found')

        updates = []
        params = []

        if 'discord_tag' in payload:
            # Check for duplicate discord_tag
            new_tag = payload['discord_tag'].strip() if payload['discord_tag'] else None
            if new_tag:
                cursor.execute('SELECT id FROM partner_accounts WHERE discord_tag = ? AND id != ?', (new_tag, partner_id))
                if cursor.fetchone():
                    raise HTTPException(status_code=400, detail='Discord tag already in use')
            updates.append('discord_tag = ?')
            params.append(new_tag)
        if 'display_name' in payload:
            updates.append('display_name = ?')
            params.append(payload['display_name'])
        if 'enabled_features' in payload:
            updates.append('enabled_features = ?')
            params.append(json.dumps(payload['enabled_features']))
        if 'is_active' in payload:
            updates.append('is_active = ?')
            params.append(1 if payload['is_active'] else 0)

        if not updates:
            raise HTTPException(status_code=400, detail='No fields to update')

        updates.append('updated_at = ?')
        params.append(datetime.now(timezone.utc).isoformat())
        params.append(partner_id)

        cursor.execute(f'''
            UPDATE partner_accounts SET {', '.join(updates)} WHERE id = ?
        ''', params)

        conn.commit()
        return {'status': 'ok'}
    finally:
        if conn:
            conn.close()

@app.post('/api/partners/{partner_id}/reset_password')
async def reset_partner_password(partner_id: int, payload: dict, session: Optional[str] = Cookie(None)):
    """Reset a partner's password (super admin only)"""
    if not is_super_admin(session):
        raise HTTPException(status_code=403, detail='Super admin access required')

    new_password = payload.get('password', '')
    if not new_password or len(new_password) < 4:
        raise HTTPException(status_code=400, detail='Password must be at least 4 characters')

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Check partner exists
        cursor.execute('SELECT id FROM partner_accounts WHERE id = ?', (partner_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail='Partner not found')

        cursor.execute(
            'UPDATE partner_accounts SET password_hash = ?, updated_at = ? WHERE id = ?',
            (hash_password(new_password), datetime.now(timezone.utc).isoformat(), partner_id)
        )
        conn.commit()
        return {'status': 'ok'}
    finally:
        if conn:
            conn.close()

@app.delete('/api/partners/{partner_id}')
async def deactivate_partner(partner_id: int, session: Optional[str] = Cookie(None)):
    """Deactivate a partner account (super admin only)"""
    if not is_super_admin(session):
        raise HTTPException(status_code=403, detail='Super admin access required')

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Check partner exists
        cursor.execute('SELECT id FROM partner_accounts WHERE id = ?', (partner_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail='Partner not found')

        cursor.execute(
            'UPDATE partner_accounts SET is_active = 0, updated_at = ? WHERE id = ?',
            (datetime.now(timezone.utc).isoformat(), partner_id)
        )
        conn.commit()
        return {'status': 'ok'}
    finally:
        if conn:
            conn.close()

@app.post('/api/partners/{partner_id}/activate')
async def activate_partner(partner_id: int, session: Optional[str] = Cookie(None)):
    """Reactivate a partner account (super admin only)"""
    if not is_super_admin(session):
        raise HTTPException(status_code=403, detail='Super admin access required')

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Check partner exists
        cursor.execute('SELECT id FROM partner_accounts WHERE id = ?', (partner_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail='Partner not found')

        cursor.execute(
            'UPDATE partner_accounts SET is_active = 1, updated_at = ? WHERE id = ?',
            (datetime.now(timezone.utc).isoformat(), partner_id)
        )
        conn.commit()
        return {'status': 'ok'}
    finally:
        if conn:
            conn.close()


# ============================================================================
# Sub-Admin Account Management
# ============================================================================

@app.get('/api/sub_admins')
async def list_sub_admins(
    partner_id: Optional[int] = None,
    show_all: bool = False,
    session: Optional[str] = Cookie(None)
):
    """
    List sub-admins. Super admin sees all (optionally filtered by partner_id).
    Partners see only their own sub-admins.
    If show_all=false and super admin has no partner_id, shows Haven's sub-admins.
    """
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail='Authentication required')

    user_type = session_data.get('user_type')
    is_super = user_type == 'super_admin'

    # Partners and sub-admins can only see sub-admins for their partner
    if not is_super:
        partner_id = session_data.get('partner_id')
        if not partner_id:
            raise HTTPException(status_code=403, detail='Access denied')

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        if partner_id:
            cursor.execute('''
                SELECT sa.*, pa.discord_tag as parent_discord_tag, pa.display_name as parent_display_name
                FROM sub_admin_accounts sa
                JOIN partner_accounts pa ON sa.parent_partner_id = pa.id
                WHERE sa.parent_partner_id = ?
                ORDER BY sa.username
            ''', (partner_id,))
        elif is_super and not show_all:
            # Super admin viewing their own sub-admins (parent_partner_id IS NULL)
            cursor.execute('''
                SELECT sa.*, NULL as parent_discord_tag, 'Haven' as parent_display_name
                FROM sub_admin_accounts sa
                WHERE sa.parent_partner_id IS NULL
                ORDER BY sa.username
            ''')
        else:
            # Super admin sees all (including their own)
            cursor.execute('''
                SELECT sa.*,
                       COALESCE(pa.discord_tag, NULL) as parent_discord_tag,
                       COALESCE(pa.display_name, 'Haven') as parent_display_name
                FROM sub_admin_accounts sa
                LEFT JOIN partner_accounts pa ON sa.parent_partner_id = pa.id
                ORDER BY COALESCE(pa.display_name, 'Haven'), sa.username
            ''')

        sub_admins = []
        for row in cursor.fetchall():
            row_dict = dict(row)
            sub_admins.append({
                'id': row['id'],
                'parent_partner_id': row['parent_partner_id'],
                'username': row['username'],
                'display_name': row['display_name'],
                'enabled_features': json.loads(row['enabled_features'] or '[]'),
                'is_active': bool(row['is_active']),
                'created_at': row['created_at'],
                'last_login_at': row['last_login_at'],
                'created_by': row['created_by'],
                'parent_discord_tag': row['parent_discord_tag'],
                'parent_display_name': row['parent_display_name'],
                'additional_discord_tags': json.loads(row_dict.get('additional_discord_tags') or '[]'),
                'can_approve_personal_uploads': bool(row_dict.get('can_approve_personal_uploads', 0))
            })

        return {'sub_admins': sub_admins}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing sub-admins: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()


@app.post('/api/sub_admins')
async def create_sub_admin(payload: dict, session: Optional[str] = Cookie(None)):
    """
    Create a sub-admin account.
    Super admin can create for any partner.
    Partners can create sub-admins under themselves.
    """
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail='Authentication required')

    user_type = session_data.get('user_type')
    is_super = user_type == 'super_admin'
    current_username = session_data.get('username')

    username = payload.get('username', '').strip()
    password = payload.get('password', '')
    display_name = payload.get('display_name', '').strip() or None
    enabled_features = payload.get('enabled_features', [])
    parent_partner_id = payload.get('parent_partner_id')
    additional_discord_tags = payload.get('additional_discord_tags', [])  # Only for Haven sub-admins
    can_approve_personal_uploads = payload.get('can_approve_personal_uploads', False)  # Only for Haven sub-admins

    # Validation
    if not username or len(username) < 3:
        raise HTTPException(status_code=400, detail='Username must be at least 3 characters')
    if not password or len(password) < 4:
        raise HTTPException(status_code=400, detail='Password must be at least 4 characters')

    # Determine parent partner
    # Super admin can create sub-admins for themselves (NULL parent) or for a partner
    # Partners create sub-admins under themselves
    is_haven_sub_admin = False
    if is_super:
        # Super admin can optionally specify parent_partner_id
        # If not specified, creates a "Haven" sub-admin (parent_partner_id = NULL)
        if not parent_partner_id:
            is_haven_sub_admin = True
    else:
        # Partners create sub-admins under themselves
        parent_partner_id = session_data.get('partner_id')
        if not parent_partner_id:
            raise HTTPException(status_code=403, detail='Only partners and super admins can create sub-admins')

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Check partner exists and is active (only if creating under a partner)
        if parent_partner_id:
            cursor.execute('SELECT id, enabled_features FROM partner_accounts WHERE id = ? AND is_active = 1', (parent_partner_id,))
            partner_row = cursor.fetchone()
            if not partner_row:
                raise HTTPException(status_code=404, detail='Parent partner not found or inactive')

            # Validate that sub-admin features are subset of parent's features
            parent_features = json.loads(partner_row['enabled_features'] or '[]')
            if 'all' not in parent_features:
                invalid_features = [f for f in enabled_features if f not in parent_features]
                if invalid_features:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Sub-admin cannot have features not granted to parent: {invalid_features}"
                    )
        # Haven sub-admins can have any features (super admin creates them)

        # Check username uniqueness across all user tables
        cursor.execute('SELECT username FROM partner_accounts WHERE username = ?', (username,))
        if cursor.fetchone():
            raise HTTPException(status_code=400, detail='Username already exists (partner account)')
        cursor.execute('SELECT username FROM sub_admin_accounts WHERE username = ?', (username,))
        if cursor.fetchone():
            raise HTTPException(status_code=400, detail='Username already exists (sub-admin account)')

        # Create sub-admin
        # additional_discord_tags and can_approve_personal_uploads only apply to Haven sub-admins (parent_partner_id is NULL)
        tags_to_store = json.dumps(additional_discord_tags) if is_haven_sub_admin else '[]'
        personal_uploads_perm = 1 if (is_haven_sub_admin and can_approve_personal_uploads) else 0
        cursor.execute('''
            INSERT INTO sub_admin_accounts
            (parent_partner_id, username, password_hash, display_name, enabled_features, created_by, additional_discord_tags, can_approve_personal_uploads)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            parent_partner_id,
            username,
            hash_password(password),
            display_name,
            json.dumps(enabled_features),
            current_username,
            tags_to_store,
            personal_uploads_perm
        ))

        sub_admin_id = cursor.lastrowid
        conn.commit()

        parent_label = f"partner {parent_partner_id}" if parent_partner_id else "Haven (super admin)"
        logger.info(f"Sub-admin created: {username} (ID: {sub_admin_id}) under {parent_label} by {current_username}")

        return {
            'status': 'ok',
            'sub_admin_id': sub_admin_id,
            'username': username
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating sub-admin: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()


@app.put('/api/sub_admins/{sub_admin_id}')
async def update_sub_admin(sub_admin_id: int, payload: dict, session: Optional[str] = Cookie(None)):
    """Update a sub-admin account."""
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail='Authentication required')

    user_type = session_data.get('user_type')
    is_super = user_type == 'super_admin'

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Get sub-admin (LEFT JOIN for Haven sub-admins with NULL parent_partner_id)
        cursor.execute('''
            SELECT sa.*, pa.enabled_features as parent_features
            FROM sub_admin_accounts sa
            LEFT JOIN partner_accounts pa ON sa.parent_partner_id = pa.id
            WHERE sa.id = ?
        ''', (sub_admin_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail='Sub-admin not found')

        # Check if this is a Haven sub-admin (no parent partner)
        is_haven_sub_admin = row['parent_partner_id'] is None

        # Permission check: super admin or parent partner can edit
        if not is_super:
            if is_haven_sub_admin:
                raise HTTPException(status_code=403, detail='Only super admin can edit Haven sub-admins')
            if session_data.get('partner_id') != row['parent_partner_id']:
                raise HTTPException(status_code=403, detail='Can only edit your own sub-admins')

        # Build update
        updates = []
        params = []

        if 'display_name' in payload:
            updates.append('display_name = ?')
            params.append(payload['display_name'] or None)

        if 'enabled_features' in payload:
            new_features = payload['enabled_features']
            # Validate features against parent (skip for Haven sub-admins - they can have any features)
            if not is_haven_sub_admin:
                parent_features = json.loads(row['parent_features'] or '[]')
                if 'all' not in parent_features:
                    invalid_features = [f for f in new_features if f not in parent_features]
                    if invalid_features:
                        raise HTTPException(
                            status_code=400,
                            detail=f"Sub-admin cannot have features not granted to parent: {invalid_features}"
                        )
            updates.append('enabled_features = ?')
            params.append(json.dumps(new_features))

        if 'is_active' in payload:
            updates.append('is_active = ?')
            params.append(1 if payload['is_active'] else 0)

        # additional_discord_tags only for Haven sub-admins
        if 'additional_discord_tags' in payload and is_haven_sub_admin:
            updates.append('additional_discord_tags = ?')
            params.append(json.dumps(payload['additional_discord_tags']))

        # can_approve_personal_uploads only for Haven sub-admins
        if 'can_approve_personal_uploads' in payload and is_haven_sub_admin:
            updates.append('can_approve_personal_uploads = ?')
            params.append(1 if payload['can_approve_personal_uploads'] else 0)

        if updates:
            updates.append('updated_at = ?')
            params.append(datetime.now(timezone.utc).isoformat())
            params.append(sub_admin_id)

            cursor.execute(
                f'UPDATE sub_admin_accounts SET {", ".join(updates)} WHERE id = ?',
                params
            )
            conn.commit()

        return {'status': 'ok'}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating sub-admin: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()


@app.post('/api/sub_admins/{sub_admin_id}/reset_password')
async def reset_sub_admin_password(sub_admin_id: int, payload: dict, session: Optional[str] = Cookie(None)):
    """Reset a sub-admin's password."""
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail='Authentication required')

    user_type = session_data.get('user_type')
    is_super = user_type == 'super_admin'

    new_password = payload.get('new_password', '')
    if not new_password or len(new_password) < 4:
        raise HTTPException(status_code=400, detail='New password must be at least 4 characters')

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT parent_partner_id FROM sub_admin_accounts WHERE id = ?', (sub_admin_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail='Sub-admin not found')

        # Check if this is a Haven sub-admin (no parent partner)
        is_haven_sub_admin = row['parent_partner_id'] is None

        # Permission check
        if not is_super:
            if is_haven_sub_admin:
                raise HTTPException(status_code=403, detail='Only super admin can reset Haven sub-admin passwords')
            if session_data.get('partner_id') != row['parent_partner_id']:
                raise HTTPException(status_code=403, detail='Can only reset passwords for your own sub-admins')

        cursor.execute(
            'UPDATE sub_admin_accounts SET password_hash = ?, updated_at = ? WHERE id = ?',
            (hash_password(new_password), datetime.now(timezone.utc).isoformat(), sub_admin_id)
        )
        conn.commit()

        return {'status': 'ok'}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resetting sub-admin password: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()


@app.delete('/api/sub_admins/{sub_admin_id}')
async def delete_sub_admin(sub_admin_id: int, session: Optional[str] = Cookie(None)):
    """Deactivate a sub-admin account."""
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail='Authentication required')

    user_type = session_data.get('user_type')
    is_super = user_type == 'super_admin'

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT parent_partner_id FROM sub_admin_accounts WHERE id = ?', (sub_admin_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail='Sub-admin not found')

        # Check if this is a Haven sub-admin (no parent partner)
        is_haven_sub_admin = row['parent_partner_id'] is None

        # Permission check
        if not is_super:
            if is_haven_sub_admin:
                raise HTTPException(status_code=403, detail='Only super admin can deactivate Haven sub-admins')
            if session_data.get('partner_id') != row['parent_partner_id']:
                raise HTTPException(status_code=403, detail='Can only deactivate your own sub-admins')

        cursor.execute(
            'UPDATE sub_admin_accounts SET is_active = 0, updated_at = ? WHERE id = ?',
            (datetime.now(timezone.utc).isoformat(), sub_admin_id)
        )
        conn.commit()

        return {'status': 'ok'}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deactivating sub-admin: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()


@app.get('/api/available_discord_tags')
async def get_available_discord_tags(session: Optional[str] = Cookie(None)):
    """
    Get list of all available discord tags (from partners).
    Super admin only - used for configuring Haven sub-admin visibility.
    """
    if not is_super_admin(session):
        raise HTTPException(status_code=403, detail='Super admin access required')

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Get all discord tags from partners (including Haven)
        cursor.execute('''
            SELECT DISTINCT discord_tag, display_name
            FROM partner_accounts
            WHERE discord_tag IS NOT NULL AND is_active = 1
            ORDER BY discord_tag
        ''')

        tags = []
        for row in cursor.fetchall():
            tags.append({
                'discord_tag': row['discord_tag'],
                'display_name': row['display_name']
            })

        return {'discord_tags': tags}
    except Exception as e:
        logger.error(f"Error fetching discord tags: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()


@app.get('/api/approval_audit')
async def get_approval_audit(
    limit: int = 100,
    offset: int = 0,
    discord_tag: Optional[str] = None,
    approver: Optional[str] = None,
    submitter: Optional[str] = None,
    action: Optional[str] = None,
    submission_type: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    search: Optional[str] = None,
    session: Optional[str] = Cookie(None)
):
    """
    Get approval audit history (super admin only).
    Returns all approval/rejection actions with full details.

    Enhanced filters:
    - discord_tag: Filter by community
    - approver: Filter by approver username
    - submitter: Filter by submitter username
    - action: Filter by action type (approved, rejected, direct_edit, direct_add)
    - submission_type: Filter by submission type (system, region)
    - start_date, end_date: Date range filter (ISO format)
    - search: Full-text search across submitter, approver, submission name, and notes
    """
    if not is_super_admin(session):
        raise HTTPException(status_code=403, detail='Super admin access required')

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        query = 'SELECT * FROM approval_audit_log WHERE 1=1'
        params = []

        if discord_tag:
            query += ' AND submission_discord_tag = ?'
            params.append(discord_tag)

        if approver:
            query += ' AND approver_username LIKE ?'
            params.append(f'%{approver}%')

        if submitter:
            query += ' AND submitter_username LIKE ?'
            params.append(f'%{submitter}%')

        if action:
            query += ' AND action = ?'
            params.append(action)

        if submission_type:
            query += ' AND submission_type = ?'
            params.append(submission_type)

        if start_date:
            query += ' AND timestamp >= ?'
            params.append(start_date)

        if end_date:
            query += ' AND timestamp <= ?'
            params.append(end_date + 'T23:59:59')

        if search:
            # Search across multiple fields: submitter, approver, submission name, and notes
            query += ''' AND (
                submitter_username LIKE ? OR
                approver_username LIKE ? OR
                submission_name LIKE ? OR
                notes LIKE ?
            )'''
            search_term = f'%{search}%'
            params.extend([search_term, search_term, search_term, search_term])

        query += ' ORDER BY timestamp DESC LIMIT ? OFFSET ?'
        params.extend([limit, offset])

        cursor.execute(query, params)
        rows = cursor.fetchall()

        audit_entries = [dict(row) for row in rows]

        # Get total count for pagination with same filters
        count_query = 'SELECT COUNT(*) FROM approval_audit_log WHERE 1=1'
        count_params = []
        if discord_tag:
            count_query += ' AND submission_discord_tag = ?'
            count_params.append(discord_tag)
        if approver:
            count_query += ' AND approver_username LIKE ?'
            count_params.append(f'%{approver}%')
        if submitter:
            count_query += ' AND submitter_username LIKE ?'
            count_params.append(f'%{submitter}%')
        if action:
            count_query += ' AND action = ?'
            count_params.append(action)
        if submission_type:
            count_query += ' AND submission_type = ?'
            count_params.append(submission_type)
        if start_date:
            count_query += ' AND timestamp >= ?'
            count_params.append(start_date)
        if end_date:
            count_query += ' AND timestamp <= ?'
            count_params.append(end_date + 'T23:59:59')
        if search:
            # Search across multiple fields: submitter, approver, submission name, and notes
            count_query += ''' AND (
                submitter_username LIKE ? OR
                approver_username LIKE ? OR
                submission_name LIKE ? OR
                notes LIKE ?
            )'''
            search_term = f'%{search}%'
            count_params.extend([search_term, search_term, search_term, search_term])

        cursor.execute(count_query, count_params)
        total = cursor.fetchone()[0]

        return {
            'entries': audit_entries,
            'total': total,
            'limit': limit,
            'offset': offset
        }
    finally:
        if conn:
            conn.close()


@app.get('/api/approval_audit/export')
async def export_approval_audit(
    format: str = 'csv',
    discord_tag: Optional[str] = None,
    approver: Optional[str] = None,
    submitter: Optional[str] = None,
    action: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    session: Optional[str] = Cookie(None)
):
    """
    Export approval audit data as CSV or JSON (super admin only).
    """
    if not is_super_admin(session):
        raise HTTPException(status_code=403, detail='Super admin access required')

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        query = 'SELECT * FROM approval_audit_log WHERE 1=1'
        params = []

        if discord_tag:
            query += ' AND submission_discord_tag = ?'
            params.append(discord_tag)
        if approver:
            query += ' AND approver_username LIKE ?'
            params.append(f'%{approver}%')
        if submitter:
            query += ' AND submitter_username LIKE ?'
            params.append(f'%{submitter}%')
        if action:
            query += ' AND action = ?'
            params.append(action)
        if start_date:
            query += ' AND timestamp >= ?'
            params.append(start_date)
        if end_date:
            query += ' AND timestamp <= ?'
            params.append(end_date + 'T23:59:59')

        query += ' ORDER BY timestamp DESC'
        cursor.execute(query, params)
        rows = cursor.fetchall()
        data = [dict(row) for row in rows]

        if format == 'json':
            return JSONResponse(content={'data': data, 'count': len(data)})
        else:
            # CSV format
            import io
            import csv
            output = io.StringIO()
            if data:
                writer = csv.DictWriter(output, fieldnames=data[0].keys())
                writer.writeheader()
                writer.writerows(data)
            csv_content = output.getvalue()
            return Response(
                content=csv_content,
                media_type='text/csv',
                headers={'Content-Disposition': 'attachment; filename=approval_audit.csv'}
            )
    finally:
        if conn:
            conn.close()


# ============================================================================
# Analytics Endpoints
# ============================================================================

@app.get('/api/analytics/submission-leaderboard')
async def get_submission_leaderboard(
    discord_tag: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    period: Optional[str] = None,
    limit: int = 50,
    session: Optional[str] = Cookie(None)
):
    """
    Get submission leaderboard showing tallies per person.
    Partners can only see their own community's leaderboard.
    Super admins can see all.

    Params:
    - discord_tag: Filter by community (partners automatically filtered)
    - start_date, end_date: Date range (ISO format)
    - period: Preset periods (week, month, year, all)
    - limit: Max results (default 50)
    """
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail='Authentication required')

    is_super = session_data.get('user_type') == 'super_admin'
    user_discord_tag = session_data.get('discord_tag')

    # Partners can only see their own community
    if not is_super and user_discord_tag:
        discord_tag = user_discord_tag

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Build date filter based on period or explicit dates
        date_filter = ''
        date_params = []

        if period == 'week':
            date_filter = " AND submission_date >= date('now', '-7 days')"
        elif period == 'month':
            date_filter = " AND submission_date >= date('now', '-30 days')"
        elif period == 'year':
            date_filter = " AND submission_date >= date('now', '-365 days')"
        elif start_date:
            date_filter = " AND submission_date >= ?"
            date_params.append(start_date)
            if end_date:
                date_filter += " AND submission_date <= ?"
                date_params.append(end_date + 'T23:59:59')

        # Build community filter
        tag_filter = ''
        tag_params = []
        if discord_tag:
            tag_filter = ' AND discord_tag = ?'
            tag_params = [discord_tag]

        # Query for leaderboard from pending_systems (includes both approved and rejected)
        # Extract username from multiple sources: submitted_by, personal_discord_username, or discovered_by from JSON
        # Skip 'Anonymous' and 'anonymous' values to find the actual username
        # Normalize usernames: remove #, strip trailing 4-digit Discord discriminators, lowercase
        # This consolidates "Obliterated", "Obliterated#4519", "obliterated4519" as the same person

        # Define the raw username extraction
        raw_username = '''COALESCE(
            NULLIF(NULLIF(submitted_by, 'Anonymous'), 'anonymous'),
            personal_discord_username,
            json_extract(system_data, '$.discovered_by'),
            'Unknown'
        )'''

        # Define normalization: trim whitespace, remove #, strip trailing 4-digit discriminator, lowercase
        # This handles: "User#1234" -> "user", "User1234" -> "user", "User" -> "user", " User " -> "user"
        # Step 1: TRIM and REPLACE # with empty string
        trimmed_username = f'''TRIM(REPLACE({raw_username}, '#', ''))'''

        normalized_username = f'''LOWER(TRIM(
            CASE
                WHEN LENGTH({trimmed_username}) > 4
                    AND SUBSTR({trimmed_username}, -4) GLOB '[0-9][0-9][0-9][0-9]'
                    AND (LENGTH({trimmed_username}) = 4
                        OR SUBSTR({trimmed_username}, -5, 1) NOT GLOB '[0-9]')
                THEN SUBSTR({trimmed_username}, 1, LENGTH({trimmed_username}) - 4)
                ELSE {trimmed_username}
            END
        ))'''

        # Use COALESCE to convert NULL/empty discord_tag to 'Personal' for grouping
        tag_display = "COALESCE(NULLIF(discord_tag, ''), 'Personal')"

        query = f'''
            SELECT
                MAX({raw_username}) as username,
                {normalized_username} as normalized_name,
                GROUP_CONCAT(DISTINCT {tag_display}) as discord_tags,
                COUNT(*) as total_submissions,
                SUM(CASE WHEN status = 'approved' THEN 1 ELSE 0 END) as approved,
                SUM(CASE WHEN status = 'rejected' THEN 1 ELSE 0 END) as rejected,
                MIN(submission_date) as first_submission,
                MAX(submission_date) as last_submission
            FROM pending_systems
            WHERE 1=1 {tag_filter} {date_filter}
            GROUP BY {normalized_username}
            HAVING {normalized_username} != 'unknown'
            ORDER BY total_submissions DESC
            LIMIT ?
        '''

        params = tag_params + date_params + [limit]
        cursor.execute(query, params)
        rows = cursor.fetchall()

        leaderboard = []
        for row in rows:
            entry = dict(row)
            total = entry['total_submissions']
            approved = entry['approved'] or 0
            entry['approval_rate'] = round((approved / total * 100), 1) if total > 0 else 0

            # For users with multiple sources (discord communities or personal), fetch breakdown
            tags = [t.strip() for t in (entry.get('discord_tags') or '').split(',') if t.strip()]
            if len(tags) > 1:
                # Use the normalized_name from the query for accurate matching
                norm_name = entry.get('normalized_name', '').lower()
                breakdown_query = f'''
                    SELECT
                        {tag_display} as discord_tag,
                        COUNT(*) as total,
                        SUM(CASE WHEN status = 'approved' THEN 1 ELSE 0 END) as approved,
                        SUM(CASE WHEN status = 'rejected' THEN 1 ELSE 0 END) as rejected
                    FROM pending_systems
                    WHERE {normalized_username} = ?
                      {date_filter}
                    GROUP BY {tag_display}
                    ORDER BY total DESC
                '''
                cursor.execute(breakdown_query, [norm_name] + date_params)
                breakdown_rows = cursor.fetchall()
                entry['tag_breakdown'] = [dict(b) for b in breakdown_rows]

            # Remove internal normalized_name from response
            entry.pop('normalized_name', None)
            leaderboard.append(entry)

        # Get totals
        totals_query = f'''
            SELECT
                COUNT(*) as total_submissions,
                SUM(CASE WHEN status = 'approved' THEN 1 ELSE 0 END) as total_approved,
                SUM(CASE WHEN status = 'rejected' THEN 1 ELSE 0 END) as total_rejected
            FROM pending_systems
            WHERE 1=1 {tag_filter} {date_filter}
        '''
        cursor.execute(totals_query, tag_params + date_params)
        totals_row = cursor.fetchone()

        return {
            'leaderboard': leaderboard,
            'totals': {
                'total_submissions': totals_row['total_submissions'] or 0,
                'total_approved': totals_row['total_approved'] or 0,
                'total_rejected': totals_row['total_rejected'] or 0
            }
        }
    finally:
        if conn:
            conn.close()


@app.get('/api/analytics/community-stats')
async def get_community_stats(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    period: Optional[str] = None,
    session: Optional[str] = Cookie(None)
):
    """
    Get statistics per community/Discord tag.
    Super admin only - shows all communities.
    """
    if not is_super_admin(session):
        raise HTTPException(status_code=403, detail='Super admin access required')

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Build date filter
        date_filter = ''
        date_params = []

        if period == 'week':
            date_filter = " AND submission_date >= date('now', '-7 days')"
        elif period == 'month':
            date_filter = " AND submission_date >= date('now', '-30 days')"
        elif period == 'year':
            date_filter = " AND submission_date >= date('now', '-365 days')"
        elif start_date:
            date_filter = " AND submission_date >= ?"
            date_params.append(start_date)
            if end_date:
                date_filter += " AND submission_date <= ?"
                date_params.append(end_date + 'T23:59:59')

        # Get community stats from pending_systems
        # Normalize usernames: trim whitespace, remove #, strip trailing 4-digit Discord discriminators, lowercase
        raw_username = '''COALESCE(
            NULLIF(NULLIF(submitted_by, 'Anonymous'), 'anonymous'),
            personal_discord_username,
            json_extract(system_data, '$.discovered_by'),
            'Unknown'
        )'''

        trimmed_username = f'''TRIM(REPLACE({raw_username}, '#', ''))'''

        normalized_username = f'''LOWER(TRIM(
            CASE
                WHEN LENGTH({trimmed_username}) > 4
                    AND SUBSTR({trimmed_username}, -4) GLOB '[0-9][0-9][0-9][0-9]'
                    AND (LENGTH({trimmed_username}) = 4
                        OR SUBSTR({trimmed_username}, -5, 1) NOT GLOB '[0-9]')
                THEN SUBSTR({trimmed_username}, 1, LENGTH({trimmed_username}) - 4)
                ELSE {trimmed_username}
            END
        ))'''

        query = f'''
            SELECT
                COALESCE(discord_tag, 'Untagged') as discord_tag,
                COUNT(*) as total_submissions,
                SUM(CASE WHEN status = 'approved' THEN 1 ELSE 0 END) as total_approved,
                SUM(CASE WHEN status = 'rejected' THEN 1 ELSE 0 END) as total_rejected,
                COUNT(DISTINCT {normalized_username}) as unique_submitters
            FROM pending_systems
            WHERE 1=1 {date_filter}
            GROUP BY discord_tag
            ORDER BY total_submissions DESC
        '''

        cursor.execute(query, date_params)
        rows = cursor.fetchall()

        communities = []
        for row in rows:
            entry = dict(row)
            total = entry['total_submissions']
            approved = entry['total_approved'] or 0
            entry['approval_rate'] = round((approved / total * 100), 1) if total > 0 else 0

            # Get top submitter for this community (with full normalization)
            tag = row['discord_tag']
            if tag and tag != 'Untagged':
                cursor.execute(f'''
                    SELECT MAX({raw_username}) as username,
                           COUNT(*) as count
                    FROM pending_systems
                    WHERE discord_tag = ? {date_filter}
                    GROUP BY {normalized_username}
                    ORDER BY count DESC
                    LIMIT 1
                ''', [tag] + date_params)
            else:
                cursor.execute(f'''
                    SELECT MAX({raw_username}) as username,
                           COUNT(*) as count
                    FROM pending_systems
                    WHERE (discord_tag IS NULL OR discord_tag = '') {date_filter}
                    GROUP BY {normalized_username}
                    ORDER BY count DESC
                    LIMIT 1
                ''', date_params)

            top_row = cursor.fetchone()
            entry['top_submitter'] = top_row['username'] if top_row else None

            # Get total systems in the database for this community
            if tag and tag != 'Untagged':
                cursor.execute('SELECT COUNT(*) FROM systems WHERE discord_tag = ?', (tag,))
            else:
                cursor.execute("SELECT COUNT(*) FROM systems WHERE discord_tag IS NULL OR discord_tag = ''")
            entry['total_systems'] = cursor.fetchone()[0]

            communities.append(entry)

        return {'communities': communities}
    finally:
        if conn:
            conn.close()


@app.get('/api/analytics/submissions-timeline')
async def get_submissions_timeline(
    discord_tag: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    granularity: str = 'day',
    session: Optional[str] = Cookie(None)
):
    """
    Get submissions over time for charting.
    Partners can only see their own community's timeline.

    Params:
    - discord_tag: Filter by community
    - start_date, end_date: Date range
    - granularity: day, week, or month
    """
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail='Authentication required')

    is_super = session_data.get('user_type') == 'super_admin'
    user_discord_tag = session_data.get('discord_tag')

    # Partners can only see their own community
    if not is_super and user_discord_tag:
        discord_tag = user_discord_tag

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Default to last 30 days if no date range specified
        if not start_date:
            start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        if not end_date:
            end_date = datetime.now().strftime('%Y-%m-%d')

        # Build date grouping based on granularity
        if granularity == 'week':
            date_format = "strftime('%Y-W%W', submission_date)"
        elif granularity == 'month':
            date_format = "strftime('%Y-%m', submission_date)"
        else:  # day
            date_format = "date(submission_date)"

        # Build filters
        tag_filter = ''
        params = [start_date, end_date + 'T23:59:59']

        if discord_tag:
            tag_filter = ' AND discord_tag = ?'
            params.append(discord_tag)

        query = f'''
            SELECT
                {date_format} as date,
                COUNT(*) as submissions,
                SUM(CASE WHEN status = 'approved' THEN 1 ELSE 0 END) as approved,
                SUM(CASE WHEN status = 'rejected' THEN 1 ELSE 0 END) as rejected
            FROM pending_systems
            WHERE submission_date >= ? AND submission_date <= ? {tag_filter}
            GROUP BY {date_format}
            ORDER BY date ASC
        '''

        cursor.execute(query, params)
        rows = cursor.fetchall()

        timeline = [dict(row) for row in rows]

        return {'timeline': timeline, 'granularity': granularity}
    finally:
        if conn:
            conn.close()


@app.get('/api/analytics/rejection-reasons')
async def get_rejection_reasons(
    discord_tag: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    session: Optional[str] = Cookie(None)
):
    """
    Get breakdown of rejection reasons.
    Super admin only.
    """
    if not is_super_admin(session):
        raise HTTPException(status_code=403, detail='Super admin access required')

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Build filters
        filters = " AND action = 'rejected' AND notes IS NOT NULL AND notes != ''"
        params = []

        if discord_tag:
            filters += ' AND submission_discord_tag = ?'
            params.append(discord_tag)
        if start_date:
            filters += ' AND timestamp >= ?'
            params.append(start_date)
        if end_date:
            filters += ' AND timestamp <= ?'
            params.append(end_date + 'T23:59:59')

        query = f'''
            SELECT
                notes as reason,
                COUNT(*) as count
            FROM approval_audit_log
            WHERE 1=1 {filters}
            GROUP BY notes
            ORDER BY count DESC
            LIMIT 20
        '''

        cursor.execute(query, params)
        rows = cursor.fetchall()

        reasons = [dict(row) for row in rows]

        return {'reasons': reasons}
    finally:
        if conn:
            conn.close()


# ============================================================================
# Discovery Analytics Endpoints (Partner Analytics Dashboard)
# ============================================================================

@app.get('/api/analytics/discovery-leaderboard')
async def get_discovery_leaderboard(
    discord_tag: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    period: Optional[str] = None,
    limit: int = 50,
    session: Optional[str] = Cookie(None)
):
    """
    Get discovery leaderboard showing top discoverers.
    Partners can only see their own community's leaderboard.
    Super admins can see all or filter by community.
    """
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail='Authentication required')

    is_super = session_data.get('user_type') == 'super_admin'
    user_discord_tag = session_data.get('discord_tag')

    # Partners can only see their own community
    if not is_super and user_discord_tag:
        discord_tag = user_discord_tag

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Build date filter
        date_filter = ''
        date_params = []

        if period == 'week':
            date_filter = " AND submission_timestamp >= date('now', '-7 days')"
        elif period == 'month':
            date_filter = " AND submission_timestamp >= date('now', '-30 days')"
        elif period == 'year':
            date_filter = " AND submission_timestamp >= date('now', '-365 days')"
        elif start_date:
            date_filter = " AND submission_timestamp >= ?"
            date_params.append(start_date)
            if end_date:
                date_filter += " AND submission_timestamp <= ?"
                date_params.append(end_date + 'T23:59:59')

        # Build community filter
        tag_filter = ''
        tag_params = []
        if discord_tag:
            tag_filter = ' AND discord_tag = ?'
            tag_params = [discord_tag]

        # Normalize discovered_by: trim, remove #, strip trailing 4-digit discriminator, lowercase
        raw_name = "COALESCE(NULLIF(NULLIF(discovered_by, 'Anonymous'), 'anonymous'), 'Unknown')"
        trimmed_name = f"TRIM(REPLACE({raw_name}, '#', ''))"
        normalized_name = f"""LOWER(TRIM(
            CASE
                WHEN LENGTH({trimmed_name}) > 4
                    AND SUBSTR({trimmed_name}, -4) GLOB '[0-9][0-9][0-9][0-9]'
                    AND (LENGTH({trimmed_name}) = 4
                        OR SUBSTR({trimmed_name}, -5, 1) NOT GLOB '[0-9]')
                THEN SUBSTR({trimmed_name}, 1, LENGTH({trimmed_name}) - 4)
                ELSE {trimmed_name}
            END
        ))"""

        query = f'''
            SELECT
                MAX(discovered_by) as discoverer,
                {normalized_name} as normalized_name,
                COUNT(*) as total_discoveries,
                COUNT(DISTINCT type_slug) as unique_types,
                GROUP_CONCAT(DISTINCT type_slug) as type_slugs,
                MIN(submission_timestamp) as first_discovery,
                MAX(submission_timestamp) as last_discovery
            FROM discoveries
            WHERE 1=1 {tag_filter} {date_filter}
            GROUP BY {normalized_name}
            HAVING {normalized_name} != 'unknown'
            ORDER BY total_discoveries DESC
            LIMIT ?
        '''

        params = tag_params + date_params + [limit]
        cursor.execute(query, params)
        rows = cursor.fetchall()

        leaderboard = []
        for i, row in enumerate(rows, 1):
            entry = dict(row)
            entry['rank'] = i
            entry['type_slugs'] = [t.strip() for t in (entry.get('type_slugs') or '').split(',') if t.strip()]
            leaderboard.append(entry)

        # Get totals
        total_query = f'''
            SELECT COUNT(*) as total_discoveries,
                   COUNT(DISTINCT {normalized_name}) as total_discoverers
            FROM discoveries
            WHERE 1=1 {tag_filter} {date_filter}
        '''
        cursor.execute(total_query, tag_params + date_params)
        totals = dict(cursor.fetchone())

        return {
            'leaderboard': leaderboard,
            'totals': totals
        }
    finally:
        if conn:
            conn.close()


@app.get('/api/analytics/discovery-timeline')
async def get_discovery_timeline(
    discord_tag: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    granularity: str = 'day',
    session: Optional[str] = Cookie(None)
):
    """
    Get time-series of discovery submissions.
    Partners see their community only.
    """
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail='Authentication required')

    is_super = session_data.get('user_type') == 'super_admin'
    user_discord_tag = session_data.get('discord_tag')

    if not is_super and user_discord_tag:
        discord_tag = user_discord_tag

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Default to last 30 days
        if not start_date:
            start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        if not end_date:
            end_date = datetime.now().strftime('%Y-%m-%d')

        # Date grouping
        if granularity == 'week':
            date_format = "strftime('%Y-W%W', submission_timestamp)"
        elif granularity == 'month':
            date_format = "strftime('%Y-%m', submission_timestamp)"
        else:
            date_format = "date(submission_timestamp)"

        tag_filter = ''
        params = [start_date, end_date + 'T23:59:59']

        if discord_tag:
            tag_filter = ' AND discord_tag = ?'
            params.append(discord_tag)

        query = f'''
            SELECT
                {date_format} as date,
                COUNT(*) as discoveries,
                COUNT(DISTINCT type_slug) as unique_types,
                COUNT(DISTINCT LOWER(TRIM(discovered_by))) as unique_discoverers
            FROM discoveries
            WHERE submission_timestamp >= ? AND submission_timestamp <= ? {tag_filter}
            GROUP BY {date_format}
            ORDER BY date ASC
        '''

        cursor.execute(query, params)
        rows = cursor.fetchall()

        timeline = [dict(row) for row in rows]

        return {'timeline': timeline, 'granularity': granularity}
    finally:
        if conn:
            conn.close()


@app.get('/api/analytics/discovery-type-breakdown')
async def get_discovery_type_breakdown(
    discord_tag: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    period: Optional[str] = None,
    session: Optional[str] = Cookie(None)
):
    """
    Get discovery counts grouped by type for a community.
    Partners see their community only.
    """
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail='Authentication required')

    is_super = session_data.get('user_type') == 'super_admin'
    user_discord_tag = session_data.get('discord_tag')

    if not is_super and user_discord_tag:
        discord_tag = user_discord_tag

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Build date filter
        date_filter = ''
        date_params = []

        if period == 'week':
            date_filter = " AND submission_timestamp >= date('now', '-7 days')"
        elif period == 'month':
            date_filter = " AND submission_timestamp >= date('now', '-30 days')"
        elif period == 'year':
            date_filter = " AND submission_timestamp >= date('now', '-365 days')"
        elif start_date:
            date_filter = " AND submission_timestamp >= ?"
            date_params.append(start_date)
            if end_date:
                date_filter += " AND submission_timestamp <= ?"
                date_params.append(end_date + 'T23:59:59')

        tag_filter = ''
        tag_params = []
        if discord_tag:
            tag_filter = ' AND discord_tag = ?'
            tag_params = [discord_tag]

        query = f'''
            SELECT
                COALESCE(type_slug, 'other') as type_slug,
                COALESCE(discovery_type, 'Other') as discovery_type,
                COUNT(*) as count
            FROM discoveries
            WHERE 1=1 {tag_filter} {date_filter}
            GROUP BY type_slug
            ORDER BY count DESC
        '''

        params = tag_params + date_params
        cursor.execute(query, params)
        rows = cursor.fetchall()

        breakdown = [dict(row) for row in rows]

        # Calculate percentages
        total = sum(item['count'] for item in breakdown)
        for item in breakdown:
            item['percentage'] = round((item['count'] / total * 100), 1) if total > 0 else 0

        return {'breakdown': breakdown, 'total': total}
    finally:
        if conn:
            conn.close()


@app.get('/api/analytics/partner-overview')
async def get_partner_overview(
    discord_tag: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    period: Optional[str] = None,
    session: Optional[str] = Cookie(None)
):
    """
    Combined overview endpoint for the partner analytics dashboard.
    Returns system submission totals, discovery totals, top submitters,
    top discoverers, and activity trends in a single call.
    """
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail='Authentication required')

    is_super = session_data.get('user_type') == 'super_admin'
    user_discord_tag = session_data.get('discord_tag')

    if not is_super and user_discord_tag:
        discord_tag = user_discord_tag

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Build date filter for pending_systems
        sub_date_filter = ''
        sub_date_params = []
        disc_date_filter = ''
        disc_date_params = []

        if period == 'week':
            sub_date_filter = " AND submission_date >= date('now', '-7 days')"
            disc_date_filter = " AND submission_timestamp >= date('now', '-7 days')"
        elif period == 'month':
            sub_date_filter = " AND submission_date >= date('now', '-30 days')"
            disc_date_filter = " AND submission_timestamp >= date('now', '-30 days')"
        elif period == 'year':
            sub_date_filter = " AND submission_date >= date('now', '-365 days')"
            disc_date_filter = " AND submission_timestamp >= date('now', '-365 days')"
        elif start_date:
            sub_date_filter = " AND submission_date >= ?"
            sub_date_params.append(start_date)
            disc_date_filter = " AND submission_timestamp >= ?"
            disc_date_params.append(start_date)
            if end_date:
                sub_date_filter += " AND submission_date <= ?"
                sub_date_params.append(end_date + 'T23:59:59')
                disc_date_filter += " AND submission_timestamp <= ?"
                disc_date_params.append(end_date + 'T23:59:59')

        sub_tag_filter = ''
        sub_tag_params = []
        disc_tag_filter = ''
        disc_tag_params = []
        if discord_tag:
            sub_tag_filter = ' AND discord_tag = ?'
            sub_tag_params = [discord_tag]
            disc_tag_filter = ' AND discord_tag = ?'
            disc_tag_params = [discord_tag]

        # --- System submission stats ---
        cursor.execute(f'''
            SELECT
                COUNT(*) as total_submissions,
                SUM(CASE WHEN status = 'approved' THEN 1 ELSE 0 END) as total_approved,
                SUM(CASE WHEN status = 'rejected' THEN 1 ELSE 0 END) as total_rejected,
                SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as total_pending
            FROM pending_systems
            WHERE 1=1 {sub_tag_filter} {sub_date_filter}
        ''', sub_tag_params + sub_date_params)
        sub_stats = dict(cursor.fetchone())

        # Active submitters (unique normalized usernames)
        raw_username = '''COALESCE(
            NULLIF(NULLIF(submitted_by, 'Anonymous'), 'anonymous'),
            personal_discord_username,
            json_extract(system_data, '$.discovered_by'),
            'Unknown'
        )'''
        trimmed_username = f"TRIM(REPLACE({raw_username}, '#', ''))"
        normalized_sub = f"""LOWER(TRIM(
            CASE
                WHEN LENGTH({trimmed_username}) > 4
                    AND SUBSTR({trimmed_username}, -4) GLOB '[0-9][0-9][0-9][0-9]'
                    AND (LENGTH({trimmed_username}) = 4
                        OR SUBSTR({trimmed_username}, -5, 1) NOT GLOB '[0-9]')
                THEN SUBSTR({trimmed_username}, 1, LENGTH({trimmed_username}) - 4)
                ELSE {trimmed_username}
            END
        ))"""

        cursor.execute(f'''
            SELECT COUNT(DISTINCT {normalized_sub}) as active_submitters
            FROM pending_systems
            WHERE 1=1 {sub_tag_filter} {sub_date_filter}
              AND {normalized_sub} != 'unknown'
        ''', sub_tag_params + sub_date_params)
        active_submitters = cursor.fetchone()['active_submitters']

        # --- Discovery stats ---
        cursor.execute(f'''
            SELECT
                COUNT(*) as total_discoveries,
                COUNT(DISTINCT LOWER(TRIM(discovered_by))) as active_discoverers,
                COUNT(DISTINCT type_slug) as unique_types
            FROM discoveries
            WHERE 1=1 {disc_tag_filter} {disc_date_filter}
        ''', disc_tag_params + disc_date_params)
        disc_stats = dict(cursor.fetchone())

        # --- Top 5 submitters ---
        cursor.execute(f'''
            SELECT
                MAX({raw_username}) as username,
                {normalized_sub} as normalized_name,
                COUNT(*) as total,
                SUM(CASE WHEN status = 'approved' THEN 1 ELSE 0 END) as approved
            FROM pending_systems
            WHERE 1=1 {sub_tag_filter} {sub_date_filter}
            GROUP BY {normalized_sub}
            HAVING {normalized_sub} != 'unknown'
            ORDER BY total DESC
            LIMIT 5
        ''', sub_tag_params + sub_date_params)
        top_submitters = [dict(row) for row in cursor.fetchall()]

        # --- Top 5 discoverers ---
        raw_disc = "COALESCE(NULLIF(NULLIF(discovered_by, 'Anonymous'), 'anonymous'), 'Unknown')"
        trimmed_disc = f"TRIM(REPLACE({raw_disc}, '#', ''))"
        normalized_disc = f"""LOWER(TRIM(
            CASE
                WHEN LENGTH({trimmed_disc}) > 4
                    AND SUBSTR({trimmed_disc}, -4) GLOB '[0-9][0-9][0-9][0-9]'
                    AND (LENGTH({trimmed_disc}) = 4
                        OR SUBSTR({trimmed_disc}, -5, 1) NOT GLOB '[0-9]')
                THEN SUBSTR({trimmed_disc}, 1, LENGTH({trimmed_disc}) - 4)
                ELSE {trimmed_disc}
            END
        ))"""

        cursor.execute(f'''
            SELECT
                MAX(discovered_by) as discoverer,
                {normalized_disc} as normalized_name,
                COUNT(*) as total,
                COUNT(DISTINCT type_slug) as unique_types
            FROM discoveries
            WHERE 1=1 {disc_tag_filter} {disc_date_filter}
            GROUP BY {normalized_disc}
            HAVING {normalized_disc} != 'unknown'
            ORDER BY total DESC
            LIMIT 5
        ''', disc_tag_params + disc_date_params)
        top_discoverers = [dict(row) for row in cursor.fetchall()]

        # --- Activity trend (last 7 days of submissions + discoveries) ---
        cursor.execute(f'''
            SELECT
                date(submission_date) as date,
                COUNT(*) as submissions
            FROM pending_systems
            WHERE submission_date >= date('now', '-7 days')
              {sub_tag_filter}
            GROUP BY date(submission_date)
            ORDER BY date ASC
        ''', sub_tag_params)
        sub_trend = {row['date']: row['submissions'] for row in cursor.fetchall()}

        cursor.execute(f'''
            SELECT
                date(submission_timestamp) as date,
                COUNT(*) as discoveries
            FROM discoveries
            WHERE submission_timestamp >= date('now', '-7 days')
              {disc_tag_filter}
            GROUP BY date(submission_timestamp)
            ORDER BY date ASC
        ''', disc_tag_params)
        disc_trend = {row['date']: row['discoveries'] for row in cursor.fetchall()}

        # Merge trends
        all_dates = sorted(set(list(sub_trend.keys()) + list(disc_trend.keys())))
        activity_trend = [
            {
                'date': d,
                'submissions': sub_trend.get(d, 0),
                'discoveries': disc_trend.get(d, 0)
            }
            for d in all_dates
        ]

        return {
            'submissions': {
                'total': sub_stats.get('total_submissions', 0),
                'approved': sub_stats.get('total_approved', 0),
                'rejected': sub_stats.get('total_rejected', 0),
                'pending': sub_stats.get('total_pending', 0),
                'active_submitters': active_submitters
            },
            'discoveries': {
                'total': disc_stats.get('total_discoveries', 0),
                'active_discoverers': disc_stats.get('active_discoverers', 0),
                'unique_types': disc_stats.get('unique_types', 0)
            },
            'top_submitters': top_submitters,
            'top_discoverers': top_discoverers,
            'activity_trend': activity_trend
        }
    finally:
        if conn:
            conn.close()


# ============================================================================
# Events Endpoints (for submission events/competitions)
# ============================================================================

@app.get('/api/events')
async def list_events(
    include_inactive: bool = False,
    session: Optional[str] = Cookie(None)
):
    """
    List submission events.
    Partners see their own community's events.
    Super admins see all.
    """
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail='Authentication required')

    is_super = session_data.get('user_type') == 'super_admin'
    user_discord_tag = session_data.get('discord_tag')

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        query = 'SELECT * FROM events WHERE 1=1'
        params = []

        if not is_super and user_discord_tag:
            query += ' AND discord_tag = ?'
            params.append(user_discord_tag)

        if not include_inactive:
            query += ' AND is_active = 1'

        query += ' ORDER BY start_date DESC'
        cursor.execute(query, params)
        rows = cursor.fetchall()

        events = []

        # Define username extraction (same as Analytics for consistency)
        # Skip 'Anonymous' and 'anonymous' values to find the actual username
        raw_username = '''COALESCE(
            NULLIF(NULLIF(submitted_by, 'Anonymous'), 'anonymous'),
            personal_discord_username,
            json_extract(system_data, '$.discovered_by'),
            'Unknown'
        )'''
        # Normalize: trim, remove #, strip trailing 4-digit Discord discriminator, lowercase
        trimmed_username = f'''TRIM(REPLACE({raw_username}, '#', ''))'''
        normalized_username = f'''LOWER(TRIM(
            CASE
                WHEN LENGTH({trimmed_username}) > 4
                    AND SUBSTR({trimmed_username}, -4) GLOB '[0-9][0-9][0-9][0-9]'
                    AND (LENGTH({trimmed_username}) = 4
                        OR SUBSTR({trimmed_username}, -5, 1) NOT GLOB '[0-9]')
                THEN SUBSTR({trimmed_username}, 1, LENGTH({trimmed_username}) - 4)
                ELSE {trimmed_username}
            END
        ))'''

        for row in rows:
            event = dict(row)
            event_type = event.get('event_type', 'submissions') or 'submissions'

            # Get submission count and participant count for this event
            if event_type in ('submissions', 'both'):
                cursor.execute(f'''
                    SELECT COUNT(*) as submissions,
                           COUNT(DISTINCT CASE WHEN {normalized_username} != 'unknown' THEN {normalized_username} END) as participants
                    FROM pending_systems
                    WHERE discord_tag = ?
                      AND submission_date >= ?
                      AND submission_date <= ?
                ''', (event['discord_tag'], event['start_date'], event['end_date'] + 'T23:59:59'))
                stats = cursor.fetchone()
                event['submission_count'] = stats['submissions'] or 0
                event['participant_count'] = stats['participants'] or 0
            else:
                event['submission_count'] = 0
                event['participant_count'] = 0

            # Get discovery count and participant count for discovery events
            if event_type in ('discoveries', 'both'):
                cursor.execute('''
                    SELECT COUNT(*) as discoveries,
                           COUNT(DISTINCT LOWER(TRIM(discovered_by))) as disc_participants
                    FROM discoveries
                    WHERE discord_tag = ?
                      AND submission_timestamp >= ?
                      AND submission_timestamp <= ?
                      AND LOWER(TRIM(discovered_by)) != 'anonymous'
                      AND LOWER(TRIM(discovered_by)) != 'unknown'
                ''', (event['discord_tag'], event['start_date'], event['end_date'] + 'T23:59:59'))
                disc_stats = cursor.fetchone()
                event['discovery_count'] = disc_stats['discoveries'] or 0
                event['discovery_participant_count'] = disc_stats['disc_participants'] or 0
            else:
                event['discovery_count'] = 0
                event['discovery_participant_count'] = 0

            # Check if event is currently active (based on dates)
            now = datetime.now().isoformat()
            event['is_current'] = event['start_date'] <= now <= event['end_date'] + 'T23:59:59'

            events.append(event)

        return {'events': events}
    finally:
        if conn:
            conn.close()


@app.post('/api/events')
async def create_event(request: Request, session: Optional[str] = Cookie(None)):
    """
    Create a new submission event.
    Partners can create events for their community.
    Super admins can create for any community.
    """
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail='Authentication required')

    is_super = session_data.get('user_type') == 'super_admin'
    user_discord_tag = session_data.get('discord_tag')

    body = await request.json()
    name = body.get('name')
    discord_tag = body.get('discord_tag')
    start_date = body.get('start_date')
    end_date = body.get('end_date')
    description = body.get('description', '')
    event_type = body.get('event_type', 'submissions')

    if event_type not in ('submissions', 'discoveries', 'both'):
        event_type = 'submissions'

    if not all([name, start_date, end_date]):
        raise HTTPException(status_code=400, detail='name, start_date, and end_date are required')

    # Partners can only create events for their own community
    if not is_super:
        if user_discord_tag:
            discord_tag = user_discord_tag
        else:
            raise HTTPException(status_code=403, detail='Cannot create events without a community')

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO events (name, discord_tag, start_date, end_date, description, created_by, event_type)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (name, discord_tag, start_date, end_date, description, session_data.get('username'), event_type))

        conn.commit()
        event_id = cursor.lastrowid

        return {'success': True, 'event_id': event_id}
    finally:
        if conn:
            conn.close()


@app.get('/api/events/{event_id}')
async def get_event(event_id: int, session: Optional[str] = Cookie(None)):
    """Get a single event by ID."""
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail='Authentication required')

    is_super = session_data.get('user_type') == 'super_admin'
    user_discord_tag = session_data.get('discord_tag')

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM events WHERE id = ?', (event_id,))
        row = cursor.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail='Event not found')

        event = dict(row)

        # Check access
        if not is_super and user_discord_tag != event['discord_tag']:
            raise HTTPException(status_code=403, detail='Access denied')

        return {'event': event}
    finally:
        if conn:
            conn.close()


@app.get('/api/events/{event_id}/leaderboard')
async def get_event_leaderboard(
    event_id: int,
    tab: str = 'submissions',
    limit: int = 50,
    session: Optional[str] = Cookie(None)
):
    """
    Get leaderboard for a specific event.
    Shows submissions and/or discoveries during the event period.

    Args:
        tab: 'submissions', 'discoveries', or 'combined'
    """
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail='Authentication required')

    is_super = session_data.get('user_type') == 'super_admin'
    user_discord_tag = session_data.get('discord_tag')

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Get event details
        cursor.execute('SELECT * FROM events WHERE id = ?', (event_id,))
        event_row = cursor.fetchone()

        if not event_row:
            raise HTTPException(status_code=404, detail='Event not found')

        event = dict(event_row)

        # Check access
        if not is_super and user_discord_tag != event['discord_tag']:
            raise HTTPException(status_code=403, detail='Access denied')

        # Normalize usernames for submission leaderboard
        raw_username = '''COALESCE(
            NULLIF(NULLIF(submitted_by, 'Anonymous'), 'anonymous'),
            personal_discord_username,
            json_extract(system_data, '$.discovered_by'),
            'Unknown'
        )'''
        trimmed_username = f'''TRIM(REPLACE({raw_username}, '#', ''))'''
        normalized_username = f'''LOWER(TRIM(
            CASE
                WHEN LENGTH({trimmed_username}) > 4
                    AND SUBSTR({trimmed_username}, -4) GLOB '[0-9][0-9][0-9][0-9]'
                    AND (LENGTH({trimmed_username}) = 4
                        OR SUBSTR({trimmed_username}, -5, 1) NOT GLOB '[0-9]')
                THEN SUBSTR({trimmed_username}, 1, LENGTH({trimmed_username}) - 4)
                ELSE {trimmed_username}
            END
        ))'''

        leaderboard = []
        totals = {}

        if tab == 'submissions':
            # Original submission leaderboard logic
            query = f'''
                SELECT
                    MAX({raw_username}) as username,
                    COUNT(*) as total_submissions,
                    SUM(CASE WHEN status = 'approved' THEN 1 ELSE 0 END) as approved,
                    SUM(CASE WHEN status = 'rejected' THEN 1 ELSE 0 END) as rejected,
                    MIN(submission_date) as first_submission,
                    MAX(submission_date) as last_submission
                FROM pending_systems
                WHERE discord_tag = ?
                  AND submission_date >= ?
                  AND submission_date <= ?
                GROUP BY {normalized_username}
                HAVING {normalized_username} != 'unknown'
                ORDER BY total_submissions DESC
                LIMIT ?
            '''
            cursor.execute(query, (event['discord_tag'], event['start_date'],
                                   event['end_date'] + 'T23:59:59', limit))
            rows = cursor.fetchall()

            rank = 1
            for row in rows:
                entry = dict(row)
                entry['rank'] = rank
                total = entry['total_submissions']
                approved = entry['approved'] or 0
                entry['approval_rate'] = round((approved / total * 100), 1) if total > 0 else 0
                leaderboard.append(entry)
                rank += 1

            cursor.execute(f'''
                SELECT
                    COUNT(*) as total_submissions,
                    SUM(CASE WHEN status = 'approved' THEN 1 ELSE 0 END) as total_approved,
                    COUNT(DISTINCT CASE WHEN {normalized_username} != 'unknown' THEN {normalized_username} END) as participants
                FROM pending_systems
                WHERE discord_tag = ?
                  AND submission_date >= ?
                  AND submission_date <= ?
            ''', (event['discord_tag'], event['start_date'], event['end_date'] + 'T23:59:59'))
            totals_row = cursor.fetchone()

            totals = {
                'total_submissions': totals_row['total_submissions'] or 0,
                'total_approved': totals_row['total_approved'] or 0,
                'participants': totals_row['participants'] or 0
            }

        elif tab == 'discoveries':
            # Discovery leaderboard
            cursor.execute('''
                SELECT
                    discovered_by as username,
                    COUNT(*) as total_discoveries,
                    COUNT(DISTINCT type_slug) as types_count,
                    GROUP_CONCAT(DISTINCT type_slug) as type_slugs,
                    MIN(submission_timestamp) as first_discovery,
                    MAX(submission_timestamp) as last_discovery
                FROM discoveries
                WHERE discord_tag = ?
                  AND submission_timestamp >= ?
                  AND submission_timestamp <= ?
                  AND LOWER(TRIM(discovered_by)) != 'anonymous'
                  AND LOWER(TRIM(discovered_by)) != 'unknown'
                GROUP BY LOWER(TRIM(discovered_by))
                ORDER BY total_discoveries DESC
                LIMIT ?
            ''', (event['discord_tag'], event['start_date'],
                  event['end_date'] + 'T23:59:59', limit))
            rows = cursor.fetchall()

            rank = 1
            for row in rows:
                entry = dict(row)
                entry['rank'] = rank
                leaderboard.append(entry)
                rank += 1

            cursor.execute('''
                SELECT
                    COUNT(*) as total_discoveries,
                    COUNT(DISTINCT LOWER(TRIM(discovered_by))) as participants
                FROM discoveries
                WHERE discord_tag = ?
                  AND submission_timestamp >= ?
                  AND submission_timestamp <= ?
                  AND LOWER(TRIM(discovered_by)) != 'anonymous'
                  AND LOWER(TRIM(discovered_by)) != 'unknown'
            ''', (event['discord_tag'], event['start_date'], event['end_date'] + 'T23:59:59'))
            totals_row = cursor.fetchone()

            totals = {
                'total_discoveries': totals_row['total_discoveries'] or 0,
                'participants': totals_row['participants'] or 0
            }

        elif tab == 'combined':
            # Combined: merge submissions + discoveries by normalized username
            # Get submission counts per user
            cursor.execute(f'''
                SELECT
                    {normalized_username} as norm_user,
                    MAX({raw_username}) as username,
                    COUNT(*) as total_submissions,
                    SUM(CASE WHEN status = 'approved' THEN 1 ELSE 0 END) as approved
                FROM pending_systems
                WHERE discord_tag = ?
                  AND submission_date >= ?
                  AND submission_date <= ?
                GROUP BY {normalized_username}
                HAVING {normalized_username} != 'unknown'
            ''', (event['discord_tag'], event['start_date'], event['end_date'] + 'T23:59:59'))

            user_data = {}
            for row in cursor.fetchall():
                r = dict(row)
                norm = r['norm_user']
                user_data[norm] = {
                    'username': r['username'],
                    'total_submissions': r['total_submissions'],
                    'approved': r['approved'] or 0,
                    'total_discoveries': 0
                }

            # Get discovery counts per user
            cursor.execute('''
                SELECT
                    LOWER(TRIM(discovered_by)) as norm_user,
                    discovered_by as username,
                    COUNT(*) as total_discoveries
                FROM discoveries
                WHERE discord_tag = ?
                  AND submission_timestamp >= ?
                  AND submission_timestamp <= ?
                  AND LOWER(TRIM(discovered_by)) != 'anonymous'
                  AND LOWER(TRIM(discovered_by)) != 'unknown'
                GROUP BY LOWER(TRIM(discovered_by))
            ''', (event['discord_tag'], event['start_date'], event['end_date'] + 'T23:59:59'))

            for row in cursor.fetchall():
                r = dict(row)
                norm = r['norm_user']
                if norm in user_data:
                    user_data[norm]['total_discoveries'] = r['total_discoveries']
                else:
                    user_data[norm] = {
                        'username': r['username'],
                        'total_submissions': 0,
                        'approved': 0,
                        'total_discoveries': r['total_discoveries']
                    }

            # Sort by combined total
            sorted_users = sorted(
                user_data.values(),
                key=lambda u: u['total_submissions'] + u['total_discoveries'],
                reverse=True
            )[:limit]

            rank = 1
            for entry in sorted_users:
                entry['rank'] = rank
                entry['combined_total'] = entry['total_submissions'] + entry['total_discoveries']
                leaderboard.append(entry)
                rank += 1

            # Combined totals
            sub_total = sum(u['total_submissions'] for u in user_data.values())
            disc_total = sum(u['total_discoveries'] for u in user_data.values())
            totals = {
                'total_submissions': sub_total,
                'total_discoveries': disc_total,
                'combined_total': sub_total + disc_total,
                'participants': len(user_data)
            }

        return {
            'event': event,
            'leaderboard': leaderboard,
            'totals': totals,
            'tab': tab
        }
    finally:
        if conn:
            conn.close()


@app.put('/api/events/{event_id}')
async def update_event(event_id: int, request: Request, session: Optional[str] = Cookie(None)):
    """Update an event."""
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail='Authentication required')

    is_super = session_data.get('user_type') == 'super_admin'
    user_discord_tag = session_data.get('discord_tag')

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Check event exists and access
        cursor.execute('SELECT * FROM events WHERE id = ?', (event_id,))
        event_row = cursor.fetchone()

        if not event_row:
            raise HTTPException(status_code=404, detail='Event not found')

        if not is_super and user_discord_tag != event_row['discord_tag']:
            raise HTTPException(status_code=403, detail='Access denied')

        body = await request.json()

        # Build update query
        updates = []
        params = []

        for field in ['name', 'start_date', 'end_date', 'description', 'is_active', 'event_type']:
            if field in body:
                if field == 'event_type' and body[field] not in ('submissions', 'discoveries', 'both'):
                    continue
                updates.append(f'{field} = ?')
                params.append(body[field])

        if updates:
            params.append(event_id)
            cursor.execute(f'''
                UPDATE events SET {', '.join(updates)} WHERE id = ?
            ''', params)
            conn.commit()

        return {'success': True}
    finally:
        if conn:
            conn.close()


@app.delete('/api/events/{event_id}')
async def delete_event(event_id: int, session: Optional[str] = Cookie(None)):
    """Delete an event."""
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail='Authentication required')

    is_super = session_data.get('user_type') == 'super_admin'
    user_discord_tag = session_data.get('discord_tag')

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Check event exists and access
        cursor.execute('SELECT * FROM events WHERE id = ?', (event_id,))
        event_row = cursor.fetchone()

        if not event_row:
            raise HTTPException(status_code=404, detail='Event not found')

        if not is_super and user_discord_tag != event_row['discord_tag']:
            raise HTTPException(status_code=403, detail='Access denied')

        cursor.execute('DELETE FROM events WHERE id = ?', (event_id,))
        conn.commit()

        return {'success': True}
    finally:
        if conn:
            conn.close()


# Get list of available discord tags (for dropdowns)
@app.get('/api/discord_tags')
async def list_discord_tags():
    """List available discord tags for system tagging (public endpoint)"""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT discord_tag, display_name, username
            FROM partner_accounts
            WHERE discord_tag IS NOT NULL AND is_active = 1
            ORDER BY display_name
        ''')
        # Start with Haven and Personal options (always available)
        tags = [
            {'tag': 'Haven', 'name': 'Haven'},
            {'tag': 'Personal', 'name': 'Personal (Not affiliated)'},
        ]
        # Add partner tags (skip Haven if a partner already has it to avoid duplicates)
        seen_tags = {t['tag'] for t in tags}
        for row in cursor.fetchall():
            if row['discord_tag'] not in seen_tags:
                tags.append({'tag': row['discord_tag'], 'name': row['display_name'] or row['username']})
                seen_tags.add(row['discord_tag'])
        return {'tags': tags}
    finally:
        if conn:
            conn.close()


# ============================================================================
# Pending Edit Requests (for partner edit approval workflow)
# ============================================================================

@app.get('/api/pending_edits')
async def list_pending_edits(session: Optional[str] = Cookie(None)):
    """List pending edit requests (super admin sees all, partners see their own)"""
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail='Authentication required')

    is_super = session_data.get('user_type') == 'super_admin'
    partner_id = session_data.get('partner_id')

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        if is_super:
            cursor.execute('''
                SELECT per.*, s.name as system_name,
                       pa.username as partner_username,
                       pa.display_name as partner_display_name,
                       pa.discord_tag as partner_discord_tag
                FROM pending_edit_requests per
                JOIN systems s ON per.system_id = s.id
                JOIN partner_accounts pa ON per.partner_id = pa.id
                WHERE per.status = 'pending'
                ORDER BY per.submitted_at DESC
            ''')
        else:
            cursor.execute('''
                SELECT per.*, s.name as system_name
                FROM pending_edit_requests per
                JOIN systems s ON per.system_id = s.id
                WHERE per.partner_id = ?
                ORDER BY per.submitted_at DESC
            ''', (partner_id,))

        requests = [dict(row) for row in cursor.fetchall()]
        for r in requests:
            try:
                r['edit_data'] = json.loads(r['edit_data'])
            except:
                pass
        return {'requests': requests}
    finally:
        if conn:
            conn.close()

@app.get('/api/pending_edits/count')
async def pending_edits_count(session: Optional[str] = Cookie(None)):
    """Get count of pending edit requests (for navbar badge)"""
    if not is_super_admin(session):
        return {'count': 0}

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as count FROM pending_edit_requests WHERE status = 'pending'")
        row = cursor.fetchone()
        return {'count': row['count'] if row else 0}
    finally:
        if conn:
            conn.close()

@app.post('/api/pending_edits/{request_id}/approve')
async def approve_edit_request(request_id: int, session: Optional[str] = Cookie(None)):
    """Approve a pending edit request and apply the changes (super admin only)"""
    if not is_super_admin(session):
        raise HTTPException(status_code=403, detail='Super admin access required')

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM pending_edit_requests WHERE id = ?', (request_id,))
        request = cursor.fetchone()
        if not request:
            raise HTTPException(status_code=404, detail='Request not found')
        if request['status'] != 'pending':
            raise HTTPException(status_code=400, detail='Request already processed')

        # Mark as approved
        cursor.execute('''
            UPDATE pending_edit_requests
            SET status = 'approved', reviewed_by = 'super_admin', review_date = ?
            WHERE id = ?
        ''', (datetime.now(timezone.utc).isoformat(), request_id))

        conn.commit()

        # Note: The actual edit application would require calling save_system logic
        # For now, we just mark as approved - super admin can manually apply if needed
        # or we could expand this to actually apply the edit_data

        return {'status': 'ok', 'message': 'Edit request approved'}
    finally:
        if conn:
            conn.close()

@app.post('/api/pending_edits/{request_id}/reject')
async def reject_edit_request(request_id: int, payload: dict = None, session: Optional[str] = Cookie(None)):
    """Reject a pending edit request (super admin only)"""
    if not is_super_admin(session):
        raise HTTPException(status_code=403, detail='Super admin access required')

    review_notes = (payload or {}).get('notes', '')

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM pending_edit_requests WHERE id = ?', (request_id,))
        request = cursor.fetchone()
        if not request:
            raise HTTPException(status_code=404, detail='Request not found')
        if request['status'] != 'pending':
            raise HTTPException(status_code=400, detail='Request already processed')

        cursor.execute('''
            UPDATE pending_edit_requests
            SET status = 'rejected', reviewed_by = 'super_admin', review_date = ?, review_notes = ?
            WHERE id = ?
        ''', (datetime.now(timezone.utc).isoformat(), review_notes, request_id))

        conn.commit()
        return {'status': 'ok', 'message': 'Edit request rejected'}
    finally:
        if conn:
            conn.close()


# ============================================================================
# Partner Theme Settings
# ============================================================================

@app.get('/api/partner/theme')
async def get_partner_theme(session: Optional[str] = Cookie(None)):
    """Get the current partner's theme settings"""
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail='Not authenticated')

    # Super admin doesn't have partner theme (uses global settings)
    if session_data.get('user_type') == 'super_admin':
        return {'theme': {}}

    partner_id = session_data.get('partner_id')
    if not partner_id:
        raise HTTPException(status_code=403, detail='Partner access required')

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT theme_settings FROM partner_accounts WHERE id = ?', (partner_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail='Partner account not found')

        theme = json.loads(row['theme_settings'] or '{}')
        return {'theme': theme}
    finally:
        if conn:
            conn.close()

@app.put('/api/partner/theme')
async def update_partner_theme(payload: dict, session: Optional[str] = Cookie(None)):
    """Update the current partner's theme settings"""
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail='Not authenticated')

    # Super admin doesn't have partner theme
    if session_data.get('user_type') == 'super_admin':
        raise HTTPException(status_code=400, detail='Super admin should use global theme settings')

    partner_id = session_data.get('partner_id')
    if not partner_id:
        raise HTTPException(status_code=403, detail='Partner access required')

    theme = payload.get('theme', {})

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('''
            UPDATE partner_accounts
            SET theme_settings = ?, updated_at = ?
            WHERE id = ?
        ''', (json.dumps(theme), datetime.now(timezone.utc).isoformat(), partner_id))

        conn.commit()
        return {'status': 'ok', 'theme': theme}
    finally:
        if conn:
            conn.close()


@app.put('/api/partner/region_color')
async def update_partner_region_color(payload: dict, session: Optional[str] = Cookie(None)):
    """Update the current partner's region color for the 3D map"""
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail='Not authenticated')

    # Only partners can set region colors (not super admin or sub-admin)
    if session_data.get('user_type') != 'partner':
        raise HTTPException(status_code=403, detail='Only partners can set region colors')

    partner_id = session_data.get('partner_id')
    if not partner_id:
        raise HTTPException(status_code=403, detail='Partner access required')

    color = payload.get('color', '#00C2B3')

    # Validate hex color format
    import re
    if not re.match(r'^#[0-9A-Fa-f]{6}$', color):
        raise HTTPException(status_code=400, detail='Invalid color format. Use hex format like #00C2B3')

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('''
            UPDATE partner_accounts
            SET region_color = ?, updated_at = ?
            WHERE id = ?
        ''', (color, datetime.now(timezone.utc).isoformat(), partner_id))

        conn.commit()
        logger.info(f"Partner {session_data.get('username')} updated region color to {color}")
        return {'status': 'ok', 'color': color}
    finally:
        if conn:
            conn.close()


@app.get('/api/partner/region_color')
async def get_partner_region_color(session: Optional[str] = Cookie(None)):
    """Get the current partner's region color"""
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail='Not authenticated')

    # Only partners have region colors
    if session_data.get('user_type') != 'partner':
        return {'color': '#00C2B3'}  # Return default for non-partners

    partner_id = session_data.get('partner_id')
    if not partner_id:
        return {'color': '#00C2B3'}

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT region_color FROM partner_accounts WHERE id = ?', (partner_id,))
        row = cursor.fetchone()

        color = row['region_color'] if row and row['region_color'] else '#00C2B3'
        return {'color': color}
    finally:
        if conn:
            conn.close()


@app.get('/api/discord_tag_colors')
async def get_discord_tag_colors():
    """Get all discord tag colors for the 3D map - PUBLIC endpoint"""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Get all active partners with their discord tags and region colors
        cursor.execute('''
            SELECT discord_tag, display_name, region_color
            FROM partner_accounts
            WHERE is_active = 1 AND discord_tag IS NOT NULL
        ''')

        colors = {}
        for row in cursor.fetchall():
            tag = row['discord_tag']
            color = row['region_color'] if row['region_color'] else '#00C2B3'
            colors[tag] = {
                'color': color,
                'name': row['display_name'] or tag
            }

        # Add default Haven color (super admin's systems)
        colors['Haven'] = {'color': '#00C2B3', 'name': 'Haven'}

        # Add personal submission color from settings
        personal_color = get_personal_color()
        colors['personal'] = {'color': personal_color, 'name': 'Personal'}

        return {'colors': colors}
    finally:
        if conn:
            conn.close()


# ============================================================================
# DATA RESTRICTIONS API ENDPOINTS
# ============================================================================

@app.get('/api/partner/my_systems')
async def get_partner_systems(session: Optional[str] = Cookie(None)):
    """Get all systems owned by the current partner with restriction status.

    Returns systems tagged with the partner's discord_tag, including
    whether each system has restrictions applied.
    """
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail='Not authenticated')

    # Get discord_tag - super admin sees all, partner sees their own
    discord_tag = None
    is_super_admin = session_data.get('user_type') == 'super_admin'

    if not is_super_admin:
        discord_tag = session_data.get('discord_tag')
        if not discord_tag:
            raise HTTPException(status_code=403, detail='Partner discord_tag required')

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Get systems with optional restriction data
        if is_super_admin:
            cursor.execute('''
                SELECT s.id, s.name, s.galaxy, s.discord_tag, s.x, s.y, s.z,
                       s.region_x, s.region_y, s.region_z, s.glyph_code,
                       r.custom_name as region_name,
                       dr.id as restriction_id,
                       dr.is_hidden_from_public,
                       dr.hidden_fields,
                       dr.map_visibility
                FROM systems s
                LEFT JOIN regions r ON s.region_x = r.region_x
                    AND s.region_y = r.region_y AND s.region_z = r.region_z
                LEFT JOIN data_restrictions dr ON s.id = dr.system_id
                ORDER BY s.discord_tag, s.name
            ''')
        else:
            cursor.execute('''
                SELECT s.id, s.name, s.galaxy, s.discord_tag, s.x, s.y, s.z,
                       s.region_x, s.region_y, s.region_z, s.glyph_code,
                       r.custom_name as region_name,
                       dr.id as restriction_id,
                       dr.is_hidden_from_public,
                       dr.hidden_fields,
                       dr.map_visibility
                FROM systems s
                LEFT JOIN regions r ON s.region_x = r.region_x
                    AND s.region_y = r.region_y AND s.region_z = r.region_z
                LEFT JOIN data_restrictions dr ON s.id = dr.system_id
                WHERE s.discord_tag = ?
                ORDER BY s.name
            ''', (discord_tag,))

        rows = cursor.fetchall()
        systems = []
        for row in rows:
            system = {
                'id': row['id'],
                'name': row['name'],
                'galaxy': row['galaxy'],
                'discord_tag': row['discord_tag'],
                'x': row['x'],
                'y': row['y'],
                'z': row['z'],
                'region_x': row['region_x'],
                'region_y': row['region_y'],
                'region_z': row['region_z'],
                'region_name': row['region_name'],
                'glyph_code': row['glyph_code'],
                'has_restriction': row['restriction_id'] is not None,
                'restriction': None
            }
            if row['restriction_id']:
                system['restriction'] = {
                    'id': row['restriction_id'],
                    'is_hidden_from_public': bool(row['is_hidden_from_public']),
                    'hidden_fields': json.loads(row['hidden_fields'] or '[]'),
                    'map_visibility': row['map_visibility'] or 'normal'
                }
            systems.append(system)

        return {'systems': systems, 'total': len(systems)}
    finally:
        if conn:
            conn.close()


@app.get('/api/data_restrictions')
async def get_data_restrictions(session: Optional[str] = Cookie(None)):
    """Get all data restrictions for the current partner's systems.

    Super admin gets all restrictions, partners get their own discord_tag's restrictions.
    """
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail='Not authenticated')

    is_super_admin = session_data.get('user_type') == 'super_admin'
    discord_tag = session_data.get('discord_tag')

    if not is_super_admin and not discord_tag:
        raise HTTPException(status_code=403, detail='Partner discord_tag required')

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        if is_super_admin:
            cursor.execute('''
                SELECT dr.*, s.name as system_name, s.galaxy
                FROM data_restrictions dr
                JOIN systems s ON dr.system_id = s.id
                ORDER BY dr.discord_tag, s.name
            ''')
        else:
            cursor.execute('''
                SELECT dr.*, s.name as system_name, s.galaxy
                FROM data_restrictions dr
                JOIN systems s ON dr.system_id = s.id
                WHERE dr.discord_tag = ?
                ORDER BY s.name
            ''', (discord_tag,))

        rows = cursor.fetchall()
        restrictions = [{
            'id': row['id'],
            'system_id': row['system_id'],
            'system_name': row['system_name'],
            'galaxy': row['galaxy'],
            'discord_tag': row['discord_tag'],
            'is_hidden_from_public': bool(row['is_hidden_from_public']),
            'hidden_fields': json.loads(row['hidden_fields'] or '[]'),
            'map_visibility': row['map_visibility'] or 'normal',
            'created_at': row['created_at'],
            'updated_at': row['updated_at'],
            'created_by': row['created_by']
        } for row in rows]

        return {'restrictions': restrictions, 'total': len(restrictions)}
    finally:
        if conn:
            conn.close()


@app.post('/api/data_restrictions')
async def save_data_restriction(payload: dict, session: Optional[str] = Cookie(None)):
    """Create or update a data restriction for a system.

    Partners can only modify restrictions for systems with their discord_tag.
    Super admin can modify any restriction.
    """
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail='Not authenticated')

    system_id = payload.get('system_id')
    if not system_id:
        raise HTTPException(status_code=400, detail='system_id is required')

    is_hidden = payload.get('is_hidden_from_public', False)
    hidden_fields = payload.get('hidden_fields', [])
    map_visibility = payload.get('map_visibility', 'normal')

    # Validate map_visibility
    if map_visibility not in ['normal', 'point_only', 'hidden']:
        raise HTTPException(status_code=400, detail='Invalid map_visibility value')

    # Validate hidden_fields
    valid_fields = list(RESTRICTABLE_FIELDS.keys())
    for field in hidden_fields:
        if field not in valid_fields:
            raise HTTPException(status_code=400, detail=f'Invalid hidden_field: {field}')

    is_super_admin = session_data.get('user_type') == 'super_admin'
    partner_discord_tag = session_data.get('discord_tag')
    username = session_data.get('username', 'Unknown')

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Verify system exists and get its discord_tag
        cursor.execute('SELECT id, discord_tag FROM systems WHERE id = ?', (system_id,))
        system = cursor.fetchone()
        if not system:
            raise HTTPException(status_code=404, detail='System not found')

        system_discord_tag = system['discord_tag']

        # Permission check - partner can only modify their own systems
        if not is_super_admin:
            if system_discord_tag != partner_discord_tag:
                raise HTTPException(status_code=403, detail='You can only modify restrictions for your own systems')

        now = datetime.now(timezone.utc).isoformat()

        # Check if restriction already exists
        cursor.execute('SELECT id FROM data_restrictions WHERE system_id = ?', (system_id,))
        existing = cursor.fetchone()

        if existing:
            # Update existing restriction
            cursor.execute('''
                UPDATE data_restrictions
                SET is_hidden_from_public = ?,
                    hidden_fields = ?,
                    map_visibility = ?,
                    updated_at = ?
                WHERE system_id = ?
            ''', (1 if is_hidden else 0, json.dumps(hidden_fields), map_visibility, now, system_id))
        else:
            # Create new restriction
            cursor.execute('''
                INSERT INTO data_restrictions
                (system_id, discord_tag, is_hidden_from_public, hidden_fields, map_visibility, created_at, updated_at, created_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (system_id, system_discord_tag, 1 if is_hidden else 0,
                  json.dumps(hidden_fields), map_visibility, now, now, username))

        conn.commit()

        # Log activity
        add_activity_log(
            'restriction_updated',
            f'Data restriction {"updated" if existing else "created"} for system ID {system_id}',
            json.dumps({'system_id': system_id, 'is_hidden': is_hidden, 'map_visibility': map_visibility}),
            username
        )

        return {'status': 'ok', 'message': 'Restriction saved'}
    finally:
        if conn:
            conn.close()


@app.post('/api/data_restrictions/bulk')
async def save_bulk_restrictions(payload: dict, session: Optional[str] = Cookie(None)):
    """Apply the same restriction settings to multiple systems.

    Partners can only modify restrictions for systems with their discord_tag.
    Super admin can modify any restriction.
    """
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail='Not authenticated')

    system_ids = payload.get('system_ids', [])
    if not system_ids or not isinstance(system_ids, list):
        raise HTTPException(status_code=400, detail='system_ids array is required')

    is_hidden = payload.get('is_hidden_from_public', False)
    hidden_fields = payload.get('hidden_fields', [])
    map_visibility = payload.get('map_visibility', 'normal')

    # Validate map_visibility
    if map_visibility not in ['normal', 'point_only', 'hidden']:
        raise HTTPException(status_code=400, detail='Invalid map_visibility value')

    # Validate hidden_fields
    valid_fields = list(RESTRICTABLE_FIELDS.keys())
    for field in hidden_fields:
        if field not in valid_fields:
            raise HTTPException(status_code=400, detail=f'Invalid hidden_field: {field}')

    is_super_admin = session_data.get('user_type') == 'super_admin'
    partner_discord_tag = session_data.get('discord_tag')
    username = session_data.get('username', 'Unknown')

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        updated = 0
        created = 0
        skipped = 0
        now = datetime.now(timezone.utc).isoformat()

        for system_id in system_ids:
            # Verify system exists and get its discord_tag
            cursor.execute('SELECT id, discord_tag FROM systems WHERE id = ?', (system_id,))
            system = cursor.fetchone()
            if not system:
                skipped += 1
                continue

            system_discord_tag = system['discord_tag']

            # Permission check - partner can only modify their own systems
            if not is_super_admin and system_discord_tag != partner_discord_tag:
                skipped += 1
                continue

            # Check if restriction already exists
            cursor.execute('SELECT id FROM data_restrictions WHERE system_id = ?', (system_id,))
            existing = cursor.fetchone()

            if existing:
                cursor.execute('''
                    UPDATE data_restrictions
                    SET is_hidden_from_public = ?,
                        hidden_fields = ?,
                        map_visibility = ?,
                        updated_at = ?
                    WHERE system_id = ?
                ''', (1 if is_hidden else 0, json.dumps(hidden_fields), map_visibility, now, system_id))
                updated += 1
            else:
                cursor.execute('''
                    INSERT INTO data_restrictions
                    (system_id, discord_tag, is_hidden_from_public, hidden_fields, map_visibility, created_at, updated_at, created_by)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (system_id, system_discord_tag, 1 if is_hidden else 0,
                      json.dumps(hidden_fields), map_visibility, now, now, username))
                created += 1

        conn.commit()

        # Log activity
        add_activity_log(
            'restriction_bulk_update',
            f'Bulk restriction update: {created} created, {updated} updated, {skipped} skipped',
            json.dumps({'system_ids': system_ids, 'is_hidden': is_hidden, 'map_visibility': map_visibility}),
            username
        )

        return {'status': 'ok', 'created': created, 'updated': updated, 'skipped': skipped}
    finally:
        if conn:
            conn.close()


@app.delete('/api/data_restrictions/{system_id}')
async def delete_data_restriction(system_id: int, session: Optional[str] = Cookie(None)):
    """Remove a data restriction from a system (returns to public visibility).

    Partners can only remove restrictions for systems with their discord_tag.
    Super admin can remove any restriction.
    """
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail='Not authenticated')

    is_super_admin = session_data.get('user_type') == 'super_admin'
    partner_discord_tag = session_data.get('discord_tag')
    username = session_data.get('username', 'Unknown')

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Get the restriction and verify ownership
        cursor.execute('''
            SELECT dr.id, dr.discord_tag, s.name as system_name
            FROM data_restrictions dr
            JOIN systems s ON dr.system_id = s.id
            WHERE dr.system_id = ?
        ''', (system_id,))
        restriction = cursor.fetchone()

        if not restriction:
            raise HTTPException(status_code=404, detail='Restriction not found')

        # Permission check
        if not is_super_admin and restriction['discord_tag'] != partner_discord_tag:
            raise HTTPException(status_code=403, detail='You can only remove restrictions for your own systems')

        cursor.execute('DELETE FROM data_restrictions WHERE system_id = ?', (system_id,))
        conn.commit()

        # Log activity
        add_activity_log(
            'restriction_removed',
            f'Data restriction removed from system: {restriction["system_name"]}',
            json.dumps({'system_id': system_id}),
            username
        )

        return {'status': 'ok', 'message': 'Restriction removed'}
    finally:
        if conn:
            conn.close()


@app.post('/api/data_restrictions/bulk_remove')
async def bulk_remove_restrictions(payload: dict, session: Optional[str] = Cookie(None)):
    """Remove restrictions from multiple systems at once.

    Partners can only remove restrictions for systems with their discord_tag.
    Super admin can remove any restriction.
    """
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail='Not authenticated')

    system_ids = payload.get('system_ids', [])
    if not system_ids or not isinstance(system_ids, list):
        raise HTTPException(status_code=400, detail='system_ids array is required')

    is_super_admin = session_data.get('user_type') == 'super_admin'
    partner_discord_tag = session_data.get('discord_tag')
    username = session_data.get('username', 'Unknown')

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        removed = 0
        skipped = 0

        for system_id in system_ids:
            # Get the restriction and verify ownership
            cursor.execute('SELECT id, discord_tag FROM data_restrictions WHERE system_id = ?', (system_id,))
            restriction = cursor.fetchone()

            if not restriction:
                skipped += 1
                continue

            # Permission check
            if not is_super_admin and restriction['discord_tag'] != partner_discord_tag:
                skipped += 1
                continue

            cursor.execute('DELETE FROM data_restrictions WHERE system_id = ?', (system_id,))
            removed += 1

        conn.commit()

        # Log activity
        add_activity_log(
            'restriction_bulk_remove',
            f'Bulk restriction removal: {removed} removed, {skipped} skipped',
            json.dumps({'system_ids': system_ids}),
            username
        )

        return {'status': 'ok', 'removed': removed, 'skipped': skipped}
    finally:
        if conn:
            conn.close()


# ============================================================================
# API Key Authentication (for NMS Save Watcher companion app)
# ============================================================================

from fastapi import Header

def hash_api_key(key: str) -> str:
    """Hash an API key using SHA256."""
    return hashlib.sha256(key.encode()).hexdigest()


def generate_api_key() -> str:
    """Generate a new API key with 'vh_live_' prefix."""
    random_part = secrets.token_urlsafe(32)
    return f"vh_live_{random_part}"


def verify_api_key(api_key: Optional[str]) -> Optional[dict]:
    """
    Verify an API key and return key info if valid.
    Returns None if key is invalid or inactive.
    """
    if not api_key:
        return None

    key_hash = hash_api_key(api_key)

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, name, permissions, rate_limit, is_active, created_by, discord_tag
            FROM api_keys WHERE key_hash = ?
        ''', (key_hash,))
        row = cursor.fetchone()

        if row and row['is_active']:
            # Update last_used_at
            cursor.execute(
                'UPDATE api_keys SET last_used_at = ? WHERE id = ?',
                (datetime.now(timezone.utc).isoformat(), row['id'])
            )
            conn.commit()

            return {
                'id': row['id'],
                'name': row['name'],
                'permissions': json.loads(row['permissions'] or '["submit"]'),
                'rate_limit': row['rate_limit'],
                'created_by': row['created_by'],
                'discord_tag': row['discord_tag']
            }
        return None
    except Exception as e:
        logger.error(f"API key verification failed: {e}")
        return None
    finally:
        if conn:
            conn.close()


def check_api_key_rate_limit(key_id: int, limit: int = 200, window_hours: int = 1) -> tuple:
    """
    Check if API key has exceeded rate limit for system submissions.
    Returns (is_allowed, remaining_requests).
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        window_start = (datetime.now(timezone.utc) - timedelta(hours=window_hours)).isoformat()

        # Count submissions from this API key in the time window
        cursor.execute('''
            SELECT COUNT(*) FROM pending_systems
            WHERE api_key_name = (SELECT name FROM api_keys WHERE id = ?)
            AND submission_date >= ?
        ''', (key_id, window_start))
        count = cursor.fetchone()[0]
        return (count < limit, max(0, limit - count))
    except Exception as e:
        logger.warning(f"API key rate limit check failed: {e}")
        return (True, limit)  # Fail open
    finally:
        if conn:
            conn.close()


# ============================================================================
# API Key Management Endpoints
# ============================================================================

@app.post('/api/keys')
async def create_api_key(payload: dict, session: Optional[str] = Cookie(None)):
    """
    Create a new API key (admin only).
    Returns the key only once - it cannot be retrieved later.
    """
    if not verify_session(session):
        raise HTTPException(status_code=401, detail="Admin authentication required")

    name = payload.get('name', '').strip()
    if not name:
        raise HTTPException(status_code=400, detail="API key name is required")

    rate_limit = payload.get('rate_limit', 200)
    permissions = payload.get('permissions', ['submit', 'check_duplicate'])
    discord_tag = payload.get('discord_tag', '').strip() or None

    # Generate the key
    api_key = generate_api_key()
    key_hash = hash_api_key(api_key)
    key_prefix = api_key[:16]  # "vh_live_" + first 8 chars of random part

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Check for duplicate name
        cursor.execute('SELECT id FROM api_keys WHERE name = ?', (name,))
        if cursor.fetchone():
            raise HTTPException(status_code=409, detail=f"API key with name '{name}' already exists")

        cursor.execute('''
            INSERT INTO api_keys (key_hash, key_prefix, name, created_at, permissions, rate_limit, created_by, discord_tag)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            key_hash,
            key_prefix,
            name,
            datetime.now(timezone.utc).isoformat(),
            json.dumps(permissions),
            rate_limit,
            'admin',
            discord_tag
        ))

        key_id = cursor.lastrowid
        conn.commit()

        logger.info(f"Created API key: {name} (ID: {key_id}) with discord_tag: {discord_tag}")

        return {
            'id': key_id,
            'name': name,
            'key': api_key,  # Only returned once!
            'key_prefix': key_prefix,
            'rate_limit': rate_limit,
            'permissions': permissions,
            'discord_tag': discord_tag,
            'created_at': datetime.now(timezone.utc).isoformat(),
            'warning': 'Save this key now - it cannot be retrieved later!'
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create API key: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create API key: {str(e)}")
    finally:
        if conn:
            conn.close()


@app.get('/api/keys')
async def list_api_keys(session: Optional[str] = Cookie(None)):
    """
    List all API keys (admin only).
    Does not return the actual key values, only metadata.
    """
    if not verify_session(session):
        raise HTTPException(status_code=401, detail="Admin authentication required")

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, key_prefix, name, created_at, last_used_at, permissions, rate_limit, is_active, discord_tag
            FROM api_keys
            ORDER BY created_at DESC
        ''')
        rows = cursor.fetchall()

        keys = []
        for row in rows:
            keys.append({
                'id': row['id'],
                'key_prefix': row['key_prefix'],
                'name': row['name'],
                'created_at': row['created_at'],
                'last_used_at': row['last_used_at'],
                'permissions': json.loads(row['permissions'] or '[]'),
                'rate_limit': row['rate_limit'],
                'is_active': bool(row['is_active']),
                'discord_tag': row['discord_tag']
            })

        return {'keys': keys}

    except Exception as e:
        logger.error(f"Failed to list API keys: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list API keys: {str(e)}")
    finally:
        if conn:
            conn.close()


@app.delete('/api/keys/{key_id}')
async def revoke_api_key(key_id: int, session: Optional[str] = Cookie(None)):
    """
    Revoke (deactivate) an API key (admin only).
    The key remains in the database for audit purposes but is no longer valid.
    """
    if not verify_session(session):
        raise HTTPException(status_code=401, detail="Admin authentication required")

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT name FROM api_keys WHERE id = ?', (key_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="API key not found")

        cursor.execute('UPDATE api_keys SET is_active = 0 WHERE id = ?', (key_id,))
        conn.commit()

        logger.info(f"Revoked API key: {row['name']} (ID: {key_id})")

        return {'status': 'ok', 'message': f"API key '{row['name']}' has been revoked"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to revoke API key: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to revoke API key: {str(e)}")
    finally:
        if conn:
            conn.close()


@app.put('/api/keys/{key_id}')
async def update_api_key(key_id: int, payload: dict, session: Optional[str] = Cookie(None)):
    """
    Update an API key's settings (admin only).
    Can update: name, rate_limit, permissions, is_active, discord_tag
    """
    if not verify_session(session):
        raise HTTPException(status_code=401, detail="Admin authentication required")

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM api_keys WHERE id = ?', (key_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="API key not found")

        # Update allowed fields
        updates = []
        params = []

        if 'name' in payload:
            updates.append('name = ?')
            params.append(payload['name'])
        if 'rate_limit' in payload:
            updates.append('rate_limit = ?')
            params.append(payload['rate_limit'])
        if 'permissions' in payload:
            updates.append('permissions = ?')
            params.append(json.dumps(payload['permissions']))
        if 'is_active' in payload:
            updates.append('is_active = ?')
            params.append(1 if payload['is_active'] else 0)
        if 'discord_tag' in payload:
            updates.append('discord_tag = ?')
            # Allow setting to None by passing empty string or null
            discord_tag = payload['discord_tag']
            params.append(discord_tag if discord_tag else None)

        if updates:
            params.append(key_id)
            cursor.execute(f"UPDATE api_keys SET {', '.join(updates)} WHERE id = ?", params)
            conn.commit()

        return {'status': 'ok', 'message': 'API key updated'}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update API key: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update API key: {str(e)}")
    finally:
        if conn:
            conn.close()


# ============================================================================
# Duplicate Check Endpoint (for companion app)
# ============================================================================

@app.get('/api/check_duplicate')
async def check_duplicate(
    glyph_code: str,
    galaxy: str = 'Euclid',
    x_api_key: Optional[str] = Header(None, alias='X-API-Key')
):
    """
    Check if a system already exists at the given coordinates.
    Used by companion app to avoid uploading duplicates.
    Requires API key authentication.
    """
    # Verify API key
    key_info = verify_api_key(x_api_key)
    if not key_info:
        raise HTTPException(status_code=401, detail="Valid API key required")

    if 'check_duplicate' not in key_info['permissions'] and 'submit' not in key_info['permissions']:
        raise HTTPException(status_code=403, detail="API key lacks permission for duplicate checking")

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Check approved systems
        cursor.execute('''
            SELECT id, name FROM systems
            WHERE glyph_code = ? AND galaxy = ?
        ''', (glyph_code, galaxy))
        approved = cursor.fetchone()

        if approved:
            return {
                'exists': True,
                'location': 'approved',
                'system_id': approved['id'],
                'system_name': approved['name']
            }

        # Check pending systems
        cursor.execute('''
            SELECT id, system_name FROM pending_systems
            WHERE status = 'pending'
            AND json_extract(system_data, '$.glyph_code') = ?
            AND json_extract(system_data, '$.galaxy') = ?
        ''', (glyph_code, galaxy))
        pending = cursor.fetchone()

        if pending:
            return {
                'exists': True,
                'location': 'pending',
                'submission_id': pending['id'],
                'system_name': pending['system_name']
            }

        return {'exists': False}

    except Exception as e:
        logger.error(f"Duplicate check failed: {e}")
        raise HTTPException(status_code=500, detail=f"Duplicate check failed: {str(e)}")
    finally:
        if conn:
            conn.close()


@app.get('/api/systems/filter-options')
async def api_systems_filter_options(reality: str = None, galaxy: str = None):
    """Return distinct values for all filterable fields.

    Used by the AdvancedFilters component to populate dropdown options.
    Optionally scoped by reality and/or galaxy for relevant results.

    Returns:
        Dictionary with arrays of distinct values for each filter field.
    """
    conn = None
    try:
        db_path = get_db_path()
        if not db_path.exists():
            return {}

        conn = get_db_connection()
        cursor = conn.cursor()

        # Build optional WHERE clause for scoping
        sys_where_clauses = []
        sys_params = []
        if reality:
            sys_where_clauses.append("COALESCE(s.reality, 'Normal') = ?")
            sys_params.append(reality)
        if galaxy:
            sys_where_clauses.append("COALESCE(s.galaxy, 'Euclid') = ?")
            sys_params.append(galaxy)
        sys_where = ("WHERE " + " AND ".join(sys_where_clauses)) if sys_where_clauses else ""

        # Planet scope: join through system
        planet_where_clauses = []
        planet_params = []
        if reality:
            planet_where_clauses.append("COALESCE(s.reality, 'Normal') = ?")
            planet_params.append(reality)
        if galaxy:
            planet_where_clauses.append("COALESCE(s.galaxy, 'Euclid') = ?")
            planet_params.append(galaxy)
        planet_where = ("WHERE " + " AND ".join(planet_where_clauses)) if planet_where_clauses else ""
        planet_join = "JOIN systems s ON p.system_id = s.id" if planet_where_clauses else ""

        # System-level fields
        def get_distinct_system(column):
            cursor.execute(f"SELECT DISTINCT s.{column} FROM systems s {sys_where} ORDER BY s.{column}", sys_params)
            return [row[0] for row in cursor.fetchall() if row[0]]

        # Planet-level fields
        def get_distinct_planet(column):
            cursor.execute(f"SELECT DISTINCT p.{column} FROM planets p {planet_join} {planet_where} ORDER BY p.{column}", planet_params)
            return [row[0] for row in cursor.fetchall() if row[0]]

        # Collect all resources from 3 columns
        def get_distinct_resources():
            resources = set()
            for col in ['common_resource', 'uncommon_resource', 'rare_resource']:
                cursor.execute(f"SELECT DISTINCT p.{col} FROM planets p {planet_join} {planet_where}", planet_params)
                for row in cursor.fetchall():
                    if row[0]:
                        resources.add(row[0])
            return sorted(resources)

        return {
            'star_types': get_distinct_system('star_type'),
            'economy_types': get_distinct_system('economy_type'),
            'economy_levels': get_distinct_system('economy_level'),
            'conflict_levels': get_distinct_system('conflict_level'),
            'dominant_lifeforms': get_distinct_system('dominant_lifeform'),
            'stellar_classifications': get_distinct_system('stellar_classification'),
            'biomes': get_distinct_planet('biome'),
            'weather_types': get_distinct_planet('weather'),
            'sentinel_levels': get_distinct_planet('sentinel_level'),
            'resources': get_distinct_resources()
        }
    except Exception as e:
        logger.error(f"Error fetching filter options: {e}")
        return {}
    finally:
        if conn:
            conn.close()


def _is_filled(val, allow_none_sentinel=False):
    """Check if a field value represents real data (not empty/default).

    NMS has legitimate values like 'None' for sentinels (no sentinels present),
    'Absent' for fauna/flora, and 0 for hazards on peaceful planets.
    These are REAL data, not missing data.
    """
    if val is None:
        return False
    s = str(val).strip()
    if not s:
        return False
    # 'N/A' is always a DB default placeholder, never real game data
    if s == 'N/A':
        return False
    # 'None' is valid for sentinel level (means no sentinels) but is a
    # DB default for other fields - only allow it where specified
    if s == 'None' and not allow_none_sentinel:
        return False
    return True


# Biomes where fauna/flora are not expected (Dead, Gas Giant categories)
NO_LIFE_BIOMES = frozenset({
    'Dead', 'Lifeless', 'Life-Incompatible', 'Airless', 'Low Atmosphere',
    'Gas Giant', 'Empty',
})


def _life_descriptor_filled(val, val_text):
    """Check if a fauna/flora field has ANY value (including 'N/A', 'None', 'Absent').

    For fauna/flora, ANY non-empty string is real data - even 'N/A' or 'None'
    means the user reported that life is absent. Only NULL/empty means not answered.
    """
    for v in [val, val_text]:
        if v is not None:
            s = str(v).strip()
            if s:
                return True
    return False


def calculate_completeness_score(cursor, system_id: str) -> dict:
    """Calculate a data completeness score (0-100) for a system.

    Scoring philosophy: measure how much COLLECTIBLE data we actually have.
    Legitimate game values (sentinel='None', fauna='Absent', hazards=0) count
    as filled. Only true nulls/DB defaults count as missing.

    Planet Life uses a biome-aware dynamic denominator:
    - Fauna/flora are excluded from scoring on Dead/Airless/Gas Giant biomes
      where life is not expected (NULL = correctly not applicable)
    - Any non-empty fauna/flora value counts as filled (including 'N/A', 'Absent')
    - Resources always count (every planet has minable resources)

    Returns a dict with:
        score: int (0-100)
        grade: str ('S', 'A', 'B', 'C')
        breakdown: dict with category scores
    """
    # Fetch system row
    cursor.execute('SELECT * FROM systems WHERE id = ?', (system_id,))
    system = cursor.fetchone()
    if not system:
        return {'score': 0, 'grade': 'C', 'breakdown': {}}
    system = dict(system)

    # Fetch planets
    cursor.execute('SELECT * FROM planets WHERE system_id = ?', (system_id,))
    planets = [dict(row) for row in cursor.fetchall()]

    # Fetch space station
    cursor.execute('SELECT * FROM space_stations WHERE system_id = ?', (system_id,))
    station = cursor.fetchone()
    station = dict(station) if station else None

    # Field name labels for audit display
    FIELD_LABELS = {
        'star_type': 'Star Type', 'economy_type': 'Economy Type', 'economy_level': 'Economy Tier',
        'conflict_level': 'Conflict Level', 'dominant_lifeform': 'Dominant Lifeform',
        'glyph_code': 'Glyph Code', 'stellar_classification': 'Stellar Class', 'description': 'Description',
        'biome': 'Biome', 'weather': 'Weather', 'sentinel': 'Sentinels',
        'fauna': 'Fauna', 'flora': 'Flora',
        'common_resource': 'Common Resource', 'uncommon_resource': 'Uncommon Resource', 'rare_resource': 'Rare Resource',
    }

    # --- System Core (35 pts) ---
    # These are the 5 essential system properties everyone should fill in.
    # Abandoned/empty systems (economy_type='None'/'Abandoned') legitimately have
    # no economy tier, conflict level, or space station - treat those as filled.
    is_abandoned = system.get('economy_type') in ('None', 'Abandoned')
    sys_core_fields = ['star_type', 'economy_type', 'economy_level', 'conflict_level', 'dominant_lifeform']
    sys_core_filled = 0
    sys_core_details = []
    for f in sys_core_fields:
        val = system.get(f)
        if f in ('economy_type', 'economy_level', 'conflict_level') and is_abandoned:
            sys_core_filled += 1
            sys_core_details.append({'name': FIELD_LABELS[f], 'value': str(val) if val else 'N/A (Abandoned)', 'status': 'filled'})
        elif _is_filled(val):
            sys_core_filled += 1
            sys_core_details.append({'name': FIELD_LABELS[f], 'value': str(val), 'status': 'filled'})
        else:
            sys_core_details.append({'name': FIELD_LABELS[f], 'value': None, 'status': 'missing'})
    sys_core_score = round((sys_core_filled / len(sys_core_fields)) * 35)

    # --- System Extra (10 pts) ---
    # Bonus fields: glyph_code is important, stellar_classification is extractor-only, description is optional
    sys_extra_fields = ['glyph_code', 'stellar_classification', 'description']
    sys_extra_details = []
    sys_extra_filled = 0
    for f in sys_extra_fields:
        val = system.get(f)
        if _is_filled(val):
            sys_extra_filled += 1
            display = str(val)[:40] + ('...' if val and len(str(val)) > 40 else '')
            sys_extra_details.append({'name': FIELD_LABELS[f], 'value': display, 'status': 'filled'})
        else:
            sys_extra_details.append({'name': FIELD_LABELS[f], 'value': None, 'status': 'missing'})
    sys_extra_score = round((sys_extra_filled / len(sys_extra_fields)) * 10)

    # --- Planet Coverage (10 pts) ---
    has_planets = len(planets) > 0
    planet_coverage_score = 10 if has_planets else 0

    # --- Planet Environment avg (25 pts) ---
    # --- Planet Life avg (15 pts) ---
    planet_env_score = 0
    planet_life_score = 0
    planet_env_details = []
    planet_life_details = []

    if planets:
        env_totals = []
        life_totals = []

        for p in planets:
            p_name = p.get('name', 'Unknown')
            p_env_fields = []
            p_life_fields = []

            # Environment scoring
            env_filled = 0
            # Biome
            if _is_filled(p.get('biome')):
                env_filled += 1
                p_env_fields.append({'name': 'Biome', 'value': p.get('biome'), 'status': 'filled'})
            else:
                p_env_fields.append({'name': 'Biome', 'value': None, 'status': 'missing'})
            # Weather (with text fallback)
            weather_filled = _is_filled(p.get('weather'))
            weather_text_filled = _is_filled(p.get('weather_text'))
            if weather_filled:
                env_filled += 1
                p_env_fields.append({'name': 'Weather', 'value': p.get('weather'), 'status': 'filled'})
            elif weather_text_filled:
                env_filled += 1
                p_env_fields.append({'name': 'Weather', 'value': p.get('weather_text'), 'status': 'filled'})
            else:
                p_env_fields.append({'name': 'Weather', 'value': None, 'status': 'missing'})
            # Sentinel
            if _is_filled(p.get('sentinel'), allow_none_sentinel=True):
                env_filled += 1
                p_env_fields.append({'name': 'Sentinels', 'value': p.get('sentinel'), 'status': 'filled'})
            elif _is_filled(p.get('sentinels_text')):
                env_filled += 1
                p_env_fields.append({'name': 'Sentinels', 'value': p.get('sentinels_text'), 'status': 'filled'})
            else:
                p_env_fields.append({'name': 'Sentinels', 'value': None, 'status': 'missing'})

            env_total_fields = 3
            env_totals.append(min(env_filled / env_total_fields, 1.0))
            planet_env_details.append({'name': p_name, 'filled': env_filled, 'total': env_total_fields, 'fields': p_env_fields})

            # Life scoring: dynamic denominator based on biome
            life_filled = 0
            life_applicable = 0
            biome_val = (p.get('biome') or '').strip()
            is_dead_biome = biome_val in NO_LIFE_BIOMES

            # Fauna
            if _life_descriptor_filled(p.get('fauna'), p.get('fauna_text')):
                life_filled += 1
                life_applicable += 1
                p_life_fields.append({'name': 'Fauna', 'value': p.get('fauna') or p.get('fauna_text'), 'status': 'filled'})
            elif not is_dead_biome:
                life_applicable += 1
                p_life_fields.append({'name': 'Fauna', 'value': None, 'status': 'missing'})
            else:
                p_life_fields.append({'name': 'Fauna', 'value': None, 'status': 'skipped'})

            # Flora
            if _life_descriptor_filled(p.get('flora'), p.get('flora_text')):
                life_filled += 1
                life_applicable += 1
                p_life_fields.append({'name': 'Flora', 'value': p.get('flora') or p.get('flora_text'), 'status': 'filled'})
            elif not is_dead_biome:
                life_applicable += 1
                p_life_fields.append({'name': 'Flora', 'value': None, 'status': 'missing'})
            else:
                p_life_fields.append({'name': 'Flora', 'value': None, 'status': 'skipped'})

            # Resources
            for f in ['common_resource', 'uncommon_resource', 'rare_resource']:
                life_applicable += 1
                if _is_filled(p.get(f)):
                    life_filled += 1
                    p_life_fields.append({'name': FIELD_LABELS[f], 'value': p.get(f), 'status': 'filled'})
                else:
                    p_life_fields.append({'name': FIELD_LABELS[f], 'value': None, 'status': 'missing'})

            life_totals.append(life_filled / max(life_applicable, 1))
            planet_life_details.append({'name': p_name, 'filled': life_filled, 'total': life_applicable, 'fields': p_life_fields})

        planet_env_score = round((sum(env_totals) / len(env_totals)) * 25)
        planet_life_score = round((sum(life_totals) / len(life_totals)) * 15)

    # --- Space Station (5 pts) ---
    # Abandoned/empty systems have no station - give full credit (not applicable)
    station_score = 0
    station_details = []
    if is_abandoned:
        station_score = 5
        station_details.append({'name': 'Station', 'value': 'N/A (Abandoned)', 'status': 'filled'})
        station_details.append({'name': 'Trade Goods', 'value': 'N/A (Abandoned)', 'status': 'filled'})
    elif station:
        station_score += 3
        station_details.append({'name': 'Station', 'value': 'Present', 'status': 'filled'})
        trade_goods = station.get('trade_goods', '[]')
        if trade_goods and trade_goods != '[]':
            station_score += 2
            station_details.append({'name': 'Trade Goods', 'value': 'Recorded', 'status': 'filled'})
        else:
            station_details.append({'name': 'Trade Goods', 'value': None, 'status': 'missing'})
    else:
        station_details.append({'name': 'Station', 'value': None, 'status': 'missing'})
        station_details.append({'name': 'Trade Goods', 'value': None, 'status': 'missing'})

    # Total
    total = sys_core_score + sys_extra_score + planet_coverage_score + planet_env_score + planet_life_score + station_score
    total = min(total, 100)

    # Grade thresholds: S (85-100), A (65-84), B (40-64), C (0-39)
    if total >= 85:
        grade = 'S'
    elif total >= 65:
        grade = 'A'
    elif total >= 40:
        grade = 'B'
    else:
        grade = 'C'

    return {
        'score': total,
        'grade': grade,
        'breakdown': {
            'system_core': sys_core_score,
            'system_extra': sys_extra_score,
            'planet_coverage': planet_coverage_score,
            'planet_environment': planet_env_score,
            'planet_life': planet_life_score,
            'space_station': station_score,
            'planet_count': len(planets),
            'details': {
                'system_core': sys_core_details,
                'system_extra': sys_extra_details,
                'planet_coverage': [{'name': 'Has Planets', 'value': f'{len(planets)} planet(s)' if planets else None, 'status': 'filled' if planets else 'missing'}],
                'planet_environment': planet_env_details,
                'planet_life': planet_life_details,
                'space_station': station_details,
            }
        }
    }


def update_completeness_score(cursor, system_id: str):
    """Calculate and store the completeness score for a system."""
    result = calculate_completeness_score(cursor, system_id)
    cursor.execute('UPDATE systems SET is_complete = ? WHERE id = ?', (result['score'], system_id))
    return result


def _build_advanced_filter_clauses(params_dict, where_clauses, params):
    """Build SQL WHERE clauses for advanced system filters.

    Shared logic between /api/systems, /api/systems/search, and /api/galaxies/summary.
    Modifies where_clauses and params lists in place.

    Args:
        params_dict: Dictionary of filter parameter values
        where_clauses: List of SQL WHERE clause strings (modified in place)
        params: List of query parameter values (modified in place)
    """
    # System-level filters
    if params_dict.get('star_type'):
        where_clauses.append("s.star_type = ?")
        params.append(params_dict['star_type'])
    if params_dict.get('economy_type'):
        where_clauses.append("s.economy_type = ?")
        params.append(params_dict['economy_type'])
    if params_dict.get('economy_level'):
        where_clauses.append("s.economy_level = ?")
        params.append(params_dict['economy_level'])
    if params_dict.get('conflict_level'):
        where_clauses.append("s.conflict_level = ?")
        params.append(params_dict['conflict_level'])
    if params_dict.get('dominant_lifeform'):
        where_clauses.append("s.dominant_lifeform = ?")
        params.append(params_dict['dominant_lifeform'])
    if params_dict.get('stellar_classification'):
        where_clauses.append("s.stellar_classification = ?")
        params.append(params_dict['stellar_classification'])
    # Grade filter: is_complete now stores score 0-100
    # Support both legacy boolean and new grade-based filtering
    is_complete_val = params_dict.get('is_complete')
    if is_complete_val is not None:
        if isinstance(is_complete_val, str) and is_complete_val in ('S', 'A', 'B', 'C'):
            grade_thresholds = {'S': (85, 100), 'A': (65, 84), 'B': (40, 64), 'C': (0, 39)}
            low, high = grade_thresholds[is_complete_val]
            where_clauses.append("s.is_complete BETWEEN ? AND ?")
            params.extend([low, high])
        elif is_complete_val:
            # Legacy: "complete" = score >= 65 (A or S)
            where_clauses.append("s.is_complete >= 65")
        else:
            # Legacy: "incomplete" = score < 65
            where_clauses.append("s.is_complete < 65")

    # Planet-level filters (use EXISTS subquery)
    if params_dict.get('biome'):
        where_clauses.append("EXISTS (SELECT 1 FROM planets p WHERE p.system_id = s.id AND p.biome = ?)")
        params.append(params_dict['biome'])
    if params_dict.get('weather'):
        where_clauses.append("EXISTS (SELECT 1 FROM planets p WHERE p.system_id = s.id AND p.weather = ?)")
        params.append(params_dict['weather'])
    if params_dict.get('sentinel_level'):
        where_clauses.append("EXISTS (SELECT 1 FROM planets p WHERE p.system_id = s.id AND p.sentinel_level = ?)")
        params.append(params_dict['sentinel_level'])
    if params_dict.get('resource'):
        where_clauses.append("""EXISTS (SELECT 1 FROM planets p WHERE p.system_id = s.id
            AND (p.common_resource = ? OR p.uncommon_resource = ? OR p.rare_resource = ?))""")
        res = params_dict['resource']
        params.extend([res, res, res])

    # Has moons filter
    if params_dict.get('has_moons') is not None:
        if params_dict['has_moons']:
            where_clauses.append("EXISTS (SELECT 1 FROM planets p WHERE p.system_id = s.id AND p.is_moon = 1)")
        else:
            where_clauses.append("NOT EXISTS (SELECT 1 FROM planets p WHERE p.system_id = s.id AND p.is_moon = 1)")

    # Planet count filters
    if params_dict.get('min_planets') is not None:
        where_clauses.append("(SELECT COUNT(*) FROM planets p WHERE p.system_id = s.id AND (p.is_moon = 0 OR p.is_moon IS NULL)) >= ?")
        params.append(params_dict['min_planets'])
    if params_dict.get('max_planets') is not None:
        where_clauses.append("(SELECT COUNT(*) FROM planets p WHERE p.system_id = s.id AND (p.is_moon = 0 OR p.is_moon IS NULL)) <= ?")
        params.append(params_dict['max_planets'])


@app.get('/api/systems')
async def api_systems(
    reality: str = None,
    galaxy: str = None,
    region_x: int = None,
    region_y: int = None,
    region_z: int = None,
    page: int = 1,
    limit: int = 50,
    include_planets: bool = False,
    discord_tag: str = None,
    star_type: str = None,
    economy_type: str = None,
    economy_level: str = None,
    conflict_level: str = None,
    dominant_lifeform: str = None,
    stellar_classification: str = None,
    biome: str = None,
    weather: str = None,
    sentinel_level: str = None,
    resource: str = None,
    has_moons: bool = None,
    min_planets: int = None,
    max_planets: int = None,
    is_complete: bool = None,
    session: Optional[str] = Cookie(None)
):
    """Return paginated systems with optional hierarchy filtering.

    This endpoint supports the containerized Systems page by allowing
    filtering at each level of the hierarchy:
    - reality: 'Normal' or 'Permadeath'
    - galaxy: Galaxy name (e.g., 'Euclid')
    - region_x, region_y, region_z: Specific region coordinates

    Args:
        reality: Filter by game mode (Normal/Permadeath)
        galaxy: Filter by galaxy name
        region_x, region_y, region_z: Filter by region coordinates (all three required together)
        page: Page number (1-indexed, default 1)
        limit: Results per page (default 50, max 100)
        include_planets: Whether to include planet data (default false for list view)
        discord_tag: Filter by discord tag ('all', 'untagged', 'personal', or specific tag)
        session: Session cookie for permission checking

    Returns:
        {
            "systems": [...],
            "pagination": {"page": 1, "limit": 50, "total": 100, "pages": 2},
            "filters": {"reality": "Normal", "galaxy": "Euclid", ...}
        }
    """
    session_data = get_session(session)
    limit = min(limit, 100)  # Cap at 100

    conn = None
    try:
        db_path = get_db_path()
        if not db_path.exists():
            return {'systems': [], 'pagination': {'page': 1, 'limit': limit, 'total': 0, 'pages': 0}}

        conn = get_db_connection()
        cursor = conn.cursor()

        # Build filter clauses
        where_clauses = []
        params = []

        if reality:
            where_clauses.append("COALESCE(s.reality, 'Normal') = ?")
            params.append(reality)

        if galaxy:
            where_clauses.append("COALESCE(s.galaxy, 'Euclid') = ?")
            params.append(galaxy)

        # Region filter - all three must be provided together
        if region_x is not None and region_y is not None and region_z is not None:
            where_clauses.append("s.region_x = ? AND s.region_y = ? AND s.region_z = ?")
            params.extend([region_x, region_y, region_z])

        # Discord tag filter
        if discord_tag and discord_tag != 'all':
            if discord_tag == 'untagged':
                where_clauses.append("(s.discord_tag IS NULL OR s.discord_tag = '')")
            elif discord_tag == 'personal':
                where_clauses.append("s.discord_tag = 'personal'")
            else:
                where_clauses.append("s.discord_tag = ?")
                params.append(discord_tag)

        # Advanced filters
        _build_advanced_filter_clauses({
            'star_type': star_type,
            'economy_type': economy_type,
            'economy_level': economy_level,
            'conflict_level': conflict_level,
            'dominant_lifeform': dominant_lifeform,
            'stellar_classification': stellar_classification,
            'biome': biome,
            'weather': weather,
            'sentinel_level': sentinel_level,
            'resource': resource,
            'has_moons': has_moons,
            'min_planets': min_planets,
            'max_planets': max_planets,
            'is_complete': is_complete,
        }, where_clauses, params)

        where_sql = ""
        if where_clauses:
            where_sql = "WHERE " + " AND ".join(where_clauses)

        # Get total count first
        cursor.execute(f'''
            SELECT COUNT(*) FROM systems s {where_sql}
        ''', params)
        total = cursor.fetchone()[0]

        # Calculate pagination
        total_pages = (total + limit - 1) // limit if total > 0 else 0
        offset = (page - 1) * limit

        # Fetch systems with pagination
        cursor.execute(f'''
            SELECT s.*, r.custom_name as region_name
            FROM systems s
            LEFT JOIN regions r ON s.region_x = r.region_x
                AND s.region_y = r.region_y AND s.region_z = r.region_z
            {where_sql}
            ORDER BY s.created_at DESC NULLS LAST, s.id DESC
            LIMIT ? OFFSET ?
        ''', params + [limit, offset])

        systems = [dict(row) for row in cursor.fetchall()]

        # Add completeness grade derived from stored score
        for sys in systems:
            score = sys.get('is_complete', 0) or 0
            if score >= 85:
                sys['completeness_grade'] = 'S'
            elif score >= 65:
                sys['completeness_grade'] = 'A'
            elif score >= 40:
                sys['completeness_grade'] = 'B'
            else:
                sys['completeness_grade'] = 'C'
            sys['completeness_score'] = score

        # Apply data restrictions
        systems = apply_data_restrictions(systems, session_data)

        # Optionally load planets for each system
        if include_planets and systems:
            system_ids = [s['id'] for s in systems]
            placeholders = ','.join(['?'] * len(system_ids))

            # Load planets
            cursor.execute(f'''
                SELECT * FROM planets WHERE system_id IN ({placeholders}) ORDER BY system_id, name
            ''', system_ids)
            all_planets = [dict(row) for row in cursor.fetchall()]

            # Index planets by system_id
            planets_by_system = {}
            for planet in all_planets:
                sys_id = planet['system_id']
                if sys_id not in planets_by_system:
                    planets_by_system[sys_id] = []
                planets_by_system[sys_id].append(planet)

            # Load moons for all planets
            planet_ids = [p['id'] for p in all_planets]
            if planet_ids:
                placeholders = ','.join(['?'] * len(planet_ids))
                cursor.execute(f'''
                    SELECT * FROM moons WHERE planet_id IN ({placeholders}) ORDER BY planet_id, name
                ''', planet_ids)
                all_moons = [dict(row) for row in cursor.fetchall()]

                # Index moons by planet_id
                moons_by_planet = {}
                for moon in all_moons:
                    planet_id = moon['planet_id']
                    if planet_id not in moons_by_planet:
                        moons_by_planet[planet_id] = []
                    moons_by_planet[planet_id].append(moon)

                # Attach moons to planets
                for planet in all_planets:
                    planet['moons'] = moons_by_planet.get(planet['id'], [])
            else:
                for planet in all_planets:
                    planet['moons'] = []

            # Attach planets to systems
            for system in systems:
                system['planets'] = planets_by_system.get(system['id'], [])
        else:
            # No planets in list view
            for system in systems:
                system['planets'] = []

        return {
            'systems': systems,
            'pagination': {
                'page': page,
                'limit': limit,
                'total': total,
                'pages': total_pages
            },
            'filters': {
                'reality': reality,
                'galaxy': galaxy,
                'region_x': region_x,
                'region_y': region_y,
                'region_z': region_z,
                'discord_tag': discord_tag
            }
        }

    except Exception as e:
        logger.error(f"Error fetching systems: {e}")
        return {
            'systems': [],
            'pagination': {'page': 1, 'limit': limit, 'total': 0, 'pages': 0},
            'filters': {}
        }
    finally:
        if conn:
            conn.close()


# NOTE: This route MUST be defined BEFORE /api/systems/{system_id} to avoid route shadowing
@app.get('/api/systems/search')
async def api_search(
    q: str = '',
    limit: int = 20,
    star_type: str = None,
    economy_type: str = None,
    economy_level: str = None,
    conflict_level: str = None,
    dominant_lifeform: str = None,
    stellar_classification: str = None,
    biome: str = None,
    weather: str = None,
    sentinel_level: str = None,
    resource: str = None,
    has_moons: bool = None,
    min_planets: int = None,
    max_planets: int = None,
    is_complete: bool = None,
    session: Optional[str] = Cookie(None)
):
    """Search systems by name, glyph code, galaxy, or description with optional advanced filters.

    Uses efficient SQL LIKE queries and returns results with region info.
    Applies data restrictions based on viewer permissions.

    Args:
        q: Search query (matches system name, glyph_code, galaxy, description)
        limit: Max results to return (default 20, max 50)
        star_type..is_complete: Advanced filter parameters
        session: Session cookie for permission checking

    Returns:
        {
            "results": [...],
            "total": 42,
            "query": "search term"
        }
    """
    session_data = get_session(session)
    q = q.strip()

    if not q:
        return {'results': [], 'total': 0, 'query': ''}

    limit = max(1, min(limit, 50))  # Clamp between 1 and 50

    conn = None
    try:
        db_path = get_db_path()
        if not db_path.exists():
            return {'results': [], 'total': 0, 'query': q}

        conn = get_db_connection()
        cursor = conn.cursor()

        # Search pattern for LIKE queries
        search_pattern = f'%{q}%'

        # Build advanced filter clauses
        adv_where_clauses = []
        adv_params = []
        _build_advanced_filter_clauses({
            'star_type': star_type,
            'economy_type': economy_type,
            'economy_level': economy_level,
            'conflict_level': conflict_level,
            'dominant_lifeform': dominant_lifeform,
            'stellar_classification': stellar_classification,
            'biome': biome,
            'weather': weather,
            'sentinel_level': sentinel_level,
            'resource': resource,
            'has_moons': has_moons,
            'min_planets': min_planets,
            'max_planets': max_planets,
            'is_complete': is_complete,
        }, adv_where_clauses, adv_params)

        adv_sql = ""
        if adv_where_clauses:
            adv_sql = " AND " + " AND ".join(adv_where_clauses)

        # Efficient SQL search across multiple fields
        # Fetch more than limit to account for filtering by data restrictions
        # Include x, y, z for map display positioning
        cursor.execute(f'''
            SELECT s.id, s.name, s.region_x, s.region_y, s.region_z,
                   s.x, s.y, s.z,
                   s.galaxy, s.glyph_code, s.discord_tag, s.star_type,
                   s.reality, s.is_complete,
                   r.custom_name as region_name,
                   (SELECT COUNT(*) FROM planets WHERE system_id = s.id) as planet_count
            FROM systems s
            LEFT JOIN regions r ON s.region_x = r.region_x
                AND s.region_y = r.region_y AND s.region_z = r.region_z
            WHERE (s.name LIKE ? COLLATE NOCASE
               OR s.glyph_code LIKE ? COLLATE NOCASE
               OR s.galaxy LIKE ? COLLATE NOCASE
               OR s.description LIKE ? COLLATE NOCASE)
            {adv_sql}
            ORDER BY
                CASE WHEN LOWER(s.name) = LOWER(?) THEN 0
                     WHEN LOWER(s.name) LIKE LOWER(?) THEN 1
                     ELSE 2
                END,
                s.name ASC
            LIMIT ?
        ''', (search_pattern, search_pattern, search_pattern, search_pattern,
              *adv_params, q, f'{q}%', limit * 2))

        rows = cursor.fetchall()
        systems = [dict(row) for row in rows]

        # Add completeness grade
        for sys in systems:
            score = sys.get('is_complete', 0) or 0
            if score >= 85:
                sys['completeness_grade'] = 'S'
            elif score >= 65:
                sys['completeness_grade'] = 'A'
            elif score >= 40:
                sys['completeness_grade'] = 'B'
            else:
                sys['completeness_grade'] = 'C'
            sys['completeness_score'] = score

        # Apply data restrictions
        systems = apply_data_restrictions(systems, session_data)

        # Limit to requested amount
        results = systems[:limit]

        return {
            'results': results,
            'total': len(results),
            'query': q
        }

    except Exception as e:
        logger.error(f"Error searching systems: {e}")
        return {'results': [], 'total': 0, 'query': q, 'error': str(e)}
    finally:
        if conn:
            conn.close()


@app.get('/api/systems_by_region')
async def api_systems_by_region(rx: int = 0, ry: int = 0, rz: int = 0,
                                 reality: str = None,
                                 galaxy: str = None,
                                 for_map: bool = False,
                                 session: Optional[str] = Cookie(None)):
    """Return all systems within a specific region.

    Args:
        rx: Region X coordinate (0-4095, centered at 2048)
        ry: Region Y coordinate (0-255, centered at 128)
        rz: Region Z coordinate (0-4095, centered at 2048)
        reality: Optional filter - 'Normal' or 'Permadeath' (None for all)
        galaxy: Optional filter - galaxy name like 'Euclid' (None for all)
        for_map: If True, applies map visibility restrictions
        session: Session cookie for permission checking

    Returns:
        Dictionary with systems list and region info
    """
    session_data = get_session(session)

    conn = None
    try:
        db_path = get_db_path()
        if db_path.exists():
            conn = get_db_connection()
            cursor = conn.cursor()

            # Build WHERE clause with optional filters
            where_clauses = ["s.region_x = ?", "s.region_y = ?", "s.region_z = ?"]
            params = [rx, ry, rz]

            if reality:
                where_clauses.append("s.reality = ?")
                params.append(reality)
            if galaxy:
                where_clauses.append("s.galaxy = ?")
                params.append(galaxy)

            where_sql = " AND ".join(where_clauses)

            # Query systems by region coordinates with optional filters
            cursor.execute(f'''
                SELECT s.*,
                    (SELECT COUNT(*) FROM planets WHERE system_id = s.id) as planet_count
                FROM systems s
                WHERE {where_sql}
                ORDER BY s.name
            ''', params)

            rows = cursor.fetchall()
            systems = []

            for row in rows:
                system = dict(row)
                sys_id = system.get('id')

                # Get planets for this system
                cursor.execute('SELECT * FROM planets WHERE system_id = ?', (sys_id,))
                planets_rows = cursor.fetchall()
                system['planets'] = [dict(p) for p in planets_rows]

                systems.append(system)

            # Apply data restrictions
            systems = apply_data_restrictions(systems, session_data, for_map=for_map)

            return {
                'region': {'x': rx, 'y': ry, 'z': rz},
                'system_count': len(systems),
                'systems': systems
            }

        # Fallback to cache if no DB
        async with _systems_lock:
            all_systems = list(_systems_cache.values())

        # Filter by region
        systems = [
            s for s in all_systems
            if s.get('region_x') == rx and s.get('region_y') == ry and s.get('region_z') == rz
        ]

        # Apply data restrictions
        systems = apply_data_restrictions(systems, session_data, for_map=for_map)

        return {
            'region': {'x': rx, 'y': ry, 'z': rz},
            'system_count': len(systems),
            'systems': systems
        }

    except Exception as e:
        logger.error(f"Error fetching systems by region: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()


@app.get('/api/regions/grouped')
async def api_regions_grouped(include_systems: bool = True, page: int = 0, limit: int = 0,
                               discord_tag: str = None,
                               reality: str = None,
                               galaxy: str = None,
                               session: Optional[str] = Cookie(None)):
    """Return all regions with their systems grouped together.

    Performance-optimized version:
    - Uses JOINs instead of N+1 queries
    - Optional pagination with page/limit params
    - include_systems=false returns just region summaries (much faster)
    - Applies data restrictions based on viewer permissions
    - discord_tag filter: 'all' or None for all, 'untagged' for NULL tags,
      'personal' for personal tag, or specific tag name
    - reality filter: 'Normal' or 'Permadeath' to filter by game mode
    - galaxy filter: Galaxy name (e.g., 'Euclid') to filter by galaxy

    Returns regions ordered by:
    1. "Sea of Gidzenuf" (home system) always first
    2. Named regions sorted by system count descending
    3. Unnamed regions sorted by system count descending
    """
    session_data = get_session(session)

    conn = None
    try:
        db_path = get_db_path()
        if not db_path.exists():
            return {'regions': [], 'total_regions': 0}

        conn = get_db_connection()
        cursor = conn.cursor()

        # Build filter clauses
        filter_clauses = []
        filter_params = []

        # Discord tag filter
        if discord_tag and discord_tag != 'all':
            if discord_tag == 'untagged':
                filter_clauses.append("(s.discord_tag IS NULL OR s.discord_tag = '')")
            elif discord_tag == 'personal':
                filter_clauses.append("s.discord_tag = 'personal'")
            else:
                filter_clauses.append("s.discord_tag = ?")
                filter_params.append(discord_tag)

        # Reality filter (Level 1 hierarchy)
        if reality:
            filter_clauses.append("COALESCE(s.reality, 'Normal') = ?")
            filter_params.append(reality)

        # Galaxy filter (Level 2 hierarchy)
        if galaxy:
            filter_clauses.append("COALESCE(s.galaxy, 'Euclid') = ?")
            filter_params.append(galaxy)

        # Combine filters
        combined_filter = ""
        if filter_clauses:
            combined_filter = " AND " + " AND ".join(filter_clauses)

        # STEP 1: Get all regions with aggregated counts in a SINGLE query
        # This replaces the N+1 pattern with one efficient GROUP BY query
        cursor.execute(f'''
            SELECT
                s.region_x, s.region_y, s.region_z,
                r.custom_name,
                r.id as region_id,
                MIN(s.created_at) as first_system_date,
                MIN(s.id) as first_system_id,
                COUNT(DISTINCT s.id) as system_count
            FROM systems s
            LEFT JOIN regions r ON s.region_x = r.region_x
                AND s.region_y = r.region_y AND s.region_z = r.region_z
            WHERE s.region_x IS NOT NULL AND s.region_y IS NOT NULL AND s.region_z IS NOT NULL
                {combined_filter}
            GROUP BY s.region_x, s.region_y, s.region_z
            ORDER BY
                CASE
                    WHEN r.custom_name = 'Sea of Gidzenuf' THEN 0
                    WHEN r.custom_name IS NOT NULL THEN 1
                    ELSE 2
                END ASC,
                COUNT(DISTINCT s.id) DESC,
                first_system_date ASC NULLS FIRST,
                first_system_id ASC
        ''', filter_params)

        region_rows = cursor.fetchall()
        all_region_rows = list(region_rows)  # Keep full list before any pagination

        regions = []

        if not include_systems:
            # Fast path: return just region summaries without nested data
            # BUT we need accurate counts, so fetch minimal system data for restriction checks
            # Use ALL region_rows (before pagination) to get accurate visible counts
            all_region_coords = [(r['region_x'], r['region_y'], r['region_z']) for r in all_region_rows]
            visible_counts = {}  # Initialize before conditional to avoid NameError

            if all_region_coords:
                # Build WHERE clause for all regions (not just paginated ones)
                placeholders = ' OR '.join(['(region_x = ? AND region_y = ? AND region_z = ?)'] * len(all_region_coords))
                params = [coord for region in all_region_coords for coord in region]
                # Add hierarchy filter params if present
                params.extend(filter_params)

                cursor.execute(f'''
                    SELECT id, discord_tag, region_x, region_y, region_z FROM systems s
                    WHERE ({placeholders}) {combined_filter}
                ''', params)

                all_systems = [dict(row) for row in cursor.fetchall()]

                # Apply data restrictions to get accurate visible systems
                visible_systems = apply_data_restrictions(all_systems, session_data)

                # Count visible systems per region
                # Note: systems with 'coordinates' restriction may have region fields stripped
                for system in visible_systems:
                    rx = system.get('region_x')
                    ry = system.get('region_y')
                    rz = system.get('region_z')
                    if rx is not None and ry is not None and rz is not None:
                        key = (rx, ry, rz)
                        visible_counts[key] = visible_counts.get(key, 0) + 1

            # Calculate the TRUE total of regions with visible systems BEFORE pagination
            true_total_regions = sum(1 for r in all_region_rows if visible_counts.get((r['region_x'], r['region_y'], r['region_z']), 0) > 0)

            # Now apply pagination to all_region_rows
            if limit > 0:
                offset = page * limit
                # Filter all_region_rows to only include those with visible systems, THEN paginate
                visible_region_rows = [r for r in all_region_rows if visible_counts.get((r['region_x'], r['region_y'], r['region_z']), 0) > 0]
                region_rows_paginated = visible_region_rows[offset:offset + limit]
            else:
                region_rows_paginated = [r for r in all_region_rows if visible_counts.get((r['region_x'], r['region_y'], r['region_z']), 0) > 0]

            for region_row in region_rows_paginated:
                region = dict(region_row)
                rx, ry, rz = region['region_x'], region['region_y'], region['region_z']

                if region['custom_name']:
                    region['display_name'] = region['custom_name']
                else:
                    region['display_name'] = f"Region ({rx}, {ry}, {rz})"

                # Use accurate visible count (visible_counts is always defined now)
                region['system_count'] = visible_counts.get((rx, ry, rz), 0)
                region['systems'] = []  # Empty for now, lazy-load via separate endpoint
                regions.append(region)

            return {
                'regions': regions,
                'total_regions': true_total_regions,
                'applied_filter': discord_tag or 'all',
                'reality': reality,
                'galaxy': galaxy
            }

        # STEP 2: Load all systems for all regions in ONE query (include_systems=True path)
        # Apply pagination for include_systems=True case
        total_regions = len(all_region_rows)
        if limit > 0:
            offset = page * limit
            paginated_region_rows = all_region_rows[offset:offset + limit]
        else:
            paginated_region_rows = all_region_rows

        region_coords = [(r['region_x'], r['region_y'], r['region_z']) for r in paginated_region_rows]
        if not region_coords:
            return {'regions': [], 'total_regions': 0}

        # Build WHERE clause for all regions
        placeholders = ' OR '.join(['(region_x = ? AND region_y = ? AND region_z = ?)'] * len(region_coords))
        params = [coord for region in region_coords for coord in region]
        # Add hierarchy filter params if present
        params.extend(filter_params)

        cursor.execute(f'''
            SELECT * FROM systems s
            WHERE ({placeholders}) {combined_filter}
            ORDER BY s.region_x, s.region_y, s.region_z, s.created_at ASC NULLS FIRST, s.id ASC
        ''', params)

        all_systems = [dict(row) for row in cursor.fetchall()]

        # Index systems by region
        systems_by_region = {}
        for system in all_systems:
            key = (system['region_x'], system['region_y'], system['region_z'])
            if key not in systems_by_region:
                systems_by_region[key] = []
            systems_by_region[key].append(system)

        # STEP 3: Load all planets for all systems in ONE query
        system_ids = [s['id'] for s in all_systems]
        if system_ids:
            placeholders = ','.join(['?'] * len(system_ids))
            cursor.execute(f'''
                SELECT * FROM planets WHERE system_id IN ({placeholders}) ORDER BY system_id, name
            ''', system_ids)
            all_planets = [dict(row) for row in cursor.fetchall()]

            # Index planets by system_id
            planets_by_system = {}
            for planet in all_planets:
                sys_id = planet['system_id']
                if sys_id not in planets_by_system:
                    planets_by_system[sys_id] = []
                planets_by_system[sys_id].append(planet)

            # STEP 4: Load all moons for all planets in ONE query
            planet_ids = [p['id'] for p in all_planets]
            if planet_ids:
                placeholders = ','.join(['?'] * len(planet_ids))
                cursor.execute(f'''
                    SELECT * FROM moons WHERE planet_id IN ({placeholders}) ORDER BY planet_id, name
                ''', planet_ids)
                all_moons = [dict(row) for row in cursor.fetchall()]

                # Index moons by planet_id
                moons_by_planet = {}
                for moon in all_moons:
                    planet_id = moon['planet_id']
                    if planet_id not in moons_by_planet:
                        moons_by_planet[planet_id] = []
                    moons_by_planet[planet_id].append(moon)

                # Attach moons to planets
                for planet in all_planets:
                    planet['moons'] = moons_by_planet.get(planet['id'], [])
            else:
                for planet in all_planets:
                    planet['moons'] = []

            # Attach planets to systems
            for system in all_systems:
                system['planets'] = planets_by_system.get(system['id'], [])
        else:
            planets_by_system = {}

        # STEP 5: Load all discoveries for all systems in ONE query
        if system_ids:
            placeholders = ','.join(['?'] * len(system_ids))
            cursor.execute(f'''
                SELECT * FROM discoveries WHERE system_id IN ({placeholders}) ORDER BY system_id, discovery_name
            ''', system_ids)
            all_discoveries = [dict(row) for row in cursor.fetchall()]

            # Index discoveries by system_id
            discoveries_by_system = {}
            for discovery in all_discoveries:
                sys_id = discovery['system_id']
                if sys_id not in discoveries_by_system:
                    discoveries_by_system[sys_id] = []
                discoveries_by_system[sys_id].append(discovery)

            # Attach discoveries to systems
            for system in all_systems:
                system['discoveries'] = discoveries_by_system.get(system['id'], [])
        else:
            for system in all_systems:
                system['discoveries'] = []

        # STEP 6: Build final region objects with data restrictions applied
        for region_row in paginated_region_rows:
            region = dict(region_row)
            rx, ry, rz = region['region_x'], region['region_y'], region['region_z']

            # Get systems for this region and apply data restrictions
            region_systems = systems_by_region.get((rx, ry, rz), [])
            region_systems = apply_data_restrictions(region_systems, session_data)

            region['systems'] = region_systems
            region['system_count'] = len(region_systems)  # Recalculate after filtering

            if region['custom_name']:
                region['display_name'] = region['custom_name']
            else:
                region['display_name'] = f"Region ({rx}, {ry}, {rz})"

            regions.append(region)

        return {
            'regions': regions,
            'total_regions': total_regions,
            'applied_filter': discord_tag or 'all',
            'reality': reality,
            'galaxy': galaxy
        }

    except Exception as e:
        import traceback
        logger.error(f"Error fetching grouped regions: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()


# ========== REGION NAME MANAGEMENT ENDPOINTS ==========

@app.get('/api/regions')
async def api_list_regions():
    """List all regions with custom names."""
    conn = None
    try:
        db_path = get_db_path()
        if not db_path.exists():
            return {'regions': []}

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT r.*,
                (SELECT COUNT(*) FROM systems s
                 WHERE s.region_x = r.region_x AND s.region_y = r.region_y AND s.region_z = r.region_z) as system_count
            FROM regions r
            ORDER BY r.custom_name
        ''')

        rows = cursor.fetchall()
        regions = [dict(row) for row in rows]

        return {'regions': regions}
    except Exception as e:
        logger.error(f"Error listing regions: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()


@app.get('/api/regions/{rx}/{ry}/{rz}')
async def api_get_region(rx: int, ry: int, rz: int, session: Optional[str] = Cookie(None)):
    """Get region info including custom name if set and any pending submissions.
    System count respects data restrictions (hidden systems are not counted for public).
    """
    session_data = get_session(session)

    conn = None
    try:
        db_path = get_db_path()
        if not db_path.exists():
            return {
                'region_x': rx,
                'region_y': ry,
                'region_z': rz,
                'custom_name': None,
                'system_count': 0,
                'pending_name': None
            }

        conn = get_db_connection()
        cursor = conn.cursor()

        # Get custom name if exists
        cursor.execute('''
            SELECT custom_name FROM regions
            WHERE region_x = ? AND region_y = ? AND region_z = ?
        ''', (rx, ry, rz))
        row = cursor.fetchone()
        custom_name = row['custom_name'] if row else None

        # Get systems in this region and apply data restrictions for accurate count
        cursor.execute('''
            SELECT id, discord_tag FROM systems
            WHERE region_x = ? AND region_y = ? AND region_z = ?
        ''', (rx, ry, rz))
        systems = [dict(row) for row in cursor.fetchall()]

        # Apply data restrictions to get accurate visible count
        visible_systems = apply_data_restrictions(systems, session_data)
        system_count = len(visible_systems)

        # Check for pending name submission
        cursor.execute('''
            SELECT proposed_name, submitted_by, submission_date FROM pending_region_names
            WHERE region_x = ? AND region_y = ? AND region_z = ? AND status = 'pending'
            ORDER BY submission_date DESC LIMIT 1
        ''', (rx, ry, rz))
        pending_row = cursor.fetchone()
        pending_name = dict(pending_row) if pending_row else None

        return {
            'region_x': rx,
            'region_y': ry,
            'region_z': rz,
            'custom_name': custom_name,
            'system_count': system_count,
            'pending_name': pending_name
        }
    except Exception as e:
        logger.error(f"Error getting region: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()


@app.get('/api/regions/{rx}/{ry}/{rz}/systems')
async def api_region_systems(rx: int, ry: int, rz: int, page: int = 1, limit: int = 50,
                              include_planets: bool = False, session: Optional[str] = Cookie(None)):
    """Get paginated systems for a specific region (lazy-loading endpoint).

    Args:
        rx, ry, rz: Region coordinates
        page: Page number (1-indexed)
        limit: Systems per page (default 50, max 200)
        include_planets: If true, include planets and moons (slower)
        session: Session cookie for permission checking

    Returns systems ordered by created_at, with optional pagination.
    Applies data restrictions based on viewer permissions.
    """
    session_data = get_session(session)

    conn = None
    try:
        db_path = get_db_path()
        if not db_path.exists():
            return {'systems': [], 'total': 0, 'page': page, 'limit': limit}

        # Cap limit to prevent huge responses (500 max for region views)
        # Use limit=0 to mean "no limit" (still capped at 500)
        if limit == 0:
            limit = 500
        else:
            limit = min(limit, 500)

        conn = get_db_connection()
        cursor = conn.cursor()

        # Get ALL systems for this region first (we need to filter before pagination)
        cursor.execute('''
            SELECT * FROM systems
            WHERE region_x = ? AND region_y = ? AND region_z = ?
            ORDER BY created_at ASC NULLS FIRST, id ASC
        ''', (rx, ry, rz))

        all_systems = [dict(row) for row in cursor.fetchall()]

        # Apply data restrictions BEFORE pagination
        all_systems = apply_data_restrictions(all_systems, session_data)

        # Now paginate the filtered results
        total = len(all_systems)
        offset = (page - 1) * limit
        systems = all_systems[offset:offset + limit]

        if include_planets and systems:
            # Batch load planets for all systems
            system_ids = [s['id'] for s in systems]
            placeholders = ','.join(['?'] * len(system_ids))

            cursor.execute(f'''
                SELECT * FROM planets WHERE system_id IN ({placeholders}) ORDER BY system_id, name
            ''', system_ids)
            all_planets = [dict(row) for row in cursor.fetchall()]

            # Index planets by system_id
            planets_by_system = {}
            for planet in all_planets:
                sys_id = planet['system_id']
                if sys_id not in planets_by_system:
                    planets_by_system[sys_id] = []
                planets_by_system[sys_id].append(planet)

            # Load moons for all planets
            planet_ids = [p['id'] for p in all_planets]
            if planet_ids:
                placeholders = ','.join(['?'] * len(planet_ids))
                cursor.execute(f'''
                    SELECT * FROM moons WHERE planet_id IN ({placeholders}) ORDER BY planet_id, name
                ''', planet_ids)
                all_moons = [dict(row) for row in cursor.fetchall()]

                # Index moons by planet_id
                moons_by_planet = {}
                for moon in all_moons:
                    planet_id = moon['planet_id']
                    if planet_id not in moons_by_planet:
                        moons_by_planet[planet_id] = []
                    moons_by_planet[planet_id].append(moon)

                # Attach moons to planets
                for planet in all_planets:
                    planet['moons'] = moons_by_planet.get(planet['id'], [])
            else:
                for planet in all_planets:
                    planet['moons'] = []

            # Attach planets to systems
            for system in systems:
                system['planets'] = planets_by_system.get(system['id'], [])
        else:
            for system in systems:
                system['planets'] = []

        return {
            'systems': systems,
            'total': total,
            'page': page,
            'limit': limit,
            'total_pages': (total + limit - 1) // limit if limit > 0 else 1
        }

    except Exception as e:
        logger.error(f"Error fetching region systems: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()


@app.get('/api/systems/{system_id}/planets')
async def api_system_planets(system_id: str, session: Optional[str] = Cookie(None)):
    """Get all planets and moons for a specific system (lazy-loading endpoint).

    Returns planets with their moons nested, using efficient batch queries.
    Applies data restrictions based on viewer permissions.
    """
    session_data = get_session(session)

    conn = None
    try:
        db_path = get_db_path()
        if not db_path.exists():
            return {'planets': [], 'system_id': system_id}

        conn = get_db_connection()
        cursor = conn.cursor()

        # Get the system to check restrictions
        cursor.execute('SELECT id, discord_tag FROM systems WHERE id = ?', (system_id,))
        system_row = cursor.fetchone()
        if not system_row:
            return {'planets': [], 'system_id': system_id}

        sys_id = system_row['id']
        system_discord_tag = system_row['discord_tag']

        # Check if viewer can bypass restrictions
        can_bypass = can_bypass_restriction(session_data, system_discord_tag)

        # Check for restrictions
        restriction = get_restriction_for_system(sys_id) if not can_bypass else None

        # If system is hidden, return empty (shouldn't happen if they got here, but safety check)
        if restriction and restriction.get('is_hidden_from_public'):
            return {'planets': [], 'system_id': system_id}

        # If planets are restricted, return empty or count only
        if restriction and 'planets' in restriction.get('hidden_fields', []):
            # Get count only
            cursor.execute('SELECT COUNT(*) as count FROM planets WHERE system_id = ?', (system_id,))
            count = cursor.fetchone()['count']
            return {'planets': [], 'system_id': system_id, 'planet_count_only': count}

        # Get all planets for this system
        cursor.execute('''
            SELECT * FROM planets WHERE system_id = ? ORDER BY name
        ''', (system_id,))
        planets = [dict(row) for row in cursor.fetchall()]

        if planets:
            # Batch load moons for all planets
            planet_ids = [p['id'] for p in planets]
            placeholders = ','.join(['?'] * len(planet_ids))

            cursor.execute(f'''
                SELECT * FROM moons WHERE planet_id IN ({placeholders}) ORDER BY planet_id, name
            ''', planet_ids)
            all_moons = [dict(row) for row in cursor.fetchall()]

            # Index moons by planet_id
            moons_by_planet = {}
            for moon in all_moons:
                planet_id = moon['planet_id']
                if planet_id not in moons_by_planet:
                    moons_by_planet[planet_id] = []
                moons_by_planet[planet_id].append(moon)

            # Attach moons to planets
            for planet in planets:
                planet['moons'] = moons_by_planet.get(planet['id'], [])

            # Apply base_location restriction if needed
            if restriction and 'base_location' in restriction.get('hidden_fields', []):
                for planet in planets:
                    if 'base_location' in planet:
                        del planet['base_location']
        else:
            for planet in planets:
                planet['moons'] = []

        return {'planets': planets, 'system_id': system_id}

    except Exception as e:
        logger.error(f"Error fetching system planets: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()


# =============================================================================
# Planet Atlas Integration - POI (Points of Interest) Endpoints
# =============================================================================

@app.get('/api/planets/{planet_id}/pois')
async def api_get_planet_pois(planet_id: int, session: Optional[str] = Cookie(None)):
    """Get all POIs for a specific planet."""
    conn = None
    try:
        db_path = get_db_path()
        if not db_path.exists():
            return {'pois': [], 'planet_id': planet_id}

        conn = get_db_connection()
        cursor = conn.cursor()

        # Get planet info first
        cursor.execute('SELECT id, name, system_id FROM planets WHERE id = ?', (planet_id,))
        planet = cursor.fetchone()
        if not planet:
            raise HTTPException(status_code=404, detail='Planet not found')

        # Get system info for context
        cursor.execute('SELECT name FROM systems WHERE id = ?', (planet['system_id'],))
        system = cursor.fetchone()

        # Get all POIs for this planet
        cursor.execute('''
            SELECT * FROM planet_pois WHERE planet_id = ? ORDER BY created_at DESC
        ''', (planet_id,))
        pois = [dict(row) for row in cursor.fetchall()]

        return {
            'pois': pois,
            'planet_id': planet_id,
            'planet_name': planet['name'],
            'system_name': system['name'] if system else 'Unknown'
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching planet POIs: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()


@app.post('/api/planets/{planet_id}/pois')
async def api_create_planet_poi(planet_id: int, payload: dict, session: Optional[str] = Cookie(None)):
    """Create a new POI on a planet."""
    # Validate required fields
    name = payload.get('name', '').strip()
    latitude = payload.get('latitude')
    longitude = payload.get('longitude')

    if not name:
        raise HTTPException(status_code=400, detail='POI name is required')
    if latitude is None or longitude is None:
        raise HTTPException(status_code=400, detail='Latitude and longitude are required')

    # Validate coordinate ranges
    try:
        latitude = float(latitude)
        longitude = float(longitude)
        if latitude < -90 or latitude > 90:
            raise HTTPException(status_code=400, detail='Latitude must be between -90 and 90')
        # Normalize longitude to -180 to 180
        longitude = ((longitude + 180) % 360) - 180
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail='Invalid latitude or longitude values')

    conn = None
    try:
        db_path = get_db_path()
        if not db_path.exists():
            raise HTTPException(status_code=500, detail='Database not initialized')

        conn = get_db_connection()
        cursor = conn.cursor()

        # Verify planet exists
        cursor.execute('SELECT id FROM planets WHERE id = ?', (planet_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail='Planet not found')

        # Get session data for created_by
        session_data = get_session(session)
        created_by = session_data.get('username') if session_data else 'anonymous'

        # Insert the POI
        cursor.execute('''
            INSERT INTO planet_pois (planet_id, name, description, latitude, longitude,
                                     poi_type, color, symbol, category, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            planet_id,
            name,
            payload.get('description', ''),
            latitude,
            longitude,
            payload.get('poi_type', 'custom'),
            payload.get('color', '#00C2B3'),
            payload.get('symbol', 'circle'),
            payload.get('category', '-'),
            created_by
        ))

        poi_id = cursor.lastrowid
        conn.commit()

        # Return the created POI
        cursor.execute('SELECT * FROM planet_pois WHERE id = ?', (poi_id,))
        poi = dict(cursor.fetchone())

        logger.info(f"Created POI '{name}' on planet {planet_id} by {created_by}")
        return {'success': True, 'poi': poi}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating planet POI: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()


@app.put('/api/planets/pois/{poi_id}')
async def api_update_planet_poi(poi_id: int, payload: dict, session: Optional[str] = Cookie(None)):
    """Update an existing POI."""
    conn = None
    try:
        db_path = get_db_path()
        if not db_path.exists():
            raise HTTPException(status_code=500, detail='Database not initialized')

        conn = get_db_connection()
        cursor = conn.cursor()

        # Check if POI exists
        cursor.execute('SELECT * FROM planet_pois WHERE id = ?', (poi_id,))
        existing = cursor.fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail='POI not found')

        # Build update query dynamically
        updates = []
        values = []

        if 'name' in payload:
            updates.append('name = ?')
            values.append(payload['name'].strip())
        if 'description' in payload:
            updates.append('description = ?')
            values.append(payload['description'])
        if 'latitude' in payload:
            lat = float(payload['latitude'])
            if lat < -90 or lat > 90:
                raise HTTPException(status_code=400, detail='Latitude must be between -90 and 90')
            updates.append('latitude = ?')
            values.append(lat)
        if 'longitude' in payload:
            lon = float(payload['longitude'])
            lon = ((lon + 180) % 360) - 180  # Normalize
            updates.append('longitude = ?')
            values.append(lon)
        if 'poi_type' in payload:
            updates.append('poi_type = ?')
            values.append(payload['poi_type'])
        if 'color' in payload:
            updates.append('color = ?')
            values.append(payload['color'])
        if 'symbol' in payload:
            updates.append('symbol = ?')
            values.append(payload['symbol'])
        if 'category' in payload:
            updates.append('category = ?')
            values.append(payload['category'])

        if not updates:
            raise HTTPException(status_code=400, detail='No fields to update')

        updates.append('updated_at = CURRENT_TIMESTAMP')
        values.append(poi_id)

        cursor.execute(f'''
            UPDATE planet_pois SET {', '.join(updates)} WHERE id = ?
        ''', values)

        conn.commit()

        # Return updated POI
        cursor.execute('SELECT * FROM planet_pois WHERE id = ?', (poi_id,))
        poi = dict(cursor.fetchone())

        logger.info(f"Updated POI {poi_id}")
        return {'success': True, 'poi': poi}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating planet POI: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()


@app.delete('/api/planets/pois/{poi_id}')
async def api_delete_planet_poi(poi_id: int, session: Optional[str] = Cookie(None)):
    """Delete a POI."""
    conn = None
    try:
        db_path = get_db_path()
        if not db_path.exists():
            raise HTTPException(status_code=500, detail='Database not initialized')

        conn = get_db_connection()
        cursor = conn.cursor()

        # Check if POI exists
        cursor.execute('SELECT name FROM planet_pois WHERE id = ?', (poi_id,))
        existing = cursor.fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail='POI not found')

        # Delete the POI
        cursor.execute('DELETE FROM planet_pois WHERE id = ?', (poi_id,))
        conn.commit()

        logger.info(f"Deleted POI {poi_id} ({existing['name']})")
        return {'success': True, 'deleted_id': poi_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting planet POI: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()


@app.get('/map/planet/{planet_id}')
async def get_planet_3d_map(planet_id: int, session: Optional[str] = Cookie(None)):
    """Serve the Planet Atlas 3D visualization for a specific planet.

    Generates an interactive 3D globe with POI markers using the planet_atlas_wrapper.
    """
    conn = None
    try:
        db_path = get_db_path()
        if not db_path.exists():
            raise HTTPException(status_code=500, detail='Database not initialized')

        conn = get_db_connection()
        cursor = conn.cursor()

        # Get planet info
        cursor.execute('''
            SELECT p.*, s.name as system_name, s.glyph_code
            FROM planets p
            JOIN systems s ON p.system_id = s.id
            WHERE p.id = ?
        ''', (planet_id,))
        planet_row = cursor.fetchone()

        if not planet_row:
            raise HTTPException(status_code=404, detail='Planet not found')

        # Convert to dict for easier access
        planet = dict(planet_row)

        # Get POIs for this planet
        cursor.execute('''
            SELECT * FROM planet_pois WHERE planet_id = ? ORDER BY created_at DESC
        ''', (planet_id,))
        pois = [dict(row) for row in cursor.fetchall()]

        # Generate the HTML visualization
        html_content = generate_planet_html(
            planet_name=planet['name'],
            planet_id=planet_id,
            system_name=planet['system_name'],
            pois=pois,
            biome=planet.get('biome'),
            glyph_code=planet.get('glyph_code')
        )

        return HTMLResponse(content=html_content)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating planet 3D map: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()


@app.put('/api/regions/{rx}/{ry}/{rz}')
async def api_update_region(rx: int, ry: int, rz: int, payload: dict, session: Optional[str] = Cookie(None)):
    """Update/set custom region name. Admin only."""
    # Check admin authentication
    if not verify_session(session):
        raise HTTPException(status_code=401, detail='Admin authentication required')

    custom_name = payload.get('custom_name', '').strip()
    if not custom_name:
        raise HTTPException(status_code=400, detail='Custom name is required')

    conn = None
    try:
        db_path = get_db_path()
        if not db_path.exists():
            raise HTTPException(status_code=500, detail='Database not initialized')

        conn = get_db_connection()
        cursor = conn.cursor()

        # Check if name already exists for a different region
        cursor.execute('''
            SELECT region_x, region_y, region_z FROM regions
            WHERE custom_name = ? AND NOT (region_x = ? AND region_y = ? AND region_z = ?)
        ''', (custom_name, rx, ry, rz))
        existing = cursor.fetchone()
        if existing:
            raise HTTPException(
                status_code=409,
                detail=f'Region name "{custom_name}" is already used by region [{existing["region_x"]}, {existing["region_y"]}, {existing["region_z"]}]'
            )

        # Insert or update the region name
        cursor.execute('''
            INSERT INTO regions (region_x, region_y, region_z, custom_name, updated_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(region_x, region_y, region_z)
            DO UPDATE SET custom_name = excluded.custom_name, updated_at = CURRENT_TIMESTAMP
        ''', (rx, ry, rz, custom_name))

        conn.commit()

        return {
            'status': 'ok',
            'region_x': rx,
            'region_y': ry,
            'region_z': rz,
            'custom_name': custom_name
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating region: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()


@app.delete('/api/regions/{rx}/{ry}/{rz}/name')
async def api_delete_region_name(rx: int, ry: int, rz: int, session: Optional[str] = Cookie(None)):
    """Remove custom region name. Admin only."""
    # Check admin authentication
    if not verify_session(session):
        raise HTTPException(status_code=401, detail='Admin authentication required')

    conn = None
    try:
        db_path = get_db_path()
        if not db_path.exists():
            return {'status': 'ok', 'message': 'No region name to delete'}

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('''
            DELETE FROM regions
            WHERE region_x = ? AND region_y = ? AND region_z = ?
        ''', (rx, ry, rz))

        conn.commit()

        return {
            'status': 'ok',
            'region_x': rx,
            'region_y': ry,
            'region_z': rz,
            'message': 'Region name removed'
        }
    except Exception as e:
        logger.error(f"Error deleting region name: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()


@app.post('/api/regions/{rx}/{ry}/{rz}/submit')
async def api_submit_region_name(rx: int, ry: int, rz: int, payload: dict, request: Request):
    """Submit a proposed region name for approval. Any user can submit."""
    from datetime import datetime, timezone

    # Debug logging for region name submissions
    client_ip = request.client.host if request.client else 'unknown'
    logger.info(f"Region name submission from {client_ip}: region=[{rx},{ry},{rz}], payload={payload}")

    proposed_name = payload.get('proposed_name', '').strip()
    submitted_by = payload.get('submitted_by', 'anonymous').strip() or 'anonymous'
    discord_tag = payload.get('discord_tag')  # Community tag for routing
    personal_discord_username = payload.get('personal_discord_username', '').strip() or None  # Discord username for contact

    if not proposed_name:
        logger.warning(f"Region name submission rejected - empty proposed_name. Full payload: {payload}")
        raise HTTPException(status_code=400, detail='Proposed name is required')

    if len(proposed_name) > 50:
        raise HTTPException(status_code=400, detail='Region name must be 50 characters or less')

    # Get client IP
    client_ip = request.client.host if request.client else 'unknown'

    conn = None
    try:
        db_path = get_db_path()
        if not db_path.exists():
            raise HTTPException(status_code=500, detail='Database not initialized')

        conn = get_db_connection()
        cursor = conn.cursor()

        # Check if this name is already used by an approved region
        cursor.execute('SELECT region_x, region_y, region_z FROM regions WHERE custom_name = ?', (proposed_name,))
        existing = cursor.fetchone()
        if existing:
            raise HTTPException(
                status_code=409,
                detail=f'Region name "{proposed_name}" is already used by region [{existing["region_x"]}, {existing["region_y"]}, {existing["region_z"]}]'
            )

        # Check if there's already a pending submission for this region
        cursor.execute('''
            SELECT id FROM pending_region_names
            WHERE region_x = ? AND region_y = ? AND region_z = ? AND status = 'pending'
        ''', (rx, ry, rz))
        pending = cursor.fetchone()
        if pending:
            raise HTTPException(
                status_code=409,
                detail='There is already a pending name submission for this region. Please wait for it to be reviewed.'
            )

        # Check if same name is pending for another region
        cursor.execute('''
            SELECT region_x, region_y, region_z FROM pending_region_names
            WHERE proposed_name = ? AND status = 'pending'
        ''', (proposed_name,))
        pending_same_name = cursor.fetchone()
        if pending_same_name:
            raise HTTPException(
                status_code=409,
                detail=f'Region name "{proposed_name}" is already pending approval for another region'
            )

        # Insert the submission
        cursor.execute('''
            INSERT INTO pending_region_names
            (region_x, region_y, region_z, proposed_name, submitted_by, submitted_by_ip, submission_date, status, discord_tag, personal_discord_username)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?)
        ''', (rx, ry, rz, proposed_name, submitted_by, client_ip, datetime.now(timezone.utc).isoformat(), discord_tag, personal_discord_username))

        conn.commit()

        # Add activity log
        add_activity_log(
            'region_submitted',
            f"Region name '{proposed_name}' submitted for approval",
            details=f"Region: [{rx}, {ry}, {rz}]",
            user_name=submitted_by
        )

        return {
            'status': 'submitted',
            'message': 'Region name submitted for approval',
            'region_x': rx,
            'region_y': ry,
            'region_z': rz,
            'proposed_name': proposed_name
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error submitting region name: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()


@app.get('/api/pending_region_names')
async def api_list_pending_region_names(session: Optional[str] = Cookie(None)):
    """
    List pending region name submissions (admin only).
    - Super admin: sees ALL submissions
    - Haven sub-admins: sees submissions tagged with "Haven" + additional discord tags
    - Partners/partner sub-admins: see only submissions tagged with their discord_tag
    """
    # Verify admin session and get session data
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail="Admin authentication required")

    is_super = session_data.get('user_type') == 'super_admin'
    is_haven_sub_admin = session_data.get('is_haven_sub_admin', False)
    partner_tag = session_data.get('discord_tag')

    conn = None
    try:
        db_path = get_db_path()
        if not db_path.exists():
            return {'pending': []}

        conn = get_db_connection()
        cursor = conn.cursor()

        if is_super:
            # Super admin sees ALL submissions
            cursor.execute('''
                SELECT id, region_x, region_y, region_z, proposed_name, submitted_by, submitted_by_ip,
                       submission_date, status, reviewed_by, review_date, review_notes,
                       discord_tag, personal_discord_username
                FROM pending_region_names
                ORDER BY
                    CASE status
                        WHEN 'pending' THEN 1
                        WHEN 'approved' THEN 2
                        WHEN 'rejected' THEN 3
                    END,
                    submission_date DESC
            ''')
        elif is_haven_sub_admin:
            # Haven sub-admins see submissions tagged with "Haven" + any additional discord tags
            additional_tags = session_data.get('additional_discord_tags', [])
            can_approve_personal = session_data.get('can_approve_personal_uploads', False)
            all_tags = ['Haven'] + additional_tags

            # Build dynamic query with placeholders
            placeholders = ','.join(['?' for _ in all_tags])

            if can_approve_personal:
                cursor.execute(f'''
                    SELECT id, region_x, region_y, region_z, proposed_name, submitted_by, submitted_by_ip,
                           submission_date, status, reviewed_by, review_date, review_notes,
                           discord_tag, personal_discord_username
                    FROM pending_region_names
                    WHERE discord_tag IN ({placeholders})
                       OR discord_tag = 'personal'
                       OR discord_tag IS NULL
                    ORDER BY
                        CASE status
                            WHEN 'pending' THEN 1
                            WHEN 'approved' THEN 2
                            WHEN 'rejected' THEN 3
                        END,
                        submission_date DESC
                ''', all_tags)
            else:
                cursor.execute(f'''
                    SELECT id, region_x, region_y, region_z, proposed_name, submitted_by, submitted_by_ip,
                           submission_date, status, reviewed_by, review_date, review_notes,
                           discord_tag, personal_discord_username
                    FROM pending_region_names
                    WHERE discord_tag IN ({placeholders})
                       OR discord_tag IS NULL
                    ORDER BY
                        CASE status
                            WHEN 'pending' THEN 1
                            WHEN 'approved' THEN 2
                            WHEN 'rejected' THEN 3
                        END,
                        submission_date DESC
                ''', all_tags)
        else:
            # Partners and partner sub-admins only see submissions tagged with their discord_tag
            cursor.execute('''
                SELECT id, region_x, region_y, region_z, proposed_name, submitted_by, submitted_by_ip,
                       submission_date, status, reviewed_by, review_date, review_notes,
                       discord_tag, personal_discord_username
                FROM pending_region_names
                WHERE discord_tag = ?
                ORDER BY
                    CASE status
                        WHEN 'pending' THEN 1
                        WHEN 'approved' THEN 2
                        WHEN 'rejected' THEN 3
                    END,
                    submission_date DESC
            ''', (partner_tag,))

        rows = cursor.fetchall()
        pending = [dict(row) for row in rows]

        # Hide personal_discord_username for Haven sub-admins (only super admin sees contact info)
        if is_haven_sub_admin and not is_super:
            for submission in pending:
                submission['personal_discord_username'] = None

        return {'pending': pending, 'count': len(pending)}
    except Exception as e:
        logger.error(f"Error listing pending region names: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()


@app.post('/api/pending_region_names/{submission_id}/approve')
async def api_approve_region_name(submission_id: int, session: Optional[str] = Cookie(None)):
    """Approve a pending region name submission. Admin only."""
    from datetime import datetime, timezone

    if not verify_session(session):
        raise HTTPException(status_code=401, detail='Admin authentication required')

    conn = None
    try:
        db_path = get_db_path()
        if not db_path.exists():
            raise HTTPException(status_code=500, detail='Database not initialized')

        conn = get_db_connection()
        cursor = conn.cursor()

        # Get the pending submission
        cursor.execute('SELECT * FROM pending_region_names WHERE id = ? AND status = ?', (submission_id, 'pending'))
        submission = cursor.fetchone()
        if not submission:
            raise HTTPException(status_code=404, detail='Pending submission not found')

        submission = dict(submission)
        rx, ry, rz = submission['region_x'], submission['region_y'], submission['region_z']
        proposed_name = submission['proposed_name']

        # Check if name is still unique
        cursor.execute('SELECT id FROM regions WHERE custom_name = ?', (proposed_name,))
        if cursor.fetchone():
            # Mark as rejected since name was taken
            cursor.execute('''
                UPDATE pending_region_names
                SET status = 'rejected', review_date = ?, review_notes = ?
                WHERE id = ?
            ''', (datetime.now(timezone.utc).isoformat(), 'Name already taken by another region', submission_id))
            conn.commit()
            raise HTTPException(status_code=409, detail='Region name was already taken by another region')

        # Insert or update the region name
        cursor.execute('''
            INSERT INTO regions (region_x, region_y, region_z, custom_name, updated_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(region_x, region_y, region_z)
            DO UPDATE SET custom_name = excluded.custom_name, updated_at = CURRENT_TIMESTAMP
        ''', (rx, ry, rz, proposed_name))

        # Mark submission as approved
        cursor.execute('''
            UPDATE pending_region_names
            SET status = 'approved', review_date = ?, reviewed_by = 'admin'
            WHERE id = ?
        ''', (datetime.now(timezone.utc).isoformat(), submission_id))

        conn.commit()

        # Add activity log
        add_activity_log(
            'region_approved',
            f"Region name '{proposed_name}' approved",
            details=f"Region: [{rx}, {ry}, {rz}]",
            user_name='Admin'
        )

        return {
            'status': 'approved',
            'region_x': rx,
            'region_y': ry,
            'region_z': rz,
            'custom_name': proposed_name
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error approving region name: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()


@app.post('/api/pending_region_names/{submission_id}/reject')
async def api_reject_region_name(submission_id: int, payload: dict = None, session: Optional[str] = Cookie(None)):
    """Reject a pending region name submission. Admin only."""
    from datetime import datetime, timezone

    if not verify_session(session):
        raise HTTPException(status_code=401, detail='Admin authentication required')

    review_notes = payload.get('notes', '') if payload else ''

    conn = None
    try:
        db_path = get_db_path()
        if not db_path.exists():
            raise HTTPException(status_code=500, detail='Database not initialized')

        conn = get_db_connection()
        cursor = conn.cursor()

        # Get the pending submission
        cursor.execute('SELECT * FROM pending_region_names WHERE id = ? AND status = ?', (submission_id, 'pending'))
        submission = cursor.fetchone()
        if not submission:
            raise HTTPException(status_code=404, detail='Pending submission not found')

        submission_dict = dict(submission)
        proposed_name = submission_dict['proposed_name']
        rx, ry, rz = submission_dict['region_x'], submission_dict['region_y'], submission_dict['region_z']

        # Mark submission as rejected
        cursor.execute('''
            UPDATE pending_region_names
            SET status = 'rejected', review_date = ?, reviewed_by = 'admin', review_notes = ?
            WHERE id = ?
        ''', (datetime.now(timezone.utc).isoformat(), review_notes, submission_id))

        conn.commit()

        # Add activity log
        add_activity_log(
            'region_rejected',
            f"Region name '{proposed_name}' rejected",
            details=f"Region: [{rx}, {ry}, {rz}]. Reason: {review_notes or 'No reason provided'}",
            user_name='Admin'
        )

        return {
            'status': 'rejected',
            'submission_id': submission_id,
            'message': 'Region name submission rejected'
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error rejecting region name: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()


@app.get('/api/systems/{system_id}')
async def get_system(system_id: str, session: Optional[str] = Cookie(None)):
    """Return a single system by id or name, including nested planets, moons, and space station.

    Applies data restrictions based on viewer permissions.
    """
    session_data = get_session(session)

    conn = None
    try:
        db_path = get_db_path()
        if db_path.exists():
            conn = get_db_connection()
            cursor = conn.cursor()
            # Try by id
            cursor.execute('SELECT * FROM systems WHERE id = ?', (system_id,))
            row = cursor.fetchone()
            if not row:
                # Try by name
                cursor.execute('SELECT * FROM systems WHERE name = ?', (system_id,))
                row = cursor.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail='System not found')
            system = dict(row)
            sys_id = system.get('id')
            system_discord_tag = system.get('discord_tag')

            # Check if viewer can bypass restrictions for this system
            can_bypass = can_bypass_restriction(session_data, system_discord_tag)

            # Check for restrictions
            restriction = get_restriction_for_system(sys_id) if not can_bypass else None

            # If system is hidden and viewer cannot bypass, return 404
            if restriction and restriction.get('is_hidden_from_public'):
                raise HTTPException(status_code=404, detail='System not found')

            # planets
            cursor.execute('SELECT * FROM planets WHERE system_id = ?', (sys_id,))
            planets_rows = cursor.fetchall()
            planets = [dict(p) for p in planets_rows]
            for p in planets:
                cursor.execute('SELECT * FROM moons WHERE planet_id = ?', (p.get('id'),))
                moons_rows = cursor.fetchall()
                p['moons'] = [dict(m) for m in moons_rows]
            system['planets'] = planets

            # space station
            cursor.execute('SELECT * FROM space_stations WHERE system_id = ?', (sys_id,))
            station_row = cursor.fetchone()
            system['space_station'] = parse_station_data(station_row)

            # Completeness grade and breakdown
            completeness = calculate_completeness_score(cursor, sys_id)
            system['completeness_grade'] = completeness['grade']
            system['completeness_score'] = completeness['score']
            system['completeness_breakdown'] = completeness['breakdown']

            # Apply field restrictions if applicable
            if restriction and restriction.get('hidden_fields'):
                system = apply_field_restrictions(system, restriction['hidden_fields'])

            return system

        # JSON fallback
        data = load_data_json()
        systems = data.get('systems', [])
        for s in systems:
            if s.get('id') == system_id or s.get('name') == system_id:
                # Apply restrictions for JSON fallback too
                system_discord_tag = s.get('discord_tag')
                can_bypass = can_bypass_restriction(session_data, system_discord_tag)
                if not can_bypass:
                    restriction = get_restriction_for_system(s.get('id'))
                    if restriction:
                        if restriction.get('is_hidden_from_public'):
                            raise HTTPException(status_code=404, detail='System not found')
                        if restriction.get('hidden_fields'):
                            s = apply_field_restrictions(s, restriction['hidden_fields'])
                return s
        raise HTTPException(status_code=404, detail='System not found')
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()


@app.delete('/api/systems/{system_id}')
async def delete_system(system_id: str):
    conn = None
    try:
        db_path = get_db_path()
        if db_path.exists():
            conn = get_db_connection()
            cursor = conn.cursor()

            # Get system name before deleting
            cursor.execute('SELECT name FROM systems WHERE id = ? OR name = ?', (system_id, system_id))
            system_row = cursor.fetchone()
            system_name = system_row['name'] if system_row else system_id

            # Try delete by id first then by name
            cursor.execute('DELETE FROM discoveries WHERE system_id = ?', (system_id,))
            # Delete planets and moons
            cursor.execute('SELECT id FROM planets WHERE system_id = ?', (system_id,))
            planet_rows = cursor.fetchall()
            planet_ids = [r[0] for r in planet_rows]
            if planet_ids:
                cursor.executemany('DELETE FROM moons WHERE planet_id = ?', [(pid,) for pid in planet_ids])
                cursor.execute('DELETE FROM planets WHERE system_id = ?', (system_id,))
            # Delete system by id first
            cursor.execute('DELETE FROM systems WHERE id = ?', (system_id,))
            # If nothing deleted, try by name
            if conn.total_changes == 0:
                cursor.execute('SELECT id FROM systems WHERE name = ?', (system_id,))
                row = cursor.fetchone()
                if row:
                    sid = row[0]
                    cursor.execute('DELETE FROM discoveries WHERE system_id = ?', (sid,))
                    cursor.execute('SELECT id FROM planets WHERE system_id = ?', (sid,))
                    pr = cursor.fetchall()
                    pids = [r[0] for r in pr]
                    if pids:
                        cursor.executemany('DELETE FROM moons WHERE planet_id = ?', [(pid,) for pid in pids])
                        cursor.execute('DELETE FROM planets WHERE system_id = ?', (sid,))
                    cursor.execute('DELETE FROM systems WHERE id = ?', (sid,))
            conn.commit()

            # Add activity log
            add_activity_log(
                'system_deleted',
                f"System '{system_name}' deleted",
                user_name='Admin'
            )

            return {'status': 'ok'}

        # Fallback to JSON
        data = load_data_json()
        systems = data.get('systems', [])
        new_systems = [s for s in systems if not (s.get('id') == system_id or s.get('name') == system_id)]
        if len(new_systems) == len(systems):
            raise HTTPException(status_code=404, detail='System not found')
        data['systems'] = new_systems
        save_data_json(data)
        async with _systems_lock:
            _systems_cache.clear()
            for s in new_systems:
                _systems_cache[s.get('name')] = s
        return {'status': 'ok'}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()


# ---- Legacy endpoints (compatibility with older integrations like Keeper) ----
@app.get('/systems')
async def legacy_systems():
    return await api_systems()

@app.get('/systems/search')
async def legacy_systems_search(q: str = ''):
    return await api_search(q)

@app.post('/api/systems/stub')
async def create_system_stub(payload: dict, request: Request):
    """
    Create a minimal system stub for discovery linking.
    No auth required. Rate-limited by IP (60/hr).

    Required: name
    Optional: galaxy (default Euclid), glyph_code, reality (default Normal), discord_tag

    If a system with the same name or glyph_code already exists, returns it instead.
    """
    import uuid as uuid_mod

    name = (payload.get('name') or '').strip()
    if not name:
        raise HTTPException(status_code=400, detail='System name is required')
    if len(name) > 100:
        raise HTTPException(status_code=400, detail='System name must be 100 characters or less')

    galaxy = payload.get('galaxy', 'Euclid') or 'Euclid'
    reality = payload.get('reality', 'Normal') or 'Normal'
    glyph_code = (payload.get('glyph_code') or '').strip() or None
    discord_tag = payload.get('discord_tag')

    # Rate limit by IP
    client_ip = request.client.host if request.client else 'unknown'
    is_allowed, remaining = check_rate_limit(client_ip, 60, 1)
    if not is_allowed:
        raise HTTPException(status_code=429, detail='Rate limit exceeded. Please try again later.')

    # Validate galaxy
    if galaxy and not validate_galaxy(galaxy):
        raise HTTPException(status_code=400, detail=f"Unknown galaxy: {galaxy}")

    # Validate reality
    if reality and not validate_reality(reality):
        raise HTTPException(status_code=400, detail="Reality must be 'Normal' or 'Permadeath'")

    # Decode glyph if provided
    star_x, star_y, star_z = None, None, None
    region_x, region_y, region_z = None, None, None
    x, y, z = 0, 0, 0
    glyph_planet, glyph_solar_system = 0, 1
    if glyph_code:
        try:
            decoded = decode_glyph_to_coords(glyph_code)
            x = decoded.get('x', 0)
            y = decoded.get('y', 0)
            z = decoded.get('z', 0)
            star_x = decoded.get('star_x')
            star_y = decoded.get('star_y')
            star_z = decoded.get('star_z')
            region_x = decoded.get('region_x')
            region_y = decoded.get('region_y')
            region_z = decoded.get('region_z')
            glyph_planet = decoded.get('planet_index', 0)
            glyph_solar_system = decoded.get('solar_system_index', 1)
        except Exception as e:
            logger.warning(f"Failed to decode glyph for stub system: {e}")
            glyph_code = None  # Don't store invalid glyph

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Check for duplicate by name (case-insensitive)
        cursor.execute('SELECT id, name, galaxy, is_stub FROM systems WHERE LOWER(name) = LOWER(?)', (name,))
        existing = cursor.fetchone()
        if existing:
            return {
                'status': 'existing',
                'system_id': existing['id'],
                'name': existing['name'],
                'galaxy': existing['galaxy'],
                'is_stub': bool(existing['is_stub'])
            }

        # Check for duplicate by glyph_code
        if glyph_code:
            cursor.execute('SELECT id, name, galaxy, is_stub FROM systems WHERE glyph_code = ?', (glyph_code,))
            existing = cursor.fetchone()
            if existing:
                return {
                    'status': 'existing',
                    'system_id': existing['id'],
                    'name': existing['name'],
                    'galaxy': existing['galaxy'],
                    'is_stub': bool(existing['is_stub'])
                }

        # Create stub system
        sys_id = str(uuid_mod.uuid4())
        cursor.execute('''
            INSERT INTO systems (
                id, name, galaxy, reality, x, y, z,
                star_x, star_y, star_z,
                glyph_code, glyph_planet, glyph_solar_system,
                region_x, region_y, region_z,
                is_stub, data_source, discord_tag
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 'stub', ?)
        ''', (
            sys_id, name, galaxy, reality, x, y, z,
            star_x, star_y, star_z,
            glyph_code, glyph_planet, glyph_solar_system,
            region_x, region_y, region_z,
            discord_tag
        ))
        # Calculate and store completeness score (will be low for stubs)
        update_completeness_score(cursor, sys_id)
        conn.commit()

        logger.info(f"Created stub system '{name}' (ID: {sys_id})")
        add_activity_log('system_stub_created', f"Stub system '{name}' created for discovery linking")

        return {
            'status': 'created',
            'system_id': sys_id,
            'name': name,
            'galaxy': galaxy,
            'is_stub': True
        }

    except Exception as e:
        logger.error(f"Error creating stub system: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()


@app.post('/api/save_system')
async def save_system(payload: dict, session: Optional[str] = Cookie(None)):
    """
    Save a system directly to the database (admin only).
    Non-admin users should use /api/submit_system instead.
    Partners can only edit systems tagged with their discord_tag or untagged systems (with explanation).
    """
    # Verify admin session
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(
            status_code=401,
            detail='Admin authentication required. Non-admin users should submit systems for approval.'
        )

    is_super = session_data.get('user_type') == 'super_admin'
    partner_tag = session_data.get('discord_tag')
    partner_id = session_data.get('partner_id')

    name = payload.get('name')
    if not name:
        raise HTTPException(status_code=400, detail='Name required')

    # Validate and normalize reality (default to Normal)
    reality = payload.get('reality', 'Normal')
    if not validate_reality(reality):
        raise HTTPException(status_code=400, detail="Reality must be 'Normal' or 'Permadeath'")
    payload['reality'] = reality

    # Validate galaxy if provided
    galaxy = payload.get('galaxy', 'Euclid')
    if galaxy and not validate_galaxy(galaxy):
        raise HTTPException(status_code=400, detail=f"Unknown galaxy: {galaxy}")
    payload['galaxy'] = galaxy

    # Get system ID if provided (for updates)
    system_id = payload.get('id')

    # Partner permission checks for editing existing systems
    if not is_super and system_id:
        conn_check = None
        try:
            conn_check = get_db_connection()
            cursor_check = conn_check.cursor()
            cursor_check.execute('SELECT discord_tag FROM systems WHERE id = ?', (system_id,))
            row = cursor_check.fetchone()
            if row:
                existing_tag = row['discord_tag']

                if existing_tag and existing_tag != partner_tag:
                    # Partner trying to edit another partner's system
                    raise HTTPException(
                        status_code=403,
                        detail=f'You can only edit systems tagged with your Discord ({partner_tag})'
                    )

                if not existing_tag:
                    # Partner editing untagged system - requires approval
                    explanation = payload.get('edit_explanation', '').strip()
                    if not explanation:
                        raise HTTPException(
                            status_code=400,
                            detail='Editing untagged systems requires an explanation'
                        )

                    # Create pending edit request instead of saving directly
                    cursor_check.execute('''
                        INSERT INTO pending_edit_requests
                        (system_id, partner_id, edit_data, explanation)
                        VALUES (?, ?, ?, ?)
                    ''', (system_id, partner_id, json.dumps(payload), explanation))
                    conn_check.commit()

                    return {
                        'status': 'pending_approval',
                        'message': 'Your edit has been submitted for super admin approval',
                        'request_id': cursor_check.lastrowid
                    }
        finally:
            if conn_check:
                conn_check.close()

    # For partners creating new systems, auto-tag with their discord
    if not is_super and not system_id and partner_tag:
        # Only auto-tag if no tag is provided or if they're trying to use their own tag
        if not payload.get('discord_tag') or payload.get('discord_tag') == partner_tag:
            payload['discord_tag'] = partner_tag
        elif payload.get('discord_tag') != partner_tag:
            raise HTTPException(
                status_code=403,
                detail='You can only tag systems with your Discord'
            )

    # Normalize empty glyph_code to None (NULL) to avoid unique constraint issues
    # The unique index only applies WHERE glyph_code IS NOT NULL, so empty strings cause conflicts
    if not payload.get('glyph_code'):
        payload['glyph_code'] = None

    # Calculate star position from glyph if available
    # Star position is the actual 3D location within the region (for non-overlapping rendering)
    star_x, star_y, star_z = None, None, None
    if payload.get('glyph_code'):
        try:
            decoded = decode_glyph_to_coords(payload['glyph_code'])
            star_x = decoded['star_x']
            star_y = decoded['star_y']
            star_z = decoded['star_z']
            logger.info(f"Calculated star position: ({star_x:.2f}, {star_y:.2f}, {star_z:.2f})")
        except Exception as e:
            logger.warning(f"Failed to calculate star position from glyph: {e}")

    # Get system ID if provided (for updates)
    system_id = payload.get('id')

    # DEBUG: Log incoming payload to diagnose data loss
    logger.info(f"=== SAVE_SYSTEM DEBUG ===")
    logger.info(f"System name: {name}, id: {system_id}")
    logger.info(f"Planets count: {len(payload.get('planets', []))}")
    for i, planet in enumerate(payload.get('planets', [])):
        logger.info(f"  Planet {i}: name={planet.get('name')}, fauna={planet.get('fauna')}, flora={planet.get('flora')}, materials={planet.get('materials')}, sentinel={planet.get('sentinel')}")

    # Save to database
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Check if system exists - prefer ID lookup (handles name changes), fallback to name
        existing = None
        if system_id:
            cursor.execute('SELECT id FROM systems WHERE id = ?', (system_id,))
            existing = cursor.fetchone()
        if not existing:
            cursor.execute('SELECT id FROM systems WHERE name = ?', (name,))
            existing = cursor.fetchone()

        # Get the editor's username for contributor tracking
        editor_username = session_data.get('username') or payload.get('personal_discord_username') or 'Unknown'
        now_iso = datetime.now(timezone.utc).isoformat()

        if existing:
            sys_id = existing['id']

            # Get current contributor data to preserve/update
            cursor.execute('SELECT discovered_by, contributors FROM systems WHERE id = ?', (sys_id,))
            current_row = cursor.fetchone()
            current_discovered_by = current_row['discovered_by'] if current_row else None
            current_contributors = current_row['contributors'] if current_row else None

            # Parse and add edit entry
            try:
                contributors_list = json.loads(current_contributors) if current_contributors else []
            except (json.JSONDecodeError, TypeError):
                contributors_list = []

            contributors_list.append({"name": editor_username, "action": "edit", "date": now_iso})

            # Update existing system (including contributor tracking, clear stub flag)
            cursor.execute('''
                UPDATE systems SET
                    name = ?, galaxy = ?, reality = ?, x = ?, y = ?, z = ?,
                    star_x = ?, star_y = ?, star_z = ?,
                    description = ?,
                    glyph_code = ?, glyph_planet = ?, glyph_solar_system = ?,
                    region_x = ?, region_y = ?, region_z = ?,
                    star_type = ?, economy_type = ?, economy_level = ?,
                    conflict_level = ?, dominant_lifeform = ?, discord_tag = ?,
                    stellar_classification = ?,
                    last_updated_by = ?, last_updated_at = ?, contributors = ?,
                    is_stub = 0
                WHERE id = ?
            ''', (
                name,
                payload.get('galaxy', 'Euclid'),
                payload.get('reality', 'Normal'),
                payload.get('x', 0),
                payload.get('y', 0),
                payload.get('z', 0),
                star_x,
                star_y,
                star_z,
                payload.get('description', ''),
                payload.get('glyph_code'),
                payload.get('glyph_planet', 0),
                payload.get('glyph_solar_system', 1),
                payload.get('region_x'),
                payload.get('region_y'),
                payload.get('region_z'),
                payload.get('star_type'),
                payload.get('economy_type'),
                payload.get('economy_level'),
                payload.get('conflict_level'),
                payload.get('dominant_lifeform'),
                payload.get('discord_tag'),
                payload.get('stellar_classification'),
                editor_username,
                datetime.now(timezone.utc).isoformat(),
                json.dumps(contributors_list),
                sys_id
            ))
            logger.info(f"Updated system {sys_id}, last_updated_by: {editor_username}")

            # Delete existing planets (will cascade to moons)
            cursor.execute('DELETE FROM planets WHERE system_id = ?', (sys_id,))
            # Delete existing space station
            cursor.execute('DELETE FROM space_stations WHERE system_id = ?', (sys_id,))
        else:
            # Generate new ID
            import uuid
            sys_id = str(uuid.uuid4())
            # Insert new system (including contributor tracking)
            cursor.execute('''
                INSERT INTO systems (id, name, galaxy, reality, x, y, z, star_x, star_y, star_z, description,
                    glyph_code, glyph_planet, glyph_solar_system, region_x, region_y, region_z,
                    star_type, economy_type, economy_level, conflict_level, dominant_lifeform, discord_tag,
                    stellar_classification, discovered_by, discovered_at, contributors)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                sys_id,
                name,
                payload.get('galaxy', 'Euclid'),
                payload.get('reality', 'Normal'),
                payload.get('x', 0),
                payload.get('y', 0),
                payload.get('z', 0),
                star_x,
                star_y,
                star_z,
                payload.get('description', ''),
                payload.get('glyph_code'),
                payload.get('glyph_planet', 0),
                payload.get('glyph_solar_system', 1),
                payload.get('region_x'),
                payload.get('region_y'),
                payload.get('region_z'),
                payload.get('star_type'),
                payload.get('economy_type'),
                payload.get('economy_level'),
                payload.get('conflict_level'),
                payload.get('dominant_lifeform'),
                payload.get('discord_tag'),
                payload.get('stellar_classification'),
                editor_username,
                now_iso,
                json.dumps([{"name": editor_username, "action": "upload", "date": now_iso}])
            ))
            logger.info(f"Created new system {sys_id}, discovered_by: {editor_username}")

        # Insert planets with ALL fields (including weather, resources, hazards from Haven Extractor)
        for planet in payload.get('planets', []):
            cursor.execute('''
                INSERT INTO planets (
                    system_id, name, x, y, z, climate, weather, sentinel, fauna, flora,
                    fauna_count, flora_count, has_water, materials, base_location, photo, notes, description,
                    biome, biome_subtype, planet_size, planet_index, is_moon,
                    storm_frequency, weather_intensity, building_density,
                    hazard_temperature, hazard_radiation, hazard_toxicity,
                    common_resource, uncommon_resource, rare_resource,
                    weather_text, sentinels_text, flora_text, fauna_text,
                    vile_brood, dissonance, ancient_bones, salvageable_scrap,
                    storm_crystals, gravitino_balls, infested, exotic_trophy
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                sys_id,
                planet.get('name', 'Unknown'),
                planet.get('x', 0),
                planet.get('y', 0),
                planet.get('z', 0),
                planet.get('climate'),
                planet.get('weather'),
                planet.get('sentinel', 'None'),
                planet.get('fauna', 'N/A'),
                planet.get('flora', 'N/A'),
                planet.get('fauna_count', 0),
                planet.get('flora_count', 0),
                planet.get('has_water', 0),
                planet.get('materials'),
                planet.get('base_location'),
                planet.get('photo'),
                planet.get('notes'),
                planet.get('description', ''),
                # Extended Haven Extractor fields
                planet.get('biome'),
                planet.get('biome_subtype'),
                planet.get('planet_size'),
                planet.get('planet_index', planet.get('index', 0)),
                1 if planet.get('is_moon', False) else 0,
                planet.get('storm_frequency'),
                planet.get('weather_intensity'),
                planet.get('building_density'),
                planet.get('hazard_temperature', 0),
                planet.get('hazard_radiation', 0),
                planet.get('hazard_toxicity', 0),
                planet.get('common_resource'),
                planet.get('uncommon_resource'),
                planet.get('rare_resource'),
                planet.get('weather_text'),
                planet.get('sentinels_text'),
                planet.get('flora_text'),
                planet.get('fauna_text'),
                # Special planet features
                1 if planet.get('vile_brood') else 0,
                1 if planet.get('dissonance') else 0,
                1 if planet.get('ancient_bones') else 0,
                1 if planet.get('salvageable_scrap') else 0,
                1 if planet.get('storm_crystals') else 0,
                1 if planet.get('gravitino_balls') else 0,
                1 if planet.get('infested') else 0,
                planet.get('exotic_trophy')
            ))
            planet_id = cursor.lastrowid

            # Insert moons with ALL fields
            for moon in planet.get('moons', []):
                cursor.execute('''
                    INSERT INTO moons (planet_id, name, orbit_radius, orbit_speed, climate, sentinel, fauna, flora, materials, notes, description, photo)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    planet_id,
                    moon.get('name', 'Unknown'),
                    moon.get('orbit_radius', 0.5),
                    moon.get('orbit_speed', 0),
                    moon.get('climate'),
                    moon.get('sentinel', 'None'),
                    moon.get('fauna', 'N/A'),
                    moon.get('flora', 'N/A'),
                    moon.get('materials'),
                    moon.get('notes'),
                    moon.get('description', ''),
                    moon.get('photo')
                ))

        # Insert space station if present
        if payload.get('space_station'):
            station = payload['space_station']
            # Convert trade_goods list to JSON string
            trade_goods_json = json.dumps(station.get('trade_goods', []))
            cursor.execute('''
                INSERT INTO space_stations (system_id, name, race, x, y, z, trade_goods)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                sys_id,
                station.get('name', f"{name} Station"),
                station.get('race', 'Gek'),
                station.get('x', 0),
                station.get('y', 0),
                station.get('z', 0),
                trade_goods_json
            ))

        # Calculate and store completeness score
        update_completeness_score(cursor, sys_id)
        conn.commit()
        logger.info(f"Saved system '{name}' to database (ID: {sys_id})")

        # Add audit log entry for direct saves (so super admin can track everything)
        is_edit = existing is not None
        action = 'direct_edit' if is_edit else 'direct_add'
        current_username = session_data.get('username')
        current_user_type = session_data.get('user_type')
        current_account_id = session_data.get('partner_id') or session_data.get('sub_admin_id')

        try:
            cursor.execute('''
                INSERT INTO approval_audit_log
                (timestamp, action, submission_type, submission_id, submission_name,
                 approver_username, approver_type, approver_account_id, approver_discord_tag,
                 submitter_username, submitter_account_id, submitter_type, notes, submission_discord_tag)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                datetime.now(timezone.utc).isoformat(),
                action,
                'system',
                0,  # Use 0 as placeholder for direct saves (bypasses pending_systems)
                name,
                current_username,
                current_user_type,
                current_account_id,
                session_data.get('discord_tag'),
                current_username,  # Submitter is same as approver for direct saves
                current_account_id,
                current_user_type,
                f"Direct save to database (system_id: {sys_id})",
                payload.get('discord_tag')
            ))
            conn.commit()
            logger.info(f"Audit log: {action} for system '{name}' by {current_username}")
        except Exception as audit_err:
            logger.warning(f"Failed to add audit log entry: {audit_err}")

        # Also save to JSON for backup
        async with _systems_lock:
            payload['id'] = sys_id
            _systems_cache[name] = payload
            save_data_json({'systems': list(_systems_cache.values())})

        return {'status': 'ok', 'saved': payload, 'system_id': sys_id}

    except Exception as e:
        logger.error(f'Error saving system to database: {e}')
        raise HTTPException(status_code=500, detail=f'Database error: {str(e)}')
    finally:
        if conn:
            conn.close()

@app.get('/api/db_stats')
async def db_stats(session: Optional[str] = Cookie(None)):
    """
    Get database statistics based on user permission level.
    - Public (no auth): Basic global stats (systems, planets, moons, regions, planet_pois)
    - Partners/Sub-admins: Community-filtered stats for their discord_tag
    - Super Admin: Curated dashboard with admin-specific stats
    """
    session_data = get_session(session) if session else None

    conn = None
    try:
        db_path = HAVEN_UI_DIR / 'data' / 'haven_ui.db'
        if not db_path.exists():
            return {'stats': {}, 'note': 'Database not found'}

        conn = get_db_connection()
        cursor = conn.cursor()

        # Determine user type
        user_type = session_data.get('user_type') if session_data else None
        is_super = user_type == 'super_admin'
        is_partner = user_type == 'partner'
        is_sub_admin = user_type == 'sub_admin'
        partner_tag = session_data.get('discord_tag') if session_data else None

        stats = {}

        if is_super:
            # ============================================
            # SUPER ADMIN: Curated dashboard with meaningful stats
            # ============================================

            # Core data stats
            cursor.execute("SELECT COUNT(*) FROM systems")
            stats['total_systems'] = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM planets")
            stats['total_planets'] = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM moons")
            stats['total_moons'] = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM regions")
            stats['total_regions'] = cursor.fetchone()[0]

            # Count populated regions (distinct region coordinates with at least one system)
            cursor.execute("""
                SELECT COUNT(*) FROM (
                    SELECT DISTINCT region_x, region_y, region_z
                    FROM systems
                    WHERE region_x IS NOT NULL AND region_y IS NOT NULL AND region_z IS NOT NULL
                )
            """)
            stats['populated_regions'] = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM space_stations")
            stats['total_space_stations'] = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM planet_pois")
            stats['total_planet_pois'] = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM discoveries")
            stats['total_discoveries'] = cursor.fetchone()[0]

            # Unique galaxies
            cursor.execute("SELECT COUNT(DISTINCT galaxy) FROM systems WHERE galaxy IS NOT NULL")
            stats['unique_galaxies'] = cursor.fetchone()[0]

            # Admin stats
            cursor.execute("SELECT COUNT(*) FROM partner_accounts")
            stats['partner_accounts'] = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM sub_admin_accounts")
            stats['sub_admin_accounts'] = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM api_keys")
            stats['api_keys'] = cursor.fetchone()[0]

            # Pending approvals
            cursor.execute("SELECT COUNT(*) FROM pending_systems WHERE status = 'pending'")
            stats['pending_systems'] = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM pending_region_names WHERE status = 'pending'")
            stats['pending_region_names'] = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM pending_edit_requests WHERE status = 'pending'")
            stats['pending_edit_requests'] = cursor.fetchone()[0]

            # Audit and activity
            cursor.execute("SELECT COUNT(*) FROM approval_audit_log")
            stats['approval_audit_entries'] = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM activity_logs")
            stats['activity_log_entries'] = cursor.fetchone()[0]

            # Community breakdown
            cursor.execute("""
                SELECT COUNT(DISTINCT discord_tag) FROM systems
                WHERE discord_tag IS NOT NULL AND discord_tag != ''
            """)
            stats['active_communities'] = cursor.fetchone()[0]

            # Data restrictions
            cursor.execute("SELECT COUNT(*) FROM data_restrictions")
            stats['data_restrictions'] = cursor.fetchone()[0]

            return {'stats': stats, 'user_type': 'super_admin'}

        elif (is_partner or is_sub_admin) and partner_tag:
            # ============================================
            # PARTNER/SUB-ADMIN: Community-filtered stats
            # ============================================

            # Count systems with partner's tag
            cursor.execute('SELECT COUNT(*) FROM systems WHERE discord_tag = ?', (partner_tag,))
            stats['star_systems'] = cursor.fetchone()[0]

            # Count planets in partner's systems
            cursor.execute('''
                SELECT COUNT(*) FROM planets p
                JOIN systems s ON p.system_id = s.id
                WHERE s.discord_tag = ?
            ''', (partner_tag,))
            stats['planets'] = cursor.fetchone()[0]

            # Count moons in partner's systems
            cursor.execute('''
                SELECT COUNT(*) FROM moons m
                JOIN planets p ON m.planet_id = p.id
                JOIN systems s ON p.system_id = s.id
                WHERE s.discord_tag = ?
            ''', (partner_tag,))
            stats['moons'] = cursor.fetchone()[0]

            # Count space stations in partner's systems
            cursor.execute('''
                SELECT COUNT(*) FROM space_stations ss
                JOIN systems s ON ss.system_id = s.id
                WHERE s.discord_tag = ?
            ''', (partner_tag,))
            stats['space_stations'] = cursor.fetchone()[0]

            # Count regions with partner's tag
            cursor.execute('SELECT COUNT(*) FROM regions WHERE discord_tag = ?', (partner_tag,))
            stats['regions'] = cursor.fetchone()[0]

            # Count planet POIs for partner's systems
            cursor.execute('''
                SELECT COUNT(*) FROM planet_pois pp
                JOIN planets p ON pp.planet_id = p.id
                JOIN systems s ON p.system_id = s.id
                WHERE s.discord_tag = ?
            ''', (partner_tag,))
            stats['planet_pois'] = cursor.fetchone()[0]

            # Count discoveries for partner (join through systems)
            cursor.execute('''
                SELECT COUNT(*) FROM discoveries d
                JOIN systems s ON d.system_id = s.id
                WHERE s.discord_tag = ?
            ''', (partner_tag,))
            stats['discoveries'] = cursor.fetchone()[0]

            # Unique galaxies for partner
            cursor.execute('''
                SELECT COUNT(DISTINCT galaxy) FROM systems
                WHERE discord_tag = ? AND galaxy IS NOT NULL
            ''', (partner_tag,))
            stats['galaxies_explored'] = cursor.fetchone()[0]

            # Pending submissions for this community (that they can see - not their own)
            logged_in_username = normalize_discord_username(session_data.get('username', ''))
            cursor.execute('''
                SELECT COUNT(*) FROM pending_systems
                WHERE status = 'pending' AND discord_tag = ?
            ''', (partner_tag,))
            stats['pending_for_review'] = cursor.fetchone()[0]

            return {'stats': stats, 'discord_tag': partner_tag, 'user_type': user_type}

        else:
            # ============================================
            # PUBLIC: Basic global stats (no sensitive info)
            # ============================================

            cursor.execute("SELECT COUNT(*) FROM systems")
            system_count = cursor.fetchone()[0]
            stats['star_systems'] = system_count
            stats['systems'] = system_count  # Alias for Dashboard compatibility

            cursor.execute("SELECT COUNT(*) FROM planets")
            stats['planets'] = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM moons")
            stats['moons'] = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM regions")
            stats['regions'] = cursor.fetchone()[0]

            # Count populated regions (distinct region coordinates with at least one system)
            cursor.execute("""
                SELECT COUNT(*) FROM (
                    SELECT DISTINCT region_x, region_y, region_z
                    FROM systems
                    WHERE region_x IS NOT NULL AND region_y IS NOT NULL AND region_z IS NOT NULL
                )
            """)
            stats['populated_regions'] = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM planet_pois")
            stats['planet_pois'] = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM discoveries")
            stats['discoveries'] = cursor.fetchone()[0]

            return {'stats': stats, 'user_type': 'public'}

    except Exception as e:
        logger.error(f'Error getting db_stats: {e}')
        return {'stats': {}, 'error': str(e)}
    finally:
        if conn:
            conn.close()


# Legacy endpoint - redirects to unified db_stats
@app.get('/api/partner/stats')
async def partner_stats(session: Optional[str] = Cookie(None)):
    """Legacy endpoint - redirects to unified /api/db_stats"""
    return await db_stats(session)

@app.post('/api/generate_map')
async def generate_map():
    """Trigger map generation (queued for background processing)"""
    # Add activity log for map generation
    add_activity_log(
        'map_generated',
        "Galaxy map regeneration triggered",
        details="Background processing queued"
    )
    # This would normally trigger a background task
    # For now, just return success
    return {'status': 'ok', 'message': 'Map generation queued'}

@app.get('/api/tests')
async def list_tests():
    """List available test files"""
    try:
        tests_dir = HAVEN_UI_DIR.parent / 'tests'
        if not tests_dir.exists():
            return {'tests': []}

        test_files = []
        for file in tests_dir.glob('**/*.py'):
            if file.name.startswith('test_'):
                test_files.append(str(file.relative_to(HAVEN_UI_DIR.parent)))

        return {'tests': test_files}
    except Exception as e:
        return {'tests': [], 'error': str(e)}

@app.post('/api/tests/run')
async def run_test(payload: dict):
    """Run a specific test"""
    import subprocess
    test_path = payload.get('test_path', '')
    if not test_path:
        raise HTTPException(status_code=400, detail='test_path required')

    try:
        result = subprocess.run(
            ['python', '-m', 'pytest', test_path, '-v'],
            capture_output=True,
            text=True,
            timeout=30
        )
        return {
            'returncode': result.returncode,
            'stdout': result.stdout,
            'stderr': result.stderr
        }
    except subprocess.TimeoutExpired:
        return {'returncode': -1, 'stdout': '', 'stderr': 'Test timed out'}
    except Exception as e:
        return {'returncode': -1, 'stdout': '', 'stderr': str(e)}

@app.post('/api/photos')
async def upload_photo(file: UploadFile = File(...)):
    filename = file.filename or 'photo'
    dest = PHOTOS_DIR / filename
    # avoid overwriting by renaming
    if dest.exists():
        base = dest.stem
        suffix = dest.suffix
        i = 1
        while (PHOTOS_DIR / f"{base}-{i}{suffix}").exists():
            i += 1
        dest = PHOTOS_DIR / f"{base}-{i}{suffix}"
    with dest.open('wb') as f:
        f.write(await file.read())
    path = str(dest.relative_to(HAVEN_UI_DIR))
    return JSONResponse({'path': path})

@app.get('/map/latest')
async def get_map():
    """Serve the Three.js-based galaxy map.

    OPTIMIZED: Systems data is now loaded asynchronously via /api/map/regions-aggregated
    instead of being injected into the HTML. This dramatically improves load time
    for large databases (5000+ systems) as:
    1. HTML file is much smaller (no embedded JSON)
    2. Data is pre-aggregated by region on the server
    3. Map only loads summary data, not individual systems
    """
    mapfile = HAVEN_UI_DIR / 'dist' / 'VH-Map-ThreeJS.html'

    if not mapfile.exists():
        return HTMLResponse('<h1>Map Not Available</h1>')

    try:
        html = mapfile.read_text(encoding='utf-8')
        # Only inject discoveries data (small payload, still needed for discovery markers)
        # Systems data is now fetched asynchronously via /api/map/regions-aggregated
        db_path = get_db_path()
        if db_path.exists():
            discoveries = query_discoveries_from_db()
            discoveries_json = json.dumps(discoveries, ensure_ascii=True)
            html = re.sub(r"window\.DISCOVERIES_DATA\s*=\s*\[.*?\];", lambda m: f"window.DISCOVERIES_DATA = {discoveries_json};", html, flags=re.S)
        return HTMLResponse(html, media_type='text/html')
    except Exception as e:
        logger.error('Failed to render map latest: %s', e)
        return HTMLResponse('<h1>Map Error</h1>')


@app.get('/haven-ui/VH-Map.html')
async def get_haven_ui_map():
    # Mirror /map/latest behavior for the UI-hosted map page
    return await get_map()


@app.get('/map/region')
async def get_region_map(rx: int = 0, ry: int = 0, rz: int = 0,
                          session: Optional[str] = Cookie(None)):
    """Serve the Region View - shows all star systems within a specific region.

    URL parameters:
        rx, ry, rz: Region coordinates

    Example: /map/region?rx=2047&ry=128&rz=2048

    Applies map visibility restrictions based on viewer permissions.
    """
    session_data = get_session(session)

    mapfile = HAVEN_UI_DIR / 'dist' / 'VH-Map-Region.html'

    if not mapfile.exists():
        # Try public folder as fallback
        mapfile = HAVEN_UI_DIR / 'public' / 'VH-Map-Region.html'

    if not mapfile.exists():
        return HTMLResponse('<h1>Region Map Not Available</h1>')

    try:
        html = mapfile.read_text(encoding='utf-8')

        # Load systems for this region from DB
        db_path = get_db_path()
        if db_path.exists():
            conn = get_db_connection()
            cursor = conn.cursor()

            cursor.execute('''
                SELECT s.*,
                    (SELECT COUNT(*) FROM planets WHERE system_id = s.id) as planet_count
                FROM systems s
                WHERE s.region_x = ? AND s.region_y = ? AND s.region_z = ?
                ORDER BY s.name
            ''', (rx, ry, rz))

            rows = cursor.fetchall()
            systems = []
            for row in rows:
                system = dict(row)
                sys_id = system.get('id')
                cursor.execute('SELECT * FROM planets WHERE system_id = ?', (sys_id,))
                planets_rows = cursor.fetchall()
                system['planets'] = [dict(p) for p in planets_rows]
                systems.append(system)
            conn.close()

            # Apply map visibility restrictions
            systems = apply_data_restrictions(systems, session_data, for_map=True)

            region_data = {
                'region_x': rx,
                'region_y': ry,
                'region_z': rz,
                'systems': systems
            }
            region_json = json.dumps(region_data, ensure_ascii=True)

            # Inject region data into HTML
            html = re.sub(
                r"window\.REGION_DATA\s*=\s*\{[^}]*region_x[^}]*\};",
                lambda m: f"window.REGION_DATA = {region_json};",
                html,
                flags=re.S
            )

        return HTMLResponse(html, media_type='text/html')
    except Exception as e:
        logger.error('Failed to render region map: %s', e)
        return HTMLResponse(f'<h1>Region Map Error: {e}</h1>')


@app.get('/map/VH-Map.html')
async def redirect_map_vh():
    return RedirectResponse(url='/map/latest')


@app.get('/haven-ui/map')
async def redirect_haven_ui_map():
    return RedirectResponse(url='/map/latest')


@app.get('/map/{page}')
async def serve_map_page(page: str):
    """Serve map pages under /map/ including system pages and assets.

    - /map/latest -> handled elsewhere
    - /map/system_<name>.html -> serve system HTML from dist with injected DB data
    - static files under /map/* are handled by the mount '/map/static' and '/map/assets'
    """
    # served by dedicated dynamic handler
    if page == 'latest':
        return await get_map()

    # handle system pages like system_AURORA-7.html
    if page.startswith('system_') and page.endswith('.html'):
        filepath = HAVEN_UI_DIR / 'dist' / page
        if not filepath.exists():
            # Try case-insensitive fallback
            found = None
            for f in (HAVEN_UI_DIR / 'dist').glob('system_*.html'):
                if f.name.lower() == page.lower():
                    found = f
                    break
            if not found:
                raise HTTPException(status_code=404, detail='System page not found')
            filepath = found
        try:
            html = filepath.read_text(encoding='utf-8', errors='ignore')
            # Parse system name from the static page's SYSTEM_META if present
            m = re.search(r"window\.SYSTEM_META\s*=\s*(\{.*?\});", html, flags=re.S)
            system_name = None
            if m:
                try:
                    meta = json.loads(m.group(1))
                    system_name = meta.get('name')
                except Exception:
                    system_name = None

            # If not found via meta, derive from filename
            if not system_name:
                # strip prefix and suffix
                system_name = page[len('system_'):-len('.html')]
                # Replace underscores with spaces where appropriate
                system_name = system_name.replace('_', ' ')

            # Now find system in DB by name or id
            systems = load_systems_from_db()
            system = None
            for s in systems:
                if s.get('name') == system_name or s.get('id') == system_name or (s.get('name') or '').lower() == (system_name or '').lower():
                    system = s
                    break

            if system:
                planets = system.get('planets', [])
                discoveries = query_discoveries_from_db(system_id=system.get('id'))

                # Load space stations for this system
                db_path = get_db_path()
                space_stations = []
                if db_path.exists():
                    conn = None
                    try:
                        conn = get_db_connection()
                        cursor = conn.cursor()
                        cursor.execute('SELECT * FROM space_stations WHERE system_id = ?', (system.get('id'),))
                        stations_rows = cursor.fetchall()
                        space_stations = [parse_station_data(row) for row in stations_rows]
                        logger.info(f"Loaded {len(space_stations)} space stations for system {system.get('name')}")
                    except Exception as e:
                        logger.warning(f"Could not load space stations: {e}")
                    finally:
                        if conn:
                            conn.close()

                # Combine planets and stations into SYSTEMS_DATA
                # Add type field to stations for proper rendering
                systems_data = planets.copy()
                for station in space_stations:
                    station['type'] = 'station'  # Critical: tells map-viewer.js to render as purple box
                    systems_data.append(station)

                system_meta = {
                    'name': system.get('name'),
                    'galaxy': system.get('galaxy'),
                    'glyph': system.get('glyph_code'),
                    'x': system.get('x'),
                    'y': system.get('y'),
                    'z': system.get('z')
                }
                # Replace JSON data in HTML - use lambda to avoid regex escape issues with unicode/emojis
                systems_data_json = json.dumps(systems_data, ensure_ascii=True)
                system_meta_json = json.dumps(system_meta, ensure_ascii=True)
                discoveries_json = json.dumps(discoveries, ensure_ascii=True)
                html = re.sub(r"window\.SYSTEMS_DATA\s*=\s*\[.*?\];", lambda m: f"window.SYSTEMS_DATA = {systems_data_json};", html, flags=re.S)
                html = re.sub(r"window\.SYSTEM_META\s*=\s*\{.*?\};", lambda m: f"window.SYSTEM_META = {system_meta_json};", html, flags=re.S)
                html = re.sub(r"window\.DISCOVERIES_DATA\s*=\s*\[.*?\];", lambda m: f"window.DISCOVERIES_DATA = {discoveries_json};", html, flags=re.S)
            # Add no-cache headers to ensure fresh data is always fetched
            return HTMLResponse(
                html,
                media_type='text/html',
                headers={
                    'Cache-Control': 'no-cache, no-store, must-revalidate',
                    'Pragma': 'no-cache',
                    'Expires': '0'
                }
            )
        except Exception as e:
            logger.error('Failed to render system page %s: %s', page, e)
            raise HTTPException(status_code=500, detail='Error rendering system page')

    # Not a special map page - 404
    raise HTTPException(status_code=404, detail='Not found')


@app.get('/map/system/{system_id}')
async def get_system_3d_view(system_id: str):
    """Serve the 3D planetary view for a specific system with injected DB data.

    This serves VH-System-View.html with system data (planets, moons, station, discoveries)
    injected into window.SYSTEM_DATA.
    """
    # Find the system view HTML file
    system_view_file = HAVEN_UI_DIR / 'dist' / 'VH-System-View.html'

    if not system_view_file.exists():
        # Fallback to public directory
        system_view_file = HAVEN_UI_DIR / 'public' / 'VH-System-View.html'

    if not system_view_file.exists():
        raise HTTPException(status_code=404, detail='System view page not found')

    conn = None
    try:
        html = system_view_file.read_text(encoding='utf-8')

        # Load system data from database
        db_path = get_db_path()
        if not db_path.exists():
            raise HTTPException(status_code=500, detail='Database not found')

        conn = get_db_connection()
        cursor = conn.cursor()

        # Try to find system by id first, then by name
        cursor.execute('SELECT * FROM systems WHERE id = ?', (system_id,))
        row = cursor.fetchone()
        if not row:
            cursor.execute('SELECT * FROM systems WHERE name = ?', (system_id,))
            row = cursor.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail='System not found')

        system = dict(row)
        sys_id = system.get('id')

        # Load planets with their moons
        cursor.execute('SELECT * FROM planets WHERE system_id = ?', (sys_id,))
        planets_rows = cursor.fetchall()
        planets = []

        for p_row in planets_rows:
            planet = dict(p_row)
            planet_id = planet.get('id')

            # Load moons for this planet
            cursor.execute('SELECT * FROM moons WHERE planet_id = ?', (planet_id,))
            moons_rows = cursor.fetchall()
            planet['moons'] = [dict(m) for m in moons_rows]

            # Load discoveries for planet
            # Also match by location_name since keeper bot may submit with planet name instead of id
            planet_name = planet.get('name', '')
            cursor.execute('''
                SELECT * FROM discoveries
                WHERE planet_id = ?
                   OR (system_id = ? AND location_name = ? AND planet_id IS NULL AND moon_id IS NULL)
            ''', (planet_id, sys_id, planet_name))
            disc_rows = cursor.fetchall()
            planet['discoveries'] = [dict(d) for d in disc_rows]

            # Load discoveries for moons
            for moon in planet['moons']:
                moon_id = moon.get('id')
                moon_name = moon.get('name', '')
                # Check moon_id column, planet_id column (for legacy), and location_name (for keeper bot)
                cursor.execute('''
                    SELECT * FROM discoveries
                    WHERE moon_id = ?
                       OR planet_id = ?
                       OR (system_id = ? AND location_name = ? AND moon_id IS NULL)
                ''', (moon_id, moon_id, sys_id, moon_name))
                moon_disc_rows = cursor.fetchall()
                moon['discoveries'] = [dict(d) for d in moon_disc_rows]

            planets.append(planet)

        system['planets'] = planets

        # Load space station
        cursor.execute('SELECT * FROM space_stations WHERE system_id = ?', (sys_id,))
        station_row = cursor.fetchone()
        system['space_station'] = parse_station_data(station_row)

        # Inject system data into HTML
        # Use ensure_ascii=True to convert unicode chars to \uXXXX escapes
        system_json = json.dumps(system, ensure_ascii=True)
        # Use a lambda replacement to avoid regex escape sequence interpretation
        # This prevents "bad escape \u" errors when data contains emojis or unicode
        html = re.sub(
            r"window\.SYSTEM_DATA\s*=\s*null;",
            lambda m: f"window.SYSTEM_DATA = {system_json};",
            html
        )

        # Add no-cache headers to ensure fresh data is always fetched
        return HTMLResponse(
            html,
            media_type='text/html',
            headers={
                'Cache-Control': 'no-cache, no-store, must-revalidate',
                'Pragma': 'no-cache',
                'Expires': '0'
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error('Failed to render system 3D view for %s: %s', system_id, e)
        raise HTTPException(status_code=500, detail=f'Error rendering system view: {str(e)}')
    finally:
        if conn:
            conn.close()


# Simple logs API
@app.get('/api/logs')
async def get_logs():
    logfile = LOGS_DIR / 'control-room-web.log'
    if not logfile.exists():
        return {'lines': []}
    lines = logfile.read_text(encoding='utf-8', errors='ignore').splitlines()[-200:]
    return {'lines': lines}

# Minimal RT-AI integration: import and initialize if available
try:
    from roundtable_ai.api_integration import get_round_table_ai
    HAVE_RTAI = True
    rtai_instance = None
except Exception:
    HAVE_RTAI = False
    rtai_instance = None

@app.get('/api/rtai/status')
async def rtai_status():
    if not HAVE_RTAI:
        return {'available': False}
    if rtai_instance is None:
        return {'available': False}
    return {'available': True, 'agents': rtai_instance.list_agents(), 'stats': rtai_instance.get_statistics()}

@app.post('/api/rtai/analyze/discoveries')
async def analyze_discoveries(limit: int = 10):
    if not HAVE_RTAI or rtai_instance is None:
        raise HTTPException(status_code=503, detail='RTAI not available')
    result = await rtai_instance.analyze_discoveries(limit=limit)
    return {'result': result}

# RT-AI chat history (simple in-memory storage)
_rtai_history = []

@app.get('/api/rtai/history')
async def rtai_history():
    """Get RT-AI chat history"""
    return {'messages': _rtai_history}

@app.post('/api/rtai/clear')
async def rtai_clear():
    """Clear RT-AI chat history"""
    _rtai_history.clear()
    return {'status': 'ok'}

@app.post('/api/backup')
async def create_backup():
    """Create database backup"""
    try:
        import shutil
        from datetime import datetime
        db_path = HAVEN_UI_DIR / 'data' / 'haven_ui.db'
        if not db_path.exists():
            raise HTTPException(status_code=404, detail='Database not found')

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = HAVEN_UI_DIR / 'data' / f'haven_ui_backup_{timestamp}.db'
        shutil.copy2(db_path, backup_path)

        return {'backup_path': str(backup_path.relative_to(HAVEN_UI_DIR))}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post('/api/db_upload')
async def db_upload(file: UploadFile = File(...)):
    """Upload a database file"""
    try:
        dest = HAVEN_UI_DIR / 'data' / 'uploaded.db'
        with open(dest, 'wb') as f:
            content = await file.read()
            f.write(content)
        return {'path': str(dest.relative_to(HAVEN_UI_DIR))}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post('/api/import_csv')
async def import_csv(file: UploadFile = File(...), session: Optional[str] = Cookie(None)):
    """
    Import star systems from a CSV file (Google Spreadsheet export format).

    Expected CSV columns:
    - Named? (ignored)
    - Coordinates (galactic format: XXXX:YYYY:ZZZZ:SSSS)
    - Original System Name (stored in notes)
    - HUB Tag (stored in notes)
    - New System Name (used as system name)
    - Generated Hub Tag (ignored)
    - ARK Member (ignored)
    - Navigation Hints (ignored)
    - Comments/Special Attributes (stored in notes)
    - Ignore columns

    Row 1 contains the region name (e.g., "HUB1 - Sea of Xionahui")

    Requires super admin OR csv_import feature enabled.
    """
    # Verify session and permissions
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail='Authentication required')

    is_super = session_data.get('user_type') == 'super_admin'

    # Check for csv_import permission
    enabled_features = session_data.get('enabled_features', [])
    if not is_super and 'csv_import' not in enabled_features and 'CSV_IMPORT' not in enabled_features:
        raise HTTPException(
            status_code=403,
            detail='CSV import permission required'
        )

    partner_tag = session_data.get('discord_tag')

    try:
        # Read the CSV file content
        content = await file.read()
        text_content = content.decode('utf-8-sig')  # Handle BOM if present

        # Parse CSV
        reader = csv.reader(io.StringIO(text_content))
        rows = list(reader)

        if len(rows) < 2:
            raise HTTPException(status_code=400, detail='CSV file must have at least a header row and one data row')

        # Row 1 (index 0) contains region name - get it from the first non-empty cell
        region_name = None
        for cell in rows[0]:
            if cell and cell.strip():
                region_name = cell.strip()
                break

        # Row 2 (index 1) is the header row
        header = rows[1]

        # Map column indices (case-insensitive)
        header_lower = [h.lower().strip() for h in header]

        def find_col(names):
            for name in names:
                for i, h in enumerate(header_lower):
                    if name.lower() in h:
                        return i
            return None

        col_coords = find_col(['coordinates', 'coord'])
        col_original_name = find_col(['original system name', 'original name'])
        col_hub_tag = find_col(['hub tag'])
        col_new_name = find_col(['new system name', 'new name'])
        col_comments = find_col(['comments', 'special attributes', 'comments/special'])

        if col_coords is None:
            raise HTTPException(status_code=400, detail='Could not find Coordinates column in CSV')
        if col_hub_tag is None:
            raise HTTPException(status_code=400, detail='Could not find Hub Tag column in CSV')

        # Process data rows (starting from row 3 / index 2)
        imported_count = 0
        skipped_count = 0
        errors = []
        imported_region_coords = None  # Track region from first imported system

        conn = get_db_connection()
        cursor = conn.cursor()

        for row_idx, row in enumerate(rows[2:], start=3):
            try:
                # Skip empty rows
                if not row or len(row) <= max(filter(lambda x: x is not None, [col_coords, col_hub_tag])):
                    continue

                # Get coordinates
                coords = row[col_coords].strip() if col_coords < len(row) else ''
                if not coords or ':' not in coords:
                    skipped_count += 1
                    continue

                # Get system name from hub tag
                system_name = row[col_hub_tag].strip() if col_hub_tag < len(row) else ''
                if not system_name:
                    skipped_count += 1
                    continue

                # Build notes from various columns
                notes_parts = []

                # Store new system name in notes (if different from hub tag)
                if col_new_name is not None and col_new_name < len(row):
                    new_name = row[col_new_name].strip()
                    if new_name and new_name != system_name:
                        notes_parts.append(f"New Name: {new_name}")

                if col_original_name is not None and col_original_name < len(row):
                    orig_name = row[col_original_name].strip()
                    if orig_name and orig_name != system_name:
                        notes_parts.append(f"Original Name: {orig_name}")

                if col_comments is not None and col_comments < len(row):
                    comments = row[col_comments].strip()
                    if comments:
                        notes_parts.append(f"Notes: {comments}")

                description = '\n'.join(notes_parts)

                # Convert galactic coordinates to portal glyph
                try:
                    glyph_data = galactic_coords_to_glyph(coords)
                except ValueError as e:
                    errors.append(f"Row {row_idx}: Invalid coordinates '{coords}' - {e}")
                    skipped_count += 1
                    continue

                glyph_code = glyph_data['glyph']
                x = glyph_data['x']
                y = glyph_data['y']
                z = glyph_data['z']
                solar_system = glyph_data['solar_system']

                # Calculate star position
                star_x, star_y, star_z = None, None, None
                try:
                    decoded = decode_glyph_to_coords(glyph_code)
                    star_x = decoded['star_x']
                    star_y = decoded['star_y']
                    star_z = decoded['star_z']
                    region_x = decoded['region_x']
                    region_y = decoded['region_y']
                    region_z = decoded['region_z']
                except Exception:
                    region_x, region_y, region_z = None, None, None

                # Check for duplicate glyph
                cursor.execute('SELECT id, name FROM systems WHERE glyph_code = ?', (glyph_code,))
                existing = cursor.fetchone()
                if existing:
                    # Skip duplicates
                    skipped_count += 1
                    continue

                # Generate system ID
                import uuid
                sys_id = str(uuid.uuid4())

                # Determine discord_tag - use partner's tag if partner, otherwise None
                discord_tag = partner_tag if not is_super else None

                # Insert system
                cursor.execute('''
                    INSERT INTO systems (id, name, galaxy, reality, x, y, z, star_x, star_y, star_z, description,
                        glyph_code, glyph_planet, glyph_solar_system, region_x, region_y, region_z, discord_tag)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    sys_id,
                    system_name,
                    'Euclid',  # Galaxy is always Euclid for now
                    'Normal',  # Reality defaults to Normal
                    x,
                    y,
                    z,
                    star_x,
                    star_y,
                    star_z,
                    description,
                    glyph_code,
                    0,  # glyph_planet
                    solar_system,
                    region_x,
                    region_y,
                    region_z,
                    discord_tag
                ))

                imported_count += 1

                # Store region coords from first successfully imported system
                if imported_region_coords is None and region_x is not None and region_y is not None and region_z is not None:
                    imported_region_coords = {'region_x': region_x, 'region_y': region_y, 'region_z': region_z}

            except Exception as e:
                errors.append(f"Row {row_idx}: {str(e)}")
                skipped_count += 1

        conn.commit()
        conn.close()

        # Update region name if provided
        if region_name and imported_count > 0 and imported_region_coords:
            # Use the region coords from the first imported system
            conn = get_db_connection()
            cursor = conn.cursor()
            # Update or insert region name
            cursor.execute('''
                INSERT INTO regions (region_x, region_y, region_z, custom_name)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(region_x, region_y, region_z)
                DO UPDATE SET custom_name = excluded.custom_name
            ''', (imported_region_coords['region_x'], imported_region_coords['region_y'], imported_region_coords['region_z'], region_name))
            conn.commit()
            conn.close()

        # Log the import
        add_activity_log(
            'csv_import',
            f"Imported {imported_count} systems from CSV",
            details=f"File: {file.filename}, Skipped: {skipped_count}, Errors: {len(errors)}, Region: {region_name}",
            user_name=session_data.get('username', 'unknown')
        )

        return {
            'status': 'ok',
            'imported': imported_count,
            'skipped': skipped_count,
            'errors': errors[:10] if errors else [],  # Return first 10 errors
            'total_errors': len(errors),
            'region_name': region_name
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"CSV import error: {e}")
        raise HTTPException(status_code=500, detail=f"Import failed: {str(e)}")


@app.post('/api/migrate_hub_tags')
async def migrate_hub_tags(session: Optional[str] = Cookie(None)):
    """Migrate existing systems: extract HUB Tag from description and use it as system name"""
    import re

    # Check session - super admin only
    if not is_super_admin(session):
        raise HTTPException(status_code=403, detail='Super admin access required')

    session_data = get_session(session)

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Find all systems with "HUB Tag:" in description
        cursor.execute('''
            SELECT id, name, description FROM systems
            WHERE description LIKE '%HUB Tag:%'
        ''')
        systems = cursor.fetchall()

        updated_count = 0
        for system in systems:
            sys_id = system['id']
            old_name = system['name']
            description = system['description'] or ''

            # Extract hub tag from description
            match = re.search(r'HUB Tag:\s*([^\n]+)', description)
            if not match:
                continue

            hub_tag = match.group(1).strip()
            if not hub_tag or hub_tag == old_name:
                continue

            # Build new description: remove "HUB Tag:" line, add "New Name:" if old name wasn't already stored
            new_desc_parts = []
            has_new_name = 'New Name:' in description

            for line in description.split('\n'):
                line = line.strip()
                if line.startswith('HUB Tag:'):
                    # Skip this line (we're using it as the name now)
                    continue
                if line:
                    new_desc_parts.append(line)

            # Add old name as "New Name:" if not already present
            if not has_new_name and old_name and old_name != hub_tag:
                new_desc_parts.insert(0, f"New Name: {old_name}")

            new_description = '\n'.join(new_desc_parts)

            # Update the system
            cursor.execute('''
                UPDATE systems SET name = ?, description = ? WHERE id = ?
            ''', (hub_tag, new_description, sys_id))
            updated_count += 1

        conn.commit()
        conn.close()

        # Log the migration
        add_activity_log(
            'hub_tag_migration',
            f"Migrated {updated_count} systems to use hub tag as name",
            user_name=session_data.get('username', 'unknown')
        )

        return {'status': 'ok', 'updated': updated_count, 'total_found': len(systems)}

    except Exception as e:
        logger.error(f"Hub tag migration error: {e}")
        raise HTTPException(status_code=500, detail=f"Migration failed: {str(e)}")


# Lightweight endpoint for the Keeper bot to post discoveries
@app.get('/api/discoveries')
async def get_discoveries(q: str = '', user_id: str = '', limit: int = 100):
    """List or search discoveries, optionally filtered by user_id"""
    conn = None
    try:
        db_path = get_db_path()
        if db_path.exists():
            # If user_id provided, filter by discord_user_id
            if user_id:
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT d.*, s.name as system_name
                    FROM discoveries d
                    LEFT JOIN systems s ON d.system_id = s.id
                    WHERE d.discord_user_id = ?
                    ORDER BY d.submission_timestamp DESC
                    LIMIT ?
                ''', (user_id, limit))
                discoveries = [dict(row) for row in cursor.fetchall()]
                return {'discoveries': discoveries}

            discoveries = query_discoveries_from_db(q=q)
            return {'results': discoveries}

        data = load_data_json()
        discoveries = data.get('discoveries', [])
        # Filter by search query if provided
        if q:
            q_lower = q.lower()
            discoveries = [
                d for d in discoveries
                if (q_lower in str(d.get('description', '')).lower() or
                    q_lower in str(d.get('discovery_name', '')).lower() or
                    q_lower in str(d.get('location_name', '')).lower())
            ]
        # Filter by user_id if provided
        if user_id:
            discoveries = [d for d in discoveries if str(d.get('discord_user_id', '')) == user_id]
            discoveries = discoveries[:limit]
        return {'results': discoveries}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()

@app.post('/api/discoveries')
async def create_discovery(payload: dict):
    """Accept a discovery submission and store in the database."""
    conn = None
    try:
        db_path = get_db_path()
        logger.info(f"Received discovery submission: {payload.get('discovery_type', 'unknown')} from {payload.get('discovered_by', 'anonymous')}")

        # Always use database (initialized on startup)
        # Use standardized connection settings to avoid database locks
        conn = get_db_connection()
        cursor = conn.cursor()

        # Check for duplicate discovery (same name, system, and location)
        discovery_name = payload.get('discovery_name') or 'Unnamed Discovery'
        system_id = payload.get('system_id')
        location_name = payload.get('location_name') or 'Unknown Location'

        cursor.execute('''
            SELECT id FROM discoveries
            WHERE discovery_name = ? AND system_id = ? AND location_name = ?
        ''', (discovery_name, system_id, location_name))

        existing = cursor.fetchone()
        if existing:
            logger.info(f"Duplicate discovery rejected: {discovery_name} at {location_name} in system {system_id}")
            return JSONResponse({
                'status': 'duplicate',
                'message': f'Discovery "{discovery_name}" at "{location_name}" already exists',
                'existing_id': existing[0]
            }, status_code=409)

        # Get submission timestamp
        submission_ts = payload.get('submission_timestamp') or datetime.now().isoformat()

        # Get discovery type and compute slug
        discovery_type = payload.get('discovery_type') or 'Unknown'
        type_slug = get_discovery_type_slug(discovery_type)

        # Serialize type_metadata to JSON if provided
        type_metadata_raw = payload.get('type_metadata')
        type_metadata_json = json.dumps(type_metadata_raw) if type_metadata_raw and isinstance(type_metadata_raw, dict) else None

        cursor.execute('''
            INSERT INTO discoveries (
                discovery_type, discovery_name, system_id, planet_id, moon_id, location_type, location_name, description, significance, discovered_by, submission_timestamp, mystery_tier, analysis_status, pattern_matches, discord_user_id, discord_guild_id, photo_url, evidence_url, type_slug, discord_tag, type_metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            discovery_type,
            discovery_name,
            system_id,
            payload.get('planet_id'),
            payload.get('moon_id'),
            payload.get('location_type') or 'space',
            location_name,
            payload.get('description') or '',
            payload.get('significance') or 'Notable',
            payload.get('discord_username') or payload.get('discovered_by') or 'anonymous',
            submission_ts,
            payload.get('mystery_tier') or 1,
            payload.get('analysis_status') or 'pending',
            payload.get('pattern_matches') or 0,
            payload.get('discord_user_id'),
            payload.get('discord_guild_id'),
            payload.get('photo_url'),
            payload.get('evidence_urls'),
            type_slug,
            payload.get('discord_tag'),
            type_metadata_json,
        ))
        conn.commit()
        discovery_id = cursor.lastrowid

        logger.info(f"Discovery saved with ID: {discovery_id}")

        # Add activity log
        add_activity_log(
            'discovery_added',
            f"Discovery '{discovery_name}' added",
            details=f"Type: {payload.get('discovery_type', 'Unknown')}",
            user_name=payload.get('discovered_by', 'Anonymous')
        )

        return JSONResponse({'status': 'ok', 'discovery_id': discovery_id}, status_code=201)

    except Exception as e:
        logger.error(f"Error saving discovery: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()


@app.post('/discoveries')
async def legacy_discoveries(payload: dict):
    # Return the same 201 created response as /api/discoveries
    result = await create_discovery(payload)
    if isinstance(result, JSONResponse):
        # If inner function already returned a JSONResponse with 201, just return it
        return result
    # Normalize response to include discovery_id
    if isinstance(result, dict) and 'id' in result:
        return JSONResponse({'status': result.get('status', 'ok'), 'discovery_id': result['id']}, status_code=201)
    return JSONResponse(result, status_code=201)


# =============================================================================
# DISCOVERIES SHOWCASE API - Browse, Stats, Recent, Feature
# =============================================================================

@app.get('/api/discoveries/types')
async def get_discovery_types():
    """Get all discovery type definitions with metadata for the frontend."""
    return {
        'types': DISCOVERY_TYPE_INFO,
        'slugs': DISCOVERY_TYPE_SLUGS
    }


@app.get('/api/discoveries/browse')
async def browse_discoveries(
    type: str = None,
    q: str = '',
    sort: str = 'newest',
    discoverer: str = None,
    page: int = 0,
    limit: int = 24
):
    """
    Browse discoveries with filtering, pagination, and sorting.

    Args:
        type: Filter by type slug (fauna, flora, starship, etc.)
        q: Search query (searches name, description, location)
        sort: Sort order - newest, oldest, name, views
        discoverer: Filter by discovered_by field
        page: Page number (0-indexed)
        limit: Items per page (max 100)
    """
    conn = None
    try:
        db_path = get_db_path()
        if not db_path.exists():
            return {'discoveries': [], 'total': 0, 'pages': 0, 'page': page}

        conn = get_db_connection()
        cursor = conn.cursor()

        # Build WHERE clause
        where_clauses = []
        params = []

        # Filter by type slug
        if type and type in DISCOVERY_TYPE_SLUGS:
            where_clauses.append("type_slug = ?")
            params.append(type)

        # Search query
        if q:
            q_pattern = f"%{q}%"
            where_clauses.append("(discovery_name LIKE ? OR description LIKE ? OR location_name LIKE ?)")
            params.extend([q_pattern, q_pattern, q_pattern])

        # Filter by discoverer
        if discoverer:
            where_clauses.append("discovered_by LIKE ?")
            params.append(f"%{discoverer}%")

        # Build base query
        where_sql = " WHERE " + " AND ".join(where_clauses) if where_clauses else ""

        # Get total count
        count_sql = f"SELECT COUNT(*) FROM discoveries{where_sql}"
        cursor.execute(count_sql, params)
        total = cursor.fetchone()[0]

        # Calculate pagination
        limit = min(limit, 100)  # Cap at 100
        offset = page * limit
        pages = (total + limit - 1) // limit if total > 0 else 0

        # Sort order
        sort_map = {
            'newest': 'submission_timestamp DESC',
            'oldest': 'submission_timestamp ASC',
            'name': 'discovery_name ASC',
            'views': 'view_count DESC',
        }
        order_by = sort_map.get(sort, 'submission_timestamp DESC')

        # Fetch discoveries with system, planet, moon info
        query = f'''
            SELECT d.*, s.name as system_name, s.galaxy as system_galaxy,
                   s.is_stub as system_is_stub,
                   p.name as planet_name, m.name as moon_name
            FROM discoveries d
            LEFT JOIN systems s ON d.system_id = s.id
            LEFT JOIN planets p ON d.planet_id = p.id
            LEFT JOIN moons m ON d.moon_id = m.id
            {where_sql}
            ORDER BY {order_by}
            LIMIT ? OFFSET ?
        '''
        cursor.execute(query, params + [limit, offset])
        discoveries = [dict(row) for row in cursor.fetchall()]

        # Add type info to each discovery
        for d in discoveries:
            slug = d.get('type_slug') or get_discovery_type_slug(d.get('discovery_type', ''))
            d['type_info'] = DISCOVERY_TYPE_INFO.get(slug, DISCOVERY_TYPE_INFO['other'])

        return {
            'discoveries': discoveries,
            'total': total,
            'pages': pages,
            'page': page
        }

    except Exception as e:
        logger.error(f"Error browsing discoveries: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()


@app.get('/api/discoveries/stats')
async def get_discovery_stats():
    """
    Get discovery statistics by type for the landing page.

    Returns total counts overall and per type, plus this week's count.
    """
    conn = None
    try:
        db_path = get_db_path()
        if not db_path.exists():
            return {
                'total': 0,
                'by_type': {slug: 0 for slug in DISCOVERY_TYPE_SLUGS},
                'this_week': 0,
                'featured_count': 0
            }

        conn = get_db_connection()
        cursor = conn.cursor()

        # Total count
        cursor.execute("SELECT COUNT(*) FROM discoveries")
        total = cursor.fetchone()[0]

        # Count by type_slug
        cursor.execute('''
            SELECT COALESCE(type_slug, 'other') as slug, COUNT(*) as cnt
            FROM discoveries
            GROUP BY type_slug
        ''')
        by_type = {slug: 0 for slug in DISCOVERY_TYPE_SLUGS}
        for row in cursor.fetchall():
            slug = row[0] if row[0] in DISCOVERY_TYPE_SLUGS else 'other'
            by_type[slug] = by_type.get(slug, 0) + row[1]

        # This week's count
        week_ago = (datetime.now() - timedelta(days=7)).isoformat()
        cursor.execute("SELECT COUNT(*) FROM discoveries WHERE submission_timestamp > ?", (week_ago,))
        this_week = cursor.fetchone()[0]

        # Featured count
        cursor.execute("SELECT COUNT(*) FROM discoveries WHERE is_featured = 1")
        featured_count = cursor.fetchone()[0]

        return {
            'total': total,
            'by_type': by_type,
            'this_week': this_week,
            'featured_count': featured_count,
            'type_info': DISCOVERY_TYPE_INFO
        }

    except Exception as e:
        logger.error(f"Error getting discovery stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()


@app.get('/api/discoveries/recent')
async def get_recent_discoveries(limit: int = 8):
    """
    Get the most recent discoveries for the landing page.

    Prioritizes discoveries with photos for better visual display.
    """
    conn = None
    try:
        db_path = get_db_path()
        if not db_path.exists():
            return {'discoveries': []}

        conn = get_db_connection()
        cursor = conn.cursor()

        # Get recent discoveries, prioritizing those with photos
        limit = min(limit, 20)
        cursor.execute('''
            SELECT d.*, s.name as system_name, s.galaxy as system_galaxy,
                   s.is_stub as system_is_stub,
                   p.name as planet_name, m.name as moon_name
            FROM discoveries d
            LEFT JOIN systems s ON d.system_id = s.id
            LEFT JOIN planets p ON d.planet_id = p.id
            LEFT JOIN moons m ON d.moon_id = m.id
            ORDER BY
                CASE WHEN d.photo_url IS NOT NULL AND d.photo_url != '' THEN 0 ELSE 1 END,
                d.submission_timestamp DESC
            LIMIT ?
        ''', (limit,))

        discoveries = [dict(row) for row in cursor.fetchall()]

        # Add type info to each discovery
        for d in discoveries:
            slug = d.get('type_slug') or get_discovery_type_slug(d.get('discovery_type', ''))
            d['type_info'] = DISCOVERY_TYPE_INFO.get(slug, DISCOVERY_TYPE_INFO['other'])

        return {'discoveries': discoveries}

    except Exception as e:
        logger.error(f"Error getting recent discoveries: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()


@app.get('/api/discoveries/{discovery_id}')
async def get_discovery(discovery_id: int):
    """Get a specific discovery by ID with system/planet/moon info."""
    conn = None
    try:
        db_path = get_db_path()
        if db_path.exists():
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT d.*, s.name as system_name, s.galaxy as system_galaxy,
                       s.is_stub as system_is_stub,
                       p.name as planet_name, m.name as moon_name
                FROM discoveries d
                LEFT JOIN systems s ON d.system_id = s.id
                LEFT JOIN planets p ON d.planet_id = p.id
                LEFT JOIN moons m ON d.moon_id = m.id
                WHERE d.id = ?
            ''', (discovery_id,))
            row = cursor.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail='Discovery not found')
            discovery = dict(row)
            # Parse type_metadata JSON if present
            if discovery.get('type_metadata'):
                try:
                    discovery['type_metadata'] = json.loads(discovery['type_metadata'])
                except (json.JSONDecodeError, TypeError):
                    pass
            return discovery

        data = load_data_json()
        discoveries = data.get('discoveries', [])

        if discovery_id < 1 or discovery_id > len(discoveries):
            raise HTTPException(status_code=404, detail='Discovery not found')

        return discoveries[discovery_id - 1]
    except HTTPException:
        raise
    except IndexError:
        raise HTTPException(status_code=404, detail='Discovery not found')
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()


@app.post('/api/discoveries/{discovery_id}/feature')
async def toggle_discovery_featured(discovery_id: int, request: Request):
    """
    Toggle the featured status of a discovery.

    Requires admin or partner session.
    """
    conn = None
    try:
        # Check for admin/partner session
        session = get_session_from_request(request)
        if not session:
            raise HTTPException(status_code=401, detail="Authentication required")

        # Only admins and partners can feature discoveries
        if session.get('role') not in ['super_admin', 'partner', 'sub_admin']:
            raise HTTPException(status_code=403, detail="Not authorized to feature discoveries")

        db_path = get_db_path()
        if not db_path.exists():
            raise HTTPException(status_code=404, detail="Database not found")

        conn = get_db_connection()
        cursor = conn.cursor()

        # Get current featured status
        cursor.execute("SELECT is_featured FROM discoveries WHERE id = ?", (discovery_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Discovery not found")

        # Toggle the status
        current_featured = row[0] or 0
        new_featured = 0 if current_featured else 1

        cursor.execute(
            "UPDATE discoveries SET is_featured = ? WHERE id = ?",
            (new_featured, discovery_id)
        )
        conn.commit()

        # Log the action
        action = 'featured' if new_featured else 'unfeatured'
        add_activity_log(
            'discovery_featured',
            f"Discovery #{discovery_id} {action}",
            user_name=session.get('username', 'Unknown')
        )

        return {'success': True, 'is_featured': bool(new_featured)}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error toggling discovery featured status: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()


@app.post('/api/discoveries/{discovery_id}/view')
async def increment_discovery_view(discovery_id: int):
    """
    Increment the view count for a discovery.

    Called when a user opens the discovery detail modal.
    """
    conn = None
    try:
        db_path = get_db_path()
        if not db_path.exists():
            return {'success': False}

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            "UPDATE discoveries SET view_count = COALESCE(view_count, 0) + 1 WHERE id = ?",
            (discovery_id,)
        )
        conn.commit()

        return {'success': True}

    except Exception as e:
        logger.error(f"Error incrementing discovery view count: {e}")
        return {'success': False}
    finally:
        if conn:
            conn.close()


# =============================================================================
# DISCOVERY APPROVAL WORKFLOW - Submit, Pending List, Approve, Reject
# =============================================================================

@app.post('/api/submit_discovery')
async def submit_discovery(payload: dict, request: Request, session: Optional[str] = Cookie(None)):
    """
    Submit a discovery for approval. Goes to pending_discoveries queue.
    No auth required (rate-limited), but accepts session for logged-in users.
    """
    # Rate limit by IP
    client_ip = request.client.host if request.client else 'unknown'
    is_allowed, remaining = check_rate_limit(client_ip, 60, 1)
    if not is_allowed:
        raise HTTPException(status_code=429, detail='Rate limit exceeded. Please try again later.')

    # Validate required fields
    discovery_name = (payload.get('discovery_name') or '').strip()
    if not discovery_name:
        raise HTTPException(status_code=400, detail='Discovery name is required')

    system_id = payload.get('system_id')
    if not system_id:
        raise HTTPException(status_code=400, detail='System is required. Please select or create a system.')

    discord_username = (payload.get('discord_username') or '').strip()
    if not discord_username:
        raise HTTPException(status_code=400, detail='Discord username is required')

    discord_tag = payload.get('discord_tag')
    if not discord_tag:
        raise HTTPException(status_code=400, detail='Community (discord tag) is required')

    # Compute type slug
    discovery_type = payload.get('discovery_type') or 'Unknown'
    type_slug = get_discovery_type_slug(discovery_type)

    # Serialize type_metadata
    type_metadata_raw = payload.get('type_metadata')
    if type_metadata_raw and isinstance(type_metadata_raw, dict):
        payload['type_metadata'] = type_metadata_raw  # Keep as dict in JSON blob

    # Check session for submitter info
    session_data = get_session(session)
    submitter_account_id = None
    submitter_account_type = None
    if session_data:
        user_type = session_data.get('user_type')
        if user_type == 'partner':
            submitter_account_id = session_data.get('partner_id')
            submitter_account_type = 'partner'
        elif user_type == 'sub_admin':
            submitter_account_id = session_data.get('sub_admin_id')
            submitter_account_type = 'sub_admin'

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Denormalize system_name, planet_name, moon_name for display
        system_name = None
        cursor.execute('SELECT name FROM systems WHERE id = ?', (str(system_id),))
        sys_row = cursor.fetchone()
        if sys_row:
            system_name = sys_row['name']

        planet_name = None
        if payload.get('planet_id'):
            cursor.execute('SELECT name FROM planets WHERE id = ?', (payload['planet_id'],))
            p_row = cursor.fetchone()
            if p_row:
                planet_name = p_row['name']

        moon_name = None
        if payload.get('moon_id'):
            cursor.execute('SELECT name FROM moons WHERE id = ?', (payload['moon_id'],))
            m_row = cursor.fetchone()
            if m_row:
                moon_name = m_row['name']

        # Store entire payload as JSON
        discovery_data = json.dumps(payload)

        cursor.execute('''
            INSERT INTO pending_discoveries (
                discovery_data, discovery_name, discovery_type, type_slug,
                system_id, system_name, planet_name, moon_name, location_type,
                discord_tag, submitted_by, submitted_by_ip,
                submitter_account_id, submitter_account_type,
                submission_date, photo_url, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending')
        ''', (
            discovery_data,
            discovery_name,
            discovery_type,
            type_slug,
            str(system_id),
            system_name,
            planet_name,
            moon_name,
            payload.get('location_type') or 'space',
            discord_tag,
            discord_username,
            client_ip,
            submitter_account_id,
            submitter_account_type,
            datetime.now(timezone.utc).isoformat(),
            payload.get('photo_url'),
        ))
        conn.commit()
        submission_id = cursor.lastrowid

        logger.info(f"Discovery '{discovery_name}' submitted for approval (ID: {submission_id})")
        add_activity_log(
            'discovery_submitted',
            f"Discovery '{discovery_name}' submitted for approval",
            details=f"Type: {discovery_type}, Community: {discord_tag}",
            user_name=discord_username
        )

        return JSONResponse({
            'status': 'pending',
            'message': 'Discovery submitted for approval!',
            'submission_id': submission_id
        }, status_code=201)

    except Exception as e:
        logger.error(f"Error submitting discovery: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()


@app.get('/api/pending_discoveries')
async def get_pending_discoveries(session: Optional[str] = Cookie(None)):
    """
    Get pending discovery submissions for approval.
    Scoped by discord_tag like pending_systems:
    - Super admin: sees ALL
    - Haven sub-admins: sees Haven + additional_discord_tags (+ personal if permitted)
    - Partners/sub-admins: sees only their discord_tag
    Self-submissions are filtered out for non-super-admins.
    """
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail="Admin authentication required")

    is_super = session_data.get('user_type') == 'super_admin'
    is_haven_sub_admin = session_data.get('is_haven_sub_admin', False)
    partner_tag = session_data.get('discord_tag')

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        select_cols = '''
            id, discovery_name, discovery_type, type_slug,
            system_name, planet_name, moon_name, location_type,
            discord_tag, submitted_by, submission_date, photo_url,
            status, reviewed_by, review_date, rejection_reason,
            submitter_account_id, submitter_account_type
        '''

        if is_super:
            cursor.execute(f'''
                SELECT {select_cols} FROM pending_discoveries
                ORDER BY
                    CASE status WHEN 'pending' THEN 1 WHEN 'approved' THEN 2 WHEN 'rejected' THEN 3 END,
                    submission_date DESC
            ''')
        elif is_haven_sub_admin:
            additional_tags = session_data.get('additional_discord_tags', [])
            can_approve_personal = session_data.get('can_approve_personal_uploads', False)
            all_tags = ['Haven'] + additional_tags
            placeholders = ','.join(['?' for _ in all_tags])

            if can_approve_personal:
                cursor.execute(f'''
                    SELECT {select_cols} FROM pending_discoveries
                    WHERE discord_tag IN ({placeholders}) OR discord_tag = 'personal'
                    ORDER BY
                        CASE status WHEN 'pending' THEN 1 WHEN 'approved' THEN 2 WHEN 'rejected' THEN 3 END,
                        submission_date DESC
                ''', all_tags)
            else:
                cursor.execute(f'''
                    SELECT {select_cols} FROM pending_discoveries
                    WHERE discord_tag IN ({placeholders})
                    ORDER BY
                        CASE status WHEN 'pending' THEN 1 WHEN 'approved' THEN 2 WHEN 'rejected' THEN 3 END,
                        submission_date DESC
                ''', all_tags)
        else:
            cursor.execute(f'''
                SELECT {select_cols} FROM pending_discoveries
                WHERE discord_tag = ?
                ORDER BY
                    CASE status WHEN 'pending' THEN 1 WHEN 'approved' THEN 2 WHEN 'rejected' THEN 3 END,
                    submission_date DESC
            ''', (partner_tag,))

        submissions = [dict(row) for row in cursor.fetchall()]

        # Filter out self-submissions for non-super-admins
        if not is_super:
            logged_in_username = normalize_discord_username(session_data.get('username', ''))
            logged_in_account_id = session_data.get('sub_admin_id') or session_data.get('partner_id')
            logged_in_account_type = session_data.get('user_type')

            def is_self_submission(sub):
                if sub.get('submitter_account_id') and sub.get('submitter_account_type'):
                    if (sub['submitter_account_id'] == logged_in_account_id and
                        sub['submitter_account_type'] == logged_in_account_type):
                        return True
                if sub.get('submitted_by') and normalize_discord_username(sub['submitted_by']) == logged_in_username:
                    return True
                return False

            submissions = [s for s in submissions if not is_self_submission(s)]

        # Add type info
        for sub in submissions:
            slug = sub.get('type_slug') or get_discovery_type_slug(sub.get('discovery_type', ''))
            sub['type_info'] = DISCOVERY_TYPE_INFO.get(slug, DISCOVERY_TYPE_INFO['other'])

        return {'submissions': submissions}

    except Exception as e:
        logger.error(f"Error getting pending discoveries: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()


@app.get('/api/pending_discoveries/{submission_id}')
async def get_pending_discovery_detail(submission_id: int, session: Optional[str] = Cookie(None)):
    """Get full details of a pending discovery submission."""
    if not verify_session(session):
        raise HTTPException(status_code=401, detail="Admin authentication required")

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM pending_discoveries WHERE id = ?', (submission_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Submission not found")

        submission = dict(row)
        if submission.get('discovery_data'):
            try:
                submission['discovery_data'] = json.loads(submission['discovery_data'])
            except (json.JSONDecodeError, TypeError):
                pass

        return submission

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting pending discovery detail: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()


@app.post('/api/approve_discovery/{submission_id}')
async def approve_discovery(submission_id: int, session: Optional[str] = Cookie(None)):
    """
    Approve a pending discovery submission.
    Self-approval blocking applies (same rules as systems).
    """
    if not verify_session(session):
        raise HTTPException(status_code=401, detail="Admin authentication required")

    session_data = get_session(session)
    current_user_type = session_data.get('user_type')
    current_username = session_data.get('username')
    current_account_id = None
    if current_user_type == 'partner':
        current_account_id = session_data.get('partner_id')
    elif current_user_type == 'sub_admin':
        current_account_id = session_data.get('sub_admin_id')

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM pending_discoveries WHERE id = ?', (submission_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Submission not found")

        submission = dict(row)

        if submission['status'] != 'pending':
            raise HTTPException(status_code=400, detail=f"Submission already {submission['status']}")

        # Self-approval blocking for non-super-admins
        if current_user_type != 'super_admin':
            submitter_account_id = submission.get('submitter_account_id')
            submitter_account_type = submission.get('submitter_account_type')
            submitted_by = submission.get('submitted_by')

            normalized_current = normalize_discord_username(current_username)
            is_self = False

            if submitter_account_id is not None and submitter_account_type:
                if current_user_type == submitter_account_type and current_account_id == submitter_account_id:
                    is_self = True
            elif submitted_by and normalized_current and normalize_discord_username(submitted_by) == normalized_current:
                is_self = True

            if is_self:
                raise HTTPException(
                    status_code=403,
                    detail="You cannot approve your own submission. Another admin must review it."
                )

        # Parse discovery data and insert into discoveries table
        discovery_data = {}
        if submission.get('discovery_data'):
            try:
                discovery_data = json.loads(submission['discovery_data'])
            except (json.JSONDecodeError, TypeError):
                discovery_data = {}

        discovery_type = discovery_data.get('discovery_type') or submission.get('discovery_type') or 'Unknown'
        type_slug = get_discovery_type_slug(discovery_type)
        discovery_name = discovery_data.get('discovery_name') or submission.get('discovery_name') or 'Unnamed Discovery'

        # Serialize type_metadata
        type_metadata_raw = discovery_data.get('type_metadata')
        type_metadata_json = json.dumps(type_metadata_raw) if type_metadata_raw and isinstance(type_metadata_raw, dict) else None

        cursor.execute('''
            INSERT INTO discoveries (
                discovery_type, discovery_name, system_id, planet_id, moon_id,
                location_type, location_name, description, significance,
                discovered_by, submission_timestamp,
                mystery_tier, analysis_status, pattern_matches,
                discord_user_id, discord_guild_id,
                photo_url, evidence_url, type_slug, discord_tag, type_metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            discovery_type,
            discovery_name,
            discovery_data.get('system_id'),
            discovery_data.get('planet_id'),
            discovery_data.get('moon_id'),
            discovery_data.get('location_type') or 'space',
            discovery_data.get('location_name') or '',
            discovery_data.get('description') or '',
            discovery_data.get('significance') or 'Notable',
            discovery_data.get('discord_username') or submission.get('submitted_by') or 'anonymous',
            submission.get('submission_date') or datetime.now(timezone.utc).isoformat(),
            discovery_data.get('mystery_tier') or 1,
            'approved',
            0,
            discovery_data.get('discord_user_id'),
            discovery_data.get('discord_guild_id'),
            discovery_data.get('photo_url') or submission.get('photo_url'),
            discovery_data.get('evidence_urls'),
            type_slug,
            discovery_data.get('discord_tag') or submission.get('discord_tag'),
            type_metadata_json,
        ))
        discovery_id = cursor.lastrowid

        # Update pending status
        cursor.execute('''
            UPDATE pending_discoveries
            SET status = 'approved', reviewed_by = ?, review_date = ?
            WHERE id = ?
        ''', (current_username, datetime.now(timezone.utc).isoformat(), submission_id))

        # Audit log
        cursor.execute('''
            INSERT INTO approval_audit_log
            (timestamp, action, submission_type, submission_id, submission_name,
             approver_username, approver_type, approver_account_id, approver_discord_tag,
             submitter_username, submitter_account_id, submitter_type, submission_discord_tag)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            datetime.now(timezone.utc).isoformat(),
            'approved',
            'discovery',
            submission_id,
            discovery_name,
            current_username,
            current_user_type,
            current_account_id,
            session_data.get('discord_tag'),
            submission.get('submitted_by'),
            submission.get('submitter_account_id'),
            submission.get('submitter_account_type'),
            submission.get('discord_tag'),
        ))

        conn.commit()

        add_activity_log(
            'discovery_approved',
            f"Discovery '{discovery_name}' approved",
            details=f"Type: {discovery_type}",
            user_name=current_username
        )

        logger.info(f"Discovery '{discovery_name}' approved (pending_id: {submission_id}, discovery_id: {discovery_id})")
        return {'status': 'ok', 'discovery_id': discovery_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error approving discovery: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()


@app.post('/api/reject_discovery/{submission_id}')
async def reject_discovery(submission_id: int, payload: dict, session: Optional[str] = Cookie(None)):
    """
    Reject a pending discovery submission.
    Self-rejection blocking applies (same rules as systems).
    """
    if not verify_session(session):
        raise HTTPException(status_code=401, detail="Admin authentication required")

    session_data = get_session(session)
    current_user_type = session_data.get('user_type')
    current_username = session_data.get('username')
    current_account_id = None
    if current_user_type == 'partner':
        current_account_id = session_data.get('partner_id')
    elif current_user_type == 'sub_admin':
        current_account_id = session_data.get('sub_admin_id')

    reason = payload.get('reason', 'No reason provided')

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM pending_discoveries WHERE id = ?', (submission_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Submission not found")

        submission = dict(row)

        if submission['status'] != 'pending':
            raise HTTPException(status_code=400, detail=f"Submission already {submission['status']}")

        # Self-rejection blocking for non-super-admins
        if current_user_type != 'super_admin':
            submitter_account_id = submission.get('submitter_account_id')
            submitter_account_type = submission.get('submitter_account_type')
            submitted_by = submission.get('submitted_by')

            normalized_current = normalize_discord_username(current_username)
            is_self = False

            if submitter_account_id is not None and submitter_account_type:
                if current_user_type == submitter_account_type and current_account_id == submitter_account_id:
                    is_self = True
            elif submitted_by and normalized_current and normalize_discord_username(submitted_by) == normalized_current:
                is_self = True

            if is_self:
                raise HTTPException(
                    status_code=403,
                    detail="You cannot reject your own submission."
                )

        # Update status
        cursor.execute('''
            UPDATE pending_discoveries
            SET status = 'rejected', reviewed_by = ?, review_date = ?, rejection_reason = ?
            WHERE id = ?
        ''', (current_username, datetime.now(timezone.utc).isoformat(), reason, submission_id))

        # Audit log
        discovery_name = submission.get('discovery_name', 'Unknown')
        cursor.execute('''
            INSERT INTO approval_audit_log
            (timestamp, action, submission_type, submission_id, submission_name,
             approver_username, approver_type, approver_account_id, approver_discord_tag,
             submitter_username, submitter_account_id, submitter_type, notes, submission_discord_tag)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            datetime.now(timezone.utc).isoformat(),
            'rejected',
            'discovery',
            submission_id,
            discovery_name,
            current_username,
            current_user_type,
            current_account_id,
            session_data.get('discord_tag'),
            submission.get('submitted_by'),
            submission.get('submitter_account_id'),
            submission.get('submitter_account_type'),
            reason,
            submission.get('discord_tag'),
        ))

        conn.commit()

        add_activity_log(
            'discovery_rejected',
            f"Discovery '{discovery_name}' rejected",
            details=f"Reason: {reason}",
            user_name=current_username
        )

        logger.info(f"Discovery '{discovery_name}' rejected (ID: {submission_id})")
        return {'status': 'ok', 'message': 'Discovery submission rejected'}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error rejecting discovery: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()


# Simple WebSocket endpoints for logs and RT-AI
@app.websocket('/ws/logs')
async def ws_logs(ws: WebSocket):
    await ws.accept()
    logpath = LOGS_DIR / 'control-room-web.log'
    try:
        while True:
            await asyncio.sleep(1.0)
            if logpath.exists():
                data = logpath.read_text(encoding='utf-8', errors='ignore')
            else:
                data = ''
            # Check if connection is still open before sending
            try:
                await ws.send_text(data[-1000:])
            except Exception:
                # Connection closed, exit gracefully
                break
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f'WebSocket /ws/logs error: {e}')
    finally:
        try:
            await ws.close()
        except:
            pass

@app.websocket('/ws/rtai')
async def ws_rtai(ws: WebSocket):
    await ws.accept()
    if not HAVE_RTAI or rtai_instance is None:
        await ws.send_text('RT-AI not available')
        await ws.close()
        return
    await ws.send_text('RT-AI connected')
    try:
        while True:
            await asyncio.sleep(3)
            await ws.send_text('RT-AI heartbeat')
    except WebSocketDisconnect:
        pass

# Allow external init of the RT-AI from other modules
def init_rtai(haven_ui_path: str):
    global rtai_instance
    if not HAVE_RTAI:
        logger.info('Roundtable AI not installed - skipping init')
        return None
    haven_ui_root = Path(haven_ui_path)
    rtai_instance = get_round_table_ai(haven_ui_root)
    return rtai_instance


# ============================================================================
# SYSTEM APPROVALS QUEUE - API Endpoints
# ============================================================================

def validate_system_data(system: dict) -> tuple[bool, str]:
    """Validate system data before accepting submission. Returns (is_valid, error_message)."""
    # Required fields
    if not system.get('name') or not isinstance(system['name'], str) or not system['name'].strip():
        return False, "System name is required"

    # Name length
    if len(system['name']) > 100:
        return False, "System name must be 100 characters or less"

    # Sanitize and validate planets
    if 'planets' in system and system['planets']:
        if not isinstance(system['planets'], list):
            return False, "Planets must be a list"

        for i, planet in enumerate(system['planets']):
            if not isinstance(planet, dict):
                return False, f"Planet {i} is invalid"
            if not planet.get('name') or not planet['name'].strip():
                return False, f"Planet {i} is missing a name"

            # Validate moons if present
            if 'moons' in planet and planet['moons']:
                if not isinstance(planet['moons'], list):
                    return False, f"Planet {i} moons must be a list"
                for j, moon in enumerate(planet['moons']):
                    if not isinstance(moon, dict):
                        return False, f"Planet {i} moon {j} is invalid"
                    if not moon.get('name') or not moon['name'].strip():
                        return False, f"Planet {i} moon {j} is missing a name"

    return True, ""


@app.post('/api/submit_system')
async def submit_system(
    payload: dict,
    request: Request,
    session: Optional[str] = Cookie(None),
    x_api_key: Optional[str] = Header(None, alias='X-API-Key')
):
    """
    Submit a system for approval.
    Accepts system data and queues it for admin review.

    Authentication:
    - Admin session: Exempt from rate limiting
    - API key: Uses API key's rate limit (default 200/hour)
    - None: IP-based rate limiting (15/hour)

    New fields supported (for NMS Save Watcher companion app):
    - star_type: Yellow, Red, Green, Blue, Purple
    - economy_type: Trading, Mining, Technology, etc.
    - economy_level: Low, Medium, High
    - conflict_level: Low, Medium, High
    - discovered_by: Original discoverer username
    - discovered_at: ISO timestamp of discovery
    """
    # Get client IP for logging
    client_ip = request.client.host if request.client else "unknown"

    # Check authentication method
    is_admin = verify_session(session)
    api_key_info = verify_api_key(x_api_key) if x_api_key else None

    # Determine source for tracking
    if api_key_info:
        source = 'companion_app'
        api_key_name = api_key_info['name']
    elif is_admin:
        source = 'manual'
        api_key_name = None
    else:
        source = 'manual'
        api_key_name = None

    # Apply rate limiting based on auth method
    if is_admin:
        # Admin is exempt from rate limiting
        pass
    elif api_key_info:
        # Check API key rate limit
        rate_limit = api_key_info.get('rate_limit', 200)
        is_allowed, remaining = check_api_key_rate_limit(api_key_info['id'], rate_limit)
        if not is_allowed:
            logger.info(f"API key rate limit exceeded for {api_key_info['name']}")
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded. Maximum {rate_limit} submissions per hour for this API key.",
                headers={"Retry-After": "3600"}
            )
    else:
        # IP-based rate limiting for anonymous users
        is_allowed, remaining = check_rate_limit(client_ip)
        if not is_allowed:
            logger.info(f"Rate limit exceeded for IP {client_ip}")
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded. Maximum 60 submissions per hour. Please try again later.",
                headers={"Retry-After": "3600"}
            )

    # Validate system data
    is_valid, error_msg = validate_system_data(payload)
    if not is_valid:
        raise HTTPException(status_code=400, detail=error_msg)

    # Classify system (phantom star and core void detection)
    # Note: We no longer block submissions - just classify and warn
    x = payload.get('x')
    y = payload.get('y')
    z = payload.get('z')
    solar_system = payload.get('glyph_solar_system', 1)

    classification_info = None
    warnings = []

    if x is not None and y is not None and z is not None:
        classification_info = get_system_classification(x, y, z, solar_system)

        # Add classification flags to payload for storage
        payload['is_phantom'] = classification_info['is_phantom']
        payload['is_in_core'] = classification_info['is_in_core']
        payload['classification'] = classification_info['classification']

        # Build warning messages
        if classification_info['is_phantom']:
            warnings.append(
                f"PHANTOM STAR: SSS index {solar_system} (0x{solar_system:03X}) indicates a phantom star. "
                f"These systems are not normally accessible via the Galactic Map."
            )

        if classification_info['is_in_core']:
            warnings.append(
                f"CORE VOID: Coordinates ({x}, {y}, {z}) are within the galactic core void "
                f"(~3,000 light years from center)."
            )

        if warnings:
            logger.info(f"System submission with special classification: {classification_info['classification']} - {'; '.join(warnings)}")

    # Extract metadata for indexing
    system_name = payload.get('name', 'Unnamed System')
    system_galaxy = payload.get('galaxy', 'Euclid')
    submitted_by = payload.get('submitted_by', 'Anonymous')
    system_id = payload.get('id')

    # Log whether this is an edit or new submission
    if system_id:
        logger.info(f"System submission is an EDIT of existing system ID: {system_id}")
    else:
        logger.info(f"System submission is a NEW system: {system_name}")

    # Store in pending_systems table
    conn = None
    try:
        db_path = get_db_path()
        # Use standardized connection settings with WAL mode
        conn = get_db_connection()
        cursor = conn.cursor()

        # Check for duplicate submissions (same name, pending status)
        cursor.execute(
            'SELECT id FROM pending_systems WHERE system_name = ? AND status = ?',
            (system_name, 'pending')
        )
        existing = cursor.fetchone()
        if existing:
            raise HTTPException(
                status_code=409,
                detail=f"A pending submission for system '{system_name}' already exists"
            )

        # Check if a system with matching glyph coordinates already exists
        # Match on last 11 characters of glyph (ignoring planet index) + galaxy + reality
        # This ensures we detect the same system even if the portal destination differs
        glyph_code = payload.get('glyph_code')
        system_reality = payload.get('reality', 'Normal')
        existing_glyph_system = None
        if glyph_code:
            existing_glyph_row = find_matching_system(cursor, glyph_code, system_galaxy, system_reality)
            if existing_glyph_row:
                existing_glyph_system = {'id': existing_glyph_row[0], 'name': existing_glyph_row[1]}
                # Check if names match - warn appropriately
                if existing_glyph_row[1] and existing_glyph_row[1].strip() != system_name.strip():
                    warnings.append(
                        f"EXISTING SYSTEM: This appears to update existing system '{existing_glyph_row[1]}' "
                        f"(same glyph coordinates in {system_galaxy}/{system_reality}). "
                        f"However, the submitted name '{system_name}' differs. Please verify before approving."
                    )
                else:
                    warnings.append(
                        f"EXISTING SYSTEM: This appears to update existing system '{existing_glyph_row[1]}' "
                        f"(same glyph coordinates in {system_galaxy}/{system_reality}). "
                        f"Approving this submission will UPDATE the existing system."
                    )
                logger.info(f"Submission for '{system_name}' has glyph matching existing system '{existing_glyph_row[1]}' (ID: {existing_glyph_row[0]}) via last-11 + galaxy + reality")

        # Extract discord_tag for filtering (partners only see their tagged submissions)
        # Priority: 1) Payload, 2) API key, 3) Logged-in user's session
        discord_tag = payload.get('discord_tag')
        if api_key_info and api_key_info.get('discord_tag') and not discord_tag:
            discord_tag = api_key_info['discord_tag']
            logger.info(f"Auto-tagging submission with API key's discord_tag: {discord_tag}")

        # Get submitter identity early so we can use their discord_tag for auto-tagging
        submitter_identity = get_submitter_identity(session)

        # If still no discord_tag, check if the logged-in user (partner or sub-admin) has one
        if not discord_tag and submitter_identity.get('discord_tag'):
            discord_tag = submitter_identity['discord_tag']
            logger.info(f"Auto-tagging submission with logged-in user's discord_tag: {discord_tag}")
        # Extract personal discord username for non-community submissions
        personal_discord_username = payload.get('personal_discord_username')

        # Determine if this is an edit (system has ID) or new submission
        # Also check if glyph_code matches an existing system
        edit_system_id = system_id  # From payload.get('id') above
        if not edit_system_id and existing_glyph_system:
            # Glyph code matches existing system - treat as edit
            edit_system_id = existing_glyph_system['id']

        # Insert submission with source tracking, discord_tag, personal_discord_username, edit tracking, and submitter identity
        cursor.execute('''
            INSERT INTO pending_systems
            (submitted_by, submitted_by_ip, submission_date, system_data, status, system_name, system_region, source, api_key_name, discord_tag, personal_discord_username, edit_system_id, submitter_account_id, submitter_account_type)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            submitter_identity['username'] if submitter_identity['username'] else submitted_by,
            client_ip,
            datetime.now(timezone.utc).isoformat(),
            json.dumps(payload),
            'pending',
            system_name,
            system_galaxy,
            source,
            api_key_name,
            discord_tag,
            personal_discord_username,
            edit_system_id,
            submitter_identity['account_id'],
            submitter_identity['type'] if submitter_identity['type'] != 'anonymous' else None
        ))

        submission_id = cursor.lastrowid
        conn.commit()

        source_info = f" via {api_key_name}" if api_key_name else ""
        logger.info(f"New system submission: '{system_name}' (ID: {submission_id}) from {client_ip}{source_info}")

        # Add activity log - differentiate watcher uploads from manual submissions
        if source == 'companion_app':
            add_activity_log(
                'watcher_upload',
                f"System '{system_name}' uploaded via NMS Save Watcher",
                details=f"Galaxy: {system_galaxy}" + (f", API Key: {api_key_name}" if api_key_name else ""),
                user_name=submitted_by
            )
        else:
            add_activity_log(
                'system_submitted',
                f"System '{system_name}' submitted for approval",
                details=f"Galaxy: {system_galaxy}",
                user_name=submitted_by
            )

        response = {
            'status': 'ok',
            'message': 'System submitted for approval',
            'submission_id': submission_id,
            'system_name': system_name
        }

        # Add classification info to response if available
        if classification_info:
            response['classification'] = classification_info['classification']
            response['is_phantom'] = classification_info['is_phantom']
            response['is_in_core'] = classification_info['is_in_core']

        # Add warnings if any
        if warnings:
            response['warnings'] = warnings

        # Add existing system info if this will be an edit
        if existing_glyph_system:
            response['existing_system'] = existing_glyph_system
            response['message'] = f"System submitted for approval (will update existing system: '{existing_glyph_system['name']}')"

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error saving submission: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save submission: {str(e)}")
    finally:
        if conn:
            conn.close()


@app.get('/api/pending_systems')
async def get_pending_systems(session: Optional[str] = Cookie(None)):
    """
    Get pending system submissions (admin only).
    - Super admin: sees ALL submissions
    - Haven sub-admins: sees ALL submissions (they work for Haven)
    - Partners/partner sub-admins: see only submissions tagged with their discord_tag
    """
    # Verify admin session and get session data
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail="Admin authentication required")

    is_super = session_data.get('user_type') == 'super_admin'
    is_haven_sub_admin = session_data.get('is_haven_sub_admin', False)
    partner_tag = session_data.get('discord_tag')

    conn = None
    try:
        db_path = get_db_path()
        conn = get_db_connection()
        cursor = conn.cursor()

        if is_super:
            # Super admin sees ALL submissions
            cursor.execute('''
                SELECT id, submitted_by, submission_date, status, system_name, system_region,
                       reviewed_by, review_date, rejection_reason, source, api_key_name, discord_tag,
                       personal_discord_username, edit_system_id, submitter_account_id, submitter_account_type
                FROM pending_systems
                ORDER BY
                    CASE status
                        WHEN 'pending' THEN 1
                        WHEN 'approved' THEN 2
                        WHEN 'rejected' THEN 3
                    END,
                    submission_date DESC
            ''')
        elif is_haven_sub_admin:
            # Haven sub-admins see submissions tagged with "Haven" + any additional discord tags
            additional_tags = session_data.get('additional_discord_tags', [])
            can_approve_personal = session_data.get('can_approve_personal_uploads', False)
            all_tags = ['Haven'] + additional_tags

            # Build dynamic query with placeholders
            placeholders = ','.join(['?' for _ in all_tags])

            # If can_approve_personal_uploads, also include submissions with discord_tag = 'personal' (personal uploads)
            if can_approve_personal:
                cursor.execute(f'''
                    SELECT id, submitted_by, submission_date, status, system_name, system_region,
                           reviewed_by, review_date, rejection_reason, source, api_key_name, discord_tag,
                           personal_discord_username, edit_system_id, submitter_account_id, submitter_account_type
                    FROM pending_systems
                    WHERE discord_tag IN ({placeholders})
                       OR discord_tag = 'personal'
                    ORDER BY
                        CASE status
                            WHEN 'pending' THEN 1
                            WHEN 'approved' THEN 2
                            WHEN 'rejected' THEN 3
                        END,
                        submission_date DESC
                ''', all_tags)
            else:
                cursor.execute(f'''
                    SELECT id, submitted_by, submission_date, status, system_name, system_region,
                           reviewed_by, review_date, rejection_reason, source, api_key_name, discord_tag,
                           personal_discord_username, edit_system_id, submitter_account_id, submitter_account_type
                    FROM pending_systems
                    WHERE discord_tag IN ({placeholders})
                    ORDER BY
                        CASE status
                            WHEN 'pending' THEN 1
                            WHEN 'approved' THEN 2
                            WHEN 'rejected' THEN 3
                        END,
                        submission_date DESC
                ''', all_tags)
        else:
            # Partners and partner sub-admins only see submissions tagged with their discord_tag
            cursor.execute('''
                SELECT id, submitted_by, submission_date, status, system_name, system_region,
                       reviewed_by, review_date, rejection_reason, source, api_key_name, discord_tag,
                       personal_discord_username, edit_system_id, submitter_account_id, submitter_account_type
                FROM pending_systems
                WHERE discord_tag = ?
                ORDER BY
                    CASE status
                        WHEN 'pending' THEN 1
                        WHEN 'approved' THEN 2
                        WHEN 'rejected' THEN 3
                    END,
                    submission_date DESC
            ''', (partner_tag,))

        rows = cursor.fetchall()
        submissions = [dict(row) for row in rows]

        # For non-super-admins, filter out self-submissions (users cannot approve their own)
        if not is_super:
            logged_in_username = normalize_discord_username(session_data.get('username', ''))
            logged_in_account_id = session_data.get('sub_admin_id') or session_data.get('partner_id')
            logged_in_account_type = session_data.get('user_type')

            def is_self_submission(sub):
                # Check by account ID first (most reliable)
                if sub.get('submitter_account_id') and sub.get('submitter_account_type'):
                    if (sub['submitter_account_id'] == logged_in_account_id and
                        sub['submitter_account_type'] == logged_in_account_type):
                        return True
                # Check by username against submitted_by (normalize to handle #XXXX discriminator)
                if sub.get('submitted_by') and normalize_discord_username(sub['submitted_by']) == logged_in_username:
                    return True
                # Check by username against personal_discord_username (normalize to handle #XXXX discriminator)
                if sub.get('personal_discord_username') and normalize_discord_username(sub['personal_discord_username']) == logged_in_username:
                    return True
                return False

            submissions = [s for s in submissions if not is_self_submission(s)]

        # Hide personal_discord_username for Haven sub-admins (only super admin sees contact info)
        # But keep discord_tag so frontend can distinguish personal uploads from Haven submissions
        if is_haven_sub_admin:
            for submission in submissions:
                submission['personal_discord_username'] = None

        return {'submissions': submissions}

    except Exception as e:
        logger.error(f"Error fetching pending systems: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch submissions: {str(e)}")
    finally:
        if conn:
            conn.close()


@app.get('/api/pending_systems/count')
async def get_pending_count(session: Optional[str] = Cookie(None)):
    """
    Get count of pending submissions for badge display.
    - Super admin: sees count of ALL pending
    - Haven sub-admins: sees count of "Haven" tagged submissions (minus self-submissions)
    - Partners/partner sub-admins: sees count of only their discord_tag submissions (minus self-submissions)
    - Not logged in: sees count of ALL pending
    Must be defined BEFORE /api/pending_systems/{submission_id} to avoid route conflict.
    """
    # Get session data if available (for partner filtering)
    session_data = get_session(session) if session else None
    is_super = session_data and session_data.get('user_type') == 'super_admin'
    is_haven_sub_admin = session_data.get('is_haven_sub_admin', False) if session_data else False
    partner_tag = session_data.get('discord_tag') if session_data else None

    conn = None
    try:
        db_path = get_db_path()
        conn = get_db_connection()
        cursor = conn.cursor()

        # For non-super-admins, we need to fetch rows and filter out self-submissions
        if is_super or not session_data:
            # Super admin or not logged in sees all - simple count
            cursor.execute("SELECT COUNT(*) FROM pending_systems WHERE status = 'pending'")
            system_count = cursor.fetchone()[0]
        else:
            # For sub-admins/partners, fetch rows to filter out self-submissions
            if is_haven_sub_admin:
                additional_tags = session_data.get('additional_discord_tags', []) if session_data else []
                can_approve_personal = session_data.get('can_approve_personal_uploads', False) if session_data else False
                all_tags = ['Haven'] + additional_tags
                placeholders = ','.join(['?' for _ in all_tags])

                if can_approve_personal:
                    cursor.execute(f"""
                        SELECT id, submitted_by, personal_discord_username, submitter_account_id, submitter_account_type
                        FROM pending_systems
                        WHERE status = 'pending' AND (discord_tag IN ({placeholders}) OR discord_tag = 'personal')
                    """, all_tags)
                else:
                    cursor.execute(f"""
                        SELECT id, submitted_by, personal_discord_username, submitter_account_id, submitter_account_type
                        FROM pending_systems
                        WHERE status = 'pending' AND discord_tag IN ({placeholders})
                    """, all_tags)
            elif partner_tag:
                cursor.execute("""
                    SELECT id, submitted_by, personal_discord_username, submitter_account_id, submitter_account_type
                    FROM pending_systems
                    WHERE status = 'pending' AND discord_tag = ?
                """, (partner_tag,))
            else:
                cursor.execute("SELECT id FROM pending_systems WHERE 1=0")  # No results

            rows = cursor.fetchall()

            # Filter out self-submissions (normalize usernames to handle #XXXX discriminator)
            logged_in_username = normalize_discord_username(session_data.get('username', ''))
            logged_in_account_id = session_data.get('sub_admin_id') or session_data.get('partner_id')
            logged_in_account_type = session_data.get('user_type')

            def is_self_submission(row):
                sub = dict(row)
                if sub.get('submitter_account_id') and sub.get('submitter_account_type'):
                    if (sub['submitter_account_id'] == logged_in_account_id and
                        sub['submitter_account_type'] == logged_in_account_type):
                        return True
                if sub.get('submitted_by') and normalize_discord_username(sub['submitted_by']) == logged_in_username:
                    return True
                if sub.get('personal_discord_username') and normalize_discord_username(sub['personal_discord_username']) == logged_in_username:
                    return True
                return False

            system_count = sum(1 for row in rows if not is_self_submission(row))

        # Count pending region names (these don't have discord_tag filtering yet)
        cursor.execute("SELECT COUNT(*) FROM pending_region_names WHERE status = 'pending'")
        region_count = cursor.fetchone()[0]

        # Return total count for badge display
        return {'count': system_count + region_count, 'systems': system_count, 'regions': region_count}

    except Exception as e:
        logger.error(f"Error getting pending count: {e}")
        return {'count': 0, 'systems': 0, 'regions': 0}
    finally:
        if conn:
            conn.close()


@app.get('/api/pending_systems/{submission_id}')
async def get_pending_system_details(submission_id: int, session: Optional[str] = Cookie(None)):
    """
    Get full details of a pending submission including system_data (admin only).
    """
    # Verify admin session
    if not verify_session(session):
        raise HTTPException(status_code=401, detail="Admin authentication required")

    # Check if Haven sub-admin (need to hide personal_discord_username)
    session_data = get_session(session)
    is_haven_sub_admin = session_data.get('is_haven_sub_admin', False) if session_data else False

    conn = None
    try:
        db_path = get_db_path()
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM pending_systems WHERE id = ?', (submission_id,))
        row = cursor.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Submission not found")

        submission = dict(row)
        # Parse JSON system_data
        if submission.get('system_data'):
            submission['system_data'] = json.loads(submission['system_data'])

        # Hide personal_discord_username for Haven sub-admins (only super admin sees contact info)
        if is_haven_sub_admin:
            submission['personal_discord_username'] = None

        return submission

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching submission details: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch submission: {str(e)}")
    finally:
        if conn:
            conn.close()


@app.post('/api/approve_system/{submission_id}')
async def approve_system(submission_id: int, session: Optional[str] = Cookie(None)):
    """
    Approve a pending system submission and add it to the main database (admin only).
    Self-approval is blocked for non-super-admin users.
    """
    # Verify admin session
    if not verify_session(session):
        raise HTTPException(status_code=401, detail="Admin authentication required")

    # Get current user identity for self-approval check and audit
    session_data = get_session(session)
    current_user_type = session_data.get('user_type')
    current_username = session_data.get('username')
    current_account_id = None
    if current_user_type == 'partner':
        current_account_id = session_data.get('partner_id')
    elif current_user_type == 'sub_admin':
        current_account_id = session_data.get('sub_admin_id')

    conn = None
    try:
        db_path = get_db_path()
        conn = get_db_connection()
        cursor = conn.cursor()

        # Get submission
        cursor.execute('SELECT * FROM pending_systems WHERE id = ?', (submission_id,))
        row = cursor.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Submission not found")

        submission = dict(row)

        if submission['status'] != 'pending':
            raise HTTPException(
                status_code=400,
                detail=f"Submission already {submission['status']}"
            )

        # SELF-APPROVAL BLOCKING
        # Super admin can approve anything (trusted role)
        # Partners and sub-admins cannot approve their own submissions
        if current_user_type != 'super_admin':
            submitter_account_id = submission.get('submitter_account_id')
            submitter_account_type = submission.get('submitter_account_type')
            submitted_by = submission.get('submitted_by')
            personal_discord_username = submission.get('personal_discord_username')
            # Normalize usernames to handle Discord #XXXX discriminator
            normalized_current = normalize_discord_username(current_username)

            is_self_submission = False

            # Match by account ID if available (most reliable)
            if submitter_account_id is not None and submitter_account_type:
                if current_user_type == submitter_account_type and current_account_id == submitter_account_id:
                    is_self_submission = True
            # Fallback: match by username (for legacy submissions without account tracking)
            elif submitted_by and normalized_current and normalize_discord_username(submitted_by) == normalized_current:
                is_self_submission = True
            # Also check personal_discord_username (used for all submissions now)
            if not is_self_submission and personal_discord_username and normalized_current:
                if normalize_discord_username(personal_discord_username) == normalized_current:
                    is_self_submission = True

            if is_self_submission:
                raise HTTPException(
                    status_code=403,
                    detail="You cannot approve your own submission. Another admin must review it."
                )

        # Parse system data
        system_data = json.loads(submission['system_data'])

        # Normalize empty glyph_code to None (NULL) to avoid unique constraint issues
        # The unique index only applies WHERE glyph_code IS NOT NULL, so empty strings cause conflicts
        if not system_data.get('glyph_code'):
            system_data['glyph_code'] = None

        # Calculate star position AND region coordinates
        # IMPORTANT: Validate that glyph_code matches X/Y/Z coordinates
        # If they don't match, the X/Y/Z coordinates are authoritative (from in-game extraction)
        star_x, star_y, star_z = None, None, None
        region_x, region_y, region_z = None, None, None

        submission_x = system_data.get('x')
        submission_y = system_data.get('y')
        submission_z = system_data.get('z')
        original_glyph = system_data.get('glyph_code')

        # EARLY CHECK: For EDIT submissions with no glyph, fetch the original system's glyph
        # This MUST happen before any glyph calculation to preserve the correct glyph
        existing_system_id = system_data.get('id')
        if existing_system_id and not original_glyph:
            cursor.execute('SELECT glyph_code, glyph_planet, glyph_solar_system FROM systems WHERE id = ?', (existing_system_id,))
            existing_row = cursor.fetchone()
            if existing_row and existing_row[0]:
                original_glyph = existing_row[0]
                system_data['glyph_code'] = original_glyph
                system_data['glyph_planet'] = existing_row[1] or 0
                system_data['glyph_solar_system'] = existing_row[2] or 1
                logger.info(f"Edit submission {submission_id}: Preserved original glyph {original_glyph} from existing system {existing_system_id}")

        if original_glyph:
            try:
                decoded = decode_glyph_to_coords(original_glyph)
                glyph_x = decoded['x']
                glyph_y = decoded['y']
                glyph_z = decoded['z']

                # Check if glyph coordinates match submission coordinates
                # Allow some tolerance for floating point comparison
                coords_match = True
                if submission_x is not None and submission_y is not None and submission_z is not None:
                    # Compare with tolerance
                    if (abs(glyph_x - submission_x) > 1 or
                        abs(glyph_y - submission_y) > 1 or
                        abs(glyph_z - submission_z) > 1):
                        coords_match = False
                        logger.warning(f"Glyph/coordinate mismatch detected!")
                        logger.warning(f"  Glyph {original_glyph} decodes to: ({glyph_x}, {glyph_y}, {glyph_z})")
                        logger.warning(f"  Submission X/Y/Z: ({submission_x}, {submission_y}, {submission_z})")

                if coords_match:
                    # Glyph matches, use decoded values
                    star_x = decoded['star_x']
                    star_y = decoded['star_y']
                    star_z = decoded['star_z']
                    region_x = decoded.get('region_x')
                    region_y = decoded.get('region_y')
                    region_z = decoded.get('region_z')
                    logger.info(f"Glyph validated: region ({region_x}, {region_y}, {region_z})")
                else:
                    # Mismatch! Recalculate glyph from submission X/Y/Z coordinates
                    # X/Y/Z from extraction are more reliable than the glyph
                    logger.warning(f"Recalculating glyph from submission coordinates...")
                    planet_idx = decoded.get('planet', 0)
                    solar_idx = decoded.get('solar_system', 1)

                    corrected_glyph = encode_coords_to_glyph(
                        int(submission_x), int(submission_y), int(submission_z),
                        planet_idx, solar_idx
                    )
                    corrected_decoded = decode_glyph_to_coords(corrected_glyph)

                    # Update system_data with corrected glyph
                    system_data['glyph_code'] = corrected_glyph
                    star_x = corrected_decoded['star_x']
                    star_y = corrected_decoded['star_y']
                    star_z = corrected_decoded['star_z']
                    region_x = corrected_decoded.get('region_x')
                    region_y = corrected_decoded.get('region_y')
                    region_z = corrected_decoded.get('region_z')

                    logger.info(f"Corrected glyph: {original_glyph} -> {corrected_glyph}")
                    logger.info(f"Corrected region: ({region_x}, {region_y}, {region_z})")

            except Exception as e:
                logger.warning(f"Failed to validate/calculate glyph during approval: {e}")

        # If we have X/Y/Z but no glyph, calculate glyph from coordinates
        elif submission_x is not None and submission_y is not None and submission_z is not None:
            try:
                calculated_glyph = encode_coords_to_glyph(
                    int(submission_x), int(submission_y), int(submission_z), 0, 1
                )
                decoded = decode_glyph_to_coords(calculated_glyph)

                system_data['glyph_code'] = calculated_glyph
                star_x = decoded['star_x']
                star_y = decoded['star_y']
                star_z = decoded['star_z']
                region_x = decoded.get('region_x')
                region_y = decoded.get('region_y')
                region_z = decoded.get('region_z')

                logger.info(f"Calculated glyph from X/Y/Z: {calculated_glyph}")
                logger.info(f"Calculated region: ({region_x}, {region_y}, {region_z})")
            except Exception as e:
                logger.warning(f"Failed to calculate glyph from coordinates: {e}")

        # Always update system_data with calculated region coords
        if region_x is not None:
            system_data['region_x'] = region_x
        if region_y is not None:
            system_data['region_y'] = region_y
        if region_z is not None:
            system_data['region_z'] = region_z

        # Check if this is an edit of an existing system (has an id)
        existing_system_id = system_data.get('id')
        is_edit = False
        original_glyph_data = None  # Store original glyph info for edits
        original_discovered_by = None
        original_discovered_at = None
        original_contributors = None

        logger.info(f"Approving submission {submission_id}: system_data.id = {existing_system_id}")

        if existing_system_id:
            # Check if the system actually exists in the database
            cursor.execute('''
                SELECT id, glyph_code, glyph_planet, glyph_solar_system,
                       discovered_by, discovered_at, contributors
                FROM systems WHERE id = ?
            ''', (existing_system_id,))
            existing_row = cursor.fetchone()
            if existing_row:
                is_edit = True
                system_id = existing_system_id
                # Store original glyph data to preserve if submission doesn't have it
                original_glyph_data = {
                    'glyph_code': existing_row[1],
                    'glyph_planet': existing_row[2],
                    'glyph_solar_system': existing_row[3]
                }
                original_discovered_by = existing_row[4]
                original_discovered_at = existing_row[5]
                original_contributors = existing_row[6]
                logger.info(f"Submission {submission_id} is an EDIT - found existing system with ID: {system_id}, original glyph: {original_glyph_data['glyph_code']}")
            else:
                logger.info(f"Submission {submission_id} has ID {existing_system_id} but system not found in DB - treating as NEW")

        # If not already an edit, check if a system with matching glyph coordinates exists
        # Match on last 11 characters (ignoring planet index) + galaxy + reality
        # This handles the case where someone submits a system that's already in the DB
        submission_galaxy = system_data.get('galaxy', 'Euclid')
        submission_reality = system_data.get('reality', 'Normal')
        existing_system_row = None

        if not is_edit and system_data.get('glyph_code'):
            existing_system_row = find_matching_system(
                cursor,
                system_data['glyph_code'],
                submission_galaxy,
                submission_reality
            )
            if existing_system_row:
                existing_name = existing_system_row[1]
                submitted_name = system_data.get('name', '').strip()

                # Check if names differ - require manual review
                if existing_name and submitted_name and existing_name.strip() != submitted_name:
                    raise HTTPException(
                        status_code=409,
                        detail=f"System glyph coordinates match existing system '{existing_name}' "
                               f"but submitted name is '{submitted_name}'. "
                               f"Please verify the names match or edit one before approving."
                    )

                is_edit = True
                system_id = existing_system_row[0]
                original_glyph_data = {
                    'glyph_code': existing_system_row[2],
                    'glyph_planet': existing_system_row[3],
                    'glyph_solar_system': existing_system_row[4]
                }
                # Store original discovered_by and contributors for preservation
                original_discovered_by = existing_system_row[5]
                original_discovered_at = existing_system_row[6]
                original_contributors = existing_system_row[7]
                logger.info(f"Submission {submission_id} has glyph matching existing system '{existing_name}' (ID: {system_id}) via last-11 + galaxy + reality - treating as EDIT")

        # For EDITS: If submission doesn't have glyph data, preserve the original
        if is_edit and original_glyph_data:
            if not system_data.get('glyph_code') and original_glyph_data.get('glyph_code'):
                system_data['glyph_code'] = original_glyph_data['glyph_code']
                system_data['glyph_planet'] = original_glyph_data.get('glyph_planet', 0)
                system_data['glyph_solar_system'] = original_glyph_data.get('glyph_solar_system', 1)
                logger.info(f"Preserved original glyph for edit: {system_data['glyph_code']}")

        if is_edit:
            # Determine the updater's username - personal_discord_username is the Discord name from the form
            updater_username = submission.get('personal_discord_username') or submission.get('submitted_by') or current_username or 'Unknown'
            now_iso = datetime.now(timezone.utc).isoformat()

            # Build updated contributors list (preserve original, add new edit entry)
            try:
                contributors_list = json.loads(original_contributors) if original_contributors else []
            except (json.JSONDecodeError, TypeError):
                contributors_list = []

            # Add edit entry (same person can appear multiple times with different edits)
            contributors_list.append({"name": updater_username, "action": "edit", "date": now_iso})

            # UPDATE existing system - PRESERVE discovered_by/discovered_at, UPDATE last_updated_by/last_updated_at
            cursor.execute('''
                UPDATE systems
                SET name = ?, galaxy = ?, x = ?, y = ?, z = ?,
                    star_x = ?, star_y = ?, star_z = ?,
                    description = ?,
                    glyph_code = ?, glyph_planet = ?, glyph_solar_system = ?,
                    region_x = ?, region_y = ?, region_z = ?,
                    star_type = ?, economy_type = ?, economy_level = ?,
                    conflict_level = ?, dominant_lifeform = ?,
                    discord_tag = ?, personal_discord_username = ?,
                    stellar_classification = ?,
                    last_updated_by = ?, last_updated_at = ?, contributors = ?
                WHERE id = ?
            ''', (
                system_data.get('name'),
                system_data.get('galaxy', 'Euclid'),
                system_data.get('x', 0),
                system_data.get('y', 0),
                system_data.get('z', 0),
                star_x,
                star_y,
                star_z,
                system_data.get('description', ''),
                system_data.get('glyph_code'),
                system_data.get('glyph_planet', 0),
                system_data.get('glyph_solar_system', 1),
                system_data.get('region_x'),
                system_data.get('region_y'),
                system_data.get('region_z'),
                system_data.get('star_type'),
                system_data.get('economy_type'),
                system_data.get('economy_level'),
                system_data.get('conflict_level'),
                system_data.get('dominant_lifeform'),
                submission.get('discord_tag'),
                submission.get('personal_discord_username'),
                system_data.get('stellar_classification'),
                updater_username,
                datetime.now(timezone.utc).isoformat(),
                json.dumps(contributors_list),
                system_id
            ))

            logger.info(f"Updated system {system_id}, preserving discovered_by='{original_discovered_by}', added contributor '{updater_username}'")

            # MERGE planets: Update existing by name, add new ones, keep others
            # First, get existing planets for this system
            cursor.execute('SELECT id, name FROM planets WHERE system_id = ?', (system_id,))
            existing_planets = {row[1]: row[0] for row in cursor.fetchall()}  # name -> id mapping

            # Track which planets we've processed (to keep unmentioned ones)
            processed_planet_names = set()
        else:
            # Generate UUID for new system
            import uuid
            system_id = str(uuid.uuid4())

            # Determine the discoverer's username - personal_discord_username is the Discord name from the form
            discoverer_username = submission.get('personal_discord_username') or submission.get('submitted_by') or 'Unknown'
            now_iso = datetime.now(timezone.utc).isoformat()

            # INSERT new system (including new tracking fields)
            cursor.execute('''
                INSERT INTO systems (id, name, galaxy, reality, x, y, z, star_x, star_y, star_z, description,
                    glyph_code, glyph_planet, glyph_solar_system, region_x, region_y, region_z,
                    star_type, economy_type, economy_level, conflict_level, dominant_lifeform,
                    discovered_by, discovered_at, discord_tag, personal_discord_username, stellar_classification,
                    contributors)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                system_id,
                system_data.get('name'),
                system_data.get('galaxy', 'Euclid'),
                system_data.get('reality', 'Normal'),
                system_data.get('x', 0),
                system_data.get('y', 0),
                system_data.get('z', 0),
                star_x,
                star_y,
                star_z,
                system_data.get('description', ''),
                system_data.get('glyph_code'),
                system_data.get('glyph_planet', 0),
                system_data.get('glyph_solar_system', 1),
                system_data.get('region_x'),
                system_data.get('region_y'),
                system_data.get('region_z'),
                system_data.get('star_type'),
                system_data.get('economy_type'),
                system_data.get('economy_level'),
                system_data.get('conflict_level'),
                system_data.get('dominant_lifeform'),
                discoverer_username,
                system_data.get('discovered_at') or now_iso,
                submission.get('discord_tag'),
                submission.get('personal_discord_username'),
                system_data.get('stellar_classification'),
                json.dumps([{"name": discoverer_username, "action": "upload", "date": now_iso}])
            ))

        # Handle planets - for edits, merge by name; for new systems, insert all
        # Initialize existing_planets if not already set (for new systems)
        if not is_edit:
            existing_planets = {}
            processed_planet_names = set()

        for planet in system_data.get('planets', []):
            # Handle sentinel_level -> sentinel field mapping (companion app sends sentinel_level)
            sentinel_val = planet.get('sentinel') or planet.get('sentinel_level', 'None')
            # Handle fauna_level/flora_level -> fauna/flora mapping
            fauna_val = planet.get('fauna') or planet.get('fauna_level', 'N/A')
            flora_val = planet.get('flora') or planet.get('flora_level', 'N/A')

            planet_name = planet.get('name')
            processed_planet_names.add(planet_name)

            # Check if this planet already exists (for edits)
            if is_edit and planet_name in existing_planets:
                # UPDATE existing planet
                existing_planet_id = existing_planets[planet_name]
                cursor.execute('''
                    UPDATE planets SET
                        x = ?, y = ?, z = ?, climate = ?, weather = ?, sentinel = ?, fauna = ?, flora = ?,
                        fauna_count = ?, flora_count = ?, has_water = ?, materials = ?, base_location = ?,
                        photo = ?, notes = ?, description = ?,
                        biome = ?, biome_subtype = ?, planet_size = ?, planet_index = ?, is_moon = ?,
                        storm_frequency = ?, weather_intensity = ?, building_density = ?,
                        hazard_temperature = ?, hazard_radiation = ?, hazard_toxicity = ?,
                        common_resource = ?, uncommon_resource = ?, rare_resource = ?,
                        weather_text = ?, sentinels_text = ?, flora_text = ?, fauna_text = ?,
                        vile_brood = ?, dissonance = ?, ancient_bones = ?, salvageable_scrap = ?,
                        storm_crystals = ?, gravitino_balls = ?, infested = ?, exotic_trophy = ?
                    WHERE id = ?
                ''', (
                    planet.get('x', 0),
                    planet.get('y', 0),
                    planet.get('z', 0),
                    planet.get('climate'),
                    planet.get('weather'),
                    sentinel_val,
                    fauna_val,
                    flora_val,
                    planet.get('fauna_count', 0),
                    planet.get('flora_count', 0),
                    planet.get('has_water', 0),
                    planet.get('materials'),
                    planet.get('base_location'),
                    planet.get('photo'),
                    planet.get('notes'),
                    planet.get('description', ''),
                    planet.get('biome'),
                    planet.get('biome_subtype'),
                    planet.get('planet_size'),
                    planet.get('planet_index'),
                    1 if planet.get('is_moon') else 0,
                    planet.get('storm_frequency'),
                    planet.get('weather_intensity'),
                    planet.get('building_density'),
                    planet.get('hazard_temperature', 0),
                    planet.get('hazard_radiation', 0),
                    planet.get('hazard_toxicity', 0),
                    planet.get('common_resource'),
                    planet.get('uncommon_resource'),
                    planet.get('rare_resource'),
                    planet.get('weather_text'),
                    planet.get('sentinels_text'),
                    planet.get('flora_text'),
                    planet.get('fauna_text'),
                    1 if planet.get('vile_brood') else 0,
                    1 if planet.get('dissonance') else 0,
                    1 if planet.get('ancient_bones') else 0,
                    1 if planet.get('salvageable_scrap') else 0,
                    1 if planet.get('storm_crystals') else 0,
                    1 if planet.get('gravitino_balls') else 0,
                    1 if planet.get('infested') else 0,
                    planet.get('exotic_trophy'),
                    existing_planet_id
                ))
                planet_id = existing_planet_id
                logger.info(f"Updated existing planet '{planet_name}' (ID: {planet_id})")
            else:
                # INSERT new planet
                cursor.execute('''
                    INSERT INTO planets (
                        system_id, name, x, y, z, climate, weather, sentinel, fauna, flora,
                        fauna_count, flora_count, has_water, materials, base_location, photo, notes, description,
                        biome, biome_subtype, planet_size, planet_index, is_moon,
                        storm_frequency, weather_intensity, building_density,
                        hazard_temperature, hazard_radiation, hazard_toxicity,
                        common_resource, uncommon_resource, rare_resource,
                        weather_text, sentinels_text, flora_text, fauna_text,
                        vile_brood, dissonance, ancient_bones, salvageable_scrap,
                        storm_crystals, gravitino_balls, infested, exotic_trophy
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    system_id,
                    planet_name,
                    planet.get('x', 0),
                    planet.get('y', 0),
                    planet.get('z', 0),
                    planet.get('climate'),
                    planet.get('weather'),
                    sentinel_val,
                    fauna_val,
                    flora_val,
                    planet.get('fauna_count', 0),
                    planet.get('flora_count', 0),
                    planet.get('has_water', 0),
                    planet.get('materials'),
                    planet.get('base_location'),
                    planet.get('photo'),
                    planet.get('notes'),
                    planet.get('description', ''),
                    planet.get('biome'),
                    planet.get('biome_subtype'),
                    planet.get('planet_size'),
                    planet.get('planet_index'),
                    1 if planet.get('is_moon') else 0,
                    planet.get('storm_frequency'),
                    planet.get('weather_intensity'),
                    planet.get('building_density'),
                    planet.get('hazard_temperature', 0),
                    planet.get('hazard_radiation', 0),
                    planet.get('hazard_toxicity', 0),
                    planet.get('common_resource'),
                    planet.get('uncommon_resource'),
                    planet.get('rare_resource'),
                    planet.get('weather_text'),
                    planet.get('sentinels_text'),
                    planet.get('flora_text'),
                    planet.get('fauna_text'),
                    1 if planet.get('vile_brood') else 0,
                    1 if planet.get('dissonance') else 0,
                    1 if planet.get('ancient_bones') else 0,
                    1 if planet.get('salvageable_scrap') else 0,
                    1 if planet.get('storm_crystals') else 0,
                    1 if planet.get('gravitino_balls') else 0,
                    1 if planet.get('infested') else 0,
                    planet.get('exotic_trophy')
                ))
                planet_id = cursor.lastrowid
                if is_edit:
                    logger.info(f"Added new planet '{planet_name}' (ID: {planet_id}) to existing system")

            # Insert moons (nested under planet)
            for moon in planet.get('moons', []):
                cursor.execute('''
                    INSERT INTO moons (planet_id, name, orbit_radius, orbit_speed, climate, sentinel, fauna, flora, materials, notes, description, photo)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    planet_id,
                    moon.get('name'),
                    moon.get('orbit_radius', 0.5),
                    moon.get('orbit_speed', 0),
                    moon.get('climate'),
                    moon.get('sentinel', 'None'),
                    moon.get('fauna', 'N/A'),
                    moon.get('flora', 'N/A'),
                    moon.get('materials'),
                    moon.get('notes'),
                    moon.get('description', ''),
                    moon.get('photo')
                ))

        # Handle root-level moons (from Haven Extractor which sends moons as flat list)
        # These moons are sent with is_moon=true but stored at root level by extraction API
        root_moons = system_data.get('moons', [])
        if root_moons and planet_id:
            # Attach root-level moons to the last inserted planet
            # (In NMS, moons orbit their closest planet, so this is a reasonable default)
            logger.info(f"Processing {len(root_moons)} root-level moons for system {system_id}")
            for moon in root_moons:
                cursor.execute('''
                    INSERT INTO moons (planet_id, name, orbit_radius, orbit_speed, climate, sentinel, fauna, flora, materials, notes, description, photo)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    planet_id,  # Attach to last planet
                    moon.get('name'),
                    moon.get('orbit_radius', 0.5),
                    moon.get('orbit_speed', 0),
                    moon.get('climate') or moon.get('weather'),
                    moon.get('sentinel') or moon.get('sentinels', 'None'),
                    moon.get('fauna', 'N/A'),
                    moon.get('flora', 'N/A'),
                    moon.get('materials'),
                    moon.get('notes'),
                    moon.get('description', ''),
                    moon.get('photo')
                ))

        # Insert space station if present
        if system_data.get('space_station'):
            station = system_data['space_station']
            # Convert trade_goods list to JSON string
            trade_goods_json = json.dumps(station.get('trade_goods', []))
            cursor.execute('''
                INSERT INTO space_stations (system_id, name, race, x, y, z, trade_goods)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                system_id,
                station.get('name') or f"{system_data.get('name')} Station",
                station.get('race') or 'Gek',
                station.get('x') or 0,
                station.get('y') or 0,
                station.get('z') or 0,
                trade_goods_json
            ))

        # Calculate and store completeness score
        update_completeness_score(cursor, system_id)

        # Mark submission as approved (use actual username instead of generic 'admin')
        cursor.execute('''
            UPDATE pending_systems
            SET status = ?, reviewed_by = ?, review_date = ?
            WHERE id = ?
        ''', ('approved', current_username, datetime.now(timezone.utc).isoformat(), submission_id))

        # Add to approval audit log for full tracking
        cursor.execute('''
            INSERT INTO approval_audit_log
            (timestamp, action, submission_type, submission_id, submission_name,
             approver_username, approver_type, approver_account_id, approver_discord_tag,
             submitter_username, submitter_account_id, submitter_type, submission_discord_tag)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            datetime.now(timezone.utc).isoformat(),
            'approved',
            'system',
            submission_id,
            system_data.get('name'),
            current_username,
            current_user_type,
            current_account_id,
            session_data.get('discord_tag'),
            # Show personal_discord_username (required for all submissions now) or fall back to submitted_by
            submission.get('personal_discord_username') or submission.get('submitted_by'),
            submission.get('submitter_account_id'),
            submission.get('submitter_account_type'),
            submission.get('discord_tag')
        ))

        conn.commit()

        action = 'updated' if is_edit else 'added'
        logger.info(f"Approved system submission: '{system_data.get('name')}' (ID: {submission_id}) - {action} by {current_username}")

        # Add activity log
        add_activity_log(
            'system_approved',
            f"System '{system_data.get('name')}' approved and {action}",
            details=f"Galaxy: {system_data.get('galaxy', 'Euclid')}, Approver: {current_username}",
            user_name=current_username
        )

        return {
            'status': 'ok',
            'message': f"System approved and {action} in database",
            'system_id': system_id,
            'system_name': system_data.get('name'),
            'is_edit': is_edit
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error approving submission: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to approve submission: {str(e)}")
    finally:
        if conn:
            conn.close()


@app.post('/api/reject_system/{submission_id}')
async def reject_system(submission_id: int, payload: dict, session: Optional[str] = Cookie(None)):
    """
    Reject a pending system submission with reason (admin only).
    Self-rejection is blocked for non-super-admin users (same as approval).
    """
    # Verify admin session
    if not verify_session(session):
        raise HTTPException(status_code=401, detail="Admin authentication required")

    # Get current user identity for self-rejection check and audit
    session_data = get_session(session)
    current_user_type = session_data.get('user_type')
    current_username = session_data.get('username')
    current_account_id = None
    if current_user_type == 'partner':
        current_account_id = session_data.get('partner_id')
    elif current_user_type == 'sub_admin':
        current_account_id = session_data.get('sub_admin_id')

    reason = payload.get('reason', 'No reason provided')

    conn = None
    try:
        db_path = get_db_path()
        conn = get_db_connection()
        cursor = conn.cursor()

        # Check submission exists and is pending
        cursor.execute('SELECT * FROM pending_systems WHERE id = ?', (submission_id,))
        row = cursor.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Submission not found")

        submission = dict(row)
        system_name = submission.get('system_name')

        if submission['status'] != 'pending':
            raise HTTPException(
                status_code=400,
                detail=f"Submission already {submission['status']}"
            )

        # SELF-REJECTION BLOCKING (same logic as approval)
        # Super admin can reject anything (trusted role)
        if current_user_type != 'super_admin':
            submitter_account_id = submission.get('submitter_account_id')
            submitter_account_type = submission.get('submitter_account_type')
            submitted_by = submission.get('submitted_by')
            personal_discord_username = submission.get('personal_discord_username')
            # Normalize usernames to handle Discord #XXXX discriminator
            normalized_current = normalize_discord_username(current_username)

            is_self_submission = False

            if submitter_account_id is not None and submitter_account_type:
                if current_user_type == submitter_account_type and current_account_id == submitter_account_id:
                    is_self_submission = True
            elif submitted_by and normalized_current and normalize_discord_username(submitted_by) == normalized_current:
                is_self_submission = True
            # Also check personal_discord_username (used for all submissions now)
            if not is_self_submission and personal_discord_username and normalized_current:
                if normalize_discord_username(personal_discord_username) == normalized_current:
                    is_self_submission = True

            if is_self_submission:
                raise HTTPException(
                    status_code=403,
                    detail="You cannot reject your own submission. Another admin must review it."
                )

        # Mark as rejected (use actual username)
        cursor.execute('''
            UPDATE pending_systems
            SET status = ?, reviewed_by = ?, review_date = ?, rejection_reason = ?
            WHERE id = ?
        ''', ('rejected', current_username, datetime.now(timezone.utc).isoformat(), reason, submission_id))

        # Add to approval audit log
        cursor.execute('''
            INSERT INTO approval_audit_log
            (timestamp, action, submission_type, submission_id, submission_name,
             approver_username, approver_type, approver_account_id, approver_discord_tag,
             submitter_username, submitter_account_id, submitter_type, notes, submission_discord_tag)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            datetime.now(timezone.utc).isoformat(),
            'rejected',
            'system',
            submission_id,
            system_name,
            current_username,
            current_user_type,
            current_account_id,
            session_data.get('discord_tag'),
            # Show personal_discord_username (required for all submissions now) or fall back to submitted_by
            submission.get('personal_discord_username') or submission.get('submitted_by'),
            submission.get('submitter_account_id'),
            submission.get('submitter_account_type'),
            reason,
            submission.get('discord_tag')
        ))

        conn.commit()

        logger.info(f"Rejected system submission: '{system_name}' (ID: {submission_id}) by {current_username}. Reason: {reason}")

        # Add activity log
        add_activity_log(
            'system_rejected',
            f"System '{system_name}' rejected",
            details=f"Reason: {reason}, Reviewer: {current_username}",
            user_name=current_username
        )

        return {
            'status': 'ok',
            'message': 'System submission rejected',
            'submission_id': submission_id
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error rejecting submission: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to reject submission: {str(e)}")
    finally:
        if conn:
            conn.close()


# =============================================================================
# BATCH APPROVAL/REJECTION ENDPOINTS
# =============================================================================

@app.post('/api/approve_systems/batch')
async def batch_approve_systems(payload: dict, session: Optional[str] = Cookie(None)):
    """
    Batch approve multiple pending system submissions (admin only).
    Requires 'batch_approvals' feature for non-super-admins.
    Self-submissions are skipped (not failed) for non-super-admin users.
    """
    # Verify admin session
    if not verify_session(session):
        raise HTTPException(status_code=401, detail="Admin authentication required")

    session_data = get_session(session)
    current_user_type = session_data.get('user_type')
    current_username = session_data.get('username')
    enabled_features = session_data.get('enabled_features', [])

    # Permission check: super admin OR has batch_approvals feature
    is_super = current_user_type == 'super_admin'
    if not is_super and 'batch_approvals' not in enabled_features:
        raise HTTPException(status_code=403, detail="Batch approvals permission required")

    current_account_id = None
    if current_user_type == 'partner':
        current_account_id = session_data.get('partner_id')
    elif current_user_type == 'sub_admin':
        current_account_id = session_data.get('sub_admin_id')

    submission_ids = payload.get('submission_ids', [])
    if not submission_ids:
        raise HTTPException(status_code=400, detail="No submission IDs provided")

    results = {
        'approved': [],
        'failed': [],
        'skipped': []
    }

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        for submission_id in submission_ids:
            try:
                # Get submission
                cursor.execute('SELECT * FROM pending_systems WHERE id = ?', (submission_id,))
                row = cursor.fetchone()

                if not row:
                    results['failed'].append({
                        'id': submission_id,
                        'name': None,
                        'error': 'Submission not found'
                    })
                    continue

                submission = dict(row)
                system_name = submission.get('system_name')

                if submission['status'] != 'pending':
                    results['skipped'].append({
                        'id': submission_id,
                        'name': system_name,
                        'reason': f"Already {submission['status']}"
                    })
                    continue

                # Self-approval check (skip for non-super-admins)
                if not is_super:
                    submitter_account_id = submission.get('submitter_account_id')
                    submitter_account_type = submission.get('submitter_account_type')
                    submitted_by = submission.get('submitted_by')
                    personal_discord_username = submission.get('personal_discord_username')
                    # Normalize usernames to handle Discord #XXXX discriminator
                    normalized_current = normalize_discord_username(current_username)

                    is_self_submission = False
                    if submitter_account_id is not None and submitter_account_type:
                        if current_user_type == submitter_account_type and current_account_id == submitter_account_id:
                            is_self_submission = True
                    elif submitted_by and normalized_current and normalize_discord_username(submitted_by) == normalized_current:
                        is_self_submission = True
                    # Also check personal_discord_username (used for all submissions now)
                    if not is_self_submission and personal_discord_username and normalized_current:
                        if normalize_discord_username(personal_discord_username) == normalized_current:
                            is_self_submission = True

                    if is_self_submission:
                        results['skipped'].append({
                            'id': submission_id,
                            'name': system_name,
                            'reason': 'Self-submission'
                        })
                        continue

                # Parse and process system data
                system_data = json.loads(submission['system_data'])
                if not system_data.get('glyph_code'):
                    system_data['glyph_code'] = None

                # Calculate star and region coordinates
                star_x, star_y, star_z = None, None, None
                region_x, region_y, region_z = None, None, None

                submission_x = system_data.get('x')
                submission_y = system_data.get('y')
                submission_z = system_data.get('z')
                original_glyph = system_data.get('glyph_code')

                # EARLY CHECK: For EDIT submissions with no glyph, fetch the original system's glyph
                existing_system_id = system_data.get('id')
                if existing_system_id and not original_glyph:
                    cursor.execute('SELECT glyph_code, glyph_planet, glyph_solar_system FROM systems WHERE id = ?', (existing_system_id,))
                    existing_row = cursor.fetchone()
                    if existing_row and existing_row[0]:
                        original_glyph = existing_row[0]
                        system_data['glyph_code'] = original_glyph
                        system_data['glyph_planet'] = existing_row[1] or 0
                        system_data['glyph_solar_system'] = existing_row[2] or 1
                        logger.info(f"Batch approval: Preserved original glyph {original_glyph} for edit of system {existing_system_id}")

                if original_glyph:
                    try:
                        decoded = decode_glyph_to_coords(original_glyph)
                        glyph_x, glyph_y, glyph_z = decoded['x'], decoded['y'], decoded['z']

                        coords_match = True
                        if submission_x is not None and submission_y is not None and submission_z is not None:
                            if (abs(glyph_x - submission_x) > 1 or
                                abs(glyph_y - submission_y) > 1 or
                                abs(glyph_z - submission_z) > 1):
                                coords_match = False

                        if coords_match:
                            star_x, star_y, star_z = decoded['star_x'], decoded['star_y'], decoded['star_z']
                            region_x = decoded.get('region_x')
                            region_y = decoded.get('region_y')
                            region_z = decoded.get('region_z')
                        else:
                            planet_idx = decoded.get('planet', 0)
                            solar_idx = decoded.get('solar_system', 1)
                            corrected_glyph = encode_coords_to_glyph(
                                int(submission_x), int(submission_y), int(submission_z),
                                planet_idx, solar_idx
                            )
                            corrected_decoded = decode_glyph_to_coords(corrected_glyph)
                            system_data['glyph_code'] = corrected_glyph
                            star_x, star_y, star_z = corrected_decoded['star_x'], corrected_decoded['star_y'], corrected_decoded['star_z']
                            region_x = corrected_decoded.get('region_x')
                            region_y = corrected_decoded.get('region_y')
                            region_z = corrected_decoded.get('region_z')
                    except Exception as e:
                        logger.warning(f"Batch approval: Failed to validate glyph for submission {submission_id}: {e}")

                elif submission_x is not None and submission_y is not None and submission_z is not None:
                    try:
                        calculated_glyph = encode_coords_to_glyph(
                            int(submission_x), int(submission_y), int(submission_z), 0, 1
                        )
                        decoded = decode_glyph_to_coords(calculated_glyph)
                        system_data['glyph_code'] = calculated_glyph
                        star_x, star_y, star_z = decoded['star_x'], decoded['star_y'], decoded['star_z']
                        region_x = decoded.get('region_x')
                        region_y = decoded.get('region_y')
                        region_z = decoded.get('region_z')
                    except Exception as e:
                        logger.warning(f"Batch approval: Failed to calculate glyph for submission {submission_id}: {e}")

                if region_x is not None:
                    system_data['region_x'] = region_x
                if region_y is not None:
                    system_data['region_y'] = region_y
                if region_z is not None:
                    system_data['region_z'] = region_z

                # Check if edit or new
                existing_system_id = system_data.get('id')
                is_edit = False
                system_id = None
                original_glyph_data = None  # Store original glyph info for edits

                if existing_system_id:
                    cursor.execute('SELECT id, glyph_code, glyph_planet, glyph_solar_system FROM systems WHERE id = ?', (existing_system_id,))
                    existing_row = cursor.fetchone()
                    if existing_row:
                        is_edit = True
                        system_id = existing_system_id
                        original_glyph_data = {
                            'glyph_code': existing_row[1],
                            'glyph_planet': existing_row[2],
                            'glyph_solar_system': existing_row[3]
                        }

                if not is_edit and system_data.get('glyph_code'):
                    cursor.execute('SELECT id, glyph_code, glyph_planet, glyph_solar_system FROM systems WHERE glyph_code = ?', (system_data['glyph_code'],))
                    existing_glyph_row = cursor.fetchone()
                    if existing_glyph_row:
                        is_edit = True
                        system_id = existing_glyph_row[0]
                        original_glyph_data = {
                            'glyph_code': existing_glyph_row[1],
                            'glyph_planet': existing_glyph_row[2],
                            'glyph_solar_system': existing_glyph_row[3]
                        }

                # For EDITS: If submission doesn't have glyph data, preserve the original
                if is_edit and original_glyph_data:
                    if not system_data.get('glyph_code') and original_glyph_data.get('glyph_code'):
                        system_data['glyph_code'] = original_glyph_data['glyph_code']
                        system_data['glyph_planet'] = original_glyph_data.get('glyph_planet', 0)
                        system_data['glyph_solar_system'] = original_glyph_data.get('glyph_solar_system', 1)

                if is_edit:
                    # Update contributors list - add edit entry
                    updater_username = submission.get('personal_discord_username') or submission.get('submitted_by') or 'Unknown'
                    now_iso = datetime.now(timezone.utc).isoformat()
                    cursor.execute('SELECT contributors FROM systems WHERE id = ?', (system_id,))
                    contrib_row = cursor.fetchone()
                    existing_contributors = json.loads(contrib_row[0]) if contrib_row and contrib_row[0] else []
                    existing_contributors.append({"name": updater_username, "action": "edit", "date": now_iso})

                    cursor.execute('''
                        UPDATE systems
                        SET name = ?, galaxy = ?, x = ?, y = ?, z = ?,
                            star_x = ?, star_y = ?, star_z = ?,
                            description = ?,
                            glyph_code = ?, glyph_planet = ?, glyph_solar_system = ?,
                            region_x = ?, region_y = ?, region_z = ?,
                            star_type = ?, economy_type = ?, economy_level = ?,
                            conflict_level = ?, dominant_lifeform = ?,
                            discord_tag = ?, personal_discord_username = ?,
                            stellar_classification = ?,
                            last_updated_by = ?, last_updated_at = ?,
                            contributors = ?
                        WHERE id = ?
                    ''', (
                        system_data.get('name'),
                        system_data.get('galaxy', 'Euclid'),
                        system_data.get('x', 0),
                        system_data.get('y', 0),
                        system_data.get('z', 0),
                        star_x, star_y, star_z,
                        system_data.get('description', ''),
                        system_data.get('glyph_code'),
                        system_data.get('glyph_planet', 0),
                        system_data.get('glyph_solar_system', 1),
                        system_data.get('region_x'),
                        system_data.get('region_y'),
                        system_data.get('region_z'),
                        system_data.get('star_type'),
                        system_data.get('economy_type'),
                        system_data.get('economy_level'),
                        system_data.get('conflict_level'),
                        system_data.get('dominant_lifeform'),
                        submission.get('discord_tag'),
                        submission.get('personal_discord_username'),
                        system_data.get('stellar_classification'),
                        updater_username,
                        now_iso,
                        json.dumps(existing_contributors),
                        system_id
                    ))

                    # Delete existing planets, moons, and space station
                    cursor.execute('SELECT id FROM planets WHERE system_id = ?', (system_id,))
                    planet_ids = [row[0] for row in cursor.fetchall()]
                    for pid in planet_ids:
                        cursor.execute('DELETE FROM moons WHERE planet_id = ?', (pid,))
                    cursor.execute('DELETE FROM planets WHERE system_id = ?', (system_id,))
                    cursor.execute('DELETE FROM space_stations WHERE system_id = ?', (system_id,))
                else:
                    import uuid
                    system_id = str(uuid.uuid4())

                    # Determine the discoverer's username - personal_discord_username is the Discord name from the form
                    discoverer_username = submission.get('personal_discord_username') or submission.get('submitted_by') or 'Unknown'
                    now_iso = datetime.now(timezone.utc).isoformat()

                    cursor.execute('''
                        INSERT INTO systems (id, name, galaxy, reality, x, y, z, star_x, star_y, star_z, description,
                            glyph_code, glyph_planet, glyph_solar_system, region_x, region_y, region_z,
                            star_type, economy_type, economy_level, conflict_level, dominant_lifeform,
                            discovered_by, discovered_at, discord_tag, personal_discord_username, stellar_classification,
                            contributors)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        system_id,
                        system_data.get('name'),
                        system_data.get('galaxy', 'Euclid'),
                        system_data.get('reality', 'Normal'),
                        system_data.get('x', 0),
                        system_data.get('y', 0),
                        system_data.get('z', 0),
                        star_x, star_y, star_z,
                        system_data.get('description', ''),
                        system_data.get('glyph_code'),
                        system_data.get('glyph_planet', 0),
                        system_data.get('glyph_solar_system', 1),
                        system_data.get('region_x'),
                        system_data.get('region_y'),
                        system_data.get('region_z'),
                        system_data.get('star_type'),
                        system_data.get('economy_type'),
                        system_data.get('economy_level'),
                        system_data.get('conflict_level'),
                        system_data.get('dominant_lifeform'),
                        discoverer_username,
                        system_data.get('discovered_at') or now_iso,
                        submission.get('discord_tag'),
                        submission.get('personal_discord_username'),
                        system_data.get('stellar_classification'),
                        json.dumps([{"name": discoverer_username, "action": "upload", "date": now_iso}])
                    ))

                # Insert planets
                for planet in system_data.get('planets', []):
                    sentinel_val = planet.get('sentinel') or planet.get('sentinel_level', 'None')
                    fauna_val = planet.get('fauna') or planet.get('fauna_level', 'N/A')
                    flora_val = planet.get('flora') or planet.get('flora_level', 'N/A')

                    cursor.execute('''
                        INSERT INTO planets (
                            system_id, name, x, y, z, climate, weather, sentinel, fauna, flora,
                            fauna_count, flora_count, has_water, materials, base_location, photo, notes, description,
                            biome, biome_subtype, planet_size, planet_index, is_moon,
                            storm_frequency, weather_intensity, building_density,
                            hazard_temperature, hazard_radiation, hazard_toxicity,
                            common_resource, uncommon_resource, rare_resource,
                            weather_text, sentinels_text, flora_text, fauna_text,
                            vile_brood, dissonance, ancient_bones, salvageable_scrap,
                            storm_crystals, gravitino_balls, infested, exotic_trophy
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        system_id,
                        planet.get('name'),
                        planet.get('x', 0),
                        planet.get('y', 0),
                        planet.get('z', 0),
                        planet.get('climate'),
                        planet.get('weather'),
                        sentinel_val,
                        fauna_val,
                        flora_val,
                        planet.get('fauna_count', 0),
                        planet.get('flora_count', 0),
                        planet.get('has_water', 0),
                        planet.get('materials'),
                        planet.get('base_location'),
                        planet.get('photo'),
                        planet.get('notes'),
                        planet.get('description', ''),
                        planet.get('biome'),
                        planet.get('biome_subtype'),
                        planet.get('planet_size'),
                        planet.get('planet_index'),
                        1 if planet.get('is_moon') else 0,
                        planet.get('storm_frequency'),
                        planet.get('weather_intensity'),
                        planet.get('building_density'),
                        planet.get('hazard_temperature', 0),
                        planet.get('hazard_radiation', 0),
                        planet.get('hazard_toxicity', 0),
                        planet.get('common_resource'),
                        planet.get('uncommon_resource'),
                        planet.get('rare_resource'),
                        planet.get('weather_text'),
                        planet.get('sentinels_text'),
                        planet.get('flora_text'),
                        planet.get('fauna_text'),
                        1 if planet.get('vile_brood') else 0,
                        1 if planet.get('dissonance') else 0,
                        1 if planet.get('ancient_bones') else 0,
                        1 if planet.get('salvageable_scrap') else 0,
                        1 if planet.get('storm_crystals') else 0,
                        1 if planet.get('gravitino_balls') else 0,
                        1 if planet.get('infested') else 0,
                        planet.get('exotic_trophy')
                    ))
                    planet_id = cursor.lastrowid

                    for moon in planet.get('moons', []):
                        cursor.execute('''
                            INSERT INTO moons (planet_id, name, orbit_radius, orbit_speed, climate, sentinel, fauna, flora, materials, notes, description, photo)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (
                            planet_id,
                            moon.get('name'),
                            moon.get('orbit_radius', 0.5),
                            moon.get('orbit_speed', 0),
                            moon.get('climate'),
                            moon.get('sentinel', 'None'),
                            moon.get('fauna', 'N/A'),
                            moon.get('flora', 'N/A'),
                            moon.get('materials'),
                            moon.get('notes'),
                            moon.get('description', ''),
                            moon.get('photo')
                        ))

                # Insert space station if present
                if system_data.get('space_station'):
                    station = system_data['space_station']
                    # Convert trade_goods list to JSON string
                    trade_goods_json = json.dumps(station.get('trade_goods', []))
                    cursor.execute('''
                        INSERT INTO space_stations (system_id, name, race, x, y, z, trade_goods)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        system_id,
                        station.get('name') or f"{system_data.get('name')} Station",
                        station.get('race') or 'Gek',
                        station.get('x') or 0,
                        station.get('y') or 0,
                        station.get('z') or 0,
                        trade_goods_json
                    ))

                # Calculate and store completeness score
                update_completeness_score(cursor, system_id)

                # Mark submission as approved
                cursor.execute('''
                    UPDATE pending_systems
                    SET status = ?, reviewed_by = ?, review_date = ?
                    WHERE id = ?
                ''', ('approved', current_username, datetime.now(timezone.utc).isoformat(), submission_id))

                # Add to approval audit log
                cursor.execute('''
                    INSERT INTO approval_audit_log
                    (timestamp, action, submission_type, submission_id, submission_name,
                     approver_username, approver_type, approver_account_id, approver_discord_tag,
                     submitter_username, submitter_account_id, submitter_type, submission_discord_tag)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    datetime.now(timezone.utc).isoformat(),
                    'approved',
                    'system',
                    submission_id,
                    system_data.get('name'),
                    current_username,
                    current_user_type,
                    current_account_id,
                    session_data.get('discord_tag'),
                    # Show personal_discord_username (required for all submissions now) or fall back to submitted_by
                    submission.get('personal_discord_username') or submission.get('submitted_by'),
                    submission.get('submitter_account_id'),
                    submission.get('submitter_account_type'),
                    submission.get('discord_tag')
                ))

                results['approved'].append({
                    'id': submission_id,
                    'name': system_data.get('name'),
                    'system_id': system_id,
                    'is_edit': is_edit
                })

            except Exception as e:
                logger.error(f"Batch approval: Error processing submission {submission_id}: {e}")
                results['failed'].append({
                    'id': submission_id,
                    'name': system_name if 'system_name' in dir() else None,
                    'error': str(e)
                })

        conn.commit()

        # Add activity log for batch operation
        add_activity_log(
            'batch_approval',
            f"Batch approved {len(results['approved'])} systems",
            details=f"Approved: {len(results['approved'])}, Failed: {len(results['failed'])}, Skipped: {len(results['skipped'])}, Approver: {current_username}",
            user_name=current_username
        )

        logger.info(f"Batch approval completed by {current_username}: {len(results['approved'])} approved, {len(results['failed'])} failed, {len(results['skipped'])} skipped")

        return {
            'status': 'ok',
            'results': results,
            'summary': {
                'total': len(submission_ids),
                'approved': len(results['approved']),
                'failed': len(results['failed']),
                'skipped': len(results['skipped'])
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Batch approval error: {e}")
        raise HTTPException(status_code=500, detail=f"Batch approval failed: {str(e)}")
    finally:
        if conn:
            conn.close()


@app.post('/api/reject_systems/batch')
async def batch_reject_systems(payload: dict, session: Optional[str] = Cookie(None)):
    """
    Batch reject multiple pending system submissions with a shared reason (admin only).
    Requires 'batch_approvals' feature for non-super-admins.
    Self-submissions are skipped (not failed) for non-super-admin users.
    """
    # Verify admin session
    if not verify_session(session):
        raise HTTPException(status_code=401, detail="Admin authentication required")

    session_data = get_session(session)
    current_user_type = session_data.get('user_type')
    current_username = session_data.get('username')
    enabled_features = session_data.get('enabled_features', [])

    # Permission check: super admin OR has batch_approvals feature
    is_super = current_user_type == 'super_admin'
    if not is_super and 'batch_approvals' not in enabled_features:
        raise HTTPException(status_code=403, detail="Batch approvals permission required")

    current_account_id = None
    if current_user_type == 'partner':
        current_account_id = session_data.get('partner_id')
    elif current_user_type == 'sub_admin':
        current_account_id = session_data.get('sub_admin_id')

    submission_ids = payload.get('submission_ids', [])
    reason = payload.get('reason', 'No reason provided')

    if not submission_ids:
        raise HTTPException(status_code=400, detail="No submission IDs provided")

    if not reason or not reason.strip():
        raise HTTPException(status_code=400, detail="Rejection reason is required")

    results = {
        'rejected': [],
        'failed': [],
        'skipped': []
    }

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        for submission_id in submission_ids:
            try:
                # Get submission
                cursor.execute('SELECT * FROM pending_systems WHERE id = ?', (submission_id,))
                row = cursor.fetchone()

                if not row:
                    results['failed'].append({
                        'id': submission_id,
                        'name': None,
                        'error': 'Submission not found'
                    })
                    continue

                submission = dict(row)
                system_name = submission.get('system_name')

                if submission['status'] != 'pending':
                    results['skipped'].append({
                        'id': submission_id,
                        'name': system_name,
                        'reason': f"Already {submission['status']}"
                    })
                    continue

                # Self-rejection check (skip for non-super-admins)
                if not is_super:
                    submitter_account_id = submission.get('submitter_account_id')
                    submitter_account_type = submission.get('submitter_account_type')
                    submitted_by = submission.get('submitted_by')
                    personal_discord_username = submission.get('personal_discord_username')
                    # Normalize usernames to handle Discord #XXXX discriminator
                    normalized_current = normalize_discord_username(current_username)

                    is_self_submission = False
                    if submitter_account_id is not None and submitter_account_type:
                        if current_user_type == submitter_account_type and current_account_id == submitter_account_id:
                            is_self_submission = True
                    elif submitted_by and normalized_current and normalize_discord_username(submitted_by) == normalized_current:
                        is_self_submission = True
                    # Also check personal_discord_username (used for all submissions now)
                    if not is_self_submission and personal_discord_username and normalized_current:
                        if normalize_discord_username(personal_discord_username) == normalized_current:
                            is_self_submission = True

                    if is_self_submission:
                        results['skipped'].append({
                            'id': submission_id,
                            'name': system_name,
                            'reason': 'Self-submission'
                        })
                        continue

                # Mark as rejected
                cursor.execute('''
                    UPDATE pending_systems
                    SET status = ?, reviewed_by = ?, review_date = ?, rejection_reason = ?
                    WHERE id = ?
                ''', ('rejected', current_username, datetime.now(timezone.utc).isoformat(), reason, submission_id))

                # Add to approval audit log
                cursor.execute('''
                    INSERT INTO approval_audit_log
                    (timestamp, action, submission_type, submission_id, submission_name,
                     approver_username, approver_type, approver_account_id, approver_discord_tag,
                     submitter_username, submitter_account_id, submitter_type, notes, submission_discord_tag)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    datetime.now(timezone.utc).isoformat(),
                    'rejected',
                    'system',
                    submission_id,
                    system_name,
                    current_username,
                    current_user_type,
                    current_account_id,
                    session_data.get('discord_tag'),
                    # Show personal_discord_username (required for all submissions now) or fall back to submitted_by
                    submission.get('personal_discord_username') or submission.get('submitted_by'),
                    submission.get('submitter_account_id'),
                    submission.get('submitter_account_type'),
                    reason,
                    submission.get('discord_tag')
                ))

                results['rejected'].append({
                    'id': submission_id,
                    'name': system_name
                })

            except Exception as e:
                logger.error(f"Batch rejection: Error processing submission {submission_id}: {e}")
                results['failed'].append({
                    'id': submission_id,
                    'name': system_name if 'system_name' in dir() else None,
                    'error': str(e)
                })

        conn.commit()

        # Add activity log for batch operation
        add_activity_log(
            'batch_rejection',
            f"Batch rejected {len(results['rejected'])} systems",
            details=f"Rejected: {len(results['rejected'])}, Failed: {len(results['failed'])}, Skipped: {len(results['skipped'])}, Reason: {reason}, Reviewer: {current_username}",
            user_name=current_username
        )

        logger.info(f"Batch rejection completed by {current_username}: {len(results['rejected'])} rejected, {len(results['failed'])} failed, {len(results['skipped'])} skipped. Reason: {reason}")

        return {
            'status': 'ok',
            'results': results,
            'summary': {
                'total': len(submission_ids),
                'rejected': len(results['rejected']),
                'failed': len(results['failed']),
                'skipped': len(results['skipped'])
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Batch rejection error: {e}")
        raise HTTPException(status_code=500, detail=f"Batch rejection failed: {str(e)}")
    finally:
        if conn:
            conn.close()


# =============================================================================
# HAVEN EXTRACTOR API ENDPOINTS
# =============================================================================

@app.post('/api/check_glyph_codes')
async def check_glyph_codes(
    payload: dict,
    request: Request,
    x_api_key: Optional[str] = Header(None, alias='X-API-Key')
):
    """
    Pre-flight duplicate check for Haven Extractor batch uploads.
    Checks multiple glyph codes against both approved systems and pending submissions.

    Required permission: check_duplicate

    Request body:
    {
        "glyph_codes": ["ABC123DEF456", "111111111111", "222222222222"]
    }

    Response:
    {
        "results": {
            "ABC123DEF456": {"status": "available", "exists": false},
            "111111111111": {"status": "already_charted", "exists": true, "location": "approved", ...},
            "222222222222": {"status": "pending_review", "exists": true, "location": "pending", ...}
        },
        "summary": {"available": 1, "already_charted": 1, "pending_review": 1, "total": 3}
    }
    """
    # Validate API key and check for check_duplicate permission
    api_key_info = verify_api_key(x_api_key) if x_api_key else None

    if not api_key_info:
        raise HTTPException(status_code=401, detail="API key required for duplicate check")

    permissions = api_key_info.get('permissions', [])
    if isinstance(permissions, str):
        try:
            permissions = json.loads(permissions)
        except:
            permissions = []

    if 'check_duplicate' not in permissions and 'submit' not in permissions:
        raise HTTPException(status_code=403, detail="API key does not have check_duplicate permission")

    glyph_codes = payload.get('glyph_codes', [])
    if not glyph_codes or not isinstance(glyph_codes, list):
        raise HTTPException(status_code=400, detail="glyph_codes array is required")

    # Limit to prevent abuse
    if len(glyph_codes) > 100:
        raise HTTPException(status_code=400, detail="Maximum 100 glyph codes per request")

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        results = {}
        summary = {'available': 0, 'already_charted': 0, 'pending_review': 0, 'total': len(glyph_codes)}

        for glyph in glyph_codes:
            # Validate glyph format
            if not glyph or len(glyph) != 12:
                results[glyph] = {'status': 'invalid', 'exists': False, 'error': 'Invalid glyph code format'}
                continue

            # Check approved systems table first
            cursor.execute('''
                SELECT id, name, galaxy, discovered_by, created_at
                FROM systems
                WHERE glyph_code = ?
            ''', (glyph,))
            approved = cursor.fetchone()

            if approved:
                results[glyph] = {
                    'status': 'already_charted',
                    'exists': True,
                    'location': 'approved',
                    'system_id': approved[0],
                    'system_name': approved[1],
                    'galaxy': approved[2],
                    'submitted_by': approved[3],
                    'approved_date': approved[4]
                }
                summary['already_charted'] += 1
                continue

            # Check pending systems
            cursor.execute('''
                SELECT id, system_name, personal_discord_username, submitter_name, submission_date
                FROM pending_systems
                WHERE glyph_code = ? AND status = 'pending'
            ''', (glyph,))
            pending = cursor.fetchone()

            if pending:
                submitted_by = pending[2] or pending[3] or 'Unknown'
                results[glyph] = {
                    'status': 'pending_review',
                    'exists': True,
                    'location': 'pending',
                    'submission_id': pending[0],
                    'system_name': pending[1],
                    'submitted_by': submitted_by,
                    'submission_date': pending[4]
                }
                summary['pending_review'] += 1
                continue

            # Not found anywhere - available
            results[glyph] = {'status': 'available', 'exists': False}
            summary['available'] += 1

        logger.info(f"Duplicate check: {len(glyph_codes)} codes checked - {summary['available']} available, {summary['already_charted']} charted, {summary['pending_review']} pending")

        return JSONResponse({
            'results': results,
            'summary': summary
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error checking glyph codes: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()


@app.post('/api/extraction')
async def receive_extraction(
    payload: dict,
    request: Request,
    x_api_key: Optional[str] = Header(None, alias='X-API-Key')
):
    """
    Receive extraction data from Haven Extractor (running in-game via pymhf).
    This endpoint accepts the JSON extraction format and converts it to a system submission.

    Expected payload format (from Haven Extractor v10+):
    {
        "extraction_time": "2024-01-15T12:00:00",
        "extractor_version": "10.0.0",
        "glyph_code": "0123456789AB",
        "galaxy_name": "Euclid",
        "galaxy_index": 0,
        "voxel_x": 100,
        "voxel_y": 50,
        "voxel_z": -200,
        "solar_system_index": 123,
        "system_name": "System Name",
        "star_type": "Yellow",
        "economy_type": "Trading",
        "economy_strength": "Wealthy",
        "conflict_level": "Low",
        "dominant_lifeform": "Gek",
        "reality": "Normal",
        "discord_username": "TurpitZz",
        "personal_id": "123456789012345678",
        "discord_tag": "Haven",
        "planets": [
            {
                "planet_index": 0,
                "planet_name": "Planet Name",
                "biome": "Lush",
                "biome_subtype": "Standard",
                "weather": "Pleasant",
                "sentinel_level": "Low",
                "flora_level": "High",
                "fauna_level": "Medium",
                "planet_size": "Large",
                "common_resource": "Copper",
                "uncommon_resource": "Carbon",
                "rare_resource": "Gold",
                "is_moon": false
            }
        ]
    }
    """
    client_ip = request.client.host if request.client else "unknown"

    # Validate API key if provided
    api_key_info = verify_api_key(x_api_key) if x_api_key else None

    # Apply rate limiting
    if api_key_info:
        rate_limit = api_key_info.get('rate_limit', 200)
        is_allowed, remaining = check_api_key_rate_limit(api_key_info['id'], rate_limit)
        if not is_allowed:
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded",
                headers={"Retry-After": "3600"}
            )
    else:
        # IP-based rate limiting for unauthenticated requests
        is_allowed, remaining = check_rate_limit(client_ip)
        if not is_allowed:
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded",
                headers={"Retry-After": "3600"}
            )

    # Extract required fields
    glyph_code = payload.get('glyph_code')
    if not glyph_code or len(glyph_code) != 12:
        raise HTTPException(status_code=400, detail="Invalid or missing glyph_code")

    # Decode glyph to get region coordinates
    try:
        glyph_coords = decode_glyph_to_coords(glyph_code)
        region_x = glyph_coords.get('region_x', 0)
        region_y = glyph_coords.get('region_y', 0)
        region_z = glyph_coords.get('region_z', 0)
    except Exception as e:
        logger.warning(f"Failed to decode glyph {glyph_code}: {e}")
        region_x = region_y = region_z = 0

    # Extract user identification fields (new in v10+)
    discord_username = payload.get('discord_username', '')
    personal_id = payload.get('personal_id', '')
    discord_tag = payload.get('discord_tag', 'personal')  # Default to personal if not specified
    reality = payload.get('reality', 'Normal')

    # Accept both star_color (v10+) and star_type (legacy)
    star_color = payload.get('star_color') or payload.get('star_type', 'Yellow')

    # Convert extraction format to submission format
    submission_data = {
        'name': payload.get('system_name', f"System_{glyph_code}"),
        'glyph_code': glyph_code,
        'galaxy': payload.get('galaxy_name', 'Euclid'),
        'reality': reality,
        'x': payload.get('voxel_x', 0),
        'y': payload.get('voxel_y', 0),
        'z': payload.get('voxel_z', 0),
        'region_x': region_x,
        'region_y': region_y,
        'region_z': region_z,
        'glyph_solar_system': payload.get('solar_system_index', 1),
        'star_color': star_color,
        'economy_type': payload.get('economy_type', 'Unknown'),
        'economy_level': payload.get('economy_strength', 'Unknown'),
        'conflict_level': payload.get('conflict_level', 'Unknown'),
        'dominant_lifeform': payload.get('dominant_lifeform', 'Unknown'),
        'discovered_by': payload.get('discoverer_name', 'HavenExtractor'),
        'discovered_at': payload.get('extraction_time'),
        'source': 'haven_extractor',
        'extractor_version': payload.get('extractor_version', 'unknown'),
    }

    # Convert planets array
    planets = []
    moons = []
    for planet_data in payload.get('planets', []):
        planet_entry = {
            'name': planet_data.get('planet_name', f"Planet_{planet_data.get('planet_index', 0) + 1}"),
            'biome': planet_data.get('biome', 'Unknown'),
            'biome_subtype': planet_data.get('biome_subtype', 'Unknown'),
            'weather': planet_data.get('weather', 'Unknown'),
            'climate': planet_data.get('weather', 'Unknown'),  # Alias for Haven UI compatibility
            'sentinels': planet_data.get('sentinel_level', 'Unknown'),
            'sentinel': planet_data.get('sentinel_level', 'Unknown'),  # Alias for Haven UI compatibility
            'flora': planet_data.get('flora_level', 'Unknown'),
            'fauna': planet_data.get('fauna_level', 'Unknown'),
            'planet_size': planet_data.get('planet_size', 'Unknown'),
            'resources': [
                r for r in [
                    planet_data.get('common_resource'),
                    planet_data.get('uncommon_resource'),
                    planet_data.get('rare_resource')
                ] if r and r != 'Unknown'
            ],
            'materials': ', '.join([
                r for r in [
                    planet_data.get('common_resource'),
                    planet_data.get('uncommon_resource'),
                    planet_data.get('rare_resource')
                ] if r and r != 'Unknown'
            ]),  # Comma-separated for Haven UI display
        }

        if planet_data.get('is_moon', False):
            moons.append(planet_entry)
        else:
            planets.append(planet_entry)

    submission_data['planets'] = planets
    submission_data['moons'] = moons

    # Store in pending_systems for admin review
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Server-side duplicate check: Check if system already exists in APPROVED systems
        cursor.execute('''
            SELECT id, name FROM systems
            WHERE glyph_code = ?
        ''', (glyph_code,))
        existing_approved = cursor.fetchone()

        if existing_approved:
            logger.info(f"Extraction rejected - system already charted: {glyph_code} as '{existing_approved[1]}'")
            return JSONResponse({
                'status': 'already_charted',
                'message': f'System already exists as "{existing_approved[1]}"',
                'existing_system_id': existing_approved[0],
                'glyph_code': glyph_code
            }, status_code=409)  # Conflict

        # Check for duplicate in pending submissions
        cursor.execute('''
            SELECT id, status FROM pending_systems
            WHERE glyph_code = ? AND status = 'pending'
        ''', (glyph_code,))
        existing_pending = cursor.fetchone()

        if existing_pending:
            # Update existing pending submission with new data
            cursor.execute('''
                UPDATE pending_systems
                SET raw_json = ?, system_data = ?, submission_timestamp = ?,
                    discord_tag = ?, personal_discord_username = ?, personal_id = ?,
                    system_name = ?, galaxy = ?, region_x = ?, region_y = ?, region_z = ?,
                    x = ?, y = ?, z = ?
                WHERE id = ?
            ''', (
                json.dumps(submission_data),
                json.dumps(submission_data),
                datetime.now(timezone.utc).isoformat(),
                discord_tag if discord_tag else None,
                discord_username if discord_username else None,
                personal_id if personal_id else None,
                submission_data['name'],
                submission_data['galaxy'],
                region_x,
                region_y,
                region_z,
                submission_data['x'],
                submission_data['y'],
                submission_data['z'],
                existing_pending[0]
            ))
            conn.commit()

            logger.info(f"Updated pending extraction for {glyph_code} (discord_tag={discord_tag})")
            return JSONResponse({
                'status': 'updated',
                'message': f'Extraction updated for {glyph_code}',
                'submission_id': existing_pending[0],
                'planet_count': len(planets),
                'moon_count': len(moons)
            })

        # Insert new pending submission with all fields
        now = datetime.now(timezone.utc).isoformat()
        raw_json_str = json.dumps(submission_data)

        # Get API key name for tracking (if authenticated)
        api_key_name = api_key_info.get('name') if api_key_info else None

        cursor.execute('''
            INSERT INTO pending_systems (
                system_name, glyph_code, galaxy, x, y, z,
                region_x, region_y, region_z,
                submitter_name, submission_timestamp, submission_date, status, source,
                raw_json, system_data, discord_tag, personal_discord_username, personal_id,
                submitted_by_ip, api_key_name
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            submission_data['name'],
            glyph_code,
            submission_data['galaxy'],
            submission_data['x'],
            submission_data['y'],
            submission_data['z'],
            region_x,
            region_y,
            region_z,
            discord_username if discord_username else 'HavenExtractor',
            now,
            now,  # submission_date
            'pending',
            'haven_extractor',
            raw_json_str,
            raw_json_str,  # system_data (same as raw_json)
            discord_tag if discord_tag else None,
            discord_username if discord_username else None,
            personal_id if personal_id else None,
            client_ip,
            api_key_name
        ))
        conn.commit()
        submission_id = cursor.lastrowid

        logger.info(f"Received extraction from Haven Extractor: {glyph_code} with {len(planets)} planets, {len(moons)} moons (discord_tag={discord_tag}, user={discord_username})")

        return JSONResponse({
            'status': 'ok',
            'message': f'Extraction received for {glyph_code}',
            'submission_id': submission_id,
            'planet_count': len(planets),
            'moon_count': len(moons)
        }, status_code=201)

    except Exception as e:
        logger.error(f"Error storing extraction: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()


# =============================================================================
# WAR ROOM API ENDPOINTS
# =============================================================================
# Territorial conflict tracking system for enrolled civilizations
# =============================================================================


def get_war_room_partner_info(session: dict) -> dict:
    """Get partner info for War Room operations. Returns None if not enrolled."""
    if not session:
        return None

    user_type = session.get('user_type')
    partner_id = None

    if user_type == 'super_admin':
        return {'is_super_admin': True, 'partner_id': None}

    if user_type == 'partner':
        partner_id = session.get('partner_id')
    elif user_type == 'sub_admin':
        # Sub-admin's parent partner is stored as 'partner_id' in session
        partner_id = session.get('partner_id')

    if not partner_id:
        return None

    # Check if enrolled in War Room
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            SELECT wre.id, pa.display_name, pa.discord_tag, pa.region_color
            FROM war_room_enrollment wre
            JOIN partner_accounts pa ON wre.partner_id = pa.id
            WHERE wre.partner_id = ? AND wre.is_active = 1
        ''', (partner_id,))
        row = cursor.fetchone()
        if not row:
            return None

        return {
            'is_super_admin': False,
            'partner_id': partner_id,
            'enrollment_id': row[0],
            'display_name': row[1],
            'discord_tag': row[2],
            'region_color': row[3]
        }
    finally:
        conn.close()


async def send_war_notification(
    partner_id: int,
    notification_type: str,
    title: str,
    message: str,
    conflict_id: int = None
):
    """Create in-app notification and optionally send Discord webhook."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Create in-app notification
        cursor.execute('''
            INSERT INTO war_notifications (recipient_partner_id, notification_type, title, message, related_conflict_id)
            VALUES (?, ?, ?, ?, ?)
        ''', (partner_id, notification_type, title, message, conflict_id))
        conn.commit()

        # Check for Discord webhook
        cursor.execute('''
            SELECT webhook_url FROM discord_webhooks
            WHERE partner_id = ? AND is_active = 1
        ''', (partner_id,))
        webhook_row = cursor.fetchone()

        if webhook_row and webhook_row[0]:
            webhook_url = webhook_row[0]
            # Send webhook using requests (fire and forget)
            import requests as req_lib
            embed = {
                "title": f"WAR ROOM: {title}",
                "description": message,
                "color": 15158332,  # Red
                "footer": {"text": "Haven War Room"},
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            try:
                req_lib.post(webhook_url, json={"embeds": [embed]}, timeout=5)
                cursor.execute('''
                    UPDATE discord_webhooks SET last_triggered_at = ? WHERE partner_id = ?
                ''', (datetime.now(timezone.utc).isoformat(), partner_id))
                conn.commit()
            except Exception as e:
                logger.warning(f"Failed to send War Room webhook to partner {partner_id}: {e}")
    finally:
        conn.close()


# --- Enrollment Endpoints ---

@app.get('/api/warroom/enrollment')
async def get_war_room_enrollment(session: Optional[str] = Cookie(None)):
    """List all enrolled civs in War Room."""
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail="Not authenticated")

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            SELECT wre.id, wre.partner_id, pa.display_name, pa.discord_tag, pa.region_color,
                   wre.enrolled_at, wre.enrolled_by, wre.is_active,
                   wre.home_region_x, wre.home_region_y, wre.home_region_z,
                   wre.home_region_name, wre.home_galaxy
            FROM war_room_enrollment wre
            JOIN partner_accounts pa ON wre.partner_id = pa.id
            WHERE wre.is_active = 1
            ORDER BY wre.enrolled_at DESC
        ''')
        rows = cursor.fetchall()

        return [{
            'id': r[0],
            'partner_id': r[1],
            'display_name': r[2],
            'discord_tag': r[3],
            'region_color': r[4],
            'enrolled_at': r[5],
            'enrolled_by': r[6],
            'is_active': r[7],
            'home_region_x': r[8],
            'home_region_y': r[9],
            'home_region_z': r[10],
            'home_region_name': r[11],
            'home_galaxy': r[12]
        } for r in rows]
    finally:
        conn.close()


@app.post('/api/warroom/enrollment')
async def enroll_in_war_room(request: Request, session: Optional[str] = Cookie(None)):
    """Enroll a partner in War Room (super admin only)."""
    session_data = get_session(session)
    if not session_data or session_data.get('user_type') != 'super_admin':
        raise HTTPException(status_code=403, detail="Super admin access required")

    data = await request.json()
    partner_id = data.get('partner_id')
    if not partner_id:
        raise HTTPException(status_code=400, detail="partner_id required")

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Check partner exists and get current enabled_features + discord_tag
        cursor.execute('SELECT id, display_name, enabled_features, discord_tag FROM partner_accounts WHERE id = ?', (partner_id,))
        partner = cursor.fetchone()
        if not partner:
            raise HTTPException(status_code=404, detail="Partner not found")

        discord_tag = partner[3]

        # Check if already enrolled (only check active enrollments)
        cursor.execute('SELECT id, is_active FROM war_room_enrollment WHERE partner_id = ?', (partner_id,))
        existing = cursor.fetchone()
        if existing:
            if existing[1] == 1:  # is_active = 1
                raise HTTPException(status_code=409, detail="Partner already enrolled")
            else:
                # Re-activate existing enrollment
                cursor.execute('''
                    UPDATE war_room_enrollment SET is_active = 1, enrolled_by = ?, enrolled_at = datetime('now')
                    WHERE partner_id = ?
                ''', (session_data.get('username'), partner_id))
        else:
            # Add new enrollment
            cursor.execute('''
                INSERT INTO war_room_enrollment (partner_id, enrolled_by)
                VALUES (?, ?)
            ''', (partner_id, session_data.get('username')))

        # Also add 'war_room' to partner's enabled_features so navbar shows the tab
        current_features = json.loads(partner[2] or '[]')
        if 'war_room' not in current_features:
            current_features.append('war_room')
            cursor.execute('''
                UPDATE partner_accounts SET enabled_features = ? WHERE id = ?
            ''', (json.dumps(current_features), partner_id))

        # Auto-claim all systems with this partner's discord_tag as initial territory
        systems_claimed = 0
        if discord_tag:
            cursor.execute('''
                SELECT id, name, region_x, region_y, region_z, galaxy, reality
                FROM systems
                WHERE discord_tag = ?
            ''', (discord_tag,))
            systems = cursor.fetchall()

            for system in systems:
                system_id, name, region_x, region_y, region_z, galaxy, reality = system
                # Check if already claimed
                cursor.execute('SELECT id FROM territorial_claims WHERE system_id = ?', (system_id,))
                if not cursor.fetchone():
                    cursor.execute('''
                        INSERT INTO territorial_claims (system_id, claimant_partner_id, region_x, region_y, region_z, galaxy, reality, claim_type, notes)
                        VALUES (?, ?, ?, ?, ?, ?, ?, 'initial', 'Auto-claimed on enrollment')
                    ''', (system_id, partner_id, region_x, region_y, region_z, galaxy, reality))
                    systems_claimed += 1

            logger.info(f"War Room: Auto-claimed {systems_claimed} systems for {partner[1]} based on discord_tag '{discord_tag}'")

        conn.commit()

        logger.info(f"War Room: Enrolled {partner[1]} (ID: {partner_id})")
        return {
            'status': 'enrolled',
            'partner_id': partner_id,
            'display_name': partner[1],
            'systems_claimed': systems_claimed
        }
    finally:
        conn.close()


@app.delete('/api/warroom/enrollment/{partner_id}')
async def unenroll_from_war_room(partner_id: int, session: Optional[str] = Cookie(None)):
    """Unenroll a partner from War Room (super admin only)."""
    session_data = get_session(session)
    if not session_data or session_data.get('user_type') != 'super_admin':
        raise HTTPException(status_code=403, detail="Super admin access required")

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            UPDATE war_room_enrollment SET is_active = 0 WHERE partner_id = ?
        ''', (partner_id,))
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Enrollment not found")

        # Also remove 'war_room' from partner's enabled_features
        cursor.execute('SELECT enabled_features FROM partner_accounts WHERE id = ?', (partner_id,))
        row = cursor.fetchone()
        if row:
            current_features = json.loads(row[0] or '[]')
            if 'war_room' in current_features:
                current_features.remove('war_room')
                cursor.execute('''
                    UPDATE partner_accounts SET enabled_features = ? WHERE id = ?
                ''', (json.dumps(current_features), partner_id))

        conn.commit()

        logger.info(f"War Room: Unenrolled partner ID {partner_id}")
        return {'status': 'unenrolled', 'partner_id': partner_id}
    finally:
        conn.close()


@app.get('/api/warroom/enrollment/status')
async def get_enrollment_status(session: Optional[str] = Cookie(None)):
    """Check if current user's civ is enrolled in War Room."""
    try:
        session_data = get_session(session)

        # Check if correspondent
        if session_data and session_data.get('user_type') == 'correspondent':
            return {
                'enrolled': False,
                'is_correspondent': True,
                'display_name': session_data.get('display_name', session_data.get('username'))
            }

        partner_info = get_war_room_partner_info(session_data)

        if partner_info and partner_info.get('is_super_admin'):
            return {'enrolled': True, 'is_super_admin': True}

        if not partner_info:
            return {'enrolled': False}

        return {
            'enrolled': True,
            'partner_id': partner_info['partner_id'],
            'display_name': partner_info['display_name'],
            'discord_tag': partner_info['discord_tag'],
            'region_color': partner_info['region_color']
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_enrollment_status: {type(e).__name__}: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Internal error: {type(e).__name__}: {str(e)}")


@app.put('/api/warroom/enrollment/{partner_id}/home-region')
async def set_home_region(partner_id: int, request: Request, session: Optional[str] = Cookie(None)):
    """Set home region for an enrolled civilization (super admin or own civ)."""
    session_data = get_session(session)
    partner_info = get_war_room_partner_info(session_data)

    if not partner_info:
        raise HTTPException(status_code=403, detail="Must be enrolled in War Room")

    # Allow super admin or the partner themselves
    is_super_admin = partner_info.get('is_super_admin')
    is_own_civ = partner_info.get('partner_id') == partner_id

    if not is_super_admin and not is_own_civ:
        raise HTTPException(status_code=403, detail="Can only set home region for your own civilization")

    data = await request.json()
    region_x = data.get('region_x')
    region_y = data.get('region_y')
    region_z = data.get('region_z')
    region_name = data.get('region_name')
    galaxy = data.get('galaxy', 'Euclid')

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Check enrollment exists
        cursor.execute('SELECT id FROM war_room_enrollment WHERE partner_id = ? AND is_active = 1', (partner_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Enrollment not found")

        cursor.execute('''
            UPDATE war_room_enrollment
            SET home_region_x = ?, home_region_y = ?, home_region_z = ?,
                home_region_name = ?, home_galaxy = ?
            WHERE partner_id = ?
        ''', (region_x, region_y, region_z, region_name, galaxy, partner_id))
        conn.commit()

        logger.info(f"War Room: Set home region for partner {partner_id}: ({region_x}, {region_y}, {region_z})")
        return {'status': 'updated', 'partner_id': partner_id}
    finally:
        conn.close()


@app.post('/api/warroom/enrollment/{partner_id}/sync-territory')
async def sync_territory(partner_id: int, session: Optional[str] = Cookie(None)):
    """Sync territory claims for an enrolled civilization based on their discord_tag.
    This adds any new systems with their discord_tag that aren't already claimed.
    Super admin only."""
    session_data = get_session(session)
    if not session_data or session_data.get('user_type') != 'super_admin':
        raise HTTPException(status_code=403, detail="Super admin access required")

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Get partner's discord_tag
        cursor.execute('''
            SELECT pa.discord_tag, pa.display_name
            FROM partner_accounts pa
            JOIN war_room_enrollment wre ON pa.id = wre.partner_id
            WHERE wre.partner_id = ? AND wre.is_active = 1
        ''', (partner_id,))
        partner = cursor.fetchone()
        if not partner:
            raise HTTPException(status_code=404, detail="Enrollment not found")

        discord_tag = partner[0]
        display_name = partner[1]

        if not discord_tag:
            return {'status': 'skipped', 'message': 'Partner has no discord_tag', 'systems_claimed': 0}

        # Find all systems with this discord_tag that aren't already claimed
        cursor.execute('''
            SELECT s.id, s.name, s.region_x, s.region_y, s.region_z, s.galaxy, s.reality
            FROM systems s
            WHERE s.discord_tag = ?
            AND s.id NOT IN (SELECT system_id FROM territorial_claims)
        ''', (discord_tag,))
        systems = cursor.fetchall()

        systems_claimed = 0
        for system in systems:
            system_id, name, region_x, region_y, region_z, galaxy, reality = system
            cursor.execute('''
                INSERT INTO territorial_claims (system_id, claimant_partner_id, region_x, region_y, region_z, galaxy, reality, claim_type, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'synced', 'Auto-synced from discord_tag')
            ''', (system_id, partner_id, region_x, region_y, region_z, galaxy, reality))
            systems_claimed += 1

        conn.commit()
        logger.info(f"War Room: Synced {systems_claimed} new systems for {display_name}")

        return {
            'status': 'synced',
            'partner_id': partner_id,
            'display_name': display_name,
            'systems_claimed': systems_claimed
        }
    finally:
        conn.close()


@app.post('/api/warroom/sync-all-territory')
async def sync_all_territory(session: Optional[str] = Cookie(None)):
    """Sync territory claims for ALL enrolled civilizations. Super admin only."""
    session_data = get_session(session)
    if not session_data or session_data.get('user_type') != 'super_admin':
        raise HTTPException(status_code=403, detail="Super admin access required")

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Get all enrolled partners with their discord_tags
        cursor.execute('''
            SELECT pa.id, pa.discord_tag, pa.display_name
            FROM partner_accounts pa
            JOIN war_room_enrollment wre ON pa.id = wre.partner_id
            WHERE wre.is_active = 1 AND pa.discord_tag IS NOT NULL
        ''')
        partners = cursor.fetchall()

        total_systems = 0
        results = []

        for partner_id, discord_tag, display_name in partners:
            # Find systems with this discord_tag that aren't claimed
            cursor.execute('''
                SELECT s.id, s.name, s.region_x, s.region_y, s.region_z, s.galaxy, s.reality
                FROM systems s
                WHERE s.discord_tag = ?
                AND s.id NOT IN (SELECT system_id FROM territorial_claims)
            ''', (discord_tag,))
            systems = cursor.fetchall()

            partner_claimed = 0
            for system in systems:
                system_id, name, region_x, region_y, region_z, galaxy, reality = system
                cursor.execute('''
                    INSERT INTO territorial_claims (system_id, claimant_partner_id, region_x, region_y, region_z, galaxy, reality, claim_type, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 'synced', 'Auto-synced from discord_tag')
                ''', (system_id, partner_id, region_x, region_y, region_z, galaxy, reality))
                partner_claimed += 1

            total_systems += partner_claimed
            if partner_claimed > 0:
                results.append({'display_name': display_name, 'systems_claimed': partner_claimed})

        conn.commit()
        logger.info(f"War Room: Bulk sync completed - {total_systems} total systems across {len(results)} civs")

        return {
            'status': 'synced',
            'total_systems_claimed': total_systems,
            'civs_updated': results
        }
    finally:
        conn.close()


@app.get('/api/warroom/region-search')
async def search_regions_for_warroom(search: str = '', limit: int = 20, session: Optional[str] = Cookie(None)):
    """Search for regions by name or coordinates. Searches both named regions and regions with systems."""
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail="Not authenticated")

    if not search or len(search) < 2:
        return []

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        results = []
        search_lower = search.lower()

        # First, search named regions
        cursor.execute('''
            SELECT r.region_x, r.region_y, r.region_z, r.custom_name as name, r.galaxy,
                   (SELECT COUNT(*) FROM systems s
                    WHERE s.region_x = r.region_x AND s.region_y = r.region_y AND s.region_z = r.region_z) as system_count
            FROM regions r
            WHERE LOWER(r.custom_name) LIKE ?
            ORDER BY r.custom_name
            LIMIT ?
        ''', (f'%{search_lower}%', limit))

        for row in cursor.fetchall():
            results.append({
                'region_x': row[0],
                'region_y': row[1],
                'region_z': row[2],
                'name': row[3],
                'region_name': row[3],
                'galaxy': row[4] or 'Euclid',
                'system_count': row[5],
                'source': 'named'
            })

        # Also search for systems whose names match (to find regions by system name)
        if len(results) < limit:
            remaining = limit - len(results)
            cursor.execute('''
                SELECT DISTINCT s.region_x, s.region_y, s.region_z, s.galaxy,
                       r.custom_name as region_name,
                       (SELECT COUNT(*) FROM systems s2
                        WHERE s2.region_x = s.region_x AND s2.region_y = s.region_y AND s2.region_z = s.region_z) as system_count,
                       GROUP_CONCAT(s.name, ', ') as sample_systems
                FROM systems s
                LEFT JOIN regions r ON s.region_x = r.region_x AND s.region_y = r.region_y AND s.region_z = r.region_z
                WHERE LOWER(s.name) LIKE ?
                GROUP BY s.region_x, s.region_y, s.region_z
                LIMIT ?
            ''', (f'%{search_lower}%', remaining))

            seen_coords = {(r['region_x'], r['region_y'], r['region_z']) for r in results}
            for row in cursor.fetchall():
                coords = (row[0], row[1], row[2])
                if coords not in seen_coords:
                    results.append({
                        'region_x': row[0],
                        'region_y': row[1],
                        'region_z': row[2],
                        'name': row[4] or f"Region ({row[0]}, {row[1]}, {row[2]})",
                        'region_name': row[4],
                        'galaxy': row[3] or 'Euclid',
                        'system_count': row[5],
                        'sample_systems': row[6][:100] if row[6] else None,  # Truncate
                        'source': 'system_match'
                    })
                    seen_coords.add(coords)

        # Also try to parse as coordinates (e.g., "123, 456, 789" or "123 456 789")
        import re
        coord_match = re.match(r'[-]?\d+[,\s]+[-]?\d+[,\s]+[-]?\d+', search.strip())
        if coord_match and len(results) < limit:
            parts = re.split(r'[,\s]+', search.strip())
            if len(parts) >= 3:
                try:
                    rx, ry, rz = int(parts[0]), int(parts[1]), int(parts[2])
                    # Check if we already have this
                    if (rx, ry, rz) not in {(r['region_x'], r['region_y'], r['region_z']) for r in results}:
                        # Look up the region
                        cursor.execute('''
                            SELECT r.custom_name,
                                   (SELECT COUNT(*) FROM systems s
                                    WHERE s.region_x = ? AND s.region_y = ? AND s.region_z = ?) as system_count,
                                   (SELECT galaxy FROM systems WHERE region_x = ? AND region_y = ? AND region_z = ? LIMIT 1) as galaxy
                            FROM regions r
                            WHERE r.region_x = ? AND r.region_y = ? AND r.region_z = ?
                        ''', (rx, ry, rz, rx, ry, rz, rx, ry, rz))
                        row = cursor.fetchone()
                        results.insert(0, {  # Put coordinate match first
                            'region_x': rx,
                            'region_y': ry,
                            'region_z': rz,
                            'name': row[0] if row and row[0] else f"Region ({rx}, {ry}, {rz})",
                            'region_name': row[0] if row else None,
                            'galaxy': row[2] if row and row[2] else 'Euclid',
                            'system_count': row[1] if row else 0,
                            'source': 'coordinates'
                        })
                except ValueError:
                    pass

        return results[:limit]
    finally:
        conn.close()


@app.get('/api/warroom/home-regions')
async def get_home_regions(session: Optional[str] = Cookie(None)):
    """Get home regions for all enrolled civilizations."""
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail="Not authenticated")

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            SELECT wre.partner_id, pa.display_name, pa.region_color,
                   wre.home_region_x, wre.home_region_y, wre.home_region_z,
                   wre.home_region_name, wre.home_galaxy
            FROM war_room_enrollment wre
            JOIN partner_accounts pa ON wre.partner_id = pa.id
            WHERE wre.is_active = 1 AND wre.home_region_x IS NOT NULL
        ''')
        rows = cursor.fetchall()

        return [{
            'partner_id': r[0],
            'display_name': r[1],
            'region_color': r[2],
            'region_x': r[3],
            'region_y': r[4],
            'region_z': r[5],
            'region_name': r[6],
            'galaxy': r[7]
        } for r in rows]
    finally:
        conn.close()


# --- Territorial Claims Endpoints ---

@app.get('/api/warroom/claims')
async def get_territorial_claims(partner_id: int = None, session: Optional[str] = Cookie(None)):
    """List all territorial claims, optionally filtered by partner."""
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail="Not authenticated")

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        query = '''
            SELECT tc.id, tc.system_id, tc.claimant_partner_id, pa.display_name, pa.discord_tag,
                   pa.region_color, tc.claimed_at, tc.claim_type, tc.region_x, tc.region_y, tc.region_z,
                   tc.galaxy, tc.reality, tc.notes, s.name as system_name
            FROM territorial_claims tc
            JOIN partner_accounts pa ON tc.claimant_partner_id = pa.id
            LEFT JOIN systems s ON tc.system_id = s.id
        '''
        params = []
        if partner_id:
            query += ' WHERE tc.claimant_partner_id = ?'
            params.append(partner_id)
        query += ' ORDER BY tc.claimed_at DESC'

        cursor.execute(query, params)
        rows = cursor.fetchall()

        return [{
            'id': r[0],
            'system_id': r[1],
            'claimant_partner_id': r[2],
            'claimant_display_name': r[3],
            'claimant_discord_tag': r[4],
            'claimant_color': r[5],
            'claimed_at': r[6],
            'claim_type': r[7],
            'region_x': r[8],
            'region_y': r[9],
            'region_z': r[10],
            'galaxy': r[11],
            'reality': r[12],
            'notes': r[13],
            'system_name': r[14]
        } for r in rows]
    finally:
        conn.close()


@app.post('/api/warroom/claims')
async def create_territorial_claim(request: Request, session: Optional[str] = Cookie(None)):
    """Claim a system for your civilization."""
    session_data = get_session(session)
    partner_info = get_war_room_partner_info(session_data)
    if not partner_info:
        raise HTTPException(status_code=403, detail="Must be enrolled in War Room")

    data = await request.json()
    system_id = data.get('system_id')
    if not system_id:
        raise HTTPException(status_code=400, detail="system_id required")

    # Super admin can claim for any partner
    partner_id = data.get('partner_id') if partner_info.get('is_super_admin') else partner_info['partner_id']
    if not partner_id:
        raise HTTPException(status_code=400, detail="partner_id required for super admin")

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Get system info
        cursor.execute('''
            SELECT id, name, region_x, region_y, region_z, galaxy, reality
            FROM systems WHERE id = ?
        ''', (system_id,))
        system = cursor.fetchone()
        if not system:
            raise HTTPException(status_code=404, detail="System not found")

        # Check if already claimed
        cursor.execute('SELECT id, claimant_partner_id FROM territorial_claims WHERE system_id = ?', (system_id,))
        existing = cursor.fetchone()
        if existing:
            raise HTTPException(status_code=409, detail="System already claimed by another civilization")

        cursor.execute('''
            INSERT INTO territorial_claims (system_id, claimant_partner_id, region_x, region_y, region_z, galaxy, reality, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (system_id, partner_id, system[2], system[3], system[4], system[5], system[6], data.get('notes')))
        conn.commit()

        logger.info(f"War Room: Partner {partner_id} claimed system {system[1]} ({system_id})")
        return {'status': 'claimed', 'claim_id': cursor.lastrowid, 'system_name': system[1]}
    finally:
        conn.close()


@app.delete('/api/warroom/claims/{claim_id}')
async def release_territorial_claim(claim_id: int, session: Optional[str] = Cookie(None)):
    """Release a territorial claim."""
    session_data = get_session(session)
    partner_info = get_war_room_partner_info(session_data)
    if not partner_info:
        raise HTTPException(status_code=403, detail="Must be enrolled in War Room")

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Check ownership
        cursor.execute('SELECT claimant_partner_id FROM territorial_claims WHERE id = ?', (claim_id,))
        claim = cursor.fetchone()
        if not claim:
            raise HTTPException(status_code=404, detail="Claim not found")

        if not partner_info.get('is_super_admin') and claim[0] != partner_info['partner_id']:
            raise HTTPException(status_code=403, detail="Can only release your own claims")

        cursor.execute('DELETE FROM territorial_claims WHERE id = ?', (claim_id,))
        conn.commit()

        return {'status': 'released', 'claim_id': claim_id}
    finally:
        conn.close()


# --- Conflict Management Endpoints ---

@app.get('/api/warroom/conflicts')
async def get_conflicts(status: str = None, partner_id: int = None, session: Optional[str] = Cookie(None)):
    """List conflicts with optional filters."""
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail="Not authenticated")

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        query = '''
            SELECT c.id, c.target_system_id, c.target_system_name,
                   c.attacker_partner_id, att.display_name, att.region_color,
                   c.defender_partner_id, def.display_name, def.region_color,
                   c.declared_at, c.declared_by, c.acknowledged_at, c.resolved_at,
                   c.status, c.resolution, c.victor_partner_id, c.notes
            FROM conflicts c
            JOIN partner_accounts att ON c.attacker_partner_id = att.id
            JOIN partner_accounts def ON c.defender_partner_id = def.id
            WHERE 1=1
        '''
        params = []
        if status:
            query += ' AND c.status = ?'
            params.append(status)
        if partner_id:
            query += ' AND (c.attacker_partner_id = ? OR c.defender_partner_id = ?)'
            params.extend([partner_id, partner_id])
        query += ' ORDER BY c.declared_at DESC'

        cursor.execute(query, params)
        rows = cursor.fetchall()

        return [{
            'id': r[0],
            'target_system_id': r[1],
            'target_system_name': r[2],
            'attacker': {'partner_id': r[3], 'display_name': r[4], 'color': r[5]},
            'defender': {'partner_id': r[6], 'display_name': r[7], 'color': r[8]},
            'declared_at': r[9],
            'declared_by': r[10],
            'acknowledged_at': r[11],
            'resolved_at': r[12],
            'status': r[13],
            'resolution': r[14],
            'victor_partner_id': r[15],
            'notes': r[16]
        } for r in rows]
    finally:
        conn.close()


@app.get('/api/warroom/conflicts/active')
async def get_active_conflicts(include_practice: bool = False, session: Optional[str] = Cookie(None)):
    """Get currently active conflicts for the live feed.

    Args:
        include_practice: If True, include practice conflicts (default: False)
    """
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail="Not authenticated")

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Filter out practice conflicts by default
        practice_filter = "" if include_practice else "AND (c.is_practice IS NULL OR c.is_practice = 0)"
        cursor.execute(f'''
            SELECT c.id, c.target_system_id, c.target_system_name,
                   att.display_name as attacker_name, att.region_color as attacker_color,
                   def.display_name as defender_name, def.region_color as defender_color,
                   c.declared_at, c.status, COALESCE(c.is_practice, 0) as is_practice
            FROM conflicts c
            JOIN partner_accounts att ON c.attacker_partner_id = att.id
            JOIN partner_accounts def ON c.defender_partner_id = def.id
            WHERE c.status IN ('pending', 'acknowledged', 'active')
            {practice_filter}
            ORDER BY c.declared_at DESC
        ''')
        rows = cursor.fetchall()

        return [{
            'id': r[0],
            'target_system_id': r[1],
            'target_system_name': r[2],
            'attacker_name': r[3],
            'attacker_color': r[4],
            'defender_name': r[5],
            'defender_color': r[6],
            'declared_at': r[7],
            'status': r[8],
            'is_practice': bool(r[9])
        } for r in rows]
    finally:
        conn.close()


@app.get('/api/warroom/conflicts/{conflict_id}')
async def get_conflict_detail(conflict_id: int, session: Optional[str] = Cookie(None)):
    """Get conflict details including timeline."""
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail="Not authenticated")

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Get conflict
        cursor.execute('''
            SELECT c.id, c.target_system_id, c.target_system_name,
                   c.attacker_partner_id, att.display_name, att.region_color,
                   c.defender_partner_id, def.display_name, def.region_color,
                   c.declared_at, c.declared_by, c.acknowledged_at, c.acknowledged_by,
                   c.resolved_at, c.resolved_by, c.status, c.resolution, c.victor_partner_id, c.notes,
                   COALESCE(c.is_practice, 0) as is_practice
            FROM conflicts c
            JOIN partner_accounts att ON c.attacker_partner_id = att.id
            JOIN partner_accounts def ON c.defender_partner_id = def.id
            WHERE c.id = ?
        ''', (conflict_id,))
        r = cursor.fetchone()
        if not r:
            raise HTTPException(status_code=404, detail="Conflict not found")

        # Get timeline events
        cursor.execute('''
            SELECT id, event_type, event_at, actor_username, details
            FROM conflict_events
            WHERE conflict_id = ?
            ORDER BY event_at ASC
        ''', (conflict_id,))
        events = cursor.fetchall()

        return {
            'id': r[0],
            'target_system_id': r[1],
            'target_system_name': r[2],
            'attacker': {'partner_id': r[3], 'display_name': r[4], 'color': r[5]},
            'defender': {'partner_id': r[6], 'display_name': r[7], 'color': r[8]},
            'declared_at': r[9],
            'declared_by': r[10],
            'acknowledged_at': r[11],
            'acknowledged_by': r[12],
            'resolved_at': r[13],
            'resolved_by': r[14],
            'status': r[15],
            'resolution': r[16],
            'victor_partner_id': r[17],
            'notes': r[18],
            'is_practice': bool(r[19]),
            'timeline': [{
                'id': e[0],
                'event_type': e[1],
                'event_at': e[2],
                'actor': e[3],
                'details': e[4]
            } for e in events]
        }
    finally:
        conn.close()


@app.post('/api/warroom/conflicts')
async def declare_conflict(request: Request, session: Optional[str] = Cookie(None)):
    """Declare an attack on another civ's territory."""
    session_data = get_session(session)
    partner_info = get_war_room_partner_info(session_data)
    if not partner_info:
        raise HTTPException(status_code=403, detail="Must be enrolled in War Room")

    data = await request.json()
    target_system_id = data.get('target_system_id')
    if not target_system_id:
        raise HTTPException(status_code=400, detail="target_system_id required")

    attacker_id = data.get('attacker_partner_id') if partner_info.get('is_super_admin') else partner_info['partner_id']
    if not attacker_id:
        raise HTTPException(status_code=400, detail="attacker_partner_id required for super admin")

    # Practice mode - creates a conflict that doesn't affect real stats
    is_practice = data.get('is_practice', False)

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Find the claim on this system
        cursor.execute('''
            SELECT tc.claimant_partner_id, pa.display_name, s.name
            FROM territorial_claims tc
            JOIN partner_accounts pa ON tc.claimant_partner_id = pa.id
            LEFT JOIN systems s ON tc.system_id = s.id
            WHERE tc.system_id = ?
        ''', (target_system_id,))
        claim = cursor.fetchone()
        if not claim:
            raise HTTPException(status_code=404, detail="System not claimed by any civilization")

        defender_id = claim[0]
        defender_name = claim[1]
        system_name = claim[2] or target_system_id

        if defender_id == attacker_id:
            raise HTTPException(status_code=400, detail="Cannot attack your own territory")

        # Check for existing active conflict on this system
        cursor.execute('''
            SELECT id FROM conflicts
            WHERE target_system_id = ? AND status IN ('pending', 'acknowledged', 'active')
        ''', (target_system_id,))
        if cursor.fetchone():
            raise HTTPException(status_code=409, detail="Active conflict already exists for this system")

        # Create conflict
        username = session_data.get('username')
        cursor.execute('''
            INSERT INTO conflicts (target_system_id, target_system_name, attacker_partner_id, defender_partner_id, declared_by, is_practice)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (target_system_id, system_name, attacker_id, defender_id, username, 1 if is_practice else 0))
        conflict_id = cursor.lastrowid

        # Add declaration event
        event_details = f"{'[PRACTICE] ' if is_practice else ''}Attack declared on {system_name}"
        cursor.execute('''
            INSERT INTO conflict_events (conflict_id, event_type, actor_partner_id, actor_username, details)
            VALUES (?, 'declared', ?, ?, ?)
        ''', (conflict_id, attacker_id, username, event_details))
        conn.commit()

        attacker_name = partner_info.get('display_name', 'Unknown')

        # Skip notifications and activity feed for practice conflicts
        if not is_practice:
            # Send notification to defender
            await send_war_notification(
                defender_id,
                'attack_declared',
                f"Attack Declaration: {system_name}",
                f"{attacker_name} has declared an attack on {system_name}! Respond to acknowledge the conflict.",
                conflict_id
            )

            # Add to public activity feed
            await add_activity_feed_entry(
                event_type='war_declared',
                headline=f"{attacker_name} declares war on {defender_name}",
                actor_partner_id=attacker_id,
                actor_name=attacker_name,
                target_partner_id=defender_id,
                target_name=defender_name,
                conflict_id=conflict_id,
                system_id=str(target_system_id),
                system_name=system_name,
                details=f"Attack declared on system {system_name}. Awaiting defender acknowledgement.",
                is_public=True
            )

        practice_label = " (PRACTICE)" if is_practice else ""
        logger.info(f"War Room: Conflict declared{practice_label} - {attacker_name} attacking {defender_name} at {system_name}")
        return {'status': 'declared', 'conflict_id': conflict_id, 'target_system': system_name, 'is_practice': is_practice}
    finally:
        conn.close()


@app.put('/api/warroom/conflicts/{conflict_id}/acknowledge')
async def acknowledge_conflict(conflict_id: int, session: Optional[str] = Cookie(None)):
    """Defender acknowledges the conflict."""
    session_data = get_session(session)
    partner_info = get_war_room_partner_info(session_data)
    if not partner_info:
        raise HTTPException(status_code=403, detail="Must be enrolled in War Room")

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Get conflict
        cursor.execute('''
            SELECT defender_partner_id, attacker_partner_id, status, target_system_name
            FROM conflicts WHERE id = ?
        ''', (conflict_id,))
        conflict = cursor.fetchone()
        if not conflict:
            raise HTTPException(status_code=404, detail="Conflict not found")

        defender_id, attacker_id, status, system_name = conflict

        # Check authorization
        if not partner_info.get('is_super_admin') and partner_info['partner_id'] != defender_id:
            raise HTTPException(status_code=403, detail="Only the defender can acknowledge")

        if status != 'pending':
            raise HTTPException(status_code=400, detail="Conflict already acknowledged or resolved")

        username = session_data.get('username')
        now = datetime.now(timezone.utc).isoformat()

        cursor.execute('''
            UPDATE conflicts SET status = 'active', acknowledged_at = ?, acknowledged_by = ?
            WHERE id = ?
        ''', (now, username, conflict_id))

        cursor.execute('''
            INSERT INTO conflict_events (conflict_id, event_type, actor_partner_id, actor_username, details)
            VALUES (?, 'acknowledged', ?, ?, ?)
        ''', (conflict_id, defender_id, username, "Defender acknowledged the conflict - battle is now active"))
        conn.commit()

        # Notify attacker
        await send_war_notification(
            attacker_id,
            'conflict_update',
            f"Conflict Acknowledged: {system_name}",
            f"The defender has acknowledged your attack on {system_name}. The battle is now active!",
            conflict_id
        )

        # Get defender and attacker names for activity feed
        cursor.execute('SELECT display_name FROM partner_accounts WHERE id = ?', (defender_id,))
        defender_row = cursor.fetchone()
        defender_name = defender_row[0] if defender_row else 'Unknown'

        cursor.execute('SELECT display_name FROM partner_accounts WHERE id = ?', (attacker_id,))
        attacker_row = cursor.fetchone()
        attacker_name = attacker_row[0] if attacker_row else 'Unknown'

        # Add to public activity feed
        await add_activity_feed_entry(
            event_type='conflict_acknowledged',
            headline=f"{defender_name} accepts {attacker_name}'s challenge",
            actor_partner_id=defender_id,
            actor_name=defender_name,
            target_partner_id=attacker_id,
            target_name=attacker_name,
            conflict_id=conflict_id,
            system_name=system_name,
            details=f"Battle for {system_name} is now active!",
            is_public=True
        )

        logger.info(f"War Room: Conflict {conflict_id} acknowledged")
        return {'status': 'acknowledged', 'conflict_id': conflict_id}
    finally:
        conn.close()


@app.put('/api/warroom/conflicts/{conflict_id}/resolve')
async def resolve_conflict(conflict_id: int, request: Request, session: Optional[str] = Cookie(None)):
    """Resolve a conflict with a victor."""
    session_data = get_session(session)
    partner_info = get_war_room_partner_info(session_data)
    if not partner_info:
        raise HTTPException(status_code=403, detail="Must be enrolled in War Room")

    data = await request.json()
    resolution = data.get('resolution')  # attacker_victory, defender_victory, stalemate
    if resolution not in ['attacker_victory', 'defender_victory', 'stalemate', 'cancelled']:
        raise HTTPException(status_code=400, detail="Invalid resolution")

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            SELECT attacker_partner_id, defender_partner_id, status, target_system_id, target_system_name,
                   COALESCE(is_practice, 0) as is_practice
            FROM conflicts WHERE id = ?
        ''', (conflict_id,))
        conflict = cursor.fetchone()
        if not conflict:
            raise HTTPException(status_code=404, detail="Conflict not found")

        attacker_id, defender_id, status, system_id, system_name, is_practice = conflict

        # Check authorization - only super admin or involved parties
        if not partner_info.get('is_super_admin'):
            if partner_info['partner_id'] not in [attacker_id, defender_id]:
                raise HTTPException(status_code=403, detail="Only involved parties can resolve")

        if status == 'resolved':
            raise HTTPException(status_code=400, detail="Conflict already resolved")

        victor_id = None
        if resolution == 'attacker_victory':
            victor_id = attacker_id
        elif resolution == 'defender_victory':
            victor_id = defender_id

        username = session_data.get('username')
        now = datetime.now(timezone.utc).isoformat()

        practice_label = "[PRACTICE] " if is_practice else ""
        cursor.execute('''
            UPDATE conflicts SET status = 'resolved', resolution = ?, victor_partner_id = ?,
                   resolved_at = ?, resolved_by = ?
            WHERE id = ?
        ''', (resolution, victor_id, now, username, conflict_id))

        cursor.execute('''
            INSERT INTO conflict_events (conflict_id, event_type, actor_username, details)
            VALUES (?, 'resolved', ?, ?)
        ''', (conflict_id, username, f"{practice_label}Conflict resolved: {resolution}"))

        # Transfer territory if attacker won (skip for practice conflicts)
        if resolution == 'attacker_victory' and not is_practice:
            cursor.execute('''
                UPDATE territorial_claims SET claimant_partner_id = ?, claimed_at = ?
                WHERE system_id = ?
            ''', (attacker_id, now, system_id))
            logger.info(f"War Room: Territory {system_name} transferred to attacker (partner {attacker_id})")

        conn.commit()

        # Recalculate statistics (practice conflicts are already excluded in the function)
        await recalculate_war_statistics_internal(conn)

        # Skip notifications and activity feed for practice conflicts
        if not is_practice:
            # Notify both parties
            for pid in [attacker_id, defender_id]:
                await send_war_notification(
                    pid,
                    'conflict_resolved',
                    f"Conflict Resolved: {system_name}",
                    f"The battle for {system_name} has ended. Resolution: {resolution.replace('_', ' ').title()}",
                    conflict_id
                )

            # Get names for activity feed
            cursor.execute('SELECT display_name FROM partner_accounts WHERE id = ?', (attacker_id,))
            attacker_row = cursor.fetchone()
            attacker_name = attacker_row[0] if attacker_row else 'Unknown'

            cursor.execute('SELECT display_name FROM partner_accounts WHERE id = ?', (defender_id,))
            defender_row = cursor.fetchone()
            defender_name = defender_row[0] if defender_row else 'Unknown'

            victor_name = None
            if victor_id == attacker_id:
                victor_name = attacker_name
            elif victor_id == defender_id:
                victor_name = defender_name

            # Add to public activity feed
            if resolution == 'attacker_victory':
                headline = f"{attacker_name} conquers {system_name} from {defender_name}"
                details = f"{attacker_name} has seized control of {system_name}. Territory transferred to the victor."
            elif resolution == 'defender_victory':
                headline = f"{defender_name} repels {attacker_name}'s invasion of {system_name}"
                details = f"{defender_name} has successfully defended {system_name} against {attacker_name}."
            elif resolution == 'stalemate':
                headline = f"Battle for {system_name} ends in stalemate"
                details = f"The conflict between {attacker_name} and {defender_name} over {system_name} has ended without a clear victor."
            else:
                headline = f"Conflict over {system_name} cancelled"
                details = f"The conflict between {attacker_name} and {defender_name} has been cancelled."

            await add_activity_feed_entry(
                event_type='conflict_resolved',
                headline=headline,
                actor_partner_id=victor_id,
                actor_name=victor_name,
                target_partner_id=defender_id if victor_id == attacker_id else attacker_id,
                target_name=defender_name if victor_id == attacker_id else attacker_name,
                conflict_id=conflict_id,
                system_id=str(system_id) if system_id else None,
                system_name=system_name,
                details=details,
                is_public=True
            )

        practice_log = " (PRACTICE)" if is_practice else ""
        logger.info(f"War Room: Conflict {conflict_id} resolved as {resolution}{practice_log}")
        return {'status': 'resolved', 'resolution': resolution, 'victor_partner_id': victor_id, 'is_practice': bool(is_practice)}
    finally:
        conn.close()


@app.delete('/api/warroom/conflicts/{conflict_id}')
async def cancel_conflict(conflict_id: int, session: Optional[str] = Cookie(None)):
    """Cancel a pending conflict (attacker only)."""
    session_data = get_session(session)
    partner_info = get_war_room_partner_info(session_data)
    if not partner_info:
        raise HTTPException(status_code=403, detail="Must be enrolled in War Room")

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            SELECT c.attacker_partner_id, c.defender_partner_id, c.status, c.target_system_name,
                   pa1.display_name as attacker_name, pa2.display_name as defender_name
            FROM conflicts c
            LEFT JOIN partner_accounts pa1 ON c.attacker_partner_id = pa1.id
            LEFT JOIN partner_accounts pa2 ON c.defender_partner_id = pa2.id
            WHERE c.id = ?
        ''', (conflict_id,))
        conflict = cursor.fetchone()
        if not conflict:
            raise HTTPException(status_code=404, detail="Conflict not found")

        attacker_id, defender_id, status, system_name, attacker_name, defender_name = conflict

        if not partner_info.get('is_super_admin') and partner_info['partner_id'] != attacker_id:
            raise HTTPException(status_code=403, detail="Only the attacker can cancel")

        if status != 'pending':
            raise HTTPException(status_code=400, detail="Can only cancel pending conflicts")

        cursor.execute('''
            UPDATE conflicts SET status = 'resolved', resolution = 'cancelled',
                   resolved_at = ?, resolved_by = ?
            WHERE id = ?
        ''', (datetime.now(timezone.utc).isoformat(), session_data.get('username'), conflict_id))
        conn.commit()

        # Add to public activity feed
        await add_activity_feed_entry(
            event_type='conflict_cancelled',
            headline=f"{attacker_name} withdraws attack on {system_name}",
            actor_partner_id=attacker_id,
            actor_name=attacker_name,
            target_partner_id=defender_id,
            target_name=defender_name,
            conflict_id=conflict_id,
            system_name=system_name,
            details=f"{attacker_name} has withdrawn their declaration of war against {defender_name} for {system_name}.",
            is_public=True
        )

        return {'status': 'cancelled', 'conflict_id': conflict_id}
    finally:
        conn.close()


@app.post('/api/warroom/conflicts/{conflict_id}/events')
async def add_conflict_event(conflict_id: int, request: Request, session: Optional[str] = Cookie(None)):
    """Add a timeline event to a conflict."""
    session_data = get_session(session)
    partner_info = get_war_room_partner_info(session_data)
    if not partner_info:
        raise HTTPException(status_code=403, detail="Must be enrolled in War Room")

    data = await request.json()
    event_type = data.get('event_type')
    details = data.get('details')

    if event_type not in ['skirmish', 'capture', 'defense', 'retreat', 'reinforcement', 'note']:
        raise HTTPException(status_code=400, detail="Invalid event_type")

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Get conflict details for activity feed
        cursor.execute('''
            SELECT c.status, c.target_system_name, pa.display_name
            FROM conflicts c
            LEFT JOIN partner_accounts pa ON c.attacker_partner_id = pa.id OR c.defender_partner_id = pa.id
            WHERE c.id = ?
        ''', (conflict_id,))
        conflict = cursor.fetchone()
        if not conflict:
            raise HTTPException(status_code=404, detail="Conflict not found")
        if conflict[0] == 'resolved':
            raise HTTPException(status_code=400, detail="Cannot add events to resolved conflict")

        system_name = conflict[1] or 'Unknown System'

        cursor.execute('''
            INSERT INTO conflict_events (conflict_id, event_type, actor_partner_id, actor_username, details)
            VALUES (?, ?, ?, ?, ?)
        ''', (conflict_id, event_type, partner_info.get('partner_id'), session_data.get('username'), details))
        event_id = cursor.lastrowid
        conn.commit()

        # Add to activity feed for significant battle events (not notes)
        if event_type != 'note':
            actor_name = partner_info.get('display_name', session_data.get('username', 'Unknown'))

            # Create appropriate headline based on event type
            event_headlines = {
                'skirmish': f"Skirmish reported at {system_name}",
                'capture': f"{actor_name} captures position at {system_name}",
                'defense': f"{actor_name} defends position at {system_name}",
                'retreat': f"Forces retreat at {system_name}",
                'reinforcement': f"{actor_name} sends reinforcements to {system_name}"
            }
            headline = event_headlines.get(event_type, f"Battle update at {system_name}")

            await add_activity_feed_entry(
                event_type=f'battle_{event_type}',
                headline=headline,
                actor_partner_id=partner_info.get('partner_id'),
                actor_name=actor_name,
                conflict_id=conflict_id,
                system_name=system_name,
                details=details,
                is_public=True
            )

        return {'status': 'added', 'event_id': event_id}
    finally:
        conn.close()


@app.get('/api/warroom/conflicts/{conflict_id}/events')
async def get_conflict_events(conflict_id: int, session: Optional[str] = Cookie(None)):
    """Get timeline events for a conflict."""
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail="Not authenticated")

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Verify conflict exists
        cursor.execute('SELECT id FROM conflicts WHERE id = ?', (conflict_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Conflict not found")

        cursor.execute('''
            SELECT id, event_type, actor_partner_id, actor_username, details, event_at
            FROM conflict_events
            WHERE conflict_id = ?
            ORDER BY event_at ASC
        ''', (conflict_id,))
        events = []
        for row in cursor.fetchall():
            events.append({
                'id': row[0],
                'event_type': row[1],
                'actor_partner_id': row[2],
                'actor_username': row[3],
                'details': row[4],
                'created_at': row[5]  # Frontend expects created_at
            })
        return events
    finally:
        conn.close()


# --- Debrief Endpoints ---

@app.get('/api/warroom/debrief')
async def get_debrief(session: Optional[str] = Cookie(None)):
    """Get current mission objectives."""
    try:
        session_data = get_session(session)
        if not session_data:
            raise HTTPException(status_code=401, detail="Not authenticated")

        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('SELECT objectives, updated_at, updated_by FROM current_debrief WHERE id = 1')
            row = cursor.fetchone()
            if not row:
                return {'objectives': [], 'updated_at': None, 'updated_by': None}

            objectives = json.loads(row[0]) if row[0] else []
            return {'objectives': objectives, 'updated_at': row[1], 'updated_by': row[2]}
        finally:
            conn.close()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_debrief: {type(e).__name__}: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Internal error: {type(e).__name__}: {str(e)}")


@app.put('/api/warroom/debrief')
async def update_debrief(request: Request, session: Optional[str] = Cookie(None)):
    """Update mission objectives (super admin only)."""
    session_data = get_session(session)
    if not session_data or session_data.get('user_type') != 'super_admin':
        raise HTTPException(status_code=403, detail="Super admin access required")

    data = await request.json()
    objectives = data.get('objectives', [])

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            UPDATE current_debrief SET objectives = ?, updated_at = ?, updated_by = ?
            WHERE id = 1
        ''', (json.dumps(objectives), datetime.now(timezone.utc).isoformat(), session_data.get('username')))
        conn.commit()

        return {'status': 'updated', 'objectives': objectives}
    finally:
        conn.close()


# --- War News Endpoints ---

@app.get('/api/warroom/news')
async def get_war_news(limit: int = 20, offset: int = 0, session: Optional[str] = Cookie(None)):
    """Get war news articles."""
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail="Not authenticated")

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            SELECT wn.id, wn.headline, wn.body, wn.author_username, wn.author_type,
                   wn.related_conflict_id, wn.published_at, wn.is_pinned,
                   wn.article_type, wn.view_count, wn.reporting_org_id,
                   ro.name as reporting_org_name, wc.display_name as author_name
            FROM war_news wn
            LEFT JOIN reporting_organizations ro ON wn.reporting_org_id = ro.id
            LEFT JOIN war_correspondents wc ON wn.author_username = wc.username
            WHERE wn.is_active = 1
            ORDER BY wn.is_pinned DESC, wn.published_at DESC
            LIMIT ? OFFSET ?
        ''', (limit, offset))
        rows = cursor.fetchall()

        return [{
            'id': r[0],
            'headline': r[1],
            'body': r[2],
            'author': r[3],
            'author_type': r[4],
            'conflict_id': r[5],
            'created_at': r[6],
            'is_pinned': r[7],
            'article_type': r[8] or 'breaking',
            'view_count': r[9] or 0,
            'reporting_org_id': r[10],
            'reporting_org_name': r[11],
            'author_name': r[12] or r[3]
        } for r in rows]
    finally:
        conn.close()


@app.get('/api/warroom/news/ticker')
async def get_news_ticker(session: Optional[str] = Cookie(None)):
    """Get latest 10 news items for the ticker."""
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail="Not authenticated")

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            SELECT id, headline, published_at FROM war_news
            WHERE is_active = 1
            ORDER BY published_at DESC
            LIMIT 10
        ''')
        rows = cursor.fetchall()

        return [{'id': r[0], 'headline': r[1], 'published_at': r[2]} for r in rows]
    finally:
        conn.close()


@app.post('/api/warroom/news')
async def create_war_news(request: Request, session: Optional[str] = Cookie(None)):
    """Create a news article (super admin, correspondent, or enrolled partner)."""
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail="Not authenticated")

    username = session_data.get('username')
    is_super_admin = session_data.get('user_type') == 'super_admin'
    author_type = 'super_admin'
    author_display_name = username

    if is_super_admin:
        author_type = 'super_admin'
    else:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Check if they're a correspondent
        cursor.execute('SELECT id, display_name FROM war_correspondents WHERE username = ? AND is_active = 1', (username,))
        correspondent = cursor.fetchone()
        if correspondent:
            author_type = 'correspondent'
            author_display_name = correspondent[1] or username
            conn.close()
        else:
            # Check if they're an enrolled partner
            partner_info = get_war_room_partner_info(session_data)
            conn.close()
            if partner_info and not partner_info.get('is_super_admin'):
                author_type = 'partner'
                author_display_name = partner_info.get('display_name', username)
            else:
                raise HTTPException(status_code=403, detail="Must be super admin, war correspondent, or enrolled partner")

    data = await request.json()
    headline = data.get('headline')
    body = data.get('body')
    article_type = data.get('article_type', 'breaking')
    if not headline or not body:
        raise HTTPException(status_code=400, detail="headline and body required")

    # Validate article_type
    valid_types = ['breaking', 'report', 'analysis', 'editorial', 'announcement']
    if article_type not in valid_types:
        article_type = 'breaking'

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO war_news (headline, body, author_username, author_type, related_conflict_id, is_pinned, article_type)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (headline, body, author_display_name, author_type, data.get('conflict_id'), data.get('is_pinned', False), article_type))
        news_id = cursor.lastrowid
        conn.commit()

        # Add to activity feed
        await add_activity_feed_entry(
            event_type='news_published',
            headline=f"News: {headline}",
            actor_name=author_display_name,
            details=f"New {article_type} article published by {author_display_name}",
            is_public=True
        )

        logger.info(f"War Room: News created by {author_display_name} ({author_type}): {headline}")
        return {'status': 'created', 'news_id': news_id}
    finally:
        conn.close()


@app.delete('/api/warroom/news/{news_id}')
async def delete_war_news(news_id: int, session: Optional[str] = Cookie(None)):
    """Delete a news article (super admin only)."""
    session_data = get_session(session)
    if not session_data or session_data.get('user_type') != 'super_admin':
        raise HTTPException(status_code=403, detail="Super admin access required")

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('UPDATE war_news SET is_active = 0 WHERE id = ?', (news_id,))
        conn.commit()
        return {'status': 'deleted', 'news_id': news_id}
    finally:
        conn.close()


# --- War Correspondents Endpoints ---

@app.get('/api/warroom/correspondents')
async def get_correspondents(session: Optional[str] = Cookie(None)):
    """List war correspondents (super admin only)."""
    session_data = get_session(session)
    if not session_data or session_data.get('user_type') != 'super_admin':
        raise HTTPException(status_code=403, detail="Super admin access required")

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            SELECT id, username, display_name, is_active, created_at, created_by
            FROM war_correspondents
            ORDER BY created_at DESC
        ''')
        rows = cursor.fetchall()

        return [{
            'id': r[0],
            'username': r[1],
            'display_name': r[2],
            'is_active': bool(r[3]),
            'created_at': r[4],
            'created_by': r[5]
        } for r in rows]
    finally:
        conn.close()


@app.post('/api/warroom/correspondents')
async def create_correspondent(request: Request, session: Optional[str] = Cookie(None)):
    """Create a war correspondent (super admin only)."""
    session_data = get_session(session)
    if not session_data or session_data.get('user_type') != 'super_admin':
        raise HTTPException(status_code=403, detail="Super admin access required")

    data = await request.json()
    username = data.get('username')
    password = data.get('password')
    display_name = data.get('display_name')

    if not username or not password:
        raise HTTPException(status_code=400, detail="username and password required")

    password_hash = hashlib.sha256(password.encode()).hexdigest()

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO war_correspondents (username, password_hash, display_name, created_by)
            VALUES (?, ?, ?, ?)
        ''', (username, password_hash, display_name, session_data.get('username')))
        conn.commit()

        logger.info(f"War Room: Correspondent created: {username}")
        return {'status': 'created', 'correspondent_id': cursor.lastrowid}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="Username already exists")
    finally:
        conn.close()


@app.post('/api/warroom/correspondents/login')
async def correspondent_login(request: Request, response: Response):
    """Login as a war correspondent."""
    data = await request.json()
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        raise HTTPException(status_code=400, detail="username and password required")

    password_hash = hashlib.sha256(password.encode()).hexdigest()

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            SELECT id, username, display_name, is_active
            FROM war_correspondents
            WHERE username = ? AND password_hash = ?
        ''', (username, password_hash))
        correspondent = cursor.fetchone()

        if not correspondent:
            raise HTTPException(status_code=401, detail="Invalid credentials")

        if not correspondent[3]:
            raise HTTPException(status_code=403, detail="Account is inactive")

        # Create session for correspondent
        session_id = secrets.token_hex(32)
        session_data = {
            'user_type': 'correspondent',
            'username': correspondent[1],
            'display_name': correspondent[2] or correspondent[1],
            'correspondent_id': correspondent[0]
        }
        sessions[session_id] = session_data

        response.set_cookie(
            key='session',
            value=session_id,
            httponly=True,
            secure=False,
            samesite='lax',
            max_age=86400 * 7
        )

        logger.info(f"War Room: Correspondent logged in: {username}")
        return {
            'status': 'success',
            'username': correspondent[1],
            'display_name': correspondent[2] or correspondent[1],
            'user_type': 'correspondent'
        }
    finally:
        conn.close()


# --- Statistics Endpoints ---

async def recalculate_war_statistics_internal(conn=None):
    """Internal function to recalculate war statistics (excludes practice conflicts)."""
    close_conn = False
    if conn is None:
        conn = get_db_connection()
        close_conn = True

    cursor = conn.cursor()
    try:
        # Clear existing stats
        cursor.execute('DELETE FROM war_statistics')

        # Note: All queries exclude practice conflicts with (is_practice IS NULL OR is_practice = 0)

        # Longest Defense: defender_victory with max duration
        cursor.execute('''
            SELECT defender_partner_id, pa.display_name,
                   CAST((julianday(resolved_at) - julianday(declared_at)) * 24 AS INTEGER) as hours,
                   target_system_name, id
            FROM conflicts c
            JOIN partner_accounts pa ON c.defender_partner_id = pa.id
            WHERE resolution = 'defender_victory' AND resolved_at IS NOT NULL
              AND (c.is_practice IS NULL OR c.is_practice = 0)
            ORDER BY hours DESC LIMIT 1
        ''')
        row = cursor.fetchone()
        if row:
            cursor.execute('''
                INSERT INTO war_statistics (stat_type, partner_id, partner_display_name, value, value_unit, details)
                VALUES ('longest_defense', ?, ?, ?, 'hours', ?)
            ''', (row[0], row[1], row[2], json.dumps({'system': row[3], 'conflict_id': row[4]})))

        # Fastest Invasion: attacker_victory with min duration
        cursor.execute('''
            SELECT attacker_partner_id, pa.display_name,
                   CAST((julianday(resolved_at) - julianday(declared_at)) * 24 AS INTEGER) as hours,
                   target_system_name, id
            FROM conflicts c
            JOIN partner_accounts pa ON c.attacker_partner_id = pa.id
            WHERE resolution = 'attacker_victory' AND resolved_at IS NOT NULL
              AND (c.is_practice IS NULL OR c.is_practice = 0)
            ORDER BY hours ASC LIMIT 1
        ''')
        row = cursor.fetchone()
        if row:
            cursor.execute('''
                INSERT INTO war_statistics (stat_type, partner_id, partner_display_name, value, value_unit, details)
                VALUES ('fastest_invasion', ?, ?, ?, 'hours', ?)
            ''', (row[0], row[1], row[2], json.dumps({'system': row[3], 'conflict_id': row[4]})))

        # Largest Battle: conflict with most events
        cursor.execute('''
            SELECT c.id, c.target_system_name, c.attacker_partner_id, att.display_name,
                   c.defender_partner_id, def.display_name, COUNT(ce.id) as event_count
            FROM conflicts c
            JOIN partner_accounts att ON c.attacker_partner_id = att.id
            JOIN partner_accounts def ON c.defender_partner_id = def.id
            LEFT JOIN conflict_events ce ON c.id = ce.conflict_id
            WHERE (c.is_practice IS NULL OR c.is_practice = 0)
            GROUP BY c.id
            ORDER BY event_count DESC LIMIT 1
        ''')
        row = cursor.fetchone()
        if row and row[6] > 0:
            cursor.execute('''
                INSERT INTO war_statistics (stat_type, partner_id, partner_display_name, value, value_unit, details)
                VALUES ('largest_battle', NULL, NULL, ?, 'events', ?)
            ''', (row[6], json.dumps({
                'conflict_id': row[0], 'system': row[1],
                'attacker': row[3], 'defender': row[5]
            })))

        # Most Conquered: attacker with most victories
        cursor.execute('''
            SELECT attacker_partner_id, pa.display_name, COUNT(*) as wins
            FROM conflicts c
            JOIN partner_accounts pa ON c.attacker_partner_id = pa.id
            WHERE resolution = 'attacker_victory'
              AND (c.is_practice IS NULL OR c.is_practice = 0)
            GROUP BY attacker_partner_id
            ORDER BY wins DESC LIMIT 1
        ''')
        row = cursor.fetchone()
        if row:
            cursor.execute('''
                INSERT INTO war_statistics (stat_type, partner_id, partner_display_name, value, value_unit, details)
                VALUES ('most_conquered', ?, ?, ?, 'systems', NULL)
            ''', (row[0], row[1], row[2]))

        conn.commit()
        logger.info("War Room: Statistics recalculated")
    finally:
        if close_conn:
            conn.close()


@app.get('/api/warroom/statistics')
async def get_war_statistics(session: Optional[str] = Cookie(None)):
    """Get war statistics."""
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail="Not authenticated")

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            SELECT stat_type, partner_id, partner_display_name, value, value_unit, details, calculated_at
            FROM war_statistics
        ''')
        rows = cursor.fetchall()

        stats = {}
        for r in rows:
            stats[r[0]] = {
                'partner_id': r[1],
                'holder': r[2],
                'value': r[3],
                'unit': r[4],
                'details': json.loads(r[5]) if r[5] else None,
                'calculated_at': r[6]
            }

        return stats
    finally:
        conn.close()


@app.get('/api/warroom/statistics/leaderboard')
async def get_war_leaderboard(session: Optional[str] = Cookie(None)):
    """Get per-civ rankings."""
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail="Not authenticated")

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Get all enrolled civs with their stats (excludes practice conflicts)
        cursor.execute('''
            SELECT pa.id, pa.display_name, pa.region_color,
                   (SELECT COUNT(*) FROM territorial_claims WHERE claimant_partner_id = pa.id) as systems_controlled,
                   (SELECT COUNT(*) FROM conflicts WHERE attacker_partner_id = pa.id AND resolution = 'attacker_victory' AND (is_practice IS NULL OR is_practice = 0)) as systems_conquered,
                   (SELECT COUNT(*) FROM conflicts WHERE defender_partner_id = pa.id AND resolution = 'attacker_victory' AND (is_practice IS NULL OR is_practice = 0)) as systems_lost,
                   (SELECT COUNT(*) FROM conflicts WHERE (attacker_partner_id = pa.id OR defender_partner_id = pa.id) AND status IN ('pending', 'acknowledged', 'active') AND (is_practice IS NULL OR is_practice = 0)) as active_conflicts
            FROM partner_accounts pa
            JOIN war_room_enrollment wre ON pa.id = wre.partner_id
            WHERE wre.is_active = 1
            ORDER BY systems_controlled DESC
        ''')
        rows = cursor.fetchall()

        return [{
            'partner_id': r[0],
            'display_name': r[1],
            'color': r[2],
            'systems_controlled': r[3],
            'systems_conquered': r[4],
            'systems_lost': r[5],
            'active_conflicts': r[6],
            'win_rate': round(r[4] / (r[4] + r[5]) * 100, 1) if (r[4] + r[5]) > 0 else 0
        } for r in rows]
    finally:
        conn.close()


@app.post('/api/warroom/statistics/recalculate')
async def recalculate_statistics(session: Optional[str] = Cookie(None)):
    """Force recalculation of statistics (super admin only)."""
    session_data = get_session(session)
    if not session_data or session_data.get('user_type') != 'super_admin':
        raise HTTPException(status_code=403, detail="Super admin access required")

    await recalculate_war_statistics_internal()
    return {'status': 'recalculated'}


# --- Notifications Endpoints ---

@app.get('/api/warroom/notifications')
async def get_notifications(session: Optional[str] = Cookie(None)):
    """Get user's War Room notifications."""
    session_data = get_session(session)
    partner_info = get_war_room_partner_info(session_data)
    if not partner_info or partner_info.get('is_super_admin'):
        return []  # Super admins don't get individual notifications

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            SELECT id, notification_type, title, message, related_conflict_id, created_at, read_at
            FROM war_notifications
            WHERE recipient_partner_id = ? AND dismissed_at IS NULL
            ORDER BY created_at DESC
            LIMIT 50
        ''', (partner_info['partner_id'],))
        rows = cursor.fetchall()

        return [{
            'id': r[0],
            'type': r[1],
            'title': r[2],
            'message': r[3],
            'conflict_id': r[4],
            'created_at': r[5],
            'read': r[6] is not None
        } for r in rows]
    finally:
        conn.close()


@app.get('/api/warroom/notifications/count')
async def get_notification_count(session: Optional[str] = Cookie(None)):
    """Get unread notification count."""
    session_data = get_session(session)
    partner_info = get_war_room_partner_info(session_data)
    if not partner_info or partner_info.get('is_super_admin'):
        return {'count': 0}

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            SELECT COUNT(*) FROM war_notifications
            WHERE recipient_partner_id = ? AND read_at IS NULL AND dismissed_at IS NULL
        ''', (partner_info['partner_id'],))
        count = cursor.fetchone()[0]
        return {'count': count}
    finally:
        conn.close()


@app.put('/api/warroom/notifications/read-all')
async def mark_all_notifications_read(session: Optional[str] = Cookie(None)):
    """Mark all notifications as read."""
    session_data = get_session(session)
    partner_info = get_war_room_partner_info(session_data)
    if not partner_info or partner_info.get('is_super_admin'):
        return {'status': 'ok'}

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            UPDATE war_notifications SET read_at = ?
            WHERE recipient_partner_id = ? AND read_at IS NULL
        ''', (datetime.now(timezone.utc).isoformat(), partner_info['partner_id']))
        conn.commit()
        return {'status': 'ok', 'marked': cursor.rowcount}
    finally:
        conn.close()


# --- Discord Webhooks Endpoints ---

@app.get('/api/warroom/webhooks')
async def get_webhook(session: Optional[str] = Cookie(None)):
    """Get webhook for current partner."""
    session_data = get_session(session)
    partner_info = get_war_room_partner_info(session_data)
    if not partner_info or partner_info.get('is_super_admin'):
        raise HTTPException(status_code=403, detail="Partner access required")

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            SELECT webhook_url, is_active, last_triggered_at
            FROM discord_webhooks WHERE partner_id = ?
        ''', (partner_info['partner_id'],))
        row = cursor.fetchone()

        if not row:
            return {'configured': False}

        return {
            'configured': True,
            'webhook_url': row[0][:50] + '...' if row[0] else None,  # Partial for security
            'is_active': bool(row[1]),
            'last_triggered_at': row[2]
        }
    finally:
        conn.close()


@app.put('/api/warroom/webhooks')
async def set_webhook(request: Request, session: Optional[str] = Cookie(None)):
    """Set or update webhook URL."""
    session_data = get_session(session)
    partner_info = get_war_room_partner_info(session_data)
    if not partner_info or partner_info.get('is_super_admin'):
        raise HTTPException(status_code=403, detail="Partner access required")

    data = await request.json()
    webhook_url = data.get('webhook_url')
    is_active = data.get('is_active', True)

    if webhook_url and not webhook_url.startswith('https://discord.com/api/webhooks/'):
        raise HTTPException(status_code=400, detail="Invalid Discord webhook URL")

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO discord_webhooks (partner_id, webhook_url, is_active)
            VALUES (?, ?, ?)
            ON CONFLICT(partner_id) DO UPDATE SET webhook_url = ?, is_active = ?
        ''', (partner_info['partner_id'], webhook_url, is_active, webhook_url, is_active))
        conn.commit()
        return {'status': 'updated'}
    finally:
        conn.close()


@app.delete('/api/warroom/webhooks')
async def delete_webhook(session: Optional[str] = Cookie(None)):
    """Remove webhook configuration."""
    session_data = get_session(session)
    partner_info = get_war_room_partner_info(session_data)
    if not partner_info or partner_info.get('is_super_admin'):
        raise HTTPException(status_code=403, detail="Partner access required")

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('DELETE FROM discord_webhooks WHERE partner_id = ?', (partner_info['partner_id'],))
        conn.commit()
        return {'status': 'deleted'}
    finally:
        conn.close()


# --- Map Data Endpoint ---

@app.get('/api/warroom/map-data')
async def get_war_map_data(session: Optional[str] = Cookie(None)):
    """Get aggregated data for the war map visualization."""
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail="Not authenticated")

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Get enrolled civs with home region data
        cursor.execute('''
            SELECT pa.id, pa.display_name, pa.discord_tag, pa.region_color,
                   wre.home_region_x, wre.home_region_y, wre.home_region_z,
                   wre.home_region_name, wre.home_galaxy
            FROM partner_accounts pa
            JOIN war_room_enrollment wre ON pa.id = wre.partner_id
            WHERE wre.is_active = 1
        ''')
        enrolled_civs = [{
            'partner_id': r[0],
            'display_name': r[1],
            'discord_tag': r[2],
            'color': r[3],
            'home_region': {
                'x': r[4],
                'y': r[5],
                'z': r[6],
                'name': r[7],
                'galaxy': r[8]
            } if r[4] is not None else None
        } for r in cursor.fetchall()]

        enrolled_ids = [c['partner_id'] for c in enrolled_civs]
        if not enrolled_ids:
            return {'regions': [], 'enrolled_civs': [], 'active_conflict_count': 0}

        # Get territorial claims grouped by region
        placeholders = ','.join('?' * len(enrolled_ids))
        cursor.execute(f'''
            SELECT tc.region_x, tc.region_y, tc.region_z, tc.galaxy, tc.reality,
                   tc.claimant_partner_id, pa.display_name, pa.region_color,
                   COUNT(*) as system_count
            FROM territorial_claims tc
            JOIN partner_accounts pa ON tc.claimant_partner_id = pa.id
            WHERE tc.claimant_partner_id IN ({placeholders})
            GROUP BY tc.region_x, tc.region_y, tc.region_z, tc.claimant_partner_id
            ORDER BY system_count DESC
        ''', enrolled_ids)

        regions = []
        for r in cursor.fetchall():
            region_key = f"{r[0]}:{r[1]}:{r[2]}"

            # Check for active conflicts in this region
            cursor.execute('''
                SELECT c.id, att.display_name, c.target_system_name
                FROM conflicts c
                JOIN territorial_claims tc ON c.target_system_id = tc.system_id
                JOIN partner_accounts att ON c.attacker_partner_id = att.id
                WHERE tc.region_x = ? AND tc.region_y = ? AND tc.region_z = ?
                  AND c.status IN ('pending', 'acknowledged', 'active')
            ''', (r[0], r[1], r[2]))
            active_conflicts = [{
                'conflict_id': ac[0],
                'attacker': ac[1],
                'target_system': ac[2]
            } for ac in cursor.fetchall()]

            regions.append({
                'region_x': r[0],
                'region_y': r[1],
                'region_z': r[2],
                'galaxy': r[3],
                'reality': r[4],
                'controlling_civ': {
                    'partner_id': r[5],
                    'display_name': r[6],
                    'color': r[7]
                },
                'system_count': r[8],
                'contested': len(active_conflicts) > 0,
                'active_conflicts': active_conflicts
            })

        # Get total active conflict count
        cursor.execute('''
            SELECT COUNT(*) FROM conflicts
            WHERE status IN ('pending', 'acknowledged', 'active')
        ''')
        active_conflict_count = cursor.fetchone()[0]

        # Build home_regions array for map visualization
        home_regions = []
        for civ in enrolled_civs:
            if civ['home_region'] and civ['home_region']['x'] is not None:
                hr = civ['home_region']
                home_regions.append({
                    'region_x': hr['x'],
                    'region_y': hr['y'],
                    'region_z': hr['z'],
                    'region_name': hr['name'],
                    'galaxy': hr['galaxy'],
                    'civ': {
                        'partner_id': civ['partner_id'],
                        'display_name': civ['display_name'],
                        'color': civ['color']
                    }
                })

        # Also mark regions that are home regions
        for region in regions:
            region['is_home_region'] = any(
                hr['region_x'] == region['region_x'] and
                hr['region_y'] == region['region_y'] and
                hr['region_z'] == region['region_z']
                for hr in home_regions
            )

        # Calculate region ownership based on systems.discord_tag (>50% rule)
        # Get all enrolled discord_tags
        enrolled_tags = {c['discord_tag']: c for c in enrolled_civs if c.get('discord_tag')}

        if enrolled_tags:
            # Query systems grouped by region and discord_tag
            tag_placeholders = ','.join('?' * len(enrolled_tags))
            cursor.execute(f'''
                SELECT region_x, region_y, region_z, galaxy, discord_tag, COUNT(*) as system_count
                FROM systems
                WHERE discord_tag IN ({tag_placeholders})
                  AND region_x IS NOT NULL
                GROUP BY region_x, region_y, region_z, discord_tag
            ''', list(enrolled_tags.keys()))

            # Build region ownership map: {region_key: {discord_tag: count, ...}}
            region_tag_counts = {}
            for row in cursor.fetchall():
                key = f"{row[0]}:{row[1]}:{row[2]}"
                if key not in region_tag_counts:
                    region_tag_counts[key] = {'galaxy': row[3], 'coords': (row[0], row[1], row[2]), 'tags': {}}
                region_tag_counts[key]['tags'][row[4]] = row[5]

            # Calculate ownership for each region (>50% = ownership)
            region_ownership = []
            for key, data in region_tag_counts.items():
                total_systems = sum(data['tags'].values())
                for tag, count in data['tags'].items():
                    percentage = (count / total_systems * 100) if total_systems > 0 else 0
                    if percentage > 50:
                        civ = enrolled_tags.get(tag)
                        if civ:
                            region_ownership.append({
                                'region_x': data['coords'][0],
                                'region_y': data['coords'][1],
                                'region_z': data['coords'][2],
                                'galaxy': data['galaxy'],
                                'owner': {
                                    'partner_id': civ['partner_id'],
                                    'display_name': civ['display_name'],
                                    'discord_tag': tag,
                                    'color': civ['color']
                                },
                                'system_count': count,
                                'total_in_region': total_systems,
                                'ownership_percentage': round(percentage, 1)
                            })
                        break  # Only one owner per region

            # Merge ownership data into existing regions and add new owned regions
            owned_region_keys = {f"{o['region_x']}:{o['region_y']}:{o['region_z']}": o for o in region_ownership}
            for region in regions:
                key = f"{region['region_x']}:{region['region_y']}:{region['region_z']}"
                if key in owned_region_keys:
                    ownership = owned_region_keys[key]
                    region['ownership'] = {
                        'owner': ownership['owner'],
                        'percentage': ownership['ownership_percentage'],
                        'system_count': ownership['system_count']
                    }
                else:
                    region['ownership'] = None

            # Add owned regions that don't have war claims
            existing_keys = {f"{r['region_x']}:{r['region_y']}:{r['region_z']}" for r in regions}
            for key, ownership in owned_region_keys.items():
                if key not in existing_keys:
                    regions.append({
                        'region_x': ownership['region_x'],
                        'region_y': ownership['region_y'],
                        'region_z': ownership['region_z'],
                        'galaxy': ownership['galaxy'],
                        'reality': 'Normal',
                        'controlling_civ': ownership['owner'],
                        'system_count': ownership['system_count'],
                        'contested': False,
                        'active_conflicts': [],
                        'is_home_region': any(
                            hr['region_x'] == ownership['region_x'] and
                            hr['region_y'] == ownership['region_y'] and
                            hr['region_z'] == ownership['region_z']
                            for hr in home_regions
                        ),
                        'ownership': {
                            'owner': ownership['owner'],
                            'percentage': ownership['ownership_percentage'],
                            'system_count': ownership['system_count']
                        }
                    })
        else:
            # No enrolled tags, no ownership data
            for region in regions:
                region['ownership'] = None

        return {
            'regions': regions,
            'enrolled_civs': enrolled_civs,
            'home_regions': home_regions,
            'active_conflict_count': active_conflict_count
        }
    finally:
        conn.close()


# --- Activity Feed Endpoints ---

async def add_activity_feed_entry(
    event_type: str,
    headline: str,
    actor_partner_id: int = None,
    actor_name: str = None,
    target_partner_id: int = None,
    target_name: str = None,
    conflict_id: int = None,
    system_id: str = None,
    system_name: str = None,
    region_name: str = None,
    details: str = None,
    is_public: bool = True
):
    """Helper function to add an entry to the activity feed."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO war_activity_feed
            (event_type, headline, actor_partner_id, actor_name, target_partner_id, target_name,
             conflict_id, system_id, system_name, region_name, details, is_public)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (event_type, headline, actor_partner_id, actor_name, target_partner_id, target_name,
              conflict_id, system_id, system_name, region_name, details, 1 if is_public else 0))
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


@app.get('/api/warroom/activity-feed')
async def get_activity_feed(limit: int = 50, offset: int = 0, session: Optional[str] = Cookie(None)):
    """Get the public activity feed."""
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail="Not authenticated")

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            SELECT id, event_type, event_at, actor_partner_id, actor_name,
                   target_partner_id, target_name, conflict_id, system_id, system_name,
                   region_name, headline, details
            FROM war_activity_feed
            WHERE is_public = 1
            ORDER BY event_at DESC
            LIMIT ? OFFSET ?
        ''', (limit, offset))
        rows = cursor.fetchall()

        # Get total count
        cursor.execute('SELECT COUNT(*) FROM war_activity_feed WHERE is_public = 1')
        total = cursor.fetchone()[0]

        # Return array directly for simpler frontend consumption
        return [{
            'id': r[0],
            'event_type': r[1],
            'created_at': r[2],  # Frontend expects created_at
            'actor_partner_id': r[3],
            'actor_name': r[4],
            'target_partner_id': r[5],
            'target_name': r[6],
            'conflict_id': r[7],
            'system_id': r[8],
            'system_name': r[9],
            'region_name': r[10],
            'headline': r[11],
            'details': r[12]
        } for r in rows]
        # Note: pagination info available if needed via separate endpoint
    finally:
        conn.close()


# --- Multi-party Conflict Endpoints ---

@app.post('/api/warroom/conflicts/{conflict_id}/join')
async def join_conflict(conflict_id: int, request: Request, session: Optional[str] = Cookie(None)):
    """Join an existing conflict as an ally."""
    session_data = get_session(session)
    partner_info = get_war_room_partner_info(session_data)
    if not partner_info:
        raise HTTPException(status_code=403, detail="Must be enrolled in War Room")

    data = await request.json()
    side = data.get('side')  # 'attacker' or 'defender'
    if side not in ['attacker', 'defender']:
        raise HTTPException(status_code=400, detail="side must be 'attacker' or 'defender'")

    joining_partner_id = data.get('partner_id') if partner_info.get('is_super_admin') else partner_info['partner_id']

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Get conflict info
        cursor.execute('''
            SELECT c.status, c.target_system_name, c.attacker_partner_id, c.defender_partner_id,
                   att.display_name, def.display_name
            FROM conflicts c
            JOIN partner_accounts att ON c.attacker_partner_id = att.id
            JOIN partner_accounts def ON c.defender_partner_id = def.id
            WHERE c.id = ?
        ''', (conflict_id,))
        conflict = cursor.fetchone()
        if not conflict:
            raise HTTPException(status_code=404, detail="Conflict not found")

        status, system_name, attacker_id, defender_id, attacker_name, defender_name = conflict

        if status == 'resolved':
            raise HTTPException(status_code=400, detail="Cannot join resolved conflict")

        # Check not already in conflict
        cursor.execute('SELECT id FROM conflict_parties WHERE conflict_id = ? AND partner_id = ?',
                       (conflict_id, joining_partner_id))
        if cursor.fetchone():
            raise HTTPException(status_code=409, detail="Already participating in this conflict")

        # Get joining partner name
        cursor.execute('SELECT display_name FROM partner_accounts WHERE id = ?', (joining_partner_id,))
        joining_name = cursor.fetchone()[0]

        # Add to conflict_parties (ensure primary parties are added if not exists)
        cursor.execute('''
            INSERT OR IGNORE INTO conflict_parties (conflict_id, partner_id, side, is_primary)
            VALUES (?, ?, 'attacker', 1)
        ''', (conflict_id, attacker_id))
        cursor.execute('''
            INSERT OR IGNORE INTO conflict_parties (conflict_id, partner_id, side, is_primary)
            VALUES (?, ?, 'defender', 1)
        ''', (conflict_id, defender_id))

        # Add joining party
        cursor.execute('''
            INSERT INTO conflict_parties (conflict_id, partner_id, side, joined_by, is_primary)
            VALUES (?, ?, ?, ?, 0)
        ''', (conflict_id, joining_partner_id, side, session_data.get('username')))

        # Add timeline event
        cursor.execute('''
            INSERT INTO conflict_events (conflict_id, event_type, actor_partner_id, actor_username, details)
            VALUES (?, 'ally_joined', ?, ?, ?)
        ''', (conflict_id, joining_partner_id, session_data.get('username'),
              f"{joining_name} joined as {side} ally"))

        conn.commit()

        # Add to activity feed
        await add_activity_feed_entry(
            'ally_joined',
            f"{joining_name} joins the battle for {system_name} as {side}",
            actor_partner_id=joining_partner_id,
            actor_name=joining_name,
            conflict_id=conflict_id,
            system_name=system_name,
            details=f"Joined on the {'attacking' if side == 'attacker' else 'defending'} side"
        )

        logger.info(f"War Room: {joining_name} joined conflict {conflict_id} as {side}")
        return {'status': 'joined', 'conflict_id': conflict_id, 'side': side}
    finally:
        conn.close()


@app.get('/api/warroom/conflicts/{conflict_id}/parties')
async def get_conflict_parties(conflict_id: int, session: Optional[str] = Cookie(None)):
    """Get all parties involved in a conflict."""
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail="Not authenticated")

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            SELECT cp.partner_id, pa.display_name, pa.region_color, cp.side, cp.is_primary,
                   cp.joined_at, cp.resolution_agreed
            FROM conflict_parties cp
            JOIN partner_accounts pa ON cp.partner_id = pa.id
            WHERE cp.conflict_id = ?
            ORDER BY cp.is_primary DESC, cp.joined_at ASC
        ''', (conflict_id,))
        rows = cursor.fetchall()

        attackers = []
        defenders = []
        for r in rows:
            party = {
                'partner_id': r[0],
                'display_name': r[1],
                'color': r[2],
                'is_primary': bool(r[4]),
                'joined_at': r[5],
                'resolution_agreed': bool(r[6])
            }
            if r[3] == 'attacker':
                attackers.append(party)
            else:
                defenders.append(party)

        return {'attackers': attackers, 'defenders': defenders}
    finally:
        conn.close()


# --- Mutual Agreement Resolution Endpoints ---

@app.put('/api/warroom/conflicts/{conflict_id}/propose-resolution')
async def propose_resolution(conflict_id: int, request: Request, session: Optional[str] = Cookie(None)):
    """Propose a resolution for the conflict. All parties must agree."""
    session_data = get_session(session)
    partner_info = get_war_room_partner_info(session_data)
    if not partner_info:
        raise HTTPException(status_code=403, detail="Must be enrolled in War Room")

    data = await request.json()
    resolution = data.get('resolution')  # attacker_victory, defender_victory, stalemate
    summary = data.get('summary', '')

    if resolution not in ['attacker_victory', 'defender_victory', 'stalemate']:
        raise HTTPException(status_code=400, detail="Invalid resolution")

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Get conflict
        cursor.execute('''
            SELECT status, attacker_partner_id, defender_partner_id, target_system_name
            FROM conflicts WHERE id = ?
        ''', (conflict_id,))
        conflict = cursor.fetchone()
        if not conflict:
            raise HTTPException(status_code=404, detail="Conflict not found")

        status, attacker_id, defender_id, system_name = conflict

        if status == 'resolved':
            raise HTTPException(status_code=400, detail="Conflict already resolved")

        # Check authorization - must be involved in conflict
        partner_id = partner_info.get('partner_id')
        is_involved = partner_id in [attacker_id, defender_id]
        if not is_involved:
            # Check if in conflict_parties
            cursor.execute('SELECT id FROM conflict_parties WHERE conflict_id = ? AND partner_id = ?',
                           (conflict_id, partner_id))
            is_involved = cursor.fetchone() is not None

        if not partner_info.get('is_super_admin') and not is_involved:
            raise HTTPException(status_code=403, detail="Must be involved in conflict")

        now = datetime.now(timezone.utc).isoformat()

        # Update conflict with proposed resolution
        cursor.execute('''
            UPDATE conflicts SET resolution = ?, resolution_summary = ?,
                   resolution_proposed_by = ?, resolution_proposed_at = ?
            WHERE id = ?
        ''', (resolution, summary, partner_id, now, conflict_id))

        # Ensure all parties exist in conflict_parties
        cursor.execute('''
            INSERT OR IGNORE INTO conflict_parties (conflict_id, partner_id, side, is_primary)
            VALUES (?, ?, 'attacker', 1)
        ''', (conflict_id, attacker_id))
        cursor.execute('''
            INSERT OR IGNORE INTO conflict_parties (conflict_id, partner_id, side, is_primary)
            VALUES (?, ?, 'defender', 1)
        ''', (conflict_id, defender_id))

        # Reset all agreements
        cursor.execute('UPDATE conflict_parties SET resolution_agreed = 0 WHERE conflict_id = ?', (conflict_id,))

        # Mark proposer as agreed
        cursor.execute('''
            UPDATE conflict_parties SET resolution_agreed = 1, resolution_agreed_at = ?
            WHERE conflict_id = ? AND partner_id = ?
        ''', (now, conflict_id, partner_id))

        # Add timeline event
        cursor.execute('''
            INSERT INTO conflict_events (conflict_id, event_type, actor_partner_id, actor_username, details)
            VALUES (?, 'resolution_proposed', ?, ?, ?)
        ''', (conflict_id, partner_id, session_data.get('username'),
              f"Proposed resolution: {resolution.replace('_', ' ').title()}. {summary}"))

        conn.commit()

        # Notify all other parties
        cursor.execute('SELECT partner_id FROM conflict_parties WHERE conflict_id = ? AND partner_id != ?',
                       (conflict_id, partner_id))
        for (pid,) in cursor.fetchall():
            await send_war_notification(
                pid,
                'resolution_proposed',
                f"Resolution Proposed: {system_name}",
                f"A resolution has been proposed for the battle of {system_name}: {resolution.replace('_', ' ').title()}. Your agreement is needed.",
                conflict_id
            )

        logger.info(f"War Room: Resolution proposed for conflict {conflict_id}: {resolution}")
        return {'status': 'proposed', 'resolution': resolution, 'awaiting_agreement': True}
    finally:
        conn.close()


@app.put('/api/warroom/conflicts/{conflict_id}/agree-resolution')
async def agree_resolution(conflict_id: int, session: Optional[str] = Cookie(None)):
    """Agree to the proposed resolution."""
    session_data = get_session(session)
    partner_info = get_war_room_partner_info(session_data)
    if not partner_info:
        raise HTTPException(status_code=403, detail="Must be enrolled in War Room")

    partner_id = partner_info.get('partner_id')

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Get conflict and proposed resolution
        cursor.execute('''
            SELECT c.status, c.resolution, c.resolution_summary, c.target_system_id, c.target_system_name,
                   c.attacker_partner_id, c.defender_partner_id
            FROM conflicts c
            WHERE c.id = ?
        ''', (conflict_id,))
        conflict = cursor.fetchone()
        if not conflict:
            raise HTTPException(status_code=404, detail="Conflict not found")

        status, resolution, summary, system_id, system_name, attacker_id, defender_id = conflict

        if status == 'resolved':
            raise HTTPException(status_code=400, detail="Conflict already resolved")

        if not resolution:
            raise HTTPException(status_code=400, detail="No resolution has been proposed yet")

        # Check if party is involved
        cursor.execute('SELECT id FROM conflict_parties WHERE conflict_id = ? AND partner_id = ?',
                       (conflict_id, partner_id))
        if not cursor.fetchone() and not partner_info.get('is_super_admin'):
            raise HTTPException(status_code=403, detail="Must be involved in conflict")

        now = datetime.now(timezone.utc).isoformat()

        # Mark as agreed
        cursor.execute('''
            UPDATE conflict_parties SET resolution_agreed = 1, resolution_agreed_at = ?
            WHERE conflict_id = ? AND partner_id = ?
        ''', (now, conflict_id, partner_id))

        # Check if all primary parties have agreed
        cursor.execute('''
            SELECT COUNT(*) FROM conflict_parties
            WHERE conflict_id = ? AND is_primary = 1 AND resolution_agreed = 0
        ''', (conflict_id,))
        remaining = cursor.fetchone()[0]

        if remaining == 0:
            # All primary parties agreed - resolve the conflict!
            victor_id = None
            if resolution == 'attacker_victory':
                victor_id = attacker_id
            elif resolution == 'defender_victory':
                victor_id = defender_id

            cursor.execute('''
                UPDATE conflicts SET status = 'resolved', victor_partner_id = ?,
                       resolved_at = ?, resolved_by = 'mutual_agreement'
                WHERE id = ?
            ''', (victor_id, now, conflict_id))

            # Add timeline event
            cursor.execute('''
                INSERT INTO conflict_events (conflict_id, event_type, actor_username, details)
                VALUES (?, 'resolved', 'System', ?)
            ''', (conflict_id, f"Conflict resolved by mutual agreement: {resolution.replace('_', ' ').title()}"))

            # Transfer territory if attacker won
            if resolution == 'attacker_victory':
                cursor.execute('''
                    UPDATE territorial_claims SET claimant_partner_id = ?, claimed_at = ?
                    WHERE system_id = ?
                ''', (attacker_id, now, system_id))

            conn.commit()

            # Recalculate statistics
            await recalculate_war_statistics_internal(conn)

            # Add to activity feed
            await add_activity_feed_entry(
                'conflict_resolved',
                f"The Battle of {system_name} has ended: {resolution.replace('_', ' ').title()}!",
                conflict_id=conflict_id,
                system_name=system_name,
                details=summary
            )

            # Notify all parties
            cursor.execute('SELECT partner_id FROM conflict_parties WHERE conflict_id = ?', (conflict_id,))
            for (pid,) in cursor.fetchall():
                await send_war_notification(
                    pid,
                    'conflict_resolved',
                    f"Conflict Resolved: {system_name}",
                    f"The battle has ended by mutual agreement. Resolution: {resolution.replace('_', ' ').title()}",
                    conflict_id
                )

            logger.info(f"War Room: Conflict {conflict_id} resolved by mutual agreement: {resolution}")
            return {'status': 'resolved', 'resolution': resolution, 'victor_partner_id': victor_id}
        else:
            conn.commit()
            logger.info(f"War Room: Partner {partner_id} agreed to resolution for conflict {conflict_id}")
            return {'status': 'agreed', 'remaining_agreements_needed': remaining}
    finally:
        conn.close()


# --- Media Upload Endpoints ---

MEDIA_UPLOAD_DIR = Path(__file__).parent.parent / 'Haven-UI' / 'public' / 'war-media'
ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


@app.post('/api/warroom/media/upload')
async def upload_war_media(
    file: UploadFile,
    caption: str = None,
    conflict_id: int = None,
    session: Optional[str] = Cookie(None)
):
    """Upload a war image/screenshot."""
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail="Not authenticated")

    # Check user type - must be super admin, correspondent, or enrolled partner
    user_type = session_data.get('user_type')
    username = session_data.get('username')
    uploader_id = None

    if user_type == 'super_admin':
        pass
    elif user_type == 'correspondent':
        pass
    elif user_type in ['partner', 'sub_admin']:
        partner_info = get_war_room_partner_info(session_data)
        if not partner_info:
            raise HTTPException(status_code=403, detail="Must be enrolled in War Room")
        uploader_id = partner_info.get('partner_id')
    else:
        raise HTTPException(status_code=403, detail="Not authorized to upload media")

    # Validate file
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"File type not allowed. Allowed: {', '.join(ALLOWED_EXTENSIONS)}")

    # Read file content
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail=f"File too large. Max size: {MAX_FILE_SIZE // 1024 // 1024}MB")

    # Create upload directory if needed
    MEDIA_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    # Generate unique filename
    unique_id = secrets.token_hex(8)
    new_filename = f"{unique_id}{ext}"
    file_path = MEDIA_UPLOAD_DIR / new_filename

    # Save file
    with open(file_path, 'wb') as f:
        f.write(content)

    # Get mime type
    mime_types = {
        '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png',
        '.gif': 'image/gif', '.webp': 'image/webp'
    }
    mime_type = mime_types.get(ext, 'application/octet-stream')

    # Save to database
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO war_media
            (filename, original_filename, file_path, file_size, mime_type,
             uploaded_by_id, uploaded_by_username, uploaded_by_type, caption, related_conflict_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (new_filename, file.filename, f'/war-media/{new_filename}', len(content),
              mime_type, uploader_id, username, user_type, caption, conflict_id))
        conn.commit()
        media_id = cursor.lastrowid

        return {
            'status': 'uploaded',
            'media_id': media_id,
            'filename': new_filename,
            'url': f'/war-media/{new_filename}'
        }
    finally:
        conn.close()


@app.get('/api/warroom/media')
async def list_war_media(
    limit: int = 50,
    offset: int = 0,
    conflict_id: int = None,
    session: Optional[str] = Cookie(None)
):
    """List uploaded war media."""
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail="Not authenticated")

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        query = '''
            SELECT id, filename, original_filename, file_path, file_size, mime_type,
                   uploaded_by_username, uploaded_by_type, uploaded_at, caption, related_conflict_id
            FROM war_media
            WHERE is_active = 1
        '''
        params = []
        if conflict_id:
            query += ' AND related_conflict_id = ?'
            params.append(conflict_id)
        query += ' ORDER BY uploaded_at DESC LIMIT ? OFFSET ?'
        params.extend([limit, offset])

        cursor.execute(query, params)
        rows = cursor.fetchall()

        return [{
            'id': r[0],
            'filename': r[1],
            'original_filename': r[2],
            'url': r[3],
            'file_size': r[4],
            'mime_type': r[5],
            'uploaded_by': r[6],
            'uploaded_by_type': r[7],
            'uploaded_at': r[8],
            'caption': r[9],
            'conflict_id': r[10]
        } for r in rows]
    finally:
        conn.close()


@app.get('/api/warroom/media/{media_id}')
async def get_war_media(media_id: int, session: Optional[str] = Cookie(None)):
    """Get single media item details."""
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail="Not authenticated")

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            SELECT id, filename, original_filename, file_path, file_size, mime_type,
                   uploaded_by_username, uploaded_by_type, uploaded_at, caption, related_conflict_id
            FROM war_media WHERE id = ? AND is_active = 1
        ''', (media_id,))
        r = cursor.fetchone()
        if not r:
            raise HTTPException(status_code=404, detail="Media not found")

        return {
            'id': r[0],
            'filename': r[1],
            'original_filename': r[2],
            'url': r[3],
            'file_size': r[4],
            'mime_type': r[5],
            'uploaded_by': r[6],
            'uploaded_by_type': r[7],
            'uploaded_at': r[8],
            'caption': r[9],
            'conflict_id': r[10]
        }
    finally:
        conn.close()


@app.delete('/api/warroom/media/{media_id}')
async def delete_war_media(media_id: int, session: Optional[str] = Cookie(None)):
    """Delete a media item (soft delete)."""
    session_data = get_session(session)
    if not session_data or session_data.get('user_type') != 'super_admin':
        raise HTTPException(status_code=403, detail="Super admin access required")

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('UPDATE war_media SET is_active = 0 WHERE id = ?', (media_id,))
        conn.commit()
        return {'status': 'deleted', 'media_id': media_id}
    finally:
        conn.close()


# --- Reporting Organizations Endpoints ---

@app.get('/api/warroom/reporting-orgs')
async def list_reporting_orgs(session: Optional[str] = Cookie(None)):
    """List reporting organizations."""
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail="Not authenticated")

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            SELECT ro.id, ro.name, ro.description, ro.discord_server_id, ro.discord_server_name,
                   ro.logo_url, ro.is_active, ro.created_at,
                   (SELECT COUNT(*) FROM reporting_org_members WHERE org_id = ro.id AND is_active = 1) as member_count
            FROM reporting_organizations ro
            ORDER BY ro.name
        ''')
        rows = cursor.fetchall()

        return [{
            'id': r[0],
            'name': r[1],
            'description': r[2],
            'discord_server_id': r[3],
            'discord_server_name': r[4],
            'logo_url': r[5],
            'is_active': bool(r[6]),
            'created_at': r[7],
            'member_count': r[8]
        } for r in rows]
    finally:
        conn.close()


@app.post('/api/warroom/reporting-orgs')
async def create_reporting_org(request: Request, session: Optional[str] = Cookie(None)):
    """Create a reporting organization (super admin only)."""
    session_data = get_session(session)
    if not session_data or session_data.get('user_type') != 'super_admin':
        raise HTTPException(status_code=403, detail="Super admin access required")

    data = await request.json()
    name = data.get('name')
    if not name:
        raise HTTPException(status_code=400, detail="name required")

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO reporting_organizations (name, description, discord_server_id, discord_server_name, logo_url, created_by)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (name, data.get('description'), data.get('discord_server_id'),
              data.get('discord_server_name'), data.get('logo_url'), session_data.get('username')))
        conn.commit()

        logger.info(f"War Room: Reporting org created: {name}")
        return {'status': 'created', 'org_id': cursor.lastrowid}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="Organization name already exists")
    finally:
        conn.close()


@app.put('/api/warroom/reporting-orgs/{org_id}')
async def update_reporting_org(org_id: int, request: Request, session: Optional[str] = Cookie(None)):
    """Update a reporting organization."""
    session_data = get_session(session)
    if not session_data or session_data.get('user_type') != 'super_admin':
        raise HTTPException(status_code=403, detail="Super admin access required")

    data = await request.json()

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        updates = []
        params = []
        for field in ['name', 'description', 'discord_server_id', 'discord_server_name', 'logo_url', 'is_active']:
            if field in data:
                updates.append(f'{field} = ?')
                params.append(data[field])

        if not updates:
            raise HTTPException(status_code=400, detail="No fields to update")

        params.append(org_id)
        cursor.execute(f'UPDATE reporting_organizations SET {", ".join(updates)} WHERE id = ?', params)
        conn.commit()

        return {'status': 'updated', 'org_id': org_id}
    finally:
        conn.close()


@app.delete('/api/warroom/reporting-orgs/{org_id}')
async def delete_reporting_org(org_id: int, session: Optional[str] = Cookie(None)):
    """Delete a reporting organization (soft delete)."""
    session_data = get_session(session)
    if not session_data or session_data.get('user_type') != 'super_admin':
        raise HTTPException(status_code=403, detail="Super admin access required")

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('UPDATE reporting_organizations SET is_active = 0 WHERE id = ?', (org_id,))
        conn.commit()
        return {'status': 'deleted', 'org_id': org_id}
    finally:
        conn.close()


@app.get('/api/warroom/reporting-orgs/{org_id}/members')
async def list_org_members(org_id: int, session: Optional[str] = Cookie(None)):
    """List members of a reporting organization."""
    session_data = get_session(session)
    if not session_data or session_data.get('user_type') != 'super_admin':
        raise HTTPException(status_code=403, detail="Super admin access required")

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            SELECT id, username, display_name, role, is_active, created_at, last_login_at
            FROM reporting_org_members
            WHERE org_id = ?
            ORDER BY created_at DESC
        ''', (org_id,))
        rows = cursor.fetchall()

        return [{
            'id': r[0],
            'username': r[1],
            'display_name': r[2],
            'role': r[3],
            'is_active': bool(r[4]),
            'created_at': r[5],
            'last_login_at': r[6]
        } for r in rows]
    finally:
        conn.close()


@app.post('/api/warroom/reporting-orgs/{org_id}/members')
async def add_org_member(org_id: int, request: Request, session: Optional[str] = Cookie(None)):
    """Add a member to a reporting organization."""
    session_data = get_session(session)
    if not session_data or session_data.get('user_type') != 'super_admin':
        raise HTTPException(status_code=403, detail="Super admin access required")

    data = await request.json()
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        raise HTTPException(status_code=400, detail="username and password required")

    password_hash = hashlib.sha256(password.encode()).hexdigest()

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Verify org exists
        cursor.execute('SELECT id FROM reporting_organizations WHERE id = ? AND is_active = 1', (org_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Organization not found")

        cursor.execute('''
            INSERT INTO reporting_org_members (org_id, username, password_hash, display_name, role, created_by)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (org_id, username, password_hash, data.get('display_name'), data.get('role', 'reporter'),
              session_data.get('username')))
        conn.commit()

        logger.info(f"War Room: Member {username} added to org {org_id}")
        return {'status': 'created', 'member_id': cursor.lastrowid}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="Username already exists in this organization")
    finally:
        conn.close()


@app.post('/api/warroom/reporting-orgs/login')
async def reporting_org_login(request: Request, response: Response):
    """Login as a reporting organization member."""
    data = await request.json()
    username = data.get('username')
    password = data.get('password')
    org_id = data.get('org_id')

    if not username or not password:
        raise HTTPException(status_code=400, detail="username and password required")

    password_hash = hashlib.sha256(password.encode()).hexdigest()

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        query = '''
            SELECT rom.id, rom.org_id, rom.username, rom.display_name, rom.role, rom.is_active,
                   ro.name as org_name, ro.is_active as org_active
            FROM reporting_org_members rom
            JOIN reporting_organizations ro ON rom.org_id = ro.id
            WHERE rom.username = ? AND rom.password_hash = ?
        '''
        params = [username, password_hash]
        if org_id:
            query += ' AND rom.org_id = ?'
            params.append(org_id)

        cursor.execute(query, params)
        member = cursor.fetchone()

        if not member:
            raise HTTPException(status_code=401, detail="Invalid credentials")

        if not member[5]:
            raise HTTPException(status_code=403, detail="Account is inactive")
        if not member[7]:
            raise HTTPException(status_code=403, detail="Organization is inactive")

        # Update last login
        cursor.execute('UPDATE reporting_org_members SET last_login_at = ? WHERE id = ?',
                       (datetime.now(timezone.utc).isoformat(), member[0]))
        conn.commit()

        # Create session
        session_id = secrets.token_hex(32)
        session_data = {
            'user_type': 'reporter',
            'username': member[2],
            'display_name': member[3] or member[2],
            'member_id': member[0],
            'org_id': member[1],
            'org_name': member[6],
            'role': member[4]
        }
        sessions[session_id] = session_data

        response.set_cookie(
            key='session',
            value=session_id,
            httponly=True,
            secure=False,
            samesite='lax',
            max_age=86400 * 7
        )

        logger.info(f"War Room: Reporter {username} logged in (org: {member[6]})")
        return {
            'status': 'success',
            'username': member[2],
            'display_name': member[3] or member[2],
            'org_name': member[6],
            'role': member[4],
            'user_type': 'reporter'
        }
    finally:
        conn.close()


# --- Enhanced News Endpoints ---

@app.get('/api/warroom/news/{news_id}')
async def get_news_article(news_id: int, session: Optional[str] = Cookie(None)):
    """Get a single news article with full details."""
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail="Not authenticated")

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            SELECT wn.id, wn.headline, wn.body, wn.author_username, wn.author_type,
                   wn.related_conflict_id, wn.published_at, wn.is_pinned, wn.article_type,
                   wn.featured_image_id, wn.reporting_org_id, wn.view_count,
                   ro.name as org_name,
                   wm.file_path as featured_image_url
            FROM war_news wn
            LEFT JOIN reporting_organizations ro ON wn.reporting_org_id = ro.id
            LEFT JOIN war_media wm ON wn.featured_image_id = wm.id
            WHERE wn.id = ? AND wn.is_active = 1
        ''', (news_id,))
        r = cursor.fetchone()
        if not r:
            raise HTTPException(status_code=404, detail="Article not found")

        # Increment view count
        cursor.execute('UPDATE war_news SET view_count = view_count + 1 WHERE id = ?', (news_id,))
        conn.commit()

        # Get attached media
        cursor.execute('''
            SELECT id, filename, file_path, caption FROM war_media
            WHERE related_news_id = ? AND is_active = 1
        ''', (news_id,))
        media = cursor.fetchall()

        return {
            'id': r[0],
            'headline': r[1],
            'body': r[2],
            'author': r[3],
            'author_type': r[4],
            'conflict_id': r[5],
            'published_at': r[6],
            'is_pinned': bool(r[7]),
            'article_type': r[8],
            'featured_image_id': r[9],
            'reporting_org_id': r[10],
            'view_count': r[11] + 1,
            'org_name': r[12],
            'featured_image_url': r[13],
            'media': [{
                'id': m[0],
                'filename': m[1],
                'url': m[2],
                'caption': m[3]
            } for m in media]
        }
    finally:
        conn.close()


@app.put('/api/warroom/news/{news_id}')
async def update_news_article(news_id: int, request: Request, session: Optional[str] = Cookie(None)):
    """Update a news article."""
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail="Not authenticated")

    # Check if super admin, correspondent, or reporter who owns the article
    user_type = session_data.get('user_type')
    username = session_data.get('username')

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Get article
        cursor.execute('SELECT author_username, author_type FROM war_news WHERE id = ? AND is_active = 1', (news_id,))
        article = cursor.fetchone()
        if not article:
            raise HTTPException(status_code=404, detail="Article not found")

        # Authorization
        if user_type != 'super_admin':
            if article[0] != username:
                raise HTTPException(status_code=403, detail="Can only edit your own articles")

        data = await request.json()
        updates = []
        params = []

        for field in ['headline', 'body', 'article_type', 'is_pinned', 'featured_image_id', 'related_conflict_id']:
            if field in data:
                updates.append(f'{field} = ?')
                params.append(data[field])

        if not updates:
            raise HTTPException(status_code=400, detail="No fields to update")

        params.append(news_id)
        cursor.execute(f'UPDATE war_news SET {", ".join(updates)} WHERE id = ?', params)
        conn.commit()

        return {'status': 'updated', 'news_id': news_id}
    finally:
        conn.close()


# =============================================================================
# WAR ROOM V3 - TERRITORY INTEGRATION & PEACE TREATY SYSTEM
# =============================================================================

def create_auto_news(conn, event_type: str, headline: str, body: str, reference_id: int = None, reference_type: str = None, conflict_id: int = None):
    """Helper to create auto-generated news articles for war events."""
    cursor = conn.cursor()

    # Check if we already created news for this event
    if reference_id and reference_type:
        cursor.execute('''
            SELECT id FROM auto_news_events
            WHERE event_type = ? AND reference_id = ? AND reference_type = ?
        ''', (event_type, reference_id, reference_type))
        if cursor.fetchone():
            return None  # Already generated

    # Create the news article
    cursor.execute('''
        INSERT INTO war_news (headline, body, author_username, author_type, related_conflict_id, article_type)
        VALUES (?, ?, 'SYSTEM', 'auto', ?, 'breaking')
    ''', (headline, body, conflict_id))
    news_id = cursor.lastrowid

    # Record that we generated this
    cursor.execute('''
        INSERT INTO auto_news_events (event_type, reference_id, reference_type, news_id)
        VALUES (?, ?, ?, ?)
    ''', (event_type, reference_id, reference_type, news_id))

    # Also add to activity feed
    cursor.execute('''
        INSERT INTO war_activity_feed (event_type, headline, details, conflict_id, is_public)
        VALUES (?, ?, ?, ?, 1)
    ''', (event_type, headline, body, conflict_id))

    return news_id


@app.get('/api/warroom/territory/by-tag')
async def get_territory_by_discord_tag(discord_tag: str = None, session: Optional[str] = Cookie(None)):
    """Get all systems owned by a discord_tag (partner territory)."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Get partner info for this discord_tag
        cursor.execute('''
            SELECT p.id, p.display_name, p.region_color, p.discord_tag
            FROM partner_accounts p
            WHERE p.discord_tag = ? AND p.is_active = 1
        ''', (discord_tag,))
        partner = cursor.fetchone()

        if not partner:
            return {'partner': None, 'systems': [], 'regions': {}}

        partner_id, display_name, color, tag = partner

        # Get all systems with this discord_tag
        cursor.execute('''
            SELECT id, name, galaxy, region_name, glyphs, region_x, region_y, region_z, reality
            FROM systems
            WHERE discord_tag = ?
            ORDER BY name
        ''', (discord_tag,))
        systems = cursor.fetchall()

        # Group by region and calculate ownership
        regions = {}
        for s in systems:
            region_key = f"{s[5]}_{s[6]}_{s[7]}_{s[2]}"  # x_y_z_galaxy
            if region_key not in regions:
                regions[region_key] = {
                    'region_x': s[5],
                    'region_y': s[6],
                    'region_z': s[7],
                    'galaxy': s[2],
                    'region_name': s[3],
                    'system_count': 0,
                    'systems': []
                }
            regions[region_key]['system_count'] += 1
            regions[region_key]['systems'].append({
                'id': s[0],
                'name': s[1],
                'glyphs': s[4],
                'reality': s[8]
            })

        return {
            'partner': {
                'id': partner_id,
                'display_name': display_name,
                'color': color,
                'discord_tag': tag
            },
            'systems': [{
                'id': s[0],
                'name': s[1],
                'galaxy': s[2],
                'region_name': s[3],
                'glyphs': s[4],
                'region_x': s[5],
                'region_y': s[6],
                'region_z': s[7],
                'reality': s[8]
            } for s in systems],
            'regions': regions,
            'total_systems': len(systems),
            'total_regions': len(regions)
        }
    finally:
        conn.close()


@app.get('/api/warroom/territory/search')
async def search_territory_systems(
    q: str = '',
    discord_tag: str = None,
    galaxy: str = None,
    limit: int = 50,
    session: Optional[str] = Cookie(None)
):
    """Search systems by name, filtering by discord_tag (for territory selection)."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        query = '''
            SELECT s.id, s.name, s.galaxy, r.custom_name as region_name, s.glyph_code,
                   s.region_x, s.region_y, s.region_z, s.discord_tag, s.reality,
                   p.display_name as owner_name, p.region_color as owner_color
            FROM systems s
            LEFT JOIN regions r ON s.region_x = r.region_x AND s.region_y = r.region_y
                AND s.region_z = r.region_z AND COALESCE(s.galaxy, 'Euclid') = COALESCE(r.galaxy, 'Euclid')
            LEFT JOIN partner_accounts p ON s.discord_tag = p.discord_tag AND p.is_active = 1
            WHERE 1=1
        '''
        params = []

        if q:
            query += ' AND (s.name LIKE ? OR r.custom_name LIKE ?)'
            params.extend([f'%{q}%', f'%{q}%'])

        if discord_tag:
            query += ' AND s.discord_tag = ?'
            params.append(discord_tag)

        if galaxy:
            query += ' AND s.galaxy = ?'
            params.append(galaxy)

        query += ' ORDER BY s.name LIMIT ?'
        params.append(limit)

        cursor.execute(query, params)
        results = cursor.fetchall()

        return [{
            'id': r[0],
            'name': r[1],
            'galaxy': r[2],
            'region_name': r[3],
            'glyphs': r[4],
            'region_x': r[5],
            'region_y': r[6],
            'region_z': r[7],
            'discord_tag': r[8],
            'reality': r[9],
            'owner_name': r[10],
            'owner_color': r[11],
            'is_partner_owned': r[10] is not None
        } for r in results]
    finally:
        conn.close()


@app.get('/api/warroom/territory/regions')
async def get_territory_regions(
    discord_tag: str = None,
    galaxy: str = 'Euclid',
    session: Optional[str] = Cookie(None)
):
    """Get regions with system counts, optionally filtered by discord_tag."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Get regions from systems table, grouped by coordinates
        query = '''
            SELECT
                s.region_x, s.region_y, s.region_z, s.galaxy,
                r.custom_name as region_name,
                s.discord_tag,
                COUNT(*) as system_count,
                p.display_name as owner_name,
                p.region_color as owner_color,
                p.id as partner_id
            FROM systems s
            LEFT JOIN regions r ON s.region_x = r.region_x AND s.region_y = r.region_y
                AND s.region_z = r.region_z AND COALESCE(s.galaxy, 'Euclid') = COALESCE(r.galaxy, 'Euclid')
            LEFT JOIN partner_accounts p ON s.discord_tag = p.discord_tag AND p.is_active = 1
            WHERE s.galaxy = ?
        '''
        params = [galaxy]

        if discord_tag:
            query += ' AND s.discord_tag = ?'
            params.append(discord_tag)

        query += '''
            GROUP BY s.region_x, s.region_y, s.region_z, s.galaxy, s.discord_tag
            ORDER BY system_count DESC
        '''

        cursor.execute(query, params)
        results = cursor.fetchall()

        # Calculate region ownership (>50% = controls region)
        region_data = {}
        for r in results:
            key = f"{r[0]}_{r[1]}_{r[2]}_{r[3]}"
            if key not in region_data:
                region_data[key] = {
                    'region_x': r[0],
                    'region_y': r[1],
                    'region_z': r[2],
                    'galaxy': r[3],
                    'region_name': r[4],
                    'total_systems': 0,
                    'owners': {}
                }

            region_data[key]['total_systems'] += r[6]
            tag = r[5] or 'unclaimed'
            if tag not in region_data[key]['owners']:
                region_data[key]['owners'][tag] = {
                    'count': 0,
                    'name': r[7],
                    'color': r[8],
                    'partner_id': r[9]
                }
            region_data[key]['owners'][tag]['count'] += r[6]

        # Determine controlling faction for each region
        regions = []
        for key, data in region_data.items():
            controlling = None
            for tag, owner_info in data['owners'].items():
                if owner_info['count'] > data['total_systems'] / 2:
                    controlling = {
                        'discord_tag': tag,
                        'name': owner_info['name'],
                        'color': owner_info['color'],
                        'partner_id': owner_info['partner_id'],
                        'system_count': owner_info['count'],
                        'percentage': round(owner_info['count'] / data['total_systems'] * 100, 1)
                    }
                    break

            regions.append({
                'region_x': data['region_x'],
                'region_y': data['region_y'],
                'region_z': data['region_z'],
                'galaxy': data['galaxy'],
                'region_name': data['region_name'],
                'total_systems': data['total_systems'],
                'controlling_faction': controlling,
                'owners': data['owners']
            })

        return regions
    finally:
        conn.close()


@app.get('/api/warroom/territory/region-ownership')
async def get_region_ownership_summary(galaxy: str = 'Euclid', session: Optional[str] = Cookie(None)):
    """Get summary of which factions control which regions (>50% ownership)."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Get all systems grouped by region and discord_tag
        cursor.execute('''
            SELECT
                s.region_x, s.region_y, s.region_z, s.galaxy,
                MAX(r.custom_name) as region_name,
                s.discord_tag,
                COUNT(*) as system_count,
                p.display_name,
                p.region_color,
                p.id as partner_id
            FROM systems s
            LEFT JOIN regions r ON s.region_x = r.region_x AND s.region_y = r.region_y
                AND s.region_z = r.region_z AND COALESCE(s.galaxy, 'Euclid') = COALESCE(r.galaxy, 'Euclid')
            LEFT JOIN partner_accounts p ON s.discord_tag = p.discord_tag AND p.is_active = 1
            WHERE s.galaxy = ?
            GROUP BY s.region_x, s.region_y, s.region_z, s.galaxy, s.discord_tag
        ''', (galaxy,))

        results = cursor.fetchall()

        # Process into regions
        regions = {}
        for r in results:
            key = f"{r[0]}_{r[1]}_{r[2]}"
            if key not in regions:
                regions[key] = {
                    'region_x': r[0],
                    'region_y': r[1],
                    'region_z': r[2],
                    'galaxy': r[3],
                    'region_name': r[4],
                    'total': 0,
                    'by_owner': {}
                }
            regions[key]['total'] += r[6]
            tag = r[5] or 'unclaimed'
            regions[key]['by_owner'][tag] = {
                'count': r[6],
                'name': r[7],
                'color': r[8],
                'partner_id': r[9]
            }

        # Determine controllers
        controlled_regions = []
        for key, data in regions.items():
            for tag, info in data['by_owner'].items():
                if info['count'] > data['total'] / 2 and tag != 'unclaimed':
                    controlled_regions.append({
                        **{k: data[k] for k in ['region_x', 'region_y', 'region_z', 'galaxy', 'region_name', 'total']},
                        'controller': {
                            'discord_tag': tag,
                            'name': info['name'],
                            'color': info['color'],
                            'partner_id': info['partner_id'],
                            'systems': info['count'],
                            'percentage': round(info['count'] / data['total'] * 100, 1)
                        }
                    })
                    break

        return {
            'galaxy': galaxy,
            'controlled_regions': controlled_regions,
            'total_regions_with_control': len(controlled_regions)
        }
    finally:
        conn.close()


# Peace Treaty Endpoints

@app.post('/api/warroom/conflicts/{conflict_id}/propose-peace')
async def propose_peace_treaty(conflict_id: int, request: Request, session: Optional[str] = Cookie(None)):
    """Propose a peace treaty with demands/offers."""
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail="Not authenticated")

    partner_id = session_data.get('partner_id')
    username = session_data.get('username')
    user_type = session_data.get('user_type')

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Get conflict details
        cursor.execute('''
            SELECT c.attacker_partner_id, c.defender_partner_id, c.status,
                   c.attacker_counter_count, c.defender_counter_count,
                   c.negotiation_status,
                   a.display_name as attacker_name,
                   d.display_name as defender_name
            FROM conflicts c
            JOIN partner_accounts a ON c.attacker_partner_id = a.id
            JOIN partner_accounts d ON c.defender_partner_id = d.id
            WHERE c.id = ?
        ''', (conflict_id,))
        conflict = cursor.fetchone()

        if not conflict:
            raise HTTPException(status_code=404, detail="Conflict not found")

        attacker_id, defender_id, status, att_counters, def_counters, neg_status, attacker_name, defender_name = conflict

        if status == 'resolved':
            raise HTTPException(status_code=400, detail="Conflict already resolved")

        # Check if user is party to the conflict
        is_attacker = partner_id == attacker_id
        is_defender = partner_id == defender_id
        is_super = user_type == 'super_admin'

        if not (is_attacker or is_defender or is_super):
            raise HTTPException(status_code=403, detail="Not a party to this conflict")

        data = await request.json()
        items = data.get('items', [])  # List of {type: system/region, direction: give/receive, system_id/region coords, to/from partner}
        message = data.get('message', '')
        is_counter = data.get('is_counter', False)

        # Check counter limits (2 per side)
        if is_counter:
            if is_attacker and att_counters >= 2:
                raise HTTPException(status_code=400, detail="Maximum counter-offers reached (2). You must accept, reject, or continue fighting.")
            if is_defender and def_counters >= 2:
                raise HTTPException(status_code=400, detail="Maximum counter-offers reached (2). You must accept, reject, or continue fighting.")

        # Validate items - ensure HQ systems are not included
        for item in items:
            if item.get('type') == 'system' and item.get('system_id'):
                # Check if this is an HQ system
                cursor.execute('''
                    SELECT e.partner_id, e.home_region_x, e.home_region_y, e.home_region_z,
                           e.is_hq_protected, s.region_x, s.region_y, s.region_z
                    FROM war_room_enrollment e
                    JOIN systems s ON s.id = ?
                    WHERE e.is_hq_protected = 1
                      AND e.home_region_x = s.region_x
                      AND e.home_region_y = s.region_y
                      AND e.home_region_z = s.region_z
                ''', (item['system_id'],))
                hq_check = cursor.fetchone()
                if hq_check:
                    raise HTTPException(status_code=400, detail="Cannot include HQ/Home region systems in peace demands")

        # Determine recipient
        recipient_id = defender_id if is_attacker else attacker_id

        # Mark any pending proposals as superseded
        cursor.execute('''
            UPDATE peace_proposals SET status = 'superseded', responded_at = datetime('now')
            WHERE conflict_id = ? AND status = 'pending'
        ''', (conflict_id,))

        # Create the proposal
        cursor.execute('''
            INSERT INTO peace_proposals (conflict_id, proposer_partner_id, recipient_partner_id,
                                        proposal_type, counter_number, message)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (conflict_id, partner_id, recipient_id,
              'counter' if is_counter else 'initial',
              (att_counters if is_attacker else def_counters) + (1 if is_counter else 0),
              message))
        proposal_id = cursor.lastrowid

        # Add proposal items
        for item in items:
            cursor.execute('''
                INSERT INTO proposal_items (proposal_id, item_type, direction, system_id, system_name,
                                           region_x, region_y, region_z, region_name, galaxy,
                                           from_partner_id, to_partner_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                proposal_id,
                item.get('type', 'system'),
                item.get('direction', 'give'),
                item.get('system_id'),
                item.get('system_name'),
                item.get('region_x'),
                item.get('region_y'),
                item.get('region_z'),
                item.get('region_name'),
                item.get('galaxy', 'Euclid'),
                item.get('from_partner_id', partner_id),
                item.get('to_partner_id', recipient_id)
            ))

        # Update conflict negotiation status
        cursor.execute('''
            UPDATE conflicts SET
                negotiation_status = 'pending',
                negotiation_started_at = COALESCE(negotiation_started_at, datetime('now'))
        ''', ())
        cursor.execute('UPDATE conflicts SET negotiation_status = ? WHERE id = ?', ('pending', conflict_id))

        # Increment counter count if this is a counter-offer
        if is_counter:
            if is_attacker:
                cursor.execute('UPDATE conflicts SET attacker_counter_count = attacker_counter_count + 1 WHERE id = ?', (conflict_id,))
            else:
                cursor.execute('UPDATE conflicts SET defender_counter_count = defender_counter_count + 1 WHERE id = ?', (conflict_id,))

        # Create notification for recipient
        cursor.execute('''
            INSERT INTO war_notifications (recipient_partner_id, notification_type, title, message, related_conflict_id)
            VALUES (?, 'peace_proposal', ?, ?, ?)
        ''', (recipient_id, 'Peace Treaty Proposed', f'A peace proposal has been sent for the conflict. Review the terms.', conflict_id))

        # Auto-news: Negotiations started
        proposer_name = attacker_name if is_attacker else defender_name
        create_auto_news(
            conn,
            'negotiations_started' if not is_counter else 'counter_offer',
            f"Peace Negotiations {'Continue' if is_counter else 'Begin'}: {attacker_name} vs {defender_name}",
            f"{proposer_name} has {'sent a counter-offer' if is_counter else 'proposed peace terms'} in the ongoing conflict.",
            reference_id=proposal_id,
            reference_type='peace_proposal',
            conflict_id=conflict_id
        )

        # Add conflict event
        cursor.execute('''
            INSERT INTO conflict_events (conflict_id, event_type, actor_partner_id, actor_username, details)
            VALUES (?, ?, ?, ?, ?)
        ''', (conflict_id, 'peace_proposed', partner_id, username,
              f"{'Counter-offer' if is_counter else 'Peace proposal'} submitted with {len(items)} items"))

        conn.commit()
        return {'status': 'proposed', 'proposal_id': proposal_id}
    finally:
        conn.close()


@app.get('/api/warroom/conflicts/{conflict_id}/peace-proposals')
async def get_peace_proposals(conflict_id: int, session: Optional[str] = Cookie(None)):
    """Get all peace proposals for a conflict."""
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail="Not authenticated")

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Get proposals
        cursor.execute('''
            SELECT pp.id, pp.proposer_partner_id, pp.recipient_partner_id, pp.proposal_type,
                   pp.counter_number, pp.status, pp.proposed_at, pp.responded_at, pp.message,
                   prop.display_name as proposer_name, prop.region_color as proposer_color,
                   rec.display_name as recipient_name, rec.region_color as recipient_color
            FROM peace_proposals pp
            JOIN partner_accounts prop ON pp.proposer_partner_id = prop.id
            JOIN partner_accounts rec ON pp.recipient_partner_id = rec.id
            WHERE pp.conflict_id = ?
            ORDER BY pp.proposed_at DESC
        ''', (conflict_id,))
        proposals = cursor.fetchall()

        result = []
        for p in proposals:
            # Get items for this proposal
            cursor.execute('''
                SELECT id, item_type, direction, system_id, system_name,
                       region_x, region_y, region_z, region_name, galaxy,
                       from_partner_id, to_partner_id
                FROM proposal_items WHERE proposal_id = ?
            ''', (p[0],))
            items = cursor.fetchall()

            result.append({
                'id': p[0],
                'proposer_partner_id': p[1],
                'recipient_partner_id': p[2],
                'proposal_type': p[3],
                'counter_number': p[4],
                'status': p[5],
                'proposed_at': p[6],
                'responded_at': p[7],
                'message': p[8],
                'proposer_name': p[9],
                'proposer_color': p[10],
                'recipient_name': p[11],
                'recipient_color': p[12],
                'items': [{
                    'id': i[0],
                    'item_type': i[1],
                    'direction': i[2],
                    'system_id': i[3],
                    'system_name': i[4],
                    'region_x': i[5],
                    'region_y': i[6],
                    'region_z': i[7],
                    'region_name': i[8],
                    'galaxy': i[9],
                    'from_partner_id': i[10],
                    'to_partner_id': i[11]
                } for i in items]
            })

        return result
    finally:
        conn.close()


@app.put('/api/warroom/peace-proposals/{proposal_id}/accept')
async def accept_peace_proposal(proposal_id: int, session: Optional[str] = Cookie(None)):
    """Accept a peace proposal, ending the conflict and transferring territory."""
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail="Not authenticated")

    partner_id = session_data.get('partner_id')
    username = session_data.get('username')
    user_type = session_data.get('user_type')

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Get proposal details
        cursor.execute('''
            SELECT pp.id, pp.conflict_id, pp.proposer_partner_id, pp.recipient_partner_id, pp.status,
                   c.attacker_partner_id, c.defender_partner_id, c.declared_at,
                   a.display_name as attacker_name, a.discord_tag as attacker_tag,
                   d.display_name as defender_name, d.discord_tag as defender_tag
            FROM peace_proposals pp
            JOIN conflicts c ON pp.conflict_id = c.id
            JOIN partner_accounts a ON c.attacker_partner_id = a.id
            JOIN partner_accounts d ON c.defender_partner_id = d.id
            WHERE pp.id = ?
        ''', (proposal_id,))
        proposal = cursor.fetchone()

        if not proposal:
            raise HTTPException(status_code=404, detail="Proposal not found")

        if proposal[4] != 'pending':
            raise HTTPException(status_code=400, detail="Proposal is not pending")

        # Check authorization - only recipient can accept
        if partner_id != proposal[3] and user_type != 'super_admin':
            raise HTTPException(status_code=403, detail="Only the recipient can accept this proposal")

        conflict_id = proposal[1]
        attacker_id = proposal[5]
        defender_id = proposal[6]
        declared_at = proposal[7]
        attacker_name = proposal[8]
        attacker_tag = proposal[9]
        defender_name = proposal[10]
        defender_tag = proposal[11]

        # Get items to transfer
        cursor.execute('SELECT * FROM proposal_items WHERE proposal_id = ?', (proposal_id,))
        items = cursor.fetchall()

        # Execute territory transfers
        systems_transferred = 0
        for item in items:
            item_type = item[2]
            direction = item[3]
            system_id = item[4]
            from_partner = item[11]
            to_partner = item[12]

            if item_type == 'system' and system_id:
                # Get the receiving partner's discord_tag
                cursor.execute('SELECT discord_tag FROM partner_accounts WHERE id = ?', (to_partner,))
                to_tag_row = cursor.fetchone()
                if to_tag_row:
                    new_tag = to_tag_row[0]

                    # Update systems.discord_tag
                    cursor.execute('UPDATE systems SET discord_tag = ? WHERE id = ?', (new_tag, system_id))

                    # Update or create territorial_claims
                    cursor.execute('DELETE FROM territorial_claims WHERE system_id = ?', (system_id,))
                    cursor.execute('''
                        INSERT INTO territorial_claims (system_id, claimant_partner_id, claim_type, notes)
                        VALUES (?, ?, 'conquered', 'Transferred via peace treaty')
                    ''', (system_id, to_partner))

                    systems_transferred += 1

            elif item_type == 'region':
                # Transfer all systems in the region
                region_x = item[5]
                region_y = item[6]
                region_z = item[7]
                galaxy = item[10]

                cursor.execute('SELECT discord_tag FROM partner_accounts WHERE id = ?', (to_partner,))
                to_tag_row = cursor.fetchone()
                if to_tag_row:
                    new_tag = to_tag_row[0]

                    # Get from_partner's discord_tag to only transfer their systems
                    cursor.execute('SELECT discord_tag FROM partner_accounts WHERE id = ?', (from_partner,))
                    from_tag_row = cursor.fetchone()
                    if from_tag_row:
                        from_tag = from_tag_row[0]

                        # Update all systems in region from the giving partner
                        cursor.execute('''
                            UPDATE systems SET discord_tag = ?
                            WHERE region_x = ? AND region_y = ? AND region_z = ?
                              AND galaxy = ? AND discord_tag = ?
                        ''', (new_tag, region_x, region_y, region_z, galaxy, from_tag))
                        systems_transferred += cursor.rowcount

        # Mark proposal as accepted
        cursor.execute('''
            UPDATE peace_proposals SET status = 'accepted', responded_at = datetime('now'), response_by = ?
            WHERE id = ?
        ''', (username, proposal_id))

        # Resolve the conflict
        cursor.execute('''
            UPDATE conflicts SET
                status = 'resolved',
                resolution = 'peace_treaty',
                resolved_at = datetime('now'),
                resolved_by = ?,
                negotiation_status = 'accepted',
                resolution_summary = ?
            WHERE id = ?
        ''', (username, f"Peace treaty accepted. {systems_transferred} systems transferred.", conflict_id))

        # Add conflict event
        cursor.execute('''
            INSERT INTO conflict_events (conflict_id, event_type, actor_partner_id, actor_username, details)
            VALUES (?, 'peace_accepted', ?, ?, ?)
        ''', (conflict_id, partner_id, username, f"Peace treaty accepted. {systems_transferred} systems transferred."))

        # Calculate war duration
        from datetime import datetime as dt
        try:
            start = dt.fromisoformat(declared_at.replace('Z', '+00:00'))
            end = dt.now()
            duration = end - start
            duration_str = f"{duration.days} days" if duration.days > 0 else f"{duration.seconds // 3600} hours"
        except:
            duration_str = "unknown duration"

        # Auto-news: Peace concluded
        create_auto_news(
            conn,
            'peace_concluded',
            f"WAR ENDS: {attacker_name} and {defender_name} Sign Peace Treaty",
            f"After {duration_str} of conflict, peace has been achieved. {systems_transferred} systems changed hands as part of the agreement.",
            reference_id=conflict_id,
            reference_type='conflict',
            conflict_id=conflict_id
        )

        # Notify both parties
        cursor.execute('''
            INSERT INTO war_notifications (recipient_partner_id, notification_type, title, message, related_conflict_id)
            VALUES (?, 'peace_accepted', 'Peace Treaty Accepted', 'The peace treaty has been accepted. The war has ended.', ?)
        ''', (proposal[2], conflict_id))  # Notify proposer

        conn.commit()

        return {
            'status': 'accepted',
            'conflict_resolved': True,
            'systems_transferred': systems_transferred,
            'duration': duration_str
        }
    finally:
        conn.close()


@app.put('/api/warroom/peace-proposals/{proposal_id}/reject')
async def reject_peace_proposal(proposal_id: int, request: Request, session: Optional[str] = Cookie(None)):
    """Reject a peace proposal. Can optionally walk away (continue fighting) or send counter-offer."""
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail="Not authenticated")

    partner_id = session_data.get('partner_id')
    username = session_data.get('username')
    user_type = session_data.get('user_type')

    data = await request.json()
    walk_away = data.get('walk_away', False)  # If true, negotiations fail and war continues

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Get proposal
        cursor.execute('''
            SELECT pp.id, pp.conflict_id, pp.proposer_partner_id, pp.recipient_partner_id, pp.status,
                   c.attacker_partner_id, c.defender_partner_id,
                   a.display_name as attacker_name,
                   d.display_name as defender_name
            FROM peace_proposals pp
            JOIN conflicts c ON pp.conflict_id = c.id
            JOIN partner_accounts a ON c.attacker_partner_id = a.id
            JOIN partner_accounts d ON c.defender_partner_id = d.id
            WHERE pp.id = ?
        ''', (proposal_id,))
        proposal = cursor.fetchone()

        if not proposal:
            raise HTTPException(status_code=404, detail="Proposal not found")

        if proposal[4] != 'pending':
            raise HTTPException(status_code=400, detail="Proposal is not pending")

        if partner_id != proposal[3] and user_type != 'super_admin':
            raise HTTPException(status_code=403, detail="Only the recipient can reject this proposal")

        conflict_id = proposal[1]
        attacker_name = proposal[7]
        defender_name = proposal[8]

        # Mark proposal as rejected
        cursor.execute('''
            UPDATE peace_proposals SET status = 'rejected', responded_at = datetime('now'), response_by = ?
            WHERE id = ?
        ''', (username, proposal_id))

        if walk_away:
            # Negotiations failed - war continues
            cursor.execute('''
                UPDATE conflicts SET negotiation_status = 'failed'
                WHERE id = ?
            ''', (conflict_id,))

            # Add conflict event
            cursor.execute('''
                INSERT INTO conflict_events (conflict_id, event_type, actor_partner_id, actor_username, details)
                VALUES (?, 'negotiations_failed', ?, ?, 'Peace talks have collapsed. The war continues.')
            ''', (conflict_id, partner_id, username))

            # Auto-news: Negotiations failed
            create_auto_news(
                conn,
                'negotiations_failed',
                f"PEACE TALKS COLLAPSE: {attacker_name} vs {defender_name} War Continues",
                f"Negotiations have broken down between the warring factions. Hostilities will continue.",
                reference_id=conflict_id,
                reference_type='conflict_negotiations',
                conflict_id=conflict_id
            )

            # Notify proposer
            cursor.execute('''
                INSERT INTO war_notifications (recipient_partner_id, notification_type, title, message, related_conflict_id)
                VALUES (?, 'negotiations_failed', 'Peace Talks Failed', 'Your peace proposal was rejected. The war continues.', ?)
            ''', (proposal[2], conflict_id))
        else:
            # Just rejected - waiting for counter-offer
            cursor.execute('''
                UPDATE conflicts SET negotiation_status = 'counter_expected'
                WHERE id = ?
            ''', (conflict_id,))

            # Add conflict event
            cursor.execute('''
                INSERT INTO conflict_events (conflict_id, event_type, actor_partner_id, actor_username, details)
                VALUES (?, 'proposal_rejected', ?, ?, 'Peace proposal rejected. Counter-offer may follow.')
            ''', (conflict_id, partner_id, username))

        conn.commit()

        return {
            'status': 'rejected',
            'walk_away': walk_away,
            'war_continues': walk_away
        }
    finally:
        conn.close()


@app.get('/api/warroom/conflicts/{conflict_id}/negotiation-status')
async def get_negotiation_status(conflict_id: int, session: Optional[str] = Cookie(None)):
    """Get current negotiation status for a conflict."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            SELECT c.negotiation_status, c.attacker_counter_count, c.defender_counter_count,
                   c.negotiation_started_at, c.status,
                   a.display_name as attacker_name,
                   d.display_name as defender_name
            FROM conflicts c
            JOIN partner_accounts a ON c.attacker_partner_id = a.id
            JOIN partner_accounts d ON c.defender_partner_id = d.id
            WHERE c.id = ?
        ''', (conflict_id,))
        conflict = cursor.fetchone()

        if not conflict:
            raise HTTPException(status_code=404, detail="Conflict not found")

        # Get pending proposal if any
        cursor.execute('''
            SELECT pp.id, pp.proposer_partner_id, pp.recipient_partner_id, pp.proposal_type,
                   pp.counter_number, pp.proposed_at, pp.message,
                   prop.display_name as proposer_name
            FROM peace_proposals pp
            JOIN partner_accounts prop ON pp.proposer_partner_id = prop.id
            WHERE pp.conflict_id = ? AND pp.status = 'pending'
            ORDER BY pp.proposed_at DESC LIMIT 1
        ''', (conflict_id,))
        pending = cursor.fetchone()

        return {
            'negotiation_status': conflict[0],
            'attacker_counter_count': conflict[1],
            'defender_counter_count': conflict[2],
            'attacker_counters_remaining': 2 - conflict[1],
            'defender_counters_remaining': 2 - conflict[2],
            'negotiation_started_at': conflict[3],
            'conflict_status': conflict[4],
            'attacker_name': conflict[5],
            'defender_name': conflict[6],
            'pending_proposal': {
                'id': pending[0],
                'proposer_partner_id': pending[1],
                'recipient_partner_id': pending[2],
                'proposal_type': pending[3],
                'counter_number': pending[4],
                'proposed_at': pending[5],
                'message': pending[6],
                'proposer_name': pending[7]
            } if pending else None
        }
    finally:
        conn.close()


if __name__ == '__main__':
    import uvicorn
    import uvicorn.logging
    from datetime import datetime

    # Try to import colorama for colored output
    try:
        from colorama import init, Fore, Style
        init()
        CYAN = Fore.CYAN
        GREEN = Fore.GREEN
        YELLOW = Fore.YELLOW
        RED = Fore.RED
        WHITE = Fore.WHITE
        MAGENTA = Fore.MAGENTA
        DIM = Style.DIM
        RESET = Style.RESET_ALL
        BRIGHT = Style.BRIGHT
    except ImportError:
        # Fallback to no colors if colorama not installed
        CYAN = GREEN = YELLOW = RED = WHITE = MAGENTA = DIM = RESET = BRIGHT = ""

    class HavenLogFormatter(logging.Formatter):
        """Custom formatter for clean boxed log output."""

        LEVEL_COLORS = {
            'DEBUG': ('DEBUG', DIM),
            'INFO': ('INFO ', GREEN),
            'WARNING': ('WARN ', YELLOW),
            'ERROR': ('ERROR', RED),
            'CRITICAL': ('CRIT ', RED + BRIGHT),
        }

        def format(self, record):
            # Get level info
            level_name = record.levelname
            level_tag, level_color = self.LEVEL_COLORS.get(level_name, (level_name[:5], WHITE))

            # Format timestamp
            timestamp = datetime.now().strftime('%H:%M:%S')

            # Clean up the message
            message = record.getMessage()

            # Special formatting for access logs (HTTP requests)
            if 'uvicorn.access' in record.name:
                # Parse access log: "IP:PORT - "METHOD PATH HTTP/X.X" STATUS"
                parts = message.split('" ')
                if len(parts) >= 2:
                    # Extract IP address (before the " - " separator)
                    ip_part = parts[0].split(' - ')[0] if ' - ' in parts[0] else ''
                    # Remove port if present (IP:PORT -> IP)
                    client_ip = ip_part.split(':')[0] if ip_part else '?'

                    method_path = parts[0].split('"')[-1] if '"' in parts[0] else parts[0]
                    status = parts[1].split()[0] if parts[1] else ''

                    # Color code by status
                    if status.startswith('2'):
                        status_color = GREEN
                    elif status.startswith('3'):
                        status_color = CYAN
                    elif status.startswith('4'):
                        status_color = YELLOW
                    else:
                        status_color = RED

                    return f"    {CYAN}│{RESET} {DIM}{timestamp}{RESET} {MAGENTA}{client_ip:>15}{RESET} {status_color}{status}{RESET} {WHITE}{method_path}{RESET}"

            # Standard log message
            return f"    {CYAN}│{RESET} {DIM}{timestamp}{RESET} [{level_color}{level_tag}{RESET}] {message}"

    def print_startup_info():
        """Print professional startup information."""
        print(f"\n{CYAN}    [SYSTEM]{RESET} Database initializing...")

        # Initialize database before uvicorn starts
        init_database()
        print(f"{GREEN}    [  OK  ]{RESET} Database ready")

        # Count records
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM systems")
            system_count = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM planets")
            planet_count = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM regions WHERE custom_name IS NOT NULL")
            region_count = cursor.fetchone()[0]
            conn.close()

            print(f"\n{CYAN}    ┌──────────────────────────────────────────────────────┐{RESET}")
            print(f"{CYAN}    │{RESET}  {BRIGHT}DATABASE STATISTICS{RESET}                                {CYAN}│{RESET}")
            print(f"{CYAN}    ├──────────────────────────────────────────────────────┤{RESET}")
            print(f"{CYAN}    │{RESET}   Systems  : {YELLOW}{system_count:>6,}{RESET}                                 {CYAN}│{RESET}")
            print(f"{CYAN}    │{RESET}   Planets  : {YELLOW}{planet_count:>6,}{RESET}                                 {CYAN}│{RESET}")
            print(f"{CYAN}    │{RESET}   Regions  : {YELLOW}{region_count:>6,}{RESET}                                 {CYAN}│{RESET}")
            print(f"{CYAN}    └──────────────────────────────────────────────────────┘{RESET}")
        except Exception as e:
            print(f"{YELLOW}    [WARN]{RESET} Could not read database stats: {e}")

        print(f"\n{GREEN}    [READY]{RESET} Haven Control Room API starting...")
        print(f"\n{CYAN}    ┌──────────────────────────────────────────────────────────────────────────┐{RESET}")
        print(f"{CYAN}    │{RESET}  {BRIGHT}SERVER LOG{RESET}                                                            {CYAN}│{RESET}")
        print(f"{CYAN}    ├──────────────────────────────────────────────────────────────────────────┤{RESET}")

    def print_shutdown_box():
        """Print shutdown box."""
        print(f"{CYAN}    └──────────────────────────────────────────────────────────────────────────┘{RESET}")

    # Run startup info
    print_startup_info()

    # Configure custom logging
    log_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "haven": {
                "()": HavenLogFormatter,
            },
        },
        "handlers": {
            "default": {
                "formatter": "haven",
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stderr",
            },
            "access": {
                "formatter": "haven",
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stdout",
            },
        },
        "loggers": {
            "uvicorn": {"handlers": ["default"], "level": "INFO", "propagate": False},
            "uvicorn.error": {"level": "INFO"},
            "uvicorn.access": {"handlers": ["access"], "level": "INFO", "propagate": False},
        },
    }

    # Register shutdown handler
    import atexit
    atexit.register(print_shutdown_box)

    # Configure uvicorn with custom logging
    uvicorn.run(
        app,
        host='0.0.0.0',
        port=8005,
        log_config=log_config,
        access_log=True
    )
