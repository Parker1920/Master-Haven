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

from constants import BACKEND_DIR, HAVEN_UI_DIR, ACTIVITY_LOG_MAX, normalize_discovery_coords

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


def norm_token(value):
    """Normalize a categorical value for case / spacing / punctuation-insensitive
    matching: lowercase, keep only alphanumerics.

    Registered as a SQLite function on every connection AND used in Python by the
    filter-options dedup, so the two stay perfectly in step. This is what lets the
    dropdown collapse formatting variants ("Power Generation" / "PowerGeneration"
    / "power-generation") into ONE option while the filter still matches every
    variant row. Returns '' for NULL.
    """
    if value is None:
        return ''
    return ''.join(ch for ch in str(value).lower() if ch.isalnum())


def get_db_connection():
    """Create a properly configured database connection with timeout and WAL mode.

    PRAGMA notes:
    - synchronous=NORMAL trades one fsync per commit for ~2x write throughput.
      Acceptable on the Pi 5 SSD with no power-event history; in WAL mode the
      database is still safe across crashes (only a transaction-in-flight at
      power loss can be lost). Do NOT downgrade back to FULL without a
      power-loss incident to justify it — this is intentional.
    - cache_size=-64000 sets a 64 MB page cache (negative means KiB).
    - mmap_size=256 MB enables memory-mapped I/O for read-heavy workloads.
    - temp_store=MEMORY keeps temp btrees off disk for the duration of a query.
    """
    db_path = get_db_path()
    conn = sqlite3.connect(str(db_path), timeout=30.0)
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA busy_timeout=30000')
    conn.execute('PRAGMA synchronous=NORMAL')
    conn.execute('PRAGMA cache_size=-64000')
    conn.execute('PRAGMA mmap_size=268435456')
    conn.execute('PRAGMA temp_store=MEMORY')
    # ON DELETE CASCADE clauses on moons/discoveries/etc. were dead code without
    # this PRAGMA — SQLite defaults FKs to OFF per-connection. Enables FK
    # enforcement for every new statement on this conn.
    conn.execute('PRAGMA foreign_keys=ON')
    # Categorical-match normalizer (see norm_token). try/except keeps it working
    # on older sqlite builds that reject the `deterministic` kwarg.
    try:
        conn.create_function('norm_token', 1, norm_token, deterministic=True)
    except (TypeError, sqlite3.NotSupportedError):
        # Older Python rejects the kwarg (TypeError); older SQLite rejects
        # deterministic functions (NotSupportedError). Plain registration works
        # everywhere — this factory must never throw.
        conn.create_function('norm_token', 1, norm_token)
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


def snapshot_child_name_maps(cursor, system_id):
    """Capture {normalized_name -> old child id} for a system's planets and moons,
    taken BEFORE a delete-and-reinsert of those rows.

    Planets/moons are routinely replaced wholesale (DELETE + re-INSERT) on every
    save/edit/batch-approve, which hands them brand-new primary keys. Discoveries
    link to planets/moons by id, so unless those links are re-pointed afterward,
    every discovery on the system is silently orphaned. Pair this with
    relink_discoveries_after_rebuild() across the delete to keep the links intact.

    Returns (planet_old, moon_old):
      planet_old: {planet_name_lower -> old planet id}
      moon_old:   {(parent_planet_name_lower, moon_name_lower) -> old moon id}
    Names are stripped + lowercased; same-named children collapse (acceptable — the
    wizard blocks duplicate body names, and a collapse degrades to a correct link
    rather than an orphan).
    """
    cursor.execute('SELECT id, name FROM planets WHERE system_id = ?', (system_id,))
    planet_old = {}
    old_pid_to_name = {}
    for row in cursor.fetchall():
        pid, pname = row[0], row[1]
        old_pid_to_name[pid] = (pname or '')
        if pname and pname.strip():
            planet_old[pname.strip().lower()] = pid
    moon_old = {}
    if old_pid_to_name:
        qmarks = ','.join('?' * len(old_pid_to_name))
        cursor.execute(
            f'SELECT id, name, planet_id FROM moons WHERE planet_id IN ({qmarks})',
            list(old_pid_to_name.keys()))
        for row in cursor.fetchall():
            mid, mname, parent_pid = row[0], row[1], row[2]
            if mname and mname.strip():
                parent_name = (old_pid_to_name.get(parent_pid) or '').strip().lower()
                moon_old[(parent_name, mname.strip().lower())] = mid
    return planet_old, moon_old


