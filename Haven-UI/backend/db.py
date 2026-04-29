"""
Database connection management for the Haven Control Room API.

Provides connection helpers, context managers, and shared data-access utilities.
All database access should go through get_db() or get_db_connection().
"""

import json
import logging
import os
import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional

from constants import BACKEND_DIR, HAVEN_UI_DIR, ACTIVITY_LOG_MAX

logger = logging.getLogger('control.room')

# Path setup using centralized config (if available)
try:
    import sys
    if str(BACKEND_DIR) not in sys.path:
        sys.path.insert(0, str(BACKEND_DIR))
    from paths import haven_paths
except ImportError:
    haven_paths = None

# Resolve directories
if haven_paths:
    _HAVEN_UI_DIR = haven_paths.haven_ui_dir
    PHOTOS_DIR = _HAVEN_UI_DIR / 'photos'
    LOGS_DIR = haven_paths.get_logs_dir('haven-ui')
else:
    _HAVEN_UI_DIR = Path(os.getenv('HAVEN_UI_DIR', BACKEND_DIR.parent))
    PHOTOS_DIR = _HAVEN_UI_DIR / 'photos'
    LOGS_DIR = _HAVEN_UI_DIR / 'logs'

# Override HAVEN_UI_DIR from constants if haven_paths provided a different one
if haven_paths:
    HAVEN_UI_DIR_RESOLVED = haven_paths.haven_ui_dir
else:
    HAVEN_UI_DIR_RESOLVED = HAVEN_UI_DIR


def get_db_path() -> Path:
    """Get the path to the Haven database using centralized config."""
    if haven_paths and haven_paths.haven_db:
        return haven_paths.haven_db
    return HAVEN_UI_DIR_RESOLVED / 'data' / 'haven_ui.db'


def get_db_connection():
    """Create a properly configured database connection with timeout and WAL mode."""
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


def _row_to_dict(row):
    """Convert a sqlite3.Row to a plain dictionary."""
    if row is None:
        return None
    return {k: row[k] for k in row.keys()}


def parse_station_data(station_row):
    """Parse space station data from database row, handling JSON trade_goods field."""
    if not station_row:
        return None
    station = dict(station_row)
    trade_goods = station.get('trade_goods', '[]')
    if isinstance(trade_goods, str):
        try:
            station['trade_goods'] = json.loads(trade_goods)
        except (json.JSONDecodeError, TypeError):
            station['trade_goods'] = []
    return station


# Per-process counter that throttles activity-log trimming. The trim was previously
# run on every insert, which under sustained submission load held the SQLite write
# lock long enough for requests to pile up and OOM the Pi. Trimming once per
# _ACTIVITY_LOG_TRIM_EVERY inserts is enough to bound table size in practice while
# keeping the hot path to a single INSERT.
_ACTIVITY_LOG_TRIM_EVERY = 100
_activity_log_insert_counter = 0


def add_activity_log(event_type: str, message: str, details: str = None, user_name: str = None):
    """Add an activity log entry to the database."""
    global _activity_log_insert_counter
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

        _activity_log_insert_counter += 1
        if _activity_log_insert_counter >= _ACTIVITY_LOG_TRIM_EVERY:
            _activity_log_insert_counter = 0
            # Indexed cutoff-based delete: looks up the timestamp of the Nth-newest row
            # via idx_activity_logs_timestamp, then deletes everything older. No full
            # scan, no in-memory sort, no NOT IN subquery.
            cursor.execute('''
                DELETE FROM activity_logs
                WHERE timestamp < COALESCE(
                    (SELECT timestamp FROM activity_logs
                     ORDER BY timestamp DESC LIMIT 1 OFFSET ?),
                    ''
                )
            ''', (ACTIVITY_LOG_MAX,))
            conn.commit()
    except Exception as e:
        logger.error(f"Failed to add activity log: {e}")
    finally:
        if conn:
            conn.close()


# ============================================================================
# System/Glyph Helpers (used by multiple route modules)
# ============================================================================

def get_system_glyph(glyph_code: str) -> Optional[str]:
    """Extract the system portion of a glyph code (last 11 characters)."""
    if not glyph_code or len(glyph_code) < 11:
        return None
    return glyph_code[-11:].upper() if len(glyph_code) >= 11 else glyph_code.upper()


