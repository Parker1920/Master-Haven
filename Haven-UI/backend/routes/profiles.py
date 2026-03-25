"""Unified user profile endpoints - public and admin."""

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Cookie, HTTPException, Request, Response

from constants import (
    TIER_SUPER_ADMIN, TIER_PARTNER, TIER_SUB_ADMIN,
    TIER_MEMBER, TIER_MEMBER_READONLY, TIER_TO_USER_TYPE,
    normalize_discord_username,
)
from db import get_db_connection
from services.auth_service import (
    _sessions,
    get_session,
    hash_password,
    verify_password,
    _needs_rehash,
    generate_session_token,
    normalize_username_for_dedup,
    find_fuzzy_profile_matches,
    get_or_create_profile,
)

logger = logging.getLogger('control.room')

router = APIRouter(tags=["profiles"])

# Session timeout - matches the value in control_room_api.py
SESSION_TIMEOUT_MINUTES = 20


# ============================================================================
# Unified User Profile Endpoints
# ============================================================================

@router.post('/api/profiles/lookup')
async def profile_lookup(request: Request):
    """
    Public endpoint: Look up a profile by username.
    Returns exact match, fuzzy suggestions, or not_found.
    Used by Wizard and DiscoverySubmitModal before submission.
    """
    body = await request.json()
    username = (body.get('username') or '').strip()
    if not username:
        raise HTTPException(status_code=400, detail="Username is required")

    normalized = normalize_username_for_dedup(username)
    if not normalized:
        raise HTTPException(status_code=400, detail="Invalid username")

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Exact match
        cursor.execute("""
            SELECT id, username, display_name, default_civ_tag, tier, default_reality, default_galaxy
            FROM user_profiles WHERE username_normalized = ? AND is_active = 1
        """, (normalized,))
        row = cursor.fetchone()

        if row:
            return {
                'status': 'found',
                'profile': {
                    'id': row['id'],
                    'username': row['username'],
                    'display_name': row['display_name'],
                    'default_civ_tag': row['default_civ_tag'],
                    'tier': row['tier'],
                    'default_reality': row['default_reality'],
                    'default_galaxy': row['default_galaxy'],
                }
            }

        # Fuzzy match
        suggestions = find_fuzzy_profile_matches(conn, username)
        if suggestions:
            return {'status': 'suggestions', 'suggestions': suggestions}

        return {'status': 'not_found'}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Profile lookup failed: {e}")
        raise HTTPException(status_code=500, detail="Lookup failed")
    finally:
        if conn:
            conn.close()


