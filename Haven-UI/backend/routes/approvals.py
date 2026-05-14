"""System approval workflow endpoints - submit, list, approve, reject, batch, extraction."""

import json
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Cookie, Header, HTTPException, Request
from fastapi.responses import JSONResponse

from constants import (
    normalize_discord_username,
    validate_galaxy,
    validate_reality,
    normalize_reality,
    GALAXY_BY_INDEX,
    resolve_source,
    get_discovery_type_slug,
)
from db import (
    get_db_path,
    get_db_connection,
    add_activity_log,
    find_matching_system,
    find_matching_pending_system,
    build_mismatch_flags,
    merge_system_data,
    get_system_glyph,
)
from glyph_decoder import (
    decode_glyph_to_coords,
    encode_coords_to_glyph,
    validate_glyph_code,
    is_in_core_void,
    is_phantom_star,
    get_system_classification,
    galactic_coords_to_glyph,
)
from services.coauthors import persist_system_coauthors
from services.auth_service import (
    get_session,
    verify_session,
    check_self_coauthor,
    require_feature,
    check_self_submission,
    get_submitter_identity,
    verify_api_key,
    get_or_create_profile,
    normalize_username_for_dedup,
)
from services.completeness import (
    calculate_completeness_score,
    update_completeness_score,
)
from services.civilizations import civ_scope_filter
from services.dispatch import fire_and_forget

logger = logging.getLogger('control.room')

router = APIRouter(tags=["approvals"])


# ============================================================================
# Co-submitted discovery drafts (Wizard v1.64.0)
# ============================================================================
#
# The wizard public submit path attaches an array of in-progress discoveries
# to a system submission. Each entry references the target planet/moon by
# NAME (not DB id) because the planets don't exist as rows yet — they're
# embedded inside the submission's system_data blob and only get IDs at
# approval time.
#
# Cap is intentionally low (20). The wizard would be unusable past that and
# the JSON column would bloat pending_systems queries.
# ============================================================================

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
        out.append({
            'discovery_name': dname[:200],
            'discovery_type': dtype[:50],
            'description': (entry.get('description') or '') or None,
            'planet_name': planet_name,
            'moon_name': moon_name,
            'location_type': loc,
            'location_name': (entry.get('location_name') or '') or None,
            'photo_url': entry.get('photo_url') or None,
            'evidence_urls': entry.get('evidence_urls') or None,
            'type_metadata': type_metadata if type_metadata else None,
            'game_version': entry.get('game_version') or None,
            'submit_for_record': bool(entry.get('submit_for_record')),
        })
    return out, None


def _promote_draft_discoveries(cursor, system_id, submission, current_username):
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

    Returns (promoted, missing_links) counts for caller logging.
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

            cursor.execute('''
                INSERT INTO discoveries (
                    discovery_type, discovery_name, system_id, planet_id, moon_id,
                    location_type, location_name, description, significance,
                    discovered_by, submission_timestamp,
                    mystery_tier, analysis_status, pattern_matches,
                    discord_user_id, discord_guild_id,
                    photo_url, evidence_url, type_slug, discord_tag, type_metadata,
                    profile_id, source
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                entry.get('discovery_type'),
                entry.get('discovery_name'),
                system_id,
                planet_id_resolved,
                moon_id_resolved,
                loc,
                entry.get('location_name'),
                entry.get('description'),
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
            ))
            discovery_id = cursor.lastrowid
            promoted += 1

            # Audit row so the trail shows this discovery rode in with the
            # system approval rather than going through pending_discoveries.
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
                    current_username,
                    None,
                    None,
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


# ============================================================================
# SYSTEM APPROVALS QUEUE - API Endpoints
# ============================================================================

def validate_system_data(system: dict) -> tuple[bool, str]:
    """Validate system data before accepting submission. Returns (is_valid, error_message)."""
    # Required fields
    if not system.get('name') or not isinstance(system['name'], str) or not system['name'].strip():
        return False, "System name is required"

    # Name length
    if len(system['name']) > 100:
        return False, "System name must be 100 characters or less"

    # Glyph code is required and must be exactly 12 hex characters
    glyph = system.get('glyph_code', '')
    if not glyph or not isinstance(glyph, str) or not re.match(r'^[0-9A-Fa-f]{12}$', glyph):
        return False, "Portal glyph code is required (exactly 12 hex characters)"

    # Sanitize and validate planets
    if 'planets' in system and system['planets']:
        if not isinstance(system['planets'], list):
            return False, "Planets must be a list"

        for i, planet in enumerate(system['planets']):
            if not isinstance(planet, dict):
                return False, f"Planet {i} is invalid"
            if not planet.get('name') or not planet['name'].strip():
                return False, f"Planet {i} is missing a name"

            # Validate moons if present
            if 'moons' in planet and planet['moons']:
                if not isinstance(planet['moons'], list):
                    return False, f"Planet {i} moons must be a list"
                for j, moon in enumerate(planet['moons']):
                    if not isinstance(moon, dict):
                        return False, f"Planet {i} moon {j} is invalid"
                    if not moon.get('name') or not moon['name'].strip():
                        return False, f"Planet {i} moon {j} is missing a name"

    return True, ""


@router.post('/api/submit_system')
async def submit_system(
    payload: dict,
    request: Request,
    background_tasks: BackgroundTasks,
    session: Optional[str] = Cookie(None),
    x_api_key: Optional[str] = Header(None, alias='X-API-Key')
):
    """
    Submit a system for approval.
    Accepts system data and queues it for admin review.

    Authentication:
    - Admin session: Exempt from rate limiting
    - API key: Uses API key's rate limit (default 200/hour)
    - None: IP-based rate limiting (15/hour)

    New fields supported (for NMS Save Watcher companion app):
    - star_type: Yellow, Red, Green, Blue, Purple
    - economy_type: Trading, Mining, Technology, etc.
    - economy_level: Low, Medium, High
    - conflict_level: Low, Medium, High
    - discovered_by: Original discoverer username
    - discovered_at: ISO timestamp of discovery
    """
    # Get client IP for logging
    client_ip = request.client.host if request.client else "unknown"

    # Check authentication method
    is_admin = verify_session(session)
    api_key_info = verify_api_key(x_api_key) if x_api_key else None

    # Determine source for tracking via the canonical resolver in constants.py
    api_key_name = api_key_info['name'] if api_key_info else None
    source = resolve_source(api_key_name)

    # Validate system data
    is_valid, error_msg = validate_system_data(payload)
    if not is_valid:
        raise HTTPException(status_code=400, detail=error_msg)

    # Validate optional co-submitted discoveries draft (Wizard v1.64.0).
    # If invalid, reject the whole submission — silently dropping the array
    # is exactly the failure mode this column was added to fix.
    discoveries_draft_clean, draft_err = _sanitize_discoveries_draft(
        payload.get('discoveries_draft')
    )
    if draft_err:
        raise HTTPException(status_code=400, detail=draft_err)
    # Pop the field so it isn't double-stored inside system_data JSON too.
    if 'discoveries_draft' in payload:
        payload.pop('discoveries_draft', None)

    # Classify system (phantom star and core void detection)
    # Note: We no longer block submissions - just classify and warn
    x = payload.get('x')
    y = payload.get('y')
    z = payload.get('z')
    solar_system = payload.get('glyph_solar_system', 1)

    classification_info = None
    warnings = []

    if x is not None and y is not None and z is not None:
        classification_info = get_system_classification(x, y, z, solar_system)

        # Add classification flags to payload for storage
        payload['is_phantom'] = classification_info['is_phantom']
        payload['is_in_core'] = classification_info['is_in_core']
        payload['classification'] = classification_info['classification']

        # Build warning messages
        if classification_info['is_phantom']:
            warnings.append(
                f"PHANTOM STAR: SSS index {solar_system} (0x{solar_system:03X}) indicates a phantom star. "
                f"These systems are not normally accessible via the Galactic Map."
            )

        if classification_info['is_in_core']:
            warnings.append(
                f"CORE VOID: Coordinates ({x}, {y}, {z}) are within the galactic core void "
                f"(~3,000 light years from center)."
            )

        if warnings:
            logger.info(f"System submission with special classification: {classification_info['classification']} - {'; '.join(warnings)}")

    # Extract metadata for indexing
    system_name = payload.get('name', 'Unnamed System')
    system_galaxy = payload.get('galaxy', 'Euclid')
    submitted_by = payload.get('submitted_by', 'Anonymous')
    system_id = payload.get('id')

    # Log whether this is an edit or new submission
    if system_id:
        logger.info(f"System submission is an EDIT of existing system ID: {system_id}")
    else:
        logger.info(f"System submission is a NEW system: {system_name}")

    # Store in pending_systems table
    conn = None
    try:
        db_path = get_db_path()
        # Use standardized connection settings with WAL mode
        conn = get_db_connection()
        cursor = conn.cursor()

        # Canonical dedup: last 11 glyph chars + galaxy + reality
        # Glyphs are required for manual submissions (validated above)
        glyph_code = payload.get('glyph_code')
        system_reality = normalize_reality(payload.get('reality'))
        existing_glyph_system = None
        mismatch_flags = []

        # Check approved systems
        if glyph_code:
            existing_glyph_row = find_matching_system(cursor, glyph_code, system_galaxy, system_reality)
            if existing_glyph_row:
                existing_glyph_system = {'id': existing_glyph_row[0], 'name': existing_glyph_row[1]}

                # Build mismatch flags by comparing against existing system data
                cursor.execute('SELECT * FROM systems WHERE id = ?', (existing_glyph_row[0],))
                existing_sys = cursor.fetchone()
                if existing_sys:
                    existing_dict = dict(existing_sys)
                    # Load existing planets for comparison
                    cursor.execute('SELECT name FROM planets WHERE system_id = ?', (existing_glyph_row[0],))
                    existing_dict['planets'] = [{'name': r['name']} for r in cursor.fetchall()]
                    moon_names = []
                    for p in cursor.execute('SELECT id FROM planets WHERE system_id = ?', (existing_glyph_row[0],)).fetchall():
                        for m in cursor.execute('SELECT name FROM moons WHERE planet_id = ?', (p[0],)).fetchall():
                            moon_names.append({'name': m['name']})
                    existing_dict['moons'] = moon_names
                    mismatch_flags = build_mismatch_flags(existing_dict, payload)

                if mismatch_flags:
                    warnings.append(
                        f"EXISTING SYSTEM: This updates '{existing_glyph_row[1]}' "
                        f"(same coordinates in {system_galaxy}/{system_reality}) but data differs: "
                        f"{'; '.join(mismatch_flags)}"
                    )
                elif existing_glyph_row[1] and existing_glyph_row[1].strip() != system_name.strip():
                    warnings.append(
                        f"EXISTING SYSTEM: This updates '{existing_glyph_row[1]}' "
                        f"(same coordinates in {system_galaxy}/{system_reality}). "
                        f"Name differs: '{system_name}'. Please verify before approving."
                    )
                else:
                    warnings.append(
                        f"EXISTING SYSTEM: This updates '{existing_glyph_row[1]}' "
                        f"(same coordinates in {system_galaxy}/{system_reality}). "
                        f"Approving will UPDATE the existing system."
                    )
                logger.info(f"Submission for '{system_name}' has glyph matching existing system '{existing_glyph_row[1]}' (ID: {existing_glyph_row[0]}) via last-11 + galaxy + reality")

        # Check pending systems for coordinate match
        if glyph_code and not existing_glyph_system:
            pending_row = find_matching_pending_system(cursor, glyph_code, system_galaxy, system_reality)
            if pending_row:
                warnings.append(
                    f"PENDING DUPLICATE: A submission for these coordinates is already pending "
                    f"as '{pending_row[1]}'. Submitting anyway for review."
                )

        # Extract discord_tag for filtering (partners only see their tagged submissions)
        # Priority: 1) Payload, 2) API key, 3) Logged-in user's session
        discord_tag = payload.get('discord_tag')
        if api_key_info and api_key_info.get('discord_tag') and not discord_tag:
            discord_tag = api_key_info['discord_tag']
            logger.info(f"Auto-tagging submission with API key's discord_tag: {discord_tag}")

        # Get submitter identity early so we can use their discord_tag for auto-tagging
        submitter_identity = get_submitter_identity(session)

        # If still no discord_tag, check if the logged-in user (partner or sub-admin) has one
        if not discord_tag and submitter_identity.get('discord_tag'):
            discord_tag = submitter_identity['discord_tag']
            logger.info(f"Auto-tagging submission with logged-in user's discord_tag: {discord_tag}")
        # Extract personal discord username for non-community submissions
        personal_discord_username = payload.get('personal_discord_username')

        # Determine if this is an edit (system has ID) or new submission
        # Glyph-based: if coordinates match an existing approved system, treat as edit
        edit_system_id = None
        if existing_glyph_system:
            edit_system_id = existing_glyph_system['id']
        elif system_id:
            # Legacy fallback: explicit system ID from frontend edit mode
            edit_system_id = system_id

        # Store mismatch flags in payload for approvers to see
        if mismatch_flags:
            payload['_mismatch_flags'] = mismatch_flags

        # Compute username_normalized using the same chain the analytics leaderboard uses
        # (submitted_by → personal_discord_username → discovered_by JSON → 'Unknown'),
        # via the canonical normalize_username_for_dedup helper. Stored at write time
        # so the leaderboard can GROUP BY an indexed column.
        _raw_for_norm = (
            submitter_identity['username'] if submitter_identity['username'] else submitted_by
        )
        if not _raw_for_norm or _raw_for_norm in ('Anonymous', 'anonymous'):
            _raw_for_norm = personal_discord_username or payload.get('discovered_by') or 'Unknown'
        username_normalized = normalize_username_for_dedup(_raw_for_norm)

        # ----- Wizard v1 fields (May 2026 rebuild) -----
        # game_version, submitter_notes, expedition_id are stored as dedicated
        # columns. coauthors[] stays in the system_data JSON blob; on approve
        # it expands into system_coauthors rows. conflict_resolution is a
        # transient per-field {field: 'mine'|'theirs'} map applied at approval
        # time — kept in the JSON blob for the approver to inspect.
        wizard_game_version = payload.get('game_version') or None
        wizard_submitter_notes = payload.get('submitter_notes') or None
        wizard_expedition_id = payload.get('expedition_id')
        try:
            wizard_expedition_id = int(wizard_expedition_id) if wizard_expedition_id else None
        except (TypeError, ValueError):
            wizard_expedition_id = None

        # Insert submission with source tracking, discord_tag, personal_discord_username,
        # edit tracking, submitter identity, wizard v1 fields, and (v1.64.0)
        # the co-submitted discoveries draft column.
        cursor.execute('''
            INSERT INTO pending_systems
            (submitted_by, submitted_by_ip, submission_date, system_data, status, system_name, system_region, galaxy, source, api_key_name, discord_tag, personal_discord_username, edit_system_id, submitter_account_id, submitter_account_type, submitter_profile_id, username_normalized, game_version, submitter_notes, expedition_id, discoveries_draft)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            submitter_identity['username'] if submitter_identity['username'] else submitted_by,
            client_ip,
            datetime.now(timezone.utc).isoformat(),
            json.dumps(payload),
            'pending',
            system_name,
            system_galaxy,
            system_galaxy,
            source,
            api_key_name,
            discord_tag,
            personal_discord_username,
            edit_system_id,
            submitter_identity['account_id'],
            submitter_identity['type'] if submitter_identity['type'] != 'anonymous' else None,
            submitter_identity.get('profile_id'),
            username_normalized,
            wizard_game_version,
            wizard_submitter_notes,
            wizard_expedition_id,
            json.dumps(discoveries_draft_clean) if discoveries_draft_clean else None,
        ))

        submission_id = cursor.lastrowid

        # ----- Deferred region name submission (Wizard v1 Option B) -----
        # The wizard now holds the proposed region name in local state and
        # ships it with the system payload so the user's discord identity
        # is attached. Only insert when the region is genuinely unnamed
        # AND has no pending name AND the caller actually included one.
        proposed_region_name_raw = payload.get('proposed_region_name')
        proposed_region_name = (
            proposed_region_name_raw.strip()
            if isinstance(proposed_region_name_raw, str) else ''
        )
        if proposed_region_name and payload.get('region_x') is not None:
            rx = payload.get('region_x')
            ry = payload.get('region_y')
            rz = payload.get('region_z')
            r_reality = normalize_reality(payload.get('reality'))
            r_galaxy = payload.get('galaxy', 'Euclid') or 'Euclid'

            try:
                cursor.execute('''
                    SELECT 1 FROM regions
                    WHERE region_x = ? AND region_y = ? AND region_z = ?
                      AND reality = ? AND galaxy = ?
                      AND custom_name IS NOT NULL
                ''', (rx, ry, rz, r_reality, r_galaxy))
                already_named = cursor.fetchone()

                cursor.execute('''
                    SELECT 1 FROM pending_region_names
                    WHERE region_x = ? AND region_y = ? AND region_z = ?
                      AND reality = ? AND galaxy = ?
                      AND status = 'pending'
                ''', (rx, ry, rz, r_reality, r_galaxy))
                already_pending = cursor.fetchone()

                if not already_named and not already_pending:
                    region_submitted_by = (
                        (personal_discord_username or '').strip()
                        or (submitter_identity.get('username') or '').strip()
                        or 'anonymous'
                    )
                    cursor.execute('''
                        INSERT INTO pending_region_names
                        (region_x, region_y, region_z, proposed_name,
                         submitted_by, submitted_by_ip, submission_date,
                         status, discord_tag, personal_discord_username,
                         reality, galaxy, submitter_profile_id, source)
                        VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?, ?, ?, ?)
                    ''', (
                        rx, ry, rz, proposed_region_name,
                        region_submitted_by, client_ip,
                        datetime.now(timezone.utc).isoformat(),
                        discord_tag, personal_discord_username,
                        r_reality, r_galaxy,
                        submitter_identity.get('profile_id'),
                        source,
                    ))
                    logger.info(
                        f"Deferred region name '{proposed_region_name}' queued for "
                        f"({rx},{ry},{rz})/{r_galaxy}/{r_reality} by {region_submitted_by}"
                    )
            except Exception as region_err:
                # A region-name failure must NOT block the system submission.
                logger.warning(f"Deferred region name insert failed: {region_err}")

        conn.commit()

        source_info = f" via {api_key_name}" if api_key_name else ""
        logger.info(f"New system submission: '{system_name}' (ID: {submission_id}) from {client_ip}{source_info}")

        # Activity log fires after the response — opens its own DB connection,
        # not part of the transactional guarantee. See services/dispatch.py.
        if source != 'manual':
            background_tasks.add_task(
                add_activity_log,
                'watcher_upload',
                f"System '{system_name}' uploaded via NMS Save Watcher",
                f"Galaxy: {system_galaxy}" + (f", API Key: {api_key_name}" if api_key_name else ""),
                submitted_by,
            )
        else:
            background_tasks.add_task(
                add_activity_log,
                'system_submitted',
                f"System '{system_name}' submitted for approval",
                f"Galaxy: {system_galaxy}",
                submitted_by,
            )

        response = {
            'status': 'ok',
            'message': 'System submitted for approval',
            'submission_id': submission_id,
            'system_name': system_name
        }

        # Add classification info to response if available
        if classification_info:
            response['classification'] = classification_info['classification']
            response['is_phantom'] = classification_info['is_phantom']
            response['is_in_core'] = classification_info['is_in_core']

        # Add warnings if any
        if warnings:
            response['warnings'] = warnings

        # Add existing system info if this will be an edit
        if existing_glyph_system:
            response['existing_system'] = existing_glyph_system
            response['message'] = f"System submitted for approval (will update existing system: '{existing_glyph_system['name']}')"

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error saving submission: {e}")
        logger.exception("Failed to save submission")
        raise HTTPException(status_code=500, detail="Failed to save submission")
    finally:
        if conn:
            conn.close()


