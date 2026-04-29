"""Partner management, sub-admin management, audit, theme, and data restriction endpoints."""

from fastapi import APIRouter, HTTPException, Response, Cookie
from fastapi.responses import JSONResponse
from typing import Optional
from datetime import datetime, timezone
import json
import logging
import re
import csv
import io

from services.auth_service import (
    get_session,
    verify_session,
    is_super_admin,
    require_feature,
    hash_password,
    verify_password,
    _needs_rehash,
    get_effective_discord_tag,
    get_personal_color,
)

from db import (
    get_db_connection,
    add_activity_log,
)

from services.restrictions import (
    get_restrictions_by_discord_tag,
)

from constants import (
    RESTRICTABLE_FIELDS,
)

router = APIRouter()
logger = logging.getLogger('control.room')


# ============================================================================
# Change Username (Partner self-service)
# ============================================================================
# /api/change_username is defined in routes/auth.py (single source of truth)
# ============================================================================

# ============================================================================
# Partner Account Management (Super Admin Only)
# ============================================================================

@router.get('/api/partners')
async def list_partners(session: Optional[str] = Cookie(None)):
    """List all partner accounts (super admin only)"""
    if not is_super_admin(session):
        raise HTTPException(status_code=403, detail='Super admin access required')

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, username, discord_tag, display_name, enabled_features,
                   theme_settings, is_active, created_at, last_login_at, created_by
            FROM partner_accounts ORDER BY created_at DESC
        ''')
        partners = [dict(row) for row in cursor.fetchall()]
        for p in partners:
            p['enabled_features'] = json.loads(p['enabled_features'] or '[]')
            p['theme_settings'] = json.loads(p['theme_settings'] or '{}')
        return {'partners': partners}
    finally:
        if conn:
            conn.close()

@router.post('/api/partners')
async def create_partner(payload: dict, session: Optional[str] = Cookie(None)):
    """Create a new partner account (super admin only)"""
    if not is_super_admin(session):
        raise HTTPException(status_code=403, detail='Super admin access required')

    username = payload.get('username', '').strip()
    password = payload.get('password', '')
    discord_tag = payload.get('discord_tag', '').strip() or None
    display_name = payload.get('display_name', '').strip() or username
    enabled_features = payload.get('enabled_features', [])

    if not username or len(username) < 3:
        raise HTTPException(status_code=400, detail='Username must be at least 3 characters')
    if not password or len(password) < 4:
        raise HTTPException(status_code=400, detail='Password must be at least 4 characters')
    if username.lower() == 'haven':
        raise HTTPException(status_code=400, detail='Username "Haven" is reserved')

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Check for duplicate username
        cursor.execute('SELECT id FROM partner_accounts WHERE username = ?', (username,))
        if cursor.fetchone():
            raise HTTPException(status_code=400, detail='Username already exists')

        # Check for duplicate discord_tag
        if discord_tag:
            cursor.execute('SELECT id FROM partner_accounts WHERE discord_tag = ?', (discord_tag,))
            if cursor.fetchone():
                raise HTTPException(status_code=400, detail='Discord tag already in use')

        cursor.execute('''
            INSERT INTO partner_accounts (username, password_hash, discord_tag, display_name, enabled_features, created_by)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (username, hash_password(password), discord_tag, display_name, json.dumps(enabled_features), 'super_admin'))

        conn.commit()
        return {'status': 'ok', 'partner_id': cursor.lastrowid, 'username': username}
    finally:
        if conn:
            conn.close()

