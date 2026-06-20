"""Events CRUD, participation picker, and approved-only leaderboards.

An event is a time-boxed, community-scoped competition. Submitters opt in by
picking an active event at upload time; the chosen `event_id` is stored on the
pending row and carried to the live `systems` / `discoveries` row on approval
(see services/events.py + the intake paths in approvals.py / discoveries.py).

Scoring counts APPROVED rows only, grouped by `event_id` — NOT a tag+date slice
of the whole submission firehose (the pre-v1.90 behaviour, which counted
pending/rejected rows and couldn't tell two overlapping events apart).

Routes:
  Admin/partner (auth):
    GET    /api/events                 — manage list (own community, approved counts)
    GET    /api/events/active          — picker feed (active, in-window events)
    POST   /api/events                 — create
    GET    /api/events/{id}            — single
    GET    /api/events/{id}/leaderboard
    PUT    /api/events/{id}            — update / toggle active
    DELETE /api/events/{id}
  Public (no auth):
    GET    /api/public/events
    GET    /api/public/events/{id}
    GET    /api/public/events/{id}/leaderboard
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Cookie, HTTPException, Request

from db import get_db_connection
from services.auth_service import get_session

logger = logging.getLogger('control.room')

router = APIRouter(tags=["events"])


# ============================================================================
# Helpers
# ============================================================================

# event_type → which submission kinds it scores.
_TYPE_ACCEPTS = {
    'submissions': ('systems',),
    'discoveries': ('discoveries',),
    'both': ('systems', 'discoveries'),
}


def _norm_user_sql(col: str) -> str:
    """SQL expression that normalizes a username column to a dedup key.

    Trim, drop a leading 'Anonymous'/'anonymous', strip '#', remove a trailing
    4-digit Discord discriminator, lowercase. Applied IDENTICALLY to the
    `discovered_by` column on both `systems` and `discoveries` so the combined
    leaderboard merges the same person from both sources (the pre-v1.90 bug
    normalized the two sides differently and double-counted)."""
    raw = f"COALESCE(NULLIF(NULLIF({col}, 'Anonymous'), 'anonymous'), 'Unknown')"
    trimmed = f"TRIM(REPLACE({raw}, '#', ''))"
    return f'''LOWER(TRIM(
        CASE
            WHEN LENGTH({trimmed}) > 4
                AND SUBSTR({trimmed}, -4) GLOB '[0-9][0-9][0-9][0-9]'
                AND (LENGTH({trimmed}) = 4
                    OR SUBSTR({trimmed}, -5, 1) NOT GLOB '[0-9]')
            THEN SUBSTR({trimmed}, 1, LENGTH({trimmed}) - 4)
            ELSE {trimmed}
        END
    ))'''


_NORM = _norm_user_sql('discovered_by')


def _compute_status(event: dict) -> str:
    """Derive an event's lifecycle status from its dates + active flag.

    Uses the UTC calendar date against the inclusive [start_date, end_date]
    window. Returned to the client so the UI doesn't re-derive it from a
    timezone-mismatched comparison (the pre-v1.90 frontend bug)."""
    if not event.get('is_active'):
        return 'inactive'
    today = datetime.now(timezone.utc).date().isoformat()
    start = (event.get('start_date') or '')[:10]
    end = (event.get('end_date') or '')[:10]
    if start and today < start:
        return 'upcoming'
    if end and today > end:
        return 'ended'
    return 'active'


def _enrich_event(cursor, event: dict) -> dict:
    """Attach approved-only counts + computed status to an event row."""
    event_type = event.get('event_type') or 'submissions'

    if event_type in ('submissions', 'both'):
        cursor.execute(f'''
            SELECT COUNT(*) AS c,
                   COUNT(DISTINCT CASE WHEN {_NORM} != 'unknown' THEN {_NORM} END) AS p
            FROM systems WHERE event_id = ?
        ''', (event['id'],))
        r = cursor.fetchone()
        event['submission_count'] = r['c'] or 0
        event['participant_count'] = r['p'] or 0
    else:
        event['submission_count'] = 0
        event['participant_count'] = 0

    if event_type in ('discoveries', 'both'):
        cursor.execute(f'''
            SELECT COUNT(*) AS c,
                   COUNT(DISTINCT CASE WHEN {_NORM} != 'unknown' THEN {_NORM} END) AS p
            FROM discoveries WHERE event_id = ?
        ''', (event['id'],))
        r = cursor.fetchone()
        event['discovery_count'] = r['c'] or 0
        event['discovery_participant_count'] = r['p'] or 0
    else:
        event['discovery_count'] = 0
        event['discovery_participant_count'] = 0

    event['status'] = _compute_status(event)
    event['is_current'] = event['status'] == 'active'
    return event


def _caller_civ_tags(session_data) -> list:
    """The communities a logged-in caller can manage events for.

    Uses the full civ_tags list (so a leader/sub-admin of multiple civs sees
    all of them), falling back to the legacy single discord_tag for older
    sessions. Empty list = no community → sees nothing (closes the pre-v1.90
    leak where a tag-less admin saw every community's events)."""
    if not session_data:
        return []
    tags = list(session_data.get('civ_tags') or [])
    legacy = session_data.get('discord_tag')
    if not tags and legacy:
        tags = [legacy]
    return tags


def _compute_leaderboard(cursor, event: dict, tab: str, limit: int) -> dict:
    """Approved-only leaderboard for one event, keyed by event_id.

    tab: 'submissions' | 'discoveries' | 'combined'. Returns {leaderboard, totals}.
    """
    event_id = event['id']
    leaderboard = []
    totals = {}

    if tab == 'discoveries':
        cursor.execute(f'''
            SELECT MAX(discovered_by) AS username,
                   COUNT(*) AS total_discoveries,
                   COUNT(DISTINCT type_slug) AS types_count,
                   GROUP_CONCAT(DISTINCT type_slug) AS type_slugs,
                   MIN(submission_timestamp) AS first_discovery,
                   MAX(submission_timestamp) AS last_discovery
            FROM discoveries
            WHERE event_id = ?
            GROUP BY {_NORM}
            HAVING {_NORM} != 'unknown'
            ORDER BY total_discoveries DESC
            LIMIT ?
        ''', (event_id, limit))
        for i, row in enumerate(cursor.fetchall(), start=1):
            entry = dict(row)
            entry['rank'] = i
            leaderboard.append(entry)

        cursor.execute(f'''
            SELECT COUNT(*) AS total_discoveries,
                   COUNT(DISTINCT CASE WHEN {_NORM} != 'unknown' THEN {_NORM} END) AS participants
            FROM discoveries WHERE event_id = ?
        ''', (event_id,))
        tr = cursor.fetchone()
        totals = {
            'total_discoveries': tr['total_discoveries'] or 0,
            'participants': tr['participants'] or 0,
        }

    elif tab == 'combined':
        user_data = {}
        cursor.execute(f'''
            SELECT {_NORM} AS norm_user, MAX(discovered_by) AS username, COUNT(*) AS total_submissions
            FROM systems
            WHERE event_id = ?
            GROUP BY {_NORM}
            HAVING {_NORM} != 'unknown'
        ''', (event_id,))
        for row in cursor.fetchall():
            r = dict(row)
            user_data[r['norm_user']] = {
                'username': r['username'],
                'total_submissions': r['total_submissions'],
                'total_discoveries': 0,
            }

        cursor.execute(f'''
            SELECT {_NORM} AS norm_user, MAX(discovered_by) AS username, COUNT(*) AS total_discoveries
            FROM discoveries
            WHERE event_id = ?
            GROUP BY {_NORM}
            HAVING {_NORM} != 'unknown'
        ''', (event_id,))
        for row in cursor.fetchall():
            r = dict(row)
            norm = r['norm_user']
            if norm in user_data:
                user_data[norm]['total_discoveries'] = r['total_discoveries']
            else:
                user_data[norm] = {
                    'username': r['username'],
                    'total_submissions': 0,
                    'total_discoveries': r['total_discoveries'],
                }

        ordered = sorted(
            user_data.values(),
            key=lambda u: u['total_submissions'] + u['total_discoveries'],
            reverse=True,
        )[:limit]
        for i, entry in enumerate(ordered, start=1):
            entry['rank'] = i
            entry['combined_total'] = entry['total_submissions'] + entry['total_discoveries']
            leaderboard.append(entry)

        sub_total = sum(u['total_submissions'] for u in user_data.values())
        disc_total = sum(u['total_discoveries'] for u in user_data.values())
        totals = {
            'total_submissions': sub_total,
            'total_discoveries': disc_total,
            'combined_total': sub_total + disc_total,
            'participants': len(user_data),
        }

    else:  # 'submissions' (default)
        cursor.execute(f'''
            SELECT MAX(discovered_by) AS username,
                   COUNT(*) AS total_submissions,
                   MIN(created_at) AS first_submission,
                   MAX(created_at) AS last_submission
            FROM systems
            WHERE event_id = ?
            GROUP BY {_NORM}
            HAVING {_NORM} != 'unknown'
            ORDER BY total_submissions DESC
            LIMIT ?
        ''', (event_id, limit))
        for i, row in enumerate(cursor.fetchall(), start=1):
            entry = dict(row)
            entry['rank'] = i
            # All rows are already approved (live `systems`), so total == approved.
            # Kept so the shared LeaderboardTable (Total/Approved/Rate columns) renders.
            entry['approved'] = entry['total_submissions']
            entry['rejected'] = 0
            entry['approval_rate'] = 100.0
            leaderboard.append(entry)

        cursor.execute(f'''
            SELECT COUNT(*) AS total_submissions,
                   COUNT(DISTINCT CASE WHEN {_NORM} != 'unknown' THEN {_NORM} END) AS participants
            FROM systems WHERE event_id = ?
        ''', (event_id,))
        tr = cursor.fetchone()
        total_sub = tr['total_submissions'] or 0
        totals = {
            'total_submissions': total_sub,
            'total_approved': total_sub,
            'participants': tr['participants'] or 0,
        }

    return {'leaderboard': leaderboard, 'totals': totals}


# ============================================================================
# Admin / partner endpoints
# ============================================================================

@router.get('/api/events')
async def list_events(
    include_inactive: bool = False,
    session: Optional[str] = Cookie(None),
):
    """List events the caller can manage (their community's; super admin sees all).

    Counts are approved-only and event-linked. The pre-v1.90 leak — where a
    non-super admin with no resolved discord_tag saw every community's events —
    is closed by scoping to the caller's civ_tags and returning nothing when
    that list is empty.
    """
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail='Authentication required')

    is_super = session_data.get('user_type') == 'super_admin'
    civ_tags = _caller_civ_tags(session_data)

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        query = 'SELECT * FROM events WHERE 1=1'
        params: list = []

        if not is_super:
            if not civ_tags:
                return {'events': []}
            placeholders = ','.join(['?'] * len(civ_tags))
            query += f' AND discord_tag IN ({placeholders})'
            params.extend(civ_tags)

        if not include_inactive:
            query += ' AND is_active = 1'

        query += ' ORDER BY start_date DESC'
        cursor.execute(query, params)
        rows = cursor.fetchall()

        events = [_enrich_event(cursor, dict(row)) for row in rows]
        return {'events': events}
    finally:
        if conn:
            conn.close()