@router.post('/api/profiles/create')
async def profile_create(request: Request):
    """
    Public endpoint: Create a new tier-5 (readonly) profile.
    Optionally set a password to immediately become tier 4.
    Used during first-submission flow.
    """
    body = await request.json()
    username = (body.get('username') or '').strip()
    password = body.get('password')
    default_civ_tag = (body.get('default_civ_tag') or '').strip() or None
    discord_snowflake_id = (body.get('discord_snowflake_id') or '').strip() or None

    if not username:
        raise HTTPException(status_code=400, detail="Username is required")
    if len(username) < 2 or len(username) > 64:
        raise HTTPException(status_code=400, detail="Username must be 2-64 characters")

    normalized = normalize_username_for_dedup(username)
    if not normalized:
        raise HTTPException(status_code=400, detail="Invalid username")

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Check for existing profile
        cursor.execute("SELECT id FROM user_profiles WHERE username_normalized = ?", (normalized,))
        if cursor.fetchone():
            raise HTTPException(status_code=409, detail="A profile with this username already exists")

        tier = TIER_MEMBER_READONLY
        password_hash = None
        if password and len(password) >= 4:
            password_hash = hash_password(password)
            tier = TIER_MEMBER

        now = datetime.now(timezone.utc).isoformat()
        cursor.execute('''
            INSERT INTO user_profiles (
                username, username_normalized, password_hash, display_name, tier,
                default_civ_tag, discord_snowflake_id, default_reality, default_galaxy,
                created_by, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, NULL, NULL, 'self_registration', ?, ?)
        ''', (username, normalized, password_hash, username, tier,
              default_civ_tag, discord_snowflake_id, now, now))
        conn.commit()

        profile_id = cursor.lastrowid
        logger.info(f"Created profile '{username}' (id={profile_id}, tier={tier})")

        return {
            'status': 'created',
            'profile': {
                'id': profile_id,
                'username': username,
                'display_name': username,
                'tier': tier,
                'default_civ_tag': default_civ_tag,
                'has_password': password_hash is not None,
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Profile creation failed: {e}")
        raise HTTPException(status_code=500, detail="Profile creation failed")
    finally:
        if conn:
            conn.close()


@router.post('/api/profiles/use')
async def profile_use(request: Request):
    """
    Public endpoint: Use an existing profile by confirming identity.
    Used when fuzzy matching shows a suggestion and the user confirms "that's me".
    Returns the profile data for the selected profile.
    """
    body = await request.json()
    profile_id = body.get('profile_id')
    username = (body.get('username') or '').strip()

    if not profile_id:
        raise HTTPException(status_code=400, detail="profile_id is required")

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, username, display_name, default_civ_tag, tier,
                   default_reality, default_galaxy
            FROM user_profiles WHERE id = ? AND is_active = 1
        """, (profile_id,))
        row = cursor.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Profile not found")

        return {
            'status': 'ok',
            'profile': {
                'id': row['id'],
                'username': row['username'],
                'display_name': row['display_name'],
                'default_civ_tag': row['default_civ_tag'],
                'tier': row['tier'],
                'default_reality': row['default_reality'],
                'default_galaxy': row['default_galaxy'],
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Profile claim failed: {e}")
        raise HTTPException(status_code=500, detail="Claim failed")
    finally:
        if conn:
            conn.close()


@router.post('/api/profile/login')
async def profile_login(credentials: dict, response: Response):
    """
    Passwordless login for tier 4/5 members.
    Username-only = tier 5 read-only session.
    Username + password = tier 4+ full session (same as /api/admin/login for members).
    """
    username = (credentials.get('username') or '').strip()
    password = credentials.get('password')

    if not username:
        raise HTTPException(status_code=400, detail="Username is required")

    normalized = normalize_username_for_dedup(username)
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, username, password_hash, display_name, tier,
                   default_civ_tag, enabled_features, partner_discord_tag,
                   default_reality, default_galaxy, is_active
            FROM user_profiles WHERE username_normalized = ?
        """, (normalized,))
        row = cursor.fetchone()

        if not row:
            # Try fuzzy match to give helpful suggestions
            suggestions = find_fuzzy_profile_matches(conn, username)
            if suggestions:
                suggestion_names = [s['username'] for s in suggestions[:3]]
                raise HTTPException(
                    status_code=404,
                    detail={
                        'message': 'Username not found. Did you mean one of these?',
                        'suggestions': suggestion_names
                    }
                )
            raise HTTPException(status_code=401, detail="Username not found. Submit a system or discovery to create your profile.")

        if not row['is_active']:
            raise HTTPException(status_code=401, detail="Account is deactivated")

        tier = row['tier']

        # Admin-tier users (1-3) must use /api/admin/login for full session
        if tier <= TIER_SUB_ADMIN:
            raise HTTPException(status_code=401, detail="Admin accounts must use the admin login. Use the Admin/Partner login tab.")

        # If password provided, verify it
        if password:
            if not row['password_hash']:
                raise HTTPException(status_code=401, detail="No password set on this account. Login with username only for read-only access, or set a password first.")
            if not verify_password(password, row['password_hash']):
                raise HTTPException(status_code=401, detail="Invalid password")
            # Upgrade hash if needed
            if _needs_rehash(row['password_hash']):
                cursor.execute('UPDATE user_profiles SET password_hash = ? WHERE id = ?',
                               (hash_password(password), row['id']))
        else:
            # Passwordless login - force read-only
            tier = TIER_MEMBER_READONLY

        user_type = TIER_TO_USER_TYPE.get(tier, 'member_readonly')

        # Update last login
        cursor.execute('UPDATE user_profiles SET last_login_at = ? WHERE id = ?',
                       (datetime.now(timezone.utc).isoformat(), row['id']))
        conn.commit()

        session_token = generate_session_token()
        _sessions[session_token] = {
            'user_type': user_type,
            'profile_id': row['id'],
            'username': row['username'],
            'discord_tag': row['partner_discord_tag'] or row['default_civ_tag'],
            'display_name': row['display_name'] or row['username'],
            'enabled_features': json.loads(row['enabled_features'] or '[]'),
            'tier': tier,
            'default_civ_tag': row['default_civ_tag'],
            'default_reality': row['default_reality'],
            'default_galaxy': row['default_galaxy'],
            'expires_at': datetime.now(timezone.utc) + timedelta(minutes=SESSION_TIMEOUT_MINUTES)
        }

        response.set_cookie(key='session', value=session_token,
                            httponly=True, max_age=600, samesite='lax')

        return {
            'status': 'ok',
            'logged_in': True,
            'user_type': user_type,
            'username': row['username'],
            'display_name': row['display_name'] or row['username'],
            'profile_id': row['id'],
            'tier': tier,
            'default_civ_tag': row['default_civ_tag'],
            'default_reality': row['default_reality'],
            'default_galaxy': row['default_galaxy'],
            'enabled_features': json.loads(row['enabled_features'] or '[]'),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Profile login failed: {e}")
        raise HTTPException(status_code=500, detail="Login failed")
    finally:
        if conn:
            conn.close()


@router.get('/api/profiles/me')
async def profile_me(session: Optional[str] = Cookie(None)):
    """Get the current user's full profile. Requires any login (including passwordless)."""
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail="Not authenticated")

    profile_id = session_data.get('profile_id')
    if not profile_id:
        # Legacy session without profile_id (super admin before migration)
        return {
            'username': session_data.get('username'),
            'display_name': session_data.get('display_name'),
            'tier': TIER_SUPER_ADMIN if session_data.get('user_type') == 'super_admin' else None,
            'user_type': session_data.get('user_type'),
        }

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, username, display_name, default_civ_tag, discord_snowflake_id,
                   tier, partner_discord_tag, enabled_features, default_reality,
                   default_galaxy, is_active, created_at, last_login_at,
                   password_hash IS NOT NULL as has_password
            FROM user_profiles WHERE id = ?
        """, (profile_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Profile not found")

        # Get submission stats (match by profile_id OR username OR partner tag for pre-profile submissions)
        username = row['username']
        partner_tag = row['partner_discord_tag'] if 'partner_discord_tag' in row.keys() else None
        if partner_tag:
            cursor.execute("""
                SELECT COUNT(DISTINCT id) as count FROM systems
                WHERE profile_id = ? OR personal_discord_username = ? OR discovered_by = ? OR discord_tag = ?
            """, (profile_id, username, username, partner_tag))
        else:
            cursor.execute("""
                SELECT COUNT(DISTINCT id) as count FROM systems
                WHERE profile_id = ? OR personal_discord_username = ? OR discovered_by = ?
            """, (profile_id, username, username))
        system_count = cursor.fetchone()['count']
        if partner_tag:
            cursor.execute("""
                SELECT COUNT(DISTINCT id) as count FROM discoveries
                WHERE profile_id = ? OR discovered_by = ? OR discord_tag = ?
            """, (profile_id, username, partner_tag))
        else:
            cursor.execute("""
                SELECT COUNT(DISTINCT id) as count FROM discoveries
                WHERE profile_id = ? OR discovered_by = ?
            """, (profile_id, username))
        discovery_count = cursor.fetchone()['count']

        return {
            'id': row['id'],
            'username': row['username'],
            'display_name': row['display_name'],
            'default_civ_tag': row['default_civ_tag'],
            'discord_snowflake_id': row['discord_snowflake_id'],
            'tier': row['tier'],
            'user_type': TIER_TO_USER_TYPE.get(row['tier'], 'member_readonly'),
            'partner_discord_tag': row['partner_discord_tag'],
            'enabled_features': json.loads(row['enabled_features'] or '[]'),
            'default_reality': row['default_reality'],
            'default_galaxy': row['default_galaxy'],
            'has_password': bool(row['has_password']),
            'created_at': row['created_at'],
            'last_login_at': row['last_login_at'],
            'stats': {
                'systems': system_count,
                'discoveries': discovery_count,
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Profile me failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to get profile")
    finally:
        if conn:
            conn.close()


@router.get('/api/profiles/me/submissions')
async def profile_my_submissions(
    page: int = 1,
    per_page: int = 50,
    source: Optional[str] = None,
    session: Optional[str] = Cookie(None)
):
    """Get the current user's systems and pending submissions with pagination and source filter."""
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail="Not authenticated")

    profile_id = session_data.get('profile_id')
    username = session_data.get('username', '')
    partner_tag = session_data.get('discord_tag') if session_data.get('user_type') == 'partner' else None

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Build WHERE clause for matching user's systems
        if profile_id and username and partner_tag:
            where = "(s.profile_id = ? OR s.personal_discord_username = ? OR s.discovered_by = ? OR s.discord_tag = ?)"
            params = [profile_id, username, username, partner_tag]
        elif profile_id and username:
            where = "(s.profile_id = ? OR s.personal_discord_username = ? OR s.discovered_by = ?)"
            params = [profile_id, username, username]
        elif profile_id:
            where = "s.profile_id = ?"
            params = [profile_id]
        else:
            where = "(s.personal_discord_username = ? OR s.discovered_by = ?)"
            params = [username, username]

        # Add source filter
        source_filter = ""
        if source == 'manual':
            source_filter = " AND COALESCE(s.source, 'manual') = 'manual'"
        elif source == 'haven_extractor':
            source_filter = " AND s.source = 'haven_extractor'"

        # Count total
        cursor.execute(f"SELECT COUNT(DISTINCT s.id) FROM systems s WHERE {where}{source_filter}", params)
        total = cursor.fetchone()[0]

        # Count by source for tab badges
        cursor.execute(f"""
            SELECT COALESCE(s.source, 'manual') as src, COUNT(DISTINCT s.id) as cnt
            FROM systems s WHERE {where}
            GROUP BY src
        """, params)
        source_counts = {r[0]: r[1] for r in cursor.fetchall()}

        # Paginated systems
        offset = (page - 1) * per_page
        cursor.execute(f"""
            SELECT DISTINCT s.id, s.name, s.galaxy, s.reality, s.star_type, s.discord_tag,
                   s.is_complete, s.created_at, COALESCE(s.source, 'manual') as source
            FROM systems s WHERE {where}{source_filter}
            ORDER BY s.created_at DESC
            LIMIT ? OFFSET ?
        """, params + [per_page, offset])
        systems = [dict(r) for r in cursor.fetchall()]

        # Pending submissions (only status='pending', no pagination needed - usually small)
        if profile_id and username:
            cursor.execute("""
                SELECT id, system_name, galaxy, reality, status, submission_date, discord_tag,
                       COALESCE(source, 'manual') as source
                FROM pending_systems WHERE status = 'pending' AND (submitter_profile_id = ? OR personal_discord_username = ? OR submitted_by = ?)
                ORDER BY submission_date DESC
            """, (profile_id, username, username))
        elif profile_id:
            cursor.execute("""
                SELECT id, system_name, galaxy, reality, status, submission_date, discord_tag,
                       COALESCE(source, 'manual') as source
                FROM pending_systems WHERE status = 'pending' AND submitter_profile_id = ?
                ORDER BY submission_date DESC
            """, (profile_id,))
        else:
            cursor.execute("""
                SELECT id, system_name, galaxy, reality, status, submission_date, discord_tag,
                       COALESCE(source, 'manual') as source
                FROM pending_systems WHERE status = 'pending' AND (personal_discord_username = ? OR submitted_by = ?)
                ORDER BY submission_date DESC
            """, (username, username))
        pending = [dict(r) for r in cursor.fetchall()]
        seen_ids = set()
        pending = [p for p in pending if not (p['id'] in seen_ids or seen_ids.add(p['id']))]

        return {
            'systems': systems,
            'pending': pending,
            'total': total,
            'page': page,
            'per_page': per_page,
            'total_pages': max(1, (total + per_page - 1) // per_page),
            'source_counts': {
                'manual': source_counts.get('manual', 0),
                'haven_extractor': source_counts.get('haven_extractor', 0),
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Profile submissions failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to get submissions")
    finally:
        if conn:
            conn.close()


@router.put('/api/profiles/me')
async def profile_update_me(request: Request, session: Optional[str] = Cookie(None)):
    """
    Update the current user's profile preferences.
    Requires tier 4+ (must have password set). Tier 5 gets 403.
    """
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail="Not authenticated")

    if session_data.get('user_type') == 'member_readonly':
        raise HTTPException(status_code=403, detail="Set a password to edit your profile")

    profile_id = session_data.get('profile_id')
    if not profile_id:
        raise HTTPException(status_code=400, detail="No profile linked to this session")

    body = await request.json()
    allowed_fields = {'display_name', 'default_civ_tag', 'default_reality', 'default_galaxy'}
    updates = {k: v for k, v in body.items() if k in allowed_fields and v is not None}

    if not updates:
        raise HTTPException(status_code=400, detail="No valid fields to update")

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        set_clause = ', '.join(f"{k} = ?" for k in updates.keys())
        values = list(updates.values()) + [datetime.now(timezone.utc).isoformat(), profile_id]
        cursor.execute(f"UPDATE user_profiles SET {set_clause}, updated_at = ? WHERE id = ?", values)
        conn.commit()

        # Update the in-memory session so /api/admin/status returns fresh data
        if 'display_name' in updates:
            session_data['display_name'] = updates['display_name']
        if 'default_civ_tag' in updates:
            session_data['default_civ_tag'] = updates['default_civ_tag']
            # Also update discord_tag if this is a member (their discord_tag comes from default_civ_tag)
            if session_data.get('user_type') in ('member', 'member_readonly'):
                session_data['discord_tag'] = updates['default_civ_tag']
        if 'default_reality' in updates:
            session_data['default_reality'] = updates['default_reality']
        if 'default_galaxy' in updates:
            session_data['default_galaxy'] = updates['default_galaxy']

        logger.info(f"Profile {profile_id} updated fields: {list(updates.keys())}")
        return {'status': 'ok', 'updated': list(updates.keys())}
    except Exception as e:
        logger.error(f"Profile update failed: {e}")
        raise HTTPException(status_code=500, detail="Update failed")
    finally:
        if conn:
            conn.close()


@router.post('/api/profiles/me/set-password')
async def profile_set_password(request: Request, session: Optional[str] = Cookie(None)):
    """
    Set or change password on the current profile.
    If tier 5 (no password), promotes to tier 4. Requires current password if already set.
    """
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail="Not authenticated")

    profile_id = session_data.get('profile_id')
    if not profile_id:
        raise HTTPException(status_code=400, detail="No profile linked to this session")

    body = await request.json()
    new_password = body.get('new_password', '')
    current_password = body.get('current_password', '')

    if not new_password or len(new_password) < 4:
        raise HTTPException(status_code=400, detail="New password must be at least 4 characters")

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT password_hash, tier FROM user_profiles WHERE id = ?", (profile_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Profile not found")

        # If already has a password, require current password
        if row['password_hash']:
            if not current_password:
                raise HTTPException(status_code=400, detail="Current password is required")
            if not verify_password(current_password, row['password_hash']):
                raise HTTPException(status_code=401, detail="Current password is incorrect")

        new_hash = hash_password(new_password)
        new_tier = row['tier']
        # Promote tier 5 to tier 4 when setting password
        if new_tier == TIER_MEMBER_READONLY:
            new_tier = TIER_MEMBER

        cursor.execute("""
            UPDATE user_profiles SET password_hash = ?, tier = ?, updated_at = ? WHERE id = ?
        """, (new_hash, new_tier, datetime.now(timezone.utc).isoformat(), profile_id))
        conn.commit()

        # Update session to reflect new tier
        session_data['tier'] = new_tier
        session_data['user_type'] = TIER_TO_USER_TYPE.get(new_tier, 'member')

        logger.info(f"Profile {profile_id} password set, tier now {new_tier}")
        return {'status': 'ok', 'tier': new_tier, 'user_type': session_data['user_type']}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Set password failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to set password")
    finally:
        if conn:
            conn.close()


