"""Region endpoints - grouped regions, region CRUD, pending region names, planet/POI endpoints."""

import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Cookie, Header, HTTPException, Request
from fastapi.responses import HTMLResponse

from constants import normalize_discord_username, normalize_reality, resolve_source
from db import get_db_connection, get_db_path, add_activity_log, archived_civ_filter
from planet_atlas_wrapper import generate_planet_html
from services.auth_service import (
    get_session,
    verify_session,
    is_super_admin,
    require_feature,
    verify_api_key,
    normalize_username_for_dedup,
    check_self_submission,
)
from services.civilizations import civ_scope_filter
from services.dispatch import fire_and_forget
from services.restrictions import (
    get_restriction_for_system,
    can_bypass_restriction,
    apply_data_restrictions,
)


async def _invalidate_posters_for_region_change(galaxy: Optional[str], discord_tag: Optional[str] = None):
    """Drop poster cache rows whose data depends on region naming.

    Same set as system approval but no voyager card (region naming isn't
    voyager-keyed). Each invalidate is independent — failures log but don't
    block the others. See docs/centralization/dispatch.md.
    """
    try:
        from services.poster_service import invalidate
    except Exception as e:
        logger.warning(f"Region poster invalidation skipped (import failed): {e}")
        return

    def _try(t, k):
        try:
            invalidate(t, k)
        except Exception as e:
            logger.warning(f"Poster invalidate {t}/{k} failed: {e}")

    _try('landing_og', 'global')
    _try('og_site', 'global')
    if galaxy:
        _try('atlas', galaxy)
        _try('atlas_thumb', galaxy)
        _try('og_atlas', galaxy)
    if discord_tag:
        _try('og_community', discord_tag)

logger = logging.getLogger('control.room')

router = APIRouter(tags=["regions"])


# ============================================================================
# Region Grouped Endpoint
# ============================================================================

from db import _build_advanced_filter_clauses