@router.get('/api/events/active')
async def list_active_events(
    discord_tag: Optional[str] = None,
    kind: Optional[str] = None,
    session: Optional[str] = Cookie(None),
):
    """Picker feed: events a submitter can currently enter.

    Public (no auth). Participation is GLOBAL (opt-in) — returns ALL events that
    are active AND whose date window currently contains today, regardless of
    which community the submitter is uploading under. Anyone can enter any active
    event; the hosting civ still owns it and the leaderboard counts by event_id.

    Query params:
      - discord_tag: OPTIONAL filter to one community's events (no longer a gate;
        omit it to list every active event, which is what the picker now does).
      - kind: 'submission' or 'discovery' — filters to events whose event_type
        scores that kind (a 'discoveries' event won't show for a system upload).
    """
    today = datetime.now(timezone.utc).date().isoformat()

    # Map the submission kind → acceptable event_type values.
    if kind == 'submission':
        type_filter = ('submissions', 'both')
    elif kind == 'discovery':
        type_filter = ('discoveries', 'both')
    else:
        type_filter = ('submissions', 'discoveries', 'both')

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        where = ['is_active = 1', 'start_date <= ?', 'end_date >= ?']
        params: list = [today, today]

        # Optional single-community filter; omitted by the picker so every active
        # event is enterable by anyone (global opt-in).
        if discord_tag:
            where.append('discord_tag = ?')
            params.append(discord_tag)

        type_ph = ','.join(['?'] * len(type_filter))
        where.append(f'event_type IN ({type_ph})')
        params.extend(type_filter)

        cursor.execute(
            'SELECT id, name, discord_tag, start_date, end_date, event_type, description '
            f'FROM events WHERE {" AND ".join(where)} ORDER BY end_date ASC LIMIT 100',
            params,
        )
        events = [dict(r) for r in cursor.fetchall()]
        return {'events': events}
    finally:
        if conn:
            conn.close()


