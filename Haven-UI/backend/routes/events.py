"""Events CRUD and leaderboard endpoints."""

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Cookie, HTTPException, Request

from db import get_db_connection
from services.auth_service import get_session

logger = logging.getLogger('control.room')

router = APIRouter(tags=["events"])


# ============================================================================
# Events Endpoints (for submission events/competitions)
# ============================================================================

@router.get('/api/events')
async def list_events(
    include_inactive: bool = False,
    session: Optional[str] = Cookie(None)
):
    """
    List submission events.
    Partners see their own community's events.
    Super admins see all.
    """
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail='Authentication required')

    is_super = session_data.get('user_type') == 'super_admin'
    user_discord_tag = session_data.get('discord_tag')

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        query = 'SELECT * FROM events WHERE 1=1'
        params = []

        if not is_super and user_discord_tag:
            query += ' AND discord_tag = ?'
            params.append(user_discord_tag)

        if not include_inactive:
            query += ' AND is_active = 1'

        query += ' ORDER BY start_date DESC'
        cursor.execute(query, params)
        rows = cursor.fetchall()

        events = []

        # Define username extraction (same as Analytics for consistency)
        # Skip 'Anonymous' and 'anonymous' values to find the actual username
        raw_username = '''COALESCE(
            NULLIF(NULLIF(submitted_by, 'Anonymous'), 'anonymous'),
            personal_discord_username,
            json_extract(system_data, '$.discovered_by'),
            'Unknown'
        )'''
        # Normalize: trim, remove #, strip trailing 4-digit Discord discriminator, lowercase
        trimmed_username = f'''TRIM(REPLACE({raw_username}, '#', ''))'''
        normalized_username = f'''LOWER(TRIM(
            CASE
                WHEN LENGTH({trimmed_username}) > 4
                    AND SUBSTR({trimmed_username}, -4) GLOB '[0-9][0-9][0-9][0-9]'
                    AND (LENGTH({trimmed_username}) = 4
                        OR SUBSTR({trimmed_username}, -5, 1) NOT GLOB '[0-9]')
                THEN SUBSTR({trimmed_username}, 1, LENGTH({trimmed_username}) - 4)
                ELSE {trimmed_username}
            END
        ))'''

        for row in rows:
            event = dict(row)
            event_type = event.get('event_type', 'submissions') or 'submissions'

            # Get submission count and participant count for this event
            if event_type in ('submissions', 'both'):
                cursor.execute(f'''
                    SELECT COUNT(*) as submissions,
                           COUNT(DISTINCT CASE WHEN {normalized_username} != 'unknown' THEN {normalized_username} END) as participants
                    FROM pending_systems
                    WHERE discord_tag = ?
                      AND submission_date >= ?
                      AND submission_date <= ?
                ''', (event['discord_tag'], event['start_date'], event['end_date'] + 'T23:59:59'))
                stats = cursor.fetchone()
                event['submission_count'] = stats['submissions'] or 0
                event['participant_count'] = stats['participants'] or 0
            else:
                event['submission_count'] = 0
                event['participant_count'] = 0

            # Get discovery count and participant count for discovery events
            if event_type in ('discoveries', 'both'):
                cursor.execute('''
                    SELECT COUNT(*) as discoveries,
                           COUNT(DISTINCT LOWER(TRIM(discovered_by))) as disc_participants
                    FROM discoveries
                    WHERE discord_tag = ?
                      AND submission_timestamp >= ?
                      AND submission_timestamp <= ?
                      AND LOWER(TRIM(discovered_by)) != 'anonymous'
                      AND LOWER(TRIM(discovered_by)) != 'unknown'
                ''', (event['discord_tag'], event['start_date'], event['end_date'] + 'T23:59:59'))
                disc_stats = cursor.fetchone()
                event['discovery_count'] = disc_stats['discoveries'] or 0
                event['discovery_participant_count'] = disc_stats['disc_participants'] or 0
            else:
                event['discovery_count'] = 0
                event['discovery_participant_count'] = 0

            # Check if event is currently active (based on dates)
            now = datetime.now().isoformat()
            event['is_current'] = event['start_date'] <= now <= event['end_date'] + 'T23:59:59'

            events.append(event)

        return {'events': events}
    finally:
        if conn:
            conn.close()


