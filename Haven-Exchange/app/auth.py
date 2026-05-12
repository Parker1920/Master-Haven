"""
Travelers Exchange — Authentication Helpers & FastAPI Dependencies

Provides password hashing, session management, and dependency injection
functions for protecting routes.
"""

import random
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
from fastapi import Depends, HTTPException, Request
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import ApiKey, Nation, Session_, User


# ---------------------------------------------------------------------------
# Keeper integration P0 — API key generation & verification
# ---------------------------------------------------------------------------
# Bearer-token credentials for external bots.  Plaintext keys look like:
#     tx_live_<32 hex chars>
# The first 12 chars (e.g. "tx_live_a1b2") are the prefix used as a fast
# index lookup; the full plaintext is then bcrypt-compared against
# ApiKey.key_hash on the matching row.

API_KEY_PREFIX_LEN = 12  # "tx_live_" + 4 hex chars
API_KEY_TAG = "tx_live_"


def generate_api_key() -> tuple[str, str, str]:
    """Mint a fresh plaintext key.

    Returns ``(plaintext, prefix, hash)``.  Caller is responsible for
    persisting prefix + hash to the database; plaintext is shown to the
    operator once and never stored.
    """
    body = secrets.token_hex(16)  # 32 hex chars
    plaintext = f"{API_KEY_TAG}{body}"
    prefix = plaintext[:API_KEY_PREFIX_LEN]
    hashed = bcrypt.hashpw(plaintext.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    return plaintext, prefix, hashed


def verify_api_key(token: str, db: Session) -> Optional[ApiKey]:
    """Look up an ApiKey by bearer token.

    Returns the active ApiKey row, or None if the token doesn't match.
    Updates ``last_used_at`` as a side effect on a successful match.
    """
    if not token or not token.startswith(API_KEY_TAG):
        return None
    prefix = token[:API_KEY_PREFIX_LEN]
    candidates = db.execute(
        select(ApiKey).where(ApiKey.key_prefix == prefix, ApiKey.is_active == True)  # noqa: E712
    ).scalars().all()
    for cand in candidates:
        try:
            if bcrypt.checkpw(token.encode("utf-8"), cand.key_hash.encode("utf-8")):
                cand.last_used_at = datetime.now(timezone.utc)
                db.commit()
                return cand
        except (ValueError, TypeError):
            continue
    return None


def _resolve_bot_user(request: Request, db: Session) -> Optional[User]:
    """If the request carries a valid bot bearer token + X-Discord-User-Id
    header, resolve (or auto-provision) the Exchange user and return it.

    Auto-provision: if no User row has the supplied discord_id, create one.
    The Keeper bot is the Exchange in bot form — first contact from a
    Discord user IS their account creation.  No website detour, no
    password prompt.

    Optional headers used during provisioning:
      X-Discord-Username  — used as username (defaults to "discord_<id>")
      X-Discord-Display   — used as display_name (defaults to None)

    Returns None when the bot key is missing/invalid or the X-Discord-
    User-Id header is absent — falls back to session auth.
    """
    auth_hdr = request.headers.get("authorization") or ""
    if not auth_hdr.lower().startswith("bearer "):
        return None
    token = auth_hdr.split(None, 1)[1].strip()
    api_key = verify_api_key(token, db)
    if api_key is None:
        return None

    discord_id = (request.headers.get("x-discord-user-id") or "").strip()
    if not discord_id:
        return None

    user = db.execute(
        select(User).where(User.discord_id == discord_id)
    ).scalar_one_or_none()
    if user is not None:
        return user

    # Auto-provision a fresh account for this Discord user.
    from app.wallet import generate_wallet_address  # local to avoid cycle

    raw_username = (request.headers.get("x-discord-username") or "").strip()
    display_name = (request.headers.get("x-discord-display") or "").strip() or None

    base_username = raw_username or f"discord_{discord_id}"
    base_username = "".join(ch for ch in base_username if ch.isalnum() or ch in "_-.")[:64] or f"discord_{discord_id}"

    # Resolve username collisions deterministically.
    username = base_username
    suffix = 1
    while db.execute(select(User).where(User.username == username)).scalar_one_or_none() is not None:
        suffix += 1
        username = f"{base_username}_{suffix}"
        if suffix > 100:
            username = f"discord_{discord_id}"  # fall back to the guaranteed-unique form
            break

    # Random unguessable password — the Discord user can't log in via the
    # web with this; they can change it later via /api/auth/settings/password
    # if they want website access.
    pw_hash = bcrypt.hashpw(secrets.token_hex(32).encode(), bcrypt.gensalt()).decode()

    new_user = User(
        username=username,
        password_hash=pw_hash,
        display_name=display_name,
        wallet_address="PENDING",
        role="citizen",
        balance=0,
        discord_id=discord_id,
    )
    db.add(new_user)
    db.flush()
    new_user.wallet_address = generate_wallet_address(new_user.id, settings.SECRET_KEY)
    db.commit()
    return new_user


# ---------------------------------------------------------------------------
# Password helpers
# ---------------------------------------------------------------------------

def hash_password(password: str) -> str:
    """Hash a plaintext password using bcrypt.

    Returns the hash as a UTF-8 string suitable for database storage.
    """
    hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
    return hashed.decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a plaintext password against a bcrypt hash.

    Returns True if the password matches, False otherwise.
    """
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


# ---------------------------------------------------------------------------
# Session management
# ---------------------------------------------------------------------------

def create_session(db: Session, user_id: int) -> str:
    """Create a new login session for the given user.

    Generates a cryptographically random token, persists a Session_ row,
    and returns the token string.
    """
    token = secrets.token_hex(32)
    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.SESSION_EXPIRY_DAYS)

    session = Session_(
        id=token,
        user_id=user_id,
        expires_at=expires_at,
    )
    db.add(session)
    db.commit()
    return token


def delete_session(db: Session, session_token: str) -> None:
    """Delete a session row by its token."""
    stmt = delete(Session_).where(Session_.id == session_token)
    db.execute(stmt)
    db.commit()


# ---------------------------------------------------------------------------
# FastAPI dependencies
# ---------------------------------------------------------------------------

def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
) -> Optional[User]:
    """FastAPI dependency that resolves the currently logged-in user.

    Resolution order:
      1. Bot bearer token + X-Discord-User-Id header — for Keeper bot
         requests.  The bearer must match an active ApiKey row, and
         the discord_id header must match a User.discord_id binding.
      2. Session cookie — the standard browser path.
    Returns None when neither produces a user.

    Occasionally cleans up expired sessions to keep the table tidy.
    """
    # 1. Bot path
    bot_user = _resolve_bot_user(request, db)
    if bot_user is not None:
        return bot_user

    # 2. Session cookie path
    token = request.cookies.get("session_token")
    if not token:
        return None

    # Look up the session
    stmt = select(Session_).where(Session_.id == token)
    session = db.execute(stmt).scalar_one_or_none()

    if session is None:
        return None

    # Check expiration
    now = datetime.now(timezone.utc)
    # Handle naive datetimes stored by SQLite (assume UTC)
    expires_at = session.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if now > expires_at:
        # Session expired — remove it
        delete_session(db, token)
        return None

    # Update last_active on the user
    session.user.last_active = datetime.now(timezone.utc)
    db.commit()

    # Occasionally clean up expired sessions (~5 % of requests)
    if random.random() < 0.05:
        cleanup_stmt = delete(Session_).where(Session_.expires_at < now)
        db.execute(cleanup_stmt)
        db.commit()

    return session.user


def require_login(
    current_user: Optional[User] = Depends(get_current_user),
) -> User:
    """FastAPI dependency that enforces authentication.

    Redirects unauthenticated visitors to ``/login`` via a 303 See Other
    response.
    """
    if current_user is None:
        raise HTTPException(
            status_code=303,
            headers={"Location": "/login"},
            detail="Not authenticated",
        )
    return current_user


def require_role(role: str):
    """Return a FastAPI dependency that enforces a specific user role.

    Usage::

        @router.get("/admin")
        def admin_panel(user: User = Depends(require_role("world_mint"))):
            ...
    """

    def _role_checker(
        request: Request,
        db: Session = Depends(get_db),
    ) -> User:
        user = get_current_user(request, db)
        if user is None:
            raise HTTPException(
                status_code=303,
                headers={"Location": "/login"},
                detail="Not authenticated",
            )
        if user.role != role:
            raise HTTPException(
                status_code=403,
                detail=f"Requires role: {role}",
            )
        return user

    return _role_checker


# ---------------------------------------------------------------------------
# Relational leader checks
# ---------------------------------------------------------------------------
# Prefer these over `if user.role == "nation_leader"` — the role enum is a
# coarse cache that drifts (e.g. when a nation is suspended the role is not
# automatically demoted).  Source of truth is the `nations` table.

def is_leader_of(user: Optional[User], nation: Optional[Nation]) -> bool:
    """True iff *user* leads the supplied *nation* and the nation is approved."""
    if user is None or nation is None:
        return False
    return nation.leader_id == user.id and nation.status == "approved"


def get_led_nation(db: Session, user: Optional[User]) -> Optional[Nation]:
    """Return the approved nation *user* currently leads, or None."""
    if user is None:
        return None
    return db.execute(
        select(Nation).where(
            Nation.leader_id == user.id,
            Nation.status == "approved",
        )
    ).scalar_one_or_none()