@router.get('/api/regions/grouped')
async def api_regions_grouped(include_systems: bool = False, page: int = 1, limit: int = 24,
                               discord_tag: str = None,
                               reality: str = None,
                               galaxy: str = None,
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
                               session: Optional[str] = Cookie(None)):
    """Return all regions with their systems grouped together."""
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

        # Advanced filters (system-level and planet-level)
        _build_advanced_filter_clauses({
            'star_type': star_type, 'economy_type': economy_type,
            'economy_level': economy_level, 'conflict_level': conflict_level,
            'dominant_lifeform': dominant_lifeform, 'stellar_classification': stellar_classification,
            'biome': biome, 'weather': weather, 'sentinel_level': sentinel_level,
            'resource': resource, 'has_moons': has_moons,
            'min_planets': min_planets, 'max_planets': max_planets, 'is_complete': is_complete,
        }, filter_clauses, filter_params)

        # Hide systems from archived civilizations for non-super-admins
        if not (session_data and session_data.get('user_type') == 'super_admin'):
            filter_clauses.append(archived_civ_filter('s'))

        # Combine filters
        combined_filter = ""
        if filter_clauses:
            combined_filter = " AND " + " AND ".join(filter_clauses)

        # STEP 1: Get all regions with aggregated counts in a SINGLE query
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
        all_region_rows = list(region_rows)

        regions = []

        if not include_systems:
            # Fast path: return just region summaries without nested data.
            # The SELECT pulls the few extra fields the card footer needs
            # (score for Grade S, submitter for contributor count) so we
            # don't have to make a second pass over the systems table.
            all_region_coords = [(r['region_x'], r['region_y'], r['region_z']) for r in all_region_rows]
            visible_counts = {}
            # Per-region aggregates for grade S count + unique contributor
            # count. Keyed by (rx, ry, rz). Contributors stored as a set
            # so we can len() at response build time.
            grade_s_counts = {}
            contributor_sets = {}

            if all_region_coords:
                cursor.execute("CREATE TEMP TABLE IF NOT EXISTS _tmp_region_coords (rx INTEGER, ry INTEGER, rz INTEGER)")
                cursor.execute("DELETE FROM _tmp_region_coords")
                cursor.executemany("INSERT INTO _tmp_region_coords VALUES (?, ?, ?)", all_region_coords)

                # NOTE: `completeness_score` was renamed/repurposed in v1.34.0
                # — only `is_complete` exists on the systems table now, and
                # it holds the 0-100 score (not the legacy boolean). The
                # downstream Python still calls .get('completeness_score')
                # first as a forward-compat shim; that returns None here and
                # falls through to is_complete cleanly.
                # `submitter_id` is pulled too because a few legacy rows
                # have it set but lack personal_discord_username — without
                # it those contributors would be invisible.
                cursor.execute(f'''
                    SELECT s.id, s.discord_tag, s.region_x, s.region_y, s.region_z,
                           s.is_complete, s.profile_id, s.submitter_id,
                           s.personal_discord_username, s.discovered_by
                    FROM systems s
                    INNER JOIN _tmp_region_coords t ON s.region_x = t.rx AND s.region_y = t.ry AND s.region_z = t.rz
                    WHERE 1=1 {combined_filter}
                ''', filter_params)

                all_systems = [dict(row) for row in cursor.fetchall()]
                visible_systems = apply_data_restrictions(all_systems, session_data)

                # Map system_id → (rx,ry,rz) so we can attribute coauthor
                # rows (which only carry system_id) back to a region.
                system_id_to_key = {}
                visible_system_ids = []
                for system in visible_systems:
                    rx = system.get('region_x')
                    ry = system.get('region_y')
                    rz = system.get('region_z')
                    if rx is None or ry is None or rz is None:
                        continue
                    key = (rx, ry, rz)
                    system_id_to_key[system['id']] = key
                    visible_system_ids.append(system['id'])
                    visible_counts[key] = visible_counts.get(key, 0) + 1
                    # Grade S threshold (services/completeness.py): score >= 85.
                    score = system.get('completeness_score')
                    if score is None:
                        score = system.get('is_complete')
                    if score is not None and score >= 85:
                        grade_s_counts[key] = grade_s_counts.get(key, 0) + 1
                    # Primary submitter — exactly ONE identity per system
                    # row. profile_id is preferred (canonical FK), then a
                    # normalized username from either column. submitter_id
                    # is only used when nothing else is available because
                    # the same person commonly has both profile_id AND a
                    # username on the row — counting all three would
                    # multi-count one person.
                    s = contributor_sets.setdefault(key, set())
                    pid = system.get('profile_id')
                    if pid:
                        s.add(('p', pid))
                    else:
                        norm = (normalize_username_for_dedup(system.get('personal_discord_username') or '')
                                or normalize_username_for_dedup(system.get('discovered_by') or ''))
                        if norm:
                            s.add(('u', norm))
                        elif system.get('submitter_id'):
                            s.add(('s', system['submitter_id']))

                # Co-author rows. Wizard v1 (migration 1.75.0) introduced
                # system_coauthors so multi-member submissions credit the
                # whole crew. Each row already stores a normalized
                # username; profile_id may be NULL for legacy/anon entries.
                if visible_system_ids:
                    placeholders = ','.join(['?'] * len(visible_system_ids))
                    cursor.execute(f'''
                        SELECT system_id, profile_id, username_normalized
                        FROM system_coauthors
                        WHERE system_id IN ({placeholders})
                    ''', visible_system_ids)
                    for ca_row in cursor.fetchall():
                        key = system_id_to_key.get(ca_row['system_id'])
                        if key is None:
                            continue
                        s = contributor_sets.setdefault(key, set())
                        if ca_row['profile_id']:
                            s.add(('p', ca_row['profile_id']))
                        elif ca_row['username_normalized']:
                            s.add(('u', ca_row['username_normalized']))

            true_total_regions = sum(1 for r in all_region_rows if visible_counts.get((r['region_x'], r['region_y'], r['region_z']), 0) > 0)

            visible_region_rows = [r for r in all_region_rows if visible_counts.get((r['region_x'], r['region_y'], r['region_z']), 0) > 0]
            # 1-based pagination. limit=0 is a back-compat sentinel meaning
            # "return everything" — used by callers that want the full list
            # in one shot (CLAUDE.md note: Dashboard still passes its own
            # tiny limit; new callers default to 24).
            if limit > 0:
                page_idx = max(1, page) - 1
                offset = page_idx * limit
                region_rows_paginated = visible_region_rows[offset:offset + limit]
                total_pages_out = max(1, (true_total_regions + limit - 1) // limit) if true_total_regions else 0
                page_out = max(1, page)
            else:
                region_rows_paginated = visible_region_rows
                total_pages_out = 1 if true_total_regions else 0
                page_out = 1

            for region_row in region_rows_paginated:
                region = dict(region_row)
                rx, ry, rz = region['region_x'], region['region_y'], region['region_z']
                key = (rx, ry, rz)

                if region['custom_name']:
                    region['display_name'] = region['custom_name']
                else:
                    region['display_name'] = f"Region ({rx}, {ry}, {rz})"

                region['system_count'] = visible_counts.get(key, 0)
                region['grade_s_count'] = grade_s_counts.get(key, 0)
                region['contributor_count'] = len(contributor_sets.get(key, set()))
                region['systems'] = []
                regions.append(region)

            return {
                'regions': regions,
                'total_regions': true_total_regions,
                'total': true_total_regions,
                'page': page_out,
                'total_pages': total_pages_out,
                'limit': limit,
                'applied_filter': discord_tag or 'all',
                'reality': reality,
                'galaxy': galaxy
            }

        # STEP 2: Load all systems for all regions in ONE query (include_systems=True path)
        total_regions = len(all_region_rows)
        # 1-based pagination, matching the fast path.
        if limit > 0:
            page_idx = max(1, page) - 1
            offset = page_idx * limit
            paginated_region_rows = all_region_rows[offset:offset + limit]
            total_pages_out = max(1, (total_regions + limit - 1) // limit) if total_regions else 0
            page_out = max(1, page)
        else:
            paginated_region_rows = all_region_rows
            total_pages_out = 1 if total_regions else 0
            page_out = 1

        region_coords = [(r['region_x'], r['region_y'], r['region_z']) for r in paginated_region_rows]
        if not region_coords:
            return {
                'regions': [],
                'total_regions': total_regions,
                'total': total_regions,
                'page': page_out,
                'total_pages': total_pages_out,
                'limit': limit,
                'applied_filter': discord_tag or 'all',
                'reality': reality,
                'galaxy': galaxy,
            }

        cursor.execute("CREATE TEMP TABLE IF NOT EXISTS _tmp_region_coords (rx INTEGER, ry INTEGER, rz INTEGER)")
        cursor.execute("DELETE FROM _tmp_region_coords")
        cursor.executemany("INSERT INTO _tmp_region_coords VALUES (?, ?, ?)", region_coords)

        cursor.execute(f'''
            SELECT s.* FROM systems s
            INNER JOIN _tmp_region_coords t ON s.region_x = t.rx AND s.region_y = t.ry AND s.region_z = t.rz
            WHERE 1=1 {combined_filter}
            ORDER BY s.region_x, s.region_y, s.region_z, s.created_at ASC NULLS FIRST, s.id ASC
        ''', filter_params)

        all_systems = [dict(row) for row in cursor.fetchall()]

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

                moons_by_planet = {}
                for moon in all_moons:
                    planet_id = moon['planet_id']
                    if planet_id not in moons_by_planet:
                        moons_by_planet[planet_id] = []
                    moons_by_planet[planet_id].append(moon)

                for planet in all_planets:
                    planet['moons'] = moons_by_planet.get(planet['id'], [])
            else:
                for planet in all_planets:
                    planet['moons'] = []

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

            discoveries_by_system = {}
            for discovery in all_discoveries:
                sys_id = discovery['system_id']
                if sys_id not in discoveries_by_system:
                    discoveries_by_system[sys_id] = []
                discoveries_by_system[sys_id].append(discovery)

            for system in all_systems:
                system['discoveries'] = discoveries_by_system.get(system['id'], [])
        else:
            for system in all_systems:
                system['discoveries'] = []

        # STEP 6: Build final region objects with data restrictions applied
        for region_row in paginated_region_rows:
            region = dict(region_row)
            rx, ry, rz = region['region_x'], region['region_y'], region['region_z']

            region_systems = systems_by_region.get((rx, ry, rz), [])
            region_systems = apply_data_restrictions(region_systems, session_data)

            region['systems'] = region_systems
            region['system_count'] = len(region_systems)

            # Grade-S count and unique-contributor count for the region card
            # footer. Uses the same logic as the fast path so numbers match.
            #   - Grade S: score >= 85 from `is_complete` (v1.34.0 repurposed).
            #   - Contributors: union of primary submitter identities on each
            #     system row + every system_coauthors row for those systems.
            #     Usernames pass through normalize_username_for_dedup so
            #     `turpitzz` and `turpitzz#9999` count as one person.
            grade_s = 0
            contributors = set()
            sys_ids_in_region = []
            for s in region_systems:
                sys_ids_in_region.append(s['id'])
                score = s.get('completeness_score')
                if score is None:
                    score = s.get('is_complete')
                if score is not None and score >= 85:
                    grade_s += 1
                # One identity per system: profile_id preferred, then a
                # normalized username, then submitter_id as last resort.
                # Adding all three would count one person N times.
                pid = s.get('profile_id')
                if pid:
                    contributors.add(('p', pid))
                else:
                    norm = (normalize_username_for_dedup(s.get('personal_discord_username') or '')
                            or normalize_username_for_dedup(s.get('discovered_by') or ''))
                    if norm:
                        contributors.add(('u', norm))
                    elif s.get('submitter_id'):
                        contributors.add(('s', s['submitter_id']))

            # Fold in coauthors for these systems. system_coauthors stores
            # username_normalized directly, so no further normalization.
            if sys_ids_in_region:
                placeholders = ','.join(['?'] * len(sys_ids_in_region))
                cursor.execute(f'''
                    SELECT profile_id, username_normalized
                    FROM system_coauthors
                    WHERE system_id IN ({placeholders})
                ''', sys_ids_in_region)
                for ca_row in cursor.fetchall():
                    if ca_row['profile_id']:
                        contributors.add(('p', ca_row['profile_id']))
                    elif ca_row['username_normalized']:
                        contributors.add(('u', ca_row['username_normalized']))

            region['grade_s_count'] = grade_s
            region['contributor_count'] = len(contributors)

            if region['custom_name']:
                region['display_name'] = region['custom_name']
            else:
                region['display_name'] = f"Region ({rx}, {ry}, {rz})"

            regions.append(region)

        return {
            'regions': regions,
            'total_regions': total_regions,
            'total': total_regions,
            'page': page_out,
            'total_pages': total_pages_out,
            'limit': limit,
            'applied_filter': discord_tag or 'all',
            'reality': reality,
            'galaxy': galaxy
        }

    except Exception as e:
        import traceback
        logger.error(f"Error fetching grouped regions: {e}")
        logger.error(traceback.format_exc())
        logger.exception("Internal server error")
        raise HTTPException(status_code=500, detail="Internal server error")
    finally:
        if conn:
            conn.close()


# ========== REGION NAME MANAGEMENT ENDPOINTS ==========

@router.get('/api/regions')
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
        logger.exception("Internal server error")
        raise HTTPException(status_code=500, detail="Internal server error")
    finally:
        if conn:
            conn.close()


@router.get('/api/regions/{rx}/{ry}/{rz}')
async def api_get_region(rx: int, ry: int, rz: int,
                         reality: str = 'Normal', galaxy: str = 'Euclid',
                         session: Optional[str] = Cookie(None)):
    """Get region info including custom name if set and any pending submissions."""
    session_data = get_session(session)

    conn = None
    try:
        db_path = get_db_path()
        if not db_path.exists():
            return {
                'region_x': rx, 'region_y': ry, 'region_z': rz,
                'reality': reality, 'galaxy': galaxy,
                'custom_name': None, 'system_count': 0, 'pending_name': None
            }

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
        systems = [dict(row) for row in cursor.fetchall()]
        visible_systems = apply_data_restrictions(systems, session_data)
        system_count = len(visible_systems)

        cursor.execute('''
            SELECT proposed_name, submitted_by, submission_date FROM pending_region_names
            WHERE region_x = ? AND region_y = ? AND region_z = ?
              AND reality = ? AND galaxy = ?
              AND status = 'pending'
            ORDER BY submission_date DESC LIMIT 1
        ''', (rx, ry, rz, reality, galaxy))
        pending_row = cursor.fetchone()
        pending_name = dict(pending_row) if pending_row else None

        return {
            'region_x': rx, 'region_y': ry, 'region_z': rz,
            'reality': reality, 'galaxy': galaxy,
            'custom_name': custom_name, 'system_count': system_count,
            'pending_name': pending_name
        }
    except Exception as e:
        logger.error(f"Error getting region: {e}")
        logger.exception("Internal server error")
        raise HTTPException(status_code=500, detail="Internal server error")
    finally:
        if conn:
            conn.close()


@router.get('/api/regions/{rx}/{ry}/{rz}/systems')
async def api_region_systems(
    rx: int, ry: int, rz: int,
    page: int = 1, limit: int = 50,
    include_planets: bool = False,
    reality: Optional[str] = None,
    galaxy: Optional[str] = None,
    session: Optional[str] = Cookie(None),
):
    """Get paginated systems for a specific region (lazy-loading endpoint).

    Reality + galaxy scoping (per regions table 5-key UNIQUE since v1.49.0).
    Pre-fix this endpoint matched only on (rx,ry,rz), mixing systems from
    different galaxies/realities under one region — wrong list for any
    non-Euclid/Normal region. Backwards-compatible: missing params skip
    the WHERE clause (matches old behavior for legacy callers).
    """
    session_data = get_session(session)

    conn = None
    try:
        db_path = get_db_path()
        if not db_path.exists():
            return {'systems': [], 'total': 0, 'page': page, 'limit': limit}

        if limit == 0:
            limit = 500
        else:
            limit = min(limit, 500)

        conn = get_db_connection()
        cursor = conn.cursor()

        where_clauses = ['s.region_x = ?', 's.region_y = ?', 's.region_z = ?']
        params: list = [rx, ry, rz]
        if reality:
            where_clauses.append('COALESCE(s.reality, ?) = ?')
            params.extend(['Normal', normalize_reality(reality)])
        if galaxy:
            where_clauses.append('COALESCE(s.galaxy, ?) = ?')
            params.extend(['Euclid', galaxy])

        # Hide systems from archived civilizations for non-super-admins
        if not (session_data and session_data.get('user_type') == 'super_admin'):
            where_clauses.append(archived_civ_filter('s'))

        where_sql = ' AND '.join(where_clauses)

        cursor.execute(f'''
            SELECT s.* FROM systems s
            WHERE {where_sql}
            ORDER BY s.created_at ASC NULLS FIRST, s.id ASC
        ''', params)

        all_systems = [dict(row) for row in cursor.fetchall()]
        all_systems = apply_data_restrictions(all_systems, session_data)

        total = len(all_systems)
        offset = (page - 1) * limit
        systems = all_systems[offset:offset + limit]

        if include_planets and systems:
            system_ids = [s['id'] for s in systems]
            placeholders = ','.join(['?'] * len(system_ids))

            cursor.execute(f'''
                SELECT * FROM planets WHERE system_id IN ({placeholders}) ORDER BY system_id, name
            ''', system_ids)
            all_planets = [dict(row) for row in cursor.fetchall()]

            planets_by_system = {}
            for planet in all_planets:
                sys_id = planet['system_id']
                if sys_id not in planets_by_system:
                    planets_by_system[sys_id] = []
                planets_by_system[sys_id].append(planet)

            planet_ids = [p['id'] for p in all_planets]
            if planet_ids:
                placeholders = ','.join(['?'] * len(planet_ids))
                cursor.execute(f'''
                    SELECT * FROM moons WHERE planet_id IN ({placeholders}) ORDER BY planet_id, name
                ''', planet_ids)
                all_moons = [dict(row) for row in cursor.fetchall()]

                moons_by_planet = {}
                for moon in all_moons:
                    planet_id = moon['planet_id']
                    if planet_id not in moons_by_planet:
                        moons_by_planet[planet_id] = []
                    moons_by_planet[planet_id].append(moon)

                for planet in all_planets:
                    planet['moons'] = moons_by_planet.get(planet['id'], [])
            else:
                for planet in all_planets:
                    planet['moons'] = []

            for system in systems:
                system['planets'] = planets_by_system.get(system['id'], [])
        else:
            for system in systems:
                system['planets'] = []

        return {
            'systems': systems, 'total': total, 'page': page, 'limit': limit,
            'total_pages': (total + limit - 1) // limit if limit > 0 else 1
        }

    except Exception as e:
        logger.error(f"Error fetching region systems: {e}")
        logger.exception("Internal server error")
        raise HTTPException(status_code=500, detail="Internal server error")
    finally:
        if conn:
            conn.close()


@router.get('/api/systems/{system_id}/planets')
async def api_system_planets(system_id: str, session: Optional[str] = Cookie(None)):
    """Get all planets and moons for a specific system (lazy-loading endpoint)."""
    session_data = get_session(session)

    conn = None
    try:
        db_path = get_db_path()
        if not db_path.exists():
            return {'planets': [], 'system_id': system_id}

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT id, discord_tag FROM systems WHERE id = ?', (system_id,))
        system_row = cursor.fetchone()
        if not system_row:
            return {'planets': [], 'system_id': system_id}

        sys_id = system_row['id']
        system_discord_tag = system_row['discord_tag']

        can_bypass = can_bypass_restriction(session_data, system_discord_tag)
        restriction = get_restriction_for_system(sys_id) if not can_bypass else None

        if restriction and restriction.get('is_hidden_from_public'):
            return {'planets': [], 'system_id': system_id}

        if restriction and 'planets' in restriction.get('hidden_fields', []):
            cursor.execute('SELECT COUNT(*) as count FROM planets WHERE system_id = ?', (system_id,))
            count = cursor.fetchone()['count']
            return {'planets': [], 'system_id': system_id, 'planet_count_only': count}

        cursor.execute('SELECT * FROM planets WHERE system_id = ? ORDER BY name', (system_id,))
        planets = [dict(row) for row in cursor.fetchall()]

        if planets:
            planet_ids = [p['id'] for p in planets]
            placeholders = ','.join(['?'] * len(planet_ids))

            cursor.execute(f'''
                SELECT * FROM moons WHERE planet_id IN ({placeholders}) ORDER BY planet_id, name
            ''', planet_ids)
            all_moons = [dict(row) for row in cursor.fetchall()]

            moons_by_planet = {}
            for moon in all_moons:
                planet_id = moon['planet_id']
                if planet_id not in moons_by_planet:
                    moons_by_planet[planet_id] = []
                moons_by_planet[planet_id].append(moon)

            for planet in planets:
                planet['moons'] = moons_by_planet.get(planet['id'], [])

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
        logger.exception("Internal server error")
        raise HTTPException(status_code=500, detail="Internal server error")
    finally:
        if conn:
            conn.close()


# =============================================================================
# Planet Atlas Integration - POI (Points of Interest) Endpoints
# =============================================================================

@router.get('/api/planets/{planet_id}/pois')
async def api_get_planet_pois(planet_id: int, session: Optional[str] = Cookie(None)):
    """Get all POIs for a specific planet."""
    conn = None
    try:
        db_path = get_db_path()
        if not db_path.exists():
            return {'pois': [], 'planet_id': planet_id}

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT id, name, system_id FROM planets WHERE id = ?', (planet_id,))
        planet = cursor.fetchone()
        if not planet:
            raise HTTPException(status_code=404, detail='Planet not found')

        cursor.execute('SELECT name FROM systems WHERE id = ?', (planet['system_id'],))
        system = cursor.fetchone()

        cursor.execute('SELECT * FROM planet_pois WHERE planet_id = ? ORDER BY created_at DESC', (planet_id,))
        pois = [dict(row) for row in cursor.fetchall()]

        return {
            'pois': pois, 'planet_id': planet_id,
            'planet_name': planet['name'],
            'system_name': system['name'] if system else 'Unknown'
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching planet POIs: {e}")
        logger.exception("Internal server error")
        raise HTTPException(status_code=500, detail="Internal server error")
    finally:
        if conn:
            conn.close()


@router.post('/api/planets/{planet_id}/pois')
async def api_create_planet_poi(planet_id: int, payload: dict, session: Optional[str] = Cookie(None)):
    """Create a new POI on a planet. Any authenticated user."""
    name = payload.get('name', '').strip()
    latitude = payload.get('latitude')
    longitude = payload.get('longitude')

    if not name:
        raise HTTPException(status_code=400, detail='POI name is required')
    if latitude is None or longitude is None:
        raise HTTPException(status_code=400, detail='Latitude and longitude are required')

    try:
        latitude = float(latitude)
        longitude = float(longitude)
        if latitude < -90 or latitude > 90:
            raise HTTPException(status_code=400, detail='Latitude must be between -90 and 90')
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

        cursor.execute('SELECT id FROM planets WHERE id = ?', (planet_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail='Planet not found')

        session_data = get_session(session)
        created_by = session_data.get('username') if session_data else 'anonymous'

        cursor.execute('''
            INSERT INTO planet_pois (planet_id, name, description, latitude, longitude,
                                     poi_type, color, symbol, category, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            planet_id, name, payload.get('description', ''), latitude, longitude,
            payload.get('poi_type', 'custom'), payload.get('color', '#00C2B3'),
            payload.get('symbol', 'circle'), payload.get('category', '-'), created_by
        ))

        poi_id = cursor.lastrowid
        conn.commit()

        cursor.execute('SELECT * FROM planet_pois WHERE id = ?', (poi_id,))
        poi = dict(cursor.fetchone())

        logger.info(f"Created POI '{name}' on planet {planet_id} by {created_by}")
        return {'success': True, 'poi': poi}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating planet POI: {e}")
        logger.exception("Internal server error")
        raise HTTPException(status_code=500, detail="Internal server error")
    finally:
        if conn:
            conn.close()


@router.put('/api/planets/pois/{poi_id}')
async def api_update_planet_poi(poi_id: int, payload: dict, session: Optional[str] = Cookie(None)):
    """Update an existing POI. Partial update - only provided fields are changed."""
    conn = None
    try:
        db_path = get_db_path()
        if not db_path.exists():
            raise HTTPException(status_code=500, detail='Database not initialized')

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM planet_pois WHERE id = ?', (poi_id,))
        existing = cursor.fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail='POI not found')

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
            lon = ((lon + 180) % 360) - 180
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

        cursor.execute(f'UPDATE planet_pois SET {", ".join(updates)} WHERE id = ?', values)
        conn.commit()

        cursor.execute('SELECT * FROM planet_pois WHERE id = ?', (poi_id,))
        poi = dict(cursor.fetchone())

        logger.info(f"Updated POI {poi_id}")
        return {'success': True, 'poi': poi}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating planet POI: {e}")
        logger.exception("Internal server error")
        raise HTTPException(status_code=500, detail="Internal server error")
    finally:
        if conn:
            conn.close()


@router.delete('/api/planets/pois/{poi_id}')
async def api_delete_planet_poi(poi_id: int, session: Optional[str] = Cookie(None)):
    """Delete a POI by ID. Any authenticated user."""
    conn = None
    try:
        db_path = get_db_path()
        if not db_path.exists():
            raise HTTPException(status_code=500, detail='Database not initialized')

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT name FROM planet_pois WHERE id = ?', (poi_id,))
        existing = cursor.fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail='POI not found')

        cursor.execute('DELETE FROM planet_pois WHERE id = ?', (poi_id,))
        conn.commit()

        logger.info(f"Deleted POI {poi_id} ({existing['name']})")
        return {'success': True, 'deleted_id': poi_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting planet POI: {e}")
        logger.exception("Internal server error")
        raise HTTPException(status_code=500, detail="Internal server error")
    finally:
        if conn:
            conn.close()


@router.get('/map/planet/{planet_id}')
async def get_planet_3d_map(planet_id: int, session: Optional[str] = Cookie(None)):
    """Serve the Planet Atlas 3D visualization for a specific planet."""
    conn = None
    try:
        db_path = get_db_path()
        if not db_path.exists():
            raise HTTPException(status_code=500, detail='Database not initialized')

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT p.*, s.name as system_name, s.glyph_code
            FROM planets p
            JOIN systems s ON p.system_id = s.id
            WHERE p.id = ?
        ''', (planet_id,))
        planet_row = cursor.fetchone()

        if not planet_row:
            raise HTTPException(status_code=404, detail='Planet not found')

        planet = dict(planet_row)

        cursor.execute('SELECT * FROM planet_pois WHERE planet_id = ? ORDER BY created_at DESC', (planet_id,))
        pois = [dict(row) for row in cursor.fetchall()]

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
        logger.exception("Internal server error")
        raise HTTPException(status_code=500, detail="Internal server error")
    finally:
        if conn:
            conn.close()


@router.put('/api/regions/{rx}/{ry}/{rz}')
async def api_update_region(rx: int, ry: int, rz: int, payload: dict, session: Optional[str] = Cookie(None)):
    """Update/set custom region name. Super admin only. Scoped by reality+galaxy.

    Direct admin update path (bypasses approval). Was gated on verify_session
    which let any logged-in admin tier through; the audit confirmed only
    super-admins should rename without approval. Poster cache invalidation
    fires after the response — see services/dispatch.py.
    """
    if not is_super_admin(session):
        raise HTTPException(status_code=403, detail='Super admin access required')

    custom_name = payload.get('custom_name', '').strip()
    if not custom_name:
        raise HTTPException(status_code=400, detail='Custom name is required')

    reality = normalize_reality(payload.get('reality'))
    galaxy = payload.get('galaxy', 'Euclid')

    conn = None
    try:
        db_path = get_db_path()
        if not db_path.exists():
            raise HTTPException(status_code=500, detail='Database not initialized')

        conn = get_db_connection()
        cursor = conn.cursor()

        # Region names are NOT globally unique — NMS names repeat across
        # galaxies (the UNIQUE(custom_name) blocker was dropped in migration
        # 1.88.0). The only uniqueness is one row per voxel, enforced by the
        # ON CONFLICT(composite) UPSERT below.
        cursor.execute('''
            INSERT INTO regions (region_x, region_y, region_z, custom_name, reality, galaxy, source, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, 'manual', CURRENT_TIMESTAMP)
            ON CONFLICT(reality, galaxy, region_x, region_y, region_z)
            DO UPDATE SET custom_name = excluded.custom_name, updated_at = CURRENT_TIMESTAMP
        ''', (rx, ry, rz, custom_name, reality, galaxy))

        conn.commit()

        # Poster cache for the affected galaxy + global stats embeds is now stale.
        fire_and_forget(_invalidate_posters_for_region_change, galaxy=galaxy)

        return {'status': 'ok', 'region_x': rx, 'region_y': ry, 'region_z': rz, 'custom_name': custom_name}
    except HTTPException:
        raise
    except Exception as e:
        # Roll back deterministically so a failed write never lingers holding
        # the SQLite write lock (the busy-timeout/"database is locked" risk).
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass
        logger.error(f"Error updating region: {e}")
        logger.exception("Internal server error")
        raise HTTPException(status_code=500, detail="Internal server error")
    finally:
        if conn:
            conn.close()


@router.delete('/api/regions/{rx}/{ry}/{rz}/name')
async def api_delete_region_name(
    rx: int, ry: int, rz: int,
    reality: Optional[str] = None,
    galaxy: Optional[str] = None,
    session: Optional[str] = Cookie(None),
):
    """Remove custom region name. Super admin only. Scoped by reality+galaxy.

    Before: deleted EVERY row matching (rx,ry,rz) regardless of reality/galaxy
    — would nuke Permadeath/Calypso region names when deleting an Euclid one.
    Now requires reality+galaxy query params and scopes the DELETE.
    """
    if not is_super_admin(session):
        raise HTTPException(status_code=403, detail='Super admin access required')

    reality_val = normalize_reality(reality)
    galaxy_val = galaxy or 'Euclid'

    conn = None
    try:
        db_path = get_db_path()
        if not db_path.exists():
            return {'status': 'ok', 'message': 'No region name to delete'}

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            'DELETE FROM regions WHERE region_x = ? AND region_y = ? AND region_z = ? AND reality = ? AND galaxy = ?',
            (rx, ry, rz, reality_val, galaxy_val),
        )
        conn.commit()

        return {'status': 'ok', 'region_x': rx, 'region_y': ry, 'region_z': rz,
                'reality': reality_val, 'galaxy': galaxy_val,
                'message': 'Region name removed'}
    except Exception as e:
        logger.error(f"Error deleting region name: {e}")
        logger.exception("Internal server error")
        raise HTTPException(status_code=500, detail="Internal server error")
    finally:
        if conn:
            conn.close()


@router.post('/api/regions/{rx}/{ry}/{rz}/submit')
async def api_submit_region_name(
    rx: int, ry: int, rz: int,
    payload: dict,
    request: Request,
    x_api_key: Optional[str] = Header(None, alias='X-API-Key'),
):
    """Submit a proposed region name for approval. Public, no auth required.

    Anonymous calls bucket as 'manual'. Authenticated calls (Haven Extractor,
    Keeper bot) bucket via the source resolver so reviewers can see at a
    glance where the proposal came from.
    """
    client_ip = request.client.host if request.client else 'unknown'
    logger.info(f"Region name submission from {client_ip}: region=[{rx},{ry},{rz}], payload={payload}")

    proposed_name = payload.get('proposed_name', '').strip()
    discord_tag = payload.get('discord_tag')
    personal_discord_username = (payload.get('personal_discord_username') or '').strip() or None
    submitted_by = (payload.get('submitted_by') or '').strip() or personal_discord_username or 'anonymous'
    reality = normalize_reality(payload.get('reality'))
    galaxy = payload.get('galaxy', 'Euclid')
    submitter_profile_id = payload.get('submitter_profile_id')

    api_key_info = verify_api_key(x_api_key) if x_api_key else None
    source = resolve_source(api_key_info['name'] if api_key_info else None)

    if not proposed_name:
        logger.warning(f"Region name submission rejected - empty proposed_name. Full payload: {payload}")
        raise HTTPException(status_code=400, detail='Proposed name is required')

    if len(proposed_name) > 50:
        raise HTTPException(status_code=400, detail='Region name must be 50 characters or less')

    client_ip = request.client.host if request.client else 'unknown'

    conn = None
    try:
        db_path = get_db_path()
        if not db_path.exists():
            raise HTTPException(status_code=500, detail='Database not initialized')

        conn = get_db_connection()
        cursor = conn.cursor()

        # Region names are NOT unique — NMS names repeat across galaxies and
        # even at the same voxel in different galaxies (the global
        # UNIQUE(custom_name) was dropped in migration 1.88.0). So we no longer
        # reject a proposal just because the name is used by, or pending for,
        # another region. We DO still keep one pending submission per voxel as
        # queue hygiene (below).
        cursor.execute('''
            SELECT id FROM pending_region_names
            WHERE region_x = ? AND region_y = ? AND region_z = ?
              AND reality = ? AND galaxy = ?
              AND status = 'pending'
        ''', (rx, ry, rz, reality, galaxy))
        pending = cursor.fetchone()
        if pending:
            raise HTTPException(
                status_code=409,
                detail='There is already a pending name submission for this region. Please wait for it to be reviewed.'
            )

        cursor.execute('''
            INSERT INTO pending_region_names
            (region_x, region_y, region_z, proposed_name, submitted_by, submitted_by_ip,
             submission_date, status, discord_tag, personal_discord_username, reality, galaxy,
             submitter_profile_id, source)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?, ?, ?, ?)
        ''', (rx, ry, rz, proposed_name, submitted_by, client_ip,
              datetime.now(timezone.utc).isoformat(), discord_tag, personal_discord_username,
              reality, galaxy, submitter_profile_id, source))

        conn.commit()

        add_activity_log(
            'region_submitted',
            f"Region name '{proposed_name}' submitted for approval",
            details=f"Region: [{rx}, {ry}, {rz}] ({reality}/{galaxy})",
            user_name=submitted_by
        )

        return {
            'status': 'submitted', 'message': 'Region name submitted for approval',
            'region_x': rx, 'region_y': ry, 'region_z': rz, 'proposed_name': proposed_name
        }
    except HTTPException:
        raise
    except Exception as e:
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass
        logger.error(f"Error submitting region name: {e}")
        logger.exception("Internal server error")
        raise HTTPException(status_code=500, detail="Internal server error")
    finally:
        if conn:
            conn.close()


@router.get('/api/pending_region_names')
async def api_list_pending_region_names(session: Optional[str] = Cookie(None)):
    """List pending region name submissions (admin only)."""
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

        select_cols = '''id, region_x, region_y, region_z, proposed_name, submitted_by, submitted_by_ip,
                       submission_date, status, reviewed_by, review_date, review_notes,
                       discord_tag, personal_discord_username'''
        order_clause = """ORDER BY
                    CASE status
                        WHEN 'pending' THEN 1
                        WHEN 'approved' THEN 2
                        WHEN 'rejected' THEN 3
                    END,
                    submission_date DESC"""

        # Single-query scoping via civ_scope_filter (migration 1.80.0).
        # Region-name submissions with NULL discord_tag are visible to any
        # leader-tier user — these are typically untagged Haven region
        # proposals that any member of the broader admin pool reviews.
        scope_clause, scope_params = civ_scope_filter(session_data, column='discord_tag')
        if scope_clause == '1=0':
            pending = []
            rows = []
        else:
            can_approve_personal = bool(
                session_data.get('can_approve_personal_uploads', False)
                or any(m.get('can_approve_personal_uploads')
                       for m in (session_data.get('civ_memberships') or []))
            )
            personal_clause = " OR discord_tag = 'personal'" if can_approve_personal else ''
            # Super admin (1=1) doesn't need the IS NULL branch — they
            # already match everything. Other tiers explicitly include
            # NULL-tag proposals.
            null_clause = "" if scope_clause == '1=1' else " OR discord_tag IS NULL"
            cursor.execute(f'''
                SELECT {select_cols} FROM pending_region_names
                WHERE ({scope_clause}){personal_clause}{null_clause}
                {order_clause}
            ''', scope_params)

        rows = cursor.fetchall()
        pending = [dict(row) for row in rows]

        if is_haven_sub_admin and not is_super:
            for submission in pending:
                submission['personal_discord_username'] = None

        return {'pending': pending, 'count': len(pending)}
    except Exception as e:
        logger.error(f"Error listing pending region names: {e}")
        logger.exception("Internal server error")
        raise HTTPException(status_code=500, detail="Internal server error")
    finally:
        if conn:
            conn.close()


@router.post('/api/pending_region_names/{submission_id}/approve')
async def api_approve_region_name(
    submission_id: int,
    background_tasks: BackgroundTasks,
    session: Optional[str] = Cookie(None),
):
    """Approve a pending region name submission. Admin only.

    Side effects (activity log, broader poster invalidation) fire AFTER the
    response — see services/dispatch.py.
    """
    if not verify_session(session):
        raise HTTPException(status_code=401, detail='Admin authentication required')
    require_feature(get_session(session), 'approvals')

    conn = None
    try:
        db_path = get_db_path()
        if not db_path.exists():
            raise HTTPException(status_code=500, detail='Database not initialized')

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM pending_region_names WHERE id = ? AND status = ?', (submission_id, 'pending'))
        submission = cursor.fetchone()
        if not submission:
            raise HTTPException(status_code=404, detail='Pending submission not found')

        submission = dict(submission)
        rx, ry, rz = submission['region_x'], submission['region_y'], submission['region_z']
        proposed_name = submission['proposed_name']

        # Self-approval prevention — was missing entirely on this endpoint
        # before. A sub-admin could submit a region name and approve it
        # themselves via this per-id route, even though the batch endpoint
        # blocked it. Super admin + partner exemption is in the helper.
        if check_self_submission(submission, get_session(session)):
            raise HTTPException(
                status_code=403,
                detail='You cannot approve your own region name submission'
            )

        reality = submission.get('reality') or 'Normal'
        galaxy = submission.get('galaxy') or 'Euclid'

        # Region names are NOT globally unique — NMS names repeat across
        # galaxies (the UNIQUE(custom_name) blocker was dropped in migration
        # 1.88.0; approving "Muxali Terminus" for Euclid while it already exists
        # in Odyalutai used to 500 here). The only uniqueness is one row per
        # voxel, handled by the ON CONFLICT(composite) UPSERT.
        try:
            cursor.execute('''
                INSERT INTO regions (region_x, region_y, region_z, custom_name, reality, galaxy, source, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(reality, galaxy, region_x, region_y, region_z)
                DO UPDATE SET custom_name = excluded.custom_name, source = excluded.source, updated_at = CURRENT_TIMESTAMP
            ''', (rx, ry, rz, proposed_name, reality, galaxy, submission.get('source') or 'manual'))
        except sqlite3.IntegrityError as ie:
            # Defensive: any residual constraint surfaces as a clean 409, never a
            # 500 with a leaked open transaction.
            conn.rollback()
            logger.warning(f"Region approve INTEGRITY clash for '{proposed_name}': {ie}")
            raise HTTPException(
                status_code=409,
                detail=(f'Region name "{proposed_name}" conflicts with an existing region. '
                        f'Approve under a different name.'))

        cursor.execute('''
            UPDATE pending_region_names
            SET status = 'approved', review_date = ?, reviewed_by = 'admin'
            WHERE id = ?
        ''', (datetime.now(timezone.utc).isoformat(), submission_id))

        # Audit log INSERT stays inline — same connection, same transaction
        # as the regions UPSERT, so partial-failure semantics are preserved.
        try:
            s_data = get_session(session)
            cursor.execute('''
                INSERT INTO approval_audit_log
                (timestamp, action, submission_type, submission_id, submission_name,
                 approver_username, approver_type, approver_account_id, approver_discord_tag,
                 submitter_username, submission_discord_tag, source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                datetime.now(timezone.utc).isoformat(), 'approved', 'region', submission_id,
                proposed_name,
                s_data.get('username', 'admin') if s_data else 'admin',
                s_data.get('user_type', 'super_admin') if s_data else 'super_admin',
                s_data.get('profile_id') if s_data else None,
                s_data.get('discord_tag') if s_data else None,
                submission.get('submitted_by'),
                submission.get('discord_tag'),
                'manual'
            ))
        except Exception as audit_err:
            logger.warning(f"Failed to add region audit log: {audit_err}")

        conn.commit()

        # Side effects fire after the response. Activity log opens its own
        # connection (sync → BackgroundTasks); poster invalidation runs on
        # the event loop (async → fire_and_forget).
        background_tasks.add_task(
            add_activity_log,
            'region_approved',
            f"Region name '{proposed_name}' approved",
            f"Region: [{rx}, {ry}, {rz}]",
            'Admin',
        )

        fire_and_forget(
            _invalidate_posters_for_region_change,
            galaxy=galaxy,
            discord_tag=submission.get('discord_tag'),
        )

        return {'status': 'approved', 'region_x': rx, 'region_y': ry, 'region_z': rz, 'custom_name': proposed_name}
    except HTTPException:
        raise
    except Exception as e:
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass
        logger.error(f"Error approving region name: {e}")
        logger.exception("Internal server error")
        raise HTTPException(status_code=500, detail="Internal server error")
    finally:
        if conn:
            conn.close()


@router.post('/api/pending_region_names/{submission_id}/reject')
async def api_reject_region_name(submission_id: int, payload: dict = None, session: Optional[str] = Cookie(None)):
    """Reject a pending region name submission. Admin only.

    Self-rejection prevention + non-empty reason required (parity with
    /api/reject_systems/batch). Previously sub-admin could reject their own
    submission with no reason.
    """
    if not verify_session(session):
        raise HTTPException(status_code=401, detail='Admin authentication required')
    require_feature(get_session(session), 'approvals')

    review_notes = (payload.get('notes', '') if payload else '').strip()
    if not review_notes:
        raise HTTPException(status_code=400, detail='Rejection reason is required')

    conn = None
    try:
        db_path = get_db_path()
        if not db_path.exists():
            raise HTTPException(status_code=500, detail='Database not initialized')

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM pending_region_names WHERE id = ? AND status = ?', (submission_id, 'pending'))
        submission = cursor.fetchone()
        if not submission:
            raise HTTPException(status_code=404, detail='Pending submission not found')

        submission_dict = dict(submission)
        proposed_name = submission_dict['proposed_name']
        rx, ry, rz = submission_dict['region_x'], submission_dict['region_y'], submission_dict['region_z']

        # Self-rejection prevention — was missing entirely on this endpoint.
        if check_self_submission(submission_dict, get_session(session)):
            raise HTTPException(
                status_code=403,
                detail='You cannot reject your own region name submission'
            )

        cursor.execute('''
            UPDATE pending_region_names
            SET status = 'rejected', review_date = ?, reviewed_by = 'admin', review_notes = ?
            WHERE id = ?
        ''', (datetime.now(timezone.utc).isoformat(), review_notes, submission_id))

        conn.commit()

        s_data = get_session(session)
        add_activity_log(
            'region_rejected',
            f"Region name '{proposed_name}' rejected",
            details=f"Region: [{rx}, {ry}, {rz}]. Reason: {review_notes or 'No reason provided'}",
            user_name=s_data.get('username', 'Admin') if s_data else 'Admin'
        )

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
                proposed_name,
                s_data.get('username', 'admin') if s_data else 'admin',
                s_data.get('user_type', 'super_admin') if s_data else 'super_admin',
                s_data.get('profile_id') if s_data else None,
                s_data.get('discord_tag') if s_data else None,
                submission_dict.get('submitted_by'),
                review_notes,
                submission_dict.get('discord_tag'),
                'manual'
            ))
            conn.commit()
        except Exception as audit_err:
            logger.warning(f"Failed to add region rejection audit log: {audit_err}")

        return {'status': 'rejected', 'submission_id': submission_id, 'message': 'Region name submission rejected'}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error rejecting region name: {e}")
        logger.exception("Internal server error")
        raise HTTPException(status_code=500, detail="Internal server error")
    finally:
        if conn:
            conn.close()


@router.post('/api/approve_region_names/batch')
async def api_batch_approve_region_names(payload: dict, session: Optional[str] = Cookie(None)):
    """Batch approve pending region name submissions. Requires batch_approvals feature."""
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
    if not submission_ids or not isinstance(submission_ids, list):
        raise HTTPException(status_code=400, detail='submission_ids array is required')

    results = {'approved': [], 'failed': [], 'skipped': []}
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
                rx, ry, rz = submission['region_x'], submission['region_y'], submission['region_z']
                proposed_name = submission['proposed_name']
                reality = submission.get('reality') or 'Normal'
                galaxy = submission.get('galaxy') or 'Euclid'

                # Self-submission check
                if not is_super:
                    submitter_profile = submission.get('submitter_profile_id')
                    submitter_username = submission.get('personal_discord_username') or submission.get('submitted_by', '')
                    if approver_profile_id and submitter_profile and approver_profile_id == submitter_profile:
                        results['skipped'].append({'id': submission_id, 'name': proposed_name, 'reason': 'Self-submission'})
                        continue
                    if submitter_username and normalize_discord_username(submitter_username) == normalize_discord_username(approver_username):
                        results['skipped'].append({'id': submission_id, 'name': proposed_name, 'reason': 'Self-submission'})
                        continue

                # Region names are NOT globally unique (UNIQUE(custom_name)
                # dropped in migration 1.88.0) — names repeat across galaxies,
                # so no longer reject a batch item just because the name exists
                # elsewhere. One row per voxel is handled by the UPSERT below.
                cursor.execute('''
                    INSERT INTO regions (region_x, region_y, region_z, custom_name, reality, galaxy, source, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(reality, galaxy, region_x, region_y, region_z)
                    DO UPDATE SET custom_name = excluded.custom_name, source = excluded.source, updated_at = CURRENT_TIMESTAMP
                ''', (rx, ry, rz, proposed_name, reality, galaxy, submission.get('source') or 'manual'))

                cursor.execute('''
                    UPDATE pending_region_names SET status = 'approved', review_date = ?, reviewed_by = ? WHERE id = ?
                ''', (datetime.now(timezone.utc).isoformat(), approver_username, submission_id))

                try:
                    cursor.execute('''
                        INSERT INTO approval_audit_log
                        (timestamp, action, submission_type, submission_id, submission_name,
                         approver_username, approver_type, approver_account_id, approver_discord_tag,
                         submitter_username, submission_discord_tag, source)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        datetime.now(timezone.utc).isoformat(), 'approved', 'region', submission_id,
                        proposed_name, approver_username,
                        session_data.get('user_type', 'super_admin'), approver_profile_id,
                        session_data.get('discord_tag'), submission.get('submitted_by'),
                        submission.get('discord_tag'), 'manual'
                    ))
                except Exception as audit_err:
                    logger.warning(f"Failed to add batch region audit log: {audit_err}")

                results['approved'].append({'id': submission_id, 'name': proposed_name,
                                           'coords': f'[{rx}, {ry}, {rz}]'})

            except Exception as e:
                results['failed'].append({'id': submission_id, 'error': str(e)})

        conn.commit()

        add_activity_log(
            'batch_region_approved',
            f"Batch approved {len(results['approved'])} region names",
            details=f"Approved: {len(results['approved'])}, Failed: {len(results['failed'])}, Skipped: {len(results['skipped'])}",
            user_name=approver_username
        )

        return results
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in batch region approve: {e}")
        logger.exception("Internal server error")
        raise HTTPException(status_code=500, detail="Internal server error")
    finally:
        if conn:
            conn.close()
