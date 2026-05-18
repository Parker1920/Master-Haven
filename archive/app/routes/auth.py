"""
Auth — shared endpoints.

  GET   /api/v1/auth/me     current session user (or 401)
  PATCH /api/v1/auth/me     edit own profile (display_name, bio, civ, beat, avatar)
  POST  /api/v1/auth/logout clear the session cookie

The dev-login (auth_dev.py) and Discord OAuth (auth_discord.py)
modules expose their own mount points but both produce the same
session cookie that this module reads.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..audit import log_audit
from ..db import get_db
from ..deps import (
    SESSION_COOKIE,
    get_current_user,
    require_login,
)
from ..models.schemas import SelfProfilePatch

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.get("/me")
def whoami(user: dict = Depends(require_login)):
    """Return the current user. 401 if no valid session."""
    # require_login already raised if no user, so user is non-None
    return {"data": user, "meta": {}}


@router.patch("/me")
def update_me(
    patch: SelfProfilePatch,
    db: Session = Depends(get_db),
    user: dict = Depends(require_login),
):
    """
    Self-edit profile: display_name, bio, civ_slug, beat, avatar_letter,
    avatar_color. Cannot change role/admin/editor flags here (admin only,
    via /admin/users).
    """
    fields = {k: v for k, v in patch.model_dump(exclude_unset=True).items()}
    # Validate civ_slug if non-empty
    if fields.get("civ_slug"):
        exists = db.execute(
            text("SELECT 1 FROM civilization WHERE slug = :s AND deleted_at IS NULL"),
            {"s": fields["civ_slug"]},
        ).first()
        if not exists:
            raise HTTPException(status_code=400, detail=f"civilization '{fields['civ_slug']}' not found")
    if fields:
        sets = ", ".join(f"{k} = :{k}" for k in fields)
        fields["id"] = user["id"]
        db.execute(
            text(
                f"UPDATE archive_user SET {sets}, updated_at = CURRENT_TIMESTAMP "
                f"WHERE id = :id"
            ),
            fields,
        )
        log_audit(db, user["id"], "user.self_edit", "archive_user", user["id"],
                  metadata={"fields_changed": [k for k in fields if k != "id"]})
        db.commit()
    row = db.execute(
        text(
            "SELECT id, discord_id, discord_username, display_name, avatar_letter, "
            "avatar_color, civ_slug, beat, base_role, is_editor, is_admin, "
            "password_hash, bio "
            "FROM archive_user WHERE id = :id"
        ),
        {"id": user["id"]},
    ).first()
    is_editor = bool(row.is_editor)
    is_admin = bool(row.is_admin)
    has_password = bool(row.password_hash)
    return {
        "data": {
            "id": row.id,
            "discord_id": row.discord_id,
            "discord_username": row.discord_username,
            "display_name": row.display_name,
            "avatar_letter": row.avatar_letter,
            "avatar_color": row.avatar_color,
            "civ_slug": row.civ_slug,
            "beat": row.beat,
            "bio": row.bio,
            "base_role": row.base_role,
            "is_editor": is_editor,
            "is_admin": is_admin,
            "has_password": has_password,
            "needs_password": (is_admin or is_editor) and not has_password,
        },
        "meta": {},
    }


@router.post("/logout")
def logout(response: Response, user: Optional[dict] = Depends(get_current_user)):
    """
    Clear the session cookie. Idempotent — calling without a session
    still returns 200 (we just delete the cookie either way).
    """
    response.delete_cookie(SESSION_COOKIE, path="/")
    return {"data": {"logged_out": True}, "meta": {}}
