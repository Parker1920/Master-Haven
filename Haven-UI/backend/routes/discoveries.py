"""Discovery CRUD, showcase, and approval workflow endpoints."""

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Cookie, Header, HTTPException, Request
from fastapi.responses import JSONResponse

from constants import (
    normalize_discord_username,
    DISCOVERY_TYPE_SLUGS, DISCOVERY_TYPE_INFO, DISCOVERY_TYPE_FIELDS,
    get_discovery_type_slug,
    resolve_source, SOURCE_MANUAL,
    normalize_discovery_coords,
)
from db import get_db_connection, get_db_path, add_activity_log, archived_civ_filter
from services.auth_service import (
    get_session,
    verify_session,
    require_feature,
    check_self_submission,
    verify_api_key,
)
from services.civilizations import civ_scope_filter, user_can_act_for_civ
from services.completeness import update_completeness_score
from services.events import resolve_submission_event_id

logger = logging.getLogger('control.room')

router = APIRouter(tags=["discoveries"])


# Helper: get session from request cookies (used by feature toggle endpoint)
def _get_session_from_request(request: Request):
    """Extract session from request cookies and return session data."""
    session_token = request.cookies.get('session')
    if not session_token:
        return None
    return get_session(session_token)


# =============================================================================
# DISCOVERY CRUD - List, Create, Legacy Redirect
# =============================================================================

@router.get('/api/discoveries')
async def get_discoveries(q: str = '', user_id: str = '', limit: int = 100):
    """List or search discoveries, optionally filtered by user_id"""
    conn = None
    # Cap caller-supplied limit. user_id-filtered branch passes limit straight to SQL.
    if limit > 500:
        limit = 500
    if limit < 1:
        limit = 100
    # Guard short-query LIKE searches: a 1-char `q` becomes `LIKE '%a%'` which scans
    # every row and matches almost everything. Require >=2 chars; treat shorter as no-q.
    q = (q or '').strip()
    if len(q) < 2:
        q = ''
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

            # Import query helper from control_room_api at module level would cause circular imports
            # So we do a simple query here
            conn = get_db_connection()
            cursor = conn.cursor()
            _acf = archived_civ_filter('d')
            if q:
                cursor.execute(f'''
                    SELECT * FROM discoveries d
                    WHERE (discovery_name LIKE ? OR description LIKE ? OR location_name LIKE ?)
                      AND {_acf}
                    ORDER BY d.submission_timestamp DESC LIMIT 200
                ''', (f'%{q}%', f'%{q}%', f'%{q}%'))
            else:
                cursor.execute(f'SELECT * FROM discoveries d WHERE {_acf} ORDER BY d.submission_timestamp DESC LIMIT 200')
            discoveries = [dict(row) for row in cursor.fetchall()]
            return {'results': discoveries}

        return {'results': []}
    except Exception as e:
        logger.exception("Internal server error")
        raise HTTPException(status_code=500, detail="Internal server error")
    finally:
        if conn:
            conn.close()

