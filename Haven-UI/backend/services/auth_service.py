"""
Authentication, session management, and user identity services.

Contains all auth-related helpers: sessions, passwords, API keys,
profile helpers, and self-approval prevention logic.

The _sessions dict is the in-memory session store shared by all routes.
"""

import hashlib
import json
import logging
import secrets
import unicodedata
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

from fastapi import Cookie, HTTPException

from constants import (
    SESSION_TIMEOUT_MINUTES,
    SUPER_ADMIN_USERNAME,
    DEFAULT_SUPER_ADMIN_PASSWORD_HASH,
    DEFAULT_PERSONAL_COLOR,
    TIER_MEMBER_READONLY,
    normalize_discord_username,
)
from db import get_db_connection

logger = logging.getLogger('control.room')

# ============================================================================
# In-Memory Session Storage
# ============================================================================

# Maps session_token -> session_data dict.
# All sessions lost on server restart (sliding-window TTL).
_sessions: Dict[str, dict] = {}

# Settings cache (theme, personal_color, etc.)
_settings_cache: dict = {}


# ============================================================================
# Password Hashing
# ============================================================================

def hash_password(password: str) -> str:
    """Hash a password using bcrypt with salt."""
    import bcrypt
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12)).decode()


def verify_password(password: str, stored_hash: str) -> bool:
    """Verify password against stored hash. Supports bcrypt and legacy SHA-256."""
    import bcrypt
    if stored_hash.startswith('$2b$') or stored_hash.startswith('$2a$'):
        return bcrypt.checkpw(password.encode(), stored_hash.encode())
    return hashlib.sha256(password.encode()).hexdigest() == stored_hash


def _needs_rehash(stored_hash: str) -> bool:
    """Check if a stored hash needs to be upgraded from SHA-256 to bcrypt."""
    return not (stored_hash.startswith('$2b$') or stored_hash.startswith('$2a$'))


# ============================================================================
# Session Management
# ============================================================================

def generate_session_token() -> str:
    """Generate a secure random session token."""
    return secrets.token_urlsafe(32)


def get_session(session_token: Optional[str]) -> Optional[dict]:
    """Look up session by token. Auto-extends on access (sliding window)."""
    if not session_token or session_token not in _sessions:
        return None
    session = _sessions[session_token]
    if datetime.now(timezone.utc) > session.get('expires_at', datetime.min.replace(tzinfo=timezone.utc)):
        del _sessions[session_token]
        return None
    session['expires_at'] = datetime.now(timezone.utc) + timedelta(minutes=SESSION_TIMEOUT_MINUTES)
    return session


def create_session(token: str, session_data: dict):
    """Store a new session in the in-memory store."""
    session_data['expires_at'] = datetime.now(timezone.utc) + timedelta(minutes=SESSION_TIMEOUT_MINUTES)
    _sessions[token] = session_data


def destroy_session(token: str):
    """Remove a session from the store."""
    _sessions.pop(token, None)


def verify_session(session_token: Optional[str]) -> bool:
    """Returns True if session token maps to a valid, non-expired session."""
    return get_session(session_token) is not None


# ============================================================================
# Feature & Role Checks
# ============================================================================

def require_feature(session_data: dict, feature: str) -> None:
    """Raise 403 if the user doesn't have the required feature. Super admins bypass all checks."""
    if session_data.get('user_type') == 'super_admin':
        return
    enabled = session_data.get('enabled_features', [])
    if feature not in enabled:
        raise HTTPException(status_code=403, detail=f"You don't have the '{feature}' permission")


def is_super_admin(session_token: Optional[str]) -> bool:
    """Returns True if session token belongs to the super admin."""
    session = get_session(session_token)
    return session is not None and session.get('user_type') == 'super_admin'


def is_partner(session_token: Optional[str]) -> bool:
    """Returns True if session token belongs to a partner account."""
    session = get_session(session_token)
    return session is not None and session.get('user_type') == 'partner'


def is_sub_admin(session_token: Optional[str]) -> bool:
    """Returns True if session token belongs to a sub-admin."""
    session = get_session(session_token)
    return session is not None and session.get('user_type') == 'sub_admin'


def get_partner_discord_tag(session_token: Optional[str]) -> Optional[str]:
    """Return discord_tag if session is a partner, else None."""
    session = get_session(session_token)
    if session and session.get('user_type') == 'partner':
        return session.get('discord_tag')
    return None


