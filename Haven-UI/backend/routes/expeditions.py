"""Expeditions CRUD endpoints — Wizard v1 rebuild (May 2026).

Expeditions are community-scoped charting campaigns that group system
submissions under a named effort. The whole community can see their own
community's expeditions; logged-in members can pick one to tag follow-on
submissions with.

Tables: expeditions, system_coauthors (linked via systems.expedition_id).
"""

import logging
import re
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Cookie, HTTPException

from db import get_db_connection
from services.auth_service import get_session

logger = logging.getLogger('control.room')

router = APIRouter(tags=["expeditions"])


def _slugify(name: str) -> str:
    """Lowercase + hyphenated slug for URL use. Falls back to a timestamp."""
    s = (name or '').strip().lower()
    s = re.sub(r'[^\w\s-]', '', s)
    s = re.sub(r'[-\s_]+', '-', s).strip('-')
    if not s:
        s = f"expedition-{int(datetime.now(timezone.utc).timestamp())}"
    return s[:80]


@router.get('/api/expeditions')
async def list_expeditions(
    status: Optional[str] = None,
    discord_tag: Optional[str] = None,
    session: Optional[str] = Cookie(None),
):
    """List expeditions visible to the caller.

    Visibility rules (per Parker's Phase 1 decisions):
    - Logged-in users see expeditions for their community (session discord_tag).
    - Anonymous callers see only public 'active' expeditions tagged 'Voyager's Haven'
      (the default community) so the wizard's expedition picker degrades gracefully.
    - Super admins see everything.

    Query params:
    - status: filter by 'active' / 'completed' / 'archived' (default: all)
    - discord_tag: scope to a specific community (super admin only; ignored for partners)
    """
    session_data = get_session(session)
    is_super = session_data and session_data.get('user_type') == 'super_admin'
    # M-W5: scope by the full civ_tags list (from civilization_members), not
    # just the session's single "acting as" discord_tag. A sub-admin of two
    # civs should see both civs' expeditions, not just whichever tag the
    # session was minted with.
    caller_civ_tags = (session_data.get('civ_tags') or []) if session_data else []
    legacy_caller_tag = session_data.get('discord_tag') if session_data else None
    # Falls back to the legacy single tag for older sessions that haven't
    # picked up the v1.80.0 civ_memberships block yet.
    if not caller_civ_tags and legacy_caller_tag:
        caller_civ_tags = [legacy_caller_tag]

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        where = []
        params: list = []

        if status:
            where.append('e.status = ?')
            params.append(status)

        # Visibility scoping
        if is_super:
            if discord_tag:
                where.append('e.discord_tag = ?')
                params.append(discord_tag)
        elif caller_civ_tags:
            # Logged-in member: any expedition belonging to any civ they're a member of.
            placeholders = ','.join(['?'] * len(caller_civ_tags))
            where.append(f'e.discord_tag IN ({placeholders})')
            params.extend(caller_civ_tags)
        else:
            # Anonymous caller — show only the default community's active expeditions
            where.append("e.discord_tag = 'Voyager''s Haven'")
            where.append("e.status = 'active'")

        where_clause = ('WHERE ' + ' AND '.join(where)) if where else ''
        cursor.execute(f"""
            SELECT e.*, COUNT(s.id) AS system_count
            FROM expeditions e
            LEFT JOIN systems s ON s.expedition_id = e.id
            {where_clause}
            GROUP BY e.id
            ORDER BY e.status = 'active' DESC, e.created_at DESC
            LIMIT 200
        """, params)
        rows = cursor.fetchall()
        return {'expeditions': [dict(r) for r in rows]}
    except Exception as e:
        logger.exception("Failed to list expeditions")
        raise HTTPException(status_code=500, detail="Failed to list expeditions")
    finally:
        if conn:
            conn.close()


@router.get('/api/expeditions/{expedition_id}')
async def get_expedition(expedition_id: int, session: Optional[str] = Cookie(None)):
    """Return a single expedition with its system list."""
    session_data = get_session(session)
    is_super = session_data and session_data.get('user_type') == 'super_admin'
    caller_tag = session_data.get('discord_tag') if session_data else None

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM expeditions WHERE id = ?', (expedition_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail='Expedition not found')
        exp = dict(row)

        # Permission: must be super, the owning community, or the public default
        if not is_super:
            if caller_tag and exp.get('discord_tag') and exp['discord_tag'] != caller_tag:
                raise HTTPException(status_code=403, detail='Not visible to your community')

        cursor.execute(
            "SELECT id, name, galaxy, glyph_code, completeness_grade FROM systems "
            "WHERE expedition_id = ? ORDER BY created_at DESC",
            (expedition_id,)
        )
        exp['systems'] = [dict(r) for r in cursor.fetchall()]
        return exp
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to get expedition")
        raise HTTPException(status_code=500, detail="Failed to get expedition")
    finally:
        if conn:
            conn.close()


