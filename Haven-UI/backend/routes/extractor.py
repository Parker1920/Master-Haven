"""Extractor registration, API key management, and communities endpoints."""

import json
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Cookie, HTTPException, Request

from db import get_db_connection
from services.auth_service import (
    get_session,
    verify_session,
    generate_api_key,
    hash_api_key,
    get_or_create_profile,
)

logger = logging.getLogger('control.room')

router = APIRouter(tags=["extractor"])


def _normalize_discord_username(username: str) -> str:
    """Normalize Discord username for duplicate detection.
    Strips whitespace, removes #, strips trailing 4-digit discriminator, lowercases.
    """
    normalized = username.strip().replace('#', '')
    # Strip trailing 4-digit discriminator (e.g. "User1234" -> "User")
    if len(normalized) > 4 and normalized[-4:].isdigit():
        prefix = normalized[:-4]
        if prefix and not prefix[-1].isdigit():
            normalized = prefix
    return normalized.lower()


# ============================================================================
# API Key Management Endpoints
# ============================================================================

@router.post('/api/keys')
async def create_api_key(payload: dict, session: Optional[str] = Cookie(None)):
    """
    Create a new API key (admin only).
    Returns the key only once - it cannot be retrieved later.
    """
    if not verify_session(session):
        raise HTTPException(status_code=401, detail="Admin authentication required")

    name = payload.get('name', '').strip()
    if not name:
        raise HTTPException(status_code=400, detail="API key name is required")

    rate_limit = payload.get('rate_limit', 200)
    permissions = payload.get('permissions', ['submit', 'check_duplicate'])
    discord_tag = payload.get('discord_tag', '').strip() or None

    # Generate the key
    api_key = generate_api_key()
    key_hash = hash_api_key(api_key)
    key_prefix = api_key[:16]  # "vh_live_" + first 8 chars of random part

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Check for duplicate name
        cursor.execute('SELECT id FROM api_keys WHERE name = ?', (name,))
        if cursor.fetchone():
            raise HTTPException(status_code=409, detail=f"API key with name '{name}' already exists")

        cursor.execute('''
            INSERT INTO api_keys (key_hash, key_prefix, name, created_at, permissions, rate_limit, created_by, discord_tag)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            key_hash,
            key_prefix,
            name,
            datetime.now(timezone.utc).isoformat(),
            json.dumps(permissions),
            rate_limit,
            'admin',
            discord_tag
        ))

        key_id = cursor.lastrowid
        conn.commit()

        logger.info(f"Created API key: {name} (ID: {key_id}) with discord_tag: {discord_tag}")

        return {
            'id': key_id,
            'name': name,
            'key': api_key,  # Only returned once!
            'key_prefix': key_prefix,
            'rate_limit': rate_limit,
            'permissions': permissions,
            'discord_tag': discord_tag,
            'created_at': datetime.now(timezone.utc).isoformat(),
            'warning': 'Save this key now - it cannot be retrieved later!'
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create API key: {e}")
        logger.exception("Failed to create API key")
        raise HTTPException(status_code=500, detail="Failed to create API key")
    finally:
        if conn:
            conn.close()


@router.get('/api/keys')
async def list_api_keys(session: Optional[str] = Cookie(None)):
    """
    List all API keys (admin only).
    Does not return the actual key values, only metadata.
    """
    if not verify_session(session):
        raise HTTPException(status_code=401, detail="Admin authentication required")

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, key_prefix, name, created_at, last_used_at, permissions, rate_limit, is_active, discord_tag,
                   key_type, discord_username, total_submissions, last_submission_at
            FROM api_keys
            ORDER BY created_at DESC
        ''')
        rows = cursor.fetchall()

        keys = []
        for row in rows:
            keys.append({
                'id': row['id'],
                'key_prefix': row['key_prefix'],
                'name': row['name'],
                'created_at': row['created_at'],
                'last_used_at': row['last_used_at'],
                'permissions': json.loads(row['permissions'] or '[]'),
                'rate_limit': row['rate_limit'],
                'is_active': bool(row['is_active']),
                'discord_tag': row['discord_tag'],
                'key_type': row['key_type'],
                'discord_username': row['discord_username'],
                'total_submissions': row['total_submissions'] or 0,
                'last_submission_at': row['last_submission_at']
            })

        return {'keys': keys}

    except Exception as e:
        logger.error(f"Failed to list API keys: {e}")
        logger.exception("Failed to list API keys")
        raise HTTPException(status_code=500, detail="Failed to list API keys")
    finally:
        if conn:
            conn.close()