# --- Admin Profile Management Endpoints ---

@router.get('/api/admin/profiles')
async def admin_list_profiles(
    session: Optional[str] = Cookie(None),
    tier: Optional[int] = None,
    search: Optional[str] = None,
    discord_tag: Optional[str] = None,
    page: int = 1,
    per_page: int = 50
):
    """
    List all user profiles (admin only).
    Super admin sees all. Partners see profiles in their community.
    """
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail="Not authenticated")
    if session_data.get('user_type') not in ('super_admin', 'partner', 'sub_admin'):
        raise HTTPException(status_code=403, detail="Admin access required")

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        where_clauses = []
        params = []

        if tier is not None:
            where_clauses.append("up.tier = ?")
            params.append(tier)

        if search:
            where_clauses.append("(up.username LIKE ? OR up.display_name LIKE ?)")
            params.extend([f"%{search}%", f"%{search}%"])

        # Partner scoping: only show profiles that have submitted to their community
        if session_data.get('user_type') == 'partner':
            partner_tag = session_data.get('discord_tag')
            if partner_tag:
                where_clauses.append("""(
                    up.default_civ_tag = ? OR up.partner_discord_tag = ?
                    OR up.id IN (SELECT DISTINCT profile_id FROM systems WHERE discord_tag = ? AND profile_id IS NOT NULL)
                    OR up.id IN (SELECT DISTINCT submitter_profile_id FROM pending_systems WHERE discord_tag = ? AND submitter_profile_id IS NOT NULL)
                )""")
                params.extend([partner_tag, partner_tag, partner_tag, partner_tag])

        if discord_tag:
            where_clauses.append("up.default_civ_tag = ?")
            params.append(discord_tag)

        where = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""
        offset = (page - 1) * per_page

        # Count total
        cursor.execute(f"SELECT COUNT(*) as total FROM user_profiles up {where}", params)
        total = cursor.fetchone()['total']

        # Fetch page
        cursor.execute(f"""
            SELECT up.id, up.username, up.display_name, up.tier, up.default_civ_tag,
                   up.partner_discord_tag, up.is_active, up.created_at, up.last_login_at,
                   up.password_hash IS NOT NULL as has_password,
                   (SELECT COUNT(*) FROM systems s WHERE s.profile_id = up.id OR s.personal_discord_username = up.username OR s.discovered_by = up.username OR (up.partner_discord_tag IS NOT NULL AND s.discord_tag = up.partner_discord_tag)) as system_count,
                   (SELECT COUNT(*) FROM discoveries d WHERE d.profile_id = up.id OR d.discovered_by = up.username OR (up.partner_discord_tag IS NOT NULL AND d.discord_tag = up.partner_discord_tag)) as discovery_count
            FROM user_profiles up
            {where}
            ORDER BY up.tier ASC, up.last_login_at DESC NULLS LAST
            LIMIT ? OFFSET ?
        """, params + [per_page, offset])

        profiles = []
        for row in cursor.fetchall():
            profiles.append({
                'id': row['id'],
                'username': row['username'],
                'display_name': row['display_name'],
                'tier': row['tier'],
                'user_type': TIER_TO_USER_TYPE.get(row['tier'], 'member_readonly'),
                'default_civ_tag': row['default_civ_tag'],
                'partner_discord_tag': row['partner_discord_tag'],
                'is_active': bool(row['is_active']),
                'has_password': bool(row['has_password']),
                'created_at': row['created_at'],
                'last_login_at': row['last_login_at'],
                'system_count': row['system_count'],
                'discovery_count': row['discovery_count'],
            })

        return {'profiles': profiles, 'total': total, 'page': page, 'per_page': per_page}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Admin list profiles failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to list profiles")
    finally:
        if conn:
            conn.close()