@router.post('/api/discoveries')
async def create_discovery(
    payload: dict,
    request: Request,
    x_api_key: Optional[str] = Header(None, alias='X-API-Key'),
):
    """Accept a discovery submission.

    Routes into the pending_discoveries approval queue instead of inserting
    directly into the live discoveries table. The bot's existing payload
    shape is preserved (discovered_by → discord_username fallback) and the
    response still contains `discovery_id` aliased to the pending submission
    id so existing clients don't break.

    `source` is resolved from the X-API-Key header so Keeper bot uploads
    are bucketed as 'keeper_bot' and any other authenticated client falls
    into 'haven_extractor'. Anonymous calls bucket as 'manual'.
    """
    conn = None
    try:
        discovery_name = (payload.get('discovery_name') or '').strip() or 'Unnamed Discovery'
        system_id = payload.get('system_id')
        discovery_type = payload.get('discovery_type') or 'Unknown'
        type_slug = get_discovery_type_slug(discovery_type)
        discord_username = (
            payload.get('discord_username')
            or payload.get('discovered_by')
            or 'anonymous'
        )
        discord_tag = payload.get('discord_tag')
        location_name = payload.get('location_name') or 'Unknown Location'
        client_ip = request.client.host if request.client else 'unknown'

        api_key_info = verify_api_key(x_api_key) if x_api_key else None
        source = resolve_source(api_key_info['name'] if api_key_info else None)

        logger.info(
            f"Received discovery submission (routed to approval queue): "
            f"{discovery_type} from {discord_username}"
        )

        conn = get_db_connection()
        cursor = conn.cursor()

        # Duplicate check against both the live table and the pending queue
        cursor.execute(
            '''SELECT id FROM discoveries
               WHERE discovery_name = ? AND system_id = ? AND location_name = ?''',
            (discovery_name, system_id, location_name),
        )
        existing = cursor.fetchone()
        if existing:
            logger.info(
                f"Duplicate discovery rejected: {discovery_name} at "
                f"{location_name} in system {system_id}"
            )
            return JSONResponse({
                'status': 'duplicate',
                'message': f'Discovery "{discovery_name}" at "{location_name}" already exists',
                'existing_id': existing[0],
            }, status_code=409)

        cursor.execute(
            '''SELECT id FROM pending_discoveries
               WHERE discovery_name = ? AND system_id = ? AND status = 'pending' ''',
            (discovery_name, str(system_id) if system_id else None),
        )
        existing_pending = cursor.fetchone()
        if existing_pending:
            return JSONResponse({
                'status': 'duplicate',
                'message': f'Discovery "{discovery_name}" is already awaiting approval',
                'existing_id': existing_pending[0],
            }, status_code=409)

        # Denormalize names for display in approval UI
        system_name = None
        if system_id is not None:
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

        api_location_type = payload.get('location_type') or 'space'
        api_lat, api_lng = normalize_discovery_coords(
            payload.get('latitude'), payload.get('longitude')
        )
        if api_location_type == 'space':
            api_lat, api_lng = None, None
        payload['latitude'] = api_lat
        payload['longitude'] = api_lng

        # Event participation — only honoured if the (bot) client passed an
        # event_id that's a valid, active, in-window discovery event for this
        # community. Almost always None for bot traffic; kept for parity.
        api_event_id = resolve_submission_event_id(
            cursor, payload.get('event_id'), discord_tag, 'discovery'
        )
        payload['event_id'] = api_event_id

        cursor.execute('''
            INSERT INTO pending_discoveries (
                discovery_data, discovery_name, discovery_type, type_slug,
                system_id, system_name, planet_name, moon_name, location_type,
                discord_tag, submitted_by, submitted_by_ip,
                submitter_account_id, submitter_account_type, submitter_profile_id,
                submission_date, photo_url, source, latitude, longitude, event_id, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending')
        ''', (
            json.dumps(payload),
            discovery_name,
            discovery_type,
            type_slug,
            str(system_id) if system_id is not None else None,
            system_name,
            planet_name,
            moon_name,
            api_location_type,
            discord_tag,
            discord_username,
            client_ip,
            None,
            None,
            None,
            datetime.now(timezone.utc).isoformat(),
            payload.get('photo_url'),
            source,
            api_lat,
            api_lng,
            api_event_id,
        ))
        conn.commit()
        submission_id = cursor.lastrowid

        logger.info(
            f"Discovery '{discovery_name}' queued for approval "
            f"(pending id: {submission_id}, source: {source})"
        )
        add_activity_log(
            'discovery_submitted',
            f"Discovery '{discovery_name}' submitted for approval",
            details=f"Type: {discovery_type}, Community: {discord_tag}",
            user_name=discord_username,
        )

        # `discovery_id` kept for backward compat with the Keeper bot's response parsing
        return JSONResponse({
            'status': 'pending',
            'message': 'Discovery submitted for approval!',
            'submission_id': submission_id,
            'discovery_id': submission_id,
        }, status_code=201)

    except Exception as e:
        logger.error(f"Error queueing discovery: {e}")
        logger.exception("Internal server error")
        raise HTTPException(status_code=500, detail="Internal server error")
    finally:
        if conn:
            conn.close()


