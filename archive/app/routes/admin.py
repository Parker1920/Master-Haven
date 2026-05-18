"""
Admin — super-admin-only operational endpoints.

  GET   /api/v1/admin/audit_log    recent audit_log entries
  GET   /api/v1/admin/users        paginated user list with search
  PATCH /api/v1/admin/users/{id}   update a user's role / civ / beat
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..audit import log_audit
from ..deps import get_db, require_admin
from ..models.schemas import AdminUserPatch, AdminUserRow, Envelope, Meta

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


@router.get("/audit_log")
def audit_log(
    db: Session = Depends(get_db),
    user: dict = Depends(require_admin),
    limit: int = Query(100, ge=1, le=500),
    action: str | None = None,
    target_type: str | None = None,
    target_id: int | None = None,
):
    """Read recent audit log entries. Filter by action, target_type, target_id."""
    where = "WHERE 1=1"
    params: dict = {"limit": limit}
    if action:
        where += " AND action = :action"
        params["action"] = action
    if target_type:
        where += " AND target_type = :tt"
        params["tt"] = target_type
    if target_id is not None:
        where += " AND target_id = :tid"
        params["tid"] = target_id
    rows = db.execute(
        text(
            f"SELECT a.id, a.user_id, u.display_name AS user_name, "
            f"a.action, a.target_type, a.target_id, a.metadata_json, "
            f"a.ip_address, a.created_at "
            f"FROM audit_log a "
            f"LEFT JOIN archive_user u ON u.id = a.user_id "
            f"{where} ORDER BY a.created_at DESC LIMIT :limit"
        ),
        params,
    ).fetchall()
    data = [
        {
            "id": r.id,
            "user_id": r.user_id,
            "user_name": r.user_name,
            "action": r.action,
            "target_type": r.target_type,
            "target_id": r.target_id,
            "metadata": json.loads(r.metadata_json) if r.metadata_json else None,
            "ip_address": r.ip_address,
            "created_at": r.created_at,
        }
        for r in rows
    ]
    return {"data": data, "meta": {"total": len(data)}}


@router.get("/users", response_model=Envelope[list[AdminUserRow]])
def list_users(
    db: Session = Depends(get_db),
    user: dict = Depends(require_admin),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    q: str | None = Query(None, description="search by username or display_name"),
):
    """List all archive users with pagination + optional search."""
    where = "WHERE deleted_at IS NULL"
    params: dict = {"limit": page_size, "offset": (page - 1) * page_size}
    if q:
        where += " AND (LOWER(discord_username) LIKE :q OR LOWER(display_name) LIKE :q)"
        params["q"] = f"%{q.lower()}%"
    total = db.execute(
        text(f"SELECT COUNT(*) FROM archive_user {where}"), params
    ).scalar() or 0
    rows = db.execute(
        text(
            f"SELECT id, discord_username, display_name, avatar_letter, avatar_color, "
            f"base_role, is_editor, is_admin, civ_slug, beat, created_at "
            f"FROM archive_user {where} "
            f"ORDER BY is_admin DESC, is_editor DESC, base_role DESC, display_name ASC "
            f"LIMIT :limit OFFSET :offset"
        ),
        params,
    ).fetchall()
    data = [
        AdminUserRow(
            id=r.id,
            discord_username=r.discord_username,
            display_name=r.display_name,
            avatar_letter=r.avatar_letter,
            avatar_color=r.avatar_color,
            base_role=r.base_role,
            is_editor=bool(r.is_editor),
            is_admin=bool(r.is_admin),
            civ_slug=r.civ_slug,
            beat=r.beat,
            created_at=r.created_at,
        )
        for r in rows
    ]
    return Envelope(data=data, meta=Meta(page=page, page_size=page_size, total=total))


@router.patch("/users/{user_id}", response_model=Envelope[AdminUserRow])
def patch_user(
    user_id: int,
    patch: AdminUserPatch,
    db: Session = Depends(get_db),
    user: dict = Depends(require_admin),
):
    """Update a user's role + permissions. Admin only."""
    target = db.execute(
        text("SELECT id, is_admin FROM archive_user WHERE id = :id AND deleted_at IS NULL"),
        {"id": user_id},
    ).first()
    if not target:
        raise HTTPException(status_code=404, detail="user not found")
    if target.id == user["id"] and patch.is_admin is False:
        raise HTTPException(status_code=400, detail="cannot remove your own admin flag")

    # Validate civ_slug if provided and non-empty
    if patch.civ_slug:
        exists = db.execute(
            text("SELECT 1 FROM civilization WHERE slug = :s AND deleted_at IS NULL"),
            {"s": patch.civ_slug},
        ).first()
        if not exists:
            raise HTTPException(status_code=400, detail=f"civilization '{patch.civ_slug}' not found")

    fields = {k: v for k, v in patch.model_dump(exclude_unset=True).items()}
    # Coerce booleans to ints for SQLite
    if "is_editor" in fields and fields["is_editor"] is not None:
        fields["is_editor"] = 1 if fields["is_editor"] else 0
    if "is_admin" in fields and fields["is_admin"] is not None:
        fields["is_admin"] = 1 if fields["is_admin"] else 0

    if fields:
        sets = ", ".join(f"{k} = :{k}" for k in fields)
        fields["id"] = target.id
        db.execute(
            text(
                f"UPDATE archive_user SET {sets}, updated_at = CURRENT_TIMESTAMP "
                f"WHERE id = :id"
            ),
            fields,
        )
    log_audit(db, user["id"], "user.patch", "archive_user", target.id,
              metadata={"fields_changed": [k for k in fields if k != "id"]})
    db.commit()

    row = db.execute(
        text(
            "SELECT id, discord_username, display_name, avatar_letter, avatar_color, "
            "base_role, is_editor, is_admin, civ_slug, beat, created_at "
            "FROM archive_user WHERE id = :id"
        ),
        {"id": target.id},
    ).first()
    return Envelope(data=AdminUserRow(
        id=row.id,
        discord_username=row.discord_username,
        display_name=row.display_name,
        avatar_letter=row.avatar_letter,
        avatar_color=row.avatar_color,
        base_role=row.base_role,
        is_editor=bool(row.is_editor),
        is_admin=bool(row.is_admin),
        civ_slug=row.civ_slug,
        beat=row.beat,
        created_at=row.created_at,
    ))