@router.get('/api/admin/profiles/{profile_id}')
async def admin_get_profile(profile_id: int, session: Optional[str] = Cookie(None)):
    """Get full profile detail (admin only)."""
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail="Not authenticated")
    if session_data.get('user_type') not in ('super_admin', 'partner', 'sub_admin'):
        raise HTTPException(status_code=403, detail="Admin access required")

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM user_profiles WHERE id = ?", (profile_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Profile not found")

        row = dict(row)

        # Get submission stats (match by profile_id OR username OR partner tag)
        username = row.get('username', '')
        partner_tag = row.get('partner_discord_tag')
        if partner_tag:
            cursor.execute("""
                SELECT COUNT(DISTINCT id) as c FROM systems
                WHERE profile_id = ? OR personal_discord_username = ? OR discovered_by = ? OR discord_tag = ?
            """, (profile_id, username, username, partner_tag))
        else:
            cursor.execute("""
                SELECT COUNT(DISTINCT id) as c FROM systems
                WHERE profile_id = ? OR personal_discord_username = ? OR discovered_by = ?
            """, (profile_id, username, username))
        system_count = cursor.fetchone()['c']
        if partner_tag:
            cursor.execute("""
                SELECT COUNT(DISTINCT id) as c FROM discoveries
                WHERE profile_id = ? OR discovered_by = ? OR discord_tag = ?
            """, (profile_id, username, partner_tag))
        else:
            cursor.execute("""
                SELECT COUNT(DISTINCT id) as c FROM discoveries
                WHERE profile_id = ? OR discovered_by = ?
            """, (profile_id, username))
        discovery_count = cursor.fetchone()['c']

        # Get parent profile info for sub-admins
        parent_info = None
        if row.get('parent_profile_id'):
            cursor.execute("SELECT id, username, display_name, partner_discord_tag FROM user_profiles WHERE id = ?",
                           (row['parent_profile_id'],))
            p = cursor.fetchone()
            if p:
                parent_info = dict(p)

        return {
            'id': row['id'],
            'username': row['username'],
            'display_name': row['display_name'],
            'tier': row['tier'],
            'user_type': TIER_TO_USER_TYPE.get(row['tier'], 'member_readonly'),
            'default_civ_tag': row['default_civ_tag'],
            'discord_snowflake_id': row['discord_snowflake_id'],
            'partner_discord_tag': row['partner_discord_tag'],
            'enabled_features': json.loads(row['enabled_features'] or '[]'),
            'theme_settings': json.loads(row['theme_settings'] or '{}'),
            'region_color': row['region_color'],
            'parent_profile_id': row['parent_profile_id'],
            'parent_info': parent_info,
            'additional_discord_tags': json.loads(row['additional_discord_tags'] or '[]'),
            'can_approve_personal_uploads': bool(row['can_approve_personal_uploads']),
            'default_reality': row['default_reality'],
            'default_galaxy': row['default_galaxy'],
            'has_password': row['password_hash'] is not None,
            'is_active': bool(row['is_active']),
            'created_at': row['created_at'],
            'updated_at': row['updated_at'],
            'last_login_at': row['last_login_at'],
            'stats': {'systems': system_count, 'discoveries': discovery_count},
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Admin get profile failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to get profile")
    finally:
        if conn:
            conn.close()


@router.put('/api/admin/profiles/{profile_id}/tier')
async def admin_set_profile_tier(profile_id: int, request: Request, session: Optional[str] = Cookie(None)):
    """
    Elevate or demote a user's tier (super admin only).
    For tier 2 (partner): must provide partner_discord_tag and enabled_features.
    For tier 3 (sub-admin): must provide parent_profile_id and enabled_features.
    """
    session_data = get_session(session)
    if not session_data or session_data.get('user_type') != 'super_admin':
        raise HTTPException(status_code=403, detail="Super admin required")

    body = await request.json()
    new_tier = body.get('tier')
    if new_tier not in (TIER_PARTNER, TIER_SUB_ADMIN, TIER_MEMBER, TIER_MEMBER_READONLY):
        raise HTTPException(status_code=400, detail="Invalid tier. Must be 2-5.")

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT id, username, tier, password_hash FROM user_profiles WHERE id = ?", (profile_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Profile not found")

        # Tier 2+ requires password
        if new_tier <= TIER_SUB_ADMIN and not row['password_hash']:
            raise HTTPException(status_code=400, detail="User must set a password before being elevated to admin tier")

        updates = {'tier': new_tier, 'updated_at': datetime.now(timezone.utc).isoformat()}

        if new_tier == TIER_PARTNER:
            partner_tag = (body.get('partner_discord_tag') or '').strip()
            if not partner_tag:
                raise HTTPException(status_code=400, detail="partner_discord_tag is required for partner tier")
            # Check uniqueness
            cursor.execute("SELECT id FROM user_profiles WHERE partner_discord_tag = ? AND id != ?",
                           (partner_tag, profile_id))
            if cursor.fetchone():
                raise HTTPException(status_code=409, detail=f"partner_discord_tag '{partner_tag}' is already taken")
            updates['partner_discord_tag'] = partner_tag
            updates['enabled_features'] = json.dumps(body.get('enabled_features', []))
            if 'theme_settings' in body:
                updates['theme_settings'] = json.dumps(body['theme_settings'])
            if 'region_color' in body:
                updates['region_color'] = body['region_color']
            # Clear sub-admin fields
            updates['parent_profile_id'] = None
            updates['additional_discord_tags'] = '[]'
            updates['can_approve_personal_uploads'] = 0

        elif new_tier == TIER_SUB_ADMIN:
            parent_id = body.get('parent_profile_id')
            updates['parent_profile_id'] = parent_id  # Can be None for Haven sub-admins
            updates['enabled_features'] = json.dumps(body.get('enabled_features', []))
            updates['additional_discord_tags'] = json.dumps(body.get('additional_discord_tags', []))
            updates['can_approve_personal_uploads'] = 1 if body.get('can_approve_personal_uploads') else 0
            # Clear partner fields
            updates['partner_discord_tag'] = None

        else:
            # Demoting to member - clear admin fields
            updates['partner_discord_tag'] = None
            updates['parent_profile_id'] = None
            updates['enabled_features'] = '[]'
            updates['additional_discord_tags'] = '[]'
            updates['can_approve_personal_uploads'] = 0

        set_clause = ', '.join(f"{k} = ?" for k in updates.keys())
        values = list(updates.values()) + [profile_id]
        cursor.execute(f"UPDATE user_profiles SET {set_clause} WHERE id = ?", values)
        conn.commit()

        logger.info(f"Profile {profile_id} ({row['username']}) tier changed: {row['tier']} -> {new_tier}")

        # Audit log for tier change
        tier_names = {1: 'Super Admin', 2: 'Partner', 3: 'Sub-Admin', 4: 'Member', 5: 'Read-Only'}
        try:
            cursor.execute('''
                INSERT INTO approval_audit_log
                (timestamp, action, submission_type, submission_id, submission_name,
                 approver_username, approver_type, approver_account_id, approver_discord_tag,
                 submitter_username, notes, submission_discord_tag, source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                datetime.now(timezone.utc).isoformat(),
                'tier_change',
                'profile',
                profile_id,
                row['username'],
                session_data.get('username'),
                session_data.get('user_type'),
                session_data.get('profile_id'),
                session_data.get('discord_tag'),
                row['username'],
                f"Tier changed: {tier_names.get(row['tier'], row['tier'])} -> {tier_names.get(new_tier, new_tier)}" +
                (f" (tag: {body.get('partner_discord_tag')})" if new_tier == TIER_PARTNER else ''),
                body.get('partner_discord_tag'),
                'manual'
            ))
            conn.commit()
        except Exception as audit_err:
            logger.warning(f"Failed to add tier change audit log: {audit_err}")

        return {'status': 'ok', 'profile_id': profile_id, 'new_tier': new_tier}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Admin set tier failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to update tier")
    finally:
        if conn:
            conn.close()


@router.put('/api/admin/profiles/{profile_id}')
async def admin_update_profile(profile_id: int, request: Request, session: Optional[str] = Cookie(None)):
    """
    Edit a profile (super admin for all, partner for own sub-admins).
    """
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail="Not authenticated")
    if session_data.get('user_type') not in ('super_admin', 'partner'):
        raise HTTPException(status_code=403, detail="Admin access required")

    body = await request.json()

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT id, username, tier, parent_profile_id FROM user_profiles WHERE id = ?", (profile_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Profile not found")

        # Partners can only edit their own sub-admins
        if session_data.get('user_type') == 'partner':
            if row['parent_profile_id'] != session_data.get('profile_id'):
                raise HTTPException(status_code=403, detail="Can only edit your own sub-admins")

        allowed = {'display_name', 'enabled_features', 'is_active',
                   'additional_discord_tags', 'can_approve_personal_uploads',
                   'default_civ_tag', 'theme_settings', 'region_color'}
        updates = {}
        for k, v in body.items():
            if k in allowed:
                if k in ('enabled_features', 'additional_discord_tags', 'theme_settings'):
                    updates[k] = json.dumps(v) if isinstance(v, (list, dict)) else v
                elif k == 'can_approve_personal_uploads':
                    updates[k] = 1 if v else 0
                elif k == 'is_active':
                    updates[k] = 1 if v else 0
                else:
                    updates[k] = v

        if not updates:
            raise HTTPException(status_code=400, detail="No valid fields to update")

        updates['updated_at'] = datetime.now(timezone.utc).isoformat()
        set_clause = ', '.join(f"{k} = ?" for k in updates.keys())
        values = list(updates.values()) + [profile_id]
        cursor.execute(f"UPDATE user_profiles SET {set_clause} WHERE id = ?", values)
        conn.commit()

        # Audit log for significant profile changes
        audit_fields = {'enabled_features', 'is_active', 'additional_discord_tags', 'can_approve_personal_uploads'}
        if audit_fields & set(body.keys()):
            try:
                action = 'deactivated' if body.get('is_active') == False else 'activated' if body.get('is_active') == True else 'permission_change'
                notes_parts = []
                if 'enabled_features' in body:
                    notes_parts.append(f"Features: {json.dumps(body['enabled_features'])}")
                if 'is_active' in body:
                    notes_parts.append(f"Active: {body['is_active']}")
                if 'additional_discord_tags' in body:
                    notes_parts.append(f"Additional tags: {json.dumps(body['additional_discord_tags'])}")
                if 'can_approve_personal_uploads' in body:
                    notes_parts.append(f"Can approve personal: {body['can_approve_personal_uploads']}")
                cursor.execute('''
                    INSERT INTO approval_audit_log
                    (timestamp, action, submission_type, submission_id, submission_name,
                     approver_username, approver_type, approver_account_id, approver_discord_tag,
                     submitter_username, notes, source)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    datetime.now(timezone.utc).isoformat(),
                    action,
                    'profile',
                    profile_id,
                    row['username'],
                    session_data.get('username'),
                    session_data.get('user_type'),
                    session_data.get('profile_id'),
                    session_data.get('discord_tag'),
                    row['username'],
                    '; '.join(notes_parts),
                    'manual'
                ))
                conn.commit()
            except Exception as audit_err:
                logger.warning(f"Failed to add profile edit audit log: {audit_err}")

        return {'status': 'ok', 'updated': list(body.keys())}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Admin update profile failed: {e}")
        raise HTTPException(status_code=500, detail="Update failed")
    finally:
        if conn:
            conn.close()