@router.put('/api/partners/{partner_id}')
async def update_partner(partner_id: int, payload: dict, session: Optional[str] = Cookie(None)):
    """Update a partner account (super admin only)"""
    if not is_super_admin(session):
        raise HTTPException(status_code=403, detail='Super admin access required')

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Check partner exists
        cursor.execute('SELECT id FROM partner_accounts WHERE id = ?', (partner_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail='Partner not found')

        updates = []
        params = []

        if 'discord_tag' in payload:
            # Check for duplicate discord_tag
            new_tag = payload['discord_tag'].strip() if payload['discord_tag'] else None
            if new_tag:
                cursor.execute('SELECT id FROM partner_accounts WHERE discord_tag = ? AND id != ?', (new_tag, partner_id))
                if cursor.fetchone():
                    raise HTTPException(status_code=400, detail='Discord tag already in use')
            updates.append('discord_tag = ?')
            params.append(new_tag)
        if 'display_name' in payload:
            updates.append('display_name = ?')
            params.append(payload['display_name'])
        if 'enabled_features' in payload:
            updates.append('enabled_features = ?')
            params.append(json.dumps(payload['enabled_features']))
        if 'is_active' in payload:
            updates.append('is_active = ?')
            params.append(1 if payload['is_active'] else 0)

        if not updates:
            raise HTTPException(status_code=400, detail='No fields to update')

        updates.append('updated_at = ?')
        params.append(datetime.now(timezone.utc).isoformat())
        params.append(partner_id)

        cursor.execute(f'''
            UPDATE partner_accounts SET {', '.join(updates)} WHERE id = ?
        ''', params)

        conn.commit()
        return {'status': 'ok'}
    finally:
        if conn:
            conn.close()

@router.post('/api/partners/{partner_id}/reset_password')
async def reset_partner_password(partner_id: int, payload: dict, session: Optional[str] = Cookie(None)):
    """Reset a partner's password (super admin only)"""
    if not is_super_admin(session):
        raise HTTPException(status_code=403, detail='Super admin access required')

    new_password = payload.get('password', '')
    if not new_password or len(new_password) < 4:
        raise HTTPException(status_code=400, detail='Password must be at least 4 characters')

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Check partner exists
        cursor.execute('SELECT id FROM partner_accounts WHERE id = ?', (partner_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail='Partner not found')

        cursor.execute(
            'UPDATE partner_accounts SET password_hash = ?, updated_at = ? WHERE id = ?',
            (hash_password(new_password), datetime.now(timezone.utc).isoformat(), partner_id)
        )
        conn.commit()
        return {'status': 'ok'}
    finally:
        if conn:
            conn.close()

@router.delete('/api/partners/{partner_id}')
async def deactivate_partner(partner_id: int, session: Optional[str] = Cookie(None)):
    """Deactivate a partner account (super admin only)"""
    if not is_super_admin(session):
        raise HTTPException(status_code=403, detail='Super admin access required')

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Check partner exists
        cursor.execute('SELECT id FROM partner_accounts WHERE id = ?', (partner_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail='Partner not found')

        cursor.execute(
            'UPDATE partner_accounts SET is_active = 0, updated_at = ? WHERE id = ?',
            (datetime.now(timezone.utc).isoformat(), partner_id)
        )
        conn.commit()
        return {'status': 'ok'}
    finally:
        if conn:
            conn.close()

@router.post('/api/partners/{partner_id}/activate')
async def activate_partner(partner_id: int, session: Optional[str] = Cookie(None)):
    """Reactivate a partner account (super admin only)"""
    if not is_super_admin(session):
        raise HTTPException(status_code=403, detail='Super admin access required')

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Check partner exists
        cursor.execute('SELECT id FROM partner_accounts WHERE id = ?', (partner_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail='Partner not found')

        cursor.execute(
            'UPDATE partner_accounts SET is_active = 1, updated_at = ? WHERE id = ?',
            (datetime.now(timezone.utc).isoformat(), partner_id)
        )
        conn.commit()
        return {'status': 'ok'}
    finally:
        if conn:
            conn.close()


# ============================================================================
# Sub-Admin Account Management
# ============================================================================

@router.get('/api/sub_admins')
async def list_sub_admins(
    partner_id: Optional[int] = None,
    show_all: bool = False,
    session: Optional[str] = Cookie(None)
):
    """
    List sub-admins. Super admin sees all (optionally filtered by partner_id).
    Partners see only their own sub-admins.
    If show_all=false and super admin has no partner_id, shows Haven's sub-admins.
    """
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail='Authentication required')

    user_type = session_data.get('user_type')
    is_super = user_type == 'super_admin'

    # Partners and sub-admins can only see sub-admins for their partner
    if not is_super:
        partner_id = session_data.get('partner_id')
        if not partner_id:
            raise HTTPException(status_code=403, detail='Access denied')

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        if partner_id:
            cursor.execute('''
                SELECT sa.*, pa.discord_tag as parent_discord_tag, pa.display_name as parent_display_name
                FROM sub_admin_accounts sa
                JOIN partner_accounts pa ON sa.parent_partner_id = pa.id
                WHERE sa.parent_partner_id = ?
                ORDER BY sa.username
            ''', (partner_id,))
        elif is_super and not show_all:
            # Super admin viewing their own sub-admins (parent_partner_id IS NULL)
            cursor.execute('''
                SELECT sa.*, NULL as parent_discord_tag, 'Haven' as parent_display_name
                FROM sub_admin_accounts sa
                WHERE sa.parent_partner_id IS NULL
                ORDER BY sa.username
            ''')
        else:
            # Super admin sees all (including their own)
            cursor.execute('''
                SELECT sa.*,
                       COALESCE(pa.discord_tag, NULL) as parent_discord_tag,
                       COALESCE(pa.display_name, 'Haven') as parent_display_name
                FROM sub_admin_accounts sa
                LEFT JOIN partner_accounts pa ON sa.parent_partner_id = pa.id
                ORDER BY COALESCE(pa.display_name, 'Haven'), sa.username
            ''')

        sub_admins = []
        for row in cursor.fetchall():
            row_dict = dict(row)
            sub_admins.append({
                'id': row['id'],
                'parent_partner_id': row['parent_partner_id'],
                'username': row['username'],
                'display_name': row['display_name'],
                'enabled_features': json.loads(row['enabled_features'] or '[]'),
                'is_active': bool(row['is_active']),
                'created_at': row['created_at'],
                'last_login_at': row['last_login_at'],
                'created_by': row['created_by'],
                'parent_discord_tag': row['parent_discord_tag'],
                'parent_display_name': row['parent_display_name'],
                'additional_discord_tags': json.loads(row_dict.get('additional_discord_tags') or '[]'),
                'can_approve_personal_uploads': bool(row_dict.get('can_approve_personal_uploads', 0))
            })

        return {'sub_admins': sub_admins}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing sub-admins: {e}")
        logger.exception("Internal server error")
        raise HTTPException(status_code=500, detail="Internal server error")
    finally:
        if conn:
            conn.close()


@router.post('/api/sub_admins')
async def create_sub_admin(payload: dict, session: Optional[str] = Cookie(None)):
    """
    Create a sub-admin account.
    Super admin can create for any partner.
    Partners can create sub-admins under themselves.
    """
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail='Authentication required')

    user_type = session_data.get('user_type')
    is_super = user_type == 'super_admin'
    current_username = session_data.get('username')

    username = payload.get('username', '').strip()
    password = payload.get('password', '')
    display_name = payload.get('display_name', '').strip() or None
    enabled_features = payload.get('enabled_features', [])
    parent_partner_id = payload.get('parent_partner_id')
    additional_discord_tags = payload.get('additional_discord_tags', [])  # Only for Haven sub-admins
    can_approve_personal_uploads = payload.get('can_approve_personal_uploads', False)  # Only for Haven sub-admins

    # Validation
    if not username or len(username) < 3:
        raise HTTPException(status_code=400, detail='Username must be at least 3 characters')
    if not password or len(password) < 4:
        raise HTTPException(status_code=400, detail='Password must be at least 4 characters')

    # Determine parent partner
    # Super admin can create sub-admins for themselves (NULL parent) or for a partner
    # Partners create sub-admins under themselves
    is_haven_sub_admin = False
    if is_super:
        # Super admin can optionally specify parent_partner_id
        # If not specified, creates a "Haven" sub-admin (parent_partner_id = NULL)
        if not parent_partner_id:
            is_haven_sub_admin = True
    else:
        # Partners create sub-admins under themselves
        parent_partner_id = session_data.get('partner_id')
        if not parent_partner_id:
            raise HTTPException(status_code=403, detail='Only partners and super admins can create sub-admins')

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Check partner exists and is active (only if creating under a partner)
        if parent_partner_id:
            cursor.execute('SELECT id, enabled_features FROM partner_accounts WHERE id = ? AND is_active = 1', (parent_partner_id,))
            partner_row = cursor.fetchone()
            if not partner_row:
                raise HTTPException(status_code=404, detail='Parent partner not found or inactive')

            # Validate that sub-admin features are subset of parent's features
            parent_features = json.loads(partner_row['enabled_features'] or '[]')
            if 'all' not in parent_features:
                invalid_features = [f for f in enabled_features if f not in parent_features]
                if invalid_features:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Sub-admin cannot have features not granted to parent: {invalid_features}"
                    )
        # Haven sub-admins can have any features (super admin creates them)

        # Check username uniqueness across all user tables
        cursor.execute('SELECT username FROM partner_accounts WHERE username = ?', (username,))
        if cursor.fetchone():
            raise HTTPException(status_code=400, detail='Username already exists (partner account)')
        cursor.execute('SELECT username FROM sub_admin_accounts WHERE username = ?', (username,))
        if cursor.fetchone():
            raise HTTPException(status_code=400, detail='Username already exists (sub-admin account)')

        # Create sub-admin
        # additional_discord_tags and can_approve_personal_uploads only apply to Haven sub-admins (parent_partner_id is NULL)
        tags_to_store = json.dumps(additional_discord_tags) if is_haven_sub_admin else '[]'
        personal_uploads_perm = 1 if (is_haven_sub_admin and can_approve_personal_uploads) else 0
        cursor.execute('''
            INSERT INTO sub_admin_accounts
            (parent_partner_id, username, password_hash, display_name, enabled_features, created_by, additional_discord_tags, can_approve_personal_uploads)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            parent_partner_id,
            username,
            hash_password(password),
            display_name,
            json.dumps(enabled_features),
            current_username,
            tags_to_store,
            personal_uploads_perm
        ))

        sub_admin_id = cursor.lastrowid
        conn.commit()

        parent_label = f"partner {parent_partner_id}" if parent_partner_id else "Haven (super admin)"
        logger.info(f"Sub-admin created: {username} (ID: {sub_admin_id}) under {parent_label} by {current_username}")

        return {
            'status': 'ok',
            'sub_admin_id': sub_admin_id,
            'username': username
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating sub-admin: {e}")
        logger.exception("Internal server error")
        raise HTTPException(status_code=500, detail="Internal server error")
    finally:
        if conn:
            conn.close()


@router.put('/api/sub_admins/{sub_admin_id}')
async def update_sub_admin(sub_admin_id: int, payload: dict, session: Optional[str] = Cookie(None)):
    """Update a sub-admin account."""
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail='Authentication required')

    user_type = session_data.get('user_type')
    is_super = user_type == 'super_admin'

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Get sub-admin (LEFT JOIN for Haven sub-admins with NULL parent_partner_id)
        cursor.execute('''
            SELECT sa.*, pa.enabled_features as parent_features
            FROM sub_admin_accounts sa
            LEFT JOIN partner_accounts pa ON sa.parent_partner_id = pa.id
            WHERE sa.id = ?
        ''', (sub_admin_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail='Sub-admin not found')

        # Check if this is a Haven sub-admin (no parent partner)
        is_haven_sub_admin = row['parent_partner_id'] is None

        # Permission check: super admin or parent partner can edit
        if not is_super:
            if is_haven_sub_admin:
                raise HTTPException(status_code=403, detail='Only super admin can edit Haven sub-admins')
            if session_data.get('partner_id') != row['parent_partner_id']:
                raise HTTPException(status_code=403, detail='Can only edit your own sub-admins')

        # Build update
        updates = []
        params = []

        if 'display_name' in payload:
            updates.append('display_name = ?')
            params.append(payload['display_name'] or None)

        if 'enabled_features' in payload:
            new_features = payload['enabled_features']
            # Validate features against parent (skip for Haven sub-admins - they can have any features)
            if not is_haven_sub_admin:
                parent_features = json.loads(row['parent_features'] or '[]')
                if 'all' not in parent_features:
                    invalid_features = [f for f in new_features if f not in parent_features]
                    if invalid_features:
                        raise HTTPException(
                            status_code=400,
                            detail=f"Sub-admin cannot have features not granted to parent: {invalid_features}"
                        )
            updates.append('enabled_features = ?')
            params.append(json.dumps(new_features))

        if 'is_active' in payload:
            updates.append('is_active = ?')
            params.append(1 if payload['is_active'] else 0)

        # additional_discord_tags only for Haven sub-admins
        if 'additional_discord_tags' in payload and is_haven_sub_admin:
            updates.append('additional_discord_tags = ?')
            params.append(json.dumps(payload['additional_discord_tags']))

        # can_approve_personal_uploads only for Haven sub-admins
        if 'can_approve_personal_uploads' in payload and is_haven_sub_admin:
            updates.append('can_approve_personal_uploads = ?')
            params.append(1 if payload['can_approve_personal_uploads'] else 0)

        if updates:
            updates.append('updated_at = ?')
            params.append(datetime.now(timezone.utc).isoformat())
            params.append(sub_admin_id)

            cursor.execute(
                f'UPDATE sub_admin_accounts SET {", ".join(updates)} WHERE id = ?',
                params
            )
            conn.commit()

        return {'status': 'ok'}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating sub-admin: {e}")
        logger.exception("Internal server error")
        raise HTTPException(status_code=500, detail="Internal server error")
    finally:
        if conn:
            conn.close()


@router.post('/api/sub_admins/{sub_admin_id}/reset_password')
async def reset_sub_admin_password(sub_admin_id: int, payload: dict, session: Optional[str] = Cookie(None)):
    """Reset a sub-admin's password."""
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail='Authentication required')

    user_type = session_data.get('user_type')
    is_super = user_type == 'super_admin'

    new_password = payload.get('new_password', '')
    if not new_password or len(new_password) < 4:
        raise HTTPException(status_code=400, detail='New password must be at least 4 characters')

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT parent_partner_id FROM sub_admin_accounts WHERE id = ?', (sub_admin_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail='Sub-admin not found')

        # Check if this is a Haven sub-admin (no parent partner)
        is_haven_sub_admin = row['parent_partner_id'] is None

        # Permission check
        if not is_super:
            if is_haven_sub_admin:
                raise HTTPException(status_code=403, detail='Only super admin can reset Haven sub-admin passwords')
            if session_data.get('partner_id') != row['parent_partner_id']:
                raise HTTPException(status_code=403, detail='Can only reset passwords for your own sub-admins')

        cursor.execute(
            'UPDATE sub_admin_accounts SET password_hash = ?, updated_at = ? WHERE id = ?',
            (hash_password(new_password), datetime.now(timezone.utc).isoformat(), sub_admin_id)
        )
        conn.commit()

        return {'status': 'ok'}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resetting sub-admin password: {e}")
        logger.exception("Internal server error")
        raise HTTPException(status_code=500, detail="Internal server error")
    finally:
        if conn:
            conn.close()


@router.delete('/api/sub_admins/{sub_admin_id}')
async def delete_sub_admin(sub_admin_id: int, session: Optional[str] = Cookie(None)):
    """Deactivate a sub-admin account."""
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail='Authentication required')

    user_type = session_data.get('user_type')
    is_super = user_type == 'super_admin'

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT parent_partner_id FROM sub_admin_accounts WHERE id = ?', (sub_admin_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail='Sub-admin not found')

        # Check if this is a Haven sub-admin (no parent partner)
        is_haven_sub_admin = row['parent_partner_id'] is None

        # Permission check
        if not is_super:
            if is_haven_sub_admin:
                raise HTTPException(status_code=403, detail='Only super admin can deactivate Haven sub-admins')
            if session_data.get('partner_id') != row['parent_partner_id']:
                raise HTTPException(status_code=403, detail='Can only deactivate your own sub-admins')

        cursor.execute(
            'UPDATE sub_admin_accounts SET is_active = 0, updated_at = ? WHERE id = ?',
            (datetime.now(timezone.utc).isoformat(), sub_admin_id)
        )
        conn.commit()

        return {'status': 'ok'}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deactivating sub-admin: {e}")
        logger.exception("Internal server error")
        raise HTTPException(status_code=500, detail="Internal server error")
    finally:
        if conn:
            conn.close()


@router.get('/api/available_discord_tags')
async def get_available_discord_tags(session: Optional[str] = Cookie(None)):
    """
    Get list of all available discord tags (from partners).
    Super admin only - used for configuring Haven sub-admin visibility.
    """
    if not is_super_admin(session):
        raise HTTPException(status_code=403, detail='Super admin access required')

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Get all discord tags from partners (including Haven)
        cursor.execute('''
            SELECT DISTINCT discord_tag, display_name
            FROM partner_accounts
            WHERE discord_tag IS NOT NULL AND is_active = 1
            ORDER BY discord_tag
        ''')

        tags = []
        for row in cursor.fetchall():
            tags.append({
                'discord_tag': row['discord_tag'],
                'display_name': row['display_name']
            })

        return {'discord_tags': tags}
    except Exception as e:
        logger.error(f"Error fetching discord tags: {e}")
        logger.exception("Internal server error")
        raise HTTPException(status_code=500, detail="Internal server error")
    finally:
        if conn:
            conn.close()


# ============================================================================
# Approval Audit
# ============================================================================

@router.get('/api/approval_audit')
async def get_approval_audit(
    limit: int = 100,
    offset: int = 0,
    discord_tag: Optional[str] = None,
    approver: Optional[str] = None,
    submitter: Optional[str] = None,
    action: Optional[str] = None,
    submission_type: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    search: Optional[str] = None,
    source: Optional[str] = None,
    session: Optional[str] = Cookie(None)
):
    """
    Get approval audit history (super admin only).
    Returns all approval/rejection actions with full details.

    Enhanced filters:
    - discord_tag: Filter by community
    - approver: Filter by approver username
    - submitter: Filter by submitter username
    - action: Filter by action type (approved, rejected, direct_edit, direct_add, tier_change, permission_change, password_reset)
    - submission_type: Filter by submission type (system, region, discovery, profile)
    - start_date, end_date: Date range filter (ISO format)
    - search: Full-text search across submitter, approver, submission name, and notes
    - source: Filter by submission source (manual, haven_extractor, companion_app)
    """
    if not is_super_admin(session):
        raise HTTPException(status_code=403, detail='Super admin access required')

    # Cap limit to prevent unbounded result loading — front-end paginates at 50/100,
    # anything above 500 is either a bug or a misuse that would OOM the Pi.
    if limit > 500:
        limit = 500
    if limit < 1:
        limit = 100
    if offset < 0:
        offset = 0

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        query = 'SELECT * FROM approval_audit_log WHERE 1=1'
        params = []

        if discord_tag:
            query += ' AND submission_discord_tag = ?'
            params.append(discord_tag)

        if approver:
            query += ' AND approver_username LIKE ?'
            params.append(f'%{approver}%')

        if submitter:
            query += ' AND submitter_username LIKE ?'
            params.append(f'%{submitter}%')

        if action:
            query += ' AND action = ?'
            params.append(action)

        if submission_type:
            query += ' AND submission_type = ?'
            params.append(submission_type)

        if start_date:
            query += ' AND timestamp >= ?'
            params.append(start_date)

        if end_date:
            query += ' AND timestamp <= ?'
            params.append(end_date + 'T23:59:59')

        if search:
            # Search across multiple fields: submitter, approver, submission name, and notes
            query += ''' AND (
                submitter_username LIKE ? OR
                approver_username LIKE ? OR
                submission_name LIKE ? OR
                notes LIKE ?
            )'''
            search_term = f'%{search}%'
            params.extend([search_term, search_term, search_term, search_term])

        if source:
            query += ' AND source = ?'
            params.append(source)

        query += ' ORDER BY timestamp DESC LIMIT ? OFFSET ?'
        params.extend([limit, offset])

        cursor.execute(query, params)
        rows = cursor.fetchall()

        audit_entries = [dict(row) for row in rows]

        # Get total count for pagination with same filters
        count_query = 'SELECT COUNT(*) FROM approval_audit_log WHERE 1=1'
        count_params = []
        if discord_tag:
            count_query += ' AND submission_discord_tag = ?'
            count_params.append(discord_tag)
        if approver:
            count_query += ' AND approver_username LIKE ?'
            count_params.append(f'%{approver}%')
        if submitter:
            count_query += ' AND submitter_username LIKE ?'
            count_params.append(f'%{submitter}%')
        if action:
            count_query += ' AND action = ?'
            count_params.append(action)
        if submission_type:
            count_query += ' AND submission_type = ?'
            count_params.append(submission_type)
        if start_date:
            count_query += ' AND timestamp >= ?'
            count_params.append(start_date)
        if end_date:
            count_query += ' AND timestamp <= ?'
            count_params.append(end_date + 'T23:59:59')
        if search:
            # Search across multiple fields: submitter, approver, submission name, and notes
            count_query += ''' AND (
                submitter_username LIKE ? OR
                approver_username LIKE ? OR
                submission_name LIKE ? OR
                notes LIKE ?
            )'''
            search_term = f'%{search}%'
            count_params.extend([search_term, search_term, search_term, search_term])
        if source:
            count_query += ' AND source = ?'
            count_params.append(source)

        cursor.execute(count_query, count_params)
        total = cursor.fetchone()[0]

        return {
            'entries': audit_entries,
            'total': total,
            'limit': limit,
            'offset': offset
        }
    finally:
        if conn:
            conn.close()


@router.get('/api/approval_audit/export')
async def export_approval_audit(
    format: str = 'csv',
    discord_tag: Optional[str] = None,
    approver: Optional[str] = None,
    submitter: Optional[str] = None,
    action: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    session: Optional[str] = Cookie(None)
):
    """
    Export approval audit data as CSV or JSON (super admin only).
    """
    if not is_super_admin(session):
        raise HTTPException(status_code=403, detail='Super admin access required')

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        query = 'SELECT * FROM approval_audit_log WHERE 1=1'
        params = []

        if discord_tag:
            query += ' AND submission_discord_tag = ?'
            params.append(discord_tag)
        if approver:
            query += ' AND approver_username LIKE ?'
            params.append(f'%{approver}%')
        if submitter:
            query += ' AND submitter_username LIKE ?'
            params.append(f'%{submitter}%')
        if action:
            query += ' AND action = ?'
            params.append(action)
        if start_date:
            query += ' AND timestamp >= ?'
            params.append(start_date)
        if end_date:
            query += ' AND timestamp <= ?'
            params.append(end_date + 'T23:59:59')

        query += ' ORDER BY timestamp DESC'
        cursor.execute(query, params)
        rows = cursor.fetchall()
        data = [dict(row) for row in rows]

        if format == 'json':
            return JSONResponse(content={'data': data, 'count': len(data)})
        else:
            # CSV format
            output = io.StringIO()
            if data:
                writer = csv.DictWriter(output, fieldnames=data[0].keys())
                writer.writeheader()
                writer.writerows(data)
            csv_content = output.getvalue()
            return Response(
                content=csv_content,
                media_type='text/csv',
                headers={'Content-Disposition': 'attachment; filename=approval_audit.csv'}
            )
    finally:
        if conn:
            conn.close()


# ============================================================================
# Pending Edit Requests (for partner edit approval workflow)
# ============================================================================

@router.get('/api/pending_edits')
async def list_pending_edits(session: Optional[str] = Cookie(None)):
    """List pending edit requests (super admin sees all, partners see their own)"""
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail='Authentication required')

    is_super = session_data.get('user_type') == 'super_admin'
    partner_id = session_data.get('partner_id')

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        if is_super:
            cursor.execute('''
                SELECT per.*, s.name as system_name,
                       pa.username as partner_username,
                       pa.display_name as partner_display_name,
                       pa.discord_tag as partner_discord_tag
                FROM pending_edit_requests per
                JOIN systems s ON per.system_id = s.id
                JOIN partner_accounts pa ON per.partner_id = pa.id
                WHERE per.status = 'pending'
                ORDER BY per.submitted_at DESC
            ''')
        else:
            cursor.execute('''
                SELECT per.*, s.name as system_name
                FROM pending_edit_requests per
                JOIN systems s ON per.system_id = s.id
                WHERE per.partner_id = ?
                ORDER BY per.submitted_at DESC
            ''', (partner_id,))

        requests = [dict(row) for row in cursor.fetchall()]
        for r in requests:
            try:
                r['edit_data'] = json.loads(r['edit_data'])
            except:
                pass
        return {'requests': requests}
    finally:
        if conn:
            conn.close()

@router.get('/api/pending_edits/count')
async def pending_edits_count(session: Optional[str] = Cookie(None)):
    """Get count of pending edit requests (for navbar badge)"""
    if not is_super_admin(session):
        return {'count': 0}

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as count FROM pending_edit_requests WHERE status = 'pending'")
        row = cursor.fetchone()
        return {'count': row['count'] if row else 0}
    finally:
        if conn:
            conn.close()

@router.post('/api/pending_edits/{request_id}/approve')
async def approve_edit_request(request_id: int, session: Optional[str] = Cookie(None)):
    """Approve a pending edit request and apply the changes (super admin only)"""
    if not is_super_admin(session):
        raise HTTPException(status_code=403, detail='Super admin access required')

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM pending_edit_requests WHERE id = ?', (request_id,))
        request = cursor.fetchone()
        if not request:
            raise HTTPException(status_code=404, detail='Request not found')
        if request['status'] != 'pending':
            raise HTTPException(status_code=400, detail='Request already processed')

        # Mark as approved
        cursor.execute('''
            UPDATE pending_edit_requests
            SET status = 'approved', reviewed_by = 'super_admin', review_date = ?
            WHERE id = ?
        ''', (datetime.now(timezone.utc).isoformat(), request_id))

        conn.commit()

        # Note: The actual edit application would require calling save_system logic
        # For now, we just mark as approved - super admin can manually apply if needed
        # or we could expand this to actually apply the edit_data

        return {'status': 'ok', 'message': 'Edit request approved'}
    finally:
        if conn:
            conn.close()

@router.post('/api/pending_edits/{request_id}/reject')
async def reject_edit_request(request_id: int, payload: dict = None, session: Optional[str] = Cookie(None)):
    """Reject a pending edit request (super admin only)"""
    if not is_super_admin(session):
        raise HTTPException(status_code=403, detail='Super admin access required')

    review_notes = (payload or {}).get('notes', '')

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM pending_edit_requests WHERE id = ?', (request_id,))
        request = cursor.fetchone()
        if not request:
            raise HTTPException(status_code=404, detail='Request not found')
        if request['status'] != 'pending':
            raise HTTPException(status_code=400, detail='Request already processed')

        cursor.execute('''
            UPDATE pending_edit_requests
            SET status = 'rejected', reviewed_by = 'super_admin', review_date = ?, review_notes = ?
            WHERE id = ?
        ''', (datetime.now(timezone.utc).isoformat(), review_notes, request_id))

        conn.commit()
        return {'status': 'ok', 'message': 'Edit request rejected'}
    finally:
        if conn:
            conn.close()


# ============================================================================
# Partner Theme Settings
# ============================================================================

@router.get('/api/partner/theme')
async def get_partner_theme(session: Optional[str] = Cookie(None)):
    """Get the current partner's theme settings"""
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail='Not authenticated')

    # Super admin doesn't have partner theme (uses global settings)
    if session_data.get('user_type') == 'super_admin':
        return {'theme': {}}

    partner_id = session_data.get('partner_id')
    if not partner_id:
        raise HTTPException(status_code=403, detail='Partner access required')

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT theme_settings FROM partner_accounts WHERE id = ?', (partner_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail='Partner account not found')

        theme = json.loads(row['theme_settings'] or '{}')
        return {'theme': theme}
    finally:
        if conn:
            conn.close()

@router.put('/api/partner/theme')
async def update_partner_theme(payload: dict, session: Optional[str] = Cookie(None)):
    """Update the current partner's theme settings"""
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail='Not authenticated')

    # Super admin doesn't have partner theme
    if session_data.get('user_type') == 'super_admin':
        raise HTTPException(status_code=400, detail='Super admin should use global theme settings')

    partner_id = session_data.get('partner_id')
    if not partner_id:
        raise HTTPException(status_code=403, detail='Partner access required')

    theme = payload.get('theme', {})

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('''
            UPDATE partner_accounts
            SET theme_settings = ?, updated_at = ?
            WHERE id = ?
        ''', (json.dumps(theme), datetime.now(timezone.utc).isoformat(), partner_id))

        conn.commit()
        return {'status': 'ok', 'theme': theme}
    finally:
        if conn:
            conn.close()


@router.put('/api/partner/region_color')
async def update_partner_region_color(payload: dict, session: Optional[str] = Cookie(None)):
    """Update the current partner's region color for the 3D map"""
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail='Not authenticated')

    # Only partners can set region colors (not super admin or sub-admin)
    if session_data.get('user_type') != 'partner':
        raise HTTPException(status_code=403, detail='Only partners can set region colors')

    partner_id = session_data.get('partner_id')
    if not partner_id:
        raise HTTPException(status_code=403, detail='Partner access required')

    color = payload.get('color', '#00C2B3')

    # Validate hex color format
    if not re.match(r'^#[0-9A-Fa-f]{6}$', color):
        raise HTTPException(status_code=400, detail='Invalid color format. Use hex format like #00C2B3')

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('''
            UPDATE partner_accounts
            SET region_color = ?, updated_at = ?
            WHERE id = ?
        ''', (color, datetime.now(timezone.utc).isoformat(), partner_id))

        conn.commit()
        logger.info(f"Partner {session_data.get('username')} updated region color to {color}")
        return {'status': 'ok', 'color': color}
    finally:
        if conn:
            conn.close()


@router.get('/api/partner/region_color')
async def get_partner_region_color(session: Optional[str] = Cookie(None)):
    """Get the current partner's region color"""
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail='Not authenticated')

    # Only partners have region colors
    if session_data.get('user_type') != 'partner':
        return {'color': '#00C2B3'}  # Return default for non-partners

    partner_id = session_data.get('partner_id')
    if not partner_id:
        return {'color': '#00C2B3'}

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT region_color FROM partner_accounts WHERE id = ?', (partner_id,))
        row = cursor.fetchone()

        color = row['region_color'] if row and row['region_color'] else '#00C2B3'
        return {'color': color}
    finally:
        if conn:
            conn.close()


@router.get('/api/discord_tag_colors')
async def get_discord_tag_colors():
    """Get all discord tag colors for the 3D map - PUBLIC endpoint"""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Get all active partners with their discord tags and region colors
        cursor.execute('''
            SELECT discord_tag, display_name, region_color
            FROM partner_accounts
            WHERE is_active = 1 AND discord_tag IS NOT NULL
        ''')

        colors = {}
        for row in cursor.fetchall():
            tag = row['discord_tag']
            color = row['region_color'] if row['region_color'] else '#00C2B3'
            colors[tag] = {
                'color': color,
                'name': row['display_name'] or tag
            }

        # Add default Haven color (super admin's systems)
        colors['Haven'] = {'color': '#00C2B3', 'name': 'Haven'}

        # Add personal submission color from settings
        personal_color = get_personal_color()
        colors['personal'] = {'color': personal_color, 'name': 'Personal'}

        return {'colors': colors}
    finally:
        if conn:
            conn.close()


# ============================================================================
# DATA RESTRICTIONS API ENDPOINTS
# ============================================================================

@router.get('/api/partner/my_systems')
async def get_partner_systems(session: Optional[str] = Cookie(None)):
    """Get all systems owned by the current partner with restriction status.

    Returns systems tagged with the partner's discord_tag, including
    whether each system has restrictions applied.
    """
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail='Not authenticated')

    # Get discord_tag - super admin sees all, partner sees their own
    discord_tag = None
    _is_super_admin = session_data.get('user_type') == 'super_admin'

    if not _is_super_admin:
        discord_tag = session_data.get('discord_tag')
        if not discord_tag:
            raise HTTPException(status_code=403, detail='Partner discord_tag required')

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Get systems with optional restriction data
        if _is_super_admin:
            cursor.execute('''
                SELECT s.id, s.name, s.galaxy, s.discord_tag, s.x, s.y, s.z,
                       s.region_x, s.region_y, s.region_z, s.glyph_code,
                       r.custom_name as region_name,
                       dr.id as restriction_id,
                       dr.is_hidden_from_public,
                       dr.hidden_fields,
                       dr.map_visibility
                FROM systems s
                LEFT JOIN regions r ON s.region_x = r.region_x
                    AND s.region_y = r.region_y AND s.region_z = r.region_z
                LEFT JOIN data_restrictions dr ON s.id = dr.system_id
                ORDER BY s.discord_tag, s.name
            ''')
        else:
            cursor.execute('''
                SELECT s.id, s.name, s.galaxy, s.discord_tag, s.x, s.y, s.z,
                       s.region_x, s.region_y, s.region_z, s.glyph_code,
                       r.custom_name as region_name,
                       dr.id as restriction_id,
                       dr.is_hidden_from_public,
                       dr.hidden_fields,
                       dr.map_visibility
                FROM systems s
                LEFT JOIN regions r ON s.region_x = r.region_x
                    AND s.region_y = r.region_y AND s.region_z = r.region_z
                LEFT JOIN data_restrictions dr ON s.id = dr.system_id
                WHERE s.discord_tag = ?
                ORDER BY s.name
            ''', (discord_tag,))

        rows = cursor.fetchall()
        systems = []
        for row in rows:
            system = {
                'id': row['id'],
                'name': row['name'],
                'galaxy': row['galaxy'],
                'discord_tag': row['discord_tag'],
                'x': row['x'],
                'y': row['y'],
                'z': row['z'],
                'region_x': row['region_x'],
                'region_y': row['region_y'],
                'region_z': row['region_z'],
                'region_name': row['region_name'],
                'glyph_code': row['glyph_code'],
                'has_restriction': row['restriction_id'] is not None,
                'restriction': None
            }
            if row['restriction_id']:
                system['restriction'] = {
                    'id': row['restriction_id'],
                    'is_hidden_from_public': bool(row['is_hidden_from_public']),
                    'hidden_fields': json.loads(row['hidden_fields'] or '[]'),
                    'map_visibility': row['map_visibility'] or 'normal'
                }
            systems.append(system)

        return {'systems': systems, 'total': len(systems)}
    finally:
        if conn:
            conn.close()


@router.get('/api/data_restrictions')
async def get_data_restrictions(session: Optional[str] = Cookie(None)):
    """Get all data restrictions for the current partner's systems.

    Super admin gets all restrictions, partners get their own discord_tag's restrictions.
    """
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail='Not authenticated')

    _is_super_admin = session_data.get('user_type') == 'super_admin'
    discord_tag = session_data.get('discord_tag')

    if not _is_super_admin and not discord_tag:
        raise HTTPException(status_code=403, detail='Partner discord_tag required')

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        if _is_super_admin:
            cursor.execute('''
                SELECT dr.*, s.name as system_name, s.galaxy
                FROM data_restrictions dr
                JOIN systems s ON dr.system_id = s.id
                ORDER BY dr.discord_tag, s.name
            ''')
        else:
            cursor.execute('''
                SELECT dr.*, s.name as system_name, s.galaxy
                FROM data_restrictions dr
                JOIN systems s ON dr.system_id = s.id
                WHERE dr.discord_tag = ?
                ORDER BY s.name
            ''', (discord_tag,))

        rows = cursor.fetchall()
        restrictions = [{
            'id': row['id'],
            'system_id': row['system_id'],
            'system_name': row['system_name'],
            'galaxy': row['galaxy'],
            'discord_tag': row['discord_tag'],
            'is_hidden_from_public': bool(row['is_hidden_from_public']),
            'hidden_fields': json.loads(row['hidden_fields'] or '[]'),
            'map_visibility': row['map_visibility'] or 'normal',
            'created_at': row['created_at'],
            'updated_at': row['updated_at'],
            'created_by': row['created_by']
        } for row in rows]

        return {'restrictions': restrictions, 'total': len(restrictions)}
    finally:
        if conn:
            conn.close()


@router.post('/api/data_restrictions')
async def save_data_restriction(payload: dict, session: Optional[str] = Cookie(None)):
    """Create or update a data restriction for a system.

    Partners can only modify restrictions for systems with their discord_tag.
    Super admin can modify any restriction.
    """
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail='Not authenticated')

    system_id = payload.get('system_id')
    if not system_id:
        raise HTTPException(status_code=400, detail='system_id is required')

    is_hidden = payload.get('is_hidden_from_public', False)
    hidden_fields = payload.get('hidden_fields', [])
    map_visibility = payload.get('map_visibility', 'normal')

    # Validate map_visibility
    if map_visibility not in ['normal', 'point_only', 'hidden']:
        raise HTTPException(status_code=400, detail='Invalid map_visibility value')

    # Validate hidden_fields
    valid_fields = list(RESTRICTABLE_FIELDS.keys())
    for field in hidden_fields:
        if field not in valid_fields:
            raise HTTPException(status_code=400, detail=f'Invalid hidden_field: {field}')

    _is_super_admin = session_data.get('user_type') == 'super_admin'
    partner_discord_tag = session_data.get('discord_tag')
    username = session_data.get('username', 'Unknown')

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Verify system exists and get its discord_tag
        cursor.execute('SELECT id, discord_tag FROM systems WHERE id = ?', (system_id,))
        system = cursor.fetchone()
        if not system:
            raise HTTPException(status_code=404, detail='System not found')

        system_discord_tag = system['discord_tag']

        # Permission check - partner can only modify their own systems
        if not _is_super_admin:
            if system_discord_tag != partner_discord_tag:
                raise HTTPException(status_code=403, detail='You can only modify restrictions for your own systems')

        now = datetime.now(timezone.utc).isoformat()

        # Check if restriction already exists
        cursor.execute('SELECT id FROM data_restrictions WHERE system_id = ?', (system_id,))
        existing = cursor.fetchone()

        if existing:
            # Update existing restriction
            cursor.execute('''
                UPDATE data_restrictions
                SET is_hidden_from_public = ?,
                    hidden_fields = ?,
                    map_visibility = ?,
                    updated_at = ?
                WHERE system_id = ?
            ''', (1 if is_hidden else 0, json.dumps(hidden_fields), map_visibility, now, system_id))
        else:
            # Create new restriction
            cursor.execute('''
                INSERT INTO data_restrictions
                (system_id, discord_tag, is_hidden_from_public, hidden_fields, map_visibility, created_at, updated_at, created_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (system_id, system_discord_tag, 1 if is_hidden else 0,
                  json.dumps(hidden_fields), map_visibility, now, now, username))

        conn.commit()

        # Log activity
        add_activity_log(
            'restriction_updated',
            f'Data restriction {"updated" if existing else "created"} for system ID {system_id}',
            json.dumps({'system_id': system_id, 'is_hidden': is_hidden, 'map_visibility': map_visibility}),
            username
        )

        return {'status': 'ok', 'message': 'Restriction saved'}
    finally:
        if conn:
            conn.close()


@router.post('/api/data_restrictions/bulk')
async def save_bulk_restrictions(payload: dict, session: Optional[str] = Cookie(None)):
    """Apply the same restriction settings to multiple systems.

    Partners can only modify restrictions for systems with their discord_tag.
    Super admin can modify any restriction.
    """
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail='Not authenticated')

    system_ids = payload.get('system_ids', [])
    if not system_ids or not isinstance(system_ids, list):
        raise HTTPException(status_code=400, detail='system_ids array is required')

    is_hidden = payload.get('is_hidden_from_public', False)
    hidden_fields = payload.get('hidden_fields', [])
    map_visibility = payload.get('map_visibility', 'normal')

    # Validate map_visibility
    if map_visibility not in ['normal', 'point_only', 'hidden']:
        raise HTTPException(status_code=400, detail='Invalid map_visibility value')

    # Validate hidden_fields
    valid_fields = list(RESTRICTABLE_FIELDS.keys())
    for field in hidden_fields:
        if field not in valid_fields:
            raise HTTPException(status_code=400, detail=f'Invalid hidden_field: {field}')

    _is_super_admin = session_data.get('user_type') == 'super_admin'
    partner_discord_tag = session_data.get('discord_tag')
    username = session_data.get('username', 'Unknown')

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        updated = 0
        created = 0
        skipped = 0
        now = datetime.now(timezone.utc).isoformat()

        for system_id in system_ids:
            # Verify system exists and get its discord_tag
            cursor.execute('SELECT id, discord_tag FROM systems WHERE id = ?', (system_id,))
            system = cursor.fetchone()
            if not system:
                skipped += 1
                continue

            system_discord_tag = system['discord_tag']

            # Permission check - partner can only modify their own systems
            if not _is_super_admin and system_discord_tag != partner_discord_tag:
                skipped += 1
                continue

            # Check if restriction already exists
            cursor.execute('SELECT id FROM data_restrictions WHERE system_id = ?', (system_id,))
            existing = cursor.fetchone()

            if existing:
                cursor.execute('''
                    UPDATE data_restrictions
                    SET is_hidden_from_public = ?,
                        hidden_fields = ?,
                        map_visibility = ?,
                        updated_at = ?
                    WHERE system_id = ?
                ''', (1 if is_hidden else 0, json.dumps(hidden_fields), map_visibility, now, system_id))
                updated += 1
            else:
                cursor.execute('''
                    INSERT INTO data_restrictions
                    (system_id, discord_tag, is_hidden_from_public, hidden_fields, map_visibility, created_at, updated_at, created_by)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (system_id, system_discord_tag, 1 if is_hidden else 0,
                      json.dumps(hidden_fields), map_visibility, now, now, username))
                created += 1

        conn.commit()

        # Log activity
        add_activity_log(
            'restriction_bulk_update',
            f'Bulk restriction update: {created} created, {updated} updated, {skipped} skipped',
            json.dumps({'system_ids': system_ids, 'is_hidden': is_hidden, 'map_visibility': map_visibility}),
            username
        )

        return {'status': 'ok', 'created': created, 'updated': updated, 'skipped': skipped}
    finally:
        if conn:
            conn.close()


@router.delete('/api/data_restrictions/{system_id}')
async def delete_data_restriction(system_id: int, session: Optional[str] = Cookie(None)):
    """Remove a data restriction from a system (returns to public visibility).

    Partners can only remove restrictions for systems with their discord_tag.
    Super admin can remove any restriction.
    """
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail='Not authenticated')

    _is_super_admin = session_data.get('user_type') == 'super_admin'
    partner_discord_tag = session_data.get('discord_tag')
    username = session_data.get('username', 'Unknown')

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Get the restriction and verify ownership
        cursor.execute('''
            SELECT dr.id, dr.discord_tag, s.name as system_name
            FROM data_restrictions dr
            JOIN systems s ON dr.system_id = s.id
            WHERE dr.system_id = ?
        ''', (system_id,))
        restriction = cursor.fetchone()

        if not restriction:
            raise HTTPException(status_code=404, detail='Restriction not found')

        # Permission check
        if not _is_super_admin and restriction['discord_tag'] != partner_discord_tag:
            raise HTTPException(status_code=403, detail='You can only remove restrictions for your own systems')

        cursor.execute('DELETE FROM data_restrictions WHERE system_id = ?', (system_id,))
        conn.commit()

        # Log activity
        add_activity_log(
            'restriction_removed',
            f'Data restriction removed from system: {restriction["system_name"]}',
            json.dumps({'system_id': system_id}),
            username
        )

        return {'status': 'ok', 'message': 'Restriction removed'}
    finally:
        if conn:
            conn.close()


@router.post('/api/data_restrictions/bulk_remove')
async def bulk_remove_restrictions(payload: dict, session: Optional[str] = Cookie(None)):
    """Remove restrictions from multiple systems at once.

    Partners can only remove restrictions for systems with their discord_tag.
    Super admin can remove any restriction.
    """
    session_data = get_session(session)
    if not session_data:
        raise HTTPException(status_code=401, detail='Not authenticated')

    system_ids = payload.get('system_ids', [])
    if not system_ids or not isinstance(system_ids, list):
        raise HTTPException(status_code=400, detail='system_ids array is required')

    _is_super_admin = session_data.get('user_type') == 'super_admin'
    partner_discord_tag = session_data.get('discord_tag')
    username = session_data.get('username', 'Unknown')

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        removed = 0
        skipped = 0

        for system_id in system_ids:
            # Get the restriction and verify ownership
            cursor.execute('SELECT id, discord_tag FROM data_restrictions WHERE system_id = ?', (system_id,))
            restriction = cursor.fetchone()

            if not restriction:
                skipped += 1
                continue

            # Permission check
            if not _is_super_admin and restriction['discord_tag'] != partner_discord_tag:
                skipped += 1
                continue

            cursor.execute('DELETE FROM data_restrictions WHERE system_id = ?', (system_id,))
            removed += 1

        conn.commit()

        # Log activity
        add_activity_log(
            'restriction_bulk_remove',
            f'Bulk restriction removal: {removed} removed, {skipped} skipped',
            json.dumps({'system_ids': system_ids}),
            username
        )

        return {'status': 'ok', 'removed': removed, 'skipped': skipped}
    finally:
        if conn:
            conn.close()