@router.post('/api/events')
async def create_event(request: Request, session: Optional[str] = Cookie(None)):
    """
    Create a new submission event.
    Partners can create events for their community.
    Super admins can create for any community.
    """
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail='Authentication required')

    is_super = session_data.get('user_type') == 'super_admin'
    user_discord_tag = session_data.get('discord_tag')

    body = await request.json()
    name = body.get('name')
    discord_tag = body.get('discord_tag')
    start_date = body.get('start_date')
    end_date = body.get('end_date')
    description = body.get('description', '')
    event_type = body.get('event_type', 'submissions')

    if event_type not in ('submissions', 'discoveries', 'both'):
        event_type = 'submissions'

    if not all([name, start_date, end_date]):
        raise HTTPException(status_code=400, detail='name, start_date, and end_date are required')

    # Partners can only create events for their own community
    if not is_super:
        if user_discord_tag:
            discord_tag = user_discord_tag
        else:
            raise HTTPException(status_code=403, detail='Cannot create events without a community')

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO events (name, discord_tag, start_date, end_date, description, created_by, event_type)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (name, discord_tag, start_date, end_date, description, session_data.get('username'), event_type))

        conn.commit()
        event_id = cursor.lastrowid

        return {'success': True, 'event_id': event_id}
    finally:
        if conn:
            conn.close()


@router.get('/api/events/{event_id}')
async def get_event(event_id: int, session: Optional[str] = Cookie(None)):
    """Get a single event by ID."""
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail='Authentication required')

    is_super = session_data.get('user_type') == 'super_admin'
    user_discord_tag = session_data.get('discord_tag')

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM events WHERE id = ?', (event_id,))
        row = cursor.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail='Event not found')

        event = dict(row)

        # Check access
        if not is_super and user_discord_tag != event['discord_tag']:
            raise HTTPException(status_code=403, detail='Access denied')

        return {'event': event}
    finally:
        if conn:
            conn.close()


