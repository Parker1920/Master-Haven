"""
Users — directory lookup for the draft co-author picker (and anything
else that needs to autocomplete an archive_user by name).

GET /api/v1/users/search?q=foo   case-insensitive prefix/contains
                                  match on display_name or
                                  discord_username. Available to any
                                  signed-in team member (not just
                                  admins) so the co-author picker on
                                  the draft page can use it.

Returns at most 20 hits, sorted by display_name. Soft-deleted users
are excluded.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..deps import get_db, require_team_role
from ..models.schemas import Envelope, Meta

router = APIRouter(prefix="/api/v1/users", tags=["users"])


@router.get("/search")
def search_users(
    db: Session = Depends(get_db),
    user: dict = Depends(require_team_role),
    q: str = Query("", max_length=80),
    limit: int = Query(20, ge=1, le=50),
):
    """Search archive_user by name or discord username. Team-role gated."""
    q_clean = (q or "").strip()
    if len(q_clean) < 1:
        return Envelope(data=[], meta=Meta(total=0, extra={"q": q_clean}))
    pat = f"%{q_clean.lower()}%"
    rows = db.execute(
        text(
            "SELECT id, discord_username, display_name, avatar_letter, "
            "avatar_color, base_role, civ_slug, beat "
            "FROM archive_user "
            "WHERE deleted_at IS NULL "
            "  AND (LOWER(display_name) LIKE :pat "
            "       OR LOWER(discord_username) LIKE :pat) "
            "ORDER BY "
            "  CASE WHEN LOWER(display_name) = :exact THEN 0 "
            "       WHEN LOWER(display_name) LIKE :prefix THEN 1 "
            "       ELSE 2 END, "
            "  display_name "
            "LIMIT :lim"
        ),
        {"pat": pat, "exact": q_clean.lower(), "prefix": f"{q_clean.lower()}%", "lim": limit},
    ).fetchall()
    data = [
        {
            "id": r.id,
            "slug": r.discord_username,
            "discord_username": r.discord_username,
            "name": r.display_name,
            "display_name": r.display_name,
            "avatar_letter": r.avatar_letter,
            "avatar_color": r.avatar_color,
            "base_role": r.base_role,
            "civ_slug": r.civ_slug,
            "beat": r.beat,
        }
        for r in rows
    ]
    return Envelope(data=data, meta=Meta(total=len(data), extra={"q": q_clean}))
