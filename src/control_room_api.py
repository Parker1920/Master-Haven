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

# Add Master-Haven root to path for config imports
master_haven_root = Path(__file__).resolve().parents[1]  # Go up from src/ to Master-Haven
sys.path.insert(0, str(master_haven_root))

try:
    from config.paths import haven_paths
except ImportError:
    # Fallback if running in a different context
    haven_paths = None

# Import schema migration system
try:
    from migrations import run_pending_migrations
except ImportError:
    from src.migrations import run_pending_migrations

# Import glyph decoder
try:
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
except ImportError:
    from src.glyph_decoder import (
        decode_glyph_to_coords,
        encode_coords_to_glyph,
        validate_glyph_code,
        is_in_core_void,
        is_phantom_star,
        get_system_classification,
        format_glyph,
        galactic_coords_to_glyph,
        GLYPH_IMAGES
    )

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
    HAVEN_UI_DIR = Path(os.getenv('HAVEN_UI_DIR', Path(__file__).resolve().parents[1] / 'Haven-UI'))
    PHOTOS_DIR = HAVEN_UI_DIR / 'photos'
    LOGS_DIR = HAVEN_UI_DIR / 'logs'

DATA_JSON = HAVEN_UI_DIR / 'data' / 'data.json'

# Load galaxies reference data for validation
GALAXIES_JSON_PATH = Path(__file__).resolve().parents[1] / 'NMS-Save-Watcher' / 'data' / 'galaxies.json'

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


# Ensure directories exist
HAVEN_UI_DIR.mkdir(parents=True, exist_ok=True)
(HAVEN_UI_DIR / 'data').mkdir(parents=True, exist_ok=True)
PHOTOS_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)

# Mount static folders (so running uvicorn directly also serves the SPA)
photos_dir = HAVEN_UI_DIR / 'photos'
if photos_dir.exists():
    app.mount('/haven-ui-photos', StaticFiles(directory=str(photos_dir)), name='haven-ui-photos')

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
        stations = [dict(st) for st in stations_rows]

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
    # Initialize DB on startup so import-time failures are avoided.
    try:
        init_database()
    except Exception as e:
        # Log the error but continue — we'll still attempt to load systems
        logger.exception('Database initialization failed during startup: %s', e)
    # Load systems from DB if available, otherwise fallback to data.json
    systems = []
    try:
        db_path = get_db_path()
        if db_path.exists():
            systems = load_systems_from_db()
        else:
            data = load_data_json()
            systems = data.get('systems', [])
    except Exception:
        data = load_data_json()
        systems = data.get('systems', [])
    async with _systems_lock:
        _systems_cache.clear()
        for s in systems:
            _systems_cache[s.get('name')] = s
    logger.info('Control Room API started with %d systems', len(_systems_cache))

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


@app.get('/api/status')
async def api_status():
    return {'status': 'ok', 'version': 'minimal-api'}

