"""
Beats — the editorial sections briefs/features get tagged with
(conflicts, diplomacy, events, civupdates, projects, ...).

GET /api/v1/beats                   distinct beats + per-beat counts
GET /api/v1/beats/{slug}/stories    stories filed under that beat

Counts come from published stories (story table); pending drafts are
excluded.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..deps import get_db
from ..models.schemas import (
    Author,
    Envelope,
    Meta,
    StorySummary,
)

router = APIRouter(prefix="/api/v1/beats", tags=["beats"])


@router.get("")
def list_beats(db: Session = Depends(get_db)):
    rows = db.execute(
        text(
            "SELECT beat, COUNT(*) AS count, MAX(published_at) AS last_published "
            "FROM story "
            "WHERE deleted_at IS NULL AND beat IS NOT NULL AND beat != '' "
            "GROUP BY beat "
            "ORDER BY count DESC, beat"
        )
    ).fetchall()
    data = [
        {
            "slug": r.beat,
            "name": r.beat,
            "count": r.count,
            "last_published": r.last_published,
        }
        for r in rows
    ]
    return {"data": data, "meta": {"total": len(data)}}


def _story_civs(db: Session, story_id: int) -> list[str]:
    rows = db.execute(
        text("SELECT civ_slug FROM story_civilization WHERE story_id = :sid"),
        {"sid": story_id},
    ).fetchall()
    return [r.civ_slug for r in rows]


@router.get("/{slug}/stories", response_model=Envelope[list[StorySummary]])
def beat_stories(
    slug: str,
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
):
    # Confirm the beat exists (any story published under it)
    exists = db.execute(
        text("SELECT 1 FROM story WHERE beat = :b AND deleted_at IS NULL LIMIT 1"),
        {"b": slug},
    ).first()
    if not exists:
        raise HTTPException(status_code=404, detail="beat not found")

    params = {"b": slug, "limit": page_size, "offset": (page - 1) * page_size}
    total = db.execute(
        text("SELECT COUNT(*) FROM story WHERE beat = :b AND deleted_at IS NULL"),
        params,
    ).scalar() or 0
    rows = db.execute(
        text(
            "SELECT s.id, s.slug, s.doctype, s.headline, s.deck, "
            "s.beat, s.published_at, s.read_minutes, "
            "s.author_id, u.discord_username AS author_slug, "
            "u.display_name AS author_name, u.avatar_letter, "
            "u.avatar_color, u.base_role "
            "FROM story s "
            "LEFT JOIN archive_user u ON u.id = s.author_id "
            "WHERE s.beat = :b AND s.deleted_at IS NULL "
            "ORDER BY s.published_at DESC "
            "LIMIT :limit OFFSET :offset"
        ),
        params,
    ).fetchall()
    summaries = [
        StorySummary(
            id=r.id,
            slug=r.slug,
            doctype=r.doctype,
            headline=r.headline,
            deck=r.deck,
            beat=r.beat,
            civs=_story_civs(db, r.id),
            author=Author(
                id=r.author_id, slug=r.author_slug, name=r.author_name,
                avatar_letter=r.avatar_letter, avatar_color=r.avatar_color,
                role=r.base_role,
            ),
            published_at=r.published_at,
            read_minutes=r.read_minutes,
        )
        for r in rows
    ]
    return Envelope(
        data=summaries,
        meta=Meta(page=page, page_size=page_size, total=total, extra={"beat": slug}),
    )
