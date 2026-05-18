"""
Claim-based authentication (option A from the v0.6 decision).

Login model:
- New username (never claimed) → user types it, account created,
  logged in immediately. Discord ID synthesized as 'claim:<username>'.
- Username with NO password set → user types it, instantly logged in
  (anyone can re-claim a free name; community trust model).
- Username WITH a password set → user MUST provide the correct password.

Endpoints:
  POST /api/v1/auth/claim              {username, password?}
  POST /api/v1/auth/set-password       {current_password?, new_password}
  POST /api/v1/auth/clear-password     {current_password}   (rare; un-locks the name)

Bootstrap rule: if NO archive_user has is_admin=1, the first user to
claim ANY username becomes admin (and is_editor). This lets a fresh
deploy work without a side-channel SQL bootstrap. After that first
admin exists, the bootstrap rule never fires again.

Admin/editor password enforcement is in deps.py — those role gates
return 403 if the user has the privilege flag but no password_hash.
"""

from __future__ import annotations

import logging
import re

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from .config import get_settings
from .deps import (
    SESSION_COOKIE,
    SESSION_MAX_AGE_SECONDS,
    get_db,
    make_session_token,
    require_login,
)
from .passwords import hash_password, verify_password

log = logging.getLogger("archive.auth_claim")

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


# Username rules: 2-32 chars, lowercase letters / digits / dot / underscore.
# Mirrors the comment-mention regex so @-handles match cleanly.
USERNAME_RE = re.compile(r"^[a-z0-9_.]{2,32}$")


# ---------------------------------------------------------------------
# request models
# ---------------------------------------------------------------------
class ClaimRequest(BaseModel):
    username: str = Field(..., min_length=2, max_length=32)
    password: str | None = Field(None, max_length=200)


class SetPasswordRequest(BaseModel):
    current_password: str | None = Field(None, max_length=200)
    new_password: str = Field(..., min_length=6, max_length=200)


class ClearPasswordRequest(BaseModel):
    current_password: str = Field(..., max_length=200)


# ---------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------
def _set_session_cookie(response: Response, user_id: int) -> None:
    token = make_session_token(user_id)
    settings = get_settings()
    response.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        max_age=SESSION_MAX_AGE_SECONDS,
        httponly=True,
        secure=settings.is_production,
        samesite="lax",
        path="/",
    )


def _no_admin_exists(db: Session) -> bool:
    row = db.execute(
        text("SELECT 1 FROM archive_user WHERE is_admin = 1 AND deleted_at IS NULL LIMIT 1")
    ).first()
    return row is None


def _avatar_color_for(username: str) -> str:
    """Stable per-username color choice from a small palette."""
    palette = ["purple", "pink", "teal", "coral", "amber", "slate", "green"]
    return palette[sum(ord(c) for c in username) % len(palette)]