def find_matching_system(cursor, glyph_code: str, galaxy: str, reality: str):
    """Find an existing system that matches by glyph coordinates + galaxy + reality."""
    system_glyph = get_system_glyph(glyph_code)
    if not system_glyph:
        return None
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
    """Find a pending system that matches by glyph coordinates + galaxy + reality."""
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
    """Compare existing system data with new submission data and return mismatch flags."""
    flags = []
    system_checks = [
        ('name', 'System name'),
        ('star_type', 'Star type'),
        ('star_color', 'Star type'),
        ('economy_type', 'Economy type'),
        ('dominant_lifeform', 'Dominant lifeform'),
    ]
    for field, label in system_checks:
        old_val = existing_data.get(field)
        new_val = new_data.get(field)
        if old_val and new_val and str(old_val).strip().lower() != str(new_val).strip().lower():
            if field == 'star_color':
                existing_star = existing_data.get('star_type') or existing_data.get('star_color')
                new_star = new_data.get('star_type') or new_data.get('star_color')
                if existing_star and new_star and str(existing_star).strip().lower() != str(new_star).strip().lower():
                    flags.append(f"{label} differs: '{existing_star}' vs '{new_star}'")
                continue
            if field == 'star_type' and 'star_color' in [c[0] for c in system_checks]:
                continue
            flags.append(f"{label} differs: '{old_val}' vs '{new_val}'")

    existing_planets = existing_data.get('planets', [])
    new_planets = new_data.get('planets', [])
    if existing_planets and new_planets and len(existing_planets) != len(new_planets):
        flags.append(f"Planet count differs: {len(existing_planets)} vs {len(new_planets)}")

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

    existing_moons = existing_data.get('moons', [])
    new_moons = new_data.get('moons', [])
    if existing_moons and new_moons and len(existing_moons) != len(new_moons):
        flags.append(f"Moon count differs: {len(existing_moons)} vs {len(new_moons)}")

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
    """Deep-merge new extraction data on top of existing pending submission data."""
    merged = dict(existing_data)

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

    if 'planets' in new_data:
        existing_planets = {p.get('name', '').strip().lower(): p for p in existing_data.get('planets', []) if p.get('name')}
        merged_planets = []
        for new_planet in new_data['planets']:
            pname = new_planet.get('name', '').strip().lower()
            if pname in existing_planets:
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
                merged_planets.append(new_planet)
        merged_planets.extend(existing_planets.values())
        merged['planets'] = merged_planets

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


# ============================================================================
# Advanced Filter SQL Builder (shared by systems, regions, galaxies endpoints)
# ============================================================================

def _build_advanced_filter_clauses(params_dict, where_clauses, params):
    """Build SQL WHERE clauses for advanced system filters.

    Shared logic between /api/systems, /api/systems/search, /api/galaxies/summary,
    and /api/regions/grouped. Modifies where_clauses and params lists in place.

    System-level filters match directly on the systems table. Planet-level filters use EXISTS
    subqueries to avoid JOIN-based row duplication.
    """
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
    is_complete_val = params_dict.get('is_complete')
    if is_complete_val is not None:
        if isinstance(is_complete_val, str) and is_complete_val in ('S', 'A', 'B', 'C'):
            grade_thresholds = {'S': (85, 100), 'A': (65, 84), 'B': (40, 64), 'C': (0, 39)}
            low, high = grade_thresholds[is_complete_val]
            where_clauses.append("s.is_complete BETWEEN ? AND ?")
            params.extend([low, high])
        elif is_complete_val:
            where_clauses.append("s.is_complete >= 65")
        else:
            where_clauses.append("s.is_complete < 65")
    if params_dict.get('biome'):
        where_clauses.append("EXISTS (SELECT 1 FROM planets p WHERE p.system_id = s.id AND p.biome = ?)")
        params.append(params_dict['biome'])
    if params_dict.get('weather'):
        where_clauses.append("EXISTS (SELECT 1 FROM planets p WHERE p.system_id = s.id AND p.weather = ?)")
        params.append(params_dict['weather'])
    if params_dict.get('sentinel_level'):
        where_clauses.append("EXISTS (SELECT 1 FROM planets p WHERE p.system_id = s.id AND p.sentinel = ?)")
        params.append(params_dict['sentinel_level'])
    if params_dict.get('resource'):
        where_clauses.append("""EXISTS (SELECT 1 FROM planets p WHERE p.system_id = s.id
            AND (p.common_resource = ? OR p.uncommon_resource = ? OR p.rare_resource = ?))""")
        res = params_dict['resource']
        params.extend([res, res, res])
    if params_dict.get('has_moons') is not None:
        if params_dict['has_moons']:
            where_clauses.append("EXISTS (SELECT 1 FROM planets p JOIN moons m ON m.planet_id = p.id WHERE p.system_id = s.id)")
        else:
            where_clauses.append("NOT EXISTS (SELECT 1 FROM planets p JOIN moons m ON m.planet_id = p.id WHERE p.system_id = s.id)")
    if params_dict.get('min_planets') is not None:
        where_clauses.append("(SELECT COUNT(*) FROM planets p WHERE p.system_id = s.id AND (p.is_moon = 0 OR p.is_moon IS NULL)) >= ?")
        params.append(params_dict['min_planets'])
    if params_dict.get('max_planets') is not None:
        where_clauses.append("(SELECT COUNT(*) FROM planets p WHERE p.system_id = s.id AND (p.is_moon = 0 OR p.is_moon IS NULL)) <= ?")
        params.append(params_dict['max_planets'])