@app.get('/api/stats')
async def api_stats():
    """Get system stats using efficient COUNT queries (no full data loading)."""
    conn = None
    try:
        db_path = get_db_path()
        if not db_path.exists():
            return {'total': 0, 'galaxies': []}

        conn = get_db_connection()
        cursor = conn.cursor()

        # Direct COUNT query - O(1) with index, no data loading
        cursor.execute('SELECT COUNT(*) FROM systems')
        total = cursor.fetchone()[0]

        # Get distinct galaxies - O(n) but only returns unique values
        cursor.execute('SELECT DISTINCT galaxy FROM systems WHERE galaxy IS NOT NULL ORDER BY galaxy')
        galaxies = [row[0] for row in cursor.fetchall()]

        return {'total': total, 'galaxies': galaxies}
    except Exception as e:
        logger.error(f"Stats query error: {e}")
        return {'total': 0, 'galaxies': []}
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
                GROUP_CONCAT(DISTINCT s.reality) as realities
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
        Dictionary with galaxies list, each containing index and name
    """
    return {
        'galaxies': [
            {'index': idx, 'name': name}
            for idx, name in sorted(GALAXY_BY_INDEX.items())
        ]
    }


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

    result = []
    for system in systems:
        system_id = system.get('id')
        system_tag = system.get('discord_tag')

        # Owner sees their own systems unrestricted
        if viewer_discord_tag and viewer_discord_tag == system_tag:
            result.append(system)
            continue

        # Check for restrictions
        restriction = get_restriction_for_system(system_id) if system_id else None

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

def check_rate_limit(client_ip: str, limit: int = 15, window_hours: int = 1) -> tuple:
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
                   sa.parent_partner_id, pa.discord_tag as parent_discord_tag,
                   pa.display_name as parent_display_name, pa.is_active as parent_is_active
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
    else:
        raise HTTPException(status_code=400, detail='Unknown user type')


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
                'parent_display_name': row['parent_display_name']
            })

        return {'sub_admins': sub_admins}
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
        cursor.execute('''
            INSERT INTO sub_admin_accounts
            (parent_partner_id, username, password_hash, display_name, enabled_features, created_by)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            parent_partner_id,
            username,
            hash_password(password),
            display_name,
            json.dumps(enabled_features),
            current_username
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

        # Get sub-admin
        cursor.execute('''
            SELECT sa.*, pa.enabled_features as parent_features
            FROM sub_admin_accounts sa
            JOIN partner_accounts pa ON sa.parent_partner_id = pa.id
            WHERE sa.id = ?
        ''', (sub_admin_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail='Sub-admin not found')

        # Permission check: super admin or parent partner can edit
        if not is_super:
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
            # Validate features against parent
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

        # Permission check
        if not is_super:
            if session_data.get('partner_id') != row['parent_partner_id']:
                raise HTTPException(status_code=403, detail='Can only reset passwords for your own sub-admins')

        cursor.execute(
            'UPDATE sub_admin_accounts SET password_hash = ?, updated_at = ? WHERE id = ?',
            (hash_password(new_password), datetime.now(timezone.utc).isoformat(), sub_admin_id)
        )
        conn.commit()

        return {'status': 'ok'}
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

        # Permission check
        if not is_super:
            if session_data.get('partner_id') != row['parent_partner_id']:
                raise HTTPException(status_code=403, detail='Can only deactivate your own sub-admins')

        cursor.execute(
            'UPDATE sub_admin_accounts SET is_active = 0, updated_at = ? WHERE id = ?',
            (datetime.now(timezone.utc).isoformat(), sub_admin_id)
        )
        conn.commit()

        return {'status': 'ok'}
    finally:
        if conn:
            conn.close()


@app.get('/api/approval_audit')
async def get_approval_audit(
    limit: int = 100,
    offset: int = 0,
    discord_tag: Optional[str] = None,
    approver: Optional[str] = None,
    session: Optional[str] = Cookie(None)
):
    """
    Get approval audit history (super admin only).
    Returns all approval/rejection actions with full details.
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
            query += ' AND approver_username = ?'
            params.append(approver)

        query += ' ORDER BY timestamp DESC LIMIT ? OFFSET ?'
        params.extend([limit, offset])

        cursor.execute(query, params)
        rows = cursor.fetchall()

        audit_entries = [dict(row) for row in rows]

        # Get total count for pagination
        count_query = 'SELECT COUNT(*) FROM approval_audit_log WHERE 1=1'
        count_params = []
        if discord_tag:
            count_query += ' AND submission_discord_tag = ?'
            count_params.append(discord_tag)
        if approver:
            count_query += ' AND approver_username = ?'
            count_params.append(approver)

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
        # Start with Haven as the primary tag (super admin's community)
        tags = [{'tag': 'Haven', 'name': 'Haven'}]
        # Add partner tags
        tags.extend([{'tag': row['discord_tag'], 'name': row['display_name'] or row['username']} for row in cursor.fetchall()])
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


@app.get('/api/systems')
async def api_systems():
    # If DB is available, return current systems by querying DB; otherwise return JSON cache
    try:
        db_path = get_db_path()
        if db_path.exists():
            systems = load_systems_from_db()
            return {'systems': systems}
    except Exception:
        pass
    async with _systems_lock:
        systems = list(_systems_cache.values())
    return {'systems': systems}


