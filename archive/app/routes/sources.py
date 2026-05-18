"""
Sources & citations.

Sources are external references (Discord threads, wiki pages,
screenshots, etc.) that back up factual claims on inquisitions and
encyclopedia entities. Each source can be cited by many targets.

  POST   /api/v1/sources                       create (team role+)
  GET    /api/v1/sources                       paginated list
  GET    /api/v1/sources/{id}                  one source
  PATCH  /api/v1/sources/{id}                  edit (creator or admin)
  DELETE /api/v1/sources/{id}                  soft delete (creator or admin)

  POST   /api/v1/sources/citations             attach source to target
  DELETE /api/v1/sources/citations/{id}        detach
  GET    /api/v1/sources/for/{type}/{id}       citations on a target
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..audit import log_audit
from ..deps import get_db, require_login, require_team_role
from ..models.schemas import (
    Envelope,
    Meta,
    SourceCitation,
    SourceCitationCreate,
    SourceDetail,
    SourceWrite,
)

log = logging.getLogger("archive.sources")

router = APIRouter(prefix="/api/v1/sources", tags=["sources"])


def _row_to_source(row) -> SourceDetail:
    return SourceDetail(
        id=row.id,
        title=row.title,
        url=row.url,
        source_type=row.source_type,
        quality=row.quality,
        notes=row.notes,
        archived_url=row.archived_url,
        added_by_id=row.added_by_id,
        added_by_name=getattr(row, "added_by_name", None),
        created_at=row.created_at,
    )


# ---------------------------------------------------------------------
# POST /api/v1/sources
# ---------------------------------------------------------------------
@router.post("", response_model=Envelope[SourceDetail], status_code=201)
def create_source(
    body: SourceWrite,
    db: Session = Depends(get_db),
    user: dict = Depends(require_team_role),
):
    result = db.execute(
        text(
            "INSERT INTO source (title, url, source_type, quality, notes, "
            "archived_url, added_by_id) "
            "VALUES (:title, :url, :st, :q, :notes, :arch, :uid)"
        ),
        {
            "title": body.title, "url": body.url,
            "st": body.source_type, "q": body.quality,
            "notes": body.notes, "arch": body.archived_url,
            "uid": user["id"],
        },
    )
    sid = result.lastrowid
    log_audit(db, user["id"], "source.create", "source", sid,
              metadata={"title": body.title})
    db.commit()
    row = _select_source(db, sid)
    return Envelope(data=_row_to_source(row))


# ---------------------------------------------------------------------
# GET /api/v1/sources
# ---------------------------------------------------------------------
@router.get("", response_model=Envelope[list[SourceDetail]])
def list_sources(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    q: str | None = Query(None, min_length=2, max_length=120),
):
    where = "WHERE s.deleted_at IS NULL"
    params: dict = {"limit": page_size, "offset": (page - 1) * page_size}
    if q:
        where += " AND (s.title LIKE :pat OR s.notes LIKE :pat OR s.url LIKE :pat)"
        params["pat"] = f"%{q}%"
    total = db.execute(
        text(f"SELECT COUNT(*) FROM source s {where}"), params
    ).scalar() or 0
    rows = db.execute(
        text(
            f"SELECT s.id, s.title, s.url, s.source_type, s.quality, s.notes, "
            f"s.archived_url, s.added_by_id, s.created_at, "
            f"u.display_name AS added_by_name "
            f"FROM source s LEFT JOIN archive_user u ON u.id = s.added_by_id "
            f"{where} ORDER BY s.created_at DESC "
            f"LIMIT :limit OFFSET :offset"
        ),
        params,
    ).fetchall()
    return Envelope(
        data=[_row_to_source(r) for r in rows],
        meta=Meta(page=page, page_size=page_size, total=total),
    )


def _select_source(db: Session, sid: int):
    return db.execute(
        text(
            "SELECT s.id, s.title, s.url, s.source_type, s.quality, s.notes, "
            "s.archived_url, s.added_by_id, s.created_at, "
            "u.display_name AS added_by_name "
            "FROM source s LEFT JOIN archive_user u ON u.id = s.added_by_id "
            "WHERE s.id = :id"
        ),
        {"id": sid},
    ).first()


# ---------------------------------------------------------------------
# GET /api/v1/sources/{id}
# ---------------------------------------------------------------------
@router.get("/{source_id}", response_model=Envelope[SourceDetail])
def get_source(source_id: int, db: Session = Depends(get_db)):
    row = _select_source(db, source_id)
    if not row:
        raise HTTPException(status_code=404, detail="source not found")
    return Envelope(data=_row_to_source(row))


# ---------------------------------------------------------------------
# PATCH /api/v1/sources/{id}
# ---------------------------------------------------------------------
@router.patch("/{source_id}", response_model=Envelope[SourceDetail])
def patch_source(
    source_id: int,
    patch: SourceWrite,
    db: Session = Depends(get_db),
    user: dict = Depends(require_login),
):
    row = db.execute(
        text("SELECT id, added_by_id FROM source WHERE id = :id AND deleted_at IS NULL"),
        {"id": source_id},
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="source not found")
    if row.added_by_id != user["id"] and not user["is_admin"]:
        raise HTTPException(status_code=403, detail="only the creator or an admin can edit this source")
    db.execute(
        text(
            "UPDATE source SET title = :title, url = :url, source_type = :st, "
            "quality = :q, notes = :notes, archived_url = :arch "
            "WHERE id = :id"
        ),
        {
            "id": source_id, "title": patch.title, "url": patch.url,
            "st": patch.source_type, "q": patch.quality,
            "notes": patch.notes, "arch": patch.archived_url,
        },
    )
    log_audit(db, user["id"], "source.patch", "source", source_id)
    db.commit()
    return Envelope(data=_row_to_source(_select_source(db, source_id)))


# ---------------------------------------------------------------------
# DELETE /api/v1/sources/{id}
# ---------------------------------------------------------------------
@router.delete("/{source_id}", status_code=204)
def delete_source(
    source_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(require_login),
):
    row = db.execute(
        text("SELECT id, added_by_id FROM source WHERE id = :id AND deleted_at IS NULL"),
        {"id": source_id},
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="source not found")
    if row.added_by_id != user["id"] and not user["is_admin"]:
        raise HTTPException(status_code=403, detail="only the creator or an admin can delete this source")
    db.execute(
        text("UPDATE source SET deleted_at = CURRENT_TIMESTAMP WHERE id = :id"),
        {"id": source_id},
    )
    log_audit(db, user["id"], "source.delete", "source", source_id)
    db.commit()


# ---------------------------------------------------------------------
# POST /api/v1/sources/citations  — attach
# ---------------------------------------------------------------------
@router.post("/citations", response_model=Envelope[SourceCitation], status_code=201)
def create_citation(
    body: SourceCitationCreate,
    db: Session = Depends(get_db),
    user: dict = Depends(require_team_role),
):
    src = _select_source(db, body.source_id)
    if not src:
        raise HTTPException(status_code=404, detail="source not found")
    result = db.execute(
        text(
            "INSERT INTO source_citation (source_id, target_type, target_id, note) "
            "VALUES (:s, :tt, :tid, :note)"
        ),
        {"s": body.source_id, "tt": body.target_type,
         "tid": body.target_id, "note": body.note},
    )
    cid = result.lastrowid
    # If we're citing an inquisition, bump its sources_count for the
    # progress chip / sidebar to stay accurate.
    if body.target_type == "inquisition":
        db.execute(
            text("UPDATE inquisition SET sources_count = sources_count + 1 WHERE id = :id"),
            {"id": body.target_id},
        )
    log_audit(db, user["id"], "source.cite", body.target_type, body.target_id,
              metadata={"source_id": body.source_id, "citation_id": cid})
    db.commit()
    row = db.execute(
        text("SELECT id, source_id, target_type, target_id, note, created_at FROM source_citation WHERE id = :id"),
        {"id": cid},
    ).first()
    return Envelope(data=SourceCitation(
        id=row.id, source_id=row.source_id, source=_row_to_source(src),
        target_type=row.target_type, target_id=row.target_id,
        note=row.note, created_at=row.created_at,
    ))


# ---------------------------------------------------------------------
# DELETE /api/v1/sources/citations/{id}
# ---------------------------------------------------------------------
@router.delete("/citations/{citation_id}", status_code=204)
def remove_citation(
    citation_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(require_team_role),
):
    row = db.execute(
        text("SELECT id, target_type, target_id FROM source_citation WHERE id = :id"),
        {"id": citation_id},
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="citation not found")
    db.execute(text("DELETE FROM source_citation WHERE id = :id"), {"id": citation_id})
    if row.target_type == "inquisition":
        db.execute(
            text(
                "UPDATE inquisition SET sources_count = MAX(0, sources_count - 1) "
                "WHERE id = :id"
            ),
            {"id": row.target_id},
        )
    log_audit(db, user["id"], "source.uncite", row.target_type, row.target_id,
              metadata={"citation_id": citation_id})
    db.commit()


# ---------------------------------------------------------------------
# GET /api/v1/sources/for/{type}/{id}
# ---------------------------------------------------------------------
@router.get("/for/{target_type}/{target_id}", response_model=Envelope[list[SourceCitation]])
def list_for_target(
    target_type: str,
    target_id: int,
    db: Session = Depends(get_db),
):
    rows = db.execute(
        text(
            "SELECT c.id, c.source_id, c.target_type, c.target_id, c.note, "
            "c.created_at, s.title, s.url, s.source_type, s.quality, "
            "s.notes, s.archived_url, s.added_by_id, s.created_at AS s_created_at, "
            "u.display_name AS added_by_name "
            "FROM source_citation c "
            "JOIN source s ON s.id = c.source_id AND s.deleted_at IS NULL "
            "LEFT JOIN archive_user u ON u.id = s.added_by_id "
            "WHERE c.target_type = :tt AND c.target_id = :tid "
            "ORDER BY c.created_at ASC"
        ),
        {"tt": target_type, "tid": target_id},
    ).fetchall()
    out: list[SourceCitation] = []
    for r in rows:
        out.append(SourceCitation(
            id=r.id, source_id=r.source_id,
            source=SourceDetail(
                id=r.source_id, title=r.title, url=r.url,
                source_type=r.source_type, quality=r.quality,
                notes=r.notes, archived_url=r.archived_url,
                added_by_id=r.added_by_id, added_by_name=r.added_by_name,
                created_at=r.s_created_at,
            ),
            target_type=r.target_type, target_id=r.target_id,
            note=r.note, created_at=r.created_at,
        ))
    return Envelope(data=out, meta=Meta(total=len(out)))
