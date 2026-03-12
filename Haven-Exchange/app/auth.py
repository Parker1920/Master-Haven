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
from app.models import Session_, User


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

    Reads the ``session_token`` cookie, looks up the corresponding
    Session_ row, and returns the associated User if the session is still
    valid.  Returns ``None`` when no valid session exists.

    Occasionally cleans up expired sessions to keep the table tidy.
    """
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
