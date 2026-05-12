"""Civilization + civilization_members CRUD endpoints.

Powers the new CivilizationManagement page (replaces PartnerManagement). All
write endpoints are super-admin-only for now — the leader-tier "add a
co-leader to my own civ" UX comes in a follow-up; super admin is the
canonical path while we settle the schema.

Routes:
    GET    /api/civilizations                                — list all civs (+ member counts)
    GET    /api/civilizations/{civ_id}                       — full detail including members
    POST   /api/civilizations                                — create a new civ + add first leader
    PUT    /api/civilizations/{civ_id}                       — update brand / defaults
    POST   /api/civilizations/{civ_id}/members               — add a member
    PUT    /api/civilizations/{civ_id}/members/{profile_id}  — change role / features
    DELETE /api/civilizations/{civ_id}/members/{profile_id}  — remove a member
"""

import json
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Cookie, HTTPException

from db import get_db_connection
from services.auth_service import get_session

logger = logging.getLogger('control.room')
router = APIRouter(tags=["civilizations"])


def _require_super_admin(session):
    """Resolve session and 401/403 if not super admin."""
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail='Authentication required')
    if session_data.get('user_type') != 'super_admin':
        raise HTTPException(status_code=403, detail='Super admin only')
    return session_data


def _serialize_civ(row) -> dict:
    """Common shape for any endpoint returning a civilization."""
    try:
        theme = json.loads(row['theme_settings']) if row['theme_settings'] else {}
    except (TypeError, json.JSONDecodeError):
        theme = {}
    try:
        defaults = json.loads(row['enabled_features_default']) if row['enabled_features_default'] else []
    except (TypeError, json.JSONDecodeError):
        defaults = []
    return {
        'id': row['id'],
        'tag': row['tag'],
        'display_name': row['display_name'],
        'region_color': row['region_color'],
        'theme_settings': theme,
        'enabled_features_default': defaults,
        'default_reality': row['default_reality'],
        'default_galaxy': row['default_galaxy'],
        'founder_profile_id': row['founder_profile_id'],
        'founded_at': row['founded_at'],
        'is_active': bool(row['is_active']),
        'created_at': row['created_at'],
        'updated_at': row['updated_at'],
    }


def _serialize_member(row) -> dict:
    try:
        features = json.loads(row['enabled_features']) if row['enabled_features'] else None
    except (TypeError, json.JSONDecodeError):
        features = None
    return {
        'civ_id': row['civ_id'],
        'profile_id': row['profile_id'],
        'username': row['username'],
        'display_name': row['display_name'],
        'tier': row['tier'],
        'role': row['role'],
        'enabled_features': features,
        'can_approve_personal_uploads': bool(row['can_approve_personal_uploads']),
        'joined_at': row['joined_at'],
        'joined_via': row['joined_via'],
        'last_login_at': row['last_login_at'],
        'is_active': bool(row['is_active']),  # profile-active, not membership-active
    }


# ============================================================================
# LIST + DETAIL
# ============================================================================

