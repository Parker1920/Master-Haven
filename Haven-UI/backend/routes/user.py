"""
User-scoped endpoints for the Systems Tab v2.0 redesign.

Hosts /api/user/saved_searches/* (CRUD on the user_saved_searches table)
and the /api/user/theme stub.

Auth model:
- Saved searches require tier 4+ (password-set members and above). Tier 5
  read-only members hit 403 with a hint to set a password. This was an
  explicit decision during the v2.0 spec lock — passwordless profiles
  are device-portable but not write-authoritative, and saved searches
  are user-scoped persistent state.
- /api/user/theme is open to any authenticated session; it currently
  returns the canonical :root token snapshot from systems-mockup-v6.html
  so the frontend can do a real boot-time fetch + apply loop. Actual
  per-user theme persistence is a parallel feature track.
"""

import json
import logging
from typing import Optional

from fastapi import APIRouter, Cookie, HTTPException, Request

from constants import TIER_MEMBER
from db import get_db_connection
from services.auth_service import get_session

logger = logging.getLogger('control.room')

router = APIRouter(tags=["user"])

# Per-spec section 3.5: a "capped collection" of saved filter sets.
MAX_SAVED_SEARCHES_PER_USER = 50

# Per-spec section 10: tokens that user theming can override at runtime.
# Returned as the default payload from /api/user/theme until per-user
# theming actually persists. The frontend applies these as inline CSS
# variables on :root on app boot.
DEFAULT_THEME_TOKENS = {
    "app_bg": "#0a0e27",
    "app_card": "#141b3d",
    "app_card_hover": "#1a2247",
    "app_primary": "#00C2B3",
    "app_primary_dim": "rgba(0, 194, 179, 0.15)",
    "app_accent_purple": "#9d4edd",
    "app_accent_amber": "#ffb44c",
    "muted": "rgba(255, 255, 255, 0.65)",
    "border_soft": "rgba(255, 255, 255, 0.08)",
}


def _require_saving_member(session_token: Optional[str]) -> dict:
    """
    Resolve a session and require tier <= TIER_MEMBER (super admin, partner,
    sub-admin, or password-set member). Tier 5 read-only members are rejected
    with a 403 that the frontend can show as "set a password to save searches".

    Returns the session dict on success; raises HTTPException otherwise.
    """
    session = get_session(session_token)
    if not session:
        raise HTTPException(status_code=401, detail="Not authenticated")

    profile_id = session.get('profile_id')
    if not profile_id:
        # Legacy super-admin sessions predate user_profiles; saved searches
        # require a profile row to scope ownership to. Surface a clear error
        # rather than silently writing rows with user_id NULL.
        raise HTTPException(
            status_code=409,
            detail="Saved searches require a user profile. Re-login to bind a profile to your session."
        )

    tier = session.get('tier')
    if tier is None or tier > TIER_MEMBER:
        raise HTTPException(
            status_code=403,
            detail="Set a password on your profile to save searches."
        )

    return session


def _row_to_saved_search(row) -> dict:
    """Marshal a user_saved_searches row to the API response shape."""
    return {
        'id': row['id'],
        'name': row['name'],
        'filters': json.loads(row['filters_json']),
        'created_at': row['created_at'],
        'updated_at': row['updated_at'],
    }


