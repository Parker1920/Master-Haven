"""Region endpoints - grouped regions, region CRUD, pending region names, planet/POI endpoints."""

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Cookie, Header, HTTPException, Request
from fastapi.responses import HTMLResponse

from constants import normalize_discord_username, resolve_source
from db import get_db_connection, get_db_path, add_activity_log
from planet_atlas_wrapper import generate_planet_html
from services.auth_service import (
    get_session,
    verify_session,
    require_feature,
    verify_api_key,
)
from services.restrictions import (
    get_restriction_for_system,
    can_bypass_restriction,
    apply_data_restrictions,
)

logger = logging.getLogger('control.room')

router = APIRouter(tags=["regions"])


# ============================================================================
# Region Grouped Endpoint
# ============================================================================

from db import _build_advanced_filter_clauses


@router.get('/api/regions/grouped')
async def api_regions_grouped(include_systems: bool = True, page: int = 0, limit: int = 0,
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
            # Fast path: return just region summaries without nested data
            all_region_coords = [(r['region_x'], r['region_y'], r['region_z']) for r in all_region_rows]
            visible_counts = {}

            if all_region_coords:
                cursor.execute("CREATE TEMP TABLE IF NOT EXISTS _tmp_region_coords (rx INTEGER, ry INTEGER, rz INTEGER)")
                cursor.execute("DELETE FROM _tmp_region_coords")
                cursor.executemany("INSERT INTO _tmp_region_coords VALUES (?, ?, ?)", all_region_coords)

                cursor.execute(f'''
                    SELECT s.id, s.discord_tag, s.region_x, s.region_y, s.region_z FROM systems s
                    INNER JOIN _tmp_region_coords t ON s.region_x = t.rx AND s.region_y = t.ry AND s.region_z = t.rz
                    WHERE 1=1 {combined_filter}
                ''', filter_params)

                all_systems = [dict(row) for row in cursor.fetchall()]
                visible_systems = apply_data_restrictions(all_systems, session_data)

                for system in visible_systems:
                    rx = system.get('region_x')
                    ry = system.get('region_y')
                    rz = system.get('region_z')
                    if rx is not None and ry is not None and rz is not None:
                        key = (rx, ry, rz)
                        visible_counts[key] = visible_counts.get(key, 0) + 1

            true_total_regions = sum(1 for r in all_region_rows if visible_counts.get((r['region_x'], r['region_y'], r['region_z']), 0) > 0)

            if limit > 0:
                offset = page * limit
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

                region['system_count'] = visible_counts.get((rx, ry, rz), 0)
                region['systems'] = []
                regions.append(region)

            return {
                'regions': regions,
                'total_regions': true_total_regions,
                'applied_filter': discord_tag or 'all',
                'reality': reality,
                'galaxy': galaxy
            }

        # STEP 2: Load all systems for all regions in ONE query (include_systems=True path)
        total_regions = len(all_region_rows)
        if limit > 0:
            offset = page * limit
            paginated_region_rows = all_region_rows[offset:offset + limit]
        else:
            paginated_region_rows = all_region_rows

        region_coords = [(r['region_x'], r['region_y'], r['region_z']) for r in paginated_region_rows]
        if not region_coords:
            return {'regions': [], 'total_regions': 0}

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
async def api_region_systems(rx: int, ry: int, rz: int, page: int = 1, limit: int = 50,
                              include_planets: bool = False, session: Optional[str] = Cookie(None)):
    """Get paginated systems for a specific region (lazy-loading endpoint)."""
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

        cursor.execute('''
            SELECT * FROM systems
            WHERE region_x = ? AND region_y = ? AND region_z = ?
            ORDER BY created_at ASC NULLS FIRST, id ASC
        ''', (rx, ry, rz))

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
    """Update/set custom region name. Admin only. Scoped by reality+galaxy."""
    if not verify_session(session):
        raise HTTPException(status_code=401, detail='Admin authentication required')

    custom_name = payload.get('custom_name', '').strip()
    if not custom_name:
        raise HTTPException(status_code=400, detail='Custom name is required')

    reality = payload.get('reality', 'Normal')
    galaxy = payload.get('galaxy', 'Euclid')

    conn = None
    try:
        db_path = get_db_path()
        if not db_path.exists():
            raise HTTPException(status_code=500, detail='Database not initialized')

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT region_x, region_y, region_z FROM regions
            WHERE custom_name = ? AND NOT (region_x = ? AND region_y = ? AND region_z = ?
              AND reality = ? AND galaxy = ?)
        ''', (custom_name, rx, ry, rz, reality, galaxy))
        existing = cursor.fetchone()
        if existing:
            raise HTTPException(
                status_code=409,
                detail=f'Region name "{custom_name}" is already used by region [{existing["region_x"]}, {existing["region_y"]}, {existing["region_z"]}]'
            )

        cursor.execute('''
            INSERT INTO regions (region_x, region_y, region_z, custom_name, reality, galaxy, source, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, 'manual', CURRENT_TIMESTAMP)
            ON CONFLICT(reality, galaxy, region_x, region_y, region_z)
            DO UPDATE SET custom_name = excluded.custom_name, updated_at = CURRENT_TIMESTAMP
        ''', (rx, ry, rz, custom_name, reality, galaxy))

        conn.commit()

        return {'status': 'ok', 'region_x': rx, 'region_y': ry, 'region_z': rz, 'custom_name': custom_name}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating region: {e}")
        logger.exception("Internal server error")
        raise HTTPException(status_code=500, detail="Internal server error")
    finally:
        if conn:
            conn.close()


@router.delete('/api/regions/{rx}/{ry}/{rz}/name')
async def api_delete_region_name(rx: int, ry: int, rz: int, session: Optional[str] = Cookie(None)):
    """Remove custom region name. Admin only."""
    if not verify_session(session):
        raise HTTPException(status_code=401, detail='Admin authentication required')

    conn = None
    try:
        db_path = get_db_path()
        if not db_path.exists():
            return {'status': 'ok', 'message': 'No region name to delete'}

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('DELETE FROM regions WHERE region_x = ? AND region_y = ? AND region_z = ?', (rx, ry, rz))
        conn.commit()

        return {'status': 'ok', 'region_x': rx, 'region_y': ry, 'region_z': rz, 'message': 'Region name removed'}
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
    reality = payload.get('reality', 'Normal')
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

        cursor.execute('SELECT region_x, region_y, region_z FROM regions WHERE custom_name = ?', (proposed_name,))
        existing = cursor.fetchone()
        if existing:
            raise HTTPException(
                status_code=409,
                detail=f'Region name "{proposed_name}" is already used by region [{existing["region_x"]}, {existing["region_y"]}, {existing["region_z"]}]'
            )

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
            SELECT region_x, region_y, region_z FROM pending_region_names
            WHERE proposed_name = ? AND status = 'pending'
        ''', (proposed_name,))
        pending_same_name = cursor.fetchone()
        if pending_same_name:
            raise HTTPException(
                status_code=409,
                detail=f'Region name "{proposed_name}" is already pending approval for another region'
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

        if is_super:
            cursor.execute(f'SELECT {select_cols} FROM pending_region_names {order_clause}')
        elif is_haven_sub_admin:
            additional_tags = session_data.get('additional_discord_tags', [])
            can_approve_personal = session_data.get('can_approve_personal_uploads', False)
            all_tags = ['Haven'] + additional_tags
            placeholders = ','.join(['?' for _ in all_tags])

            if can_approve_personal:
                cursor.execute(f'''
                    SELECT {select_cols} FROM pending_region_names
                    WHERE discord_tag IN ({placeholders})
                       OR discord_tag = 'personal'
                       OR discord_tag IS NULL
                    {order_clause}
                ''', all_tags)
            else:
                cursor.execute(f'''
                    SELECT {select_cols} FROM pending_region_names
                    WHERE discord_tag IN ({placeholders})
                       OR discord_tag IS NULL
                    {order_clause}
                ''', all_tags)
        else:
            cursor.execute(f'''
                SELECT {select_cols} FROM pending_region_names
                WHERE discord_tag = ?
                {order_clause}
            ''', (partner_tag,))

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
async def api_approve_region_name(submission_id: int, session: Optional[str] = Cookie(None)):
    """Approve a pending region name submission. Admin only."""
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

        cursor.execute('SELECT id FROM regions WHERE custom_name = ?', (proposed_name,))
        if cursor.fetchone():
            cursor.execute('''
                UPDATE pending_region_names
                SET status = 'rejected', review_date = ?, review_notes = ?
                WHERE id = ?
            ''', (datetime.now(timezone.utc).isoformat(), 'Name already taken by another region', submission_id))
            conn.commit()
            raise HTTPException(status_code=409, detail='Region name was already taken by another region')

        reality = submission.get('reality') or 'Normal'
        galaxy = submission.get('galaxy') or 'Euclid'
        cursor.execute('''
            INSERT INTO regions (region_x, region_y, region_z, custom_name, reality, galaxy, source, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(reality, galaxy, region_x, region_y, region_z)
            DO UPDATE SET custom_name = excluded.custom_name, source = excluded.source, updated_at = CURRENT_TIMESTAMP
        ''', (rx, ry, rz, proposed_name, reality, galaxy, submission.get('source') or 'manual'))

        cursor.execute('''
            UPDATE pending_region_names
            SET status = 'approved', review_date = ?, reviewed_by = 'admin'
            WHERE id = ?
        ''', (datetime.now(timezone.utc).isoformat(), submission_id))

        conn.commit()

        add_activity_log(
            'region_approved',
            f"Region name '{proposed_name}' approved",
            details=f"Region: [{rx}, {ry}, {rz}]",
            user_name='Admin'
        )

        # Audit log
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
            conn.commit()
        except Exception as audit_err:
            logger.warning(f"Failed to add region audit log: {audit_err}")

        # Invalidate atlas cache for the affected galaxy so the next
        # request renders with the freshly-named region.
        try:
            from services.poster_service import invalidate
            invalidate('atlas', galaxy)
            invalidate('atlas_thumb', galaxy)
        except Exception as inv_err:
            logger.warning(f"Atlas invalidation failed (non-fatal): {inv_err}")

        return {'status': 'approved', 'region_x': rx, 'region_y': ry, 'region_z': rz, 'custom_name': proposed_name}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error approving region name: {e}")
        logger.exception("Internal server error")
        raise HTTPException(status_code=500, detail="Internal server error")
    finally:
        if conn:
            conn.close()


@router.post('/api/pending_region_names/{submission_id}/reject')
async def api_reject_region_name(submission_id: int, payload: dict = None, session: Optional[str] = Cookie(None)):
    """Reject a pending region name submission. Admin only."""
    if not verify_session(session):
        raise HTTPException(status_code=401, detail='Admin authentication required')
    require_feature(get_session(session), 'approvals')

    review_notes = payload.get('notes', '') if payload else ''

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

                cursor.execute('SELECT id FROM regions WHERE custom_name = ?', (proposed_name,))
                if cursor.fetchone():
                    results['failed'].append({'id': submission_id, 'name': proposed_name, 'error': 'Name already taken'})
                    cursor.execute('''
                        UPDATE pending_region_names SET status = 'rejected', review_date = ?, review_notes = ? WHERE id = ?
                    ''', (datetime.now(timezone.utc).isoformat(), 'Name already taken by another region', submission_id))
                    continue

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
