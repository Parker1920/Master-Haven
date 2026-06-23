"""Co-submitted discovery drafts — the single, centralized path for discoveries
that ride along with a system submission.

A discovery bundled with a system (via the wizard) is carried on the system
payload as a `discoveries_draft` array. Each entry references its target
planet/moon by NAME, not DB id, because the planets/moons don't exist as rows
yet (a new system has no ids at submit time; even an edit rebuilds them). The
backend resolves those names to live ids at the moment the planets/moons are
inserted — the SAME helper for every caller:

  - Public/member submit  -> stored on pending_systems.discoveries_draft, then
    promoted by approve_system / batch approve when the system is approved.
  - Trusted direct save    -> promoted by save_system in the same transaction
    that inserts the system live.

There is intentionally ONE promotion code path (`_promote_draft_discoveries`)
and ONE validator (`_sanitize_discoveries_draft`). The previous split — where
trusted saves looped a separate /api/submit_discovery round-trip that only sent
a (frequently-null) numeric planet_id and had no name fallback — is what
silently unlinked co-submitted discoveries. Permission decides whether the
system (and its bundled discoveries) goes live now or to the pending queue; it
does NOT change how discoveries are attached or resolved.

Cap is intentionally low (20). The wizard would be unusable past that and the
JSON column would bloat pending_systems queries.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Optional

from constants import (
    get_discovery_type_slug,
    normalize_discovery_coords,
)

logger = logging.getLogger('control.room')

MAX_DISCOVERIES_DRAFT = 20
_DRAFT_LOCATION_TYPES = {'planet', 'moon', 'space'}


def _sanitize_discoveries_draft(raw) -> tuple[Optional[list], Optional[str]]:
    """Validate and normalize the incoming discoveries_draft payload.

    Returns (sanitized_list_or_None, error_string_or_None). When raw is
    missing or empty, returns (None, None) — no draft is fine. On any shape
    violation returns (None, error) so the caller can 400.
    """
    if raw is None:
        return None, None
    if not isinstance(raw, list):
        return None, "discoveries_draft must be a list"
    if len(raw) == 0:
        return None, None
    if len(raw) > MAX_DISCOVERIES_DRAFT:
        return None, f"discoveries_draft cannot exceed {MAX_DISCOVERIES_DRAFT} entries"
    out = []
    for i, entry in enumerate(raw):
        if not isinstance(entry, dict):
            return None, f"discoveries_draft[{i}] must be an object"
        dname = (entry.get('discovery_name') or '').strip()
        dtype = (entry.get('discovery_type') or '').strip()
        if not dname:
            return None, f"discoveries_draft[{i}].discovery_name is required"
        if not dtype:
            return None, f"discoveries_draft[{i}].discovery_type is required"
        loc = (entry.get('location_type') or 'planet').strip().lower()
        if loc not in _DRAFT_LOCATION_TYPES:
            return None, f"discoveries_draft[{i}].location_type must be planet/moon/space"
        # When location_type=space we always null both names regardless of
        # any stale state that leaked through the frontend.
        if loc == 'space':
            planet_name = None
            moon_name = None
        else:
            planet_name = (entry.get('planet_name') or '').strip() or None
            moon_name = (entry.get('moon_name') or '').strip() or None
            if loc == 'moon' and not moon_name:
                # Allow it through with null moon link — backend resolution
                # logs a warning and inserts NULL moon_id. The reviewer can
                # see the mismatch in the admin card.
                pass
        type_metadata = entry.get('type_metadata')
        if type_metadata is not None and not isinstance(type_metadata, dict):
            return None, f"discoveries_draft[{i}].type_metadata must be an object"
        # Surface coordinates — normalized/range-checked, nulled for space.
        latitude, longitude = normalize_discovery_coords(
            entry.get('latitude'), entry.get('longitude')
        )
        if loc == 'space':
            latitude, longitude = None, None
        out.append({
            'discovery_name': dname[:200],
            'discovery_type': dtype[:50],
            'description': (entry.get('description') or '') or None,
            'planet_name': planet_name,
            'moon_name': moon_name,
            'location_type': loc,
            'location_name': (entry.get('location_name') or '') or None,
            'latitude': latitude,
            'longitude': longitude,
            'photo_url': entry.get('photo_url') or None,
            'evidence_urls': entry.get('evidence_urls') or None,
            'type_metadata': type_metadata if type_metadata else None,
            'game_version': entry.get('game_version') or None,
            'submit_for_record': bool(entry.get('submit_for_record')),
        })
    return out, None


def _promote_draft_discoveries(cursor, system_id, submission, current_username,
                                 current_user_type=None, current_account_id=None):
    """Promote a pending submission's discoveries_draft into live `discoveries`.

    Called inside the same transaction that just inserted/updated the system
    and its planets/moons, before the commit. Each draft becomes one row in
    `discoveries` with status='approved' (analysis_status), inheriting
    submitter identity from the parent pending row.

    Resolution rules:
      - location_type='planet' → match planet_name against planets.name for
        this system_id. NULL planet_id on no match (logged).
      - location_type='moon'   → match (parent_planet_name, moon_name)
        against the planets×moons join for this system_id. NULL moon_id on
        no match (logged).
      - location_type='space'  → both NULL.

    `current_user_type` is plumbed through so the audit row's NOT NULL
    `approver_type` column gets a real value instead of NULL (which used
    to silently drop the audit insert).

    `submission` is a dict shaped like a pending_systems row. The two callers
    pass either the real pending row (approve path) or a row-shaped dict built
    from the save payload + session (trusted direct-save path) — same keys,
    same behavior. Returns (promoted, missing_links) counts for caller logging.
    """
    raw = submission.get('discoveries_draft')
    if not raw:
        return 0, 0
    try:
        drafts = json.loads(raw) if isinstance(raw, str) else raw
    except (json.JSONDecodeError, TypeError) as e:
        logger.warning(
            f"Discoveries_draft promote: malformed JSON on pending row "
            f"{submission.get('id')}: {e}"
        )
        return 0, 0
    if not drafts:
        return 0, 0

    # Build name → id maps for this system.
    cursor.execute(
        'SELECT id, name FROM planets WHERE system_id = ?',
        (system_id,)
    )
    planet_rows = cursor.fetchall()
    planet_id_by_name = {}
    for row in planet_rows:
        pname = row[1] if not hasattr(row, 'keys') else row['name']
        pid = row[0] if not hasattr(row, 'keys') else row['id']
        if pname:
            planet_id_by_name.setdefault(pname, pid)

    moon_id_by_parent_and_name = {}
    if planet_rows:
        # Walk each planet's moons. Cheap because there are typically <30
        # planet rows per system and a handful of moons each.
        for row in planet_rows:
            pname = row[1] if not hasattr(row, 'keys') else row['name']
            pid = row[0] if not hasattr(row, 'keys') else row['id']
            if not pname:
                continue
            cursor.execute('SELECT id, name FROM moons WHERE planet_id = ?', (pid,))
            for mrow in cursor.fetchall():
                mname = mrow[1] if not hasattr(mrow, 'keys') else mrow['name']
                mid = mrow[0] if not hasattr(mrow, 'keys') else mrow['id']
                if mname:
                    moon_id_by_parent_and_name.setdefault((pname, mname), mid)

    discord_tag = submission.get('discord_tag')
    profile_id = submission.get('submitter_profile_id')
    discord_username = (
        submission.get('personal_discord_username')
        or submission.get('submitted_by')
        or 'anonymous'
    )
    source = submission.get('source') or 'manual'
    # Co-submitted discoveries inherit the parent system's event so a system
    # tagged into an event drags its bundled discoveries into the same event.
    parent_event_id = submission.get('event_id')
    submission_iso = (
        submission.get('submission_date')
        or datetime.now(timezone.utc).isoformat()
    )

    promoted = 0
    missing_links = 0
    for entry in drafts:
        try:
            loc = entry.get('location_type') or 'space'
            planet_name = entry.get('planet_name')
            moon_name = entry.get('moon_name')
            planet_id_resolved = None
            moon_id_resolved = None
            if loc == 'planet' and planet_name:
                planet_id_resolved = planet_id_by_name.get(planet_name)
                if not planet_id_resolved:
                    missing_links += 1
                    logger.warning(
                        f"Discoveries_draft promote: pending {submission.get('id')} "
                        f"discovery '{entry.get('discovery_name')}' references unknown "
                        f"planet '{planet_name}' — inserting with NULL planet_id"
                    )
            elif loc == 'moon' and moon_name:
                # planet_name in the draft for a moon-targeted discovery
                # is the parent planet's name (qualifies the moon).
                key = (planet_name, moon_name)
                moon_id_resolved = moon_id_by_parent_and_name.get(key)
                if moon_id_resolved is None:
                    missing_links += 1
                    logger.warning(
                        f"Discoveries_draft promote: pending {submission.get('id')} "
                        f"discovery '{entry.get('discovery_name')}' references unknown "
                        f"moon '{planet_name}::{moon_name}' — inserting with NULL moon_id"
                    )
                # Also resolve planet_id for the parent (used by display joins
                # that show 'moon of <planet>' context).
                if planet_name:
                    planet_id_resolved = planet_id_by_name.get(planet_name)

            type_metadata = entry.get('type_metadata')
            type_metadata_json = (
                json.dumps(type_metadata)
                if isinstance(type_metadata, dict) and type_metadata
                else None
            )

            # `discoveries.description` is NOT NULL on the live schema (and a
            # handful of other columns) — coalesce to empty string here so a
            # draft with no description doesn't trip the constraint and get
            # silently swallowed by the outer try/except (Parker 2026-05-13).
            # Surface coordinates (sanitizer already range-checked + nulled
            # for space; re-normalize defensively in case an unsanitized
            # legacy draft blob is replayed).
            d_lat, d_lng = normalize_discovery_coords(
                entry.get('latitude'), entry.get('longitude')
            )
            if loc == 'space':
                d_lat, d_lng = None, None

            cursor.execute('''
                INSERT INTO discoveries (
                    discovery_type, discovery_name, system_id, planet_id, moon_id,
                    location_type, location_name, description, significance,
                    discovered_by, submission_timestamp,
                    mystery_tier, analysis_status, pattern_matches,
                    discord_user_id, discord_guild_id,
                    photo_url, evidence_url, type_slug, discord_tag, type_metadata,
                    profile_id, source, latitude, longitude, event_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                entry.get('discovery_type') or 'Unknown',
                entry.get('discovery_name'),
                system_id,
                planet_id_resolved,
                moon_id_resolved,
                loc,
                entry.get('location_name'),
                entry.get('description') or '',
                'Notable',
                discord_username,
                submission_iso,
                1,
                'approved',
                0,
                None,
                None,
                entry.get('photo_url'),
                entry.get('evidence_urls'),
                get_discovery_type_slug(entry.get('discovery_type') or ''),
                discord_tag,
                type_metadata_json,
                profile_id,
                source,
                d_lat,
                d_lng,
                parent_event_id,
            ))
            discovery_id = cursor.lastrowid
            promoted += 1

            # Audit row so the trail shows this discovery rode in with the
            # system approval rather than going through pending_discoveries.
            # approver_type / approver_username are NOT NULL on the audit
            # schema — fall back to 'auto' / 'system' if the caller didn't
            # plumb the approver context through (keeps the helper safe to
            # call from scripts).
            try:
                cursor.execute('''
                    INSERT INTO approval_audit_log
                    (timestamp, action, submission_type, submission_id, submission_name,
                     approver_username, approver_type, approver_account_id, approver_discord_tag,
                     submitter_username, submitter_account_id, submitter_type, submission_discord_tag, source)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    datetime.now(timezone.utc).isoformat(),
                    'discovery_auto_approved_with_system',
                    'discovery',
                    discovery_id,
                    entry.get('discovery_name'),
                    current_username or 'system',
                    current_user_type or 'auto',
                    current_account_id,
                    None,
                    discord_username,
                    submission.get('submitter_account_id'),
                    submission.get('submitter_account_type'),
                    discord_tag,
                    source,
                ))
            except Exception as audit_err:
                logger.warning(
                    f"Discoveries_draft promote: audit insert failed for "
                    f"draft '{entry.get('discovery_name')}': {audit_err}"
                )
        except Exception as e:
            logger.warning(
                f"Discoveries_draft promote: skipped draft "
                f"'{entry.get('discovery_name')}' on pending {submission.get('id')}: {e}"
            )

    return promoted, missing_links