def can_access_feature(session_token: Optional[str], feature: str) -> bool:
    """Check if user can access a feature. Super admin always passes."""
    session = get_session(session_token)
    if not session:
        return False
    if session.get('user_type') == 'super_admin':
        return True
    enabled = session.get('enabled_features', [])
    if 'all' in enabled:
        return True
    return feature in enabled


def get_effective_discord_tag(session_token: Optional[str]) -> Optional[str]:
    """Return discord_tag for partners or sub-admins. None for super admin."""
    session = get_session(session_token)
    if not session:
        return None
    if session.get('user_type') in ['partner', 'sub_admin']:
        return session.get('discord_tag')
    return None


def get_submitter_identity(session_token: Optional[str]) -> dict:
    """Return identity dict for audit logging and self-approval prevention."""
    session = get_session(session_token)
    if not session:
        return {'type': 'anonymous', 'username': None, 'account_id': None, 'profile_id': None, 'discord_tag': None}

    user_type = session.get('user_type')
    profile_id = session.get('profile_id')
    account_id = profile_id
    if not account_id:
        if user_type == 'partner':
            account_id = session.get('partner_id')
        elif user_type == 'sub_admin':
            account_id = session.get('sub_admin_id')

    return {
        'type': user_type,
        'username': session.get('username'),
        'account_id': account_id,
        'profile_id': profile_id,
        'discord_tag': session.get('discord_tag')
    }


def check_self_submission(submission: dict, session_data: dict) -> bool:
    """
    Check if a submission was made by the current user (self-approval prevention).
    Returns True if it IS a self-submission (should be blocked).
    Super admin and partners are always exempt (returns False).
    """
    current_user_type = session_data.get('user_type')
    if current_user_type in ('super_admin', 'partner'):
        return False

    current_profile_id = session_data.get('profile_id')
    submitter_profile_id = submission.get('submitter_profile_id')
    if current_profile_id and submitter_profile_id:
        return current_profile_id == submitter_profile_id

    submitter_account_id = submission.get('submitter_account_id')
    submitter_account_type = submission.get('submitter_account_type')
    current_account_id = session_data.get('profile_id') or session_data.get('partner_id') or session_data.get('sub_admin_id')
    if submitter_account_id is not None and submitter_account_type:
        if current_user_type == submitter_account_type and current_account_id == submitter_account_id:
            return True

    current_username = session_data.get('username', '')
    normalized_current = normalize_discord_username(current_username)
    if not normalized_current:
        return False

    submitted_by = submission.get('submitted_by') or ''
    personal_discord_username = submission.get('personal_discord_username') or ''

    if submitted_by and normalize_discord_username(submitted_by) == normalized_current:
        return True
    if personal_discord_username and normalize_discord_username(personal_discord_username) == normalized_current:
        return True

    return False


# ============================================================================
# Super Admin Password & Settings
# ============================================================================

def get_super_admin_password_hash() -> str:
    """Get super admin password hash from database, or return default if not set."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM super_admin_settings WHERE key = 'password_hash'")
        row = cursor.fetchone()
        if row:
            return row['value']
    except Exception as e:
        logger.warning(f"Failed to get super admin password from DB: {e}")
    finally:
        if conn:
            conn.close()
    return DEFAULT_SUPER_ADMIN_PASSWORD_HASH


def set_super_admin_password_hash(password_hash: str) -> bool:
    """Store super admin password hash in database."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO super_admin_settings (key, value, updated_at)
            VALUES ('password_hash', ?, ?)
        ''', (password_hash, datetime.now(timezone.utc).isoformat()))
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Failed to set super admin password: {e}")
        return False
    finally:
        if conn:
            conn.close()


def get_personal_color() -> str:
    """Get personal submission color from database, or return default."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM super_admin_settings WHERE key = 'personal_color'")
        row = cursor.fetchone()
        if row:
            return row['value']
    except Exception as e:
        logger.warning(f"Failed to get personal color from DB: {e}")
    finally:
        if conn:
            conn.close()
    return DEFAULT_PERSONAL_COLOR


def set_personal_color(color: str) -> bool:
    """Store personal submission color in database."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO super_admin_settings (key, value, updated_at)
            VALUES ('personal_color', ?, ?)
        ''', (color, datetime.now(timezone.utc).isoformat()))
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Failed to set personal color: {e}")
        return False
    finally:
        if conn:
            conn.close()


# ============================================================================
# API Key Helpers
# ============================================================================

