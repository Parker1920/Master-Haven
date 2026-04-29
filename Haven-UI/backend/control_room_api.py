from fastapi import FastAPI, UploadFile, File, Form, WebSocket, WebSocketDisconnect, HTTPException, Request, Response, Cookie
from fastapi.responses import JSONResponse, FileResponse, HTMLResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Dict, Optional
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
import time
import csv
import io
from fastapi.staticfiles import StaticFiles
import mimetypes

# Register WebP MIME type - not in all systems' MIME databases (e.g. Raspberry Pi OS)
# Without this, StaticFiles serves .webp as text/plain, showing raw binary in browser
mimetypes.add_type('image/webp', '.webp')

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

# Import image processor for upload compression
from image_processor import process_image

# ============================================================================
# Shared Module Imports
# These modules are the single source of truth for their respective concerns.
# ============================================================================

from constants import (
    DEFAULT_PAGE_LIMIT, MAX_PAGE_LIMIT, ACTIVITY_LOG_MAX,
    SESSION_TIMEOUT_MINUTES, GRADE_THRESHOLDS, score_to_grade,
    NO_LIFE_BIOMES,
    TIER_SUPER_ADMIN, TIER_PARTNER, TIER_SUB_ADMIN, TIER_MEMBER, TIER_MEMBER_READONLY,
    TIER_TO_USER_TYPE,
    DISCOVERY_EMOJI_TO_SLUG, DISCOVERY_SLUG_TO_EMOJI, DISCOVERY_TYPE_SLUGS,
    DISCOVERY_TYPE_INFO, DISCOVERY_TYPE_FIELDS,
    RESTRICTABLE_FIELDS,
    GALAXIES_DATA, GALAXY_NAMES, GALAXY_BY_INDEX, GALAXY_BY_NAME,
    validate_galaxy, validate_reality,
    get_discovery_type_slug, normalize_discord_username,
)

from db import (
    get_db_path, get_db_connection, get_db, _row_to_dict,
    parse_station_data, add_activity_log,
    get_system_glyph, find_matching_system, find_matching_pending_system,
    build_mismatch_flags, merge_system_data,
    PHOTOS_DIR, LOGS_DIR,
)

from services.auth_service import (
    _sessions, _settings_cache,
    hash_password, verify_password, _needs_rehash,
    generate_session_token, get_session, create_session, destroy_session,
    verify_session, require_feature,
    is_super_admin, is_partner, is_sub_admin,
    get_partner_discord_tag, can_access_feature, get_effective_discord_tag,
    get_submitter_identity, check_self_submission,
    get_super_admin_password_hash, set_super_admin_password_hash,
    get_personal_color, set_personal_color,
    hash_api_key, generate_api_key, verify_api_key,
    normalize_username_for_dedup, _levenshtein_distance,
    find_fuzzy_profile_matches, get_or_create_profile,
)

from services.completeness import (
    _is_filled, _life_descriptor_filled,
    calculate_completeness_score, update_completeness_score,
)

from services.restrictions import (
    get_restriction_for_system, get_restrictions_batch,
    get_restrictions_by_discord_tag, can_bypass_restriction,
    apply_field_restrictions, apply_data_restrictions,
)

app = FastAPI()
logger = logging.getLogger('control.room')

# CORS - restrict to known origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://havenmap.online",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://10.0.0.229:8005",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-API-Key", "Cookie"],
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

# ============================================================================
# Discovery Constants
# Emoji-to-slug mapping, type metadata, and per-type submission fields.
# Used by discovery browsing, submission, and approval endpoints.
# ============================================================================

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

