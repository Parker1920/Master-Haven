"""
Poster routes — single PNG endpoint, manual refresh, admin status.

The PNG endpoint is the single share-source for every consumer:
  - <img> tags in the Haven UI (Profile, Systems tab thumbnails)
  - Discord scrapers reading OG meta tags
  - Direct URL pastes
  - Discord bot slash commands

Adding a new poster type does NOT require a new route — it only needs a
registry entry in services/poster_service.py and a React component in
src/posters/.
"""

import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Cookie, HTTPException, Response
from fastapi.responses import FileResponse

from db import get_db_connection
from services.auth_service import get_session
from services.poster_service import (
    REGISTRY,
    cache_stats,
    force_refresh,
    get_or_render,
    get_template,
)

logger = logging.getLogger('control.room')

router = APIRouter()


# ============================================================================
# PNG endpoint — the single share-source
# ============================================================================

@router.get('/api/posters/{poster_type}/{cache_key}.png')
async def get_poster_png(poster_type: str, cache_key: str):
    """Return the rendered PNG for (type, key).

    Cache hit → serve from disk.
    Cache miss / stale → render via Playwright, cache, serve.
    Render failure → fall back to last good cache if any, else 503.

    Public for all types unless the template marks itself non-public.
    Voyager-type templates additionally check user_profiles.poster_public
    and serve a privacy placeholder if the user opted out.
    """
    template = get_template(poster_type)
    if template is None:
        raise HTTPException(status_code=404, detail=f'Unknown poster type: {poster_type}')

    if not template.public:
        raise HTTPException(status_code=403, detail='Poster type is not public')

    # Privacy opt-out for voyager-type templates
    if template.requires_opt_in_check:
        if not _voyager_is_public(cache_key):
            return _privacy_placeholder_response(template)

    try:
        path = await get_or_render(poster_type, cache_key)
    except Exception as e:
        logger.exception(f'Poster render failed for {poster_type}/{cache_key}: {e}')
        raise HTTPException(status_code=503, detail=f'Render failed: {e}')

    if path is None or not path.exists():
        raise HTTPException(status_code=500, detail='Poster file missing after render')

    headers = {
        # Short browser cache so event-driven invalidation propagates within a few minutes.
        # Discord's OG scraper has its own cache (hours-to-days) — we can't influence that.
        'Cache-Control': 'public, max-age=300, must-revalidate',
        'X-Poster-Type': poster_type,
        'X-Poster-Version': str(template.version),
    }
    return FileResponse(str(path), media_type='image/png', headers=headers)


# ============================================================================
# Manual refresh — drop the cache so the next request renders fresh
# ============================================================================

@router.post('/api/posters/{poster_type}/{cache_key}/refresh')
async def refresh_poster(
    poster_type: str,
    cache_key: str,
    session: Optional[str] = Cookie(None),
):
    """Drop the cache for (type, key). Next consumer request re-renders.

    Auth:
      - Super admin can refresh any poster
      - Profile owner can refresh their own voyager card
      - Otherwise 403
    """
    template = get_template(poster_type)
    if template is None:
        raise HTTPException(status_code=404, detail=f'Unknown poster type: {poster_type}')

    session_data = get_session(session) or {}
    user_type = session_data.get('user_type')

    is_super = user_type == 'super_admin'
    is_owner = False
    if template.requires_opt_in_check:
        # Voyager templates: owner is the user whose normalized name matches the cache_key
        session_username = (session_data.get('username') or '').lower()
        is_owner = session_username == cache_key.lower()

    if not (is_super or is_owner):
        raise HTTPException(status_code=403, detail='Not authorized to refresh this poster')

    dropped = force_refresh(poster_type, cache_key)
    return {
        'status': 'ok',
        'dropped_cache': dropped,
        'poster_type': poster_type,
        'cache_key': cache_key,
    }


# ============================================================================
# Admin queue / status
# ============================================================================

@router.get('/api/posters/admin/queue')
async def poster_queue_status(session: Optional[str] = Cookie(None)):
    """Return registry, browser status, and per-type cache counts.

    Super admin only.
    """
    session_data = get_session(session)
    if not session_data or session_data.get('user_type') != 'super_admin':
        raise HTTPException(status_code=403, detail='Super admin only')

    return cache_stats()


# ============================================================================
# Helpers
# ============================================================================

def _voyager_is_public(username_normalized: str) -> bool:
    """Look up user_profiles.poster_public for a voyager cache key.

    Returns True if the user has not opted out (default), or if no profile row
    exists (we don't gate non-registered users since their card may still be
    legitimately viewable from their public contributions).
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT poster_public FROM user_profiles WHERE username_normalized = ? LIMIT 1',
                (username_normalized.lower(),),
            )
            row = cursor.fetchone()
            if row is None:
                return True  # No profile row means no opt-out
            value = row['poster_public']
            return bool(value) if value is not None else True
    except Exception as e:
        logger.warning(f'poster_public lookup failed for {username_normalized}: {e}')
        return True  # Fail open — privacy enforcement isn't worth a 500


def _privacy_placeholder_response(template) -> FileResponse:
    """Serve a stock 'this voyager has chosen privacy' PNG.

    For now we 404 with a useful message rather than ship a placeholder PNG —
    callers (Discord bot, frontend) can render their own friendly fallback.
    A real placeholder PNG can be added in a future pass.
    """
    raise HTTPException(
        status_code=403,
        detail='This voyager has chosen privacy.',
    )