@router.post('/discoveries')
async def legacy_discoveries(
    payload: dict,
    request: Request,
    x_api_key: Optional[str] = Header(None, alias='X-API-Key'),
):
    """Legacy endpoint alias for Keeper bot compatibility — routes to the same
    pending_discoveries approval queue as /api/discoveries."""
    return await create_discovery(payload, request, x_api_key)


# =============================================================================
# DISCOVERIES SHOWCASE API - Browse, Stats, Recent, Feature
# =============================================================================

@router.get('/api/discoveries/types')
async def get_discovery_types():
    """Get all discovery type definitions with metadata for the frontend."""
    return {
        'types': DISCOVERY_TYPE_INFO,
        'slugs': DISCOVERY_TYPE_SLUGS
    }


@router.get('/api/discoveries/browse')
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

        # Filter by type slug.
        # NOTE: every where-clause column is qualified with the `d.` alias.
        # The fetch query LEFT JOINs systems/planets/moons, and `description`
        # (and `discovered_by`) also exist on `systems` — an unqualified
        # reference raised `ambiguous column name: description`, 500ing every
        # text search. The count query also aliases the table as `d`, so the
        # qualification is valid in both.
        if type and type in DISCOVERY_TYPE_SLUGS:
            where_clauses.append("d.type_slug = ?")
            params.append(type)

        # Search query — 2-char minimum mirrors the v1.51 Stage 2 hardening
        # of the older /api/discoveries endpoint. Single-char wildcard scans
        # against discovery_name/description/location_name across the full
        # table are the OOM pattern the prior fix was meant to prevent.
        q_clean = (q or '').strip()
        if q_clean and len(q_clean) >= 2:
            q_pattern = f"%{q_clean}%"
            where_clauses.append("(d.discovery_name LIKE ? OR d.description LIKE ? OR d.location_name LIKE ?)")
            params.extend([q_pattern, q_pattern, q_pattern])

        # Filter by discoverer
        if discoverer:
            where_clauses.append("d.discovered_by LIKE ?")
            params.append(f"%{discoverer}%")

        # Hide discoveries from archived civilizations (public endpoint)
        where_clauses.append(archived_civ_filter('d'))

        # Build base query — note: count query aliases the table as d to match
        # the archived_civ_filter subquery alias.
        where_sql = " WHERE " + " AND ".join(where_clauses) if where_clauses else ""

        # Get total count
        count_sql = f"SELECT COUNT(*) FROM discoveries d{where_sql}"
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

        # Add type info + parse the type_metadata JSON blob so the client gets
        # an object. browse/recent historically returned the raw JSON string,
        # so detail panels that key off `typeof === 'object'` silently dropped
        # every field (species, behavior, class, …).
        for d in discoveries:
            slug = d.get('type_slug') or get_discovery_type_slug(d.get('discovery_type', ''))
            d['type_info'] = DISCOVERY_TYPE_INFO.get(slug, DISCOVERY_TYPE_INFO['other'])
            if d.get('type_metadata'):
                try:
                    d['type_metadata'] = json.loads(d['type_metadata'])
                except (TypeError, ValueError):
                    pass

        return {
            'discoveries': discoveries,
            'total': total,
            'pages': pages,
            'page': page
        }

    except Exception as e:
        logger.error(f"Error browsing discoveries: {e}")
        logger.exception("Internal server error")
        raise HTTPException(status_code=500, detail="Internal server error")
    finally:
        if conn:
            conn.close()