@router.post('/api/events')
async def create_event(request: Request, session: Optional[str] = Cookie(None)):
    """Create an event. Partners create for their own community; super admins
    can target any community via discord_tag."""
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail='Authentication required')

    is_super = session_data.get('user_type') == 'super_admin'
    civ_tags = _caller_civ_tags(session_data)

    body = await request.json()
    name = (body.get('name') or '').strip()
    discord_tag = body.get('discord_tag')
    start_date = body.get('start_date')
    end_date = body.get('end_date')
    description = body.get('description', '')
    event_type = body.get('event_type', 'submissions')

    if event_type not in ('submissions', 'discoveries', 'both'):
        event_type = 'submissions'

    if not all([name, start_date, end_date]):
        raise HTTPException(status_code=400, detail='name, start_date, and end_date are required')

    if (end_date or '')[:10] < (start_date or '')[:10]:
        raise HTTPException(status_code=400, detail='end_date cannot be before start_date')

    if not is_super:
        # Partners can only create for a community they belong to.
        if not civ_tags:
            raise HTTPException(status_code=403, detail='Cannot create events without a community')
        if not discord_tag or discord_tag not in civ_tags:
            discord_tag = civ_tags[0]
    if not discord_tag:
        raise HTTPException(status_code=400, detail='Community (discord_tag) is required')

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO events (name, discord_tag, start_date, end_date, description, created_by, event_type)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (name, discord_tag, start_date, end_date, description,
              session_data.get('username'), event_type))
        conn.commit()
        return {'success': True, 'event_id': cursor.lastrowid}
    finally:
        if conn:
            conn.close()