def relink_discoveries_after_rebuild(cursor, system_id, planet_old, moon_old):
    """Re-point this system's discoveries from old planet/moon ids to the new ids
    that share the same (case-insensitive) name, after the planets/moons were
    deleted and re-inserted. `planet_old`/`moon_old` come from
    snapshot_child_name_maps() called BEFORE the delete. Returns the number of
    discovery rows re-pointed. Safe no-op when nothing changed.
    """
    if not planet_old and not moon_old:
        return 0

    # Build new name -> id maps from the freshly-inserted rows.
    cursor.execute('SELECT id, name FROM planets WHERE system_id = ?', (system_id,))
    planet_new = {}
    new_pid_to_name = {}
    for row in cursor.fetchall():
        pid, pname = row[0], row[1]
        new_pid_to_name[pid] = (pname or '')
        if pname and pname.strip():
            planet_new[pname.strip().lower()] = pid
    moon_new = {}
    if new_pid_to_name:
        qmarks = ','.join('?' * len(new_pid_to_name))
        cursor.execute(
            f'SELECT id, name, planet_id FROM moons WHERE planet_id IN ({qmarks})',
            list(new_pid_to_name.keys()))
        for row in cursor.fetchall():
            mid, mname, parent_pid = row[0], row[1], row[2]
            if mname and mname.strip():
                parent_name = (new_pid_to_name.get(parent_pid) or '').strip().lower()
                moon_new[(parent_name, mname.strip().lower())] = mid

    relinked = 0
    for name, old_id in planet_old.items():
        new_id = planet_new.get(name)
        if new_id is not None and new_id != old_id:
            cursor.execute(
                'UPDATE discoveries SET planet_id = ? WHERE system_id = ? AND planet_id = ?',
                (new_id, system_id, old_id))
            relinked += cursor.rowcount
    for key, old_id in moon_old.items():
        new_id = moon_new.get(key)
        if new_id is not None and new_id != old_id:
            cursor.execute(
                'UPDATE discoveries SET moon_id = ? WHERE system_id = ? AND moon_id = ?',
                (new_id, system_id, old_id))
            relinked += cursor.rowcount
    return relinked


def set_base_fields(cursor, table: str, row_id, body: dict) -> None:
    """Persist a planet/moon's base location + lat/long after its INSERT.

    Base data (free-text `base_location` + `base_latitude`/`base_longitude`) is
    manual-only (entered in the wizard) and is set via a small follow-up UPDATE
    rather than threaded through every positional INSERT — there are several such
    INSERTs and a miscounted placeholder would silently shift columns. Only
    writes when at least one base field is present, so it's a no-op for extractor
    / coordinate-less bodies. Coordinates are range-validated (lat [-90,90],
    lng [-180,180]) via the shared discovery-coord normalizer.
    """
    if table not in ('planets', 'moons') or not row_id:
        return
    loc = body.get('base_location')
    loc = loc if (loc is not None and str(loc).strip()) else None
    lat, lng = normalize_discovery_coords(body.get('base_latitude'), body.get('base_longitude'))
    if loc is None and lat is None and lng is None:
        return
    # COALESCE keeps a base_location already written by the INSERT (planets) when
    # this call doesn't carry one; lat/lng are authoritative from the body.
    cursor.execute(
        f'UPDATE {table} SET base_location = COALESCE(?, base_location), '
        'base_latitude = ?, base_longitude = ? WHERE id = ?',
        (loc, lat, lng, row_id),
    )