@router.delete('/api/keys/{key_id}')
async def revoke_api_key(key_id: int, session: Optional[str] = Cookie(None)):
    """
    Revoke (deactivate) an API key (admin only).
    The key remains in the database for audit purposes but is no longer valid.
    """
    if not verify_session(session):
        raise HTTPException(status_code=401, detail="Admin authentication required")

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT name FROM api_keys WHERE id = ?', (key_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="API key not found")

        cursor.execute('UPDATE api_keys SET is_active = 0 WHERE id = ?', (key_id,))
        conn.commit()

        logger.info(f"Revoked API key: {row['name']} (ID: {key_id})")

        return {'status': 'ok', 'message': f"API key '{row['name']}' has been revoked"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to revoke API key: {e}")
        logger.exception("Failed to revoke API key")
        raise HTTPException(status_code=500, detail="Failed to revoke API key")
    finally:
        if conn:
            conn.close()


@router.put('/api/keys/{key_id}')
async def update_api_key(key_id: int, payload: dict, session: Optional[str] = Cookie(None)):
    """
    Update an API key's settings (admin only).
    Can update: name, rate_limit, permissions, is_active, discord_tag
    """
    if not verify_session(session):
        raise HTTPException(status_code=401, detail="Admin authentication required")

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM api_keys WHERE id = ?', (key_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="API key not found")

        # Update allowed fields
        updates = []
        params = []

        if 'name' in payload:
            updates.append('name = ?')
            params.append(payload['name'])
        if 'rate_limit' in payload:
            updates.append('rate_limit = ?')
            params.append(payload['rate_limit'])
        if 'permissions' in payload:
            updates.append('permissions = ?')
            params.append(json.dumps(payload['permissions']))
        if 'is_active' in payload:
            updates.append('is_active = ?')
            params.append(1 if payload['is_active'] else 0)
        if 'discord_tag' in payload:
            updates.append('discord_tag = ?')
            # Allow setting to None by passing empty string or null
            discord_tag = payload['discord_tag']
            params.append(discord_tag if discord_tag else None)

        if updates:
            params.append(key_id)
            cursor.execute(f"UPDATE api_keys SET {', '.join(updates)} WHERE id = ?", params)
            conn.commit()

        return {'status': 'ok', 'message': 'API key updated'}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update API key: {e}")
        logger.exception("Failed to update API key")
        raise HTTPException(status_code=500, detail="Failed to update API key")
    finally:
        if conn:
            conn.close()


# ============================================================================
# Per-User Extractor Registration & Management
# ============================================================================

@router.post('/api/extractor/register')
async def register_extractor(request: Request):
    """
    Self-service registration for Haven Extractor users.
    Creates a personal API key tied to a Discord username.
    Returns the key ONCE - it cannot be retrieved later.
    No authentication required (public endpoint).
    """
    body = await request.json()
    discord_username = (body.get('discord_username') or '').strip()

    if not discord_username:
        raise HTTPException(status_code=400, detail="Discord username is required")
    if len(discord_username) < 2 or len(discord_username) > 32:
        raise HTTPException(status_code=400, detail="Discord username must be 2-32 characters")

    normalized = _normalize_discord_username(discord_username)

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Check if an extractor key already exists for this normalized username
        cursor.execute("""
            SELECT id, key_prefix, is_active, discord_username
            FROM api_keys
            WHERE key_type = 'extractor' AND LOWER(TRIM(REPLACE(discord_username, '#', ''))) = ?
        """, (normalized,))
        existing = cursor.fetchone()

        if existing:
            if existing['is_active']:
                # Also return profile_id if linked
                profile_id = None
                cursor.execute("SELECT profile_id FROM api_keys WHERE id = ?", (existing['id'],))
                pk_row = cursor.fetchone()
                if pk_row:
                    profile_id = pk_row['profile_id']
                # If no profile linked yet, create one and link it
                if not profile_id:
                    profile_id = get_or_create_profile(conn, discord_username, created_by='extractor_registration')
                    if profile_id:
                        cursor.execute("UPDATE api_keys SET profile_id = ? WHERE id = ?", (profile_id, existing['id']))
                        conn.commit()
                return {
                    'status': 'already_registered',
                    'key_prefix': existing['key_prefix'],
                    'discord_username': existing['discord_username'],
                    'profile_id': profile_id,
                    'message': 'An API key already exists for this username. If you lost your key, contact an admin.'
                }
            else:
                raise HTTPException(
                    status_code=403,
                    detail="Your extractor account has been suspended. Contact an admin for assistance."
                )

        # Create profile for this user (or get existing)
        profile_id = get_or_create_profile(conn, discord_username, created_by='extractor_registration')

        # Generate new personal API key
        api_key = generate_api_key()
        key_hash = hash_api_key(api_key)
        key_prefix = api_key[:16]
        now = datetime.now(timezone.utc).isoformat()

        cursor.execute('''
            INSERT INTO api_keys (key_hash, key_prefix, name, created_at, permissions, rate_limit,
                                  is_active, created_by, discord_tag, key_type, discord_username, profile_id)
            VALUES (?, ?, ?, ?, ?, ?, 1, 'self_registration', NULL, 'extractor', ?, ?)
        ''', (
            key_hash,
            key_prefix,
            f"Extractor - {discord_username}",
            now,
            json.dumps(["submit", "check_duplicate"]),
            100,  # Lower rate limit than shared key (1000) or admin keys (200)
            discord_username,
            profile_id
        ))
        conn.commit()

        key_id = cursor.lastrowid

        # Link profile to API key
        if profile_id:
            cursor.execute("UPDATE user_profiles SET api_key_id = ? WHERE id = ?", (key_id, profile_id))
            conn.commit()

        logger.info(f"Registered extractor key for '{discord_username}' (ID: {key_id}, profile: {profile_id})")

        return {
            'status': 'registered',
            'key': api_key,
            'key_prefix': key_prefix,
            'discord_username': discord_username,
            'profile_id': profile_id,
            'rate_limit': 100,
            'message': 'Save this key now - it cannot be retrieved later!'
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Extractor registration failed: {e}")
        raise HTTPException(status_code=500, detail="Registration failed. Please try again.")
    finally:
        if conn:
            conn.close()


@router.get('/api/communities')
async def list_communities():
    """
    Public endpoint: list available communities for Haven Extractor dropdown.
    Returns partner communities + 'personal' option.
    """
    # Import the discord_tags endpoint from control_room_api at runtime to avoid circular imports
    # This endpoint just wraps the existing list_discord_tags logic
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT discord_tag as tag,
                   COALESCE(display_name, discord_tag) as name
            FROM partner_accounts
            WHERE discord_tag IS NOT NULL AND discord_tag != ''
            ORDER BY display_name
        ''')
        rows = cursor.fetchall()
        tags = [{'tag': row['tag'], 'name': row['name']} for row in rows]

        return {'communities': tags}
    except Exception as e:
        logger.error(f"Failed to list communities: {e}")
        return {'communities': []}
    finally:
        if conn:
            conn.close()


@router.get('/api/extractor/users')
async def list_extractor_users(session: Optional[str] = Cookie(None)):
    """
    List registered extractor users with submission stats.
    Super admin: sees all extractor users.
    Partners: sees users who have submitted to their community (read-only).
    """
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail='Authentication required')

    is_super = session_data.get('user_type') == 'super_admin'
    user_discord_tag = session_data.get('discord_tag')

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        if is_super:
            cursor.execute("""
                SELECT id, key_prefix, name, discord_username, created_at, last_used_at,
                       last_submission_at, rate_limit, is_active, total_submissions
                FROM api_keys
                WHERE key_type = 'extractor'
                ORDER BY last_submission_at DESC NULLS LAST, created_at DESC
            """)
        else:
            # Partner: users who have submitted to their community
            cursor.execute("""
                SELECT DISTINCT ak.id, ak.key_prefix, ak.name, ak.discord_username,
                       ak.created_at, ak.last_used_at, ak.last_submission_at,
                       ak.rate_limit, ak.is_active, ak.total_submissions
                FROM api_keys ak
                INNER JOIN pending_systems ps ON ps.api_key_name = ak.name
                WHERE ak.key_type = 'extractor'
                  AND ps.discord_tag = ?
                ORDER BY ak.last_submission_at DESC NULLS LAST, ak.created_at DESC
            """, (user_discord_tag,))

        rows = cursor.fetchall()
        users = []
        for row in rows:
            # Get per-community submission breakdown
            cursor.execute("""
                SELECT discord_tag, COUNT(*) as count,
                       SUM(CASE WHEN status = 'approved' THEN 1 ELSE 0 END) as approved,
                       SUM(CASE WHEN status = 'rejected' THEN 1 ELSE 0 END) as rejected,
                       SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending
                FROM pending_systems
                WHERE api_key_name = ?
                GROUP BY discord_tag
            """, (row['name'],))
            communities = [
                {
                    'tag': c['discord_tag'] or 'personal',
                    'count': c['count'],
                    'approved': c['approved'],
                    'rejected': c['rejected'],
                    'pending': c['pending']
                }
                for c in cursor.fetchall()
            ]

            users.append({
                'id': row['id'],
                'key_prefix': row['key_prefix'],
                'name': row['name'],
                'discord_username': row['discord_username'],
                'created_at': row['created_at'],
                'last_used_at': row['last_used_at'],
                'last_submission_at': row['last_submission_at'],
                'rate_limit': row['rate_limit'],
                'is_active': bool(row['is_active']),
                'total_submissions': row['total_submissions'] or 0,
                'communities_used': communities
            })

        return {'users': users, 'total': len(users)}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list extractor users: {e}")
        raise HTTPException(status_code=500, detail="Failed to load extractor users")
    finally:
        if conn:
            conn.close()


@router.put('/api/extractor/users/{key_id}')
async def update_extractor_user(key_id: int, request: Request, session: Optional[str] = Cookie(None)):
    """
    Update an extractor user's settings (super admin only).
    Can update: rate_limit, is_active (suspend/reactivate).
    """
    session_data = get_session(session)
    if not session_data or session_data.get('user_type') != 'super_admin':
        raise HTTPException(status_code=403, detail="Super admin access required")

    body = await request.json()

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Verify this is an extractor key
        cursor.execute("SELECT id, name, key_type, discord_username FROM api_keys WHERE id = ?", (key_id,))
        key_row = cursor.fetchone()
        if not key_row:
            raise HTTPException(status_code=404, detail="Extractor user not found")
        if key_row['key_type'] != 'extractor':
            raise HTTPException(status_code=400, detail="This is not an extractor user key")

        updates = []
        params = []

        if 'rate_limit' in body:
            rate_limit = int(body['rate_limit'])
            if rate_limit < 1 or rate_limit > 10000:
                raise HTTPException(status_code=400, detail="Rate limit must be between 1 and 10000")
            updates.append('rate_limit = ?')
            params.append(rate_limit)

        if 'is_active' in body:
            updates.append('is_active = ?')
            params.append(1 if body['is_active'] else 0)

        if not updates:
            raise HTTPException(status_code=400, detail="No valid fields to update")

        params.append(key_id)
        cursor.execute(f"UPDATE api_keys SET {', '.join(updates)} WHERE id = ?", params)
        conn.commit()

        action = 'updated'
        if 'is_active' in body:
            action = 'reactivated' if body['is_active'] else 'suspended'

        logger.info(f"Extractor user '{key_row['discord_username']}' {action} by super admin")

        return {
            'status': 'ok',
            'message': f"Extractor user {action} successfully",
            'discord_username': key_row['discord_username']
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update extractor user: {e}")
        raise HTTPException(status_code=500, detail="Failed to update extractor user")
    finally:
        if conn:
            conn.close()
