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
from constants import LEADER_FEATURES

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


def _require_civ_manage_access(session, civ_id: int):
    """Resolve session and authorize managing a civ's roster.

    Allows a super admin (any civ) OR a leader/co_leader of THIS civ. This is
    what lets a civ's own leaders moderate their sub-admins (add / edit
    features / remove) from the Sub-Admins page without going through a super
    admin — mirroring the capability partners had on the legacy
    sub_admin_accounts page. Membership is read from the session
    (civ_memberships), so no extra DB hit.
    """
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail='Authentication required')
    if session_data.get('user_type') == 'super_admin':
        return session_data
    for m in session_data.get('civ_memberships') or []:
        if m.get('civ_id') == civ_id and m.get('is_leader_like'):
            return session_data
    raise HTTPException(status_code=403, detail='You must be a leader of this civilization to manage its members')


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

        # Case-insensitive uniqueness — pre-fix this was strict-case, so
        # `GHUB` and `ghub` could both exist simultaneously and split
        # submissions across casings. Filter queries are case-sensitive too,
        # so the split was silent.
        cur.execute("SELECT id, tag FROM civilizations WHERE LOWER(tag) = LOWER(?)", (tag,))
        existing = cur.fetchone()
        if existing:
            raise HTTPException(
                status_code=409,
                detail=f"A civilization with tag '{existing['tag']}' already exists (case-insensitive match)",
            )

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
        # Sync founder's features from the civ's enabled_features_default
        # (per-member override is NULL above, so the helper falls through
        # to the civ default). Same fix as the add_member path.
        _recompute_profile_features(cur, founder_profile_id)

        conn.commit()
        return {'status': 'ok', 'civ_id': civ_id, 'tag': tag}
    finally:
        if conn:
            conn.close()