@router.post('/api/admin/profiles/{profile_id}/reset-password')
async def admin_reset_password(profile_id: int, request: Request, session: Optional[str] = Cookie(None)):
    """Reset a user's password (super admin, or partner for own sub-admins)."""
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail="Not authenticated")
    if session_data.get('user_type') not in ('super_admin', 'partner'):
        raise HTTPException(status_code=403, detail="Admin access required")

    body = await request.json()
    new_password = body.get('new_password', '')
    if not new_password or len(new_password) < 4:
        raise HTTPException(status_code=400, detail="New password must be at least 4 characters")

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT id, username, tier, parent_profile_id FROM user_profiles WHERE id = ?", (profile_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Profile not found")

        # Partners can only reset their own sub-admins
        if session_data.get('user_type') == 'partner':
            if row['parent_profile_id'] != session_data.get('profile_id'):
                raise HTTPException(status_code=403, detail="Can only reset password for your own sub-admins")

        new_hash = hash_password(new_password)
        new_tier = row['tier']
        if new_tier == TIER_MEMBER_READONLY:
            new_tier = TIER_MEMBER  # Promote on password set

        cursor.execute("""
            UPDATE user_profiles SET password_hash = ?, tier = ?, updated_at = ? WHERE id = ?
        """, (new_hash, new_tier, datetime.now(timezone.utc).isoformat(), profile_id))
        conn.commit()

        # Audit log for password reset
        try:
            cursor.execute('''
                INSERT INTO approval_audit_log
                (timestamp, action, submission_type, submission_id, submission_name,
                 approver_username, approver_type, approver_account_id, approver_discord_tag,
                 submitter_username, notes, source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                datetime.now(timezone.utc).isoformat(),
                'password_reset',
                'profile',
                profile_id,
                row['username'],
                session_data.get('username'),
                session_data.get('user_type'),
                session_data.get('profile_id'),
                session_data.get('discord_tag'),
                row['username'],
                'Admin password reset',
                'manual'
            ))
            conn.commit()
        except Exception as audit_err:
            logger.warning(f"Failed to add password reset audit log: {audit_err}")

        return {'status': 'ok', 'new_tier': new_tier}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Admin reset password failed: {e}")
        raise HTTPException(status_code=500, detail="Reset failed")
    finally:
        if conn:
            conn.close()