@router.get('/api/events/{event_id}/leaderboard')
async def get_event_leaderboard(
    event_id: int,
    tab: str = 'submissions',
    limit: int = 50,
    session: Optional[str] = Cookie(None)
):
    """
    Get leaderboard for a specific event.
    Shows submissions and/or discoveries during the event period.

    Args:
        tab: 'submissions', 'discoveries', or 'combined'
    """
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail='Authentication required')

    is_super = session_data.get('user_type') == 'super_admin'
    user_discord_tag = session_data.get('discord_tag')

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Get event details
        cursor.execute('SELECT * FROM events WHERE id = ?', (event_id,))
        event_row = cursor.fetchone()

        if not event_row:
            raise HTTPException(status_code=404, detail='Event not found')

        event = dict(event_row)

        # Check access
        if not is_super and user_discord_tag != event['discord_tag']:
            raise HTTPException(status_code=403, detail='Access denied')

        # Normalize usernames for submission leaderboard
        raw_username = '''COALESCE(
            NULLIF(NULLIF(submitted_by, 'Anonymous'), 'anonymous'),
            personal_discord_username,
            json_extract(system_data, '$.discovered_by'),
            'Unknown'
        )'''
        trimmed_username = f'''TRIM(REPLACE({raw_username}, '#', ''))'''
        normalized_username = f'''LOWER(TRIM(
            CASE
                WHEN LENGTH({trimmed_username}) > 4
                    AND SUBSTR({trimmed_username}, -4) GLOB '[0-9][0-9][0-9][0-9]'
                    AND (LENGTH({trimmed_username}) = 4
                        OR SUBSTR({trimmed_username}, -5, 1) NOT GLOB '[0-9]')
                THEN SUBSTR({trimmed_username}, 1, LENGTH({trimmed_username}) - 4)
                ELSE {trimmed_username}
            END
        ))'''

        leaderboard = []
        totals = {}

        if tab == 'submissions':
            # Original submission leaderboard logic
            query = f'''
                SELECT
                    MAX({raw_username}) as username,
                    COUNT(*) as total_submissions,
                    SUM(CASE WHEN status = 'approved' THEN 1 ELSE 0 END) as approved,
                    SUM(CASE WHEN status = 'rejected' THEN 1 ELSE 0 END) as rejected,
                    MIN(submission_date) as first_submission,
                    MAX(submission_date) as last_submission
                FROM pending_systems
                WHERE discord_tag = ?
                  AND submission_date >= ?
                  AND submission_date <= ?
                GROUP BY {normalized_username}
                HAVING {normalized_username} != 'unknown'
                ORDER BY total_submissions DESC
                LIMIT ?
            '''
            cursor.execute(query, (event['discord_tag'], event['start_date'],
                                   event['end_date'] + 'T23:59:59', limit))
            rows = cursor.fetchall()

            rank = 1
            for row in rows:
                entry = dict(row)
                entry['rank'] = rank
                total = entry['total_submissions']
                approved = entry['approved'] or 0
                entry['approval_rate'] = round((approved / total * 100), 1) if total > 0 else 0
                leaderboard.append(entry)
                rank += 1

            cursor.execute(f'''
                SELECT
                    COUNT(*) as total_submissions,
                    SUM(CASE WHEN status = 'approved' THEN 1 ELSE 0 END) as total_approved,
                    COUNT(DISTINCT CASE WHEN {normalized_username} != 'unknown' THEN {normalized_username} END) as participants
                FROM pending_systems
                WHERE discord_tag = ?
                  AND submission_date >= ?
                  AND submission_date <= ?
            ''', (event['discord_tag'], event['start_date'], event['end_date'] + 'T23:59:59'))
            totals_row = cursor.fetchone()

            totals = {
                'total_submissions': totals_row['total_submissions'] or 0,
                'total_approved': totals_row['total_approved'] or 0,
                'participants': totals_row['participants'] or 0
            }

        elif tab == 'discoveries':
            # Discovery leaderboard
            cursor.execute('''
                SELECT
                    discovered_by as username,
                    COUNT(*) as total_discoveries,
                    COUNT(DISTINCT type_slug) as types_count,
                    GROUP_CONCAT(DISTINCT type_slug) as type_slugs,
                    MIN(submission_timestamp) as first_discovery,
                    MAX(submission_timestamp) as last_discovery
                FROM discoveries
                WHERE discord_tag = ?
                  AND submission_timestamp >= ?
                  AND submission_timestamp <= ?
                  AND LOWER(TRIM(discovered_by)) != 'anonymous'
                  AND LOWER(TRIM(discovered_by)) != 'unknown'
                GROUP BY LOWER(TRIM(discovered_by))
                ORDER BY total_discoveries DESC
                LIMIT ?
            ''', (event['discord_tag'], event['start_date'],
                  event['end_date'] + 'T23:59:59', limit))
            rows = cursor.fetchall()

            rank = 1
            for row in rows:
                entry = dict(row)
                entry['rank'] = rank
                leaderboard.append(entry)
                rank += 1

            cursor.execute('''
                SELECT
                    COUNT(*) as total_discoveries,
                    COUNT(DISTINCT LOWER(TRIM(discovered_by))) as participants
                FROM discoveries
                WHERE discord_tag = ?
                  AND submission_timestamp >= ?
                  AND submission_timestamp <= ?
                  AND LOWER(TRIM(discovered_by)) != 'anonymous'
                  AND LOWER(TRIM(discovered_by)) != 'unknown'
            ''', (event['discord_tag'], event['start_date'], event['end_date'] + 'T23:59:59'))
            totals_row = cursor.fetchone()

            totals = {
                'total_discoveries': totals_row['total_discoveries'] or 0,
                'participants': totals_row['participants'] or 0
            }

        elif tab == 'combined':
            # Combined: merge submissions + discoveries by normalized username
            # Get submission counts per user
            cursor.execute(f'''
                SELECT
                    {normalized_username} as norm_user,
                    MAX({raw_username}) as username,
                    COUNT(*) as total_submissions,
                    SUM(CASE WHEN status = 'approved' THEN 1 ELSE 0 END) as approved
                FROM pending_systems
                WHERE discord_tag = ?
                  AND submission_date >= ?
                  AND submission_date <= ?
                GROUP BY {normalized_username}
                HAVING {normalized_username} != 'unknown'
            ''', (event['discord_tag'], event['start_date'], event['end_date'] + 'T23:59:59'))

            user_data = {}
            for row in cursor.fetchall():
                r = dict(row)
                norm = r['norm_user']
                user_data[norm] = {
                    'username': r['username'],
                    'total_submissions': r['total_submissions'],
                    'approved': r['approved'] or 0,
                    'total_discoveries': 0
                }

            # Get discovery counts per user
            cursor.execute('''
                SELECT
                    LOWER(TRIM(discovered_by)) as norm_user,
                    discovered_by as username,
                    COUNT(*) as total_discoveries
                FROM discoveries
                WHERE discord_tag = ?
                  AND submission_timestamp >= ?
                  AND submission_timestamp <= ?
                  AND LOWER(TRIM(discovered_by)) != 'anonymous'
                  AND LOWER(TRIM(discovered_by)) != 'unknown'
                GROUP BY LOWER(TRIM(discovered_by))
            ''', (event['discord_tag'], event['start_date'], event['end_date'] + 'T23:59:59'))

            for row in cursor.fetchall():
                r = dict(row)
                norm = r['norm_user']
                if norm in user_data:
                    user_data[norm]['total_discoveries'] = r['total_discoveries']
                else:
                    user_data[norm] = {
                        'username': r['username'],
                        'total_submissions': 0,
                        'approved': 0,
                        'total_discoveries': r['total_discoveries']
                    }

            # Sort by combined total
            sorted_users = sorted(
                user_data.values(),
                key=lambda u: u['total_submissions'] + u['total_discoveries'],
                reverse=True
            )[:limit]

            rank = 1
            for entry in sorted_users:
                entry['rank'] = rank
                entry['combined_total'] = entry['total_submissions'] + entry['total_discoveries']
                leaderboard.append(entry)
                rank += 1

            # Combined totals
            sub_total = sum(u['total_submissions'] for u in user_data.values())
            disc_total = sum(u['total_discoveries'] for u in user_data.values())
            totals = {
                'total_submissions': sub_total,
                'total_discoveries': disc_total,
                'combined_total': sub_total + disc_total,
                'participants': len(user_data)
            }

        return {
            'event': event,
            'leaderboard': leaderboard,
            'totals': totals,
            'tab': tab
        }
    finally:
        if conn:
            conn.close()


