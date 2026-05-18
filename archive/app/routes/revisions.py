"""
Generic revision history endpoint.

GET /api/v1/revisions/{target_type}/{target_id}

Returns the entity_revision rows for any supported target_type. The
existing per-resource routes (`/api/v1/civilizations/{slug}/revisions`
etc.) keep working — this endpoint is a uniform alternative the
frontend's <RevisionHistory> component can hit without knowing the
resource-specific slug/id contract.

target_type ∈ {civilization, person, event, place, story, inquisition}

For civ/person/event/place the {target_id} segment may be either the
integer PK or the slug; we resolve the slug to an id internally.

For story / inquisition the {target_id} must be the integer id (those
two resources are addressed by id throughout the rest of the API).

story / inquisition currently have no revision rows because
revisions.record_revision() rejects those types — see the schema
comment. The endpoint still returns 200 with an empty array so the
frontend can render its (empty) history section unconditionally.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..deps import get_db
from ..models.schemas import Author, Envelope, Meta, RevisionEntry

router = APIRouter(prefix="/api/v1/revisions", tags=["revisions"])

_SLUG_TABLES = {
    "civilization": "civilization",
    "person": "person",
    "event": "event",
    "place": "place",
}
_ID_TYPES = {"story", "inquisition"}
_ALL_TYPES = set(_SLUG_TABLES.keys()) | _ID_TYPES


def _resolve_entity_id(db: Session, target_type: str, target_id: str) -> int:
    """Accept either an integer id or a slug; return the integer entity id."""
    if target_id.isdigit():
        return int(target_id)
    if target_type in _SLUG_TABLES:
        table = _SLUG_TABLES[target_type]
        row = db.execute(
            text(f"SELECT id FROM {table} WHERE slug = :s AND deleted_at IS NULL"),
            {"s": target_id},
        ).first()
        if not row:
            raise HTTPException(status_code=404, detail=f"{target_type} not found")
        return int(row.id)
    raise HTTPException(status_code=400, detail=f"{target_type} requires an integer id")


@router.get("/{target_type}/{target_id}", response_model=Envelope[list[RevisionEntry]])
def list_revisions(
    target_type: str = Path(..., regex="^(civilization|person|event|place|story|inquisition)$"),
    target_id: str = Path(...),
    db: Session = Depends(get_db),
):
    if target_type not in _ALL_TYPES:
        raise HTTPException(status_code=400, detail="unsupported target_type")
    eid = _resolve_entity_id(db, target_type, target_id)
    rows = db.execute(
        text(
            "SELECT r.id, r.change_summary, r.snapshot_json, r.created_at, "
            "u.id AS uid, u.discord_username AS uslug, u.display_name AS uname, "
            "u.avatar_letter, u.avatar_color, u.base_role "
            "FROM entity_revision r "
            "LEFT JOIN archive_user u ON u.id = r.changed_by_id "
            "WHERE r.entity_type = :et AND r.entity_id = :eid "
            "ORDER BY r.created_at DESC"
        ),
        {"et": target_type, "eid": eid},
    ).fetchall()
    data = [
        RevisionEntry(
            id=r.id,
            changed_by=(
                Author(
                    id=r.uid, slug=r.uslug, name=r.uname,
                    avatar_letter=r.avatar_letter, avatar_color=r.avatar_color,
                    role=r.base_role,
                )
                if r.uid
                else Author(id=0, slug="system", name="system")
            ),
            change_summary=r.change_summary,
            snapshot=json.loads(r.snapshot_json) if r.snapshot_json else {},
            created_at=r.created_at,
        )
        for r in rows
    ]
    return Envelope(
        data=data,
        meta=Meta(total=len(data), extra={"target_type": target_type, "target_id": target_id}),
    )
