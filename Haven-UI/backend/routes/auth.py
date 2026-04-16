"""Authentication, login, logout, password, and settings endpoints."""

import json
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Cookie, HTTPException, Response

from services.auth_service import (
    get_session,
    create_session,
    destroy_session,
    verify_session,
    hash_password,
    verify_password,
    _needs_rehash,
    generate_session_token,
    is_super_admin,
    is_partner,
    is_sub_admin,
    get_super_admin_password_hash,
    set_super_admin_password_hash,
    get_personal_color,
    set_personal_color,
    _settings_cache,
    normalize_username_for_dedup,
    get_or_create_profile,
)

from db import get_db_connection, get_db

from constants import (
    SUPER_ADMIN_USERNAME,
    TIER_SUPER_ADMIN,
    TIER_PARTNER,
    TIER_SUB_ADMIN,
    TIER_MEMBER,
    TIER_MEMBER_READONLY,
    TIER_TO_USER_TYPE,
    SESSION_TIMEOUT_MINUTES,
)

logger = logging.getLogger('control.room')

router = APIRouter()


# ============================================================================
# Health Check
# ============================================================================

@router.get('/api/status')
async def api_status():
    """Health check endpoint. Public. Returns API version for frontend compatibility checks."""
    return {'status': 'ok', 'version': '1.48.4', 'api': 'Master Haven'}


# ============================================================================
# Settings
# ============================================================================

@router.get('/api/settings')
async def get_settings():
    """Get current settings (theme, etc.)"""
    return _settings_cache

@router.post('/api/settings')
async def save_settings(settings: dict):
    """Save settings"""
    _settings_cache.update(settings)
    # Persist personal_color to database if provided
    if 'personal_color' in settings:
        set_personal_color(settings['personal_color'])
    return {'status': 'ok'}


# ============================================================================
# Admin Status (Session Check)
# ============================================================================

@router.get('/api/admin/status')
async def admin_status(session: Optional[str] = Cookie(None)):
    """Check login status and return user info. Called by AuthContext on every page load."""
    session_data = get_session(session)
    if not session_data:
        return {'logged_in': False}

    user_type = session_data.get('user_type')
    profile_id = session_data.get('profile_id')
    # Backward compat: account_id = profile_id
    account_id = profile_id
    if not account_id:
        if user_type == 'partner':
            account_id = session_data.get('partner_id')
        elif user_type == 'sub_admin':
            account_id = session_data.get('sub_admin_id')

    return {
        'logged_in': True,
        'user_type': user_type,
        'username': session_data.get('username'),
        'discord_tag': session_data.get('discord_tag'),
        'display_name': session_data.get('display_name'),
        'enabled_features': session_data.get('enabled_features', []),
        'account_id': account_id,
        'profile_id': profile_id,
        'tier': session_data.get('tier'),
        'default_civ_tag': session_data.get('default_civ_tag'),
        'default_reality': session_data.get('default_reality'),
        'default_galaxy': session_data.get('default_galaxy'),
        'parent_display_name': session_data.get('parent_display_name'),  # For sub-admins
        'is_haven_sub_admin': session_data.get('is_haven_sub_admin', False)  # True if sub-admin under Haven
    }


# ============================================================================
# Login
# ============================================================================