@router.get('/api/user/saved_searches')
async def list_saved_searches(session: Optional[str] = Cookie(None)):
    """List the current user's saved searches, newest first."""
    user = _require_saving_member(session)
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, name, filters_json, created_at, updated_at
            FROM user_saved_searches
            WHERE user_id = ?
            ORDER BY created_at DESC
        """, (user['profile_id'],))
        return [_row_to_saved_search(r) for r in cursor.fetchall()]
    finally:
        conn.close()


@router.post('/api/user/saved_searches')
async def create_saved_search(request: Request, session: Optional[str] = Cookie(None)):
    """
    Create a saved search.

    Body: {name: str, filters: object}
    - name is required, trimmed, capped at 80 chars
    - filters must be a JSON-serializable object; we store the serialized
      form to keep the column stable regardless of frontend filter-shape
      evolution
    """
    user = _require_saving_member(session)
    body = await request.json()

    name = (body.get('name') or '').strip()
    filters = body.get('filters')
    if not name:
        raise HTTPException(status_code=400, detail="Name is required")
    if len(name) > 80:
        raise HTTPException(status_code=400, detail="Name must be 80 characters or fewer")
    if filters is None or not isinstance(filters, (dict, list)):
        raise HTTPException(status_code=400, detail="filters must be a JSON object or array")

    try:
        filters_json = json.dumps(filters)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=f"filters is not JSON-serializable: {exc}")

    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) AS c FROM user_saved_searches WHERE user_id = ?",
            (user['profile_id'],),
        )
        if cursor.fetchone()['c'] >= MAX_SAVED_SEARCHES_PER_USER:
            raise HTTPException(
                status_code=400,
                detail=f"Saved search limit reached ({MAX_SAVED_SEARCHES_PER_USER}). Delete one before saving another."
            )

        cursor.execute("""
            INSERT INTO user_saved_searches (user_id, name, filters_json)
            VALUES (?, ?, ?)
        """, (user['profile_id'], name, filters_json))
        conn.commit()
        new_id = cursor.lastrowid

        cursor.execute("""
            SELECT id, name, filters_json, created_at, updated_at
            FROM user_saved_searches WHERE id = ?
        """, (new_id,))
        return _row_to_saved_search(cursor.fetchone())
    finally:
        conn.close()


@router.patch('/api/user/saved_searches/{search_id}')
async def update_saved_search(
    search_id: int,
    request: Request,
    session: Optional[str] = Cookie(None),
):
    """
    Update a saved search's name and/or filters. Either field is optional;
    rejects with 400 if both are absent. Ownership is verified before write.
    """
    user = _require_saving_member(session)
    body = await request.json()
    has_name = 'name' in body
    has_filters = 'filters' in body
    if not has_name and not has_filters:
        raise HTTPException(status_code=400, detail="Nothing to update — pass name and/or filters")

    new_name = None
    if has_name:
        new_name = (body.get('name') or '').strip()
        if not new_name:
            raise HTTPException(status_code=400, detail="Name cannot be empty")
        if len(new_name) > 80:
            raise HTTPException(status_code=400, detail="Name must be 80 characters or fewer")

    new_filters_json = None
    if has_filters:
        filters = body.get('filters')
        if not isinstance(filters, (dict, list)):
            raise HTTPException(status_code=400, detail="filters must be a JSON object or array")
        try:
            new_filters_json = json.dumps(filters)
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=f"filters is not JSON-serializable: {exc}")

    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT user_id FROM user_saved_searches WHERE id = ?",
            (search_id,),
        )
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Saved search not found")
        if row['user_id'] != user['profile_id']:
            raise HTTPException(status_code=403, detail="Not your saved search")

        sets = []
        params: list = []
        if new_name is not None:
            sets.append("name = ?")
            params.append(new_name)
        if new_filters_json is not None:
            sets.append("filters_json = ?")
            params.append(new_filters_json)
        sets.append("updated_at = CURRENT_TIMESTAMP")
        params.append(search_id)

        cursor.execute(
            f"UPDATE user_saved_searches SET {', '.join(sets)} WHERE id = ?",
            params,
        )
        conn.commit()

        cursor.execute("""
            SELECT id, name, filters_json, created_at, updated_at
            FROM user_saved_searches WHERE id = ?
        """, (search_id,))
        return _row_to_saved_search(cursor.fetchone())
    finally:
        conn.close()


@router.delete('/api/user/saved_searches/{search_id}')
async def delete_saved_search(search_id: int, session: Optional[str] = Cookie(None)):
    """Delete a saved search owned by the current user."""
    user = _require_saving_member(session)
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT user_id FROM user_saved_searches WHERE id = ?",
            (search_id,),
        )
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Saved search not found")
        if row['user_id'] != user['profile_id']:
            raise HTTPException(status_code=403, detail="Not your saved search")

        cursor.execute("DELETE FROM user_saved_searches WHERE id = ?", (search_id,))
        conn.commit()
        return {'status': 'ok', 'id': search_id}
    finally:
        conn.close()


# ============================================================================
# Theme stub
# ============================================================================

@router.get('/api/user/theme')
async def get_user_theme(session: Optional[str] = Cookie(None)):
    """
    Return the user's theme tokens. Currently returns canonical defaults
    matching the :root block in Haven-UI/src/styles/index.css; per-user
    persistence is a parallel feature track. Endpoint exists now so the
    frontend can wire a real boot-time fetch + apply loop and have user
    theming drop in as a backend-only change later.

    Authenticated only — once we add persistence we'll need a profile to
    scope it to, and surfacing 401 here now keeps that contract honest.
    """
    if not get_session(session):
        raise HTTPException(status_code=401, detail="Not authenticated")
    return {
        'tokens': DEFAULT_THEME_TOKENS,
        'is_default': True,
    }