# NOTE: This route MUST be defined BEFORE /api/systems/{system_id} to avoid route shadowing
@app.get('/api/systems/search')
async def api_search(q: str = '', limit: int = 20, session: Optional[str] = Cookie(None)):
    """Search systems by name, glyph code, galaxy, or description.

    Uses efficient SQL LIKE queries and returns results with region info.
    Applies data restrictions based on viewer permissions.

    Args:
        q: Search query (matches system name, glyph_code, galaxy, description)
        limit: Max results to return (default 20, max 50)
        session: Session cookie for permission checking

    Returns:
        {
            "results": [
                {
                    "id": "system-uuid",
                    "name": "System Name",
                    "region_x": 2, "region_y": 45, "region_z": -12,
                    "region_name": "Widjir",
                    "galaxy": "Euclid",
                    "glyph_code": "1234...",
                    "planet_count": 4,
                    "discord_tag": "Haven"
                }
            ],
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

        # Efficient SQL search across multiple fields
        # Fetch more than limit to account for filtering by data restrictions
        cursor.execute('''
            SELECT s.id, s.name, s.region_x, s.region_y, s.region_z,
                   s.galaxy, s.glyph_code, s.discord_tag, s.star_type,
                   r.custom_name as region_name,
                   (SELECT COUNT(*) FROM planets WHERE system_id = s.id) as planet_count
            FROM systems s
            LEFT JOIN regions r ON s.region_x = r.region_x
                AND s.region_y = r.region_y AND s.region_z = r.region_z
            WHERE s.name LIKE ? COLLATE NOCASE
               OR s.glyph_code LIKE ? COLLATE NOCASE
               OR s.galaxy LIKE ? COLLATE NOCASE
               OR s.description LIKE ? COLLATE NOCASE
            ORDER BY
                CASE WHEN LOWER(s.name) = LOWER(?) THEN 0
                     WHEN LOWER(s.name) LIKE LOWER(?) THEN 1
                     ELSE 2
                END,
                s.name ASC
            LIMIT ?
        ''', (search_pattern, search_pattern, search_pattern, search_pattern,
              q, f'{q}%', limit * 2))

        rows = cursor.fetchall()
        systems = [dict(row) for row in rows]

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
                               session: Optional[str] = Cookie(None)):
    """Return all regions with their systems grouped together.

    Performance-optimized version:
    - Uses JOINs instead of N+1 queries
    - Optional pagination with page/limit params
    - include_systems=false returns just region summaries (much faster)
    - Applies data restrictions based on viewer permissions

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

        # STEP 1: Get all regions with aggregated counts in a SINGLE query
        # This replaces the N+1 pattern with one efficient GROUP BY query
        cursor.execute('''
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
        ''')

        region_rows = cursor.fetchall()
        total_regions = len(region_rows)

        # Apply pagination if requested
        if limit > 0:
            offset = page * limit
            region_rows = region_rows[offset:offset + limit]

        regions = []

        if not include_systems:
            # Fast path: return just region summaries without nested data
            # BUT we need accurate counts, so fetch minimal system data for restriction checks
            region_coords = [(r['region_x'], r['region_y'], r['region_z']) for r in region_rows]

            if region_coords:
                # Build WHERE clause for all regions
                placeholders = ' OR '.join(['(region_x = ? AND region_y = ? AND region_z = ?)'] * len(region_coords))
                params = [coord for region in region_coords for coord in region]

                cursor.execute(f'''
                    SELECT id, discord_tag, region_x, region_y, region_z FROM systems
                    WHERE {placeholders}
                ''', params)

                all_systems = [dict(row) for row in cursor.fetchall()]

                # Apply data restrictions to get accurate visible systems
                visible_systems = apply_data_restrictions(all_systems, session_data)

                # Count visible systems per region
                visible_counts = {}
                for system in visible_systems:
                    key = (system['region_x'], system['region_y'], system['region_z'])
                    visible_counts[key] = visible_counts.get(key, 0) + 1

            for region_row in region_rows:
                region = dict(region_row)
                rx, ry, rz = region['region_x'], region['region_y'], region['region_z']

                if region['custom_name']:
                    region['display_name'] = region['custom_name']
                else:
                    region['display_name'] = f"Region ({rx}, {ry}, {rz})"

                # Use accurate visible count
                region['system_count'] = visible_counts.get((rx, ry, rz), 0) if region_coords else 0
                region['systems'] = []  # Empty for now, lazy-load via separate endpoint
                regions.append(region)

            # Filter out regions with no visible systems
            regions = [r for r in regions if r['system_count'] > 0]

            return {'regions': regions, 'total_regions': len(regions)}

        # STEP 2: Load all systems for all regions in ONE query
        region_coords = [(r['region_x'], r['region_y'], r['region_z']) for r in region_rows]
        if not region_coords:
            return {'regions': [], 'total_regions': 0}

        # Build WHERE clause for all regions
        placeholders = ' OR '.join(['(region_x = ? AND region_y = ? AND region_z = ?)'] * len(region_coords))
        params = [coord for region in region_coords for coord in region]

        cursor.execute(f'''
            SELECT * FROM systems
            WHERE {placeholders}
            ORDER BY region_x, region_y, region_z, created_at ASC NULLS FIRST, id ASC
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
        for region_row in region_rows:
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

        return {'regions': regions, 'total_regions': total_regions}

    except Exception as e:
        logger.error(f"Error fetching grouped regions: {e}")
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
            (region_x, region_y, region_z, proposed_name, submitted_by, submitted_by_ip, submission_date, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'pending')
        ''', (rx, ry, rz, proposed_name, submitted_by, client_ip, datetime.now(timezone.utc).isoformat()))

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
async def api_list_pending_region_names():
    """List all pending region name submissions. Public endpoint."""
    conn = None
    try:
        db_path = get_db_path()
        if not db_path.exists():
            return {'pending': []}

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT * FROM pending_region_names
            WHERE status = 'pending'
            ORDER BY submission_date DESC
        ''')

        rows = cursor.fetchall()
        pending = [dict(row) for row in rows]

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
            if station_row:
                system['space_station'] = dict(station_row)
            else:
                system['space_station'] = None

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

        if existing:
            sys_id = existing['id']
            # Update existing system (including name for renames and new NMS fields)
            cursor.execute('''
                UPDATE systems SET
                    name = ?, galaxy = ?, reality = ?, x = ?, y = ?, z = ?,
                    star_x = ?, star_y = ?, star_z = ?,
                    description = ?,
                    glyph_code = ?, glyph_planet = ?, glyph_solar_system = ?,
                    region_x = ?, region_y = ?, region_z = ?,
                    star_type = ?, economy_type = ?, economy_level = ?,
                    conflict_level = ?, dominant_lifeform = ?, discord_tag = ?
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
                sys_id
            ))
            # Delete existing planets (will cascade to moons)
            cursor.execute('DELETE FROM planets WHERE system_id = ?', (sys_id,))
            # Delete existing space station
            cursor.execute('DELETE FROM space_stations WHERE system_id = ?', (sys_id,))
        else:
            # Generate new ID
            import uuid
            sys_id = str(uuid.uuid4())
            # Insert new system (including new NMS fields and discord_tag)
            cursor.execute('''
                INSERT INTO systems (id, name, galaxy, reality, x, y, z, star_x, star_y, star_z, description,
                    glyph_code, glyph_planet, glyph_solar_system, region_x, region_y, region_z,
                    star_type, economy_type, economy_level, conflict_level, dominant_lifeform, discord_tag)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                payload.get('discord_tag')
            ))

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
                    weather_text, sentinels_text, flora_text, fauna_text
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                planet.get('fauna_text')
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
            cursor.execute('''
                INSERT INTO space_stations (system_id, name, race, x, y, z, sell_percent, buy_percent)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                sys_id,
                station.get('name', f"{name} Station"),
                station.get('race', 'Gek'),
                station.get('x', 0),
                station.get('y', 0),
                station.get('z', 0),
                station.get('sell_percent', 80),
                station.get('buy_percent', 50)
            ))

        conn.commit()
        logger.info(f"Saved system '{name}' to database (ID: {sys_id})")

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
async def db_stats():
    """Get database statistics"""
    conn = None
    try:
        db_path = HAVEN_UI_DIR / 'data' / 'haven_ui.db'
        if not db_path.exists():
            return {'stats': {}, 'note': 'Database not found'}

        conn = get_db_connection()
        cursor = conn.cursor()

        stats = {}
        # Get table counts
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]

        for table in tables:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                count = cursor.fetchone()[0]
                stats[table] = count
            except:
                pass

        return {'stats': stats}
    except Exception as e:
        logger.error(f'Error getting db_stats: {e}')
        return {'stats': {}, 'error': str(e)}
    finally:
        if conn:
            conn.close()