@router.post('/api/admin/login')
async def admin_login(credentials: dict, response: Response):
    """Login with username/password - supports all tiers via user_profiles table.
    Falls back to legacy partner_accounts/sub_admin_accounts if profile not found."""
    username = credentials.get('username', '').strip()
    password = credentials.get('password', '')

    if not username or not password:
        raise HTTPException(status_code=401, detail='Username and password are required')

    normalized = normalize_username_for_dedup(username)
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Primary path: look up in user_profiles
        cursor.execute("""
            SELECT id, username, username_normalized, password_hash, display_name, tier,
                   partner_discord_tag, enabled_features, theme_settings, region_color,
                   parent_profile_id, additional_discord_tags, can_approve_personal_uploads,
                   default_civ_tag, default_reality, default_galaxy, is_active
            FROM user_profiles WHERE username_normalized = ?
        """, (normalized,))
        profile = cursor.fetchone()

        if profile:
            profile = dict(profile)

            if not profile['is_active']:
                raise HTTPException(status_code=401, detail='Account is deactivated')

            if not profile['password_hash']:
                # Super admin may have password in super_admin_settings, not in profile
                if profile['tier'] == TIER_SUPER_ADMIN:
                    stored_hash = get_super_admin_password_hash()
                    if verify_password(password, stored_hash):
                        # Migrate password to profile
                        new_hash = hash_password(password) if _needs_rehash(stored_hash) else stored_hash
                        cursor.execute('UPDATE user_profiles SET password_hash = ? WHERE id = ?',
                                       (new_hash, profile['id']))
                        conn.commit()
                        profile['password_hash'] = new_hash
                    else:
                        raise HTTPException(status_code=401, detail='Invalid password')
                else:
                    raise HTTPException(status_code=401, detail='No password set. Use member login for read-only access, or set a password first.')

            if not verify_password(password, profile['password_hash']):
                raise HTTPException(status_code=401, detail='Invalid username or password')

            # Upgrade legacy hash
            if _needs_rehash(profile['password_hash']):
                cursor.execute('UPDATE user_profiles SET password_hash = ? WHERE id = ?',
                               (hash_password(password), profile['id']))

            # Update last login
            cursor.execute('UPDATE user_profiles SET last_login_at = ? WHERE id = ?',
                           (datetime.now(timezone.utc).isoformat(), profile['id']))
            conn.commit()

            tier = profile['tier']
            user_type = TIER_TO_USER_TYPE.get(tier, 'member')
            enabled_features = json.loads(profile['enabled_features'] or '[]')

            # Build session dict
            session_dict = {
                'user_type': user_type,
                'profile_id': profile['id'],
                'username': profile['username'],
                'discord_tag': profile['partner_discord_tag'] or profile['default_civ_tag'],
                'partner_id': profile['id'] if tier == TIER_PARTNER else profile['parent_profile_id'],
                'display_name': profile['display_name'] or profile['username'],
                'enabled_features': enabled_features,
                'tier': tier,
                'default_civ_tag': profile['default_civ_tag'],
                'default_reality': profile['default_reality'] or None,
                'default_galaxy': profile['default_galaxy'] or None,
            }

            # Sub-admin specific fields
            if tier == TIER_SUB_ADMIN:
                is_haven_sub_admin = profile['parent_profile_id'] is None
                additional_discord_tags = json.loads(profile['additional_discord_tags'] or '[]') if is_haven_sub_admin else []
                can_approve_personal_uploads = bool(profile['can_approve_personal_uploads']) if is_haven_sub_admin else False

                # Get parent info for discord_tag inheritance
                if profile['parent_profile_id']:
                    cursor.execute("SELECT partner_discord_tag, display_name FROM user_profiles WHERE id = ?",
                                   (profile['parent_profile_id'],))
                    parent = cursor.fetchone()
                    if parent:
                        session_dict['discord_tag'] = parent['partner_discord_tag']
                        session_dict['parent_display_name'] = parent['display_name']
                    else:
                        session_dict['parent_display_name'] = 'Unknown'
                else:
                    session_dict['discord_tag'] = None  # Haven sub-admin
                    session_dict['parent_display_name'] = 'Haven'

                session_dict['sub_admin_id'] = profile['id']
                session_dict['is_haven_sub_admin'] = is_haven_sub_admin
                session_dict['additional_discord_tags'] = additional_discord_tags
                session_dict['can_approve_personal_uploads'] = can_approve_personal_uploads

            session_token = generate_session_token()
            create_session(session_token, session_dict)

            response.set_cookie(key='session', value=session_token,
                                httponly=True, max_age=600, samesite='lax')

            result = {
                'status': 'ok',
                'logged_in': True,
                'user_type': user_type,
                'username': profile['username'],
                'discord_tag': session_dict.get('discord_tag'),
                'display_name': session_dict['display_name'],
                'enabled_features': enabled_features,
                'account_id': profile['id'],
                'profile_id': profile['id'],
                'tier': tier,
                'default_civ_tag': profile['default_civ_tag'],
                'default_reality': profile['default_reality'],
                'default_galaxy': profile['default_galaxy'],
            }
            if tier == TIER_SUB_ADMIN:
                result['parent_display_name'] = session_dict.get('parent_display_name')
                result['is_haven_sub_admin'] = session_dict.get('is_haven_sub_admin', False)
            return result

        # ── Fallback: legacy tables (for transition period) ──
        # Check super admin hardcoded username
        if username == SUPER_ADMIN_USERNAME:
            stored_hash = get_super_admin_password_hash()
            if verify_password(password, stored_hash):
                if _needs_rehash(stored_hash):
                    set_super_admin_password_hash(hash_password(password))
                session_token = generate_session_token()
                create_session(session_token, {
                    'user_type': 'super_admin',
                    'username': username,
                    'discord_tag': None,
                    'partner_id': None,
                    'display_name': 'Super Admin',
                    'enabled_features': ['all'],
                    'tier': TIER_SUPER_ADMIN,
                })
                response.set_cookie(key='session', value=session_token,
                                    httponly=True, max_age=600, samesite='lax')
                return {
                    'status': 'ok', 'logged_in': True, 'user_type': 'super_admin',
                    'username': username, 'discord_tag': None, 'display_name': 'Super Admin',
                    'enabled_features': ['all'], 'account_id': None
                }
            raise HTTPException(status_code=401, detail='Invalid password')

        # Fallback: check partner_accounts
        cursor.execute('SELECT id, password_hash, discord_tag, display_name, enabled_features, is_active FROM partner_accounts WHERE username = ?', (username,))
        row = cursor.fetchone()
        if row:
            if not row['is_active']:
                raise HTTPException(status_code=401, detail='Account is deactivated')
            if not verify_password(password, row['password_hash']):
                raise HTTPException(status_code=401, detail='Invalid username or password')
            if _needs_rehash(row['password_hash']):
                cursor.execute('UPDATE partner_accounts SET password_hash = ? WHERE id = ?', (hash_password(password), row['id']))
            cursor.execute('UPDATE partner_accounts SET last_login_at = ? WHERE id = ?', (datetime.now(timezone.utc).isoformat(), row['id']))
            conn.commit()
            enabled_features = json.loads(row['enabled_features'] or '[]')
            session_token = generate_session_token()
            create_session(session_token, {
                'user_type': 'partner', 'username': username, 'discord_tag': row['discord_tag'],
                'partner_id': row['id'], 'display_name': row['display_name'] or username,
                'enabled_features': enabled_features, 'tier': TIER_PARTNER,
            })
            response.set_cookie(key='session', value=session_token, httponly=True, max_age=600, samesite='lax')
            return {
                'status': 'ok', 'logged_in': True, 'user_type': 'partner', 'username': username,
                'discord_tag': row['discord_tag'], 'display_name': row['display_name'] or username,
                'enabled_features': enabled_features, 'account_id': row['id']
            }

        # Fallback: check sub_admin_accounts
        cursor.execute('''
            SELECT sa.id, sa.password_hash, sa.display_name, sa.enabled_features, sa.is_active,
                   sa.parent_partner_id, sa.additional_discord_tags, sa.can_approve_personal_uploads,
                   pa.discord_tag as parent_discord_tag, pa.display_name as parent_display_name,
                   pa.is_active as parent_is_active
            FROM sub_admin_accounts sa LEFT JOIN partner_accounts pa ON sa.parent_partner_id = pa.id
            WHERE sa.username = ?
        ''', (username,))
        sub_row = cursor.fetchone()
        if not sub_row:
            raise HTTPException(status_code=401, detail='Invalid username or password')
        if not sub_row['is_active']:
            raise HTTPException(status_code=401, detail='Account is deactivated')
        if sub_row['parent_partner_id'] and not sub_row['parent_is_active']:
            raise HTTPException(status_code=401, detail='Parent partner account is deactivated')
        if not verify_password(password, sub_row['password_hash']):
            raise HTTPException(status_code=401, detail='Invalid username or password')
        if _needs_rehash(sub_row['password_hash']):
            cursor.execute('UPDATE sub_admin_accounts SET password_hash = ? WHERE id = ?', (hash_password(password), sub_row['id']))
        cursor.execute('UPDATE sub_admin_accounts SET last_login_at = ? WHERE id = ?', (datetime.now(timezone.utc).isoformat(), sub_row['id']))
        conn.commit()
        enabled_features = json.loads(sub_row['enabled_features'] or '[]')
        is_haven_sub_admin = sub_row['parent_partner_id'] is None
        discord_tag = None if is_haven_sub_admin else sub_row['parent_discord_tag']
        parent_display_name = 'Haven' if is_haven_sub_admin else sub_row['parent_display_name']
        sub_row_dict = dict(sub_row)
        additional_discord_tags = json.loads(sub_row_dict.get('additional_discord_tags') or '[]') if is_haven_sub_admin else []
        can_approve_personal_uploads = bool(sub_row_dict.get('can_approve_personal_uploads', 0)) if is_haven_sub_admin else False
        session_token = generate_session_token()
        create_session(session_token, {
            'user_type': 'sub_admin', 'username': username, 'discord_tag': discord_tag,
            'sub_admin_id': sub_row['id'], 'partner_id': sub_row['parent_partner_id'],
            'display_name': sub_row['display_name'] or username, 'parent_display_name': parent_display_name,
            'enabled_features': enabled_features, 'is_haven_sub_admin': is_haven_sub_admin,
            'additional_discord_tags': additional_discord_tags,
            'can_approve_personal_uploads': can_approve_personal_uploads,
            'tier': TIER_SUB_ADMIN,
        })
        response.set_cookie(key='session', value=session_token, httponly=True, max_age=600, samesite='lax')
        return {
            'status': 'ok', 'logged_in': True, 'user_type': 'sub_admin', 'username': username,
            'discord_tag': discord_tag, 'display_name': sub_row['display_name'] or username,
            'parent_display_name': parent_display_name, 'enabled_features': enabled_features,
            'is_haven_sub_admin': is_haven_sub_admin, 'account_id': sub_row['id']
        }
    finally:
        if conn:
            conn.close()


