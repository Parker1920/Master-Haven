"""Systems browsing, search, galaxy, glyph, and stats endpoints."""

import asyncio
import base64
import hashlib
import json
import logging
import re
from typing import Optional

from fastapi import APIRouter, Cookie, Header, HTTPException
from fastapi.responses import Response

from constants import (
    GALAXY_BY_INDEX,
    score_to_grade,
    GRADE_THRESHOLDS,
    GALAXY_NAMES,
    validate_galaxy,
    validate_reality,
    normalize_reality,
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
from services.namegen_service import generate_names
from option_catalog import get_option_catalog

logger = logging.getLogger('control.room')

router = APIRouter()


# ============================================================================
# Module-level helpers
# ============================================================================

# _build_advanced_filter_clauses lives in db.py (shared across systems, regions, galaxies)
from db import _build_advanced_filter_clauses, archived_civ_filter, norm_token


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
    galaxy: str = None,
    focus_civ: str = None,
    focus_user: str = None,
):
    """Get pre-aggregated region data for the 3D galaxy map.

    Args:
        reality: Optional filter - 'Normal' or 'Permadeath' (None for all)
        galaxy: Optional filter - galaxy name like 'Euclid' (None for all)
        focus_civ: Mark regions where this discord_tag has systems with
            is_focused=True. Does NOT filter — the full region list is still
            returned so the map can offer a "show all regions" toggle that
            doesn't require a re-fetch.
        focus_user: Same shape as focus_civ but matches against
            discovered_by / personal_discord_username (the contributor on
            the row). Useful for "View on Map" from a contributor search hit.

    Returns one data point per region with:
    - Region coordinates (region_x, region_y, region_z)
    - Display coordinates (x, y, z) from the first system
    - System count
    - Custom region name if set
    - List of galaxies present
    - is_focused: bool — true when the region contains systems matching
      focus_civ / focus_user, false otherwise. Always present.

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

        # Hide systems from archived civilizations (public endpoint)
        where_clauses.append(archived_civ_filter('s'))

        where_sql = " AND ".join(where_clauses)

        # Pre-compute the set of focused region coord tuples so the per-row
        # is_focused flag is an O(1) lookup. Done as a second query to keep
        # the aggregated query simple — the focused-region count is always
        # small (one civ's territory, or one user's submissions).
        focused_keys = set()
        if focus_civ:
            cursor.execute(
                "SELECT DISTINCT region_x, region_y, region_z "
                "FROM systems "
                "WHERE region_x IS NOT NULL AND region_y IS NOT NULL AND region_z IS NOT NULL "
                "AND discord_tag = ? COLLATE NOCASE",
                (focus_civ,)
            )
            focused_keys = {(r['region_x'], r['region_y'], r['region_z']) for r in cursor.fetchall()}
        elif focus_user:
            # Match contributor by either column. Case-insensitive — the
            # leaderboard normalizes harder (strips discriminators) but for
            # map focus a simple NOCASE compare is the right precision.
            cursor.execute(
                "SELECT DISTINCT region_x, region_y, region_z "
                "FROM systems "
                "WHERE region_x IS NOT NULL AND region_y IS NOT NULL AND region_z IS NOT NULL "
                "AND (discovered_by = ? COLLATE NOCASE OR personal_discord_username = ? COLLATE NOCASE)",
                (focus_user, focus_user)
            )
            focused_keys = {(r['region_x'], r['region_y'], r['region_z']) for r in cursor.fetchall()}

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
            # v1.68.0 — focus flag. False when no focus_* param is set, so the
            # client can rely on the field always being present.
            region['is_focused'] = (
                (region['region_x'], region['region_y'], region['region_z']) in focused_keys
                if (focus_civ or focus_user) else False
            )
            regions.append(region)

        return {
            'regions': regions,
            'total_systems': total_systems,
            'total_regions': len(regions),
            'focus_active': bool(focus_civ or focus_user),
            'focus_civ': focus_civ,
            'focus_user': focus_user,
        }

    except Exception as e:
        logger.error(f"Map aggregation error: {e}")
        return {'regions': [], 'total_systems': 0, 'total_regions': 0}
    finally:
        if conn:
            conn.close()


# ============================================================================
# Map snapshot — single bulk bundle for the Cartographer v10 galaxy map
# ============================================================================

# In-memory cache for the built snapshot. Keyed on (reality, galaxy, token)
# where token = systems row count + newest modified_at, so any approval/edit
# invalidates it on the next request without a manual bust. v1 cache per the
# integration dispatch — see docs/cartographer-integration-notes.md.
_SNAPSHOT_CACHE: dict = {}


def _spread_star(rx: int, ry: int, rz: int, sss: int) -> tuple:
    """Deterministic intra-region spread — mirrors glyph_decoder.calculate_star_position_in_region.

    Systems within the same NMS region share identical (x, y, z) glyph coordinates.
    The SSS (solar system index) has no spatial meaning, so we hash it against the
    region address to spread systems WITHIN their own voxel.

    TRUE SCALE: world unit = 1 region voxel (= ~400 ly in NMS). A region is a
    single 400 ly cube, so its systems must stay inside ±0.5 voxel — otherwise
    they smear across neighbouring regions and destroy all spatial locality.
    (The previous ±64-voxel spread was ~128× too large: it scattered one
    region's systems across ~25,600 ly of space.) We use ±0.45 so stars fill
    the voxel without sitting exactly on its faces.
    """
    h = hashlib.sha256(f"NMS:{rx}:{ry}:{rz}:{sss}".encode()).digest()
    ox = (int.from_bytes(h[0:4], 'big') / 0xFFFFFFFF - 0.5) * 0.9
    oy = (int.from_bytes(h[4:8], 'big') / 0xFFFFFFFF - 0.5) * 0.9
    oz = (int.from_bytes(h[8:12], 'big') / 0xFFFFFFFF - 0.5) * 0.9
    bx = rx if rx <= 0x7FF else rx - 0x1000
    by = ry if ry <= 0x7F  else ry - 0x100
    bz = rz if rz <= 0x7FF else rz - 0x1000
    return bx + ox, by + oy, bz + oz


# Canonical star-type order — matches the mockup's `star_types` pool and the
# in-page legend / shader palette. NULL or unmapped star types fall into an
# 'Unknown' bucket appended on demand so unscanned systems still render.
_STAR_TYPE_ORDER = ['Yellow', 'Red', 'Green', 'Blue', 'Purple']

# Canonical planet-size order, pre-seeded so common sizes get low stable indices
# (mockup pool was ['', 'Small', 'Medium', 'Large']).
_SIZE_ORDER = ['Small', 'Medium', 'Large', 'Giant', 'Moon']


@router.get('/api/map/snapshot')
async def api_map_snapshot(reality: str = None, galaxy: str = None):
    """Bulk galaxy snapshot for the Cartographer v10 map.

    Replaces the mockup's baked `<script id="snapshot">` blob — the response
    shape matches the mockup's parseSnapshot() exactly, so the only client
    change is `JSON.parse(scriptTag)` -> `fetch('/api/map/snapshot')`.

    Public, no auth — matches the existing /map/latest + /api/map/regions-aggregated
    surface. Per-system hot data is base64-packed little-endian typed arrays;
    categorical fields are string pools indexed by Uint8/Uint16 arrays; the
    detail panel reads a sparse planets_by_idx. Optional reality/galaxy filters
    mirror /api/map/regions-aggregated.

    Field contract documented in docs/cartographer-integration-notes.md.
    """
    import numpy as np

    # Empty-DB envelope keeps the shape stable so parseSnapshot() never NPEs.
    empty = {
        'n': 0, 'pos': '', 'st': '', 'ti': '', 'hp': '', 'hs': '', 'ri': '',
        'rpos': '', 'rcount': '', 'rn': 0, 'galaxies': [], 'regions': [], 'names': [],
        'glyphs': [], 'star_types': list(_STAR_TYPE_ORDER), 'tag_pool': [''],
        'tag_colors': {}, 'biomes': [''], 'sizes': [''], 'sentinel': [''],
        'planets_by_idx': {},
    }

    conn = None
    try:
        db_path = get_db_path()
        if not db_path.exists():
            return empty

        conn = get_db_connection()
        cursor = conn.cursor()

        # --- Cache token: row count + newest write. Cheap, index-friendly. ---
        cursor.execute("SELECT COUNT(*), COALESCE(MAX(modified_at), '') FROM systems")
        meta = cursor.fetchone()
        token = f"{meta[0]}::{meta[1]}"
        cache_key = (reality or '', galaxy or '', token)
        if cache_key in _SNAPSHOT_CACHE:
            # Cached value is the already-serialized JSON string, so a warm hit
            # skips both the DB build and re-serialization of a ~2 MB payload.
            return Response(content=_SNAPSHOT_CACHE[cache_key],
                            media_type='application/json')

        # --- Optional reality/galaxy scope (same filters as regions-aggregated) ---
        where = ["s.x IS NOT NULL AND s.y IS NOT NULL AND s.z IS NOT NULL"]
        params = []
        if reality:
            where.append("s.reality = ?")
            params.append(reality)
        if galaxy:
            where.append("s.galaxy = ?")
            params.append(galaxy)
        where.append(archived_civ_filter('s'))
        where.append("s.glyph_code IS NOT NULL AND LENGTH(s.glyph_code) = 12")
        where_sql = " AND ".join(where)

        # --- Systems in stable id order. The row position IS the snapshot
        #     index that every per-system array and planets_by_idx key uses. ---
        cursor.execute(f"""
            SELECT s.id,
                   COALESCE(NULLIF(TRIM(s.name), ''),
                            NULLIF(TRIM(s.description), ''),
                            'System ' || s.glyph_code) AS name,
                   s.x, s.y, s.z, s.star_type, s.discord_tag,
                   s.glyph_code, s.region_x, s.region_y, s.region_z
            FROM systems s
            WHERE {where_sql}
            ORDER BY s.id
        """, params)
        systems = cursor.fetchall()
        n = len(systems)
        if n == 0:
            return empty

        # --- hasPlanets / hasStation as set lookups (one query each, not n) ---
        cursor.execute("SELECT DISTINCT system_id FROM planets")
        planet_systems = {r[0] for r in cursor.fetchall()}
        cursor.execute("SELECT DISTINCT system_id FROM space_stations")
        station_systems = {r[0] for r in cursor.fetchall()}

        # --- Per-system arrays + categorical pools (built while walking rows) ---
        star_index = {name: i for i, name in enumerate(_STAR_TYPE_ORDER)}
        star_types = list(_STAR_TYPE_ORDER)
        unknown_star_idx = None
        tag_index = {'': 0}   # '' = untagged, index 0 (matches mockup pool)
        tag_pool = ['']

        positions = np.empty(n * 3, dtype='<f4')  # little-endian f32, JS-compatible
        st = np.zeros(n, dtype=np.uint8)
        ti = np.zeros(n, dtype=np.uint8)
        hp = np.zeros(n, dtype=np.uint8)
        hs = np.zeros(n, dtype=np.uint8)
        names = []
        glyphs = []
        id_to_idx = {}
        # Per-system region voxel key, captured in row order so we can emit a
        # per-system region index (ri) once the region pool below is built. The
        # Cartographer uses this to derive which regions contain a filter match.
        sys_region_keys = []

        for i, s in enumerate(systems):
            sid = s['id']
            id_to_idx[sid] = i
            glyph = s['glyph_code'] or ''
            rx = s['region_x']
            sys_region_keys.append((s['region_x'], s['region_y'], s['region_z']))
            if len(glyph) == 12 and rx is not None:
                # Spread systems within their region using the same deterministic
                # hash as glyph_decoder.calculate_star_position_in_region so every
                # system has a unique visible position when the camera zooms in.
                sss = int(glyph[1:4], 16)
                px, py, pz = _spread_star(rx, s['region_y'] or 0, s['region_z'] or 0, sss)
            else:
                px, py, pz = (s['x'] or 0.0), (s['y'] or 0.0), (s['z'] or 0.0)
            positions[i * 3]     = px
            positions[i * 3 + 1] = py
            positions[i * 3 + 2] = pz

            stype = s['star_type']
            if stype in star_index:
                st[i] = star_index[stype]
            else:
                # NULL / unmapped star type -> lazily-created 'Unknown' bucket
                if unknown_star_idx is None:
                    unknown_star_idx = len(star_types)
                    star_types.append('Unknown')
                st[i] = unknown_star_idx

            tag = s['discord_tag'] or ''
            if tag not in tag_index:
                tag_index[tag] = len(tag_pool)
                tag_pool.append(tag)
            ti[i] = tag_index[tag]

            hp[i] = 1 if sid in planet_systems else 0
            hs[i] = 1 if sid in station_systems else 0
            names.append(s['name'] or '(unnamed)')
            glyphs.append(s['glyph_code'] or '')

        # --- planets_by_idx + biome / size / sentinel pools ---
        biome_index = {'': 0}
        biomes = ['']
        size_index = {'': 0}
        sizes = ['']
        sent_index = {'': 0}
        sentinel = ['']

        def pool_idx(value, index_map, pool):
            """Intern a categorical string into its pool, returning its index."""
            v = value or ''
            if v not in index_map:
                index_map[v] = len(pool)
                pool.append(v)
            return index_map[v]

        # Pre-seed sizes so common values keep low, stable indices.
        for sz in _SIZE_ORDER:
            pool_idx(sz, size_index, sizes)

        # Single LEFT JOIN + GROUP BY for moon counts — avoids one correlated
        # subquery per planet row (~30k) which is slow on the Pi's SD-card I/O.
        cursor.execute("""
            SELECT p.id, p.system_id, p.name, p.biome, p.planet_size,
                   p.sentinel_level, p.planet_index, p.is_moon,
                   p.has_rings, p.is_gas_giant, p.water_world, p.is_bubble,
                   p.is_floating_islands, p.is_dissonant, p.is_infested,
                   p.extreme_weather,
                   COUNT(m.id) AS moon_count
            FROM planets p
            LEFT JOIN moons m ON m.planet_id = p.id
            GROUP BY p.id
            ORDER BY p.system_id, p.planet_index
        """)
        planets_by_idx = {}
        for p in cursor.fetchall():
            idx = id_to_idx.get(p['system_id'])
            if idx is None:
                continue  # planet of a system outside the filtered / archived set
            # Pack special features into the bitfield the mockup decodes.
            flags = 0
            if p['has_rings']:           flags |= 1
            if p['is_gas_giant']:        flags |= 2
            if p['water_world']:         flags |= 4
            if p['is_bubble']:           flags |= 8
            if p['is_floating_islands']: flags |= 16
            if p['is_dissonant']:        flags |= 32
            if p['is_infested']:         flags |= 64
            if p['extreme_weather']:     flags |= 128
            planet_tuple = [
                p['name'] or '',
                pool_idx(p['biome'], biome_index, biomes),
                pool_idx(p['planet_size'], size_index, sizes),
                pool_idx(p['sentinel_level'], sent_index, sentinel),
                flags,
                p['moon_count'] or 0,
                p['planet_index'] or 0,
                1 if p['is_moon'] else 0,
            ]
            planets_by_idx.setdefault(str(idx), []).append(planet_tuple)

        # --- Region aggregation: centroid (avg) position, count, dominant tag,
        #     custom name. Same join shape as /api/map/regions-aggregated. ---
        rwhere = ["s.region_x IS NOT NULL AND s.region_y IS NOT NULL AND s.region_z IS NOT NULL"]
        rparams = []
        if reality:
            rwhere.append("s.reality = ?"); rparams.append(reality)
        if galaxy:
            rwhere.append("s.galaxy = ?"); rparams.append(galaxy)
        rwhere.append(archived_civ_filter('s'))
        rwhere_sql = " AND ".join(rwhere)

        cursor.execute(f"""
            SELECT s.region_x, s.region_y, s.region_z,
                   r.custom_name AS region_name,
                   COUNT(*) AS system_count,
                   AVG(s.x) AS cx, AVG(s.y) AS cy, AVG(s.z) AS cz,
                   GROUP_CONCAT(DISTINCT s.discord_tag) AS tags
            FROM systems s
            LEFT JOIN regions r ON s.region_x = r.region_x
                AND s.region_y = r.region_y AND s.region_z = r.region_z
                AND COALESCE(s.reality, 'Normal') = COALESCE(r.reality, 'Normal')
                AND COALESCE(s.galaxy, 'Euclid') = COALESCE(r.galaxy, 'Euclid')
            WHERE {rwhere_sql}
            GROUP BY s.region_x, s.region_y, s.region_z
            ORDER BY system_count DESC
        """, rparams)
        region_rows = cursor.fetchall()
        rn = len(region_rows)
        rpos = np.empty(rn * 3, dtype='<f4')
        rcount = np.empty(rn, dtype='<u2')  # little-endian uint16
        regions = []
        for i, r in enumerate(region_rows):
            rpos[i * 3]     = r['cx'] or 0.0
            rpos[i * 3 + 1] = r['cy'] or 0.0
            rpos[i * 3 + 2] = r['cz'] or 0.0
            cnt = r['system_count'] or 0
            rcount[i] = min(cnt, 65535)  # clamp to Uint16 range
            # Dominant tag = first non-null tag in the region (matches the
            # existing regions-aggregated convention).
            dom_tag = None
            if r['tags']:
                for t in r['tags'].split(','):
                    if t and t != 'None':
                        dom_tag = t
                        break
            regions.append({
                'rx': r['region_x'], 'ry': r['region_y'], 'rz': r['region_z'],
                'name': r['region_name'] or '',
                'count': cnt,
                'tag': dom_tag,
            })

        # --- Per-system region index (ri): aligned to the per-system arrays,
        #     valued by position in the `regions` pool above. 65535 = no region
        #     (system with NULL region coords). Lets the Cartographer filter map
        #     a matched system back to its region for region-layer hiding. ---
        region_key_to_idx = {(reg['rx'], reg['ry'], reg['rz']): i
                             for i, reg in enumerate(regions)}
        ri = np.fromiter(
            (region_key_to_idx.get(k, 65535) for k in sys_region_keys),
            dtype='<u2', count=n)

        # --- tag_colors: reuse the canonical /api/discord_tag_colors source so
        #     the map tints match the rest of the site. Lazy import avoids any
        #     module-load circular dependency between route modules. ---
        try:
            from routes.partners import get_discord_tag_colors
            tag_colors = (await get_discord_tag_colors()).get('colors', {})
        except Exception as e:
            logger.warning("snapshot: tag_colors lookup failed: %s", e)
            tag_colors = {}

        # --- Full galaxy list for the map's Galaxy dropdown. Reality-scoped but
        #     NOT galaxy-scoped, so the dropdown keeps every option even when the
        #     snapshot itself is narrowed to one galaxy. ---
        gal_where = ["galaxy IS NOT NULL AND TRIM(galaxy) != ''"]
        gal_params = []
        if reality:
            gal_where.append("COALESCE(reality, 'Normal') = ?")
            gal_params.append(reality)
        cursor.execute(
            f"SELECT DISTINCT galaxy FROM systems WHERE {' AND '.join(gal_where)} ORDER BY galaxy",
            gal_params)
        all_galaxies = [r[0] for r in cursor.fetchall() if r[0]]

        def b64(arr):
            return base64.b64encode(arr.tobytes()).decode('ascii')

        result = {
            'n': n,
            'pos': b64(positions),
            'st': b64(st),
            'ti': b64(ti),
            'hp': b64(hp),
            'hs': b64(hs),
            'ri': b64(ri),
            'rpos': b64(rpos),
            'rcount': b64(rcount),
            'rn': rn,
            'galaxies': all_galaxies,
            'regions': regions,
            'names': names,
            'glyphs': glyphs,
            'star_types': star_types,
            'tag_pool': tag_pool,
            'tag_colors': tag_colors,
            'biomes': biomes,
            'sizes': sizes,
            'sentinel': sentinel,
            'planets_by_idx': planets_by_idx,
        }

        # Serialize once and cache the JSON string (not the dict) so warm hits
        # are a straight byte return. Keep only the most recent few keys so the
        # cache can't grow unbounded across reality/galaxy/token combinations.
        payload = json.dumps(result, ensure_ascii=True)
        _SNAPSHOT_CACHE[cache_key] = payload
        if len(_SNAPSHOT_CACHE) > 6:
            for k in list(_SNAPSHOT_CACHE.keys())[:-6]:
                _SNAPSHOT_CACHE.pop(k, None)
        return Response(content=payload, media_type='application/json')

    except Exception as e:
        logger.error("Map snapshot error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="snapshot build failed")
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
                SUM(CASE WHEN COALESCE(s.is_complete, 0) >= 85 AND COALESCE(s.is_fully_charted, 0) = 1 THEN 1 ELSE 0 END) as grade_splus,
                SUM(CASE WHEN COALESCE(s.is_complete, 0) >= 85 AND COALESCE(s.is_fully_charted, 0) = 0 THEN 1 ELSE 0 END) as grade_s,
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
        cursor.execute(f'''
            SELECT s.id, s.name, s.galaxy, s.glyph_code, s.region_x, s.region_y, s.region_z,
                   s.created_at, s.star_type,
                   (SELECT COUNT(*) FROM planets WHERE system_id = s.id) as planet_count
            FROM systems s
            WHERE {archived_civ_filter('s')}
            ORDER BY s.created_at DESC NULLS LAST, s.id DESC
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


def _decode_glyph_parts(glyph_code: str) -> Optional[dict]:
    """Split a 12-char portal glyph code into its components.

    Layout (MSB-first, 48 bits): P SSS YY ZZZ XXX — planet(4) / solar-system
    index(12) / region_y(8) / region_z(12) / region_x(12). This is the same
    validated packing used by the standalone glyph resolver tool. Returns None
    if the code isn't valid hex.
    """
    try:
        val = int(glyph_code, 16)
    except (ValueError, TypeError):
        return None
    return {
        'planet': (val >> 44) & 0xF,
        'ssi': (val >> 32) & 0xFFF,
        'region_y': (val >> 24) & 0xFF,
        'region_z': (val >> 12) & 0xFFF,
        'region_x': val & 0xFFF,
    }


@router.get('/api/glyph/resolve')
async def api_resolve_glyph_by_name(
    name: str = '',
    galaxy: str = None,
    reality: str = None,
    session: Optional[str] = Cookie(None),
):
    """Resolve an NMS system NAME back to its 12-char portal glyph code.

    The inverse of the namegen: you know a system by name (from a spreadsheet,
    a Discord post, the site) and want the portal glyphs to actually travel
    there in-game. This is the instant, server-side version of the standalone
    glyph resolver's Tier 1 (catalogue) lookup — it matches the name against
    Haven's uploaded systems and returns each match's stored glyph code,
    decoded SSI/region, and a confidence based on how many systems share the
    name (NMS procgen names repeat, so a name can map to several systems).

    Query:
        name: system name to resolve (required, >= 2 chars)
        galaxy: optional galaxy filter, e.g. "Euclid" (disambiguates repeats)
        reality: optional reality filter, "Normal" / "Permadeath"

    Response:
        { query, galaxy, reality, method, confidence, count,
          candidates[], suggestions[] }
        confidence: high (1 glyph) | medium (2-5) | low (>5) | none (0)
        suggestions: fuzzy near-name matches, returned only when count == 0
    """
    name_norm = (name or '').strip()
    empty = {
        'query': name_norm, 'galaxy': galaxy, 'reality': reality,
        'method': 'none', 'confidence': 'none', 'count': 0,
        'candidates': [], 'suggestions': [],
    }
    if len(name_norm) < 2:
        return empty

    session_data = get_session(session)
    is_super = bool(session_data and session_data.get('user_type') == 'super_admin')

    select_cols = (
        "s.id, s.name, s.region_x, s.region_y, s.region_z, "
        "s.galaxy, s.glyph_code, s.discord_tag, s.star_type, s.reality, "
        "s.is_complete, s.is_fully_charted, s.discovered_by, "
        "s.personal_discord_username, r.custom_name as region_name"
    )
    join = ("LEFT JOIN regions r ON s.region_x = r.region_x "
            "AND s.region_y = r.region_y AND s.region_z = r.region_z "
            "AND COALESCE(r.reality, 'Normal') = COALESCE(s.reality, 'Normal') "
            "AND COALESCE(r.galaxy,  'Euclid') = COALESCE(s.galaxy,  'Euclid')")

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # ---- Exact-name match (the authoritative catalogue path) ----------
        where = ["s.name = ? COLLATE NOCASE"]
        params = [name_norm]
        if galaxy:
            where.append("s.galaxy = ? COLLATE NOCASE")
            params.append(galaxy)
        if reality:
            where.append("s.reality = ? COLLATE NOCASE")
            params.append(reality)
        if not is_super:
            where.append(archived_civ_filter('s'))

        cursor.execute(
            f"SELECT {select_cols} FROM systems s {join} "
            f"WHERE {' AND '.join(where)} ORDER BY s.name ASC LIMIT 100",
            params,
        )
        rows = apply_data_restrictions([dict(r) for r in cursor.fetchall()], session_data)

        seen = set()
        candidates = []
        for row in rows:
            gc = (row.get('glyph_code') or '').strip().upper()
            if len(gc) != 12 or gc in seen:
                continue  # skip stubs/legacy rows without a usable glyph + dupes
            seen.add(gc)
            parts = _decode_glyph_parts(gc) or {}
            score = row.get('is_complete', 0) or 0
            candidates.append({
                'id': row.get('id'),
                'name': row.get('name'),
                'glyph_code': gc,
                'galaxy': row.get('galaxy'),
                'reality': row.get('reality'),
                'region_name': row.get('region_name'),
                'region_x': row.get('region_x'),
                'region_y': row.get('region_y'),
                'region_z': row.get('region_z'),
                'ssi': parts.get('ssi'),
                'planet': parts.get('planet'),
                'star_type': row.get('star_type'),
                'discord_tag': row.get('discord_tag'),
                'discovered_by': row.get('discovered_by') or row.get('personal_discord_username'),
                'completeness_grade': score_to_grade(score, bool(row.get('is_fully_charted'))),
            })

        count = len(candidates)
        confidence = ('high' if count == 1 else 'medium' if 2 <= count <= 5
                      else 'low' if count > 5 else 'none')

        # ---- No exact hit -> fuzzy near-name suggestions (not authoritative)
        suggestions = []
        if count == 0:
            sug_where = ["s.name LIKE ? COLLATE NOCASE", "LENGTH(s.glyph_code) = 12"]
            sug_params = [f'%{name_norm}%']
            if galaxy:
                sug_where.append("s.galaxy = ? COLLATE NOCASE")
                sug_params.append(galaxy)
            if reality:
                sug_where.append("s.reality = ? COLLATE NOCASE")
                sug_params.append(reality)
            if not is_super:
                sug_where.append(archived_civ_filter('s'))
            cursor.execute(
                f"SELECT {select_cols} FROM systems s {join} "
                f"WHERE {' AND '.join(sug_where)} "
                f"ORDER BY CASE WHEN LOWER(s.name) LIKE LOWER(?) THEN 0 ELSE 1 END, "
                f"s.name ASC LIMIT 12",
                (*sug_params, f'{name_norm}%'),
            )
            srows = apply_data_restrictions([dict(r) for r in cursor.fetchall()], session_data)
            sseen = set()
            for row in srows:
                gc = (row.get('glyph_code') or '').strip().upper()
                if len(gc) != 12 or gc in sseen:
                    continue
                sseen.add(gc)
                suggestions.append({
                    'id': row.get('id'),
                    'name': row.get('name'),
                    'glyph_code': gc,
                    'galaxy': row.get('galaxy'),
                    'reality': row.get('reality'),
                    'region_name': row.get('region_name'),
                })

        return {
            'query': name_norm,
            'galaxy': galaxy,
            'reality': reality,
            'method': 'catalog' if count else 'none',
            'confidence': confidence,
            'count': count,
            'candidates': candidates,
            'suggestions': suggestions,
        }
    except Exception as e:
        logger.error(f"Error resolving glyph by name: {e}")
        return {**empty, 'error': str(e)}
    finally:
        if conn:
            conn.close()


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

        # Collapse duplicate options that differ only by case, internal spacing,
        # or punctuation ("Power Generation" / "PowerGeneration" / "trading" /
        # "Trading ") into ONE entry, and drop obvious junk (single chars,
        # pure-numeric values like "1"). The dedup key is norm_token() — the very
        # same normalizer the filter WHERE clauses use — so a collapsed option
        # always still matches its rows. Among the variants in a group we surface
        # the best-formatted one (most word breaks, mixed case, then longest).
        def _dedup_clean(values):
            def _score(s):
                return (s.count(' '), 0 if (s.isupper() or s.islower()) else 1, len(s))
            groups = {}
            for v in values:
                if not v or not isinstance(v, str):
                    continue
                disp = ' '.join(v.split())  # trim + collapse internal whitespace runs
                key = norm_token(disp)
                if len(key) < 2 or key.isdigit():
                    continue  # drop single-char / pure-numeric noise ("1")
                cur = groups.get(key)
                if cur is None or _score(disp) > _score(cur):
                    groups[key] = disp
            return sorted(groups.values(), key=lambda s: s.lower())

        # System-level fields
        def get_distinct_system(column):
            cursor.execute(f"SELECT DISTINCT s.{column} FROM systems s {sys_where} ORDER BY s.{column}", sys_params)
            return _dedup_clean(row[0] for row in cursor.fetchall())

        # Planet-level fields
        def get_distinct_planet(column):
            cursor.execute(f"SELECT DISTINCT p.{column} FROM planets p {planet_join} {planet_where} ORDER BY p.{column}", planet_params)
            return _dedup_clean(row[0] for row in cursor.fetchall())

        # Resources come from the planets.materials AND moons.materials lists
        # (the dedicated common/uncommon/rare columns are ~empty). Normalize each
        # cell to canonical names (migration 1.93.0 already did this in the DB;
        # this also covers any not-yet-normalized rows) and keep only tokens that
        # map to a real canonical resource — so the dropdown is the clean set
        # actually present, not the 170-entry typo/case mess. Moons are scanned
        # too so a resource that only occurs on a moon is still listed + filterable.
        def get_distinct_resources():
            from resource_catalog import normalize_materials, CANONICAL_RESOURCES
            canon_by_lower = {r.lower(): r for r in CANONICAL_RESOURCES}
            present = set()

            def _collect(sql):
                cursor.execute(sql, planet_params)
                for row in cursor.fetchall():
                    mats = row[0]
                    if not mats:
                        continue
                    for part in normalize_materials(mats).split(','):
                        key = part.strip().lower()
                        if key in canon_by_lower:
                            present.add(canon_by_lower[key])

            _collect(f"SELECT DISTINCT p.materials FROM planets p {planet_join} {planet_where}")
            _collect(f"SELECT DISTINCT m.materials FROM moons m JOIN planets p ON m.planet_id = p.id {planet_join} {planet_where}")
            return sorted(present)

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

        # Hide systems from archived civilizations for non-super-admins
        if not (session_data and session_data.get('user_type') == 'super_admin'):
            where_clauses.append(archived_civ_filter('s'))

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

        # Fetch systems with pagination.
        # Parker 2026-05-11: include planet_count + moon_count subqueries so
        # the L4 SystemCard text doesn't say "0 planets" when the system_thumb
        # poster correctly shows 4 planets. Both columns are indexed
        # (idx_planets_system_id from v1.32.0) so the subqueries are cheap.
        cursor.execute(f'''
            SELECT s.*, r.custom_name as region_name,
                   (SELECT COUNT(*) FROM planets p
                    WHERE p.system_id = s.id
                      AND COALESCE(p.is_moon, 0) = 0) AS planet_count,
                   (SELECT COUNT(*) FROM moons m
                    WHERE m.planet_id IN (SELECT id FROM planets WHERE system_id = s.id)) AS moon_count
            FROM systems s
            LEFT JOIN regions r ON s.region_x = r.region_x
                AND s.region_y = r.region_y AND s.region_z = r.region_z
                AND COALESCE(r.reality, 'Normal') = COALESCE(s.reality, 'Normal')
                AND COALESCE(r.galaxy,  'Euclid') = COALESCE(s.galaxy,  'Euclid')
            {where_sql}
            ORDER BY s.created_at DESC NULLS LAST, s.id DESC
            LIMIT ? OFFSET ?
        ''', params + [limit, offset])

        systems = [dict(row) for row in cursor.fetchall()]

        # Add completeness grade derived from stored score + fully-charted flag
        # (SELECT s.* above carries is_fully_charted, so S+ surfaces here).
        for sys in systems:
            score = sys.get('is_complete', 0) or 0
            sys['completeness_grade'] = score_to_grade(score, bool(sys.get('is_fully_charted')))
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


# ============================================================================
# Search query parsing helpers
# ============================================================================

# Matches a 12-char glyph (full code) or 11-char suffix (last 11 are the
# galactic-coords portion — the dedup key). Hex digits 0-9 and A-F.
_GLYPH_RE = re.compile(r'^[0-9A-Fa-f]{11,12}$')
# Loose match for NMSPortals share URLs. The live site is
# `nmsportals.github.io` — the historical `.com` was never registered. Also
# accepts the older `.com` form just in case. Pulls a 12-char hex glyph
# from anywhere in the URL (query string, fragment, or path).
_NMSPORTAL_RE = re.compile(
    r'nmsportals?\.(?:github\.io|com)[^\s]*?([0-9A-Fa-f]{12})',
    re.IGNORECASE,
)


def _parse_search_query(raw: str):
    """Normalize a raw user query into a structured search intent.

    Returns a dict with:
      - text: normalized query for LIKE matching (uppercased for glyphs)
      - kind: 'glyph_full' | 'glyph_suffix' | 'nmsportal' | 'free'
      - glyph: 12-char glyph if kind starts with 'glyph_' or 'nmsportal'
      - suffix: last-11-char glyph suffix when relevant

    Cases handled:
      - Bare 12-char hex → exact glyph match
      - Bare 11-char hex → suffix-index match (the dedup key from migration v1.73.0)
      - NMSPortals URL → extract embedded glyph and treat as glyph_full
      - Anything else → free text, falls through to multi-column LIKE
    """
    q = (raw or '').strip()
    if not q:
        return {'text': '', 'kind': 'free'}

    # NMSPortals URL? Pull the glyph out.
    m = _NMSPORTAL_RE.search(q)
    if m:
        glyph = m.group(1).upper()
        return {
            'text': glyph,
            'kind': 'nmsportal',
            'glyph': glyph,
            'suffix': glyph[-11:],
        }

    # Bare hex string?
    if _GLYPH_RE.match(q):
        g = q.upper()
        if len(g) == 12:
            return {'text': g, 'kind': 'glyph_full', 'glyph': g, 'suffix': g[-11:]}
        return {'text': g, 'kind': 'glyph_suffix', 'suffix': g}

    return {'text': q, 'kind': 'free'}


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
    # Scope filters used by SearchOverlay's "scope chip" (Systems Tab v2).
    # Pre-fix these were silently ignored — the chip claimed to scope but the
    # backend returned global results, so users saw irrelevant hits.
    reality: str = None,
    galaxy: str = None,
    rx: int = None,
    ry: int = None,
    rz: int = None,
    session: Optional[str] = Cookie(None)
):
    """Search systems by name, glyph, region name, community tag, or contributor.

    v1.66.0 expansion: the placeholder always promised "name, glyph code,
    contributor, or community" but the backend only searched name + glyph +
    galaxy + description. This now matches reality. Specifically the WHERE
    clause OR-spans:
      - s.name (system name)
      - s.glyph_code (full or partial)
      - s.glyph_code_suffix (when the query is a bare 11-char hex string —
        the indexed dedup key from migration v1.73.0; this is what people
        actually paste when they copy from NMSPortals minus the planet idx)
      - s.galaxy (galaxy name)
      - r.custom_name (named region) — region was already joined for display,
        just unused as a search column pre-1.66.0
      - s.discord_tag (community tag, e.g. "Haven", "GHUB")
      - s.discovered_by + s.personal_discord_username (contributor on the row)
      - EXISTS on system_coauthors.username_normalized (co-credited members
        from Wizard v1 multi-author submissions)

    Each returned row gets a `match_reason` field naming which column drove
    the match, so the UI can render "matched on community" / "matched on
    contributor" chips without re-checking on the frontend.

    Args:
        q: Search query (free text, hex glyph, or NMSPortals URL)
        page: Page number (1-indexed, default 1)
        limit: Max results per page (default 20, max 50)
        star_type..is_complete: Advanced filter parameters (compose with q)
        reality, galaxy, rx/ry/rz: scope chip filters from SearchOverlay
        session: Session cookie for permission checking
    """
    session_data = get_session(session)
    parsed = _parse_search_query(q)
    q_norm = parsed['text']

    # 2-char minimum for free-text queries — a single keystroke shouldn't
    # trigger a 20-row scan of partial matches across name/glyph/galaxy/
    # region/community/contributor. Glyph-shaped queries (always ≥11 hex
    # chars) and nmsportal URLs (always carry a 12-char glyph) bypass this
    # guard since they take the indexed exact-match path. Matches the
    # /api/search popover guard.
    if not q_norm or (parsed['kind'] == 'free' and len(q_norm) < 2):
        return {'results': [], 'total': 0, 'page': 1, 'total_pages': 1, 'query': q_norm}

    limit = max(1, min(limit, 50))
    page = max(1, page)
    offset = (page - 1) * limit

    conn = None
    try:
        db_path = get_db_path()
        if not db_path.exists():
            return {'results': [], 'total': 0, 'query': q}

        conn = get_db_connection()
        cursor = conn.cursor()

        # Build advanced filter clauses (composes AND with the search WHERE)
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

        # Scope-chip clauses (SearchOverlay).
        if reality:
            adv_where_clauses.append("s.reality = ? COLLATE NOCASE")
            adv_params.append(reality)
        if galaxy:
            adv_where_clauses.append("s.galaxy = ? COLLATE NOCASE")
            adv_params.append(galaxy)
        if rx is not None and ry is not None and rz is not None:
            adv_where_clauses.append("s.region_x = ? AND s.region_y = ? AND s.region_z = ?")
            adv_params.extend([rx, ry, rz])

        # Hide systems from archived civilizations for non-super-admins
        if not (session_data and session_data.get('user_type') == 'super_admin'):
            adv_where_clauses.append(archived_civ_filter('s'))

        adv_sql = ""
        if adv_where_clauses:
            adv_sql = " AND " + " AND ".join(adv_where_clauses)

        # Build the search WHERE based on query shape.
        # Glyph-shaped queries take the indexed fast path (exact match on
        # glyph_code or glyph_code_suffix) instead of substring LIKE — this
        # is both faster and avoids spurious matches in description text.
        if parsed['kind'] == 'glyph_full':
            search_where = "(s.glyph_code = ? COLLATE NOCASE OR s.glyph_code_suffix = ?)"
            search_params = [parsed['glyph'], parsed['suffix']]
        elif parsed['kind'] in ('glyph_suffix', 'nmsportal'):
            search_where = "(s.glyph_code_suffix = ? OR s.glyph_code = ? COLLATE NOCASE)"
            # nmsportal also has a full glyph; glyph_suffix only has suffix.
            full_for_match = parsed.get('glyph') or parsed['suffix']
            search_params = [parsed['suffix'], full_for_match]
        else:
            pattern = f'%{q_norm}%'
            search_where = (
                "(s.name LIKE ? COLLATE NOCASE"
                " OR s.glyph_code LIKE ? COLLATE NOCASE"
                " OR s.galaxy LIKE ? COLLATE NOCASE"
                " OR r.custom_name LIKE ? COLLATE NOCASE"
                " OR s.discord_tag LIKE ? COLLATE NOCASE"
                " OR s.discovered_by LIKE ? COLLATE NOCASE"
                " OR s.personal_discord_username LIKE ? COLLATE NOCASE"
                " OR EXISTS (SELECT 1 FROM system_coauthors ca"
                "            WHERE ca.system_id = s.id"
                "              AND (ca.username LIKE ? COLLATE NOCASE"
                "                   OR ca.username_normalized LIKE ? COLLATE NOCASE)))"
            )
            search_params = [pattern] * 9

        # Count total matches
        cursor.execute(
            f"SELECT COUNT(*) FROM systems s "
            f"LEFT JOIN regions r ON s.region_x = r.region_x "
            f"  AND s.region_y = r.region_y AND s.region_z = r.region_z "
            f"  AND COALESCE(r.reality, 'Normal') = COALESCE(s.reality, 'Normal') "
            f"  AND COALESCE(r.galaxy,  'Euclid') = COALESCE(s.galaxy,  'Euclid') "
            f"WHERE {search_where} {adv_sql}",
            (*search_params, *adv_params),
        )
        total = cursor.fetchone()[0]

        # Free-text path uses LOWER(name) priority ordering for relevance.
        # Glyph paths order by exact > suffix > anything else.
        if parsed['kind'] == 'free':
            order_sql = (
                "CASE WHEN LOWER(s.name) = LOWER(?) THEN 0"
                "     WHEN LOWER(s.name) LIKE LOWER(?) THEN 1"
                "     ELSE 2 END, s.name ASC"
            )
            order_params = [q_norm, f'{q_norm}%']
        else:
            order_sql = "s.name ASC"
            order_params = []

        cursor.execute(
            f"SELECT s.id, s.name, s.region_x, s.region_y, s.region_z, "
            f"       s.x, s.y, s.z, s.galaxy, s.glyph_code, s.discord_tag, "
            f"       s.star_type, s.reality, s.is_complete, s.is_fully_charted, "
            f"       s.discovered_by, s.personal_discord_username, "
            f"       r.custom_name as region_name, "
            f"       (SELECT COUNT(*) FROM planets WHERE system_id = s.id) as planet_count "
            f"FROM systems s "
            f"LEFT JOIN regions r ON s.region_x = r.region_x "
            f"  AND s.region_y = r.region_y AND s.region_z = r.region_z "
            f"  AND COALESCE(r.reality, 'Normal') = COALESCE(s.reality, 'Normal') "
            f"  AND COALESCE(r.galaxy,  'Euclid') = COALESCE(s.galaxy,  'Euclid') "
            f"WHERE {search_where} {adv_sql} "
            f"ORDER BY {order_sql} "
            f"LIMIT ? OFFSET ?",
            (*search_params, *adv_params, *order_params, limit, offset),
        )

        rows = [dict(r) for r in cursor.fetchall()]

        # Compute match_reason per row so the UI can render "matched by …"
        # chips without re-checking strings. Order matters: a system can match
        # several columns at once; we report the most user-meaningful one.
        for sys in rows:
            score = sys.get('is_complete', 0) or 0
            sys['completeness_grade'] = score_to_grade(score, bool(sys.get('is_fully_charted')))
            sys['completeness_score'] = score
            sys['match_reason'] = _compute_match_reason(sys, parsed, q_norm)

        results = apply_data_restrictions(rows, session_data)

        total_pages = max(1, (total + limit - 1) // limit)

        return {
            'results': results,
            'total': total,
            'page': page,
            'total_pages': total_pages,
            'query': q,
            'parsed_kind': parsed['kind'],
        }

    except Exception as e:
        logger.error(f"Error searching systems: {e}")
        return {'results': [], 'total': 0, 'query': q, 'error': str(e)}
    finally:
        if conn:
            conn.close()


def _compute_match_reason(sys_row: dict, parsed: dict, q_norm: str) -> Optional[dict]:
    """Decide which column "won" the match for a system row.

    Returns {'kind': 'name'|'glyph'|'region'|'community'|'contributor', 'snippet': str}
    or None for free-text matches on the name (the default — nothing to show).
    """
    if parsed['kind'] != 'free':
        # Glyph match: always show the glyph itself
        return {'kind': 'glyph', 'snippet': sys_row.get('glyph_code') or ''}

    q_low = q_norm.lower()
    name = (sys_row.get('name') or '').lower()
    if q_low in name:
        # Name is the default expectation — no chip needed (saves visual noise)
        return None

    glyph = (sys_row.get('glyph_code') or '').lower()
    if q_low in glyph:
        return {'kind': 'glyph', 'snippet': sys_row.get('glyph_code') or ''}

    region_name = (sys_row.get('region_name') or '').lower()
    if region_name and q_low in region_name:
        return {'kind': 'region', 'snippet': sys_row.get('region_name')}

    discord_tag = (sys_row.get('discord_tag') or '').lower()
    if discord_tag and q_low in discord_tag:
        return {'kind': 'community', 'snippet': sys_row.get('discord_tag')}

    discoverer = sys_row.get('discovered_by') or sys_row.get('personal_discord_username')
    if discoverer and q_low in discoverer.lower():
        return {'kind': 'contributor', 'snippet': discoverer}

    # Match probably came from coauthors EXISTS subquery — we don't have the
    # name on the row, so report a generic chip.
    return {'kind': 'contributor', 'snippet': 'co-author'}


# ============================================================================
# Unified Categorized Search (Systems Tab v2.0 popover backend)
# ============================================================================

@router.get('/api/search')
async def api_unified_search(
    q: str = '',
    limit: int = 6,
    # Scope chips — same shape as /api/systems/search
    reality: str = None,
    galaxy: str = None,
    rx: int = None,
    ry: int = None,
    rz: int = None,
    # Advanced filters (apply to the systems category only — communities,
    # regions, contributors aren't subject to per-system filters)
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
    session: Optional[str] = Cookie(None),
):
    """Categorized search returning communities, regions, contributors, systems.

    Powers the SearchOverlay popover in Systems Tab v2. The popover renders
    up to `limit` results per category (default 6); a separate "View all"
    page hits this same endpoint with a higher limit.

    Each category has its own match logic:
      - Communities: civilizations.tag / display_name LIKE; falls back to
        DISTINCT systems.discord_tag for unregistered tags
      - Regions: regions.custom_name LIKE — scoped by reality+galaxy when set
      - Contributors: user_profiles.username (with normalized variant),
        plus DISTINCT systems.discovered_by / personal_discord_username for
        anonymous (no-profile) submitters
      - Systems: reuses /api/systems/search SQL via parse + same WHERE

    Filters and scope chips apply ONLY to the systems category.
    """
    session_data = get_session(session)
    q_raw = (q or '').strip()
    if len(q_raw) < 2:
        return {
            'query': q_raw,
            'communities': [],
            'regions': [],
            'contributors': [],
            'systems': [],
            'totals': {'communities': 0, 'regions': 0, 'contributors': 0, 'systems': 0},
        }

    parsed = _parse_search_query(q_raw)
    limit = max(1, min(limit, 20))

    conn = None
    try:
        db_path = get_db_path()
        if not db_path.exists():
            return {
                'query': q_raw, 'communities': [], 'regions': [], 'contributors': [],
                'systems': [], 'totals': {'communities': 0, 'regions': 0, 'contributors': 0, 'systems': 0},
            }

        conn = get_db_connection()
        cursor = conn.cursor()
        pattern = f'%{q_raw}%'

        # ---- Communities ---------------------------------------------------
        # Canonical source is civilizations (v1.80.0+); legacy partners had a
        # discord_tag only on systems, so we LEFT JOIN system counts and also
        # surface unregistered tags as a secondary pass so nothing is silently
        # dropped.
        cursor.execute(
            "SELECT c.tag, c.display_name, "
            "       (SELECT COUNT(*) FROM systems s WHERE s.discord_tag = c.tag) AS system_count "
            "FROM civilizations c "
            "WHERE c.is_active = 1 "
            "  AND (c.tag LIKE ? COLLATE NOCASE OR c.display_name LIKE ? COLLATE NOCASE) "
            "ORDER BY system_count DESC, c.display_name ASC "
            "LIMIT ?",
            (pattern, pattern, limit + 1),
        )
        community_rows = [dict(r) for r in cursor.fetchall()]
        known_tags_lower = {(r['tag'] or '').lower() for r in community_rows}

        # Fold in unregistered tags from the systems table only if user query
        # would match them — and only if room remains in the result list.
        if len(community_rows) < limit:
            cursor.execute(
                "SELECT discord_tag AS tag, discord_tag AS display_name, "
                "       COUNT(*) AS system_count "
                "FROM systems "
                "WHERE discord_tag IS NOT NULL AND discord_tag != '' "
                "  AND discord_tag LIKE ? COLLATE NOCASE "
                "GROUP BY discord_tag "
                "ORDER BY system_count DESC "
                "LIMIT ?",
                (pattern, limit + 1),
            )
            for r in cursor.fetchall():
                d = dict(r)
                if (d['tag'] or '').lower() in known_tags_lower:
                    continue
                d['unregistered'] = True
                community_rows.append(d)
                if len(community_rows) >= limit + 1:
                    break

        # ---- Regions -------------------------------------------------------
        # Region scoping: when reality / galaxy are set, only show regions in
        # that subspace. Coords get the system_count so the row is useful even
        # for unnamed-but-matching regions (q could match coords if cast).
        region_where = ["r.custom_name LIKE ? COLLATE NOCASE"]
        region_params = [pattern]
        if reality:
            region_where.append("COALESCE(r.reality, 'Normal') = ?")
            region_params.append(reality)
        if galaxy:
            region_where.append("COALESCE(r.galaxy, 'Euclid') = ?")
            region_params.append(galaxy)
        cursor.execute(
            f"SELECT r.region_x, r.region_y, r.region_z, r.custom_name, "
            f"       COALESCE(r.reality, 'Normal') AS reality, "
            f"       COALESCE(r.galaxy, 'Euclid') AS galaxy, "
            f"       (SELECT COUNT(*) FROM systems s "
            f"        WHERE s.region_x = r.region_x AND s.region_y = r.region_y "
            f"          AND s.region_z = r.region_z) AS system_count "
            f"FROM regions r "
            f"WHERE {' AND '.join(region_where)} "
            f"ORDER BY system_count DESC, r.custom_name ASC "
            f"LIMIT ?",
            (*region_params, limit + 1),
        )
        region_rows = [dict(r) for r in cursor.fetchall()]

        # ---- Contributors --------------------------------------------------
        # Two-source merge: registered profiles (canonical) + anonymous
        # submitter strings on systems. Profile rows include submission count
        # via a correlated subquery so the popover shows real activity.
        cursor.execute(
            "SELECT id, username, username_normalized, "
            "       (SELECT COUNT(*) FROM systems s "
            "        WHERE s.profile_id = u.id) AS system_count "
            "FROM user_profiles u "
            "WHERE u.is_active = 1 "
            "  AND (u.username LIKE ? COLLATE NOCASE "
            "       OR u.username_normalized LIKE ? COLLATE NOCASE) "
            "ORDER BY system_count DESC, u.username ASC "
            "LIMIT ?",
            (pattern, pattern, limit + 1),
        )
        contributor_rows = [
            {**dict(r), 'source': 'profile'} for r in cursor.fetchall()
        ]
        seen_norm = {(r.get('username_normalized') or '').lower() for r in contributor_rows}

        if len(contributor_rows) < limit:
            # Pull DISTINCT anonymous submitter strings from systems for
            # contributors who never registered a profile. These match against
            # a normalized form so "ekimo", "Ekimo", "ekimo#1234" all collapse.
            cursor.execute(
                "SELECT COALESCE(NULLIF(personal_discord_username, ''), discovered_by) AS username, "
                "       COUNT(*) AS system_count "
                "FROM systems "
                "WHERE profile_id IS NULL "
                "  AND (discovered_by LIKE ? COLLATE NOCASE "
                "       OR personal_discord_username LIKE ? COLLATE NOCASE) "
                "  AND COALESCE(NULLIF(personal_discord_username, ''), discovered_by) IS NOT NULL "
                "GROUP BY username "
                "ORDER BY system_count DESC "
                "LIMIT ?",
                (pattern, pattern, limit + 1),
            )
            for r in cursor.fetchall():
                d = dict(r)
                norm = (d.get('username') or '').lower().strip()
                if not norm or norm in seen_norm:
                    continue
                d['source'] = 'anonymous'
                contributor_rows.append(d)
                if len(contributor_rows) >= limit + 1:
                    break

        # ---- Systems -------------------------------------------------------
        # Reuse the same multi-column WHERE the /api/systems/search endpoint
        # uses so a system the user expects to see ("matched contributor=ekimo")
        # appears in BOTH the contributors category AND the systems category.
        adv_where = []
        adv_params = []
        _build_advanced_filter_clauses({
            'star_type': star_type, 'economy_type': economy_type,
            'economy_level': economy_level, 'conflict_level': conflict_level,
            'dominant_lifeform': dominant_lifeform,
            'stellar_classification': stellar_classification,
            'biome': biome, 'weather': weather, 'sentinel_level': sentinel_level,
            'resource': resource, 'has_moons': has_moons,
            'min_planets': min_planets, 'max_planets': max_planets,
            'is_complete': is_complete,
        }, adv_where, adv_params)

        if reality:
            adv_where.append("s.reality = ? COLLATE NOCASE")
            adv_params.append(reality)
        if galaxy:
            adv_where.append("s.galaxy = ? COLLATE NOCASE")
            adv_params.append(galaxy)
        if rx is not None and ry is not None and rz is not None:
            adv_where.append("s.region_x = ? AND s.region_y = ? AND s.region_z = ?")
            adv_params.extend([rx, ry, rz])

        # Hide systems from archived civilizations for non-super-admins
        if not (session_data and session_data.get('user_type') == 'super_admin'):
            adv_where.append(archived_civ_filter('s'))

        adv_sql = (" AND " + " AND ".join(adv_where)) if adv_where else ""

        if parsed['kind'] == 'glyph_full':
            sys_where = "(s.glyph_code = ? COLLATE NOCASE OR s.glyph_code_suffix = ?)"
            sys_params = [parsed['glyph'], parsed['suffix']]
        elif parsed['kind'] in ('glyph_suffix', 'nmsportal'):
            sys_where = "(s.glyph_code_suffix = ? OR s.glyph_code = ? COLLATE NOCASE)"
            full_for_match = parsed.get('glyph') or parsed['suffix']
            sys_params = [parsed['suffix'], full_for_match]
        else:
            sys_where = (
                "(s.name LIKE ? COLLATE NOCASE"
                " OR s.glyph_code LIKE ? COLLATE NOCASE"
                " OR s.galaxy LIKE ? COLLATE NOCASE"
                " OR r.custom_name LIKE ? COLLATE NOCASE"
                " OR s.discord_tag LIKE ? COLLATE NOCASE"
                " OR s.discovered_by LIKE ? COLLATE NOCASE"
                " OR s.personal_discord_username LIKE ? COLLATE NOCASE"
                " OR EXISTS (SELECT 1 FROM system_coauthors ca"
                "            WHERE ca.system_id = s.id"
                "              AND (ca.username LIKE ? COLLATE NOCASE"
                "                   OR ca.username_normalized LIKE ? COLLATE NOCASE)))"
            )
            sys_params = [pattern] * 9

        # Count + page in one go (cap+1 trick — we ask for limit+1 to know if
        # the "View all" link should appear, then trim).
        cursor.execute(
            f"SELECT COUNT(*) FROM systems s "
            f"LEFT JOIN regions r ON s.region_x = r.region_x "
            f"  AND s.region_y = r.region_y AND s.region_z = r.region_z "
            f"  AND COALESCE(r.reality, 'Normal') = COALESCE(s.reality, 'Normal') "
            f"  AND COALESCE(r.galaxy,  'Euclid') = COALESCE(s.galaxy,  'Euclid') "
            f"WHERE {sys_where} {adv_sql}",
            (*sys_params, *adv_params),
        )
        system_total = cursor.fetchone()[0]

        if parsed['kind'] == 'free':
            order_sql = (
                "CASE WHEN LOWER(s.name) = LOWER(?) THEN 0"
                "     WHEN LOWER(s.name) LIKE LOWER(?) THEN 1"
                "     ELSE 2 END, s.name ASC"
            )
            order_params = [q_raw, f'{q_raw}%']
        else:
            order_sql = "s.name ASC"
            order_params = []

        cursor.execute(
            f"SELECT s.id, s.name, s.region_x, s.region_y, s.region_z, "
            f"       s.galaxy, s.glyph_code, s.discord_tag, s.star_type, "
            f"       s.reality, s.is_complete, s.is_fully_charted, s.discovered_by, "
            f"       s.personal_discord_username, r.custom_name AS region_name "
            f"FROM systems s "
            f"LEFT JOIN regions r ON s.region_x = r.region_x "
            f"  AND s.region_y = r.region_y AND s.region_z = r.region_z "
            f"  AND COALESCE(r.reality, 'Normal') = COALESCE(s.reality, 'Normal') "
            f"  AND COALESCE(r.galaxy,  'Euclid') = COALESCE(s.galaxy,  'Euclid') "
            f"WHERE {sys_where} {adv_sql} "
            f"ORDER BY {order_sql} "
            f"LIMIT ?",
            (*sys_params, *adv_params, *order_params, limit),
        )
        system_rows = [dict(r) for r in cursor.fetchall()]

        for s in system_rows:
            score = s.get('is_complete', 0) or 0
            s['completeness_grade'] = score_to_grade(score, bool(s.get('is_fully_charted')))
            s['completeness_score'] = score
            s['match_reason'] = _compute_match_reason(s, parsed, q_raw)

        system_rows = apply_data_restrictions(system_rows, session_data)

        # Trim each category to `limit`; totals carry the full count so the
        # UI knows when to show "+N more" / "View all".
        return {
            'query': q_raw,
            'parsed_kind': parsed['kind'],
            'communities': community_rows[:limit],
            'regions': region_rows[:limit],
            'contributors': contributor_rows[:limit],
            'systems': system_rows[:limit],
            'totals': {
                'communities': len(community_rows),  # capped, but >limit means "more available"
                'regions': len(region_rows),
                'contributors': len(contributor_rows),
                'systems': system_total,
            },
        }

    except Exception as e:
        logger.exception(f"Unified search failed: {e}")
        return {
            'query': q_raw, 'communities': [], 'regions': [], 'contributors': [],
            'systems': [], 'totals': {'communities': 0, 'regions': 0, 'contributors': 0, 'systems': 0},
            'error': str(e),
        }
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

            # Hide systems from archived civilizations for non-super-admins
            if not (session_data and session_data.get('user_type') == 'super_admin'):
                where_clauses.append(archived_civ_filter('s'))

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


@router.get('/api/namegen')
async def api_namegen(glyph: str, galaxy: str = 'Euclid'):
    """Generate procedural system and region names from a glyph code and galaxy.

    Public endpoint — used by the Wizard to pre-populate name fields so users
    can verify the procedural name before submitting. Delegates to the shared
    `services.namegen_service` (same logic the extractor + glyph/preview use).

    Returns:
        system_name: Procedural system name
        region_name: Procedural region name
    """
    glyph = (glyph or '').strip().upper()
    if len(glyph) != 12:
        raise HTTPException(status_code=400, detail="glyph must be a 12-character hex string")
    try:
        int(glyph, 16)
    except ValueError:
        raise HTTPException(status_code=400, detail="glyph must be valid hexadecimal")

    system_name, region_name = generate_names(glyph, galaxy)
    if system_name is None:
        # Glyph is valid (checked above), so a None result means the
        # nms_namegen library is unavailable/errored in this build.
        raise HTTPException(status_code=503, detail="Name generation library not available")
    return {'system_name': system_name, 'region_name': region_name}


@router.get('/api/glyph/preview')
async def api_glyph_preview(
    glyph: str,
    galaxy: str = 'Euclid',
    reality: str = 'Normal',
    session: Optional[str] = Cookie(None),
):
    """One-call preview for a glyph: decoded coords + procedural system/region
    names + the region's current naming status.

    Public, no auth. Built so the Keeper Discord bot (and any client) can mirror
    the Wizard's "glyph -> names + region check" flow in a single round-trip
    instead of calling /api/decode_glyph + /api/namegen + /api/regions/... .

    Response:
        {
          "glyph", "galaxy", "reality",
          "decoded": { "planet", "ssi", "region_x", "region_y", "region_z" },
          "system_name", "region_name",          # procedural suggestions (may be null)
          "region_status": {
            "named": bool, "custom_name": str|null,
            "pending": bool, "system_count": int
          }
        }
    """
    glyph = (glyph or '').strip().upper()
    if len(glyph) != 12:
        raise HTTPException(status_code=400, detail="glyph must be a 12-character hex string")
    parts = _decode_glyph_parts(glyph)
    if parts is None:
        raise HTTPException(status_code=400, detail="glyph must be valid hexadecimal")

    reality = normalize_reality(reality)
    galaxy = galaxy or 'Euclid'

    system_name, region_name = generate_names(glyph, galaxy)

    rx, ry, rz = parts['region_x'], parts['region_y'], parts['region_z']
    region_status = {
        'named': False, 'custom_name': None, 'pending': False, 'system_count': 0,
    }
    session_data = get_session(session)
    conn = None
    try:
        db_path = get_db_path()
        if db_path.exists():
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT custom_name FROM regions
                WHERE region_x = ? AND region_y = ? AND region_z = ?
                  AND reality = ? AND galaxy = ?
            ''', (rx, ry, rz, reality, galaxy))
            row = cursor.fetchone()
            custom_name = row['custom_name'] if row else None

            cursor.execute('''
                SELECT id, discord_tag FROM systems
                WHERE region_x = ? AND region_y = ? AND region_z = ?
                  AND reality = ? AND galaxy = ?
            ''', (rx, ry, rz, reality, galaxy))
            systems = [dict(r) for r in cursor.fetchall()]
            visible = apply_data_restrictions(systems, session_data)

            cursor.execute('''
                SELECT 1 FROM pending_region_names
                WHERE region_x = ? AND region_y = ? AND region_z = ?
                  AND reality = ? AND galaxy = ? AND status = 'pending'
                LIMIT 1
            ''', (rx, ry, rz, reality, galaxy))
            pending = cursor.fetchone() is not None

            region_status = {
                'named': custom_name is not None,
                'custom_name': custom_name,
                'pending': pending,
                'system_count': len(visible),
            }
    except Exception as e:
        # Region status is best-effort; never fail the whole preview over it.
        logger.warning(f"glyph preview region lookup failed for {glyph}: {e}")
    finally:
        if conn:
            conn.close()

    return {
        'glyph': glyph,
        'galaxy': galaxy,
        'reality': reality,
        'decoded': {
            'planet': parts['planet'],
            'ssi': parts['ssi'],
            'region_x': rx, 'region_y': ry, 'region_z': rz,
        },
        'system_name': system_name,
        'region_name': region_name,
        'region_status': region_status,
    }


def _region_custom_name(cursor, rx, ry, rz, reality, galaxy):
    """Return a region's approved custom name for these coords, or None. Best-effort."""
    try:
        cursor.execute(
            'SELECT custom_name FROM regions '
            'WHERE region_x = ? AND region_y = ? AND region_z = ? '
            '  AND reality = ? AND galaxy = ?',
            (rx, ry, rz, reality, galaxy),
        )
        row = cursor.fetchone()
        return row['custom_name'] if row else None
    except Exception:
        return None


@router.get('/api/glyph/system')
async def api_glyph_system(
    glyph: str,
    galaxy: str = 'Euclid',
    reality: str = 'Normal',
    session: Optional[str] = Cookie(None),
):
    """Resolve a 12-char portal glyph to the catalogued Haven system + a deep
    link into the 3D cartography system view.

    Public, no auth (systems and the /map/system page are already public). Built
    for the Keeper Discord bot: a user pastes a glyph and gets a link that opens
    that system on the map; if it isn't catalogued, the decoded region + a submit
    link come back instead. Matching uses the canonical last-11 + galaxy + reality
    rule (find_matching_system), so a glyph read while standing on a *different*
    planet of the same system still resolves. URLs are RELATIVE on purpose — the
    caller prefixes the public site URL (never the internal docker host).
    """
    glyph = (glyph or '').strip().upper()
    if len(glyph) != 12:
        raise HTTPException(status_code=400, detail="glyph must be a 12-character hex string")
    parts = _decode_glyph_parts(glyph)
    if parts is None:
        raise HTTPException(status_code=400, detail="glyph must be valid hexadecimal")

    reality = normalize_reality(reality)
    galaxy = galaxy or 'Euclid'
    rx, ry, rz = parts['region_x'], parts['region_y'], parts['region_z']
    decoded = {
        'planet': parts['planet'],
        'ssi': parts['ssi'],
        'region_x': rx, 'region_y': ry, 'region_z': rz,
    }

    session_data = get_session(session)
    conn = None
    try:
        db_path = get_db_path()
        if not db_path.exists():
            raise HTTPException(status_code=503, detail="database unavailable")
        conn = get_db_connection()
        cursor = conn.cursor()

        # 1) Live (approved) system — the happy path.
        approved = find_matching_system(cursor, glyph, galaxy, reality)
        if approved:
            sys_id = approved[0]
            cursor.execute('SELECT id, name, discord_tag FROM systems WHERE id = ?', (sys_id,))
            srow = cursor.fetchone()
            # Honour hidden-from-public / restricted rows for the calling session;
            # if it's not visible to this caller, fall through (never leak a link).
            if srow and apply_data_restrictions([dict(srow)], session_data):
                try:
                    grade = calculate_completeness_score(cursor, sys_id)['grade']
                except Exception:
                    grade = None
                return {
                    'status': 'approved',
                    'system_id': sys_id,
                    'name': srow['name'],
                    'completeness_grade': grade,
                    'galaxy': galaxy,
                    'reality': reality,
                    'region_name': _region_custom_name(cursor, rx, ry, rz, reality, galaxy),
                    'decoded': decoded,
                    'map_url': f'/map/system/{sys_id}',
                    'detail_url': f'/systems/{sys_id}',
                    'cartographer_url': f'/map/latest?focus=system:{sys_id}',
                }

        # 2) Submitted but still in the approval queue (not on the live map yet).
        pending = find_matching_pending_system(cursor, glyph, galaxy, reality)
        if pending:
            return {
                'status': 'pending',
                'submission_id': pending[0],
                'name': pending[1],
                'galaxy': galaxy,
                'reality': reality,
                'region_name': _region_custom_name(cursor, rx, ry, rz, reality, galaxy),
                'decoded': decoded,
            }

        # 3) Not catalogued — hand back the decoded region + a submit link.
        region_name = _region_custom_name(cursor, rx, ry, rz, reality, galaxy)
        cursor.execute(
            'SELECT id, discord_tag FROM systems '
            'WHERE region_x = ? AND region_y = ? AND region_z = ? '
            '  AND reality = ? AND galaxy = ?',
            (rx, ry, rz, reality, galaxy),
        )
        region_systems = apply_data_restrictions([dict(r) for r in cursor.fetchall()], session_data)
        if not region_name:
            try:
                region_name = generate_names(glyph, galaxy)[1]
            except Exception:
                region_name = None
        from urllib.parse import quote
        submit_url = f'/create?glyph={glyph}&galaxy={quote(galaxy)}&reality={quote(reality)}'
        return {
            'status': 'not_found',
            'galaxy': galaxy,
            'reality': reality,
            'region_name': region_name,
            'region_system_count': len(region_systems),
            'decoded': decoded,
            'submit_url': submit_url,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"glyph->system resolve failed for {glyph}: {e}")
        raise HTTPException(status_code=500, detail="glyph resolution failed")
    finally:
        if conn:
            conn.close()


@router.get('/api/option-catalog')
async def api_option_catalog():
    """Canonical curated option lists for system submission.

    Returns the searchable adjective lists (biomes, weather, sentinel, flora,
    fauna, resources, exotic trophies), the system-level enums (star / economy /
    conflict / lifeform / game-mode / reality), planet sizes, and the planet/moon
    boolean attribute definitions.

    SINGLE SOURCE OF TRUTH: served straight from src/data/optionCatalog.json,
    the same file the web wizard reads (via src/data/adjectives.js). Public, no
    auth. Built for the Keeper Discord bot's slash-command autocomplete, but
    usable by any client. Cached in-process; small + static.
    """
    catalog = get_option_catalog()
    if not catalog:
        raise HTTPException(status_code=503, detail="Option catalog unavailable")
    return catalog