@router.get('/api/events/{event_id}')
async def get_event(event_id: int, session: Optional[str] = Cookie(None)):
    """Get a single event by ID (community-scoped for non-super callers)."""
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail='Authentication required')

    is_super = session_data.get('user_type') == 'super_admin'
    civ_tags = _caller_civ_tags(session_data)

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM events WHERE id = ?', (event_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail='Event not found')
        event = dict(row)
        if not is_super and event['discord_tag'] not in civ_tags:
            raise HTTPException(status_code=403, detail='Access denied')
        return {'event': _enrich_event(cursor, event)}
    finally:
        if conn:
            conn.close()


@router.get('/api/events/{event_id}/leaderboard')
async def get_event_leaderboard(
    event_id: int,
    tab: str = 'submissions',
    limit: int = 50,
    session: Optional[str] = Cookie(None),
):
    """Approved-only leaderboard for an event (community-scoped)."""
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail='Authentication required')

    is_super = session_data.get('user_type') == 'super_admin'
    civ_tags = _caller_civ_tags(session_data)
    limit = max(1, min(limit, 200))

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM events WHERE id = ?', (event_id,))
        event_row = cursor.fetchone()
        if not event_row:
            raise HTTPException(status_code=404, detail='Event not found')
        event = dict(event_row)
        if not is_super and event['discord_tag'] not in civ_tags:
            raise HTTPException(status_code=403, detail='Access denied')

        result = _compute_leaderboard(cursor, event, tab, limit)
        return {'event': event, 'tab': tab, **result}
    finally:
        if conn:
            conn.close()