# ============================================================================
# Logout
# ============================================================================

@router.post('/api/admin/logout')
async def admin_logout(response: Response, session: Optional[str] = Cookie(None)):
    """Logout - clears session"""
    if session:
        destroy_session(session)
    response.delete_cookie('session')
    return {'status': 'ok'}


# ============================================================================
# Change Password
# ============================================================================

@router.post('/api/change_password')
async def change_password(payload: dict, session: Optional[str] = Cookie(None)):
    """
    Change password for the currently logged-in user.
    Uses user_profiles table as primary, with legacy fallback.
    """
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail='Not authenticated')

    current_password = payload.get('current_password', '')
    new_password = payload.get('new_password', '')

    if not current_password:
        raise HTTPException(status_code=400, detail='Current password is required')

    if not new_password or len(new_password) < 4:
        raise HTTPException(status_code=400, detail='New password must be at least 4 characters')

    profile_id = session_data.get('profile_id')

    # Primary: use profiles table
    if profile_id:
        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT password_hash FROM user_profiles WHERE id = ?', (profile_id,))
            row = cursor.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail='Profile not found')
            if not row['password_hash']:
                raise HTTPException(status_code=400, detail='No password set. Use set-password endpoint instead.')
            if not verify_password(current_password, row['password_hash']):
                raise HTTPException(status_code=401, detail='Current password is incorrect')
            cursor.execute('UPDATE user_profiles SET password_hash = ?, updated_at = ? WHERE id = ?',
                           (hash_password(new_password), datetime.now(timezone.utc).isoformat(), profile_id))
            conn.commit()
            logger.info(f"Profile {profile_id} ({session_data.get('username')}) changed password")
            return {'status': 'ok', 'message': 'Password changed successfully'}
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to change password: {e}")
            raise HTTPException(status_code=500, detail="Failed to change password")
        finally:
            if conn:
                conn.close()

    # Legacy fallback for sessions without profile_id
    user_type = session_data.get('user_type')

    if user_type == 'super_admin':
        if not verify_password(current_password, get_super_admin_password_hash()):
            raise HTTPException(status_code=401, detail='Current password is incorrect')
        if set_super_admin_password_hash(hash_password(new_password)):
            return {'status': 'ok', 'message': 'Password changed successfully'}
        raise HTTPException(status_code=500, detail='Failed to save new password')

    elif user_type == 'partner':
        partner_id = session_data.get('partner_id')
        if not partner_id:
            raise HTTPException(status_code=400, detail='Invalid session')
        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT password_hash FROM partner_accounts WHERE id = ?', (partner_id,))
            row = cursor.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail='Account not found')
            if not verify_password(current_password, row['password_hash']):
                raise HTTPException(status_code=401, detail='Current password is incorrect')
            cursor.execute('UPDATE partner_accounts SET password_hash = ?, updated_at = ? WHERE id = ?',
                           (hash_password(new_password), datetime.now(timezone.utc).isoformat(), partner_id))
            conn.commit()
            return {'status': 'ok', 'message': 'Password changed successfully'}
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to change partner password: {e}")
            raise HTTPException(status_code=500, detail="Failed to change password")
        finally:
            if conn:
                conn.close()

    elif user_type == 'sub_admin':
        sub_admin_id = session_data.get('sub_admin_id')
        if not sub_admin_id:
            raise HTTPException(status_code=400, detail='Invalid session')
        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT password_hash FROM sub_admin_accounts WHERE id = ?', (sub_admin_id,))
            row = cursor.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail='Account not found')
            if not verify_password(current_password, row['password_hash']):
                raise HTTPException(status_code=401, detail='Current password is incorrect')
            cursor.execute('UPDATE sub_admin_accounts SET password_hash = ?, updated_at = ? WHERE id = ?',
                           (hash_password(new_password), datetime.now(timezone.utc).isoformat(), sub_admin_id))
            conn.commit()
            return {'status': 'ok', 'message': 'Password changed successfully'}
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to change sub-admin password: {e}")
            raise HTTPException(status_code=500, detail="Failed to change password")
        finally:
            if conn:
                conn.close()

    else:
        raise HTTPException(status_code=400, detail='Unknown user type')