@router.get('/api/discoveries/stats')
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

        _acf = archived_civ_filter('d')

        # Total count
        cursor.execute(f"SELECT COUNT(*) FROM discoveries d WHERE {_acf}")
        total = cursor.fetchone()[0]

        # Count by type_slug
        cursor.execute(f'''
            SELECT COALESCE(type_slug, 'other') as slug, COUNT(*) as cnt
            FROM discoveries d
            WHERE {_acf}
            GROUP BY type_slug
        ''')
        by_type = {slug: 0 for slug in DISCOVERY_TYPE_SLUGS}
        for row in cursor.fetchall():
            slug = row[0] if row[0] in DISCOVERY_TYPE_SLUGS else 'other'
            by_type[slug] = by_type.get(slug, 0) + row[1]

        # This week's count
        week_ago = (datetime.now() - timedelta(days=7)).isoformat()
        cursor.execute(f"SELECT COUNT(*) FROM discoveries d WHERE d.submission_timestamp > ? AND {_acf}", (week_ago,))
        this_week = cursor.fetchone()[0]

        # Featured count
        cursor.execute(f"SELECT COUNT(*) FROM discoveries d WHERE d.is_featured = 1 AND {_acf}")
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
        logger.exception("Internal server error")
        raise HTTPException(status_code=500, detail="Internal server error")
    finally:
        if conn:
            conn.close()


@router.get('/api/discoveries/recent')
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
        cursor.execute(f'''
            SELECT d.*, s.name as system_name, s.galaxy as system_galaxy,
                   s.is_stub as system_is_stub,
                   p.name as planet_name, m.name as moon_name
            FROM discoveries d
            LEFT JOIN systems s ON d.system_id = s.id
            LEFT JOIN planets p ON d.planet_id = p.id
            LEFT JOIN moons m ON d.moon_id = m.id
            WHERE {archived_civ_filter('d')}
            ORDER BY
                CASE WHEN d.photo_url IS NOT NULL AND d.photo_url != '' THEN 0 ELSE 1 END,
                d.submission_timestamp DESC
            LIMIT ?
        ''', (limit,))

        discoveries = [dict(row) for row in cursor.fetchall()]

        # Add type info + parse the type_metadata JSON blob (see browse()).
        for d in discoveries:
            slug = d.get('type_slug') or get_discovery_type_slug(d.get('discovery_type', ''))
            d['type_info'] = DISCOVERY_TYPE_INFO.get(slug, DISCOVERY_TYPE_INFO['other'])
            if d.get('type_metadata'):
                try:
                    d['type_metadata'] = json.loads(d['type_metadata'])
                except (TypeError, ValueError):
                    pass

        return {'discoveries': discoveries}

    except Exception as e:
        logger.error(f"Error getting recent discoveries: {e}")
        logger.exception("Internal server error")
        raise HTTPException(status_code=500, detail="Internal server error")
    finally:
        if conn:
            conn.close()


@router.get('/api/discoveries/{discovery_id}')
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

        raise HTTPException(status_code=404, detail='Discovery not found')
    except HTTPException:
        raise
    except IndexError:
        raise HTTPException(status_code=404, detail='Discovery not found')
    except Exception as e:
        logger.exception("Internal server error")
        raise HTTPException(status_code=500, detail="Internal server error")
    finally:
        if conn:
            conn.close()


@router.post('/api/discoveries/{discovery_id}/feature')
async def toggle_discovery_featured(discovery_id: int, request: Request):
    """
    Toggle the featured status of a discovery.

    Requires admin or partner session.
    """
    conn = None
    try:
        # Check for admin/partner session
        session = _get_session_from_request(request)
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
        logger.exception("Internal server error")
        raise HTTPException(status_code=500, detail="Internal server error")
    finally:
        if conn:
            conn.close()


@router.post('/api/discoveries/{discovery_id}/view')
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