def hash_api_key(key: str) -> str:
    """Hash an API key using SHA256."""
    return hashlib.sha256(key.encode()).hexdigest()


def generate_api_key() -> str:
    """Generate a new API key with 'vh_live_' prefix."""
    random_part = secrets.token_urlsafe(32)
    return f"vh_live_{random_part}"


def verify_api_key(api_key: Optional[str]) -> Optional[dict]:
    """Verify an API key and return key info if valid."""
    if not api_key:
        return None

    key_hash = hash_api_key(api_key)

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, name, permissions, rate_limit, is_active, created_by, discord_tag,
                   key_type, discord_username, profile_id
            FROM api_keys WHERE key_hash = ?
        ''', (key_hash,))
        row = cursor.fetchone()

        if row and row['is_active']:
            cursor.execute(
                'UPDATE api_keys SET last_used_at = ? WHERE id = ?',
                (datetime.now(timezone.utc).isoformat(), row['id'])
            )
            conn.commit()

            return {
                'id': row['id'],
                'name': row['name'],
                'permissions': json.loads(row['permissions'] or '["submit"]'),
                'rate_limit': row['rate_limit'],
                'created_by': row['created_by'],
                'discord_tag': row['discord_tag'],
                'key_type': row['key_type'],
                'discord_username': row['discord_username'],
                'profile_id': row['profile_id']
            }
        return None
    except Exception as e:
        logger.error(f"API key verification failed: {e}")
        return None
    finally:
        if conn:
            conn.close()


# ============================================================================
# Profile Helpers
# ============================================================================

def normalize_username_for_dedup(username: str) -> str:
    """Authoritative normalization for user_profiles.username_normalized."""
    if not username:
        return ''
    normalized = unicodedata.normalize('NFKD', username)
    normalized = ''.join(ch for ch in normalized if not unicodedata.combining(ch))
    normalized = normalized.strip().lower()
    normalized = normalized.replace('#', '').replace(' ', '').replace('_', '').replace('-', '')
    if len(normalized) > 4 and normalized[-4:].isdigit():
        prefix = normalized[:-4]
        if prefix and not prefix[-1].isdigit():
            normalized = prefix
    return normalized


def _levenshtein_distance(s1: str, s2: str) -> int:
    """Classic dynamic programming Levenshtein distance."""
    if len(s1) < len(s2):
        return _levenshtein_distance(s2, s1)
    if len(s2) == 0:
        return len(s1)
    prev_row = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        curr_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = prev_row[j + 1] + 1
            deletions = curr_row[j] + 1
            substitutions = prev_row[j] + (c1 != c2)
            curr_row.append(min(insertions, deletions, substitutions))
        prev_row = curr_row
    return prev_row[-1]


def find_fuzzy_profile_matches(conn, username: str, max_distance: int = 2) -> list:
    """Find profiles within Levenshtein edit distance of the given username."""
    normalized = normalize_username_for_dedup(username)
    if not normalized:
        return []
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, username, display_name, default_civ_tag, username_normalized
        FROM user_profiles WHERE is_active = 1
    """)
    matches = []
    for row in cursor.fetchall():
        dist = _levenshtein_distance(normalized, row['username_normalized'])
        if 0 < dist <= max_distance:
            matches.append({
                'id': row['id'],
                'username': row['username'],
                'display_name': row['display_name'],
                'default_civ_tag': row['default_civ_tag'],
                'distance': dist
            })
    return sorted(matches, key=lambda m: m['distance'])[:5]


def get_or_create_profile(conn, username: str, discord_snowflake_id: str = None,
                          default_civ_tag: str = None, created_by: str = 'auto') -> int:
    """Look up a profile by normalized username. If not found, create a tier-5 profile."""
    normalized = normalize_username_for_dedup(username)
    if not normalized:
        return None
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM user_profiles WHERE username_normalized = ?", (normalized,))
    row = cursor.fetchone()
    if row:
        return row['id']
    now = datetime.now(timezone.utc).isoformat()
    cursor.execute('''
        INSERT INTO user_profiles (
            username, username_normalized, display_name, tier,
            discord_snowflake_id, default_civ_tag, default_reality, default_galaxy,
            created_by, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, NULL, NULL, ?, ?, ?)
    ''', (username, normalized, username, TIER_MEMBER_READONLY,
          discord_snowflake_id, default_civ_tag, created_by, now, now))
    return cursor.lastrowid