@router.put('/api/events/{event_id}')
async def update_event(event_id: int, request: Request, session: Optional[str] = Cookie(None)):
    """Update an event (name/dates/description/active/type). Community-scoped."""
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail='Authentication required')

    is_super = session_data.get('user_type') == 'super_admin'
    civ_tags = _caller_civ_tags(session_data)

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM events WHERE id = ?', (event_id,))
        event_row = cursor.fetchone()
        if not event_row:
            raise HTTPException(status_code=404, detail='Event not found')
        if not is_super and event_row['discord_tag'] not in civ_tags:
            raise HTTPException(status_code=403, detail='Access denied')

        body = await request.json()
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
            cursor.execute(f'UPDATE events SET {", ".join(updates)} WHERE id = ?', params)
            conn.commit()

        return {'success': True}
    finally:
        if conn:
            conn.close()


@router.delete('/api/events/{event_id}')
async def delete_event(event_id: int, session: Optional[str] = Cookie(None)):
    """Delete an event (community-scoped). The event_id stays stamped on any
    already-linked systems/discoveries (harmless dangling reference)."""
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail='Authentication required')

    is_super = session_data.get('user_type') == 'super_admin'
    civ_tags = _caller_civ_tags(session_data)

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM events WHERE id = ?', (event_id,))
        event_row = cursor.fetchone()
        if not event_row:
            raise HTTPException(status_code=404, detail='Event not found')
        if not is_super and event_row['discord_tag'] not in civ_tags:
            raise HTTPException(status_code=403, detail='Access denied')

        cursor.execute('DELETE FROM events WHERE id = ?', (event_id,))
        conn.commit()
        return {'success': True}
    finally:
        if conn:
            conn.close()


# ============================================================================
# Public endpoints (no auth) — read-only competition showcase
# ============================================================================

@router.get('/api/public/events')
async def public_list_events(discord_tag: Optional[str] = None):
    """Public list of active events (any community, or one via discord_tag).

    Only `is_active = 1` events are exposed — toggling an event inactive is how
    admins hide it from the public page. Each row carries approved-only counts
    and a computed status so the page can group Active / Upcoming / Past.
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        if discord_tag:
            cursor.execute(
                'SELECT * FROM events WHERE is_active = 1 AND discord_tag = ? ORDER BY start_date DESC',
                (discord_tag,),
            )
        else:
            cursor.execute('SELECT * FROM events WHERE is_active = 1 ORDER BY start_date DESC')
        events = [_enrich_event(cursor, dict(row)) for row in cursor.fetchall()]
        return {'events': events}
    finally:
        if conn:
            conn.close()


@router.get('/api/public/events/{event_id}')
async def public_get_event(event_id: int):
    """Public single-event detail (active events only)."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM events WHERE id = ? AND is_active = 1', (event_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail='Event not found')
        return {'event': _enrich_event(cursor, dict(row))}
    finally:
        if conn:
            conn.close()


@router.get('/api/public/events/{event_id}/leaderboard')
async def public_event_leaderboard(event_id: int, tab: str = 'submissions', limit: int = 50):
    """Public approved-only leaderboard for an active event."""
    limit = max(1, min(limit, 200))
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM events WHERE id = ? AND is_active = 1', (event_id,))
        event_row = cursor.fetchone()
        if not event_row:
            raise HTTPException(status_code=404, detail='Event not found')
        event = dict(event_row)
        result = _compute_leaderboard(cursor, event, tab, limit)
        return {'event': event, 'tab': tab, **result}
    finally:
        if conn:
            conn.close()
