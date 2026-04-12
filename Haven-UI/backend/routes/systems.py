"""Systems browsing, search, galaxy, glyph, and stats endpoints."""

import asyncio
import logging
import re
from typing import Optional

from fastapi import APIRouter, Cookie, Header, HTTPException

from constants import (
    GALAXY_BY_INDEX,
    score_to_grade,
    GRADE_THRESHOLDS,
    GALAXY_NAMES,
    validate_galaxy,
    validate_reality,
)
from db import (
    get_db_connection,
    get_db_path,
    add_activity_log,
    parse_station_data,
    find_matching_system,
    find_matching_pending_system,
)
from glyph_decoder import (
    decode_glyph_to_coords,
    encode_coords_to_glyph,
    validate_glyph_code,
    format_glyph,
    is_in_core_void,
    is_phantom_star,
    get_system_classification,
    galactic_coords_to_glyph,
    GLYPH_IMAGES,
)
from services.auth_service import get_session, verify_session, get_effective_discord_tag, verify_api_key
from services.completeness import (
    calculate_completeness_score,
    update_completeness_score,
    _is_filled,
)
from services.restrictions import apply_data_restrictions

logger = logging.getLogger('control.room')

router = APIRouter()


# ============================================================================
# Module-level helpers
# ============================================================================

# _build_advanced_filter_clauses lives in db.py (shared across systems, regions, galaxies)
from db import _build_advanced_filter_clauses


# ============================================================================
# Status & Stats
# ============================================================================

# /api/status is defined in routes/auth.py (single source of truth for version)

@router.get('/api/stats')
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


@router.get('/api/stats/daily_changes')
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


# ============================================================================
# Map
# ============================================================================

@router.get('/api/map/regions-aggregated')
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


# ============================================================================
# Galaxies & Realities
# ============================================================================

@router.get('/api/galaxies')
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


@router.get('/api/realities/summary')
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


@router.get('/api/galaxies/summary')
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
    is_complete: str = None,
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


# ============================================================================
# Activity Logs & Recent Systems
# ============================================================================

@router.get('/api/activity_logs')
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


@router.get('/api/systems/recent')
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


# ============================================================================
# Glyph Operations
# ============================================================================

# Glyph operations
@router.post('/api/decode_glyph')
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


@router.post('/api/encode_glyph')
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


@router.get('/api/glyph_images')
async def api_glyph_images():
    """
    Get mapping of hex digits to glyph image filenames.

    Response: {"0": "IMG_9202.webp", "1": "IMG_9203.webp", ...}
    """
    return GLYPH_IMAGES


@router.post('/api/validate_glyph')
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


# ============================================================================
# Duplicate Check
# ============================================================================