@router.get('/api/civilizations')
async def list_civilizations(session: Optional[str] = Cookie(None)):
    """List all civilizations with member counts.

    Super admin sees all. Tier-2/3 users see only civs they belong to —
    enough to power the "switch acting civ" dropdown without leaking
    every civ on the site.
    """
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail='Authentication required')

    is_super = session_data.get('user_type') == 'super_admin'
    civ_ids = [m['civ_id'] for m in (session_data.get('civ_memberships') or [])]

    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        if is_super:
            cur.execute("""
                SELECT c.*,
                       (SELECT COUNT(*) FROM civilization_members WHERE civ_id = c.id) AS member_count,
                       (SELECT COUNT(*) FROM civilization_members WHERE civ_id = c.id AND role IN ('leader','co_leader')) AS leader_count,
                       (SELECT COUNT(*) FROM civilization_members WHERE civ_id = c.id AND role = 'sub_admin') AS sub_admin_count,
                       (SELECT COUNT(*) FROM systems WHERE discord_tag = c.tag) AS system_count
                FROM civilizations c
                ORDER BY c.is_active DESC, c.display_name ASC
            """)
        elif civ_ids:
            placeholders = ','.join(['?'] * len(civ_ids))
            cur.execute(f"""
                SELECT c.*,
                       (SELECT COUNT(*) FROM civilization_members WHERE civ_id = c.id) AS member_count,
                       (SELECT COUNT(*) FROM civilization_members WHERE civ_id = c.id AND role IN ('leader','co_leader')) AS leader_count,
                       (SELECT COUNT(*) FROM civilization_members WHERE civ_id = c.id AND role = 'sub_admin') AS sub_admin_count,
                       (SELECT COUNT(*) FROM systems WHERE discord_tag = c.tag) AS system_count
                FROM civilizations c
                WHERE c.id IN ({placeholders})
                ORDER BY c.is_active DESC, c.display_name ASC
            """, civ_ids)
        else:
            return {'civilizations': []}

        rows = cur.fetchall()
        out = []
        for r in rows:
            d = _serialize_civ(r)
            d['member_count'] = r['member_count']
            d['leader_count'] = r['leader_count']
            d['sub_admin_count'] = r['sub_admin_count']
            d['system_count'] = r['system_count']
            out.append(d)
        return {'civilizations': out}
    finally:
        if conn:
            conn.close()


@router.get('/api/civilizations/{civ_id}')
async def get_civilization(civ_id: int, session: Optional[str] = Cookie(None)):
    """Civilization detail + every member with profile metadata."""
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail='Authentication required')

    is_super = session_data.get('user_type') == 'super_admin'
    my_civ_ids = [m['civ_id'] for m in (session_data.get('civ_memberships') or [])]
    if not is_super and civ_id not in my_civ_ids:
        raise HTTPException(status_code=403, detail='You are not a member of this civilization')

    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM civilizations WHERE id = ?", (civ_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail='Civilization not found')

        civ = _serialize_civ(row)

        # Members joined to user_profiles for display fields. Leader-tier
        # rows come first, then sub_admin, then username alphabetically.
        cur.execute("""
            SELECT cm.civ_id, cm.profile_id, cm.role, cm.enabled_features,
                   cm.can_approve_personal_uploads, cm.joined_at, cm.joined_via,
                   up.username, up.display_name, up.tier, up.last_login_at, up.is_active
            FROM civilization_members cm
            JOIN user_profiles up ON up.id = cm.profile_id
            WHERE cm.civ_id = ?
            ORDER BY
                CASE cm.role
                    WHEN 'leader' THEN 0 WHEN 'co_leader' THEN 1
                    WHEN 'sub_admin' THEN 2 ELSE 3
                END ASC,
                up.username COLLATE NOCASE ASC
        """, (civ_id,))
        civ['members'] = [_serialize_member(r) for r in cur.fetchall()]
        return civ
    finally:
        if conn:
            conn.close()


# ============================================================================
# CREATE / UPDATE / DEACTIVATE (super admin only)
# ============================================================================

