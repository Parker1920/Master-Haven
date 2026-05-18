"""
Civilizations — encyclopedia entries.

Read endpoints (Phase 2):
  GET /api/v1/civilizations                  paginated list (summary cards)
  GET /api/v1/civilizations/{slug}           single civ (detail)
  GET /api/v1/civilizations/{slug}/coverage  stories + inquisitions tagged with this civ

Write endpoints come in Phase 4.

Field shapes mirror the v0.9 mockup's CIVS objects so Phase 5 can
render civ cards / civ pages without any client-side reshaping.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import text
from sqlalchemy.orm import Session

import json

from ..audit import log_audit
from ..deps import get_db, require_admin, require_historian_or_higher
from ..models.schemas import (
    Author,
    CivStats,
    CivilizationDetail,
    CivilizationPatch,
    CivilizationSummary,
    CivilizationWrite,
    CoverageItem,
    Envelope,
    Meta,
    RevisionEntry,
)
from ..revisions import record_revision

router = APIRouter(prefix="/api/v1/civilizations", tags=["civilizations"])


# ---------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------
def _row_to_summary(row, stats: CivStats) -> CivilizationSummary:
    """Build a CivilizationSummary from a SELECT * row."""
    return CivilizationSummary(
        slug=row.slug,
        name=row.name,
        status=row.status,
        galaxy=row.galaxy,
        founded=row.founded,
        ended=row.ended,
        tagline=row.tagline,
        color_primary=row.color_primary,
        color_secondary=row.color_secondary,
        stats=stats,
    )


def _compute_stats(db: Session, civ_slug: str, founded_year: int | None, ended_year: int | None) -> CivStats:
    """
    Compute live counts for a civ's stat strip.

    `entries` = stories tagged with this civ + inquisitions tagged with this civ
    `inquisitions` = inquisitions tagged with this civ
    `people` = archive_user rows whose primary civ_slug matches
    `years` = founded → ended (or current year, 2026) span
    """
    story_count = db.execute(
        text("SELECT COUNT(*) FROM story_civilization WHERE civ_slug = :s"),
        {"s": civ_slug},
    ).scalar() or 0
    inq_count = db.execute(
        text("SELECT COUNT(*) FROM inquisition_civilization WHERE civ_slug = :s"),
        {"s": civ_slug},
    ).scalar() or 0
    people_count = db.execute(
        text(
            "SELECT COUNT(*) FROM archive_user "
            "WHERE civ_slug = :s AND deleted_at IS NULL"
        ),
        {"s": civ_slug},
    ).scalar() or 0
    # Years active. If still active, use current archive year (2026).
    years = 0
    if founded_year is not None:
        end = ended_year if ended_year else 2026
        years = max(0, end - founded_year)
    return CivStats(
        entries=story_count + inq_count,
        inquisitions=inq_count,
        people=people_count,
        years=years,
    )


# ---------------------------------------------------------------------
# GET /api/v1/civilizations
# ---------------------------------------------------------------------
@router.get("", response_model=Envelope[list[CivilizationSummary]])
def list_civilizations(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    status: str | None = Query(None, regex="^(active|dormant|archived)$"),
):
    """Paginated list of civilizations. Optional status filter."""
    where = "WHERE deleted_at IS NULL"
    params: dict = {"limit": page_size, "offset": (page - 1) * page_size}
    if status:
        where += " AND status = :status"
        params["status"] = status

    total = db.execute(
        text(f"SELECT COUNT(*) FROM civilization {where}"), params
    ).scalar() or 0

    rows = db.execute(
        text(
            f"SELECT slug, name, status, galaxy, founded, founded_year, "
            f"ended, ended_year, tagline, color_primary, color_secondary "
            f"FROM civilization {where} "
            f"ORDER BY founded_year DESC, name ASC "
            f"LIMIT :limit OFFSET :offset"
        ),
        params,
    ).fetchall()

    summaries = [
        _row_to_summary(r, _compute_stats(db, r.slug, r.founded_year, r.ended_year))
        for r in rows
    ]
    return Envelope(
        data=summaries,
        meta=Meta(page=page, page_size=page_size, total=total),
    )


# ---------------------------------------------------------------------
# GET /api/v1/civilizations/{slug}
# ---------------------------------------------------------------------
@router.get("/{slug}", response_model=Envelope[CivilizationDetail])
def get_civilization(slug: str, db: Session = Depends(get_db)):
    row = db.execute(
        text(
            "SELECT slug, name, status, galaxy, founded, founded_year, "
            "ended, ended_year, tagline, description, "
            "color_primary, color_secondary "
            "FROM civilization "
            "WHERE slug = :s AND deleted_at IS NULL"
        ),
        {"s": slug},
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="civilization not found")
    stats = _compute_stats(db, row.slug, row.founded_year, row.ended_year)
    detail = CivilizationDetail(
        slug=row.slug,
        name=row.name,
        status=row.status,
        galaxy=row.galaxy,
        founded=row.founded,
        founded_year=row.founded_year,
        ended=row.ended,
        ended_year=row.ended_year,
        tagline=row.tagline,
        description=row.description,
        color_primary=row.color_primary,
        color_secondary=row.color_secondary,
        stats=stats,
    )
    return Envelope(data=detail)


# ---------------------------------------------------------------------
# GET /api/v1/civilizations/{slug}/coverage
# ---------------------------------------------------------------------
@router.get("/{slug}/coverage", response_model=Envelope[list[CoverageItem]])
def civilization_coverage(
    slug: str,
    db: Session = Depends(get_db),
    limit: int = Query(50, ge=1, le=200),
):
    """
    All coverage tagged with this civ, sorted newest first.

    Returns a mixed list of stories and inquisitions. The 'kind' field
    tells the frontend which page to route to on click.
    """
    # Verify civ exists (so we don't return [] for a typo'd slug)
    exists = db.execute(
        text("SELECT 1 FROM civilization WHERE slug = :s AND deleted_at IS NULL"),
        {"s": slug},
    ).first()
    if not exists:
        raise HTTPException(status_code=404, detail="civilization not found")

    items: list[CoverageItem] = []

    # Stories
    story_rows = db.execute(
        text(
            "SELECT s.id, s.slug, s.doctype, s.headline, s.deck, s.beat, "
            "s.published_at, s.author_id, "
            "u.discord_username AS author_slug, u.display_name AS author_name, "
            "u.avatar_letter, u.avatar_color, u.base_role "
            "FROM story s "
            "JOIN story_civilization sc ON sc.story_id = s.id "
            "LEFT JOIN archive_user u ON u.id = s.author_id "
            "WHERE sc.civ_slug = :s AND s.deleted_at IS NULL "
            "ORDER BY s.published_at DESC LIMIT :lim"
        ),
        {"s": slug, "lim": limit},
    ).fetchall()
    for r in story_rows:
        items.append(CoverageItem(
            kind="story",
            id=r.id,
            slug=r.slug,
            doctype=r.doctype,
            headline=r.headline,
            deck=r.deck,
            beat=r.beat,
            published_at=r.published_at,
            author=Author(
                id=r.author_id,
                slug=r.author_slug,
                name=r.author_name,
                avatar_letter=r.avatar_letter,
                avatar_color=r.avatar_color,
                role=r.base_role,
            ) if r.author_id else None,
        ))

    # Inquisitions
    inq_rows = db.execute(
        text(
            "SELECT i.id, i.slug, i.numeral, i.title, i.subtitle, i.deck, "
            "i.state, i.started_at, i.lead_author_id, "
            "u.discord_username AS author_slug, u.display_name AS author_name, "
            "u.avatar_letter, u.avatar_color, u.base_role "
            "FROM inquisition i "
            "JOIN inquisition_civilization ic ON ic.inquisition_id = i.id "
            "LEFT JOIN archive_user u ON u.id = i.lead_author_id "
            "WHERE ic.civ_slug = :s AND i.deleted_at IS NULL "
            "ORDER BY i.started_at DESC LIMIT :lim"
        ),
        {"s": slug, "lim": limit},
    ).fetchall()
    for r in inq_rows:
        items.append(CoverageItem(
            kind="inquisition",
            id=r.id,
            slug=r.slug,
            doctype="inquisition",
            headline=f"Inquisition {r.numeral}: {r.title}",
            deck=r.deck or r.subtitle,
            numeral=r.numeral,
            state=r.state,
            started_at=r.started_at,
            author=Author(
                id=r.lead_author_id,
                slug=r.author_slug,
                name=r.author_name,
                avatar_letter=r.avatar_letter,
                avatar_color=r.avatar_color,
                role=r.base_role,
            ) if r.lead_author_id else None,
        ))

    # Sort all items newest-first (use whichever date column populates)
    def _sort_key(c: CoverageItem) -> str:
        return c.published_at or c.started_at or ""
    items.sort(key=_sort_key, reverse=True)
    items = items[:limit]

    return Envelope(
        data=items,
        meta=Meta(total=len(items), extra={"civ": slug}),
    )


# ---------------------------------------------------------------------
# Phase 4 writes — historian+ only
# ---------------------------------------------------------------------

def _civ_row_snapshot(row) -> dict:
    """Convert a civilization SELECT * row into a JSON-able dict."""
    return {
        "id": row.id,
        "slug": row.slug,
        "name": row.name,
        "status": row.status,
        "galaxy": row.galaxy,
        "founded": row.founded,
        "founded_year": row.founded_year,
        "ended": row.ended,
        "ended_year": row.ended_year,
        "tagline": row.tagline,
        "description": row.description,
        "color_primary": row.color_primary,
        "color_secondary": row.color_secondary,
    }


@router.post("", response_model=Envelope[CivilizationDetail], status_code=201)
def create_civilization(
    body: CivilizationWrite,
    db: Session = Depends(get_db),
    user: dict = Depends(require_historian_or_higher),
):
    """Create a new civilization. Historian or admin only."""
    existing = db.execute(
        text("SELECT 1 FROM civilization WHERE slug = :s"), {"s": body.slug}
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"slug '{body.slug}' already exists")
    result = db.execute(
        text(
            "INSERT INTO civilization (slug, name, status, galaxy, founded, "
            "founded_year, ended, ended_year, tagline, description, "
            "color_primary, color_secondary, created_by) "
            "VALUES (:slug, :name, :status, :galaxy, :founded, :founded_year, "
            ":ended, :ended_year, :tagline, :description, "
            ":color_primary, :color_secondary, :created_by)"
        ),
        {**body.model_dump(), "created_by": user["id"]},
    )
    civ_id = result.lastrowid
    new_row = db.execute(
        text(
            "SELECT id, slug, name, status, galaxy, founded, founded_year, "
            "ended, ended_year, tagline, description, "
            "color_primary, color_secondary FROM civilization WHERE id = :id"
        ),
        {"id": civ_id},
    ).first()
    snapshot = _civ_row_snapshot(new_row)
    record_revision(db, "civilization", civ_id, user["id"],
                    "created", snapshot)
    log_audit(db, user["id"], "civilization.create", "civilization", civ_id,
              metadata={"slug": body.slug})
    db.commit()

    stats = _compute_stats(db, body.slug, body.founded_year, body.ended_year)
    return Envelope(data=CivilizationDetail(
        slug=new_row.slug,
        name=new_row.name,
        status=new_row.status,
        galaxy=new_row.galaxy,
        founded=new_row.founded,
        founded_year=new_row.founded_year,
        ended=new_row.ended,
        ended_year=new_row.ended_year,
        tagline=new_row.tagline,
        description=new_row.description,
        color_primary=new_row.color_primary,
        color_secondary=new_row.color_secondary,
        stats=stats,
    ))


@router.patch("/{slug}", response_model=Envelope[CivilizationDetail])
def patch_civilization(
    slug: str,
    patch: CivilizationPatch,
    db: Session = Depends(get_db),
    user: dict = Depends(require_historian_or_higher),
):
    """Update a civilization. Historian or admin only. Records a revision."""
    row = db.execute(
        text("SELECT id FROM civilization WHERE slug = :s AND deleted_at IS NULL"),
        {"s": slug},
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="civilization not found")
    fields = {k: v for k, v in patch.model_dump(exclude_unset=True).items() if v is not None}
    if fields:
        sets = ", ".join(f"{k} = :{k}" for k in fields)
        fields["id"] = row.id
        db.execute(
            text(
                f"UPDATE civilization SET {sets}, updated_at = CURRENT_TIMESTAMP "
                f"WHERE id = :id"
            ),
            fields,
        )
    new_row = db.execute(
        text(
            "SELECT id, slug, name, status, galaxy, founded, founded_year, "
            "ended, ended_year, tagline, description, "
            "color_primary, color_secondary FROM civilization WHERE id = :id"
        ),
        {"id": row.id},
    ).first()
    snapshot = _civ_row_snapshot(new_row)
    record_revision(db, "civilization", row.id, user["id"],
                    f"patched {', '.join(fields.keys()) if len(fields) > 1 else 'fields'}"
                    if fields else "no-op patch", snapshot)
    log_audit(db, user["id"], "civilization.patch", "civilization", row.id,
              metadata={"slug": slug, "fields_changed": list(fields.keys())})
    db.commit()

    stats = _compute_stats(db, new_row.slug, new_row.founded_year, new_row.ended_year)
    return Envelope(data=CivilizationDetail(
        slug=new_row.slug, name=new_row.name, status=new_row.status,
        galaxy=new_row.galaxy, founded=new_row.founded,
        founded_year=new_row.founded_year, ended=new_row.ended,
        ended_year=new_row.ended_year, tagline=new_row.tagline,
        description=new_row.description, color_primary=new_row.color_primary,
        color_secondary=new_row.color_secondary, stats=stats,
    ))


@router.delete("/{slug}", status_code=204)
def delete_civilization(
    slug: str,
    db: Session = Depends(get_db),
    user: dict = Depends(require_admin),
):
    """Soft-delete a civilization. Admin only."""
    row = db.execute(
        text("SELECT id FROM civilization WHERE slug = :s AND deleted_at IS NULL"),
        {"s": slug},
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="civilization not found")
    db.execute(
        text("UPDATE civilization SET deleted_at = CURRENT_TIMESTAMP WHERE id = :id"),
        {"id": row.id},
    )
    record_revision(db, "civilization", row.id, user["id"], "deleted", {"slug": slug})
    log_audit(db, user["id"], "civilization.delete", "civilization", row.id,
              metadata={"slug": slug})
    db.commit()
    return Response(status_code=204)


@router.get("/{slug}/revisions", response_model=Envelope[list[RevisionEntry]])
def list_civ_revisions(slug: str, db: Session = Depends(get_db)):
    """Public read: revision history for a civilization."""
    civ = db.execute(
        text("SELECT id FROM civilization WHERE slug = :s AND deleted_at IS NULL"),
        {"s": slug},
    ).first()
    if not civ:
        raise HTTPException(status_code=404, detail="civilization not found")
    rows = db.execute(
        text(
            "SELECT r.id, r.change_summary, r.snapshot_json, r.created_at, "
            "u.id AS uid, u.discord_username AS uslug, u.display_name AS uname, "
            "u.avatar_letter, u.avatar_color, u.base_role "
            "FROM entity_revision r "
            "LEFT JOIN archive_user u ON u.id = r.changed_by_id "
            "WHERE r.entity_type = 'civilization' AND r.entity_id = :id "
            "ORDER BY r.created_at DESC"
        ),
        {"id": civ.id},
    ).fetchall()
    return Envelope(
        data=[
            RevisionEntry(
                id=r.id,
                changed_by=Author(
                    id=r.uid, slug=r.uslug, name=r.uname,
                    avatar_letter=r.avatar_letter, avatar_color=r.avatar_color,
                    role=r.base_role,
                ) if r.uid else Author(id=0, slug="system", name="system"),
                change_summary=r.change_summary,
                snapshot=json.loads(r.snapshot_json) if r.snapshot_json else {},
                created_at=r.created_at,
            )
            for r in rows
        ],
        meta=Meta(total=len(rows), extra={"slug": slug}),
    )