@router.put('/api/events/{event_id}')
async def update_event(event_id: int, request: Request, session: Optional[str] = Cookie(None)):
    """Update an event."""
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail='Authentication required')

    is_super = session_data.get('user_type') == 'super_admin'
    user_discord_tag = session_data.get('discord_tag')

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Check event exists and access
        cursor.execute('SELECT * FROM events WHERE id = ?', (event_id,))
        event_row = cursor.fetchone()

        if not event_row:
            raise HTTPException(status_code=404, detail='Event not found')

        if not is_super and user_discord_tag != event_row['discord_tag']:
            raise HTTPException(status_code=403, detail='Access denied')

        body = await request.json()

        # Build update query
        updates = []
        params = []

        for field in ['name', 'start_date', 'end_date', 'description', 'is_active', 'event_type']:
            if field in body:
                if field == 'event_type' and body[field] not in ('submissions', 'discoveries', 'both'):
                    continue
                updates.append(f'{field} = ?')
                params.append(body[field])

        if updates:
            params.append(event_id)
            cursor.execute(f'''
                UPDATE events SET {', '.join(updates)} WHERE id = ?
            ''', params)
            conn.commit()

        return {'success': True}
    finally:
        if conn:
            conn.close()


@router.delete('/api/events/{event_id}')
async def delete_event(event_id: int, session: Optional[str] = Cookie(None)):
    """Delete an event."""
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail='Authentication required')

    is_super = session_data.get('user_type') == 'super_admin'
    user_discord_tag = session_data.get('discord_tag')

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Check event exists and access
        cursor.execute('SELECT * FROM events WHERE id = ?', (event_id,))
        event_row = cursor.fetchone()

        if not event_row:
            raise HTTPException(status_code=404, detail='Event not found')

        if not is_super and user_discord_tag != event_row['discord_tag']:
            raise HTTPException(status_code=403, detail='Access denied')

        cursor.execute('DELETE FROM events WHERE id = ?', (event_id,))
        conn.commit()

        return {'success': True}
    finally:
        if conn:
            conn.close()