@router.post('/api/civilizations')
async def create_civilization(payload: dict, session: Optional[str] = Cookie(None)):
    """Create a new civilization and seat its first leader.

    Required fields: `tag`, `display_name`, `founder_profile_id`.
    Optional: `region_color`, `theme_settings`, `enabled_features_default`,
    `default_reality`, `default_galaxy`.
    """
    _require_super_admin(session)

    tag = (payload.get('tag') or '').strip()
    display_name = (payload.get('display_name') or '').strip() or tag
    founder_profile_id = payload.get('founder_profile_id')
    if not tag:
        raise HTTPException(status_code=400, detail='tag is required')
    if not isinstance(founder_profile_id, int):
        raise HTTPException(status_code=400, detail='founder_profile_id (integer) is required')

    region_color = payload.get('region_color') or '#00C2B3'
    theme = payload.get('theme_settings') or {}
    defaults = payload.get('enabled_features_default') or []
    default_reality = payload.get('default_reality')
    default_galaxy = payload.get('default_galaxy')

    now = datetime.now(timezone.utc).isoformat()
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("SELECT id FROM civilizations WHERE tag = ?", (tag,))
        if cur.fetchone():
            raise HTTPException(status_code=409, detail=f"A civilization with tag '{tag}' already exists")

        cur.execute("SELECT id, tier FROM user_profiles WHERE id = ? AND is_active = 1", (founder_profile_id,))
        founder = cur.fetchone()
        if not founder:
            raise HTTPException(status_code=400, detail='founder_profile_id does not exist or is inactive')

        cur.execute("""
            INSERT INTO civilizations (
                tag, display_name, region_color, theme_settings,
                enabled_features_default, default_reality, default_galaxy,
                founder_profile_id, founded_at, is_active, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
        """, (tag, display_name, region_color, json.dumps(theme),
              json.dumps(defaults), default_reality, default_galaxy,
              founder_profile_id, now, now))
        civ_id = cur.lastrowid

        # Promote the founder to tier 2 (partner) if they aren't already
        # leader-tier. They can still belong to other civs; this just
        # gives them the auth tier needed to act as a civ leader.
        if founder['tier'] not in (1, 2):
            cur.execute("UPDATE user_profiles SET tier = 2 WHERE id = ?", (founder_profile_id,))

        # Add founder as leader
        cur.execute("""
            INSERT INTO civilization_members
                (civ_id, profile_id, role, enabled_features, can_approve_personal_uploads,
                 joined_at, joined_via)
            VALUES (?, ?, 'leader', NULL, 0, ?, 'founder')
        """, (civ_id, founder_profile_id, now))

        conn.commit()
        return {'status': 'ok', 'civ_id': civ_id, 'tag': tag}
    finally:
        if conn:
            conn.close()


@router.put('/api/civilizations/{civ_id}')
async def update_civilization(civ_id: int, payload: dict, session: Optional[str] = Cookie(None)):
    """Update civilization brand / defaults. Super admin only for now —
    leader-edit path can be added later by checking user_is_leader_of."""
    _require_super_admin(session)

    allowed = {
        'display_name', 'region_color', 'theme_settings',
        'enabled_features_default', 'default_reality', 'default_galaxy',
        'is_active',
    }
    updates = {}
    for k in allowed:
        if k in payload:
            updates[k] = payload[k]
    if not updates:
        raise HTTPException(status_code=400, detail='No updatable fields provided')

    # JSON columns
    for k in ('theme_settings', 'enabled_features_default'):
        if k in updates and not isinstance(updates[k], str):
            updates[k] = json.dumps(updates[k])

    set_clause = ', '.join(f"{k} = ?" for k in updates) + ", updated_at = ?"
    params = list(updates.values()) + [datetime.now(timezone.utc).isoformat(), civ_id]

    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(f"UPDATE civilizations SET {set_clause} WHERE id = ?", params)
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail='Civilization not found')
        conn.commit()
        return {'status': 'ok', 'civ_id': civ_id, 'updated_fields': list(updates.keys())}
    finally:
        if conn:
            conn.close()


# ============================================================================
# MEMBERS
# ============================================================================

VALID_ROLES = ('leader', 'co_leader', 'sub_admin')


