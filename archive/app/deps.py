"""
FastAPI dependencies — auth and role gates.

How the session works:
- Login (auth_dev or auth_discord) sets a signed cookie named
  `archive_session` carrying the user_id. Signed with SESSION_SECRET
  via itsdangerous so it can't be tampered with.
- get_current_user() reads + verifies the cookie, fetches the user
  from archive_user. Returns None if no/invalid cookie.
- require_login()       — 401 if not logged in
- require_team_role()   — 403 if base_role == 'reader'
- require_diplomat_or_higher() — same as team_role (diplomat is the
  lowest team role); kept as a named dep so route intent is clearer
- require_historian_or_higher() — 403 if base_role != 'historian'
                                 and not is_admin
- require_editor()      — 403 if is_editor != 1 and not is_admin
- require_admin()       — 403 if is_admin != 1
- require_can_edit_draft(draft_id) — returns the draft if current user
  is author or co-author; 403 otherwise. Phase 4 wires this in for
  draft PATCH/publish.

Sessions cookie:
- httponly=True (no JS access)
- secure=True only in production (Phase 6 puts NPM in front with SSL)
- samesite=Lax (works for first-party navigation; blocks most CSRF)
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import Cookie, Depends, HTTPException, Request, status
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy import text
from sqlalchemy.orm import Session

from .config import get_settings
from .db import get_db

log = logging.getLogger("archive.deps")

SESSION_COOKIE = "archive_session"
SESSION_MAX_AGE_SECONDS = 60 * 60 * 24 * 30  # 30 days


# ---------------------------------------------------------------------
# session cookie signing
# ---------------------------------------------------------------------
def _serializer() -> URLSafeTimedSerializer:
    """Per-app signer. New instance is cheap; secret is the same."""
    return URLSafeTimedSerializer(get_settings().session_secret, salt="archive-session")


def make_session_token(user_id: int) -> str:
    """Sign a {user_id} payload into a cookie value."""
    return _serializer().dumps({"uid": user_id})


def read_session_token(token: str) -> Optional[int]:
    """Verify + unpack a cookie value. Returns user_id or None."""
    try:
        payload = _serializer().loads(token, max_age=SESSION_MAX_AGE_SECONDS)
    except SignatureExpired:
        log.info("session cookie expired")
        return None
    except BadSignature:
        log.warning("session cookie has bad signature — possibly tampered")
        return None
    return payload.get("uid")


# ---------------------------------------------------------------------
# user fetcher
# ---------------------------------------------------------------------
def _fetch_user(db: Session, user_id: int) -> Optional[dict]:
    """Return a user dict by id, or None if missing/soft-deleted."""
    row = db.execute(
        text(
            "SELECT id, discord_id, discord_username, display_name, "
            "avatar_letter, avatar_color, civ_slug, beat, "
            "base_role, is_editor, is_admin, password_hash "
            "FROM archive_user "
            "WHERE id = :id AND deleted_at IS NULL"
        ),
        {"id": user_id},
    ).first()
    if not row:
        return None
    is_editor = bool(row.is_editor)
    is_admin = bool(row.is_admin)
    has_password = bool(row.password_hash)
    return {
        "id": row.id,
        "discord_id": row.discord_id,
        "discord_username": row.discord_username,
        "display_name": row.display_name,
        "avatar_letter": row.avatar_letter,
        "avatar_color": row.avatar_color,
        "civ_slug": row.civ_slug,
        "beat": row.beat,
        "base_role": row.base_role,
        "is_editor": is_editor,
        "is_admin": is_admin,
        "has_password": has_password,
        # Privileged accounts MUST have a password before doing privileged
        # things. Plain readers/diplomats/historians never need one.
        "needs_password": (is_admin or is_editor) and not has_password,
    }


# ---------------------------------------------------------------------
# FastAPI dependencies
# ---------------------------------------------------------------------
def get_current_user(
    db: Session = Depends(get_db),
    archive_session: Optional[str] = Cookie(default=None),
) -> Optional[dict]:
    """Reads cookie, returns user dict or None. Does NOT raise."""
    if not archive_session:
        return None
    uid = read_session_token(archive_session)
    if uid is None:
        return None
    return _fetch_user(db, uid)


def require_login(user: Optional[dict] = Depends(get_current_user)) -> dict:
    """401 if not logged in."""
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="login required",
        )
    return user


def require_team_role(user: dict = Depends(require_login)) -> dict:
    """403 if base_role == 'reader'. Diplomat or higher passes."""
    if user["base_role"] == "reader":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="team role required (diplomat or historian)",
        )
    return user


# Named alias — same gate, clearer route intent.
require_diplomat_or_higher = require_team_role


def require_historian_or_higher(user: dict = Depends(require_login)) -> dict:
    """403 if not historian and not admin. Historian-only writes go here."""
    if user["base_role"] != "historian" and not user["is_admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="historian role required",
        )
    return user


def require_editor(user: dict = Depends(require_login)) -> dict:
    """403 if not editor (admin counts as editor). Also 403 if no password set."""
    if not user["is_editor"] and not user["is_admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="editor elevation required",
        )
    if user["needs_password"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="password required for editor actions — set one in your profile",
        )
    return user


def require_admin(user: dict = Depends(require_login)) -> dict:
    """403 if not admin. Also 403 if no password set."""
    if not user["is_admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="admin required",
        )
    if user["needs_password"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="password required for admin actions — set one in your profile",
        )
    return user


def require_can_edit_draft(
    draft_id: int,
    user: dict = Depends(require_login),
    db: Session = Depends(get_db),
) -> dict:
    """
    Returns the draft row (as dict) if the current user is the author
    or a co-author. 403 otherwise. 404 if draft is missing.

    Phase 4 will wire this into draft PATCH and the publish flow.
    """
    draft = db.execute(
        text(
            "SELECT id, doctype, headline, deck, body, beat, numeral, "
            "status, author_id, reviewed_by_id, reviewed_at, "
            "published_as_story_id, published_as_inquisition_id, "
            "last_edited_at, created_at "
            "FROM draft "
            "WHERE id = :id AND deleted_at IS NULL"
        ),
        {"id": draft_id},
    ).first()
    if not draft:
        raise HTTPException(status_code=404, detail="draft not found")
    if draft.author_id == user["id"]:
        return dict(draft._mapping)
    coauthor = db.execute(
        text(
            "SELECT 1 FROM draft_coauthor "
            "WHERE draft_id = :d AND user_id = :u"
        ),
        {"d": draft_id, "u": user["id"]},
    ).first()
    if coauthor:
        return dict(draft._mapping)
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="not authorized to edit this draft",
    )