# ---------------------------------------------------------------------
# POST /api/v1/auth/claim
# ---------------------------------------------------------------------
@router.post("/claim")
def claim(
    body: ClaimRequest,
    response: Response,
    db: Session = Depends(get_db),
):
    """
    Claim a username. Three branches:
    - username doesn't exist: create row, log in (first-admin bootstrap
      if no admin yet)
    - exists without password_hash: log in (free re-claim)
    - exists with password_hash: require password to match
    """
    username = body.username.strip().lower()
    if not USERNAME_RE.match(username):
        raise HTTPException(
            status_code=400,
            detail="username must be 2-32 chars of lowercase letters/digits/dot/underscore",
        )

    existing = db.execute(
        text(
            "SELECT id, display_name, base_role, is_admin, is_editor, "
            "password_hash FROM archive_user "
            "WHERE discord_username = :u AND deleted_at IS NULL"
        ),
        {"u": username},
    ).first()

    if existing is None:
        # First-admin bootstrap: if no admin row exists yet, the first
        # claimer becomes admin + editor. Otherwise, plain reader.
        bootstrap_admin = _no_admin_exists(db)
        base_role = "historian" if bootstrap_admin else "reader"
        result = db.execute(
            text(
                "INSERT INTO archive_user ("
                "discord_id, discord_username, display_name, "
                "avatar_letter, avatar_color, base_role, is_editor, is_admin"
                ") VALUES ("
                ":discord_id, :u, :name, :letter, :color, :role, :editor, :admin"
                ")"
            ),
            {
                "discord_id": f"claim:{username}",
                "u": username,
                "name": username,
                "letter": username[0].upper(),
                "color": _avatar_color_for(username),
                "role": base_role,
                "editor": 1 if bootstrap_admin else 0,
                "admin": 1 if bootstrap_admin else 0,
            },
        )
        new_id = result.lastrowid
        db.execute(
            text("UPDATE archive_user SET last_login = CURRENT_TIMESTAMP WHERE id = :id"),
            {"id": new_id},
        )
        db.commit()
        if bootstrap_admin:
            log.info("claim bootstrap admin: %s (id=%d)", username, new_id)
        else:
            log.info("claim new user: %s (id=%d)", username, new_id)
        _set_session_cookie(response, new_id)
        return {"data": {
            "id": new_id,
            "username": username,
            "is_new": True,
            "is_bootstrap_admin": bootstrap_admin,
            "needs_password": bootstrap_admin,  # admin must set one
        }, "meta": {}}

    # User exists. Check for password requirement.
    if existing.password_hash:
        if not body.password or not verify_password(body.password, existing.password_hash):
            raise HTTPException(
                status_code=401,
                detail="password required for this username",
            )
    # else: name is unlocked, anyone can re-claim it

    db.execute(
        text("UPDATE archive_user SET last_login = CURRENT_TIMESTAMP WHERE id = :id"),
        {"id": existing.id},
    )
    db.commit()
    _set_session_cookie(response, existing.id)
    log.info("claim existing: %s (id=%d)", username, existing.id)
    needs_password = (
        (bool(existing.is_admin) or bool(existing.is_editor))
        and not existing.password_hash
    )
    return {"data": {
        "id": existing.id,
        "username": username,
        "is_new": False,
        "needs_password": needs_password,
    }, "meta": {}}


# ---------------------------------------------------------------------
# POST /api/v1/auth/set-password
# ---------------------------------------------------------------------
@router.post("/set-password")
def set_password(
    body: SetPasswordRequest,
    db: Session = Depends(get_db),
    user: dict = Depends(require_login),
):
    """
    Set or change the current user's password.

    - If the user already has a password, current_password must verify.
    - If not (first time setting), current_password is ignored.
    """
    existing_hash = db.execute(
        text("SELECT password_hash FROM archive_user WHERE id = :id"),
        {"id": user["id"]},
    ).scalar()

    if existing_hash:
        if not body.current_password or not verify_password(
            body.current_password, existing_hash
        ):
            raise HTTPException(status_code=401, detail="current password incorrect")

    new_hash = hash_password(body.new_password)
    db.execute(
        text("UPDATE archive_user SET password_hash = :h WHERE id = :id"),
        {"h": new_hash, "id": user["id"]},
    )
    db.commit()
    log.info("password set for user %s (id=%d)", user["discord_username"], user["id"])
    return {"data": {"password_set": True}, "meta": {}}


# ---------------------------------------------------------------------
# POST /api/v1/auth/clear-password
# ---------------------------------------------------------------------
@router.post("/clear-password")
def clear_password(
    body: ClearPasswordRequest,
    db: Session = Depends(get_db),
    user: dict = Depends(require_login),
):
    """
    Remove your password (unlock the username). Reverses the lock that
    set-password applied. Admin/editor accounts shouldn't normally call
    this — once cleared, they'll be in the needs_password state and
    can't perform privileged actions until they set one again.
    """
    existing_hash = db.execute(
        text("SELECT password_hash FROM archive_user WHERE id = :id"),
        {"id": user["id"]},
    ).scalar()
    if not existing_hash:
        return {"data": {"password_cleared": True}, "meta": {}}
    if not verify_password(body.current_password, existing_hash):
        raise HTTPException(status_code=401, detail="current password incorrect")
    db.execute(
        text("UPDATE archive_user SET password_hash = NULL WHERE id = :id"),
        {"id": user["id"]},
    )
    db.commit()
    log.info("password cleared for user %s (id=%d)", user["discord_username"], user["id"])
    return {"data": {"password_cleared": True}, "meta": {}}