@router.post('/api/civilizations/{civ_id}/members')
async def add_member(civ_id: int, payload: dict, session: Optional[str] = Cookie(None)):
    """Add a user_profile as a member of a civilization.

    Required: `profile_id`. Optional: `role` (default `sub_admin`),
    `enabled_features` (per-member override JSON list), `can_approve_personal_uploads`.

    Adding as leader / co_leader auto-promotes the profile's tier to 2
    (partner) so the auth helpers treat them as full leaders. Adding as
    sub_admin promotes to tier 3 if they're below that today.
    """
    _require_super_admin(session)

    profile_id = payload.get('profile_id')
    role = payload.get('role', 'sub_admin')
    features = payload.get('enabled_features')
    cap = bool(payload.get('can_approve_personal_uploads', False))

    if not isinstance(profile_id, int):
        raise HTTPException(status_code=400, detail='profile_id (integer) is required')
    if role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail=f'role must be one of {VALID_ROLES}')

    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("SELECT id FROM civilizations WHERE id = ?", (civ_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail='Civilization not found')
        cur.execute("SELECT id, tier FROM user_profiles WHERE id = ? AND is_active = 1", (profile_id,))
        profile = cur.fetchone()
        if not profile:
            raise HTTPException(status_code=400, detail='Profile not found or inactive')

        cur.execute("SELECT 1 FROM civilization_members WHERE civ_id = ? AND profile_id = ?",
                    (civ_id, profile_id))
        if cur.fetchone():
            raise HTTPException(status_code=409, detail='That profile is already a member of this civilization')

        now = datetime.now(timezone.utc).isoformat()
        cur.execute("""
            INSERT INTO civilization_members
                (civ_id, profile_id, role, enabled_features, can_approve_personal_uploads,
                 joined_at, joined_via)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (civ_id, profile_id, role,
              json.dumps(features) if features is not None else None,
              1 if cap else 0, now,
              f"invited_by:{session_user_id(session)}"))

        # H-CM2: recompute tier from the FULL membership set including the
        # row we just inserted. This is correct whether the profile is new
        # (was tier 4, now needs promotion) or was already tier 2 on
        # another civ (no demotion when adding them here as sub_admin).
        _recompute_profile_tier(cur, profile_id)

        conn.commit()
        return {'status': 'ok', 'civ_id': civ_id, 'profile_id': profile_id, 'role': role}
    finally:
        if conn:
            conn.close()


def _count_civ_leaders(cur, civ_id: int) -> int:
    """Return how many leader-tier members (leader OR co_leader) a civ has."""
    cur.execute(
        "SELECT COUNT(*) FROM civilization_members WHERE civ_id = ? AND role IN ('leader','co_leader')",
        (civ_id,),
    )
    return cur.fetchone()[0]


def _recompute_profile_tier(cur, profile_id: int) -> None:
    """Recompute user_profiles.tier from the highest-priority remaining
    civilization_members row for this profile.

    H-CM2: avoids the multi-civ tier-sync bug where demoting a member on one
    civ would silently downgrade them even though they were still a leader
    on another civ. Single source of truth is the membership table.

    Tier mapping:
      leader / co_leader on ANY civ  -> tier 2 (partner)
      sub_admin on ANY civ           -> tier 3 (sub_admin)
      no remaining memberships       -> tier 4 (member)

    Super admin (tier 1) is never touched.
    """
    cur.execute(
        "SELECT role FROM civilization_members WHERE profile_id = ?",
        (profile_id,),
    )
    roles = {r[0] for r in cur.fetchall()}
    if 'leader' in roles or 'co_leader' in roles:
        target_tier = 2
    elif 'sub_admin' in roles:
        target_tier = 3
    else:
        target_tier = 4
    cur.execute(
        "UPDATE user_profiles SET tier = ? WHERE id = ? AND tier != 1",
        (target_tier, profile_id),
    )


@router.put('/api/civilizations/{civ_id}/members/{profile_id}')
async def update_member(civ_id: int, profile_id: int, payload: dict,
                        session: Optional[str] = Cookie(None)):
    """Change a member's role or per-member feature override.

    Promoting/demoting role also adjusts the user_profile's tier so the
    auth helpers continue to do the right thing — see _recompute_profile_tier
    for the multi-civ-correct logic.
    """
    _require_super_admin(session)

    updates = {}
    if 'role' in payload:
        if payload['role'] not in VALID_ROLES:
            raise HTTPException(status_code=400, detail=f'role must be one of {VALID_ROLES}')
        updates['role'] = payload['role']
    if 'enabled_features' in payload:
        f = payload['enabled_features']
        updates['enabled_features'] = json.dumps(f) if f is not None else None
    if 'can_approve_personal_uploads' in payload:
        updates['can_approve_personal_uploads'] = 1 if payload['can_approve_personal_uploads'] else 0

    if not updates:
        raise HTTPException(status_code=400, detail='No updatable fields provided')

    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        # Make sure the row exists first so 404 vs no-op is clear.
        cur.execute("SELECT role FROM civilization_members WHERE civ_id = ? AND profile_id = ?",
                    (civ_id, profile_id))
        existing = cur.fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail='Member not found in that civilization')

        # H-CM1: block demoting the last leader of a civ. Civs without at
        # least one leader-tier member lose their ability to manage their
        # own scope. Demoting from leader/co_leader to sub_admin counts.
        existing_role = existing[0]
        new_role = updates.get('role', existing_role)
        if (existing_role in ('leader', 'co_leader')
                and new_role not in ('leader', 'co_leader')):
            leader_count = _count_civ_leaders(cur, civ_id)
            if leader_count <= 1:
                raise HTTPException(
                    status_code=409,
                    detail='Cannot demote the last leader of a civilization. Promote another member to leader first.'
                )

        set_clause = ', '.join(f"{k} = ?" for k in updates)
        cur.execute(f"""
            UPDATE civilization_members
            SET {set_clause}
            WHERE civ_id = ? AND profile_id = ?
        """, list(updates.values()) + [civ_id, profile_id])

        # H-CM2: recompute tier from the FULL membership set, not just this
        # civ's row. Avoids stomping a tier 2 leader who's still a leader on
        # another civ when we change their role here to sub_admin.
        if 'role' in updates:
            _recompute_profile_tier(cur, profile_id)

        conn.commit()
        return {'status': 'ok', 'civ_id': civ_id, 'profile_id': profile_id,
                'updated_fields': list(updates.keys())}
    finally:
        if conn:
            conn.close()


@router.delete('/api/civilizations/{civ_id}/members/{profile_id}')
async def remove_member(civ_id: int, profile_id: int, session: Optional[str] = Cookie(None)):
    """Remove a member from a civilization.

    H-CM1: blocks removing the last leader of a civ. Other roles can be
    removed freely (a civ with no sub-admins is fine; a civ with no
    leaders is broken).

    Profile tier is recomputed from the full remaining membership set
    (H-CM2) so a multi-civ leader doesn't get accidentally demoted.
    """
    _require_super_admin(session)
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Look up the row first so we can enforce H-CM1 before deleting.
        cur.execute("SELECT role FROM civilization_members WHERE civ_id = ? AND profile_id = ?",
                    (civ_id, profile_id))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail='Member not found in that civilization')

        existing_role = row[0]
        if existing_role in ('leader', 'co_leader'):
            leader_count = _count_civ_leaders(cur, civ_id)
            if leader_count <= 1:
                raise HTTPException(
                    status_code=409,
                    detail='Cannot remove the last leader of a civilization. Promote another member to leader first.'
                )

        cur.execute("DELETE FROM civilization_members WHERE civ_id = ? AND profile_id = ?",
                    (civ_id, profile_id))

        # Recompute tier from remaining memberships.
        _recompute_profile_tier(cur, profile_id)

        cur.execute("SELECT COUNT(*) FROM civilization_members WHERE profile_id = ?", (profile_id,))
        remaining = cur.fetchone()[0]

        conn.commit()
        return {'status': 'ok', 'remaining_memberships': remaining}
    finally:
        if conn:
            conn.close()


# Tiny helper to grab the acting user's profile id for audit context.
def session_user_id(session_token: Optional[str]) -> Optional[int]:
    sd = get_session(session_token)
    return sd.get('profile_id') if sd else None