@router.get('/api/pending_systems')
async def get_pending_systems(session: Optional[str] = Cookie(None)):
    """
    Get pending system submissions (admin only).
    - Super admin: sees ALL submissions
    - Haven sub-admins: sees ALL submissions (they work for Haven)
    - Partners/partner sub-admins: see only submissions tagged with their discord_tag
    """
    # Verify admin session and get session data
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail="Admin authentication required")

    is_super = session_data.get('user_type') == 'super_admin'
    # Whether the user can approve personal uploads. Was historically only
    # set on Haven sub-admins; with civilizations, any membership row can
    # carry this flag (set per-civ on the civilization_members row).
    can_approve_personal = bool(
        session_data.get('can_approve_personal_uploads', False)
        or any(m.get('can_approve_personal_uploads')
               for m in (session_data.get('civ_memberships') or []))
    )

    conn = None
    try:
        db_path = get_db_path()
        conn = get_db_connection()
        cursor = conn.cursor()

        # Single scoping path (civ_scope_filter collapses the old 3-branch
        # super_admin / is_haven_sub_admin / partner mess into one query).
        # Personal-upload visibility ORs in when the user has it enabled.
        scope_clause, scope_params = civ_scope_filter(session_data, column='discord_tag')
        where_parts = [scope_clause]
        if can_approve_personal and not is_super:
            where_parts = [f"(({scope_clause}) OR discord_tag = 'personal')"]
        where_sql = ' AND '.join(where_parts) if where_parts else '1=1'

        cursor.execute(f'''
            SELECT id, submitted_by, submission_date, status, system_name, system_region, galaxy,
                   reviewed_by, review_date, rejection_reason, source, api_key_name, discord_tag,
                   personal_discord_username, edit_system_id, submitter_account_id, submitter_account_type
            FROM pending_systems
            WHERE {where_sql}
            ORDER BY
                CASE status
                    WHEN 'pending' THEN 1
                    WHEN 'approved' THEN 2
                    WHEN 'rejected' THEN 3
                END,
                submission_date DESC
        ''', scope_params)

        rows = cursor.fetchall()
        submissions = [dict(row) for row in rows]

        # For sub-admins, mark self-submissions (cannot approve their own)
        # Partners and super admins can self-approve (trusted community leaders who need to test the mod)
        is_partner = session_data.get('user_type') == 'partner'
        if not is_super and not is_partner:
            logged_in_username = normalize_discord_username(session_data.get('username', ''))
            logged_in_account_id = session_data.get('sub_admin_id') or session_data.get('partner_id')
            logged_in_account_type = session_data.get('user_type')

            def is_self_submission(sub):
                # Check by account ID first (most reliable)
                if sub.get('submitter_account_id') and sub.get('submitter_account_type'):
                    if (sub['submitter_account_id'] == logged_in_account_id and
                        sub['submitter_account_type'] == logged_in_account_type):
                        return True
                # Check by username against submitted_by (normalize to handle #XXXX discriminator)
                if sub.get('submitted_by') and normalize_discord_username(sub['submitted_by']) == logged_in_username:
                    return True
                # Check by username against personal_discord_username (normalize to handle #XXXX discriminator)
                if sub.get('personal_discord_username') and normalize_discord_username(sub['personal_discord_username']) == logged_in_username:
                    return True
                return False

            for sub in submissions:
                sub['is_self_submission'] = is_self_submission(sub)

        # Hide personal_discord_username for sub-admin-tier viewers (only
        # super admin and leader-tier members see contact info). Keeps the
        # legacy is_haven_sub_admin flag as the trigger, but generalizes
        # to "any sub_admin role on any of the user's civs" so the same
        # rule applies under the new civilizations model.
        is_haven_sub_admin = session_data.get('is_haven_sub_admin', False)
        viewer_is_sub_admin_only = (
            session_data.get('user_type') == 'sub_admin'
            or is_haven_sub_admin
            or (
                session_data.get('user_type') not in ('super_admin', 'partner')
                and all(m.get('role') == 'sub_admin'
                        for m in (session_data.get('civ_memberships') or []))
                and bool(session_data.get('civ_memberships'))
            )
        )
        if viewer_is_sub_admin_only:
            for submission in submissions:
                submission['personal_discord_username'] = None

        return {'submissions': submissions}

    except Exception as e:
        logger.error(f"Error fetching pending systems: {e}")
        logger.exception("Failed to fetch submissions")
        raise HTTPException(status_code=500, detail="Failed to fetch submissions")
    finally:
        if conn:
            conn.close()


@router.get('/api/pending_systems/count')
async def get_pending_count(session: Optional[str] = Cookie(None)):
    """
    Get count of pending submissions for badge display.
    - Super admin: sees count of ALL pending
    - Haven sub-admins: sees count of "Haven" tagged submissions (minus self-submissions)
    - Partners/partner sub-admins: sees count of only their discord_tag submissions (minus self-submissions)
    - Not logged in: sees count of ALL pending
    Must be defined BEFORE /api/pending_systems/{submission_id} to avoid route conflict.
    """
    # Get session data if available (for partner filtering)
    session_data = get_session(session) if session else None
    is_super = session_data and session_data.get('user_type') == 'super_admin'
    is_haven_sub_admin = session_data.get('is_haven_sub_admin', False) if session_data else False
    partner_tag = session_data.get('discord_tag') if session_data else None

    conn = None
    try:
        db_path = get_db_path()
        conn = get_db_connection()
        cursor = conn.cursor()

        # For non-super-admins, exclude self-submissions in SQL rather than loading
        # every pending row into Python. This endpoint is polled every 60s by every
        # admin's navbar; the previous implementation grew linearly with the queue.
        if is_super or not session_data:
            cursor.execute("SELECT COUNT(*) FROM pending_systems WHERE status = 'pending'")
            system_count = cursor.fetchone()[0]
        else:
            logged_in_username = normalize_discord_username(session_data.get('username', ''))
            logged_in_account_id = session_data.get('sub_admin_id') or session_data.get('partner_id')
            logged_in_account_type = session_data.get('user_type')

            # Mirror normalize_discord_username() in SQL: lower(trim(split_on_hash(value))).
            # Re-used twice (submitted_by, personal_discord_username); duplicating the
            # CASE keeps each match a sargable expression on its own column.
            self_sub_clause = """
                NOT (
                    (submitter_account_id IS NOT NULL
                     AND submitter_account_type IS NOT NULL
                     AND submitter_account_id = ?
                     AND submitter_account_type = ?)
                    OR (submitted_by IS NOT NULL AND submitted_by != ''
                        AND LOWER(TRIM(CASE
                            WHEN INSTR(submitted_by, '#') > 0
                            THEN SUBSTR(submitted_by, 1, INSTR(submitted_by, '#') - 1)
                            ELSE submitted_by
                        END)) = ?)
                    OR (personal_discord_username IS NOT NULL AND personal_discord_username != ''
                        AND LOWER(TRIM(CASE
                            WHEN INSTR(personal_discord_username, '#') > 0
                            THEN SUBSTR(personal_discord_username, 1, INSTR(personal_discord_username, '#') - 1)
                            ELSE personal_discord_username
                        END)) = ?)
                )
            """
            self_params = [logged_in_account_id, logged_in_account_type,
                           logged_in_username, logged_in_username]

            scope_clause, scope_params = civ_scope_filter(session_data, column='discord_tag')
            # `1=0` means the user has no civ memberships at all → nothing
            # to count. Short-circuit so we don't run the query for free.
            if scope_clause == '1=0':
                system_count = 0
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
                cursor.execute(
                    f"SELECT COUNT(*) FROM pending_systems "
                    f"WHERE status = 'pending' AND {tag_clause} AND {self_sub_clause}",
                    scope_params + self_params,
                )
                system_count = cursor.fetchone()[0]

        # Count pending region names (these don't have discord_tag filtering yet)
        cursor.execute("SELECT COUNT(*) FROM pending_region_names WHERE status = 'pending'")
        region_count = cursor.fetchone()[0]

        # Return total count for badge display
        return {'count': system_count + region_count, 'systems': system_count, 'regions': region_count}

    except Exception as e:
        logger.error(f"Error getting pending count: {e}")
        return {'count': 0, 'systems': 0, 'regions': 0}
    finally:
        if conn:
            conn.close()


@router.get('/api/pending_systems/{submission_id}')
async def get_pending_system_details(submission_id: int, session: Optional[str] = Cookie(None)):
    """
    Get full details of a pending submission including system_data (admin only).
    """
    # Verify admin session
    if not verify_session(session):
        raise HTTPException(status_code=401, detail="Admin authentication required")

    # Check if Haven sub-admin (need to hide personal_discord_username)
    session_data = get_session(session)
    is_haven_sub_admin = session_data.get('is_haven_sub_admin', False) if session_data else False

    conn = None
    try:
        db_path = get_db_path()
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM pending_systems WHERE id = ?', (submission_id,))
        row = cursor.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Submission not found")

        submission = dict(row)
        # Parse JSON system_data
        if submission.get('system_data'):
            submission['system_data'] = json.loads(submission['system_data'])

        # Hide personal_discord_username for Haven sub-admins (only super admin sees contact info)
        if is_haven_sub_admin:
            submission['personal_discord_username'] = None

        return submission

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching submission details: {e}")
        logger.exception("Failed to fetch submission")
        raise HTTPException(status_code=500, detail="Failed to fetch submission")
    finally:
        if conn:
            conn.close()