# Discovery type display info (emoji and label only; colors live in the frontend's
# src/data/discoveryTypes.js to avoid drift between backend and frontend copies)
DISCOVERY_TYPE_INFO = {
    'fauna': {'emoji': '🦗', 'label': 'Fauna'},
    'flora': {'emoji': '🌿', 'label': 'Flora'},
    'mineral': {'emoji': '💎', 'label': 'Mineral'},
    'ancient': {'emoji': '🏛️', 'label': 'Ancient'},
    'history': {'emoji': '📜', 'label': 'History'},
    'bones': {'emoji': '🦴', 'label': 'Bones'},
    'alien': {'emoji': '👽', 'label': 'Alien'},
    'starship': {'emoji': '🚀', 'label': 'Starship'},
    'multitool': {'emoji': '⚙️', 'label': 'Multi-tool'},
    'lore': {'emoji': '📖', 'label': 'Lore'},
    'base': {'emoji': '🏠', 'label': 'Custom Base'},
    'other': {'emoji': '🆕', 'label': 'Other'},
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


# ============================================================================
# Galaxy Reference Data
# All 256 NMS galaxy names loaded from bundled JSON. Provides lookup dicts
# by index and by name, plus validation helpers.
# ============================================================================

# Bundled with the backend so it deploys to production (Pi) without NMS-Save-Watcher
GALAXIES_JSON_PATH = Path(__file__).resolve().parent / 'data' / 'galaxies.json'

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


# ============================================================================
# Unified User Profile System - Tier Constants & Helpers
# ============================================================================

TIER_SUPER_ADMIN = 1
TIER_PARTNER = 2
TIER_SUB_ADMIN = 3
TIER_MEMBER = 4
TIER_MEMBER_READONLY = 5

TIER_TO_USER_TYPE = {
    TIER_SUPER_ADMIN: 'super_admin',
    TIER_PARTNER: 'partner',
    TIER_SUB_ADMIN: 'sub_admin',
    TIER_MEMBER: 'member',
    TIER_MEMBER_READONLY: 'member_readonly',
}


def normalize_username_for_dedup(username: str) -> str:
    """
    Authoritative normalization for user_profiles.username_normalized.
    Strips unicode accents, lowercases, removes spaces/underscores/dashes/#,
    strips trailing 4-digit Discord discriminator.
    """
    import unicodedata
    if not username:
        return ''
    # Strip unicode accents (e.g., û -> u)
    normalized = unicodedata.normalize('NFKD', username)
    normalized = ''.join(ch for ch in normalized if not unicodedata.combining(ch))
    normalized = normalized.strip().lower()
    normalized = normalized.replace('#', '').replace(' ', '').replace('_', '').replace('-', '')
    # Strip trailing 4-digit Discord discriminator
    if len(normalized) > 4 and normalized[-4:].isdigit():
        prefix = normalized[:-4]
        if prefix and not prefix[-1].isdigit():
            normalized = prefix
    return normalized


def _levenshtein_distance(s1: str, s2: str) -> int:
    """Classic dynamic programming Levenshtein distance."""
    if len(s1) < len(s2):
        return _levenshtein_distance(s2, s1)
    if len(s2) == 0:
        return len(s1)
    prev_row = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        curr_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = prev_row[j + 1] + 1
            deletions = curr_row[j] + 1
            substitutions = prev_row[j] + (c1 != c2)
            curr_row.append(min(insertions, deletions, substitutions))
        prev_row = curr_row
    return prev_row[-1]


def find_fuzzy_profile_matches(conn, username: str, max_distance: int = 2) -> list:
    """
    Find profiles within Levenshtein edit distance of the given username.
    Returns list of {id, username, display_name, default_civ_tag, distance}.
    Excludes exact matches (distance 0) — those are handled by exact lookup.
    """
    normalized = normalize_username_for_dedup(username)
    if not normalized:
        return []
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, username, display_name, default_civ_tag, username_normalized
        FROM user_profiles WHERE is_active = 1
    """)
    matches = []
    for row in cursor.fetchall():
        dist = _levenshtein_distance(normalized, row['username_normalized'])
        if 0 < dist <= max_distance:
            matches.append({
                'id': row['id'],
                'username': row['username'],
                'display_name': row['display_name'],
                'default_civ_tag': row['default_civ_tag'],
                'distance': dist
            })
    return sorted(matches, key=lambda m: m['distance'])[:5]


def get_or_create_profile(conn, username: str, discord_snowflake_id: str = None,
                          default_civ_tag: str = None, created_by: str = 'auto') -> int:
    """
    Look up a profile by normalized username. If not found, create a tier-5 profile.
    Returns the profile_id.
    """
    normalized = normalize_username_for_dedup(username)
    if not normalized:
        return None
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM user_profiles WHERE username_normalized = ?", (normalized,))
    row = cursor.fetchone()
    if row:
        return row['id']
    now = datetime.now(timezone.utc).isoformat()
    cursor.execute('''
        INSERT INTO user_profiles (
            username, username_normalized, display_name, tier,
            discord_snowflake_id, default_civ_tag, default_reality, default_galaxy,
            created_by, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, NULL, NULL, ?, ?, ?)
    ''', (username, normalized, username, TIER_MEMBER_READONLY,
          discord_snowflake_id, default_civ_tag, created_by, now, now))
    return cursor.lastrowid


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


def find_matching_pending_system(cursor, glyph_code: str, galaxy: str, reality: str):
    """
    Find a pending system that matches by glyph coordinates + galaxy + reality.
    Same logic as find_matching_system() but queries pending_systems table.
    Only returns submissions with status='pending'.
    """
    system_glyph = get_system_glyph(glyph_code)
    if not system_glyph:
        return None

    cursor.execute('''
        SELECT id, system_name, glyph_code, system_data, status
        FROM pending_systems
        WHERE SUBSTR(glyph_code, -11) = ?
          AND galaxy = ?
          AND reality = ?
          AND status = 'pending'
    ''', (system_glyph, galaxy or 'Euclid', reality or 'Normal'))

    return cursor.fetchone()


def build_mismatch_flags(existing_data: dict, new_data: dict) -> list:
    """
    Compare existing system data with new submission data and return a list
    of mismatch flags for review. Only checks fields that both sources provide.
    Coordinates match (that's how we got here) but other attributes may differ.
    """
    flags = []

    # System-level attribute checks
    system_checks = [
        ('name', 'System name'),
        ('star_type', 'Star type'),
        ('star_color', 'Star type'),  # extractor uses star_color
        ('economy_type', 'Economy type'),
        ('dominant_lifeform', 'Dominant lifeform'),
    ]
    for field, label in system_checks:
        old_val = existing_data.get(field)
        new_val = new_data.get(field)
        if old_val and new_val and str(old_val).strip().lower() != str(new_val).strip().lower():
            # For star_type/star_color, check both field names before flagging
            if field == 'star_color':
                existing_star = existing_data.get('star_type') or existing_data.get('star_color')
                new_star = new_data.get('star_type') or new_data.get('star_color')
                if existing_star and new_star and str(existing_star).strip().lower() != str(new_star).strip().lower():
                    flags.append(f"{label} differs: '{existing_star}' vs '{new_star}'")
                continue
            if field == 'star_type' and 'star_color' in [c[0] for c in system_checks]:
                continue  # Already handled by star_color check
            flags.append(f"{label} differs: '{old_val}' vs '{new_val}'")

    # Planet count check
    existing_planets = existing_data.get('planets', [])
    new_planets = new_data.get('planets', [])
    if existing_planets and new_planets and len(existing_planets) != len(new_planets):
        flags.append(f"Planet count differs: {len(existing_planets)} vs {len(new_planets)}")

    # Planet name comparison (order-independent)
    if existing_planets and new_planets:
        existing_names = {p.get('name', '').strip().lower() for p in existing_planets if p.get('name')}
        new_names = {p.get('name', '').strip().lower() for p in new_planets if p.get('name')}
        if existing_names and new_names:
            missing = existing_names - new_names
            added = new_names - existing_names
            if missing:
                flags.append(f"Planets removed: {', '.join(sorted(missing))}")
            if added:
                flags.append(f"Planets added: {', '.join(sorted(added))}")

    # Moon count check
    existing_moons = existing_data.get('moons', [])
    new_moons = new_data.get('moons', [])
    if existing_moons and new_moons and len(existing_moons) != len(new_moons):
        flags.append(f"Moon count differs: {len(existing_moons)} vs {len(new_moons)}")

    # Moon name comparison
    if existing_moons and new_moons:
        existing_moon_names = {m.get('name', '').strip().lower() for m in existing_moons if m.get('name')}
        new_moon_names = {m.get('name', '').strip().lower() for m in new_moons if m.get('name')}
        if existing_moon_names and new_moon_names:
            missing = existing_moon_names - new_moon_names
            added = new_moon_names - existing_moon_names
            if missing:
                flags.append(f"Moons removed: {', '.join(sorted(missing))}")
            if added:
                flags.append(f"Moons added: {', '.join(sorted(added))}")

    return flags


def merge_system_data(existing_data: dict, new_data: dict) -> dict:
    """
    Deep-merge new extraction data on top of existing pending submission data.
    Extractor fields win (from live game memory). Manual-only fields are preserved.

    Fields the extractor does NOT send (preserved from existing):
    - spectral_class / stellar_classification
    - space_station (entire object)
    - Planet/moon: notes, photos, base_location, description, has_rings,
      water_world, is_gas_giant, exotic_trophy, has_water
    """
    merged = dict(existing_data)

    # System-level: extractor fields overwrite
    extractor_system_fields = {
        'name', 'glyph_code', 'galaxy', 'reality', 'x', 'y', 'z',
        'region_x', 'region_y', 'region_z', 'glyph_solar_system',
        'star_color', 'economy_type', 'economy_level', 'conflict_level',
        'dominant_lifeform', 'discovered_by', 'discovered_at', 'source',
        'extractor_version', 'game_mode',
    }
    for field in extractor_system_fields:
        if field in new_data:
            merged[field] = new_data[field]

    # Planets: merge by matching planet name (case-insensitive)
    if 'planets' in new_data:
        existing_planets = {p.get('name', '').strip().lower(): p for p in existing_data.get('planets', []) if p.get('name')}
        merged_planets = []
        for new_planet in new_data['planets']:
            pname = new_planet.get('name', '').strip().lower()
            if pname in existing_planets:
                # Merge: new extractor data on top, preserve manual-only fields
                merged_planet = dict(existing_planets[pname])
                extractor_planet_fields = {
                    'name', 'biome', 'biome_subtype', 'weather', 'climate',
                    'sentinels', 'sentinel', 'flora', 'fauna', 'planet_size',
                    'common_resource', 'uncommon_resource', 'rare_resource',
                    'plant_resource', 'materials',
                    'is_dissonant', 'is_infested', 'extreme_weather',
                    'vile_brood', 'ancient_bones', 'salvageable_scrap',
                    'storm_crystals', 'gravitino_balls', 'dissonance',
                    'planet_description', 'planet_type', 'is_weather_extreme',
                }
                for field in extractor_planet_fields:
                    if field in new_planet:
                        merged_planet[field] = new_planet[field]
                merged_planets.append(merged_planet)
                del existing_planets[pname]
            else:
                # New planet from extractor
                merged_planets.append(new_planet)

        # Keep any remaining existing planets the extractor didn't mention
        merged_planets.extend(existing_planets.values())
        merged['planets'] = merged_planets

    # Moons: same merge logic
    if 'moons' in new_data:
        existing_moons = {m.get('name', '').strip().lower(): m for m in existing_data.get('moons', []) if m.get('name')}
        merged_moons = []
        for new_moon in new_data['moons']:
            mname = new_moon.get('name', '').strip().lower()
            if mname in existing_moons:
                merged_moon = dict(existing_moons[mname])
                extractor_moon_fields = {
                    'name', 'biome', 'biome_subtype', 'weather', 'climate',
                    'sentinels', 'sentinel', 'flora', 'fauna', 'planet_size',
                    'common_resource', 'uncommon_resource', 'rare_resource',
                    'plant_resource', 'materials',
                    'is_dissonant', 'is_infested', 'extreme_weather',
                    'vile_brood', 'ancient_bones', 'salvageable_scrap',
                    'storm_crystals', 'gravitino_balls', 'dissonance',
                }
                for field in extractor_moon_fields:
                    if field in new_moon:
                        merged_moon[field] = new_moon[field]
                merged_moons.append(merged_moon)
                del existing_moons[mname]
            else:
                merged_moons.append(new_moon)

        merged_moons.extend(existing_moons.values())
        merged['moons'] = merged_moons

    return merged


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
        app.mount('/haven-ui-static', StaticFiles(directory=str(ui_static_dir)), name='haven-ui-static')

# NOTE: html=True catch-all mount removed — SPA routes handle HTML fallback below.
# The /haven-ui/assets mount serves JS/CSS/images. SPA routes serve index.html for
# all React router paths (/haven-ui/wizard, /haven-ui/systems, etc.).

# In-memory system cache
_systems_cache: Dict[str, dict] = {}
_systems_lock = asyncio.Lock()

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
    # v1.4.6: Special attributes for moons (matching planets table)
    add_column_if_missing('moons', 'has_rings', 'INTEGER DEFAULT 0')
    add_column_if_missing('moons', 'is_dissonant', 'INTEGER DEFAULT 0')
    add_column_if_missing('moons', 'is_infested', 'INTEGER DEFAULT 0')
    add_column_if_missing('moons', 'extreme_weather', 'INTEGER DEFAULT 0')
    add_column_if_missing('moons', 'water_world', 'INTEGER DEFAULT 0')
    add_column_if_missing('moons', 'vile_brood', 'INTEGER DEFAULT 0')
    add_column_if_missing('moons', 'exotic_trophy', 'TEXT')
    add_column_if_missing('moons', 'ancient_bones', 'INTEGER DEFAULT 0')
    add_column_if_missing('moons', 'salvageable_scrap', 'INTEGER DEFAULT 0')
    add_column_if_missing('moons', 'storm_crystals', 'INTEGER DEFAULT 0')
    add_column_if_missing('moons', 'gravitino_balls', 'INTEGER DEFAULT 0')
    add_column_if_missing('moons', 'infested', 'INTEGER DEFAULT 0')
    # v1.50.0: Moon columns matching planets table (fixes missing biome/weather/photo display)
    add_column_if_missing('moons', 'biome', 'TEXT')
    add_column_if_missing('moons', 'biome_subtype', 'TEXT')
    add_column_if_missing('moons', 'weather', 'TEXT')
    add_column_if_missing('moons', 'planet_size', 'TEXT')
    add_column_if_missing('moons', 'common_resource', 'TEXT')
    add_column_if_missing('moons', 'uncommon_resource', 'TEXT')
    add_column_if_missing('moons', 'rare_resource', 'TEXT')
    add_column_if_missing('moons', 'weather_text', 'TEXT')
    add_column_if_missing('moons', 'sentinels_text', 'TEXT')
    add_column_if_missing('moons', 'flora_text', 'TEXT')
    add_column_if_missing('moons', 'fauna_text', 'TEXT')
    add_column_if_missing('moons', 'is_gas_giant', 'INTEGER DEFAULT 0')
    add_column_if_missing('moons', 'dissonance', 'INTEGER DEFAULT 0')
    add_column_if_missing('moons', 'is_bubble', 'INTEGER DEFAULT 0')
    add_column_if_missing('moons', 'is_floating_islands', 'INTEGER DEFAULT 0')
    add_column_if_missing('moons', 'plant_resource', 'TEXT')

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

    # Boot the persistent Playwright browser used by the poster service. The
    # browser stays alive for the process lifetime to amortize the ~3s startup
    # cost across many renders. Boot is non-fatal: if Playwright isn't
    # installed (e.g. on a stripped-down deploy) the poster endpoints will
    # 503, but the rest of the API keeps running.
    try:
        from services.poster_service import init_browser
        await init_browser()
    except Exception as e:
        logger.warning('Poster service: Playwright failed to boot at startup (%s) — '
                       '/api/posters/* endpoints will 503 until restart', e)


@app.on_event('shutdown')
async def on_shutdown():
    """Tear down Playwright cleanly on app shutdown."""
    try:
        from services.poster_service import shutdown_browser
        await shutdown_browser()
    except Exception as e:
        logger.warning('Poster service: shutdown error (non-fatal): %s', e)


# ============================================================================
# Mount Route Modules
# Each module is a FastAPI APIRouter containing related endpoints.
# ============================================================================

from routes.auth import router as auth_router
from routes.analytics import router as analytics_router
from routes.partners import router as partners_router
from routes.warroom import router as warroom_router
from routes.systems import router as systems_router
from routes.approvals import router as approvals_router
from routes.discoveries import router as discoveries_router
from routes.profiles import router as profiles_router
from routes.events import router as events_router
from routes.regions import router as regions_router
from routes.extractor import router as extractor_router
from routes.csv_import import router as csv_import_router
from routes.posters import router as posters_router
from routes.ssr import router as ssr_router

app.include_router(auth_router)
app.include_router(systems_router)
app.include_router(analytics_router)
app.include_router(partners_router)
app.include_router(approvals_router)
app.include_router(discoveries_router)
app.include_router(profiles_router)
app.include_router(events_router)
app.include_router(regions_router)
app.include_router(extractor_router)
app.include_router(csv_import_router)
app.include_router(warroom_router)
app.include_router(posters_router)

# SSR shim catches share-friendly URLs like /voyager/:user and /atlas/:galaxy
# BEFORE the SPA index falls through. Discord/Twitter scrapers stop at the
# meta tags here; real browsers run the inline JS and continue to the SPA.
app.include_router(ssr_router)

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
    """Serve workbox JS from dist if present, otherwise 204."""
    from fastapi.responses import FileResponse, Response
    # Try to serve from dist, otherwise return 204
    dist_path = HAVEN_UI_DIR / 'dist' / f'workbox-{version}.js'
    if dist_path.exists():
        return FileResponse(str(dist_path))
    return Response(status_code=204)


@app.get('/haven-ui/sw.js')
async def sw_js():
    """Serve service worker JS from dist or static, otherwise 204."""
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
    """Serve service worker registration script from dist or static."""
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

# Additional SPA routes for all React pages
@app.get('/haven-ui/community-stats')
async def spa_community_stats():
    return await _serve_spa_index()

@app.get('/haven-ui/community-stats/{path:path}')
async def spa_community_detail(path: str):
    return await _serve_spa_index()

@app.get('/haven-ui/events')
async def spa_events():
    return await _serve_spa_index()

@app.get('/haven-ui/analytics')
async def spa_analytics():
    return await _serve_spa_index()

@app.get('/haven-ui/partner-analytics')
async def spa_partner_analytics():
    return await _serve_spa_index()

@app.get('/haven-ui/db_stats')
async def spa_db_stats():
    return await _serve_spa_index()

@app.get('/haven-ui/admin/{path:path}')
async def spa_admin(path: str):
    return await _serve_spa_index()

@app.get('/haven-ui/api-keys')
async def spa_api_keys():
    return await _serve_spa_index()

@app.get('/haven-ui/csv-import')
async def spa_csv_import():
    return await _serve_spa_index()

@app.get('/haven-ui/data-restrictions')
async def spa_data_restrictions():
    return await _serve_spa_index()

@app.get('/haven-ui/profile')
async def spa_profile():
    return await _serve_spa_index()

@app.get('/haven-ui/regions/{path:path}')
async def spa_regions(path: str):
    return await _serve_spa_index()

# Catch-all for any other /haven-ui/ routes not matched above
@app.get('/haven-ui/{path:path}')
async def spa_catchall(path: str):
    """Fallback: serve index.html for any unmatched /haven-ui/ route (React handles routing)."""
    # Don't catch asset requests
    if path.startswith('assets/') or path.endswith(('.js', '.css', '.png', '.svg', '.ico', '.webp', '.woff2')):
        return Response(status_code=404)
    return await _serve_spa_index()


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



@app.post('/api/reject_region_names/batch')
async def api_batch_reject_region_names(payload: dict, session: Optional[str] = Cookie(None)):
    """Batch reject pending region name submissions. Requires batch_approvals feature."""
    from datetime import datetime, timezone

    if not verify_session(session):
        raise HTTPException(status_code=401, detail='Admin authentication required')
    session_data = get_session(session)
    require_feature(session_data, 'approvals')

    is_super = session_data.get('user_type') == 'super_admin'
    if not is_super:
        enabled_features = session_data.get('enabled_features', [])
        if 'batch_approvals' not in enabled_features:
            raise HTTPException(status_code=403, detail='Batch approvals permission required')

    submission_ids = payload.get('submission_ids', [])
    reason = payload.get('reason', '')
    if not submission_ids or not isinstance(submission_ids, list):
        raise HTTPException(status_code=400, detail='submission_ids array is required')

    results = {'rejected': [], 'failed': [], 'skipped': []}
    approver_username = session_data.get('username', 'admin')
    approver_profile_id = session_data.get('profile_id')

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        for submission_id in submission_ids:
            try:
                cursor.execute('SELECT * FROM pending_region_names WHERE id = ? AND status = ?',
                               (submission_id, 'pending'))
                row = cursor.fetchone()
                if not row:
                    results['failed'].append({'id': submission_id, 'error': 'Not found or already processed'})
                    continue

                submission = dict(row)
                proposed_name = submission['proposed_name']

                # Mark as rejected
                cursor.execute('''
                    UPDATE pending_region_names SET status = 'rejected', review_date = ?, reviewed_by = ?, review_notes = ?
                    WHERE id = ?
                ''', (datetime.now(timezone.utc).isoformat(), approver_username, reason, submission_id))

                # Audit log
                try:
                    cursor.execute('''
                        INSERT INTO approval_audit_log
                        (timestamp, action, submission_type, submission_id, submission_name,
                         approver_username, approver_type, approver_account_id, approver_discord_tag,
                         submitter_username, notes, submission_discord_tag, source)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        datetime.now(timezone.utc).isoformat(), 'rejected', 'region', submission_id,
                        proposed_name, approver_username,
                        session_data.get('user_type', 'super_admin'), approver_profile_id,
                        session_data.get('discord_tag'), submission.get('submitted_by'),
                        reason, submission.get('discord_tag'), 'manual'
                    ))
                except Exception as audit_err:
                    logger.warning(f"Failed to add batch region reject audit log: {audit_err}")

                results['rejected'].append({'id': submission_id, 'name': proposed_name})

            except Exception as e:
                results['failed'].append({'id': submission_id, 'error': str(e)})

        conn.commit()

        add_activity_log(
            'batch_region_rejected',
            f"Batch rejected {len(results['rejected'])} region names",
            details=f"Rejected: {len(results['rejected'])}, Failed: {len(results['failed'])}. Reason: {reason or 'No reason'}",
            user_name=approver_username
        )

        return results
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in batch region reject: {e}")
        logger.exception("Internal server error")
        raise HTTPException(status_code=500, detail="Internal server error")
    finally:
        if conn:
            conn.close()


@app.post('/api/systems/bulk')
async def get_systems_bulk(request: Request):
    """Return full detail for multiple systems by ID in one request.

    Body: {"ids": ["id1", "id2", ...]}
    Returns: {"systems": [...], "not_found": [...]}
    Max 100 IDs per request.
    """
    conn = None
    try:
        body = await request.json()
        ids = body.get('ids', [])
        if not ids or not isinstance(ids, list):
            raise HTTPException(400, "Request body must contain 'ids' array")
        ids = ids[:100]  # Cap at 100

        db_path = get_db_path()
        if not db_path.exists():
            raise HTTPException(404, "Database not found")

        conn = get_db_connection()
        cursor = conn.cursor()

        systems = []
        not_found = []

        # Batch-fetch all systems
        placeholders = ','.join(['?'] * len(ids))
        cursor.execute(f'SELECT * FROM systems WHERE id IN ({placeholders})', ids)
        system_rows = {str(dict(r)['id']): dict(r) for r in cursor.fetchall()}

        # Batch-fetch all planets for these systems
        found_ids = list(system_rows.keys())
        if found_ids:
            ph = ','.join(['?'] * len(found_ids))
            cursor.execute(f'SELECT * FROM planets WHERE system_id IN ({ph}) ORDER BY system_id, name', found_ids)
            all_planets = [dict(r) for r in cursor.fetchall()]

            # Batch-fetch all moons
            planet_ids = [p['id'] for p in all_planets]
            all_moons = []
            if planet_ids:
                ph2 = ','.join(['?'] * len(planet_ids))
                cursor.execute(f'SELECT * FROM moons WHERE planet_id IN ({ph2}) ORDER BY planet_id, name', planet_ids)
                all_moons = [dict(m) for m in cursor.fetchall()]

            # Index moons by planet_id
            moons_by_planet = {}
            for m in all_moons:
                moons_by_planet.setdefault(m['planet_id'], []).append(m)

            # Index planets by system_id, attach moons
            planets_by_system = {}
            for p in all_planets:
                p['moons'] = moons_by_planet.get(p['id'], [])
                planets_by_system.setdefault(p['system_id'], []).append(p)

            # Batch-fetch space stations
            cursor.execute(f'SELECT * FROM space_stations WHERE system_id IN ({ph})', found_ids)
            stations_by_system = {}
            for row in cursor.fetchall():
                stations_by_system[str(dict(row)['system_id'])] = parse_station_data(row)

        for sid in ids:
            if str(sid) in system_rows:
                system = system_rows[str(sid)]
                system['planets'] = planets_by_system.get(str(sid), [])
                system['space_station'] = stations_by_system.get(str(sid))
                systems.append(system)
            else:
                not_found.append(sid)

        return {"systems": systems, "not_found": not_found}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in bulk system fetch: {e}")
        raise HTTPException(500, str(e))
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
            # Lookup by ID only — system identity is glyph-based, not name-based
            cursor.execute('SELECT * FROM systems WHERE id = ?', (system_id,))
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

        raise HTTPException(status_code=404, detail='System not found')
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Internal server error")
        raise HTTPException(status_code=500, detail="Internal server error")
    finally:
        if conn:
            conn.close()


@app.delete('/api/systems/{system_id}')
async def delete_system(system_id: str, session: Optional[str] = Cookie(None)):
    """Delete a system and all its children (planets, moons, discoveries). Super admin only."""
    if not is_super_admin(session):
        raise HTTPException(status_code=403, detail='Super admin access required')
    conn = None
    try:
        db_path = get_db_path()
        if db_path.exists():
            conn = get_db_connection()
            cursor = conn.cursor()

            # Get system name before deleting — ID only, no name fallback
            cursor.execute('SELECT name FROM systems WHERE id = ?', (system_id,))
            system_row = cursor.fetchone()
            if not system_row:
                raise HTTPException(status_code=404, detail='System not found')
            system_name = system_row['name']

            # Delete by ID only — no name fallback
            cursor.execute('DELETE FROM discoveries WHERE system_id = ?', (system_id,))
            cursor.execute('SELECT id FROM planets WHERE system_id = ?', (system_id,))
            planet_rows = cursor.fetchall()
            planet_ids = [r[0] for r in planet_rows]
            if planet_ids:
                cursor.executemany('DELETE FROM moons WHERE planet_id = ?', [(pid,) for pid in planet_ids])
                cursor.execute('DELETE FROM planets WHERE system_id = ?', (system_id,))
            cursor.execute('DELETE FROM systems WHERE id = ?', (system_id,))
            conn.commit()

            # Add activity log
            add_activity_log(
                'system_deleted',
                f"System '{system_name}' deleted",
                user_name='Admin'
            )

            return {'status': 'ok'}

        raise HTTPException(status_code=404, detail='System not found')
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Internal server error")
        raise HTTPException(status_code=500, detail="Internal server error")
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
    No auth required.

    Required: name, glyph_code (12 hex chars)
    Optional: galaxy (default Euclid), reality (default Normal), discord_tag

    Dedup: Uses canonical last-11 glyph chars + galaxy + reality.
    If a matching system already exists, returns it instead.
    """
    import uuid as uuid_mod

    name = (payload.get('name') or '').strip()
    if not name:
        raise HTTPException(status_code=400, detail='System name is required')
    if len(name) > 100:
        raise HTTPException(status_code=400, detail='System name must be 100 characters or less')

    # Glyph code is REQUIRED for stubs (prevents 0,0,0 coordinate stubs)
    glyph_code = (payload.get('glyph_code') or '').strip()
    if not glyph_code or not re.match(r'^[0-9A-Fa-f]{12}$', glyph_code):
        raise HTTPException(status_code=400, detail='Portal glyph code is required (exactly 12 hex characters)')

    galaxy = payload.get('galaxy', 'Euclid') or 'Euclid'
    reality = payload.get('reality', 'Normal') or 'Normal'
    discord_tag = payload.get('discord_tag')

    # Validate galaxy
    if galaxy and not validate_galaxy(galaxy):
        raise HTTPException(status_code=400, detail=f"Unknown galaxy: {galaxy}")

    # Validate reality
    if reality and not validate_reality(reality):
        raise HTTPException(status_code=400, detail="Reality must be 'Normal' or 'Permadeath'")

    # Decode glyph
    star_x, star_y, star_z = None, None, None
    region_x, region_y, region_z = None, None, None
    x, y, z = 0, 0, 0
    glyph_planet, glyph_solar_system = 0, 1
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
        raise HTTPException(status_code=400, detail='Invalid glyph code')

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Canonical dedup: last-11 glyph chars + galaxy + reality
        existing_row = find_matching_system(cursor, glyph_code, galaxy, reality)
        if existing_row:
            return {
                'status': 'existing',
                'system_id': existing_row[0],
                'name': existing_row[1],
                'galaxy': galaxy,
                'is_stub': False  # Existing full system
            }

        # Also check pending systems
        pending_row = find_matching_pending_system(cursor, glyph_code, galaxy, reality)
        if pending_row:
            return {
                'status': 'existing_pending',
                'submission_id': pending_row[0],
                'name': pending_row[1],
                'galaxy': galaxy,
                'message': 'A system at these coordinates is already pending approval'
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

        logger.info(f"Created stub system '{name}' (ID: {sys_id}, glyph: {glyph_code})")
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
        logger.exception("Internal server error")
        raise HTTPException(status_code=500, detail="Internal server error")
    finally:
        if conn:
            conn.close()


@app.post('/api/save_system')
async def save_system(payload: dict, session: Optional[str] = Cookie(None)):
    """Create or update a full system with planets, moons, and space station. Admin only.

    # NOTE: INTENTIONAL DESIGN — Two-track submission pipeline:
    # Partners with SYSTEM_CREATE feature bypass the pending queue and save directly.
    # This is intentional — partners are trusted community leaders; the SYSTEM_CREATE flag
    # controls this privilege, not a security boundary. Their saves are still audit-logged.
    # Public submissions go through /api/submit_system -> pending_systems queue for review.

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

    # Feature enforcement: system_create for new, system_edit for updates
    system_id = payload.get('id')
    if system_id:
        require_feature(session_data, 'system_edit')
    else:
        require_feature(session_data, 'system_create')

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

    # NOTE: INTENTIONAL DESIGN - partners creating new systems are auto-tagged with their
    # community discord tag to ensure proper attribution.
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

        # Check if system exists - canonical dedup: glyph last-11 + galaxy + reality
        # Fallback to ID if no glyph available (legacy edge case)
        existing = None
        if payload.get('glyph_code'):
            existing_row = find_matching_system(cursor, payload['glyph_code'], galaxy, reality)
            if existing_row:
                existing = {'id': existing_row[0]}
        if not existing and system_id:
            cursor.execute('SELECT id FROM systems WHERE id = ?', (system_id,))
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

            # NOTE: Delete-and-reinsert for planets. Frontend sends the complete planet list
            # each time, so we replace all rather than diffing individual planet rows.
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
                    stellar_classification, discovered_by, discovered_at, contributors,
                    profile_id, personal_discord_username, source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                json.dumps([{"name": editor_username, "action": "upload", "date": now_iso}]),
                session_data.get('profile_id'),
                session_data.get('username') or payload.get('personal_discord_username'),
                'manual'
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
                    has_rings, is_dissonant, is_infested, extreme_weather, water_world, vile_brood,
                    ancient_bones, salvageable_scrap, storm_crystals, gravitino_balls, is_gas_giant, exotic_trophy,
                    is_bubble, is_floating_islands
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                # Planet specials + valuable resources
                1 if planet.get('has_rings') else 0,
                1 if planet.get('is_dissonant') else 0,
                1 if planet.get('is_infested') else 0,
                1 if planet.get('extreme_weather') else 0,
                1 if planet.get('water_world') else 0,
                1 if planet.get('vile_brood') else 0,
                1 if planet.get('ancient_bones') else 0,
                1 if planet.get('salvageable_scrap') else 0,
                1 if planet.get('storm_crystals') else 0,
                1 if planet.get('gravitino_balls') else 0,
                1 if planet.get('is_gas_giant') else 0,
                planet.get('exotic_trophy'),
                1 if planet.get('is_bubble') else 0,
                1 if planet.get('is_floating_islands') else 0
            ))
            planet_id = cursor.lastrowid

            # Insert moons with ALL fields
            for moon in planet.get('moons', []):
                cursor.execute('''
                    INSERT INTO moons (planet_id, name, orbit_radius, orbit_speed, climate, sentinel, fauna, flora, materials, notes, description, photo,
                        has_rings, is_dissonant, is_infested, extreme_weather, water_world, vile_brood, exotic_trophy,
                        ancient_bones, salvageable_scrap, storm_crystals, gravitino_balls, infested, is_gas_giant,
                        is_bubble, is_floating_islands)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    moon.get('photo'),
                    1 if moon.get('has_rings') else 0,
                    1 if moon.get('is_dissonant') else 0,
                    1 if moon.get('is_infested') else 0,
                    1 if moon.get('extreme_weather') else 0,
                    1 if moon.get('water_world') else 0,
                    1 if moon.get('vile_brood') else 0,
                    moon.get('exotic_trophy'),
                    1 if moon.get('ancient_bones') else 0,
                    1 if moon.get('salvageable_scrap') else 0,
                    1 if moon.get('storm_crystals') else 0,
                    1 if moon.get('gravitino_balls') else 0,
                    1 if moon.get('infested') else 0,
                    1 if moon.get('is_gas_giant') else 0,
                    1 if moon.get('is_bubble') else 0,
                    1 if moon.get('is_floating_islands') else 0
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
                 submitter_username, submitter_account_id, submitter_type, notes, submission_discord_tag, source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                payload.get('discord_tag'),
                'manual'
            ))
            conn.commit()
            logger.info(f"Audit log: {action} for system '{name}' by {current_username}")
        except Exception as audit_err:
            logger.warning(f"Failed to add audit log entry: {audit_err}")

        return {'status': 'ok', 'saved': payload, 'system_id': sys_id}

    except Exception as e:
        logger.error(f'Error saving system to database: {e}')
        logger.exception("Database error")
        raise HTTPException(status_code=500, detail="Database error")
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

        # NOTE: Response shape varies by role - super admin gets admin-specific counts,
        # partners get community-filtered stats, public gets basic global counts.
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

            # Count populated regions, scoped to match the regions table UNIQUE constraint
            # (reality, galaxy, region_x, region_y, region_z) — set in migration v1.49.0.
            cursor.execute("""
                SELECT COUNT(*) FROM (
                    SELECT DISTINCT
                        COALESCE(reality, 'Normal') AS reality,
                        COALESCE(galaxy, 'Euclid') AS galaxy,
                        region_x, region_y, region_z
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

            # Count populated regions, scoped to match the regions table UNIQUE constraint
            # (reality, galaxy, region_x, region_y, region_z) — set in migration v1.49.0.
            cursor.execute("""
                SELECT COUNT(*) FROM (
                    SELECT DISTINCT
                        COALESCE(reality, 'Normal') AS reality,
                        COALESCE(galaxy, 'Euclid') AS galaxy,
                        region_x, region_y, region_z
                    FROM systems
                    WHERE region_x IS NOT NULL AND region_y IS NOT NULL AND region_z IS NOT NULL
                )
            """)
            stats['populated_regions'] = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM planet_pois")
            stats['planet_pois'] = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM discoveries")
            stats['discoveries'] = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(DISTINCT galaxy) FROM systems WHERE galaxy IS NOT NULL")
            stats['galaxies_explored'] = cursor.fetchone()[0]
            stats['unique_galaxies'] = stats['galaxies_explored']

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

        # Lookup by ID only — system identity is glyph-based, not name-based
        cursor.execute('SELECT * FROM systems WHERE id = ?', (system_id,))
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

        # NOTE: Server-side data injection - system JSON is embedded into the HTML template
        # so the 3D viewer has data immediately without a second API call.
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
        logger.exception("Error rendering system view")
        raise HTTPException(status_code=500, detail="Error rendering system view")
    finally:
        if conn:
            conn.close()


# ========== ADMIN TOOLS ==========

@app.get('/api/logs')
async def get_logs():
    """Return last 200 lines of the server log file. No auth required."""
    logfile = LOGS_DIR / 'control-room-web.log'
    if not logfile.exists():
        return {'lines': []}
    lines = logfile.read_text(encoding='utf-8', errors='ignore').splitlines()[-200:]
    return {'lines': lines}

@app.post('/api/backup')
async def create_backup(session: Optional[str] = Cookie(None)):
    """Create database backup (super admin only)"""
    if not is_super_admin(session):
        raise HTTPException(status_code=403, detail='Super admin access required')
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
        logger.exception("Internal server error")
        raise HTTPException(status_code=500, detail="Internal server error")




@app.websocket('/ws/logs')
async def ws_logs(ws: WebSocket):
    """Stream last 1000 chars of web log file to connected clients every 1s."""
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

    # Glyph code is required and must be exactly 12 hex characters
    glyph = system.get('glyph_code', '')
    if not glyph or not isinstance(glyph, str) or not re.match(r'^[0-9A-Fa-f]{12}$', glyph):
        return False, "Portal glyph code is required (exactly 12 hex characters)"

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




if __name__ == '__main__':
    import uvicorn
    import uvicorn.logging
    from datetime import datetime

    # Fix Windows console encoding for Unicode box-drawing characters
    import sys
    if sys.platform == 'win32':
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')

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
