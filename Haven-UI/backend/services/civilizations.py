"""
Civilizations service — N:M membership lookup + scoping helpers.

Replaces the legacy 1:1 "one partner profile owns one discord_tag" model
introduced by `user_profiles.partner_discord_tag` with a proper civ entity
table + membership join table. See migration 1.80.0 for the schema.

A "civ" here is a `civilizations` row keyed on its immutable `tag` string
(the same string that's been on every `systems.discord_tag` since the
project started). Civ-level brand fields (display_name, region_color,
theme_settings, enabled_features_default) live on this row — they used
to live on a partner's user_profiles row.

This module is the single source of truth for "which civs does this user
belong to, and in what role?". Every scoping query (approvals, regions,
discoveries, war room, restrictions) consumes the helpers below instead
of branching on tier / partner_discord_tag / additional_discord_tags
manually.
"""

import json
import logging
from typing import Iterable, List, Optional

logger = logging.getLogger('control.room')


def load_memberships_for_profile(cursor, profile_id: int) -> List[dict]:
    """Return every civilization_members row for a profile, joined to the
    civilization row so brand + defaults are available to the session.

    Order: leader > co_leader > sub_admin, then by civilization name for
    stable UX. The first leader-role row wins as the default "active" civ
    when home_civ_id isn't set.
    """
    cursor.execute("""
        SELECT cm.civ_id, cm.role, cm.enabled_features, cm.can_approve_personal_uploads,
               c.tag, c.display_name, c.region_color, c.theme_settings,
               c.enabled_features_default, c.default_reality, c.default_galaxy,
               c.is_active
        FROM civilization_members cm
        JOIN civilizations c ON c.id = cm.civ_id
        WHERE cm.profile_id = ?
        ORDER BY
            CASE cm.role
                WHEN 'leader' THEN 0
                WHEN 'co_leader' THEN 1
                WHEN 'sub_admin' THEN 2
                ELSE 3
            END ASC,
            c.display_name ASC
    """, (profile_id,))

    result = []
    for row in cursor.fetchall():
        # JSON columns get parsed once at session-build time so route
        # handlers can read them as Python objects without re-parsing
        # every request.
        try:
            per_member_features = json.loads(row['enabled_features']) if row['enabled_features'] else None
        except (TypeError, json.JSONDecodeError):
            per_member_features = None
        try:
            default_features = json.loads(row['enabled_features_default']) if row['enabled_features_default'] else []
        except (TypeError, json.JSONDecodeError):
            default_features = []
        try:
            theme = json.loads(row['theme_settings']) if row['theme_settings'] else {}
        except (TypeError, json.JSONDecodeError):
            theme = {}

        # Effective features for this member on this civ: per-member
        # override wins when set, otherwise inherit the civ's default.
        effective_features = per_member_features if per_member_features is not None else default_features

        result.append({
            'civ_id': row['civ_id'],
            'tag': row['tag'],
            'display_name': row['display_name'],
            'region_color': row['region_color'],
            'theme_settings': theme,
            'role': row['role'],
            'is_leader_like': row['role'] in ('leader', 'co_leader'),
            'enabled_features': effective_features,
            'can_approve_personal_uploads': bool(row['can_approve_personal_uploads']),
            'default_reality': row['default_reality'],
            'default_galaxy': row['default_galaxy'],
            'civ_is_active': bool(row['is_active']),
        })
    return result


def pick_active_civ(memberships: List[dict], home_civ_id: Optional[int], requested_civ_id: Optional[int] = None) -> Optional[dict]:
    """Choose which civ the user is "acting as" right now.

    Priority:
      1. An explicit request (e.g. the `active_civ` cookie or
         `?active_civ=...` query param) — used by the "Acting as" selector.
      2. The user's home_civ_id setting.
      3. The first membership in priority order (leader > co_leader > sub_admin).

    Returns None when the user has zero active memberships.
    """
    active_only = [m for m in memberships if m['civ_is_active']]
    if not active_only:
        return None

    if requested_civ_id:
        match = next((m for m in active_only if m['civ_id'] == requested_civ_id), None)
        if match:
            return match

    if home_civ_id:
        match = next((m for m in active_only if m['civ_id'] == home_civ_id), None)
        if match:
            return match

    return active_only[0]


def civ_scope_filter(session_data: Optional[dict], column: str = 'discord_tag') -> tuple:
    """Build a SQL WHERE-clause fragment for civ-tag scoping.

    Returns (clause, params) suitable for splicing into an f-string and
    extending the query's parameter list.

    Cases:
      - Super admin: matches everything. Returns ('1=1', []).
      - Tier 2/3 with civ_tags: returns ('<col> IN (?, ?, ...)', tags).
      - Anyone else (member, anonymous): returns ('1=0', []) — no rows.

    The default column name is 'discord_tag' because that's how the legacy
    tag lives on systems / pending_systems / discoveries / regions /
    pending_region_names — every existing scoping query was already
    keyed on this column.
    """
    if not session_data:
        return ('1=0', [])

    if session_data.get('user_type') == 'super_admin':
        return ('1=1', [])

    tags = session_data.get('civ_tags') or []
    if not tags:
        return ('1=0', [])

    placeholders = ','.join(['?'] * len(tags))
    return (f"{column} IN ({placeholders})", list(tags))


def user_can_act_for_civ(session_data: Optional[dict], civ_tag: str) -> bool:
    """True if the current user belongs to the given civ in ANY role
    (leader, co_leader, or sub_admin), or is super admin.

    Used for data-restriction bypass and "acting as" validation — anywhere
    we need to ask "can this session do something on behalf of civ X?"
    without caring about which specific role they hold.
    """
    if not session_data:
        return False
    if session_data.get('user_type') == 'super_admin':
        return True
    tags = session_data.get('civ_tags') or []
    return civ_tag in tags


def user_is_leader_of(session_data: Optional[dict], civ_tag: str) -> bool:
    """True if the user is a leader-tier member (leader or co_leader) of
    the given civ. Used for leader-only actions like editing the civ's
    brand or adding/removing members.
    """
    if not session_data:
        return False
    if session_data.get('user_type') == 'super_admin':
        return True
    for m in session_data.get('civ_memberships') or []:
        if m.get('tag') == civ_tag and m.get('is_leader_like'):
            return True
    return False