@app.get('/api/partner/stats')
async def partner_stats(session: Optional[str] = Cookie(None)):
    """Get stats filtered for the current partner's discord_tag"""
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail='Authentication required')

    is_super = session_data.get('user_type') == 'super_admin'
    partner_tag = session_data.get('discord_tag')

    # Super admin gets all stats
    if is_super:
        return await db_stats()

    # Partners without a tag get empty stats
    if not partner_tag:
        return {'stats': {'systems': 0, 'planets': 0, 'moons': 0, 'regions': 0, 'space_stations': 0}}

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        stats = {}

        # Count systems with partner's tag
        cursor.execute('SELECT COUNT(*) FROM systems WHERE discord_tag = ?', (partner_tag,))
        stats['systems'] = cursor.fetchone()[0]

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

        return {'stats': stats, 'discord_tag': partner_tag}
    except Exception as e:
        logger.error(f'Error getting partner stats: {e}')
        return {'stats': {}, 'error': str(e)}
    finally:
        if conn:
            conn.close()

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
                        space_stations = [dict(row) for row in stations_rows]
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
        if station_row:
            system['space_station'] = dict(station_row)
        else:
            system['space_station'] = None

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

@app.get('/api/discoveries/{discovery_id}')
async def get_discovery(discovery_id: int):
    """Get a specific discovery by ID"""
    conn = None
    try:
        db_path = get_db_path()
        if db_path.exists():
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM discoveries WHERE id = ?', (discovery_id,))
            row = cursor.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail='Discovery not found')
            return dict(row)

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

        cursor.execute('''
            INSERT INTO discoveries (
                discovery_type, discovery_name, system_id, planet_id, moon_id, location_type, location_name, description, significance, discovered_by, submission_timestamp, mystery_tier, analysis_status, pattern_matches, discord_user_id, discord_guild_id, photo_url, evidence_url
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            payload.get('discovery_type') or 'Unknown',
            discovery_name,
            system_id,
            payload.get('planet_id'),
            payload.get('moon_id'),
            payload.get('location_type') or 'space',
            location_name,
            payload.get('description') or '',
            payload.get('significance') or 'Notable',
            payload.get('discovered_by') or 'anonymous',
            submission_ts,
            payload.get('mystery_tier') or 1,
            payload.get('analysis_status') or 'pending',
            payload.get('pattern_matches') or 0,
            payload.get('discord_user_id'),
            payload.get('discord_guild_id'),
            payload.get('photo_url'),
            payload.get('evidence_urls'),
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
                detail="Rate limit exceeded. Maximum 15 submissions per hour. Please try again later.",
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

        # Check if a system with this glyph_code already exists (will be treated as edit on approval)
        glyph_code = payload.get('glyph_code')
        existing_glyph_system = None
        if glyph_code:
            cursor.execute('SELECT id, name FROM systems WHERE glyph_code = ?', (glyph_code,))
            existing_glyph_row = cursor.fetchone()
            if existing_glyph_row:
                existing_glyph_system = {'id': existing_glyph_row[0], 'name': existing_glyph_row[1]}
                warnings.append(
                    f"EXISTING SYSTEM: A system with this glyph code already exists: '{existing_glyph_row[1]}'. "
                    f"Approving this submission will UPDATE the existing system."
                )
                logger.info(f"Submission for '{system_name}' has glyph_code matching existing system '{existing_glyph_row[1]}' (ID: {existing_glyph_row[0]})")

        # Extract discord_tag for filtering (partners only see their tagged submissions)
        # If submitted via API key, use the API key's discord_tag (auto-tagging)
        discord_tag = payload.get('discord_tag')
        if api_key_info and api_key_info.get('discord_tag') and not discord_tag:
            discord_tag = api_key_info['discord_tag']
            logger.info(f"Auto-tagging submission with API key's discord_tag: {discord_tag}")
        # Extract personal discord username for non-community submissions
        personal_discord_username = payload.get('personal_discord_username')

        # Determine if this is an edit (system has ID) or new submission
        # Also check if glyph_code matches an existing system
        edit_system_id = system_id  # From payload.get('id') above
        if not edit_system_id and existing_glyph_system:
            # Glyph code matches existing system - treat as edit
            edit_system_id = existing_glyph_system['id']

        # Get submitter identity for self-approval detection
        submitter_identity = get_submitter_identity(session)

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
    - Partners: see only submissions tagged with their discord_tag
    """
    # Verify admin session and get session data
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail="Admin authentication required")

    is_super = session_data.get('user_type') == 'super_admin'
    partner_tag = session_data.get('discord_tag')

    conn = None
    try:
        db_path = get_db_path()
        conn = get_db_connection()
        cursor = conn.cursor()

        if is_super:
            # Super admin sees ALL submissions with discord_tag visible
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
        else:
            # Partners and sub-admins only see submissions tagged with their discord_tag
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
    - Super admin / not logged in: sees count of ALL pending
    - Partners: sees count of only their discord_tag submissions
    Must be defined BEFORE /api/pending_systems/{submission_id} to avoid route conflict.
    """
    # Get session data if available (for partner filtering)
    session_data = get_session(session) if session else None
    is_super = session_data and session_data.get('user_type') == 'super_admin'
    partner_tag = session_data.get('discord_tag') if session_data else None

    conn = None
    try:
        db_path = get_db_path()
        conn = get_db_connection()
        cursor = conn.cursor()

        # Count pending systems (filtered for partners)
        if session_data and not is_super and partner_tag:
            # Partner only sees their tagged submissions
            cursor.execute("SELECT COUNT(*) FROM pending_systems WHERE status = 'pending' AND discord_tag = ?", (partner_tag,))
        else:
            # Super admin or not logged in sees all
            cursor.execute("SELECT COUNT(*) FROM pending_systems WHERE status = 'pending'")
        system_count = cursor.fetchone()[0]

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

            is_self_submission = False

            # Match by account ID if available (most reliable)
            if submitter_account_id is not None and submitter_account_type:
                if current_user_type == submitter_account_type and current_account_id == submitter_account_id:
                    is_self_submission = True
            # Fallback: match by username (for legacy submissions without account tracking)
            elif submitted_by and current_username and submitted_by.lower() == current_username.lower():
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

        logger.info(f"Approving submission {submission_id}: system_data.id = {existing_system_id}")

        if existing_system_id:
            # Check if the system actually exists in the database
            cursor.execute('SELECT id FROM systems WHERE id = ?', (existing_system_id,))
            existing_row = cursor.fetchone()
            if existing_row:
                is_edit = True
                system_id = existing_system_id
                logger.info(f"Submission {submission_id} is an EDIT - found existing system with ID: {system_id}")
            else:
                logger.info(f"Submission {submission_id} has ID {existing_system_id} but system not found in DB - treating as NEW")

        # If not already an edit, check if a system with this glyph_code already exists
        # This handles the case where someone submits via text input a glyph that's already in the DB
        if not is_edit and system_data.get('glyph_code'):
            cursor.execute('SELECT id, name FROM systems WHERE glyph_code = ?', (system_data['glyph_code'],))
            existing_glyph_row = cursor.fetchone()
            if existing_glyph_row:
                is_edit = True
                system_id = existing_glyph_row[0]
                existing_name = existing_glyph_row[1]
                logger.info(f"Submission {submission_id} has glyph_code that matches existing system '{existing_name}' (ID: {system_id}) - treating as EDIT")

        if is_edit:
            # UPDATE existing system (including new companion app fields)
            cursor.execute('''
                UPDATE systems
                SET name = ?, galaxy = ?, x = ?, y = ?, z = ?,
                    star_x = ?, star_y = ?, star_z = ?,
                    description = ?,
                    glyph_code = ?, glyph_planet = ?, glyph_solar_system = ?,
                    region_x = ?, region_y = ?, region_z = ?,
                    star_type = ?, economy_type = ?, economy_level = ?,
                    conflict_level = ?, dominant_lifeform = ?,
                    discovered_by = ?, discovered_at = ?,
                    discord_tag = ?, personal_discord_username = ?
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
                system_data.get('discovered_by'),
                system_data.get('discovered_at'),
                submission.get('discord_tag'),
                submission.get('personal_discord_username'),
                system_id
            ))

            # Delete existing planets, moons, and space station for this system (will re-insert)
            cursor.execute('SELECT id FROM planets WHERE system_id = ?', (system_id,))
            planet_ids = [row[0] for row in cursor.fetchall()]
            for pid in planet_ids:
                cursor.execute('DELETE FROM moons WHERE planet_id = ?', (pid,))
            cursor.execute('DELETE FROM planets WHERE system_id = ?', (system_id,))
            cursor.execute('DELETE FROM space_stations WHERE system_id = ?', (system_id,))
        else:
            # Generate UUID for new system
            import uuid
            system_id = str(uuid.uuid4())

            # INSERT new system (including new companion app fields and discord_tag)
            cursor.execute('''
                INSERT INTO systems (id, name, galaxy, reality, x, y, z, star_x, star_y, star_z, description,
                    glyph_code, glyph_planet, glyph_solar_system, region_x, region_y, region_z,
                    star_type, economy_type, economy_level, conflict_level, dominant_lifeform,
                    discovered_by, discovered_at, discord_tag, personal_discord_username)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                system_data.get('discovered_by'),
                system_data.get('discovered_at'),
                submission.get('discord_tag'),
                submission.get('personal_discord_username')
            ))

        # Insert planets (including all Haven Extractor v7.9.6+ fields)
        for planet in system_data.get('planets', []):
            # Handle sentinel_level -> sentinel field mapping (companion app sends sentinel_level)
            sentinel_val = planet.get('sentinel') or planet.get('sentinel_level', 'None')
            # Handle fauna_level/flora_level -> fauna/flora mapping
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
                    weather_text, sentinels_text, flora_text, fauna_text
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                # New Haven Extractor fields
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
                planet.get('fauna_text')
            ))
            planet_id = cursor.lastrowid

            # Insert moons
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
            # Use 'or 0' pattern to handle both missing keys AND null values
            # This fixes cases where coordinates exist but are null (e.g., user cleared input fields)
            cursor.execute('''
                INSERT INTO space_stations (system_id, name, race, x, y, z, sell_percent, buy_percent)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                system_id,
                station.get('name') or f"{system_data.get('name')} Station",
                station.get('race') or 'Gek',
                station.get('x') or 0,
                station.get('y') or 0,
                station.get('z') or 0,
                station.get('sell_percent') or 80,
                station.get('buy_percent') or 50
            ))

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
            submission.get('submitted_by'),
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

            is_self_submission = False

            if submitter_account_id is not None and submitter_account_type:
                if current_user_type == submitter_account_type and current_account_id == submitter_account_id:
                    is_self_submission = True
            elif submitted_by and current_username and submitted_by.lower() == current_username.lower():
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
            submission.get('submitted_by'),
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

                    is_self_submission = False
                    if submitter_account_id is not None and submitter_account_type:
                        if current_user_type == submitter_account_type and current_account_id == submitter_account_id:
                            is_self_submission = True
                    elif submitted_by and current_username and submitted_by.lower() == current_username.lower():
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

                if existing_system_id:
                    cursor.execute('SELECT id FROM systems WHERE id = ?', (existing_system_id,))
                    existing_row = cursor.fetchone()
                    if existing_row:
                        is_edit = True
                        system_id = existing_system_id

                if not is_edit and system_data.get('glyph_code'):
                    cursor.execute('SELECT id FROM systems WHERE glyph_code = ?', (system_data['glyph_code'],))
                    existing_glyph_row = cursor.fetchone()
                    if existing_glyph_row:
                        is_edit = True
                        system_id = existing_glyph_row[0]

                if is_edit:
                    cursor.execute('''
                        UPDATE systems
                        SET name = ?, galaxy = ?, x = ?, y = ?, z = ?,
                            star_x = ?, star_y = ?, star_z = ?,
                            description = ?,
                            glyph_code = ?, glyph_planet = ?, glyph_solar_system = ?,
                            region_x = ?, region_y = ?, region_z = ?,
                            star_type = ?, economy_type = ?, economy_level = ?,
                            conflict_level = ?, dominant_lifeform = ?,
                            discovered_by = ?, discovered_at = ?,
                            discord_tag = ?, personal_discord_username = ?
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
                        system_data.get('discovered_by'),
                        system_data.get('discovered_at'),
                        submission.get('discord_tag'),
                        submission.get('personal_discord_username'),
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

                    cursor.execute('''
                        INSERT INTO systems (id, name, galaxy, reality, x, y, z, star_x, star_y, star_z, description,
                            glyph_code, glyph_planet, glyph_solar_system, region_x, region_y, region_z,
                            star_type, economy_type, economy_level, conflict_level, dominant_lifeform,
                            discovered_by, discovered_at, discord_tag, personal_discord_username)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                        system_data.get('discovered_by'),
                        system_data.get('discovered_at'),
                        submission.get('discord_tag'),
                        submission.get('personal_discord_username')
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
                            weather_text, sentinels_text, flora_text, fauna_text
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                        planet.get('fauna_text')
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
                    cursor.execute('''
                        INSERT INTO space_stations (system_id, name, race, x, y, z, sell_percent, buy_percent)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        system_id,
                        station.get('name') or f"{system_data.get('name')} Station",
                        station.get('race') or 'Gek',
                        station.get('x') or 0,
                        station.get('y') or 0,
                        station.get('z') or 0,
                        station.get('sell_percent') or 80,
                        station.get('buy_percent') or 50
                    ))

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
                    submission.get('submitted_by'),
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

                    is_self_submission = False
                    if submitter_account_id is not None and submitter_account_type:
                        if current_user_type == submitter_account_type and current_account_id == submitter_account_id:
                            is_self_submission = True
                    elif submitted_by and current_username and submitted_by.lower() == current_username.lower():
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
                    submission.get('submitted_by'),
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
# HAVEN EXTRACTOR API ENDPOINT
# =============================================================================

@app.post('/api/extraction')
async def receive_extraction(
    payload: dict,
    request: Request,
    x_api_key: Optional[str] = Header(None, alias='X-API-Key')
):
    """
    Receive extraction data from Haven Extractor (running in-game via pymhf).
    This endpoint accepts the JSON extraction format and converts it to a system submission.

    Expected payload format (from Haven Extractor):
    {
        "extraction_time": "2024-01-15T12:00:00",
        "extractor_version": "7.6.0",
        "glyph_code": "0123456789AB",
        "galaxy_name": "Euclid",
        "galaxy_index": 0,
        "voxel_x": 100,
        "voxel_y": 50,
        "voxel_z": -200,
        "solar_system_index": 123,
        "star_type": "Yellow",
        "economy_type": "Trading",
        "economy_strength": "Wealthy",
        "conflict_level": "Low",
        "dominant_lifeform": "Gek",
        "planets": [
            {
                "planet_index": 0,
                "planet_name": "Planet Name",
                "biome": "Lush",
                "weather": "Pleasant",
                "sentinel_level": "Low",
                "flora_level": "High",
                "fauna_level": "Medium",
                "is_moon": false,
                ...
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

    # Convert extraction format to submission format
    submission_data = {
        'name': payload.get('system_name', f"System_{glyph_code}"),
        'glyph_code': glyph_code,
        'galaxy': payload.get('galaxy_name', 'Euclid'),
        'x': payload.get('voxel_x', 0),
        'y': payload.get('voxel_y', 0),
        'z': payload.get('voxel_z', 0),
        'glyph_solar_system': payload.get('solar_system_index', 1),
        'star_type': payload.get('star_type', 'Yellow'),
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
            'sentinels': planet_data.get('sentinel_level', 'Unknown'),
            'flora': planet_data.get('flora_level', 'Unknown'),
            'fauna': planet_data.get('fauna_level', 'Unknown'),
            'resources': [
                r for r in [
                    planet_data.get('common_resource'),
                    planet_data.get('uncommon_resource'),
                    planet_data.get('rare_resource')
                ] if r and r != 'Unknown'
            ],
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

        # Check for duplicate submission by glyph code
        cursor.execute('''
            SELECT id, status FROM pending_systems
            WHERE glyph_code = ? AND status = 'pending'
        ''', (glyph_code,))
        existing = cursor.fetchone()

        if existing:
            # Update existing pending submission
            cursor.execute('''
                UPDATE pending_systems
                SET raw_json = ?, submission_timestamp = ?
                WHERE id = ?
            ''', (json.dumps(submission_data), datetime.now(timezone.utc).isoformat(), existing[0]))
            conn.commit()

            logger.info(f"Updated pending extraction for {glyph_code}")
            return JSONResponse({
                'status': 'updated',
                'message': f'Extraction updated for {glyph_code}',
                'submission_id': existing[0],
                'planet_count': len(planets),
                'moon_count': len(moons)
            })

        # Insert new pending submission
        now = datetime.now(timezone.utc).isoformat()
        raw_json_str = json.dumps(submission_data)
        cursor.execute('''
            INSERT INTO pending_systems (
                system_name, glyph_code, galaxy, x, y, z,
                submitter_name, submission_timestamp, submission_date, status, source, raw_json, system_data
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            submission_data['name'],
            glyph_code,
            submission_data['galaxy'],
            submission_data['x'],
            submission_data['y'],
            submission_data['z'],
            submission_data['discovered_by'],
            now,
            now,  # submission_date
            'pending',
            'haven_extractor',
            raw_json_str,
            raw_json_str  # system_data (same as raw_json)
        ))
        conn.commit()
        submission_id = cursor.lastrowid

        logger.info(f"Received extraction from Haven Extractor: {glyph_code} with {len(planets)} planets, {len(moons)} moons")

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


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=8005)