@router.post('/api/submit_discovery')
async def submit_discovery(payload: dict, request: Request, session: Optional[str] = Cookie(None)):
    """
    Submit a discovery for approval. Goes to pending_discoveries queue.
    No auth required, but accepts session for logged-in users.
    """
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

    # Optional: this submission is an EDIT of an existing live discovery
    # (mirror of pending_systems.edit_system_id). NULL = a brand-new discovery.
    # Validated against the DB inside the transaction below (must exist + live
    # on the same system — edits can change planet/moon, never move systems).
    edit_discovery_id = payload.get('edit_discovery_id')
    try:
        edit_discovery_id = int(edit_discovery_id) if edit_discovery_id not in (None, '') else None
    except (TypeError, ValueError):
        edit_discovery_id = None
    payload['edit_discovery_id'] = edit_discovery_id

    # Get client IP for tracking
    client_ip = request.client.host if request.client else "unknown"

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
    submitter_profile_id = None
    if session_data:
        user_type = session_data.get('user_type')
        submitter_profile_id = session_data.get('profile_id')
        if user_type == 'partner':
            submitter_account_id = session_data.get('partner_id')
            submitter_account_type = 'partner'
        elif user_type == 'sub_admin':
            submitter_account_id = session_data.get('sub_admin_id')
            submitter_account_type = 'sub_admin'
        elif user_type in ('member', 'member_readonly'):
            submitter_account_id = submitter_profile_id
            submitter_account_type = user_type

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

        # Validate the edit target: must exist and live on the SAME system.
        if edit_discovery_id is not None:
            cursor.execute('SELECT system_id FROM discoveries WHERE id = ?', (edit_discovery_id,))
            tgt = cursor.fetchone()
            if not tgt:
                raise HTTPException(status_code=404, detail='The discovery you are editing no longer exists.')
            if str(tgt['system_id']) != str(system_id):
                raise HTTPException(status_code=400, detail='An edit cannot move a discovery to a different system.')

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

        # Surface coordinates — only meaningful for planet/moon discoveries.
        # Normalize + range-check, null them for space discoveries, and write
        # the cleaned values back into the payload blob so the approval path
        # (which reads from discovery_data) promotes the validated values.
        location_type = payload.get('location_type') or 'space'
        latitude, longitude = normalize_discovery_coords(
            payload.get('latitude'), payload.get('longitude')
        )
        if location_type == 'space':
            latitude, longitude = None, None
        payload['latitude'] = latitude
        payload['longitude'] = longitude

        # Event participation (opt-in competition). Validate the submitter's
        # chosen event against this discovery's community; drop it if it's not
        # an active, in-window, discovery-accepting event. Mirror it into the
        # JSON blob so the approval path can read it.
        event_id = resolve_submission_event_id(
            cursor, payload.get('event_id'), discord_tag, 'discovery'
        )
        payload['event_id'] = event_id

        # Store entire payload as JSON
        discovery_data = json.dumps(payload)

        cursor.execute('''
            INSERT INTO pending_discoveries (
                discovery_data, discovery_name, discovery_type, type_slug,
                system_id, system_name, planet_name, moon_name, location_type,
                discord_tag, submitted_by, submitted_by_ip,
                submitter_account_id, submitter_account_type, submitter_profile_id,
                submission_date, photo_url, source, latitude, longitude,
                edit_discovery_id, event_id, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending')
        ''', (
            discovery_data,
            discovery_name,
            discovery_type,
            type_slug,
            str(system_id),
            system_name,
            planet_name,
            moon_name,
            location_type,
            discord_tag,
            discord_username,
            client_ip,
            submitter_account_id,
            submitter_account_type,
            submitter_profile_id,
            datetime.now(timezone.utc).isoformat(),
            payload.get('photo_url'),
            SOURCE_MANUAL,
            latitude,
            longitude,
            edit_discovery_id,
            event_id,
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
            'message': 'Discovery edit submitted for approval!' if edit_discovery_id else 'Discovery submitted for approval!',
            'submission_id': submission_id
        }, status_code=201)

    except HTTPException:
        raise
    except Exception as e:
        # Roll back deterministically so a failed write never lingers holding
        # the SQLite write lock (the "database is locked" busy-timeout risk).
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass
        logger.error(f"Error submitting discovery: {e}")
        logger.exception("Internal server error")
        raise HTTPException(status_code=500, detail="Internal server error")
    finally:
        if conn:
            conn.close()