# ============================================================================
# Change Username
# ============================================================================

@router.post('/api/change_username')
async def change_username(payload: dict, session: Optional[str] = Cookie(None)):
    """
    Change username for the currently logged-in partner.
    Requires current password for verification.
    """
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail='Not authenticated')

    user_type = session_data.get('user_type')

    # Only partners can change their username via this endpoint
    if user_type != 'partner':
        raise HTTPException(status_code=403, detail='Only partner accounts can change username')

    current_password = payload.get('current_password', '')
    new_username = payload.get('new_username', '').strip()

    if not current_password:
        raise HTTPException(status_code=400, detail='Current password is required')

    if not new_username or len(new_username) < 3:
        raise HTTPException(status_code=400, detail='New username must be at least 3 characters')

    if len(new_username) > 50:
        raise HTTPException(status_code=400, detail='Username must be 50 characters or less')

    # Basic username validation - alphanumeric, underscores, hyphens
    if not re.match(r'^[a-zA-Z0-9_-]+$', new_username):
        raise HTTPException(status_code=400, detail='Username can only contain letters, numbers, underscores, and hyphens')

    partner_id = session_data.get('partner_id')
    if not partner_id:
        raise HTTPException(status_code=400, detail='Invalid session')

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Get current password hash and username
        cursor.execute('SELECT username, password_hash FROM partner_accounts WHERE id = ?', (partner_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail='Account not found')

        current_username = row['username']

        # Check if new username is same as current
        if new_username.lower() == current_username.lower():
            raise HTTPException(status_code=400, detail='New username must be different from current username')

        # Verify current password
        if not verify_password(current_password, row['password_hash']):
            raise HTTPException(status_code=401, detail='Current password is incorrect')

        # Check if new username is already taken
        cursor.execute('SELECT id FROM partner_accounts WHERE LOWER(username) = LOWER(?) AND id != ?', (new_username, partner_id))
        if cursor.fetchone():
            raise HTTPException(status_code=409, detail='Username is already taken')

        # Update username
        cursor.execute(
            'UPDATE partner_accounts SET username = ?, updated_at = ? WHERE id = ?',
            (new_username, datetime.now(timezone.utc).isoformat(), partner_id)
        )
        conn.commit()

        logger.info(f"Partner changed username from '{current_username}' to '{new_username}'")
        return {'status': 'ok', 'message': 'Username changed successfully'}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to change partner username: {e}")
        logger.exception("Failed to change username")
        raise HTTPException(status_code=500, detail="Failed to change username")
    finally:
        if conn:
            conn.close()