@router.post('/api/expeditions')
async def create_expedition(payload: dict, session: Optional[str] = Cookie(None)):
    """Create a new expedition.

    Auth: any logged-in user with a profile or partner/sub-admin/super-admin session.
    The expedition is auto-tagged with the caller's discord_tag (community).
    Anonymous callers cannot create expeditions.
    """
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail='Authentication required to create expeditions')

    name = (payload.get('name') or '').strip()
    if not name:
        raise HTTPException(status_code=400, detail='Expedition name is required')
    if len(name) > 100:
        raise HTTPException(status_code=400, detail='Expedition name must be 100 characters or less')

    description = (payload.get('description') or '').strip() or None
    discord_tag = payload.get('discord_tag') or session_data.get('discord_tag')
    is_super = session_data.get('user_type') == 'super_admin'

    # Non-super users can only create for their own community
    if not is_super and discord_tag != session_data.get('discord_tag'):
        discord_tag = session_data.get('discord_tag')

    if not discord_tag:
        # Default to Voyager's Haven if no community context
        discord_tag = "Voyager's Haven"

    owner_profile_id = session_data.get('profile_id')
    owner_username = session_data.get('username') or 'Unknown'

    now = datetime.now(timezone.utc).isoformat()
    base_slug = _slugify(name)

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Disambiguate slug if collision
        slug = base_slug
        attempt = 1
        while True:
            cursor.execute('SELECT 1 FROM expeditions WHERE slug = ?', (slug,))
            if not cursor.fetchone():
                break
            attempt += 1
            slug = f"{base_slug}-{attempt}"
            if attempt > 50:
                raise HTTPException(status_code=500, detail='Could not generate unique slug')

        cursor.execute("""
            INSERT INTO expeditions
            (name, slug, owner_profile_id, owner_username, discord_tag,
             status, description, started_at, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, 'active', ?, ?, ?, ?)
        """, (name, slug, owner_profile_id, owner_username, discord_tag,
              description, now, now, now))
        exp_id = cursor.lastrowid
        conn.commit()

        cursor.execute('SELECT * FROM expeditions WHERE id = ?', (exp_id,))
        return {'status': 'created', 'expedition': dict(cursor.fetchone())}
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to create expedition")
        raise HTTPException(status_code=500, detail="Failed to create expedition")
    finally:
        if conn:
            conn.close()


@router.put('/api/expeditions/{expedition_id}')
async def update_expedition(
    expedition_id: int,
    payload: dict,
    session: Optional[str] = Cookie(None),
):
    """Update an expedition's name/description/status.

    Only the owner (by profile_id or username) or super admin can update.
    """
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail='Authentication required')

    is_super = session_data.get('user_type') == 'super_admin'
    caller_profile = session_data.get('profile_id')
    caller_username = session_data.get('username')

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM expeditions WHERE id = ?', (expedition_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail='Expedition not found')
        exp = dict(row)

        owns_it = (
            caller_profile and exp.get('owner_profile_id') == caller_profile
        ) or (
            caller_username and exp.get('owner_username') == caller_username
        )
        if not is_super and not owns_it:
            raise HTTPException(status_code=403, detail='Only the owner or a super admin can edit this expedition')

        sets = []
        params = []
        if 'name' in payload:
            new_name = (payload['name'] or '').strip()
            if not new_name:
                raise HTTPException(status_code=400, detail='Expedition name cannot be empty')
            sets.append('name = ?')
            params.append(new_name)
        if 'description' in payload:
            sets.append('description = ?')
            params.append(payload['description'] or None)
        if 'status' in payload:
            new_status = payload['status']
            if new_status not in ('active', 'completed', 'archived'):
                raise HTTPException(status_code=400, detail='status must be active|completed|archived')
            sets.append('status = ?')
            params.append(new_status)
            if new_status in ('completed', 'archived') and not exp.get('ended_at'):
                sets.append('ended_at = ?')
                params.append(datetime.now(timezone.utc).isoformat())

        if not sets:
            return {'status': 'noop', 'expedition': exp}

        sets.append('updated_at = ?')
        params.append(datetime.now(timezone.utc).isoformat())
        params.append(expedition_id)

        cursor.execute(f"UPDATE expeditions SET {', '.join(sets)} WHERE id = ?", params)
        conn.commit()
        cursor.execute('SELECT * FROM expeditions WHERE id = ?', (expedition_id,))
        return {'status': 'updated', 'expedition': dict(cursor.fetchone())}
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to update expedition")
        raise HTTPException(status_code=500, detail="Failed to update expedition")
    finally:
        if conn:
            conn.close()