@router.put('/api/civilizations/{civ_id}')
async def update_civilization(civ_id: int, payload: dict, session: Optional[str] = Cookie(None)):
    """Update civilization brand / defaults.

    Authorized for super admin OR a leader/co_leader of THIS civ — a leader
    can edit their own civ's brand (display name, color, theme), defaults, and
    the sub-admin feature template. Archiving / unarchiving (`is_active`) stays
    super-admin-only: it severs every member's access site-wide and hides all
    of the civ's data, which is a platform-level decision, not a leader one.
    """
    session_data = _require_civ_manage_access(session, civ_id)
    is_super = session_data.get('user_type') == 'super_admin'

    allowed = {
        'display_name', 'region_color', 'theme_settings',
        'enabled_features_default', 'default_reality', 'default_galaxy',
        'is_active',
    }
    updates = {}
    for k in allowed:
        if k in payload:
            updates[k] = payload[k]

    # The feature template (`enabled_features_default`) is a PERMISSION setting,
    # so it is super-admin-only. A civ leader manages the roster (add member,
    # change role, remove), NOT permissions — this stops a leader changing their
    # civ's feature set, and therefore stops them escalating their own or anyone
    # else's access. The frontend hides the grid for leaders; this is the
    # authoritative server-side guard. (War Room, also a member of this set, was
    # already leader-locked — this subsumes that.)
    if not is_super:
        updates.pop('enabled_features_default', None)

    if not updates:
        raise HTTPException(status_code=400, detail='No updatable fields provided')

    # Archive / unarchive is super-admin-only — a leader cannot deactivate
    # (or reactivate) their own civilization.
    if 'is_active' in updates and not is_super:
        raise HTTPException(status_code=403, detail='Only a super admin can archive or unarchive a civilization')

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

        # If the civ's default featureset changed OR the civ was deactivated,
        # every member's user_profiles.enabled_features is now stale. Re-sync
        # them so the change actually takes effect in their session on next
        # login. Only fans out when the affected fields are in the update.
        if 'enabled_features_default' in updates or 'is_active' in updates:
            cur.execute("SELECT DISTINCT profile_id FROM civilization_members WHERE civ_id = ?", (civ_id,))
            for (member_id,) in cur.fetchall():
                _recompute_profile_features(cur, member_id)
                # When archiving/unarchiving, tier must also be recomputed so
                # members drop to member/read-only (archive) or regain their
                # civ-derived tier (unarchive).
                if 'is_active' in updates:
                    _recompute_profile_tier(cur, member_id)

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

    Authorized for super admin or a leader/co_leader of this civ.
    """
    session_data = _require_civ_manage_access(session, civ_id)
    is_super = session_data.get('user_type') == 'super_admin'

    profile_id = payload.get('profile_id')
    role = payload.get('role', 'sub_admin')
    # Per-member feature overrides are a permission setting → super-admin-only.
    # A leader adds the member with a role; their access comes from the role
    # (leaders are full by role) or, for a sub-admin, the zero-perm default
    # below — a super admin grants features afterward.
    features = payload.get('enabled_features') if is_super else None
    cap = bool(payload.get('can_approve_personal_uploads', False))

    if not isinstance(profile_id, int):
        raise HTTPException(status_code=400, detail='profile_id (integer) is required')
    if role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail=f'role must be one of {VALID_ROLES}')

    # A new sub-admin starts with ZERO permissions until a leader explicitly
    # grants them — store an EMPTY override ([]), not NULL. NULL falls through
    # to the civ's enabled_features_default in _recompute_profile_features,
    # which is the silent "I added them and they could already approve" bug.
    # The civ default is kept as a one-click "Reset to civ default" opt-in, not
    # an auto-grant. Leaders / co_leaders are full-power BY ROLE and ignore this
    # column entirely, so we leave their override NULL.
    if features is None and role == 'sub_admin':
        features = []

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
              f"invited_by:{session_data.get('profile_id')}"))

        # H-CM2: recompute tier from the FULL membership set including the
        # row we just inserted. This is correct whether the profile is new
        # (was tier 4, now needs promotion) or was already tier 2 on
        # another civ (no demotion when adding them here as sub_admin).
        _recompute_profile_tier(cur, profile_id)
        # Sync enabled_features from civ memberships so the new member
        # actually has the access their role implies. Without this they'd
        # get tier=2 but features=[], which is the "I added them as leader
        # but they can't do anything" bug.
        _recompute_profile_features(cur, profile_id)

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


def _recompute_profile_features(cur, profile_id: int) -> None:
    """Sync user_profiles.enabled_features from civ memberships.

    Why this exists: tier alone isn't a permission — the session reads
    `user_profiles.enabled_features` (auth.py login query) and route guards
    check that list. A leader added via the new civ flow used to get
    tier=2 but features=[], so they had the right title and zero access.

    Semantics: union of effective features across all of the profile's
    ACTIVE civ memberships, where effective features per membership are:

      - leader / co_leader -> the full LEADER_FEATURES set, BY ROLE,
        regardless of the civ default or any per-member override. Leaders
        are full-power within their civ ("'leader' and 'co_leader' are
        functionally identical" — migration 1.80.0); their access must not
        hinge on whether the founder ticked the (sub-admin-framed,
        usually-empty) enabled_features_default checkboxes. This is the fix
        for "added them as leader but they can't see Approvals".

      - sub_admin -> per-member override (civilization_members.enabled_features)
        if set, else civ default (civilizations.enabled_features_default).
        Kept delegable/restrictable so a leader can hand a sub-admin a subset.
        A NEW sub-admin's override is seeded EMPTY ([]) by add_member, so they
        start with zero access until a leader explicitly grants it. 'war_room'
        is ALWAYS stripped from a sub-admin's effective set here — it is granted
        only via the civ-scoped check above, never via a per-member override, so
        a stray war_room in an override can't leak it out of civ scope.

    Inactive civs are skipped so a deactivated civ stops granting features.

    No memberships -> features cleared to [] (they're not a partner/
    sub-admin of anything; _recompute_profile_tier will set them to tier 4).

    Super admin (tier 1) is never touched — super admin permissions
    come from `user_type == 'super_admin'`, not the features list.
    """
    cur.execute("""
        SELECT cm.role, cm.enabled_features, c.enabled_features_default
        FROM civilization_members cm
        JOIN civilizations c ON c.id = cm.civ_id
        WHERE cm.profile_id = ? AND c.is_active = 1
    """, (profile_id,))

    union: set = set()
    for row in cur.fetchall():
        role, per_member_raw, default_raw = row[0], row[1], row[2]

        # Parse the civ default up front — needed both for the sub_admin path
        # below AND for the civ-scoped War Room grant (which applies to leaders
        # too, who otherwise skip the civ default).
        try:
            default = json.loads(default_raw) if default_raw else []
        except (TypeError, json.JSONDecodeError):
            default = []
        if not isinstance(default, list):
            default = []

        # War Room is CIV-SCOPED, not a by-role grant: every moderator of a civ
        # that has it enabled gets it; a leader of a civ WITHOUT it does not.
        # This is why 'war_room' is deliberately absent from LEADER_FEATURES
        # (see constants.py). Without this special-case a civ leader would see
        # the War Room of a civ that was never given the feature.
        if 'war_room' in default:
            union.add('war_room')

        if role in ('leader', 'co_leader'):
            # Full power by role — independent of civ default / override.
            union.update(LEADER_FEATURES)
            continue
        try:
            per_member = json.loads(per_member_raw) if per_member_raw else None
        except (TypeError, json.JSONDecodeError):
            per_member = None
        effective = per_member if per_member is not None else default
        if isinstance(effective, list):
            # A sub-admin can NEVER hold a feature the civ itself wasn't granted.
            # Cap the per-member override at the civ's enabled_features_default —
            # so granting (e.g.) csv_import to a sub-admin of a civ that doesn't
            # have csv_import is silently dropped, not honored. (war_room is
            # civ-scoped, handled above; excluded here regardless.) This is the
            # authoritative server-side ceiling: it holds no matter who set the
            # override or what the UI offered.
            default_set = set(default)
            union.update(f for f in effective if f != 'war_room' and f in default_set)

    cur.execute(
        "UPDATE user_profiles SET enabled_features = ? WHERE id = ? AND tier != 1",
        (json.dumps(sorted(union)), profile_id),
    )


@router.put('/api/civilizations/{civ_id}/members/{profile_id}')
async def update_member(civ_id: int, profile_id: int, payload: dict,
                        session: Optional[str] = Cookie(None)):
    """Change a member's role or per-member feature override.

    Promoting/demoting role also adjusts the user_profile's tier so the
    auth helpers continue to do the right thing — see _recompute_profile_tier
    for the multi-civ-correct logic.

    Authorized for super admin or a leader/co_leader of this civ.
    """
    session_data = _require_civ_manage_access(session, civ_id)
    is_super = session_data.get('user_type') == 'super_admin'

    updates = {}
    if 'role' in payload:
        if payload['role'] not in VALID_ROLES:
            raise HTTPException(status_code=400, detail=f'role must be one of {VALID_ROLES}')
        updates['role'] = payload['role']
    # Per-member feature overrides are a permission setting → super-admin-only.
    # A leader can change a member's role (and remove them), but not edit the
    # feature set — so a leader can never change their own or anyone's perms.
    if 'enabled_features' in payload and is_super:
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
        # Re-sync features whenever role OR enabled_features changes. Role
        # change can flip them between civ-default and per-member-override
        # bucket downstream readers care about; explicit features override
        # has to propagate to user_profiles.enabled_features (the session
        # source).
        if 'role' in updates or 'enabled_features' in updates:
            _recompute_profile_features(cur, profile_id)

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

    Authorized for super admin or a leader/co_leader of this civ.
    """
    _require_civ_manage_access(session, civ_id)
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
        # Recompute features too — removing the row may strip access the
        # member used to have via this civ. Empty memberships -> features=[].
        _recompute_profile_features(cur, profile_id)

        cur.execute("SELECT COUNT(*) FROM civilization_members WHERE profile_id = ?", (profile_id,))
        remaining = cur.fetchone()[0]

        conn.commit()
        return {'status': 'ok', 'remaining_memberships': remaining}
    finally:
        if conn:
            conn.close()