@router.put('/api/pending_systems/{submission_id}')
async def edit_pending_system(submission_id: int, request: Request, session: Optional[str] = Cookie(None)):
    """
    Edit a pending system submission before approval (super admin only).
    Updates the system_data JSON and syncs top-level columns.
    """
    session_data = get_session(session)
    if not session_data or session_data.get('user_type') != 'super_admin':
        raise HTTPException(status_code=403, detail="Super admin access required")

    body = await request.json()
    updated_system_data = body.get('system_data')
    if not updated_system_data or not isinstance(updated_system_data, dict):
        raise HTTPException(status_code=400, detail="system_data object is required")

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM pending_systems WHERE id = ?', (submission_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Submission not found")

        submission = dict(row)
        if submission.get('status') != 'pending':
            raise HTTPException(status_code=400, detail="Only pending submissions can be edited")

        old_system_data = json.loads(submission.get('system_data', '{}'))
        old_name = old_system_data.get('name', '')
        new_name = updated_system_data.get('name', old_name)

        # Update the system_data JSON column and sync top-level system_name
        cursor.execute('''
            UPDATE pending_systems
            SET system_data = ?, system_name = ?
            WHERE id = ?
        ''', (json.dumps(updated_system_data), new_name, submission_id))

        # Audit log
        current_username = session_data.get('username', 'unknown')
        current_account_id = session_data.get('account_id')
        try:
            cursor.execute('''
                INSERT INTO approval_audit_log
                (timestamp, action, submission_type, submission_id, submission_name,
                 approver_username, approver_type, approver_account_id, approver_discord_tag,
                 submitter_username, submitter_account_id, submitter_type, notes, submission_discord_tag, source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                datetime.now(timezone.utc).isoformat(),
                'edit_pending',
                'system',
                submission_id,
                new_name,
                current_username,
                'super_admin',
                current_account_id,
                session_data.get('discord_tag'),
                submission.get('submitted_by'),
                submission.get('submitter_account_id'),
                submission.get('submitter_account_type'),
                f"Edited pending submission (old name: '{old_name}', new name: '{new_name}')",
                submission.get('discord_tag'),
                submission.get('source', 'manual')
            ))
        except Exception as audit_err:
            logger.warning(f"Failed to add audit log for edit: {audit_err}")

        conn.commit()
        logger.info(f"Super admin '{current_username}' edited pending submission {submission_id} ('{old_name}' -> '{new_name}')")

        # Return the updated submission
        cursor.execute('SELECT * FROM pending_systems WHERE id = ?', (submission_id,))
        updated_row = cursor.fetchone()
        result = dict(updated_row)
        if result.get('system_data'):
            result['system_data'] = json.loads(result['system_data'])
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error editing pending submission: {e}")
        logger.exception("Failed to edit submission")
        raise HTTPException(status_code=500, detail="Failed to edit submission")
    finally:
        if conn:
            conn.close()


@router.post('/api/approve_system/{submission_id}')
async def approve_system(
    submission_id: int,
    background_tasks: BackgroundTasks,
    session: Optional[str] = Cookie(None),
):
    """
    Approve a pending system submission and add it to the main database (admin only).
    Self-approval is blocked for non-super-admin users.

    Side effects (activity log, poster cache invalidation) run AFTER the response
    is returned — see services/dispatch.py. The audit_log INSERT inside the
    transaction stays inline because it's part of the transactional guarantee.
    """
    # Verify admin session
    if not verify_session(session):
        raise HTTPException(status_code=401, detail="Admin authentication required")

    # Get current user identity for self-approval check and audit
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
        db_path = get_db_path()
        conn = get_db_connection()
        cursor = conn.cursor()

        # Get submission
        cursor.execute('SELECT * FROM pending_systems WHERE id = ?', (submission_id,))
        row = cursor.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Submission not found")

        submission = dict(row)

        if submission['status'] != 'pending':
            raise HTTPException(
                status_code=400,
                detail=f"Submission already {submission['status']}"
            )

        # SELF-APPROVAL BLOCKING: prevents users from reviewing their own submissions.
        if check_self_submission(dict(submission), session_data):
            raise HTTPException(
                status_code=403,
                detail="You cannot approve your own submission. Another admin must review it."
            )

        # Parse system data
        system_data = json.loads(submission['system_data'])

        # H-C2: prevent co-authors from approving systems that credit them.
        # Independent of tier (a partner can still benefit from coauthor credit).
        if check_self_coauthor(system_data.get('coauthors') or [], session_data):
            raise HTTPException(
                status_code=403,
                detail="You are listed as a co-author on this submission. Another admin must review it."
            )

        # Normalize empty glyph_code to None (NULL) to avoid unique constraint issues
        # The unique index only applies WHERE glyph_code IS NOT NULL, so empty strings cause conflicts
        if not system_data.get('glyph_code'):
            system_data['glyph_code'] = None

        # Calculate star position AND region coordinates
        # IMPORTANT: Validate that glyph_code matches X/Y/Z coordinates
        # If they don't match, the X/Y/Z coordinates are authoritative (from in-game extraction)
        star_x, star_y, star_z = None, None, None
        region_x, region_y, region_z = None, None, None

        submission_x = system_data.get('x')
        submission_y = system_data.get('y')
        submission_z = system_data.get('z')
        original_glyph = system_data.get('glyph_code')

        # EARLY CHECK: For EDIT submissions with no glyph, fetch the original system's glyph
        # This MUST happen before any glyph calculation to preserve the correct glyph
        existing_system_id = system_data.get('id')
        if existing_system_id and not original_glyph:
            cursor.execute('SELECT glyph_code, glyph_planet, glyph_solar_system FROM systems WHERE id = ?', (existing_system_id,))
            existing_row = cursor.fetchone()
            if existing_row and existing_row[0]:
                original_glyph = existing_row[0]
                system_data['glyph_code'] = original_glyph
                system_data['glyph_planet'] = existing_row[1] or 0
                system_data['glyph_solar_system'] = existing_row[2] or 1
                logger.info(f"Edit submission {submission_id}: Preserved original glyph {original_glyph} from existing system {existing_system_id}")

        if original_glyph:
            try:
                decoded = decode_glyph_to_coords(original_glyph)
                glyph_x = decoded['x']
                glyph_y = decoded['y']
                glyph_z = decoded['z']

                # Check if glyph coordinates match submission coordinates
                # Allow some tolerance for floating point comparison
                coords_match = True
                if submission_x is not None and submission_y is not None and submission_z is not None:
                    # Compare with tolerance
                    if (abs(glyph_x - submission_x) > 1 or
                        abs(glyph_y - submission_y) > 1 or
                        abs(glyph_z - submission_z) > 1):
                        coords_match = False
                        logger.warning(f"Glyph/coordinate mismatch detected!")
                        logger.warning(f"  Glyph {original_glyph} decodes to: ({glyph_x}, {glyph_y}, {glyph_z})")
                        logger.warning(f"  Submission X/Y/Z: ({submission_x}, {submission_y}, {submission_z})")

                if coords_match:
                    # Glyph matches, use decoded values
                    star_x = decoded['star_x']
                    star_y = decoded['star_y']
                    star_z = decoded['star_z']
                    region_x = decoded.get('region_x')
                    region_y = decoded.get('region_y')
                    region_z = decoded.get('region_z')
                    logger.info(f"Glyph validated: region ({region_x}, {region_y}, {region_z})")
                else:
                    # Mismatch! Recalculate glyph from submission X/Y/Z coordinates
                    # X/Y/Z from extraction are more reliable than the glyph
                    logger.warning(f"Recalculating glyph from submission coordinates...")
                    planet_idx = decoded.get('planet', 0)
                    solar_idx = decoded.get('solar_system', 1)

                    corrected_glyph = encode_coords_to_glyph(
                        int(submission_x), int(submission_y), int(submission_z),
                        planet_idx, solar_idx
                    )
                    corrected_decoded = decode_glyph_to_coords(corrected_glyph)

                    # Update system_data with corrected glyph
                    system_data['glyph_code'] = corrected_glyph
                    star_x = corrected_decoded['star_x']
                    star_y = corrected_decoded['star_y']
                    star_z = corrected_decoded['star_z']
                    region_x = corrected_decoded.get('region_x')
                    region_y = corrected_decoded.get('region_y')
                    region_z = corrected_decoded.get('region_z')

                    logger.info(f"Corrected glyph: {original_glyph} -> {corrected_glyph}")
                    logger.info(f"Corrected region: ({region_x}, {region_y}, {region_z})")

            except Exception as e:
                logger.warning(f"Failed to validate/calculate glyph during approval: {e}")

        # If we have X/Y/Z but no glyph, calculate glyph from coordinates
        elif submission_x is not None and submission_y is not None and submission_z is not None:
            try:
                calculated_glyph = encode_coords_to_glyph(
                    int(submission_x), int(submission_y), int(submission_z), 0, 1
                )
                decoded = decode_glyph_to_coords(calculated_glyph)

                system_data['glyph_code'] = calculated_glyph
                star_x = decoded['star_x']
                star_y = decoded['star_y']
                star_z = decoded['star_z']
                region_x = decoded.get('region_x')
                region_y = decoded.get('region_y')
                region_z = decoded.get('region_z')

                logger.info(f"Calculated glyph from X/Y/Z: {calculated_glyph}")
                logger.info(f"Calculated region: ({region_x}, {region_y}, {region_z})")
            except Exception as e:
                logger.warning(f"Failed to calculate glyph from coordinates: {e}")

        # Always update system_data with calculated region coords
        if region_x is not None:
            system_data['region_x'] = region_x
        if region_y is not None:
            system_data['region_y'] = region_y
        if region_z is not None:
            system_data['region_z'] = region_z

        # Determine if this is an edit: canonical glyph-first dedup
        # Priority: 1) Glyph coordinates (last-11 + galaxy + reality) — authoritative
        #           2) edit_system_id from pending row — set during extraction/submission dedup
        #           3) system_data JSON 'id' field — legacy fallback from frontend edits
        submission_galaxy = system_data.get('galaxy', 'Euclid')
        submission_reality = system_data.get('reality', 'Normal')

        is_edit = False
        original_glyph_data = None
        original_discovered_by = None
        original_discovered_at = None
        original_contributors = None

        # Primary: glyph-based coordinate match
        if system_data.get('glyph_code'):
            existing_system_row = find_matching_system(
                cursor,
                system_data['glyph_code'],
                submission_galaxy,
                submission_reality
            )
            if existing_system_row:
                existing_name = existing_system_row[1]
                submitted_name = system_data.get('name', '').strip()

                if existing_name and submitted_name and existing_name.strip() != submitted_name:
                    logger.warning(f"Submission {submission_id}: glyph coordinates match existing system "
                                   f"'{existing_name}' but submitted name is '{submitted_name}' - "
                                   f"proceeding as edit (admin approved)")

                is_edit = True
                system_id = existing_system_row[0]
                original_glyph_data = {
                    'glyph_code': existing_system_row[2],
                    'glyph_planet': existing_system_row[3],
                    'glyph_solar_system': existing_system_row[4]
                }
                original_discovered_by = existing_system_row[5]
                original_discovered_at = existing_system_row[6]
                original_contributors = existing_system_row[7]
                logger.info(f"Submission {submission_id} matched existing system '{existing_name}' (ID: {system_id}) via glyph last-11 + galaxy + reality")

        # Fallback: edit_system_id from pending row or system_data JSON id
        if not is_edit:
            existing_system_id = submission.get('edit_system_id') or system_data.get('id')
            if existing_system_id:
                cursor.execute('''
                    SELECT id, glyph_code, glyph_planet, glyph_solar_system,
                           discovered_by, discovered_at, contributors
                    FROM systems WHERE id = ?
                ''', (existing_system_id,))
                existing_row = cursor.fetchone()
                if existing_row:
                    is_edit = True
                    system_id = existing_system_id
                    original_glyph_data = {
                        'glyph_code': existing_row[1],
                        'glyph_planet': existing_row[2],
                        'glyph_solar_system': existing_row[3]
                    }
                    original_discovered_by = existing_row[4]
                    original_discovered_at = existing_row[5]
                    original_contributors = existing_row[6]
                    logger.info(f"Submission {submission_id} is EDIT via ID fallback: {existing_system_id}")
                else:
                    logger.info(f"Submission {submission_id} has ID {existing_system_id} but not found in DB - treating as NEW")

        # For EDITS: If submission doesn't have glyph data, preserve the original
        if is_edit and original_glyph_data:
            if not system_data.get('glyph_code') and original_glyph_data.get('glyph_code'):
                system_data['glyph_code'] = original_glyph_data['glyph_code']
                system_data['glyph_planet'] = original_glyph_data.get('glyph_planet', 0)
                system_data['glyph_solar_system'] = original_glyph_data.get('glyph_solar_system', 1)
                logger.info(f"Preserved original glyph for edit: {system_data['glyph_code']}")

        if is_edit:
            # Determine the updater's username - personal_discord_username is the Discord name from the form
            updater_username = submission.get('personal_discord_username') or submission.get('submitted_by') or current_username or 'Unknown'
            now_iso = datetime.now(timezone.utc).isoformat()

            # Build updated contributors list (preserve original, add new edit entry)
            try:
                contributors_list = json.loads(original_contributors) if original_contributors else []
            except (json.JSONDecodeError, TypeError):
                contributors_list = []

            # Add edit entry (same person can appear multiple times with different edits)
            contributors_list.append({"name": updater_username, "action": "edit", "date": now_iso})

            # Wizard v1: copy game_version + expedition_id from pending row to systems
            wizard_game_version = (
                submission.get('game_version')
                or system_data.get('game_version')
            )
            wizard_expedition_id = (
                submission.get('expedition_id')
                or system_data.get('expedition_id')
            )

            # UPDATE existing system - PRESERVE discovered_by/discovered_at, UPDATE last_updated_by/last_updated_at
            cursor.execute('''
                UPDATE systems
                SET name = ?, galaxy = ?, x = ?, y = ?, z = ?,
                    star_x = ?, star_y = ?, star_z = ?,
                    description = ?,
                    glyph_code = ?, glyph_planet = ?, glyph_solar_system = ?,
                    region_x = ?, region_y = ?, region_z = ?,
                    star_type = ?, economy_type = ?, economy_level = ?,
                    conflict_level = ?, dominant_lifeform = ?,
                    discord_tag = ?, personal_discord_username = ?,
                    stellar_classification = ?,
                    last_updated_by = ?, last_updated_at = ?, contributors = ?,
                    game_version = COALESCE(?, game_version),
                    expedition_id = COALESCE(?, expedition_id)
                WHERE id = ?
            ''', (
                system_data.get('name'),
                system_data.get('galaxy', 'Euclid'),
                system_data.get('x', 0),
                system_data.get('y', 0),
                system_data.get('z', 0),
                star_x,
                star_y,
                star_z,
                system_data.get('description', ''),
                system_data.get('glyph_code'),
                system_data.get('glyph_planet', 0),
                system_data.get('glyph_solar_system', 1),
                system_data.get('region_x'),
                system_data.get('region_y'),
                system_data.get('region_z'),
                system_data.get('star_type') or system_data.get('star_color'),
                system_data.get('economy_type'),
                system_data.get('economy_level'),
                system_data.get('conflict_level'),
                system_data.get('dominant_lifeform'),
                submission.get('discord_tag'),
                submission.get('personal_discord_username'),
                system_data.get('stellar_classification'),
                updater_username,
                datetime.now(timezone.utc).isoformat(),
                json.dumps(contributors_list),
                wizard_game_version,
                wizard_expedition_id,
                system_id
            ))
            logger.info(f"Updated system {system_id}, preserving discovered_by='{original_discovered_by}', added contributor '{updater_username}'")

            # MERGE planets: Update existing by name, add new ones, keep others
            # First, get existing planets for this system
            cursor.execute('SELECT id, name FROM planets WHERE system_id = ?', (system_id,))
            existing_planets = {row[1]: row[0] for row in cursor.fetchall()}  # name -> id mapping

            # Track which planets we've processed (to keep unmentioned ones)
            processed_planet_names = set()
        else:
            # Generate UUID for new system
            system_id = str(uuid.uuid4())

            # Determine the discoverer's username - personal_discord_username is the Discord name from the form
            discoverer_username = submission.get('personal_discord_username') or submission.get('submitted_by') or 'Unknown'
            now_iso = datetime.now(timezone.utc).isoformat()

            # Wizard v1: pull game_version + expedition_id from pending row
            new_game_version = (
                submission.get('game_version')
                or system_data.get('game_version')
            )
            new_expedition_id = (
                submission.get('expedition_id')
                or system_data.get('expedition_id')
            )

            # INSERT new system (including new tracking fields + wizard v1 fields)
            cursor.execute('''
                INSERT INTO systems (id, name, galaxy, reality, x, y, z, star_x, star_y, star_z, description,
                    glyph_code, glyph_planet, glyph_solar_system, region_x, region_y, region_z,
                    star_type, economy_type, economy_level, conflict_level, dominant_lifeform,
                    discovered_by, discovered_at, discord_tag, personal_discord_username, stellar_classification,
                    contributors, created_at, game_mode, profile_id, source,
                    game_version, expedition_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                system_id,
                system_data.get('name'),
                system_data.get('galaxy', 'Euclid'),
                system_data.get('reality', 'Normal'),
                system_data.get('x', 0),
                system_data.get('y', 0),
                system_data.get('z', 0),
                star_x,
                star_y,
                star_z,
                system_data.get('description', ''),
                system_data.get('glyph_code'),
                system_data.get('glyph_planet', 0),
                system_data.get('glyph_solar_system', 1),
                system_data.get('region_x'),
                system_data.get('region_y'),
                system_data.get('region_z'),
                system_data.get('star_type') or system_data.get('star_color'),
                system_data.get('economy_type'),
                system_data.get('economy_level'),
                system_data.get('conflict_level'),
                system_data.get('dominant_lifeform'),
                discoverer_username,
                system_data.get('discovered_at') or now_iso,
                submission.get('discord_tag'),
                submission.get('personal_discord_username'),
                system_data.get('stellar_classification'),
                json.dumps([{"name": discoverer_username, "action": "upload", "date": now_iso}]),
                now_iso,
                system_data.get('game_mode') or submission.get('game_mode', 'Normal'),
                submission.get('submitter_profile_id'),
                submission.get('source', 'manual'),
                new_game_version,
                new_expedition_id,
            ))

        # Handle planets - for edits, merge by name; for new systems, insert all
        # Initialize existing_planets if not already set (for new systems)
        if not is_edit:
            existing_planets = {}
            processed_planet_names = set()

        for planet in system_data.get('planets', []):
            # Handle sentinel_level -> sentinel field mapping (companion app sends sentinel_level)
            sentinel_val = planet.get('sentinel') or planet.get('sentinel_level', 'None')
            # Handle fauna_level/flora_level -> fauna/flora mapping
            fauna_val = planet.get('fauna') or planet.get('fauna_level', 'N/A')
            flora_val = planet.get('flora') or planet.get('flora_level', 'N/A')

            planet_name = planet.get('name')
            processed_planet_names.add(planet_name)

            # Check if this planet already exists (for edits)
            if is_edit and planet_name in existing_planets:
                # UPDATE existing planet
                existing_planet_id = existing_planets[planet_name]
                cursor.execute('''
                    UPDATE planets SET
                        x = ?, y = ?, z = ?, climate = ?, weather = ?, sentinel = ?, fauna = ?, flora = ?,
                        fauna_count = ?, flora_count = ?, has_water = ?, materials = ?, base_location = ?,
                        photo = ?, notes = ?, description = ?,
                        biome = ?, biome_subtype = ?, planet_size = ?, planet_index = ?, is_moon = ?,
                        storm_frequency = ?, weather_intensity = ?, building_density = ?,
                        hazard_temperature = ?, hazard_radiation = ?, hazard_toxicity = ?,
                        common_resource = ?, uncommon_resource = ?, rare_resource = ?,
                        weather_text = ?, sentinels_text = ?, flora_text = ?, fauna_text = ?,
                        has_rings = ?, is_dissonant = ?, is_infested = ?, extreme_weather = ?, water_world = ?, vile_brood = ?,
                        ancient_bones = ?, salvageable_scrap = ?, storm_crystals = ?, gravitino_balls = ?, is_gas_giant = ?, exotic_trophy = ?,
                        is_bubble = ?, is_floating_islands = ?,
                        -- M-W1: Wonders Notes are now overwriteable. The
                        -- wizard always re-sends the existing value in edit
                        -- mode (originalSystem snapshot), so a blank means
                        -- the user deliberately cleared the field.
                        estimated_age = ?,
                        core_element = ?,
                        lore_notes = ?,
                        root_structure = ?,
                        nutrient_source = ?
                    WHERE id = ?
                ''', (
                    planet.get('x', 0),
                    planet.get('y', 0),
                    planet.get('z', 0),
                    planet.get('climate'),
                    planet.get('weather'),
                    sentinel_val,
                    fauna_val,
                    flora_val,
                    planet.get('fauna_count', 0),
                    planet.get('flora_count', 0),
                    planet.get('has_water', 0),
                    planet.get('materials'),
                    planet.get('base_location'),
                    planet.get('photo'),
                    planet.get('notes'),
                    planet.get('description', ''),
                    planet.get('biome'),
                    planet.get('biome_subtype'),
                    planet.get('planet_size'),
                    planet.get('planet_index'),
                    1 if planet.get('is_moon') else 0,
                    planet.get('storm_frequency'),
                    planet.get('weather_intensity'),
                    planet.get('building_density'),
                    planet.get('hazard_temperature', 0),
                    planet.get('hazard_radiation', 0),
                    planet.get('hazard_toxicity', 0),
                    planet.get('common_resource'),
                    planet.get('uncommon_resource'),
                    planet.get('rare_resource'),
                    planet.get('weather_text'),
                    planet.get('sentinels_text'),
                    planet.get('flora_text'),
                    planet.get('fauna_text'),
                    1 if planet.get('has_rings') else 0,
                    1 if planet.get('is_dissonant') else 0,
                    1 if planet.get('is_infested') else 0,
                    1 if planet.get('extreme_weather') else 0,
                    1 if planet.get('water_world') else 0,
                    1 if planet.get('vile_brood') else 0,
                    1 if planet.get('ancient_bones') else 0,
                    1 if planet.get('salvageable_scrap') else 0,
                    1 if planet.get('storm_crystals') else 0,
                    1 if planet.get('gravitino_balls') else 0,
                    1 if planet.get('is_gas_giant') else 0,
                    planet.get('exotic_trophy'),
                    1 if planet.get('is_bubble') else 0,
                    1 if planet.get('is_floating_islands') else 0,
                    # Wonders Page Notes — COALESCE protects existing values
                    # on edit when the submitter leaves them blank.
                    planet.get('estimated_age') or None,
                    planet.get('core_element') or None,
                    planet.get('lore_notes') or None,
                    planet.get('root_structure') or None,
                    planet.get('nutrient_source') or None,
                    existing_planet_id
                ))
                planet_id = existing_planet_id
                logger.info(f"Updated existing planet '{planet_name}' (ID: {planet_id})")
            else:
                # INSERT new planet
                cursor.execute('''
                    INSERT INTO planets (
                        system_id, name, x, y, z, climate, weather, sentinel, fauna, flora,
                        fauna_count, flora_count, has_water, materials, base_location, photo, notes, description,
                        biome, biome_subtype, planet_size, planet_index, is_moon,
                        storm_frequency, weather_intensity, building_density,
                        hazard_temperature, hazard_radiation, hazard_toxicity,
                        common_resource, uncommon_resource, rare_resource,
                        weather_text, sentinels_text, flora_text, fauna_text,
                        has_rings, is_dissonant, is_infested, extreme_weather, water_world, vile_brood,
                        ancient_bones, salvageable_scrap, storm_crystals, gravitino_balls, is_gas_giant, exotic_trophy,
                        is_bubble, is_floating_islands,
                        estimated_age, core_element, lore_notes, root_structure, nutrient_source
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    system_id,
                    planet_name,
                    planet.get('x', 0),
                    planet.get('y', 0),
                    planet.get('z', 0),
                    planet.get('climate'),
                    planet.get('weather'),
                    sentinel_val,
                    fauna_val,
                    flora_val,
                    planet.get('fauna_count', 0),
                    planet.get('flora_count', 0),
                    planet.get('has_water', 0),
                    planet.get('materials'),
                    planet.get('base_location'),
                    planet.get('photo'),
                    planet.get('notes'),
                    planet.get('description', ''),
                    planet.get('biome'),
                    planet.get('biome_subtype'),
                    planet.get('planet_size'),
                    planet.get('planet_index'),
                    1 if planet.get('is_moon') else 0,
                    planet.get('storm_frequency'),
                    planet.get('weather_intensity'),
                    planet.get('building_density'),
                    planet.get('hazard_temperature', 0),
                    planet.get('hazard_radiation', 0),
                    planet.get('hazard_toxicity', 0),
                    planet.get('common_resource'),
                    planet.get('uncommon_resource'),
                    planet.get('rare_resource'),
                    planet.get('weather_text'),
                    planet.get('sentinels_text'),
                    planet.get('flora_text'),
                    planet.get('fauna_text'),
                    1 if planet.get('has_rings') else 0,
                    1 if planet.get('is_dissonant') else 0,
                    1 if planet.get('is_infested') else 0,
                    1 if planet.get('extreme_weather') else 0,
                    1 if planet.get('water_world') else 0,
                    1 if planet.get('vile_brood') else 0,
                    1 if planet.get('ancient_bones') else 0,
                    1 if planet.get('salvageable_scrap') else 0,
                    1 if planet.get('storm_crystals') else 0,
                    1 if planet.get('gravitino_balls') else 0,
                    1 if planet.get('is_gas_giant') else 0,
                    planet.get('exotic_trophy'),
                    1 if planet.get('is_bubble') else 0,
                    1 if planet.get('is_floating_islands') else 0,
                    # Wonders Page Notes (migration 1.76.0)
                    planet.get('estimated_age'),
                    planet.get('core_element'),
                    planet.get('lore_notes'),
                    planet.get('root_structure'),
                    planet.get('nutrient_source')
                ))
                planet_id = cursor.lastrowid
                if is_edit:
                    logger.info(f"Added new planet '{planet_name}' (ID: {planet_id}) to existing system")

            # For edits: clear existing moons on this planet before re-inserting
            # to prevent duplication when the same planet is resubmitted
            if is_edit and planet_name in existing_planets:
                cursor.execute('DELETE FROM moons WHERE planet_id = ?', (planet_id,))

            # Insert moons (nested under planet)
            for moon in planet.get('moons', []):
                cursor.execute('''
                    INSERT INTO moons (planet_id, name, orbit_radius, orbit_speed, climate, sentinel, fauna, flora, materials, notes, description, photo,
                        has_rings, is_dissonant, is_infested, extreme_weather, water_world, vile_brood, exotic_trophy,
                        ancient_bones, salvageable_scrap, storm_crystals, gravitino_balls, infested, is_gas_giant,
                        is_bubble, is_floating_islands,
                        biome, biome_subtype, weather, planet_size, common_resource, uncommon_resource, rare_resource, plant_resource,
                        estimated_age, core_element, lore_notes, root_structure, nutrient_source)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    planet_id,
                    moon.get('name'),
                    moon.get('orbit_radius', 0.5),
                    moon.get('orbit_speed', 0),
                    moon.get('climate') or moon.get('weather'),
                    moon.get('sentinel', 'None'),
                    moon.get('fauna', 'N/A'),
                    moon.get('flora', 'N/A'),
                    moon.get('materials'),
                    moon.get('notes'),
                    moon.get('description', ''),
                    moon.get('photo'),
                    1 if moon.get('has_rings') else 0,
                    1 if moon.get('is_dissonant') else 0,
                    1 if moon.get('is_infested') else 0,
                    1 if moon.get('extreme_weather') else 0,
                    1 if moon.get('water_world') else 0,
                    1 if moon.get('vile_brood') else 0,
                    moon.get('exotic_trophy'),
                    1 if moon.get('ancient_bones') else 0,
                    1 if moon.get('salvageable_scrap') else 0,
                    1 if moon.get('storm_crystals') else 0,
                    1 if moon.get('gravitino_balls') else 0,
                    1 if moon.get('infested') else 0,
                    1 if moon.get('is_gas_giant') else 0,
                    1 if moon.get('is_bubble') else 0,
                    1 if moon.get('is_floating_islands') else 0,
                    moon.get('biome'),
                    moon.get('biome_subtype'),
                    moon.get('weather'),
                    moon.get('planet_size'),
                    moon.get('common_resource'),
                    moon.get('uncommon_resource'),
                    moon.get('rare_resource'),
                    moon.get('plant_resource'),
                    # Wonders Page Notes (migration 1.76.0)
                    moon.get('estimated_age'),
                    moon.get('core_element'),
                    moon.get('lore_notes'),
                    moon.get('root_structure'),
                    moon.get('nutrient_source'),
                ))

        # Handle root-level moons (from Haven Extractor which sends moons as flat list)
        # These moons are sent with is_moon=true but stored at root level by extraction API
        root_moons = system_data.get('moons', [])
        if root_moons and planet_id:
            # Attach root-level moons to the last inserted planet
            # (In NMS, moons orbit their closest planet, so this is a reasonable default)
            logger.info(f"Processing {len(root_moons)} root-level moons for system {system_id}")
            for moon in root_moons:
                cursor.execute('''
                    INSERT INTO moons (planet_id, name, orbit_radius, orbit_speed, climate, sentinel, fauna, flora, materials, notes, description, photo,
                        has_rings, is_dissonant, is_infested, extreme_weather, water_world, vile_brood, exotic_trophy,
                        ancient_bones, salvageable_scrap, storm_crystals, gravitino_balls, infested, is_gas_giant,
                        is_bubble, is_floating_islands,
                        biome, biome_subtype, weather, planet_size, common_resource, uncommon_resource, rare_resource, plant_resource,
                        estimated_age, core_element, lore_notes, root_structure, nutrient_source)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    planet_id,  # Attach to last planet
                    moon.get('name'),
                    moon.get('orbit_radius', 0.5),
                    moon.get('orbit_speed', 0),
                    moon.get('climate') or moon.get('weather'),
                    moon.get('sentinel') or moon.get('sentinels', 'None'),
                    moon.get('fauna', 'N/A'),
                    moon.get('flora', 'N/A'),
                    moon.get('materials'),
                    moon.get('notes'),
                    moon.get('description', ''),
                    moon.get('photo'),
                    1 if moon.get('has_rings') else 0,
                    1 if moon.get('is_dissonant') else 0,
                    1 if moon.get('is_infested') else 0,
                    1 if moon.get('extreme_weather') else 0,
                    1 if moon.get('water_world') else 0,
                    1 if moon.get('vile_brood') else 0,
                    moon.get('exotic_trophy'),
                    1 if moon.get('ancient_bones') else 0,
                    1 if moon.get('salvageable_scrap') else 0,
                    1 if moon.get('storm_crystals') else 0,
                    1 if moon.get('gravitino_balls') else 0,
                    1 if moon.get('infested') else 0,
                    1 if moon.get('is_gas_giant') else 0,
                    1 if moon.get('is_bubble') else 0,
                    1 if moon.get('is_floating_islands') else 0,
                    moon.get('biome'),
                    moon.get('biome_subtype'),
                    moon.get('weather'),
                    moon.get('planet_size'),
                    moon.get('common_resource'),
                    moon.get('uncommon_resource'),
                    moon.get('rare_resource'),
                    moon.get('plant_resource'),
                    # Wonders Page Notes (migration 1.76.0)
                    moon.get('estimated_age'),
                    moon.get('core_element'),
                    moon.get('lore_notes'),
                    moon.get('root_structure'),
                    moon.get('nutrient_source'),
                ))

        # Insert space station if present
        if system_data.get('space_station'):
            station = system_data['space_station']
            # Convert trade_goods list to JSON string
            trade_goods_json = json.dumps(station.get('trade_goods', []))
            cursor.execute('''
                INSERT INTO space_stations (system_id, name, race, x, y, z, trade_goods)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                system_id,
                station.get('name') or f"{system_data.get('name')} Station",
                station.get('race') or 'Gek',
                station.get('x') or 0,
                station.get('y') or 0,
                station.get('z') or 0,
                trade_goods_json
            ))

        # Wizard v1: persist coauthors. coauthors[] lives in system_data JSON;
        # SEPARATE from primary submitter — leaderboard treats them distinctly.
        # Imported eagerly at module top (services.coauthors) so a stray
        # init-order issue can't drop coauthors silently. Pass submitter
        # identity so the helper can H-C1-block self-co-author entries.
        submitter_username_for_coauthors = (
            submission.get('personal_discord_username')
            or submission.get('submitted_by')
        )
        persist_system_coauthors(
            cursor, system_id, system_data.get('coauthors') or [],
            submitter_username=submitter_username_for_coauthors,
            submitter_profile_id=submission.get('submitter_profile_id'),
        )

        # Calculate and store completeness score
        update_completeness_score(cursor, system_id)

        # Promote any co-submitted discoveries drafts now that planets/moons
        # have IDs we can resolve names against. Runs inside the same
        # transaction so a draft promote failure doesn't leave the system
        # half-approved. Helper swallows per-draft errors internally.
        try:
            promoted_n, missing_n = _promote_draft_discoveries(
                cursor, system_id, submission, current_username
            )
            if promoted_n or missing_n:
                logger.info(
                    f"Submission {submission_id}: promoted {promoted_n} draft "
                    f"discoveries ({missing_n} with unresolved planet/moon link)"
                )
        except Exception as draft_err:
            logger.warning(
                f"Submission {submission_id}: draft discovery promotion failed: {draft_err}"
            )

        # Mark submission as approved (use actual username instead of generic 'admin')
        cursor.execute('''
            UPDATE pending_systems
            SET status = ?, reviewed_by = ?, review_date = ?
            WHERE id = ?
        ''', ('approved', current_username, datetime.now(timezone.utc).isoformat(), submission_id))

        # Add to approval audit log for full tracking
        cursor.execute('''
            INSERT INTO approval_audit_log
            (timestamp, action, submission_type, submission_id, submission_name,
             approver_username, approver_type, approver_account_id, approver_discord_tag,
             submitter_username, submitter_account_id, submitter_type, submission_discord_tag, source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            datetime.now(timezone.utc).isoformat(),
            'approved',
            'system',
            submission_id,
            system_data.get('name'),
            current_username,
            current_user_type,
            current_account_id,
            session_data.get('discord_tag'),
            submission.get('personal_discord_username') or submission.get('submitted_by'),
            submission.get('submitter_account_id'),
            submission.get('submitter_account_type'),
            submission.get('discord_tag'),
            submission.get('source', 'manual')
        ))

        conn.commit()

        action = 'updated' if is_edit else 'added'
        logger.info(f"Approved system submission: '{system_data.get('name')}' (ID: {submission_id}) - {action} by {current_username}")

        # Side effects fire AFTER the response. add_activity_log is sync (opens its
        # own connection) so it goes through FastAPI's BackgroundTasks; poster
        # invalidation is async (event-loop-friendly) so it goes through
        # fire_and_forget. Both are non-critical — failures log but don't surface
        # to the user.
        background_tasks.add_task(
            add_activity_log,
            'system_approved',
            f"System '{system_data.get('name')}' approved and {action}",
            f"Galaxy: {system_data.get('galaxy', 'Euclid')}, Approver: {current_username}",
            current_username,
        )

        # Post-approval poster invalidation. system_thumb fires every time
        # (covers both first upload and edit-via-approval per Parker spec).
        # region_thumb is threshold-gated inside the helper.
        _rcoords = None
        try:
            rx, ry, rz = system_data.get('region_x'), system_data.get('region_y'), system_data.get('region_z')
            if rx is not None and ry is not None and rz is not None:
                _rcoords = (int(rx), int(ry), int(rz))
        except (TypeError, ValueError):
            pass
        fire_and_forget(
            _invalidate_posters_async,
            submitted_by=submission.get('submitted_by') or submission.get('personal_discord_username'),
            galaxy=system_data.get('galaxy', 'Euclid'),
            discord_tag=submission.get('discord_tag'),
            system_id=system_id,
            region_coords=_rcoords,
            reality=system_data.get('reality') or 'Normal',
        )

        return {
            'status': 'ok',
            'message': f"System approved and {action} in database",
            'system_id': system_id,
            'system_name': system_data.get('name'),
            'is_edit': is_edit
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error approving submission: {e}")
        logger.exception("Failed to approve submission")
        raise HTTPException(status_code=500, detail="Failed to approve submission")
    finally:
        if conn:
            conn.close()


# ============================================================================
# Poster cache invalidation
# Event-driven first, TTL second. The set covers every poster type whose
# rendered content depends on system-level facts (counts, per-galaxy lists,
# per-community stats, voyager profile). Failure is non-fatal — TTL serves
# as the safety net (1h on landing_og/og_site, 24h on the rest).
#
# This used to run inline in the request handler. It now fires after the
# response via fire_and_forget — see services/dispatch.py.
# ============================================================================
def _invalidate_posters_for_submission(
    submitted_by: Optional[str],
    galaxy: Optional[str],
    discord_tag: Optional[str] = None,
    system_id: Optional[str] = None,
    region_coords: Optional[tuple] = None,
    reality: Optional[str] = None,
):
    """Drop cached PNGs for everything the new system affects.

    Always invalidates the global homepage embed and site-wide stats embed
    (both poll system counts), the per-galaxy atlas (both forms), the
    submitter's per-community card if present, and the submitter's voyager
    cards. Each invalidate() call is independent — one failure does not
    block the others.

    Parker 2026-05-11: also invalidate `system_thumb` for the specific
    system_id on approval (first upload OR subsequent edit). `region_thumb`
    invalidation is threshold-based — only fire when the region's system
    count has grown ≥10 since the last cached render, OR the cache is
    >7 days old. See _should_refresh_region_thumb().
    """
    try:
        from services.poster_service import invalidate
    except Exception as e:
        logger.warning(f"Poster invalidation skipped (import failed): {e}")
        return

    def _try(poster_type: str, key: str):
        try:
            invalidate(poster_type, key)
        except Exception as e:
            logger.warning(f"Poster invalidate {poster_type}/{key} failed: {e}")

    # Site-wide: homepage embed + global OG card
    _try('landing_og', 'global')
    _try('og_site', 'global')

    # Per-galaxy atlas (regular + thumbnail) — both consume galaxy-level facts
    if galaxy:
        _try('atlas', galaxy)
        _try('atlas_thumb', galaxy)
        _try('og_atlas', galaxy)

    # Per-community card — keyed by discord_tag (slug-clean it lightly)
    if discord_tag:
        _try('og_community', discord_tag)

    # Per-voyager cards — slug derived from username with the share-link rules
    if submitted_by:
        clean = (submitted_by or '').replace('#', '').strip()
        if (len(clean) > 4
                and clean[-4:].isdigit()
                and (len(clean) == 4 or not clean[-5].isdigit())):
            clean = clean[:-4]
        slug = clean.lower().strip()
        if slug:
            _try('voyager', slug)
            _try('voyager_og', slug)

    # system_thumb — always invalidate this exact system on approval/edit.
    # The og_system card too (per-system social embed).
    if system_id:
        _try('system_thumb', str(system_id))
        _try('og_system', str(system_id))

    # region_thumb — threshold-based: only invalidate if the region has
    # grown enough OR the cache is stale. Cheap to compute since we just
    # need the current system_count for that region.
    if region_coords and len(region_coords) == 3:
        rx, ry, rz = region_coords
        try:
            if _should_refresh_region_thumb(rx, ry, rz, reality, galaxy):
                _try('region_thumb', f'{rx}_{ry}_{rz}')
        except Exception as e:
            logger.warning(f"Region thumb refresh check failed: {e}")


def _should_refresh_region_thumb(rx, ry, rz, reality, galaxy):
    """Return True when the region_thumb cached PNG is stale enough to drop.

    Rules:
      - No cache row yet → False (next view will lazy-render fresh anyway)
      - Cache row >7 days old → True (safety-net for slow-drip changes)
      - system_count grew by ≥ 10 since last render → True
      - system_count grew by ≥ 10% since last render → True (small regions)
    """
    from db import get_db_connection
    from datetime import datetime, timezone, timedelta

    cache_key = f'{rx}_{ry}_{rz}'
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT generated_at, system_count_at_render
            FROM poster_cache
            WHERE poster_type = 'region_thumb' AND cache_key = ?
            LIMIT 1
        """, (cache_key,))
        row = cursor.fetchone()
        if not row:
            return False

        # Time-based safety net
        try:
            gen = datetime.fromisoformat(row['generated_at'].replace('Z', '+00:00'))
            if gen.tzinfo is None:
                gen = gen.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) - gen > timedelta(days=7):
                return True
        except (ValueError, KeyError, TypeError):
            pass

        # Count-based threshold
        last_count = row['system_count_at_render'] or 0
        params = [rx, ry, rz]
        where = "region_x = ? AND region_y = ? AND region_z = ?"
        if reality:
            where += " AND COALESCE(reality, 'Normal') = ?"
            params.append(reality)
        if galaxy:
            where += " AND COALESCE(galaxy, 'Euclid') = ?"
            params.append(galaxy)
        cursor.execute(f"SELECT COUNT(*) AS c FROM systems WHERE {where}", params)
        current_count = cursor.fetchone()['c']
        if current_count - last_count >= 10:
            return True
        if last_count > 0 and (current_count - last_count) / last_count >= 0.10:
            return True
    return False


async def _invalidate_posters_async(
    submitted_by: Optional[str],
    galaxy: Optional[str],
    discord_tag: Optional[str] = None,
    system_id: Optional[str] = None,
    region_coords: Optional[tuple] = None,
    reality: Optional[str] = None,
):
    """Async wrapper so fire_and_forget can schedule it as a coroutine."""
    _invalidate_posters_for_submission(
        submitted_by, galaxy, discord_tag,
        system_id=system_id, region_coords=region_coords, reality=reality,
    )


@router.post('/api/reject_system/{submission_id}')
async def reject_system(
    submission_id: int,
    payload: dict,
    background_tasks: BackgroundTasks,
    session: Optional[str] = Cookie(None),
):
    """
    Reject a pending system submission with reason (admin only).
    Self-rejection is blocked for non-super-admin users (same as approval).
    """
    # Verify admin session
    if not verify_session(session):
        raise HTTPException(status_code=401, detail="Admin authentication required")

    # Get current user identity for self-rejection check and audit
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
        db_path = get_db_path()
        conn = get_db_connection()
        cursor = conn.cursor()

        # Check submission exists and is pending
        cursor.execute('SELECT * FROM pending_systems WHERE id = ?', (submission_id,))
        row = cursor.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Submission not found")

        submission = dict(row)
        system_name = submission.get('system_name')

        if submission['status'] != 'pending':
            raise HTTPException(
                status_code=400,
                detail=f"Submission already {submission['status']}"
            )

        # SELF-REJECTION BLOCKING: same identity matching as approval.
        if check_self_submission(submission, session_data):
            raise HTTPException(
                status_code=403,
                detail="You cannot reject your own submission. Another admin must review it."
            )

        # Mark as rejected (use actual username)
        cursor.execute('''
            UPDATE pending_systems
            SET status = ?, reviewed_by = ?, review_date = ?, rejection_reason = ?
            WHERE id = ?
        ''', ('rejected', current_username, datetime.now(timezone.utc).isoformat(), reason, submission_id))

        # Add to approval audit log
        cursor.execute('''
            INSERT INTO approval_audit_log
            (timestamp, action, submission_type, submission_id, submission_name,
             approver_username, approver_type, approver_account_id, approver_discord_tag,
             submitter_username, submitter_account_id, submitter_type, notes, submission_discord_tag, source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            datetime.now(timezone.utc).isoformat(),
            'rejected',
            'system',
            submission_id,
            system_name,
            current_username,
            current_user_type,
            current_account_id,
            session_data.get('discord_tag'),
            submission.get('personal_discord_username') or submission.get('submitted_by'),
            submission.get('submitter_account_id'),
            submission.get('submitter_account_type'),
            reason,
            submission.get('discord_tag'),
            submission.get('source', 'manual')
        ))

        conn.commit()

        logger.info(f"Rejected system submission: '{system_name}' (ID: {submission_id}) by {current_username}. Reason: {reason}")

        # Activity log fires after the response. See services/dispatch.py.
        background_tasks.add_task(
            add_activity_log,
            'system_rejected',
            f"System '{system_name}' rejected",
            f"Reason: {reason}, Reviewer: {current_username}",
            current_username,
        )

        return {
            'status': 'ok',
            'message': 'System submission rejected',
            'submission_id': submission_id
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error rejecting submission: {e}")
        logger.exception("Failed to reject submission")
        raise HTTPException(status_code=500, detail="Failed to reject submission")
    finally:
        if conn:
            conn.close()


# =============================================================================
# BATCH APPROVAL/REJECTION ENDPOINTS
# =============================================================================

@router.post('/api/approve_systems/batch')
async def batch_approve_systems(
    payload: dict,
    background_tasks: BackgroundTasks,
    session: Optional[str] = Cookie(None),
):
    """
    Submit a batch of pending systems for asynchronous approval.

    Returns 202 + job_id immediately. Actual processing runs as a background
    task; the frontend polls /api/batch_jobs/{job_id} for progress. Previously
    this endpoint processed everything inline within one HTTP request and
    blew through Nginx Proxy Manager's 60-second timeout for ~100-system
    batches, leaving the queue in a half-processed state.

    Idempotency: if a submission has already been approved or rejected by
    the time the worker reaches it (status != 'pending'), it's recorded as
    'skipped' rather than failing the batch.
    """
    if not verify_session(session):
        raise HTTPException(status_code=401, detail="Admin authentication required")

    session_data = get_session(session)
    current_user_type = session_data.get('user_type')
    current_username = session_data.get('username')
    enabled_features = session_data.get('enabled_features', [])

    is_super = current_user_type == 'super_admin'
    require_feature(session_data, 'approvals')
    if not is_super and 'batch_approvals' not in enabled_features:
        raise HTTPException(status_code=403, detail="Batch approvals permission required")

    submission_ids = payload.get('submission_ids', [])
    if not submission_ids or not isinstance(submission_ids, list):
        raise HTTPException(status_code=400, detail="No submission IDs provided")
    if len(submission_ids) > 1000:
        raise HTTPException(status_code=400, detail="Batch too large (>1000 submissions)")

    job_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).isoformat()

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO batch_jobs
            (id, status, total_systems, processed_systems, failed_systems, failures,
             submitted_by_username, created_at)
            VALUES (?, 'pending', ?, 0, 0, '[]', ?, ?)
        ''', (job_id, len(submission_ids), current_username, created_at))
        conn.commit()
    except Exception as e:
        logger.exception(f"Failed to create batch job: {e}")
        raise HTTPException(status_code=500, detail="Failed to create batch job")
    finally:
        if conn:
            conn.close()

    # Snapshot session into a plain dict so the worker doesn't depend on the
    # request scope. The session itself stays alive for the user, but copying
    # the fields the worker needs decouples job processing from the cookie.
    session_snapshot = {
        'user_type': current_user_type,
        'username': current_username,
        'enabled_features': list(enabled_features) if enabled_features else [],
        'discord_tag': session_data.get('discord_tag'),
        'partner_id': session_data.get('partner_id'),
        'sub_admin_id': session_data.get('sub_admin_id'),
        'is_haven_sub_admin': session_data.get('is_haven_sub_admin', False),
        'additional_discord_tags': session_data.get('additional_discord_tags', []),
        'profile_id': session_data.get('profile_id'),
        'account_id': session_data.get('account_id'),
        'can_approve_personal_uploads': session_data.get('can_approve_personal_uploads', False),
    }

    fire_and_forget(_run_batch_approval_job, job_id, list(submission_ids), session_snapshot)

    logger.info(f"Batch approval job {job_id} queued by {current_username}: {len(submission_ids)} submissions")

    return JSONResponse(
        status_code=202,
        content={
            'job_id': job_id,
            'status': 'pending',
            'total_systems': len(submission_ids),
            'message': 'Batch approval queued. Poll /api/batch_jobs/{job_id} for progress.',
        }
    )


def _process_batch_approvals_sync(job_id: str, submission_ids: list, session_snapshot: dict):
    """Synchronous worker that processes a batch approval job.

    Runs in a thread (via asyncio.to_thread inside the async wrapper) so
    sqlite3's blocking calls don't peg the event loop. Updates batch_jobs row
    with progress every PROGRESS_FLUSH submissions and on completion.
    """
    PROGRESS_FLUSH = 5
    current_user_type = session_snapshot.get('user_type')
    current_username = session_snapshot.get('username')
    current_account_id = None
    if current_user_type == 'partner':
        current_account_id = session_snapshot.get('partner_id')
    elif current_user_type == 'sub_admin':
        current_account_id = session_snapshot.get('sub_admin_id')

    processed = 0
    failed = 0
    failures = []
    approved_meta = []  # for post-job poster invalidation

    def _update_progress(conn, status=None):
        cur = conn.cursor()
        if status:
            cur.execute('''
                UPDATE batch_jobs
                SET status = ?, processed_systems = ?, failed_systems = ?, failures = ?
                WHERE id = ?
            ''', (status, processed, failed, json.dumps(failures), job_id))
        else:
            cur.execute('''
                UPDATE batch_jobs
                SET processed_systems = ?, failed_systems = ?, failures = ?
                WHERE id = ?
            ''', (processed, failed, json.dumps(failures), job_id))
        conn.commit()

    conn = None
    try:
        conn = get_db_connection()
        # Mark job as processing
        _update_progress(conn, status='processing')
        cursor = conn.cursor()

        for idx, submission_id in enumerate(submission_ids):
            try:
                cursor.execute('SELECT * FROM pending_systems WHERE id = ?', (submission_id,))
                row = cursor.fetchone()

                if not row:
                    failed += 1
                    failures.append({'id': submission_id, 'index': idx, 'error': 'Submission not found'})
                    continue

                submission = dict(row)
                system_name = submission.get('system_name')

                # Idempotency: already approved/rejected by another admin between
                # job submission and processing? Count as processed (not failed)
                # so the user can retry the same job ID safely.
                if submission['status'] != 'pending':
                    processed += 1
                    continue

                # Self-approval check: self-submissions are skipped (not failed)
                if check_self_submission(submission, session_snapshot):
                    processed += 1
                    continue

                # Parse and process system data
                system_data = json.loads(submission['system_data'])

                # H-C2 batch: also skip submissions that credit this approver
                # as a co-author. Same "skipped, not failed" semantics so the
                # frontend doesn't surface them as errors.
                if check_self_coauthor(system_data.get('coauthors') or [], session_snapshot):
                    processed += 1
                    continue

                if not system_data.get('glyph_code'):
                    system_data['glyph_code'] = None

                # Calculate star and region coordinates
                star_x, star_y, star_z = None, None, None
                region_x, region_y, region_z = None, None, None

                submission_x = system_data.get('x')
                submission_y = system_data.get('y')
                submission_z = system_data.get('z')
                original_glyph = system_data.get('glyph_code')

                # EARLY CHECK: For EDIT submissions with no glyph, fetch the original system's glyph
                existing_system_id = system_data.get('id')
                if existing_system_id and not original_glyph:
                    cursor.execute('SELECT glyph_code, glyph_planet, glyph_solar_system FROM systems WHERE id = ?', (existing_system_id,))
                    existing_row = cursor.fetchone()
                    if existing_row and existing_row[0]:
                        original_glyph = existing_row[0]
                        system_data['glyph_code'] = original_glyph
                        system_data['glyph_planet'] = existing_row[1] or 0
                        system_data['glyph_solar_system'] = existing_row[2] or 1
                        logger.info(f"Batch approval: Preserved original glyph {original_glyph} for edit of system {existing_system_id}")

                if original_glyph:
                    try:
                        decoded = decode_glyph_to_coords(original_glyph)
                        glyph_x, glyph_y, glyph_z = decoded['x'], decoded['y'], decoded['z']

                        coords_match = True
                        if submission_x is not None and submission_y is not None and submission_z is not None:
                            if (abs(glyph_x - submission_x) > 1 or
                                abs(glyph_y - submission_y) > 1 or
                                abs(glyph_z - submission_z) > 1):
                                coords_match = False

                        if coords_match:
                            star_x, star_y, star_z = decoded['star_x'], decoded['star_y'], decoded['star_z']
                            region_x = decoded.get('region_x')
                            region_y = decoded.get('region_y')
                            region_z = decoded.get('region_z')
                        else:
                            planet_idx = decoded.get('planet', 0)
                            solar_idx = decoded.get('solar_system', 1)
                            corrected_glyph = encode_coords_to_glyph(
                                int(submission_x), int(submission_y), int(submission_z),
                                planet_idx, solar_idx
                            )
                            corrected_decoded = decode_glyph_to_coords(corrected_glyph)
                            system_data['glyph_code'] = corrected_glyph
                            star_x, star_y, star_z = corrected_decoded['star_x'], corrected_decoded['star_y'], corrected_decoded['star_z']
                            region_x = corrected_decoded.get('region_x')
                            region_y = corrected_decoded.get('region_y')
                            region_z = corrected_decoded.get('region_z')
                    except Exception as e:
                        logger.warning(f"Batch approval: Failed to validate glyph for submission {submission_id}: {e}")

                elif submission_x is not None and submission_y is not None and submission_z is not None:
                    try:
                        calculated_glyph = encode_coords_to_glyph(
                            int(submission_x), int(submission_y), int(submission_z), 0, 1
                        )
                        decoded = decode_glyph_to_coords(calculated_glyph)
                        system_data['glyph_code'] = calculated_glyph
                        star_x, star_y, star_z = decoded['star_x'], decoded['star_y'], decoded['star_z']
                        region_x = decoded.get('region_x')
                        region_y = decoded.get('region_y')
                        region_z = decoded.get('region_z')
                    except Exception as e:
                        logger.warning(f"Batch approval: Failed to calculate glyph for submission {submission_id}: {e}")

                if region_x is not None:
                    system_data['region_x'] = region_x
                if region_y is not None:
                    system_data['region_y'] = region_y
                if region_z is not None:
                    system_data['region_z'] = region_z

                # Check if edit or new — glyph-first canonical dedup
                # Priority: 1) Glyph last-11 + galaxy + reality
                #           2) edit_system_id / system_data id fallback
                is_edit = False
                system_id = None
                original_glyph_data = None

                # Primary: glyph-based coordinate match
                if system_data.get('glyph_code'):
                    existing_glyph_row = find_matching_system(
                        cursor, system_data['glyph_code'],
                        system_data.get('galaxy', 'Euclid'),
                        system_data.get('reality', 'Normal')
                    )
                    if existing_glyph_row:
                        is_edit = True
                        system_id = existing_glyph_row[0]
                        original_glyph_data = {
                            'glyph_code': existing_glyph_row[2],
                            'glyph_planet': existing_glyph_row[3],
                            'glyph_solar_system': existing_glyph_row[4]
                        }
                        logger.info(f"Batch approval {submission_id}: glyph matches existing system '{existing_glyph_row[1]}' (ID: {system_id})")

                # Fallback: edit_system_id or system_data id
                if not is_edit:
                    existing_system_id = submission.get('edit_system_id') or system_data.get('id')
                    if existing_system_id:
                        cursor.execute('SELECT id, glyph_code, glyph_planet, glyph_solar_system FROM systems WHERE id = ?', (existing_system_id,))
                        existing_row = cursor.fetchone()
                        if existing_row:
                            is_edit = True
                            system_id = existing_system_id
                            original_glyph_data = {
                                'glyph_code': existing_row[1],
                                'glyph_planet': existing_row[2],
                                'glyph_solar_system': existing_row[3]
                            }
                            logger.info(f"Batch approval {submission_id}: edit via ID fallback: {existing_system_id}")

                # For EDITS: If submission doesn't have glyph data, preserve the original
                if is_edit and original_glyph_data:
                    if not system_data.get('glyph_code') and original_glyph_data.get('glyph_code'):
                        system_data['glyph_code'] = original_glyph_data['glyph_code']
                        system_data['glyph_planet'] = original_glyph_data.get('glyph_planet', 0)
                        system_data['glyph_solar_system'] = original_glyph_data.get('glyph_solar_system', 1)

                if is_edit:
                    # Update contributors list - add edit entry
                    updater_username = submission.get('personal_discord_username') or submission.get('submitted_by') or 'Unknown'
                    now_iso = datetime.now(timezone.utc).isoformat()
                    cursor.execute('SELECT contributors FROM systems WHERE id = ?', (system_id,))
                    contrib_row = cursor.fetchone()
                    existing_contributors = json.loads(contrib_row[0]) if contrib_row and contrib_row[0] else []
                    existing_contributors.append({"name": updater_username, "action": "edit", "date": now_iso})

                    cursor.execute('''
                        UPDATE systems
                        SET name = ?, galaxy = ?, x = ?, y = ?, z = ?,
                            star_x = ?, star_y = ?, star_z = ?,
                            description = ?,
                            glyph_code = ?, glyph_planet = ?, glyph_solar_system = ?,
                            region_x = ?, region_y = ?, region_z = ?,
                            star_type = ?, economy_type = ?, economy_level = ?,
                            conflict_level = ?, dominant_lifeform = ?,
                            discord_tag = ?, personal_discord_username = ?,
                            stellar_classification = ?,
                            last_updated_by = ?, last_updated_at = ?,
                            contributors = ?
                        WHERE id = ?
                    ''', (
                        system_data.get('name'),
                        system_data.get('galaxy', 'Euclid'),
                        system_data.get('x', 0),
                        system_data.get('y', 0),
                        system_data.get('z', 0),
                        star_x, star_y, star_z,
                        system_data.get('description', ''),
                        system_data.get('glyph_code'),
                        system_data.get('glyph_planet', 0),
                        system_data.get('glyph_solar_system', 1),
                        system_data.get('region_x'),
                        system_data.get('region_y'),
                        system_data.get('region_z'),
                        system_data.get('star_type') or system_data.get('star_color'),
                        system_data.get('economy_type'),
                        system_data.get('economy_level'),
                        system_data.get('conflict_level'),
                        system_data.get('dominant_lifeform'),
                        submission.get('discord_tag'),
                        submission.get('personal_discord_username'),
                        system_data.get('stellar_classification'),
                        updater_username,
                        now_iso,
                        json.dumps(existing_contributors),
                        system_id
                    ))

                    # Delete existing planets, moons, and space station
                    cursor.execute('SELECT id FROM planets WHERE system_id = ?', (system_id,))
                    planet_ids = [row[0] for row in cursor.fetchall()]
                    for pid in planet_ids:
                        cursor.execute('DELETE FROM moons WHERE planet_id = ?', (pid,))
                    cursor.execute('DELETE FROM planets WHERE system_id = ?', (system_id,))
                    cursor.execute('DELETE FROM space_stations WHERE system_id = ?', (system_id,))
                else:
                    system_id = str(uuid.uuid4())

                    # Determine the discoverer's username - personal_discord_username is the Discord name from the form
                    discoverer_username = submission.get('personal_discord_username') or submission.get('submitted_by') or 'Unknown'
                    now_iso = datetime.now(timezone.utc).isoformat()

                    cursor.execute('''
                        INSERT INTO systems (id, name, galaxy, reality, x, y, z, star_x, star_y, star_z, description,
                            glyph_code, glyph_planet, glyph_solar_system, region_x, region_y, region_z,
                            star_type, economy_type, economy_level, conflict_level, dominant_lifeform,
                            discovered_by, discovered_at, discord_tag, personal_discord_username, stellar_classification,
                            contributors, created_at, game_mode, profile_id, source)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        system_id,
                        system_data.get('name'),
                        system_data.get('galaxy', 'Euclid'),
                        system_data.get('reality', 'Normal'),
                        system_data.get('x', 0),
                        system_data.get('y', 0),
                        system_data.get('z', 0),
                        star_x, star_y, star_z,
                        system_data.get('description', ''),
                        system_data.get('glyph_code'),
                        system_data.get('glyph_planet', 0),
                        system_data.get('glyph_solar_system', 1),
                        system_data.get('region_x'),
                        system_data.get('region_y'),
                        system_data.get('region_z'),
                        system_data.get('star_type') or system_data.get('star_color'),
                        system_data.get('economy_type'),
                        system_data.get('economy_level'),
                        system_data.get('conflict_level'),
                        system_data.get('dominant_lifeform'),
                        discoverer_username,
                        system_data.get('discovered_at') or now_iso,
                        submission.get('discord_tag'),
                        submission.get('personal_discord_username'),
                        system_data.get('stellar_classification'),
                        json.dumps([{"name": discoverer_username, "action": "upload", "date": now_iso}]),
                        now_iso,
                        system_data.get('game_mode') or submission.get('game_mode', 'Normal'),
                        submission.get('submitter_profile_id'),
                        submission.get('source', 'manual'),
                    ))

                # Insert planets
                for planet in system_data.get('planets', []):
                    sentinel_val = planet.get('sentinel') or planet.get('sentinel_level', 'None')
                    fauna_val = planet.get('fauna') or planet.get('fauna_level', 'N/A')
                    flora_val = planet.get('flora') or planet.get('flora_level', 'N/A')

                    cursor.execute('''
                        INSERT INTO planets (
                            system_id, name, x, y, z, climate, weather, sentinel, fauna, flora,
                            fauna_count, flora_count, has_water, materials, base_location, photo, notes, description,
                            biome, biome_subtype, planet_size, planet_index, is_moon,
                            storm_frequency, weather_intensity, building_density,
                            hazard_temperature, hazard_radiation, hazard_toxicity,
                            common_resource, uncommon_resource, rare_resource,
                            weather_text, sentinels_text, flora_text, fauna_text,
                            has_rings, is_dissonant, is_infested, extreme_weather, water_world, vile_brood,
                            ancient_bones, salvageable_scrap, storm_crystals, gravitino_balls, is_gas_giant, exotic_trophy,
                            is_bubble, is_floating_islands,
                            estimated_age, core_element, lore_notes, root_structure, nutrient_source
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        system_id,
                        planet.get('name'),
                        planet.get('x', 0),
                        planet.get('y', 0),
                        planet.get('z', 0),
                        planet.get('climate'),
                        planet.get('weather'),
                        sentinel_val,
                        fauna_val,
                        flora_val,
                        planet.get('fauna_count', 0),
                        planet.get('flora_count', 0),
                        planet.get('has_water', 0),
                        planet.get('materials'),
                        planet.get('base_location'),
                        planet.get('photo'),
                        planet.get('notes'),
                        planet.get('description', ''),
                        planet.get('biome'),
                        planet.get('biome_subtype'),
                        planet.get('planet_size'),
                        planet.get('planet_index'),
                        1 if planet.get('is_moon') else 0,
                        planet.get('storm_frequency'),
                        planet.get('weather_intensity'),
                        planet.get('building_density'),
                        planet.get('hazard_temperature', 0),
                        planet.get('hazard_radiation', 0),
                        planet.get('hazard_toxicity', 0),
                        planet.get('common_resource'),
                        planet.get('uncommon_resource'),
                        planet.get('rare_resource'),
                        planet.get('weather_text'),
                        planet.get('sentinels_text'),
                        planet.get('flora_text'),
                        planet.get('fauna_text'),
                        1 if planet.get('has_rings') else 0,
                        1 if planet.get('is_dissonant') else 0,
                        1 if planet.get('is_infested') else 0,
                        1 if planet.get('extreme_weather') else 0,
                        1 if planet.get('water_world') else 0,
                        1 if planet.get('vile_brood') else 0,
                        1 if planet.get('ancient_bones') else 0,
                        1 if planet.get('salvageable_scrap') else 0,
                        1 if planet.get('storm_crystals') else 0,
                        1 if planet.get('gravitino_balls') else 0,
                        1 if planet.get('is_gas_giant') else 0,
                        planet.get('exotic_trophy'),
                        1 if planet.get('is_bubble') else 0,
                        1 if planet.get('is_floating_islands') else 0,
                        # Wonders Page Notes (migration 1.76.0)
                        planet.get('estimated_age'),
                        planet.get('core_element'),
                        planet.get('lore_notes'),
                        planet.get('root_structure'),
                        planet.get('nutrient_source')
                    ))
                    planet_id = cursor.lastrowid

                    for moon in planet.get('moons', []):
                        cursor.execute('''
                            INSERT INTO moons (planet_id, name, orbit_radius, orbit_speed, climate, sentinel, fauna, flora, materials, notes, description, photo,
                                has_rings, is_dissonant, is_infested, extreme_weather, water_world, vile_brood, exotic_trophy,
                                ancient_bones, salvageable_scrap, storm_crystals, gravitino_balls, infested, is_gas_giant,
                                is_bubble, is_floating_islands,
                                biome, biome_subtype, weather, planet_size, common_resource, uncommon_resource, rare_resource, plant_resource,
                                estimated_age, core_element, lore_notes, root_structure, nutrient_source)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (
                            planet_id,
                            moon.get('name'),
                            moon.get('orbit_radius', 0.5),
                            moon.get('orbit_speed', 0),
                            moon.get('climate') or moon.get('weather'),
                            moon.get('sentinel', 'None'),
                            moon.get('fauna', 'N/A'),
                            moon.get('flora', 'N/A'),
                            moon.get('materials'),
                            moon.get('notes'),
                            moon.get('description', ''),
                            moon.get('photo'),
                            1 if moon.get('has_rings') else 0,
                            1 if moon.get('is_dissonant') else 0,
                            1 if moon.get('is_infested') else 0,
                            1 if moon.get('extreme_weather') else 0,
                            1 if moon.get('water_world') else 0,
                            1 if moon.get('vile_brood') else 0,
                            moon.get('exotic_trophy'),
                            1 if moon.get('ancient_bones') else 0,
                            1 if moon.get('salvageable_scrap') else 0,
                            1 if moon.get('storm_crystals') else 0,
                            1 if moon.get('gravitino_balls') else 0,
                            1 if moon.get('infested') else 0,
                            1 if moon.get('is_gas_giant') else 0,
                            1 if moon.get('is_bubble') else 0,
                            1 if moon.get('is_floating_islands') else 0,
                            moon.get('biome'),
                            moon.get('biome_subtype'),
                            moon.get('weather'),
                            moon.get('planet_size'),
                            moon.get('common_resource'),
                            moon.get('uncommon_resource'),
                            moon.get('rare_resource'),
                            moon.get('plant_resource'),
                            # Wonders Page Notes (migration 1.76.0)
                            moon.get('estimated_age'),
                            moon.get('core_element'),
                            moon.get('lore_notes'),
                            moon.get('root_structure'),
                            moon.get('nutrient_source'),
                        ))

                # Insert space station if present
                if system_data.get('space_station'):
                    station = system_data['space_station']
                    # Convert trade_goods list to JSON string
                    trade_goods_json = json.dumps(station.get('trade_goods', []))
                    cursor.execute('''
                        INSERT INTO space_stations (system_id, name, race, x, y, z, trade_goods)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        system_id,
                        station.get('name') or f"{system_data.get('name')} Station",
                        station.get('race') or 'Gek',
                        station.get('x') or 0,
                        station.get('y') or 0,
                        station.get('z') or 0,
                        trade_goods_json
                    ))

                # Wizard v1: persist co-authors. Mirrors the single-approve
                # handler at approvals.py:~1538 — the batch handler used to
                # silently drop coauthors on approval (only the single path
                # called persist_system_coauthors), so submissions approved
                # in bulk credited the primary submitter but no one else.
                # Same self-co-author guard via submitter context.
                submitter_username_for_coauthors = (
                    submission.get('personal_discord_username')
                    or submission.get('submitted_by')
                )
                persist_system_coauthors(
                    cursor, system_id, system_data.get('coauthors') or [],
                    submitter_username=submitter_username_for_coauthors,
                    submitter_profile_id=submission.get('submitter_profile_id'),
                )

                # Calculate and store completeness score
                update_completeness_score(cursor, system_id)

                # Promote any co-submitted discoveries drafts (Wizard v1.64.0).
                # Same transactional guarantee as the planets/moons inserts —
                # a draft failure here rolls back the whole submission in the
                # outer except branch. Helper swallows per-draft errors.
                try:
                    _promoted_n, _missing_n = _promote_draft_discoveries(
                        cursor, system_id, submission, current_username
                    )
                    if _promoted_n or _missing_n:
                        logger.info(
                            f"Batch job {job_id} submission {submission_id}: "
                            f"promoted {_promoted_n} draft discoveries "
                            f"({_missing_n} with unresolved planet/moon link)"
                        )
                except Exception as _draft_err:
                    logger.warning(
                        f"Batch job {job_id} submission {submission_id}: "
                        f"draft discovery promotion failed: {_draft_err}"
                    )

                # Mark submission as approved
                cursor.execute('''
                    UPDATE pending_systems
                    SET status = ?, reviewed_by = ?, review_date = ?
                    WHERE id = ?
                ''', ('approved', current_username, datetime.now(timezone.utc).isoformat(), submission_id))

                # Add to approval audit log
                cursor.execute('''
                    INSERT INTO approval_audit_log
                    (timestamp, action, submission_type, submission_id, submission_name,
                     approver_username, approver_type, approver_account_id, approver_discord_tag,
                     submitter_username, submitter_account_id, submitter_type, submission_discord_tag, source)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    datetime.now(timezone.utc).isoformat(),
                    'approved',
                    'system',
                    submission_id,
                    system_data.get('name'),
                    current_username,
                    current_user_type,
                    current_account_id,
                    session_snapshot.get('discord_tag'),
                    submission.get('personal_discord_username') or submission.get('submitted_by'),
                    submission.get('submitter_account_id'),
                    submission.get('submitter_account_type'),
                    submission.get('discord_tag'),
                    submission.get('source', 'manual')
                ))

                # Commit per-submission so a later failure doesn't roll back
                # successfully-approved earlier ones in the batch.
                conn.commit()

                processed += 1
                _rcoords = None
                try:
                    rx_, ry_, rz_ = system_data.get('region_x'), system_data.get('region_y'), system_data.get('region_z')
                    if rx_ is not None and ry_ is not None and rz_ is not None:
                        _rcoords = (int(rx_), int(ry_), int(rz_))
                except (TypeError, ValueError):
                    pass
                approved_meta.append({
                    'submitted_by': submission.get('submitted_by') or submission.get('personal_discord_username'),
                    'galaxy': system_data.get('galaxy', 'Euclid'),
                    'discord_tag': submission.get('discord_tag'),
                    'system_id': system_id,
                    'region_coords': _rcoords,
                    'reality': system_data.get('reality') or 'Normal',
                })

            except Exception as e:
                logger.error(f"Batch job {job_id}: error processing submission {submission_id}: {e}")
                logger.exception("Per-submission failure")
                try:
                    conn.rollback()
                except Exception:
                    pass
                failed += 1
                failures.append({
                    'id': submission_id,
                    'index': idx,
                    'error': str(e)[:500],
                })

            # Periodic progress flush so the polling endpoint sees movement.
            if (idx + 1) % PROGRESS_FLUSH == 0:
                try:
                    _update_progress(conn)
                except Exception as flush_err:
                    logger.warning(f"Batch job {job_id}: progress flush failed: {flush_err}")

        # Mark job complete
        completed_at = datetime.now(timezone.utc).isoformat()
        cursor.execute('''
            UPDATE batch_jobs
            SET status = 'completed', processed_systems = ?, failed_systems = ?,
                failures = ?, completed_at = ?
            WHERE id = ?
        ''', (processed, failed, json.dumps(failures), completed_at, job_id))
        conn.commit()

        logger.info(
            f"Batch job {job_id} completed: {processed} processed, {failed} failed, "
            f"by {current_username}"
        )

    except Exception as e:
        logger.exception(f"Batch job {job_id} catastrophic failure: {e}")
        if conn:
            try:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE batch_jobs
                    SET status = 'failed', processed_systems = ?, failed_systems = ?,
                        failures = ?, completed_at = ?
                    WHERE id = ?
                ''', (
                    processed, failed,
                    json.dumps(failures + [{'error': f'Job worker failed: {str(e)[:500]}'}]),
                    datetime.now(timezone.utc).isoformat(), job_id,
                ))
                conn.commit()
            except Exception:
                pass
    finally:
        if conn:
            conn.close()

    # Post-job side effects: poster invalidation for every approved system,
    # plus a single batch-level activity-log entry. These fire on the calling
    # thread (already a worker thread); no need for fire_and_forget chain.
    try:
        for meta in approved_meta:
            try:
                _invalidate_posters_for_submission(
                    submitted_by=meta['submitted_by'],
                    galaxy=meta['galaxy'],
                    discord_tag=meta['discord_tag'],
                    system_id=meta.get('system_id'),
                    region_coords=meta.get('region_coords'),
                    reality=meta.get('reality'),
                )
            except Exception as inv_err:
                logger.warning(f"Batch job {job_id}: poster invalidation for one submission failed: {inv_err}")
    except Exception as e:
        logger.warning(f"Batch job {job_id}: poster invalidation pass failed: {e}")

    try:
        add_activity_log(
            'batch_approval',
            f"Batch approval job {job_id}: {processed - failed} approved, {failed} failed",
            f"Job ID: {job_id}, Processed: {processed}, Failed: {failed}, Approver: {current_username}",
            current_username,
        )
    except Exception as e:
        logger.warning(f"Batch job {job_id}: activity log write failed: {e}")


async def _run_batch_approval_job(job_id: str, submission_ids: list, session_snapshot: dict):
    """Async wrapper: offloads the synchronous worker to a thread so the
    sqlite3 calls don't block the event loop."""
    import asyncio as _asyncio
    await _asyncio.to_thread(_process_batch_approvals_sync, job_id, submission_ids, session_snapshot)


@router.get('/api/batch_jobs/{job_id}')
async def get_batch_job_status(job_id: str, session: Optional[str] = Cookie(None)):
    """Poll the status of an async batch-approval job.

    Frontend polls this every 2-3 seconds until status == 'completed' or
    'failed'. Returns 404 if the job doesn't exist.
    """
    if not verify_session(session):
        raise HTTPException(status_code=401, detail="Admin authentication required")

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, status, total_systems, processed_systems, failed_systems,
                   failures, submitted_by_username, created_at, completed_at
            FROM batch_jobs WHERE id = ?
        ''', (job_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Job not found")

        job = dict(row)
        try:
            job['failures'] = json.loads(job.get('failures') or '[]')
        except (json.JSONDecodeError, TypeError):
            job['failures'] = []
        job['successful_systems'] = max(job['processed_systems'] - job['failed_systems'], 0)
        return job
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to read batch job status: {e}")
        raise HTTPException(status_code=500, detail="Failed to read job status")
    finally:
        if conn:
            conn.close()


@router.post('/api/reject_systems/batch')
async def batch_reject_systems(
    payload: dict,
    background_tasks: BackgroundTasks,
    session: Optional[str] = Cookie(None),
):
    """
    Batch reject multiple pending system submissions with a shared reason (admin only).
    Requires 'batch_approvals' feature for non-super-admins.
    Self-submissions are skipped (not failed) for non-super-admin users.
    """
    # Verify admin session
    if not verify_session(session):
        raise HTTPException(status_code=401, detail="Admin authentication required")

    session_data = get_session(session)
    current_user_type = session_data.get('user_type')
    current_username = session_data.get('username')
    enabled_features = session_data.get('enabled_features', [])

    # Permission check: super admin OR has both approvals AND batch_approvals features
    is_super = current_user_type == 'super_admin'
    require_feature(session_data, 'approvals')
    if not is_super and 'batch_approvals' not in enabled_features:
        raise HTTPException(status_code=403, detail="Batch approvals permission required")

    current_account_id = None
    if current_user_type == 'partner':
        current_account_id = session_data.get('partner_id')
    elif current_user_type == 'sub_admin':
        current_account_id = session_data.get('sub_admin_id')

    submission_ids = payload.get('submission_ids', [])
    reason = payload.get('reason', 'No reason provided')

    if not submission_ids:
        raise HTTPException(status_code=400, detail="No submission IDs provided")

    if not reason or not reason.strip():
        raise HTTPException(status_code=400, detail="Rejection reason is required")

    results = {
        'rejected': [],
        'failed': [],
        'skipped': []
    }

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        for submission_id in submission_ids:
            try:
                # Get submission
                cursor.execute('SELECT * FROM pending_systems WHERE id = ?', (submission_id,))
                row = cursor.fetchone()

                if not row:
                    results['failed'].append({
                        'id': submission_id,
                        'name': None,
                        'error': 'Submission not found'
                    })
                    continue

                submission = dict(row)
                system_name = submission.get('system_name')

                if submission['status'] != 'pending':
                    results['skipped'].append({
                        'id': submission_id,
                        'name': system_name,
                        'reason': f"Already {submission['status']}"
                    })
                    continue

                # Self-rejection check (skip for non-super-admins)
                if not is_super and check_self_submission(submission, session_data):
                    results['skipped'].append({
                        'id': submission_id,
                        'name': system_name,
                        'reason': 'Self-submission'
                    })
                    continue

                # Mark as rejected
                cursor.execute('''
                    UPDATE pending_systems
                    SET status = ?, reviewed_by = ?, review_date = ?, rejection_reason = ?
                    WHERE id = ?
                ''', ('rejected', current_username, datetime.now(timezone.utc).isoformat(), reason, submission_id))

                # Add to approval audit log
                cursor.execute('''
                    INSERT INTO approval_audit_log
                    (timestamp, action, submission_type, submission_id, submission_name,
                     approver_username, approver_type, approver_account_id, approver_discord_tag,
                     submitter_username, submitter_account_id, submitter_type, notes, submission_discord_tag, source)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    datetime.now(timezone.utc).isoformat(),
                    'rejected',
                    'system',
                    submission_id,
                    system_name,
                    current_username,
                    current_user_type,
                    current_account_id,
                    session_data.get('discord_tag'),
                    submission.get('personal_discord_username') or submission.get('submitted_by'),
                    submission.get('submitter_account_id'),
                    submission.get('submitter_account_type'),
                    reason,
                    submission.get('discord_tag'),
                    submission.get('source', 'manual')
                ))

                results['rejected'].append({
                    'id': submission_id,
                    'name': system_name
                })

            except Exception as e:
                logger.error(f"Batch rejection: Error processing submission {submission_id}: {e}")
                results['failed'].append({
                    'id': submission_id,
                    'name': system_name if 'system_name' in dir() else None,
                    'error': str(e)
                })

        conn.commit()

        # Activity log fires after the response. See services/dispatch.py.
        background_tasks.add_task(
            add_activity_log,
            'batch_rejection',
            f"Batch rejected {len(results['rejected'])} systems",
            f"Rejected: {len(results['rejected'])}, Failed: {len(results['failed'])}, Skipped: {len(results['skipped'])}, Reason: {reason}, Reviewer: {current_username}",
            current_username,
        )

        logger.info(f"Batch rejection completed by {current_username}: {len(results['rejected'])} rejected, {len(results['failed'])} failed, {len(results['skipped'])} skipped. Reason: {reason}")

        return {
            'status': 'ok',
            'results': results,
            'summary': {
                'total': len(submission_ids),
                'rejected': len(results['rejected']),
                'failed': len(results['failed']),
                'skipped': len(results['skipped'])
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Batch rejection error: {e}")
        logger.exception("Batch rejection failed")
        raise HTTPException(status_code=500, detail="Batch rejection failed")
    finally:
        if conn:
            conn.close()


# =============================================================================
# HAVEN EXTRACTOR API ENDPOINTS
# =============================================================================

# --- Glyph Duplicate Checking ---

@router.post('/api/check_glyph_codes')
async def check_glyph_codes(
    payload: dict,
    request: Request,
    x_api_key: Optional[str] = Header(None, alias='X-API-Key')
):
    """
    Pre-flight duplicate check for Haven Extractor batch uploads.
    Checks multiple glyph codes against both approved systems and pending submissions.

    Required permission: check_duplicate

    Request body:
    {
        "glyph_codes": ["ABC123DEF456", "111111111111", "222222222222"]
    }

    Response:
    {
        "results": {
            "ABC123DEF456": {"status": "available", "exists": false},
            "111111111111": {"status": "already_charted", "exists": true, "location": "approved", ...},
            "222222222222": {"status": "pending_review", "exists": true, "location": "pending", ...}
        },
        "summary": {"available": 1, "already_charted": 1, "pending_review": 1, "total": 3}
    }
    """
    # Validate API key and check for check_duplicate permission
    api_key_info = verify_api_key(x_api_key) if x_api_key else None

    if not api_key_info:
        raise HTTPException(status_code=401, detail="API key required for duplicate check")

    permissions = api_key_info.get('permissions', [])
    if isinstance(permissions, str):
        try:
            permissions = json.loads(permissions)
        except:
            permissions = []

    if 'check_duplicate' not in permissions and 'submit' not in permissions:
        raise HTTPException(status_code=403, detail="API key does not have check_duplicate permission")

    glyph_codes = payload.get('glyph_codes', [])
    if not glyph_codes or not isinstance(glyph_codes, list):
        raise HTTPException(status_code=400, detail="glyph_codes array is required")

    # Optional galaxy/reality for scoped dedup (defaults match most common case)
    galaxy = payload.get('galaxy', 'Euclid') or 'Euclid'
    reality = normalize_reality(payload.get('reality'))

    # Limit to prevent abuse
    if len(glyph_codes) > 100:
        raise HTTPException(status_code=400, detail="Maximum 100 glyph codes per request")

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        results = {}
        summary = {'available': 0, 'already_charted': 0, 'pending_review': 0, 'total': len(glyph_codes)}

        for glyph in glyph_codes:
            # Validate glyph format
            if not glyph or len(glyph) != 12:
                results[glyph] = {'status': 'invalid', 'exists': False, 'error': 'Invalid glyph code format'}
                continue

            # Canonical dedup: last-11 glyph chars + galaxy + reality
            approved_row = find_matching_system(cursor, glyph, galaxy, reality)

            if approved_row:
                results[glyph] = {
                    'status': 'already_charted',
                    'exists': True,
                    'location': 'approved',
                    'system_id': approved_row[0],
                    'system_name': approved_row[1],
                    'galaxy': galaxy,
                }
                summary['already_charted'] += 1
                continue

            # Check pending systems with same canonical dedup
            pending_row = find_matching_pending_system(cursor, glyph, galaxy, reality)

            if pending_row:
                results[glyph] = {
                    'status': 'pending_review',
                    'exists': True,
                    'location': 'pending',
                    'submission_id': pending_row[0],
                    'system_name': pending_row[1],
                }
                summary['pending_review'] += 1
                continue

            # Not found anywhere - available
            results[glyph] = {'status': 'available', 'exists': False}
            summary['available'] += 1

        logger.info(f"Duplicate check: {len(glyph_codes)} codes checked - {summary['available']} available, {summary['already_charted']} charted, {summary['pending_review']} pending")

        return JSONResponse({
            'results': results,
            'summary': summary
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error checking glyph codes: {e}")
        logger.exception("Internal server error")
        raise HTTPException(status_code=500, detail="Internal server error")
    finally:
        if conn:
            conn.close()


# NOTE: INTENTIONAL DESIGN:
# - The extraction endpoint uses API key auth, not session auth
# - It routes to pending_systems queue (same as public submissions), not direct save
# - Duplicate glyph_codes update the existing pending row rather than creating a new one

@router.post('/api/extraction')
async def receive_extraction(
    payload: dict,
    request: Request,
    x_api_key: Optional[str] = Header(None, alias='X-API-Key')
):
    """
    Receive extraction data from Haven Extractor (running in-game via pymhf).
    This endpoint accepts the JSON extraction format and converts it to a system submission.

    Expected payload format (from Haven Extractor v10+):
    {
        "extraction_time": "2024-01-15T12:00:00",
        "extractor_version": "10.0.0",
        "glyph_code": "0123456789AB",
        "galaxy_name": "Euclid",
        "galaxy_index": 0,
        "voxel_x": 100,
        "voxel_y": 50,
        "voxel_z": -200,
        "solar_system_index": 123,
        "system_name": "System Name",
        "star_type": "Yellow",
        "economy_type": "Trading",
        "economy_strength": "Wealthy",
        "conflict_level": "Low",
        "dominant_lifeform": "Gek",
        "reality": "Normal",
        "discord_username": "TurpitZz",
        "personal_id": "123456789012345678",
        "discord_tag": "Haven",
        "planets": [
            {
                "planet_index": 0,
                "planet_name": "Planet Name",
                "biome": "Lush",
                "biome_subtype": "Standard",
                "weather": "Pleasant",
                "sentinel_level": "Low",
                "flora_level": "High",
                "fauna_level": "Medium",
                "planet_size": "Large",
                "common_resource": "Copper",
                "uncommon_resource": "Carbon",
                "rare_resource": "Gold",
                "is_moon": false
            }
        ]
    }
    """
    # Validate API key if provided
    api_key_info = verify_api_key(x_api_key) if x_api_key else None

    # Get client IP for tracking
    client_ip = request.client.host if request.client else "unknown"

    # Extract required fields
    glyph_code = payload.get('glyph_code')
    if not glyph_code or len(glyph_code) != 12:
        raise HTTPException(status_code=400, detail="Invalid or missing glyph_code")

    # Decode glyph to get region coordinates
    try:
        glyph_coords = decode_glyph_to_coords(glyph_code)
        region_x = glyph_coords.get('region_x', 0)
        region_y = glyph_coords.get('region_y', 0)
        region_z = glyph_coords.get('region_z', 0)
    except Exception as e:
        logger.warning(f"Failed to decode glyph {glyph_code}: {e}")
        region_x = region_y = region_z = 0

    # Extract user identification fields (new in v10+)
    discord_username = payload.get('discord_username', '')
    personal_id = payload.get('personal_id', '')
    discord_tag = payload.get('discord_tag', 'personal')  # Default to personal if not specified
    reality = normalize_reality(payload.get('reality'))
    game_mode = payload.get('game_mode', 'Normal')  # v1.6.8: difficulty preset tracking
    # Profile ID: from payload (new extractor) or resolve from username/api_key
    submitter_profile_id = payload.get('profile_id')

    # Accept both star_color (v10+) and star_type (legacy)
    star_color = payload.get('star_color') or payload.get('star_type', 'Unknown')

    # Convert extraction format to submission format
    submission_data = {
        'name': payload.get('system_name', f"System_{glyph_code}"),
        'glyph_code': glyph_code,
        'galaxy': payload.get('galaxy_name', 'Euclid'),
        'reality': reality,
        'x': payload.get('voxel_x', 0),
        'y': payload.get('voxel_y', 0),
        'z': payload.get('voxel_z', 0),
        'region_x': region_x,
        'region_y': region_y,
        'region_z': region_z,
        'glyph_solar_system': payload.get('solar_system_index', 1),
        'star_color': star_color,
        'discovered_by': payload.get('discoverer_name', 'HavenExtractor'),
        'discovered_at': payload.get('extraction_time'),
        'source': resolve_source(api_key_info.get('name') if api_key_info else None),
        'extractor_version': payload.get('extractor_version', 'unknown'),
        'game_mode': game_mode,
        # v1.48.7: Accept description from extractor. Haven Extractor 1.9.2+ stuffs the
        # procedural name here when the user applies a custom name for renamed systems,
        # so the canonical procgen name isn't lost on approval.
        'description': payload.get('description', '') or '',
        # v1.48.2: Flag from extractor indicating NMS itself reports "-Data Unavailable-" /
        # "Uncharted" for economy/conflict/lifeform. When True, the four fields below are
        # set to None (NULL in DB) so the frontend can render them as unavailable rather
        # than as literal "Unknown" strings.
        'no_trade_data': bool(payload.get('no_trade_data', False)),
    }

    # Populate economy/conflict/lifeform only when NMS has data for them.
    # Extractor omits these keys from the payload for no-data systems (race_raw > 6).
    if submission_data['no_trade_data']:
        submission_data['economy_type'] = None
        submission_data['economy_level'] = None
        submission_data['conflict_level'] = None
        submission_data['dominant_lifeform'] = None
    else:
        submission_data['economy_type'] = payload.get('economy_type', 'Unknown')
        submission_data['economy_level'] = payload.get('economy_strength', 'Unknown')
        submission_data['conflict_level'] = payload.get('conflict_level', 'Unknown')
        submission_data['dominant_lifeform'] = payload.get('dominant_lifeform', 'Unknown')

    # Convert planets array
    planets = []
    moons = []
    for planet_data in payload.get('planets', []):
        planet_entry = {
            'name': planet_data.get('planet_name', f"Planet_{planet_data.get('planet_index', 0) + 1}"),
            'biome': planet_data.get('biome', 'Unknown'),
            'biome_subtype': planet_data.get('biome_subtype', 'Unknown'),
            'weather': planet_data.get('weather', 'Unknown'),
            'climate': planet_data.get('weather', 'Unknown'),  # Alias for Haven UI compatibility
            'sentinels': planet_data.get('sentinel_level', 'Unknown'),
            'sentinel': planet_data.get('sentinel_level', 'Unknown'),  # Alias for Haven UI compatibility
            'flora': planet_data.get('flora_level', 'Unknown'),
            'fauna': planet_data.get('fauna_level', 'Unknown'),
            'planet_size': planet_data.get('planet_size', 'Unknown'),
            'common_resource': planet_data.get('common_resource') if planet_data.get('common_resource') not in ('Unknown', 'None', '', None) and isinstance(planet_data.get('common_resource'), str) and len(planet_data.get('common_resource', '')) >= 2 else None,
            'uncommon_resource': planet_data.get('uncommon_resource') if planet_data.get('uncommon_resource') not in ('Unknown', 'None', '', None) and isinstance(planet_data.get('uncommon_resource'), str) and len(planet_data.get('uncommon_resource', '')) >= 2 else None,
            'rare_resource': planet_data.get('rare_resource') if planet_data.get('rare_resource') not in ('Unknown', 'None', '', None) and isinstance(planet_data.get('rare_resource'), str) and len(planet_data.get('rare_resource', '')) >= 2 else None,
            'materials': ', '.join([
                r for r in [
                    planet_data.get('plant_resource'),
                    planet_data.get('common_resource'),
                    planet_data.get('uncommon_resource'),
                    planet_data.get('rare_resource')
                ] if r and isinstance(r, str) and len(r) >= 2 and r[0].isalpha()
                   and r not in ('Unknown', 'None')
            ]),  # Comma-separated for Haven UI display
            # Planet specials + valuable resources
            'has_rings': planet_data.get('has_rings'),
            'is_dissonant': planet_data.get('is_dissonant') or planet_data.get('dissonance'),
            'is_infested': planet_data.get('is_infested') or planet_data.get('infested'),
            'extreme_weather': planet_data.get('extreme_weather') or planet_data.get('is_weather_extreme'),
            'water_world': planet_data.get('water_world'),
            'vile_brood': planet_data.get('vile_brood'),
            'ancient_bones': planet_data.get('ancient_bones'),
            'salvageable_scrap': planet_data.get('salvageable_scrap'),
            'storm_crystals': planet_data.get('storm_crystals'),
            'gravitino_balls': planet_data.get('gravitino_balls'),
            'is_gas_giant': planet_data.get('is_gas_giant'),
            'exotic_trophy': planet_data.get('exotic_trophy'),
            'is_bubble': planet_data.get('is_bubble'),
            'is_floating_islands': planet_data.get('is_floating_islands'),
        }

        if planet_data.get('is_moon', False):
            moons.append(planet_entry)
        else:
            planets.append(planet_entry)

    submission_data['planets'] = planets
    submission_data['moons'] = moons

    # Store in pending_systems for admin review
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Canonical dedup: last 11 glyph chars + galaxy + reality
        # Check approved systems first
        edit_system_id = None
        mismatch_flags = []
        existing_system_row = find_matching_system(
            cursor, glyph_code, submission_data['galaxy'], reality
        )
        if existing_system_row:
            edit_system_id = existing_system_row[0]
            # Build mismatch flags for approver review
            cursor.execute('SELECT * FROM systems WHERE id = ?', (existing_system_row[0],))
            existing_sys = cursor.fetchone()
            if existing_sys:
                existing_dict = dict(existing_sys)
                cursor.execute('SELECT id, name FROM planets WHERE system_id = ?', (existing_system_row[0],))
                planet_rows = cursor.fetchall()
                existing_dict['planets'] = [{'name': r['name']} for r in planet_rows]
                moon_names = []
                for p in planet_rows:
                    for m in cursor.execute('SELECT name FROM moons WHERE planet_id = ?', (p[0],)).fetchall():
                        moon_names.append({'name': m['name']})
                existing_dict['moons'] = moon_names
                mismatch_flags = build_mismatch_flags(existing_dict, submission_data)
            if mismatch_flags:
                submission_data['_mismatch_flags'] = mismatch_flags
            logger.info(f"Extraction matches existing system '{existing_system_row[1]}' "
                        f"(ID: {edit_system_id}) via coordinate match - marking as edit"
                        + (f" with mismatches: {mismatch_flags}" if mismatch_flags else ""))

        # Check for duplicate in pending submissions (same canonical dedup)
        existing_pending = find_matching_pending_system(
            cursor, glyph_code, submission_data['galaxy'], reality
        )

        if existing_pending:
            # MERGE: preserve manual-only fields from existing pending, overwrite with extractor data
            try:
                existing_system_data = json.loads(existing_pending[3])  # system_data column
            except (json.JSONDecodeError, TypeError):
                existing_system_data = {}

            merged_data = merge_system_data(existing_system_data, submission_data)
            # Preserve mismatch flags if we found them
            if mismatch_flags:
                merged_data['_mismatch_flags'] = mismatch_flags

            cursor.execute('''
                UPDATE pending_systems
                SET raw_json = ?, system_data = ?, submission_timestamp = ?,
                    discord_tag = ?, personal_discord_username = ?, personal_id = ?,
                    system_name = ?, galaxy = ?, reality = ?, glyph_code = ?,
                    region_x = ?, region_y = ?, region_z = ?,
                    x = ?, y = ?, z = ?, edit_system_id = ?
                WHERE id = ?
            ''', (
                json.dumps(merged_data),
                json.dumps(merged_data),
                datetime.now(timezone.utc).isoformat(),
                discord_tag if discord_tag else None,
                discord_username if discord_username else None,
                personal_id if personal_id else None,
                submission_data['name'],
                submission_data['galaxy'],
                reality,
                glyph_code,
                region_x,
                region_y,
                region_z,
                submission_data['x'],
                submission_data['y'],
                submission_data['z'],
                edit_system_id,
                existing_pending[0]
            ))
            conn.commit()

            logger.info(f"Merged extraction into pending submission for {glyph_code} (discord_tag={discord_tag})")
            return JSONResponse({
                'status': 'updated',
                'message': f'Extraction merged for {glyph_code}',
                'submission_id': existing_pending[0],
                'planet_count': len(planets),
                'moon_count': len(moons)
            })

        # Insert new pending submission with all fields
        now = datetime.now(timezone.utc).isoformat()
        raw_json_str = json.dumps(submission_data)

        # Resolve submitter_profile_id from payload, api_key, or username
        if not submitter_profile_id:
            # Try from API key link
            if api_key_info and api_key_info.get('profile_id'):
                submitter_profile_id = api_key_info['profile_id']
            # Fallback: look up or create profile from discord_username
            elif discord_username:
                submitter_profile_id = get_or_create_profile(
                    conn, discord_username,
                    discord_snowflake_id=personal_id or None,
                    default_civ_tag=discord_tag if discord_tag != 'personal' else None,
                    created_by='extraction'
                )

        # Get API key name for tracking (if authenticated)
        api_key_name = api_key_info.get('name') if api_key_info else None
        # Tag submissions from the old shared key as "unregistered"
        if api_key_info and api_key_info.get('key_type') == 'system':
            api_key_name = f"{api_key_info['name']} (unregistered)"

        submitter_display = discord_username if discord_username else 'HavenExtractor'

        # Source attribution via the canonical resolver. Keeper bot keys
        # (Keeper 2.0 / Keeper Bot) bucket as 'keeper_bot'; everything else
        # authenticated buckets as 'haven_extractor'.
        submission_source = resolve_source(api_key_info.get('name') if api_key_info else None)

        # Compute the indexed username_normalized column at write time.
        username_normalized = normalize_username_for_dedup(
            submitter_display if submitter_display and submitter_display != 'HavenExtractor'
            else (discord_username or 'Unknown')
        )

        cursor.execute('''
            INSERT INTO pending_systems (
                system_name, glyph_code, galaxy, reality, x, y, z,
                region_x, region_y, region_z,
                submitter_name, submitted_by, submission_timestamp, submission_date, status, source,
                raw_json, system_data, discord_tag, personal_discord_username, personal_id,
                submitted_by_ip, api_key_name, edit_system_id, game_mode, submitter_profile_id,
                username_normalized
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            submission_data['name'],
            glyph_code,
            submission_data['galaxy'],
            reality,
            submission_data['x'],
            submission_data['y'],
            submission_data['z'],
            region_x,
            region_y,
            region_z,
            submitter_display,
            submitter_display,  # submitted_by - was missing, caused "Anonymous" display
            now,
            now,  # submission_date
            'pending',
            submission_source,
            raw_json_str,
            raw_json_str,  # system_data (same as raw_json)
            discord_tag if discord_tag else None,
            discord_username if discord_username else None,
            personal_id if personal_id else None,
            client_ip,
            api_key_name,
            edit_system_id,
            game_mode,
            submitter_profile_id,
            username_normalized,
        ))
        conn.commit()
        submission_id = cursor.lastrowid

        # Update per-key submission stats
        if api_key_info:
            try:
                cursor.execute("""
                    UPDATE api_keys
                    SET total_submissions = COALESCE(total_submissions, 0) + 1,
                        last_submission_at = ?
                    WHERE id = ?
                """, (now, api_key_info['id']))
                conn.commit()
            except Exception:
                pass  # Non-critical, don't fail the submission

        logger.info(f"Received extraction from Haven Extractor: {glyph_code} with {len(planets)} planets, {len(moons)} moons (discord_tag={discord_tag}, user={discord_username})")

        return JSONResponse({
            'status': 'ok',
            'message': f'Extraction received for {glyph_code}',
            'submission_id': submission_id,
            'planet_count': len(planets),
            'moon_count': len(moons)
        }, status_code=201)

    except Exception as e:
        logger.error(f"Error storing extraction: {e}")
        logger.exception("Internal server error")
        raise HTTPException(status_code=500, detail="Internal server error")
    finally:
        if conn:
            conn.close()