@router.get('/api/check_duplicate')
async def check_duplicate(
    glyph_code: str,
    galaxy: str = 'Euclid',
    reality: str = 'Normal',
    x_api_key: Optional[str] = Header(None, alias='X-API-Key')
):
    """
    Check if a system already exists at the given coordinates.
    Uses canonical dedup: last 11 glyph chars + galaxy + reality.
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

        # Check approved systems using canonical dedup (last-11 + galaxy + reality)
        approved_row = find_matching_system(cursor, glyph_code, galaxy, reality)

        if approved_row:
            return {
                'exists': True,
                'location': 'approved',
                'system_id': approved_row[0],
                'system_name': approved_row[1]
            }

        # Check pending systems using same canonical dedup
        pending_row = find_matching_pending_system(cursor, glyph_code, galaxy, reality)

        if pending_row:
            return {
                'exists': True,
                'location': 'pending',
                'submission_id': pending_row[0],
                'system_name': pending_row[1]
            }

        return {'exists': False}

    except Exception as e:
        logger.error(f"Duplicate check failed: {e}")
        logger.exception("Duplicate check failed")
        raise HTTPException(status_code=500, detail="Duplicate check failed")
    finally:
        if conn:
            conn.close()


# ============================================================================
# Filter Options
# ============================================================================

@router.get('/api/systems/filter-options')
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
                    val = row[0]
                    if val and isinstance(val, str) and len(val) >= 2 and val[0].isalpha():
                        resources.add(val)
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
            'sentinel_levels': get_distinct_planet('sentinel'),
            'resources': get_distinct_resources()
        }
    except Exception as e:
        logger.error(f"Error fetching filter options: {e}")
        return {}
    finally:
        if conn:
            conn.close()


# ============================================================================
# Systems List, Search, By Region
# ============================================================================

@router.get('/api/systems')
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
    is_complete: str = None,
    updated_since: str = None,
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
    limit = min(limit, 500)  # Cap at 500 (raised from 100 for sync use)

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

        # Incremental sync: only return systems created or updated since timestamp
        if updated_since:
            where_clauses.append(
                "(s.created_at >= ? OR s.last_updated_at >= ?)"
            )
            params.extend([updated_since, updated_since])

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
@router.get('/api/systems/search')
async def api_search(
    q: str = '',
    page: int = 1,
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
    is_complete: str = None,
    session: Optional[str] = Cookie(None)
):
    """Search systems by name, glyph code, galaxy, or description with optional advanced filters.

    Uses efficient SQL LIKE queries and returns paginated results with region info.
    Applies data restrictions based on viewer permissions.

    Args:
        q: Search query (matches system name, glyph_code, galaxy, description)
        page: Page number (1-indexed, default 1)
        limit: Max results per page (default 20, max 50)
        star_type..is_complete: Advanced filter parameters
        session: Session cookie for permission checking

    Returns:
        {
            "results": [...],
            "total": 42,
            "page": 1,
            "total_pages": 3,
            "query": "search term"
        }
    """
    session_data = get_session(session)
    q = q.strip()

    if not q:
        return {'results': [], 'total': 0, 'page': 1, 'total_pages': 1, 'query': ''}

    limit = max(1, min(limit, 50))  # Clamp between 1 and 50
    page = max(1, page)
    offset = (page - 1) * limit

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

        # Count total matches first (for pagination metadata)
        cursor.execute(f'''
            SELECT COUNT(*) FROM systems s
            WHERE (s.name LIKE ? COLLATE NOCASE
               OR s.glyph_code LIKE ? COLLATE NOCASE
               OR s.galaxy LIKE ? COLLATE NOCASE
               OR s.description LIKE ? COLLATE NOCASE)
            {adv_sql}
        ''', (search_pattern, search_pattern, search_pattern, search_pattern, *adv_params))
        total = cursor.fetchone()[0]

        # Efficient SQL search across multiple fields with pagination
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
            -- NOTE: Priority ordering: exact match first, prefix match second, substring last
            ORDER BY
                CASE WHEN LOWER(s.name) = LOWER(?) THEN 0
                     WHEN LOWER(s.name) LIKE LOWER(?) THEN 1
                     ELSE 2
                END,
                s.name ASC
            LIMIT ? OFFSET ?
        ''', (search_pattern, search_pattern, search_pattern, search_pattern,
              *adv_params, q, f'{q}%', limit, offset))

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
        results = apply_data_restrictions(systems, session_data)

        total_pages = max(1, (total + limit - 1) // limit)

        return {
            'results': results,
            'total': total,
            'page': page,
            'total_pages': total_pages,
            'query': q
        }

    except Exception as e:
        logger.error(f"Error searching systems: {e}")
        return {'results': [], 'total': 0, 'query': q, 'error': str(e)}
    finally:
        if conn:
            conn.close()


@router.get('/api/systems_by_region')
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

        # No DB found - return empty
        return {
            'region': {'x': rx, 'y': ry, 'z': rz},
            'system_count': 0,
            'systems': []
        }

    except Exception as e:
        logger.error(f"Error fetching systems by region: {e}")
        logger.exception("Internal server error")
        raise HTTPException(status_code=500, detail="Internal server error")
    finally:
        if conn:
            conn.close()