@router.get('/api/pending_discoveries')
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
            system_id, system_name, planet_name, moon_name, location_type,
            latitude, longitude,
            discord_tag, submitted_by, submission_date, photo_url,
            status, reviewed_by, review_date, rejection_reason,
            submitter_account_id, submitter_account_type, edit_discovery_id
        '''

        # Single-query scoping via civ_scope_filter (migration 1.80.0).
        scope_clause, scope_params = civ_scope_filter(session_data, column='discord_tag')
        if scope_clause == '1=0':
            submissions = []
            cursor_rows = []
        else:
            can_approve_personal = bool(
                session_data.get('can_approve_personal_uploads', False)
                or any(m.get('can_approve_personal_uploads')
                       for m in (session_data.get('civ_memberships') or []))
            )
            tag_clause = (
                f"(({scope_clause}) OR discord_tag = 'personal')"
                if can_approve_personal else scope_clause
            )
            cursor.execute(f'''
                SELECT {select_cols} FROM pending_discoveries
                WHERE {tag_clause}
                ORDER BY
                    CASE status WHEN 'pending' THEN 1 WHEN 'approved' THEN 2 WHEN 'rejected' THEN 3 END,
                    submission_date DESC
            ''', scope_params)

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
        logger.exception("Internal server error")
        raise HTTPException(status_code=500, detail="Internal server error")
    finally:
        if conn:
            conn.close()


@router.get('/api/pending_discoveries/{submission_id}')
async def get_pending_discovery_detail(submission_id: int, session: Optional[str] = Cookie(None)):
    """Get full details of a pending discovery submission.

    Community-scoped (parity with pending_systems detail endpoint). Returns
    404 (not 403) when out of scope so callers cannot enumerate IDs to
    discover what civs are submitting what.
    """
    if not verify_session(session):
        raise HTTPException(status_code=401, detail="Admin authentication required")

    session_data = get_session(session)
    is_super = session_data.get('user_type') == 'super_admin' if session_data else False

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM pending_discoveries WHERE id = ?', (submission_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Submission not found")

        submission = dict(row)

        # Community scoping for non-super-admins
        if not is_super:
            sub_tag = submission.get('discord_tag')
            if not user_can_act_for_civ(session_data, sub_tag):
                raise HTTPException(status_code=404, detail="Submission not found")

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
        logger.exception("Internal server error")
        raise HTTPException(status_code=500, detail="Internal server error")
    finally:
        if conn:
            conn.close()


# Editable fields a super admin can change on a pending discovery before
# approval. system_id and discord_tag are intentionally locked (a discovery
# stays on its system and keeps its community).
_EDITABLE_DISCOVERY_FIELDS = (
    'discovery_name', 'discovery_type', 'description', 'significance',
    'location_type', 'planet_id', 'moon_id', 'location_name',
    'latitude', 'longitude', 'photo_url', 'evidence_urls', 'type_metadata',
)


@router.put('/api/pending_discoveries/{submission_id}')
async def edit_pending_discovery(submission_id: int, payload: dict, session: Optional[str] = Cookie(None)):
    """Super-admin inline edit of a PENDING discovery before approval.

    Mirrors PUT /api/pending_systems/{id}: merges the edited fields into the
    discovery_data JSON blob and re-syncs the denormalized columns the queue
    card reads. Does not approve — the row stays pending.
    """
    session_data = get_session(session)
    if not session_data or session_data.get('user_type') != 'super_admin':
        raise HTTPException(status_code=403, detail="Super admin required")

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
            raise HTTPException(status_code=400, detail="Only pending submissions can be edited")

        # Merge edited fields into the existing discovery_data blob
        data = {}
        if submission.get('discovery_data'):
            try:
                data = json.loads(submission['discovery_data'])
            except (json.JSONDecodeError, TypeError):
                data = {}
        for k in _EDITABLE_DISCOVERY_FIELDS:
            if k in payload:
                data[k] = payload[k]

        discovery_name = (data.get('discovery_name') or submission.get('discovery_name') or 'Unnamed Discovery')
        discovery_type = data.get('discovery_type') or submission.get('discovery_type') or 'Unknown'
        type_slug = get_discovery_type_slug(discovery_type)
        location_type = data.get('location_type') or 'space'

        # Re-denormalize planet/moon names + coords
        planet_name = None
        if data.get('planet_id'):
            cursor.execute('SELECT name FROM planets WHERE id = ?', (data['planet_id'],))
            r = cursor.fetchone()
            planet_name = r['name'] if r else None
        moon_name = None
        if data.get('moon_id'):
            cursor.execute('SELECT name FROM moons WHERE id = ?', (data['moon_id'],))
            r = cursor.fetchone()
            moon_name = r['name'] if r else None
        latitude, longitude = normalize_discovery_coords(data.get('latitude'), data.get('longitude'))
        if location_type == 'space':
            latitude, longitude = None, None
        data['latitude'], data['longitude'] = latitude, longitude

        cursor.execute('''
            UPDATE pending_discoveries SET
                discovery_data = ?, discovery_name = ?, discovery_type = ?, type_slug = ?,
                location_type = ?, planet_name = ?, moon_name = ?,
                latitude = ?, longitude = ?, photo_url = ?
            WHERE id = ?
        ''', (
            json.dumps(data), discovery_name, discovery_type, type_slug,
            location_type, planet_name, moon_name,
            latitude, longitude, data.get('photo_url') or submission.get('photo_url'),
            submission_id,
        ))

        cursor.execute('''
            INSERT INTO approval_audit_log
            (timestamp, action, submission_type, submission_id, submission_name,
             approver_username, approver_type, approver_account_id, approver_discord_tag,
             submitter_username, submitter_account_id, submitter_type, submission_discord_tag, source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            datetime.now(timezone.utc).isoformat(),
            'edit_pending_discovery', 'discovery', submission_id, discovery_name,
            session_data.get('username'), 'super_admin', None, session_data.get('discord_tag'),
            submission.get('submitted_by'), submission.get('submitter_account_id'),
            submission.get('submitter_account_type'), submission.get('discord_tag'),
            submission.get('source', 'manual'),
        ))
        conn.commit()

        logger.info(f"Pending discovery {submission_id} edited inline by super admin")
        return {'status': 'ok'}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error editing pending discovery: {e}")
        logger.exception("Internal server error")
        raise HTTPException(status_code=500, detail="Internal server error")
    finally:
        if conn:
            conn.close()