def find_matching_system(cursor, glyph_code: str, galaxy: str, reality: str):
    """Find an existing system that matches by glyph coordinates + galaxy + reality.

    Uses the indexed `glyph_code_suffix` column (auto-maintained by triggers in
    migration 1.73.0). The previous `SUBSTR(glyph_code, -11) = ?` form defeated
    idx_systems_glyph_code because the LHS was an expression — this function is
    called inside the approval transaction and on every extractor upload, so it
    needs to use the index.
    """
    system_glyph = get_system_glyph(glyph_code)
    if not system_glyph:
        return None
    cursor.execute('''
        SELECT id, name, glyph_code, glyph_planet, glyph_solar_system,
               discovered_by, discovered_at, contributors
        FROM systems
        WHERE glyph_code_suffix = ?
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
        WHERE glyph_code_suffix = ?
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
# Archived Civilization Filter (shared across public endpoints)
# ============================================================================

# SQL fragment that excludes rows whose discord_tag belongs to an archived
# (is_active=0) civilization.  Works for any table aliased as `s` (systems),
# `d` (discoveries), or `r` (regions) — pass the alias.
# Returns (clause_str, params_list).  Caller appends to its WHERE chain.
# Super-admin callers should skip this entirely.

ARCHIVED_CIV_FILTER_SQL = (
    "NOT EXISTS ("
    "  SELECT 1 FROM civilizations _ac"
    "  WHERE _ac.tag = {alias}.discord_tag AND _ac.is_active = 0"
    ")"
)


def archived_civ_filter(alias: str = 's') -> str:
    """Return a SQL clause that hides rows belonging to archived civilizations.

    The subquery checks if the row's discord_tag matches any civ with
    is_active = 0.  Rows with NULL/empty discord_tag or tags that don't
    have a civilizations entry pass through (they're personal or
    unregistered — not archived).

    Usage:
        if not is_super_admin:
            where_clauses.append(archived_civ_filter('s'))
    """
    return ARCHIVED_CIV_FILTER_SQL.format(alias=alias)


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
    # Comma-separated lists collapse to SQL IN (...) for OR-logic multi-select.
    # Single values still work — _split_csv returns a 1-element list. Per spec
    # section 3.3, star_type / economy_level / conflict_level / completeness
    # grade are OR-logic multi-select.
    def _split_csv(v):
        if v is None:
            return None
        s = str(v).strip()
        if not s:
            return None
        return [p.strip() for p in s.split(',') if p.strip()]

    # Categorical fields are matched through norm_token() (case / spacing /
    # punctuation-insensitive) so a dropdown option that the filter-options dedup
    # collapsed ("Power Generation") still matches every stored variant
    # ("PowerGeneration", "power-generation", ...). Same normalizer on both sides.
    star_types = _split_csv(params_dict.get('star_type'))
    if star_types:
        where_clauses.append(f"norm_token(s.star_type) IN ({','.join(['?'] * len(star_types))})")
        params.extend(norm_token(v) for v in star_types)
    if params_dict.get('economy_type'):
        where_clauses.append("norm_token(s.economy_type) = ?")
        params.append(norm_token(params_dict['economy_type']))
    economy_levels = _split_csv(params_dict.get('economy_level'))
    if economy_levels:
        where_clauses.append(f"norm_token(s.economy_level) IN ({','.join(['?'] * len(economy_levels))})")
        params.extend(norm_token(v) for v in economy_levels)
    conflict_levels = _split_csv(params_dict.get('conflict_level'))
    if conflict_levels:
        where_clauses.append(f"norm_token(s.conflict_level) IN ({','.join(['?'] * len(conflict_levels))})")
        params.extend(norm_token(v) for v in conflict_levels)
    if params_dict.get('dominant_lifeform'):
        where_clauses.append("norm_token(s.dominant_lifeform) = ?")
        params.append(norm_token(params_dict['dominant_lifeform']))
    if params_dict.get('stellar_classification'):
        where_clauses.append("norm_token(s.stellar_classification) = ?")
        params.append(norm_token(params_dict['stellar_classification']))
    is_complete_val = params_dict.get('is_complete')
    if is_complete_val is not None:
        grade_thresholds = {'S': (85, 100), 'A': (65, 84), 'B': (40, 64), 'C': (0, 39)}
        grades = _split_csv(is_complete_val) if isinstance(is_complete_val, str) else None
        if grades and all(g in grade_thresholds for g in grades):
            # 1+ valid grade letters → OR'd BETWEEN clauses. Single-letter case
            # produces "((s.is_complete BETWEEN ? AND ?))" — extra parens are
            # harmless and avoid a special-case branch.
            grade_clauses = []
            for g in grades:
                low, high = grade_thresholds[g]
                grade_clauses.append("(s.is_complete BETWEEN ? AND ?)")
                params.extend([low, high])
            where_clauses.append("(" + " OR ".join(grade_clauses) + ")")
        elif is_complete_val:
            # Legacy boolean / truthy fallback — used when callers send
            # `is_complete=true` rather than a grade letter.
            where_clauses.append("s.is_complete >= 65")
        else:
            where_clauses.append("s.is_complete < 65")
    if params_dict.get('biome'):
        where_clauses.append("EXISTS (SELECT 1 FROM planets p WHERE p.system_id = s.id AND norm_token(p.biome) = ?)")
        params.append(norm_token(params_dict['biome']))
    if params_dict.get('weather'):
        where_clauses.append("EXISTS (SELECT 1 FROM planets p WHERE p.system_id = s.id AND norm_token(p.weather) = ?)")
        params.append(norm_token(params_dict['weather']))
    if params_dict.get('sentinel_level'):
        where_clauses.append("EXISTS (SELECT 1 FROM planets p WHERE p.system_id = s.id AND norm_token(p.sentinel) = ?)")
        params.append(norm_token(params_dict['sentinel_level']))
    if params_dict.get('resource'):
        # The real resource data lives in planets.materials (a ", "-joined list,
        # normalized to canonical names by migration 1.93.0); the dedicated
        # common/uncommon/rare columns are ~empty. Match the resource as a whole
        # comma-bounded token (LIKE is case-insensitive in SQLite), normalizing
        # the two stray separators ("." and " and ") inline so pre-normalization
        # rows still match. Dedicated columns kept as a fallback.
        res = params_dict['resource']
        where_clauses.append("""EXISTS (SELECT 1 FROM planets p WHERE p.system_id = s.id
            AND (
                ', ' || REPLACE(REPLACE(COALESCE(p.materials, ''), '. ', ', '), ' and ', ', ') || ', '
                    LIKE '%, ' || ? || ', %'
                OR p.common_resource = ? OR p.uncommon_resource = ? OR p.rare_resource = ?
            ))""")
        params.extend([res, res, res, res])
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
