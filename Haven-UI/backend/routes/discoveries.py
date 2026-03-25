"""Discovery CRUD, showcase, and approval workflow endpoints."""

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Cookie, HTTPException, Request
from fastapi.responses import JSONResponse

from constants import (
    normalize_discord_username,
    DISCOVERY_TYPE_SLUGS, DISCOVERY_TYPE_INFO, DISCOVERY_TYPE_FIELDS,
    get_discovery_type_slug,
)
from db import get_db_connection, get_db_path, add_activity_log
from services.auth_service import (
    get_session,
    verify_session,
    require_feature,
    check_self_submission,
)

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
            if q:
                cursor.execute('''
                    SELECT * FROM discoveries
                    WHERE discovery_name LIKE ? OR description LIKE ? OR location_name LIKE ?
                    ORDER BY submission_timestamp DESC LIMIT 200
                ''', (f'%{q}%', f'%{q}%', f'%{q}%'))
            else:
                cursor.execute('SELECT * FROM discoveries ORDER BY submission_timestamp DESC LIMIT 200')
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
        logger.exception("Internal server error")
        raise HTTPException(status_code=500, detail="Internal server error")
    finally:
        if conn:
            conn.close()


@router.post('/discoveries')
async def legacy_discoveries(payload: dict):
    """Legacy endpoint redirect for Keeper bot compatibility."""
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
                submitter_account_id, submitter_account_type, submitter_profile_id,
                submission_date, photo_url, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending')
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
            submitter_profile_id,
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
        logger.exception("Internal server error")
        raise HTTPException(status_code=500, detail="Internal server error")
    finally:
        if conn:
            conn.close()


@router.get('/api/pending_discoveries/{submission_id}')
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

        cursor.execute('''
            INSERT INTO discoveries (
                discovery_type, discovery_name, system_id, planet_id, moon_id,
                location_type, location_name, description, significance,
                discovered_by, submission_timestamp,
                mystery_tier, analysis_status, pattern_matches,
                discord_user_id, discord_guild_id,
                photo_url, evidence_url, type_slug, discord_tag, type_metadata, profile_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            submission.get('submitter_profile_id'),
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

        # Self-rejection blocking: same rules as system rejection
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