@router.post('/api/approve_discovery/{submission_id}')
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
    require_feature(session_data, 'approvals')
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

        # Self-approval blocking
        if check_self_submission(submission, session_data):
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

        # Surface coordinates — prefer the dedicated pending columns, fall back
        # to the JSON blob (covers rows queued before the columns existed).
        location_type = discovery_data.get('location_type') or 'space'
        latitude, longitude = normalize_discovery_coords(
            submission.get('latitude') if submission.get('latitude') is not None else discovery_data.get('latitude'),
            submission.get('longitude') if submission.get('longitude') is not None else discovery_data.get('longitude'),
        )
        if location_type == 'space':
            latitude, longitude = None, None

        # Is this an EDIT of an existing live discovery? (mirror of system edits)
        edit_discovery_id = submission.get('edit_discovery_id')
        if edit_discovery_id is None:
            edit_discovery_id = discovery_data.get('edit_discovery_id')
        try:
            edit_discovery_id = int(edit_discovery_id) if edit_discovery_id not in (None, '') else None
        except (TypeError, ValueError):
            edit_discovery_id = None

        is_edit = False
        # Parent system whose cached completeness must be refreshed after this
        # approval (a discovery's planet/moon link feeds the S+ checklist).
        parent_system_id = None
        if edit_discovery_id is not None:
            # EDIT path: update the live discovery in place. Preserve the original
            # attribution (discovered_by, submission_timestamp, system_id,
            # discord_tag, profile_id, source) — only the editable fields change.
            cursor.execute('SELECT id, system_id FROM discoveries WHERE id = ?', (edit_discovery_id,))
            live_row = cursor.fetchone()
            if not live_row:
                raise HTTPException(
                    status_code=400,
                    detail="The discovery this edit targets no longer exists. Reject this submission instead."
                )
            # Edits can change planet/moon but never the system, so the live row's
            # system_id is the parent to re-score.
            parent_system_id = live_row['system_id']
            cursor.execute('''
                UPDATE discoveries SET
                    discovery_type = ?, discovery_name = ?, type_slug = ?,
                    planet_id = ?, moon_id = ?, location_type = ?, location_name = ?,
                    description = ?, significance = ?, mystery_tier = ?,
                    photo_url = ?, evidence_url = ?, type_metadata = ?,
                    latitude = ?, longitude = ?
                WHERE id = ?
            ''', (
                discovery_type,
                discovery_name,
                type_slug,
                discovery_data.get('planet_id'),
                discovery_data.get('moon_id'),
                location_type,
                discovery_data.get('location_name') or '',
                discovery_data.get('description') or '',
                discovery_data.get('significance') or 'Notable',
                discovery_data.get('mystery_tier') or 1,
                discovery_data.get('photo_url') or submission.get('photo_url'),
                discovery_data.get('evidence_urls'),
                type_metadata_json,
                latitude,
                longitude,
                edit_discovery_id,
            ))
            discovery_id = edit_discovery_id
            is_edit = True
        else:
            cursor.execute('''
                INSERT INTO discoveries (
                    discovery_type, discovery_name, system_id, planet_id, moon_id,
                    location_type, location_name, description, significance,
                    discovered_by, submission_timestamp,
                    mystery_tier, analysis_status, pattern_matches,
                    discord_user_id, discord_guild_id,
                    photo_url, evidence_url, type_slug, discord_tag, type_metadata, profile_id, source,
                    latitude, longitude, event_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                discovery_type,
                discovery_name,
                discovery_data.get('system_id'),
                discovery_data.get('planet_id'),
                discovery_data.get('moon_id'),
                location_type,
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
                submission.get('submitter_profile_id'),
                submission.get('source') or SOURCE_MANUAL,
                latitude,
                longitude,
                submission.get('event_id') if submission.get('event_id') is not None else discovery_data.get('event_id'),
            ))
            discovery_id = cursor.lastrowid
            parent_system_id = discovery_data.get('system_id')

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
             submitter_username, submitter_account_id, submitter_type, submission_discord_tag, source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            submission.get('source', 'manual'),
        ))

        # A discovery's link to a planet/moon is a primary input to the S+
        # "fully charted" checklist, so refresh the parent system's cached
        # completeness/is_fully_charted now that the live discovery exists.
        # The system detail page recomputes live, but the systems list / map /
        # search / posters read the cached column — without this they'd disagree
        # on S vs S+ (the Mabaya bug).
        if parent_system_id:
            try:
                update_completeness_score(cursor, parent_system_id)
            except Exception as score_err:
                logger.warning(
                    f"Completeness recompute after discovery approve failed "
                    f"for system {parent_system_id}: {score_err}"
                )

        conn.commit()

        add_activity_log(
            'discovery_approved',
            f"Discovery '{discovery_name}' {'edit approved' if is_edit else 'approved'}",
            details=f"Type: {discovery_type}",
            user_name=current_username
        )

        logger.info(
            f"Discovery '{discovery_name}' {'EDIT ' if is_edit else ''}approved "
            f"(pending_id: {submission_id}, discovery_id: {discovery_id})"
        )
        return {'status': 'ok', 'discovery_id': discovery_id, 'is_edit': is_edit}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error approving discovery: {e}")
        logger.exception("Internal server error")
        raise HTTPException(status_code=500, detail="Internal server error")
    finally:
        if conn:
            conn.close()


@router.post('/api/reject_discovery/{submission_id}')
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
    require_feature(session_data, 'approvals')
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

        # Self-rejection blocking: use the canonical helper. The inline
        # version this replaced was missing the profile_id comparison and
        # the personal_discord_username fallback that approve_discovery's
        # check_self_submission() call covers — letting a self-rejection
        # slip through gaps the helper closes.
        if check_self_submission(submission, session_data):
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
             submitter_username, submitter_account_id, submitter_type, notes, submission_discord_tag, source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            submission.get('source', 'manual'),
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
        logger.exception("Internal server error")
        raise HTTPException(status_code=500, detail="Internal server error")
    finally:
        if conn:
            conn.close()
