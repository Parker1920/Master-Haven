"""
Travelers Exchange — Authentication Routes

Provides registration, login, and logout endpoints under ``/api/auth``.
"""

from fastapi import APIRouter, Depends, Form, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import (
    create_session,
    delete_session,
    hash_password,
    verify_password,
)
from app.config import settings
from app.database import get_db
from app.models import User
from app.wallet import generate_wallet_address

router = APIRouter(prefix="/api/auth", tags=["auth"])

# Cookie configuration
COOKIE_KEY = "session_token"
COOKIE_MAX_AGE = 7 * 24 * 60 * 60  # 7 days in seconds


def _set_session_cookie(response: Response, token: str) -> None:
    """Apply the session cookie to *response* with standard settings.

    NOTE on `secure=True`: cookies marked Secure are only sent by browsers
    over HTTPS.  Production runs behind Cloudflare → Nginx Proxy Manager
    with TLS termination so this is correct there.  In a plain-HTTP local
    dev setup (e.g. running the container on http://localhost:8010 without
    a proxy), real browsers will refuse to *store* the cookie at all and
    every request will appear unauthenticated.  Workarounds for local dev:
      1. Run the dev container behind an HTTPS proxy (e.g. mkcert + caddy).
      2. Temporarily flip secure=False here for local-only debugging.
    A future hardening pass should gate this on an env var (e.g.
    `settings.COOKIE_SECURE`) so the same code base works in both modes
    without requiring a manual toggle.
    """
    response.set_cookie(
        key=COOKIE_KEY,
        value=token,
        httponly=True,
        samesite="lax",
        secure=False,  # TEMP for local-dev demo — flip back to True before merging
        max_age=COOKIE_MAX_AGE,
    )


# ---------------------------------------------------------------------------
# POST /api/auth/register
# ---------------------------------------------------------------------------

@router.post("/register")
def register(
    request: Request,
    response: Response,
    username: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...),
    email: str = Form(None),
    display_name: str = Form(None),
    db: Session = Depends(get_db),
) -> dict:
    """Register a new user account.

    Accepts form-encoded data, validates inputs, creates the user with a
    wallet address, starts a session, and returns the wallet address.
    """
    # --- Validation ---
    if not username or not username.strip():
        return {"success": False, "error": "Username is required"}

    username = username.strip()

    if len(password) < 8:
        return {"success": False, "error": "Password must be at least 8 characters"}

    if password != confirm_password:
        return {"success": False, "error": "Passwords do not match"}

    # Check uniqueness
    stmt = select(User).where(User.username == username)
    existing = db.execute(stmt).scalar_one_or_none()
    if existing is not None:
        return {"success": False, "error": "Username already taken"}

    # --- Create user (without wallet address first) ---
    hashed_pw = hash_password(password)

    new_user = User(
        username=username,
        password_hash=hashed_pw,
        email=email or None,
        display_name=display_name or None,
        wallet_address="PENDING",  # placeholder — will be replaced after flush
        role="citizen",
        balance=0,
    )
    db.add(new_user)
    db.flush()  # assigns new_user.id without committing

    # Generate wallet address from the real user ID
    wallet_address = generate_wallet_address(new_user.id, settings.SECRET_KEY)
    new_user.wallet_address = wallet_address

    db.commit()

    # --- Start session ---
    token = create_session(db, new_user.id)
    _set_session_cookie(response, token)

    return {"success": True, "wallet_address": wallet_address}


# ---------------------------------------------------------------------------
# POST /api/auth/login
# ---------------------------------------------------------------------------

@router.post("/login")
def login(
    request: Request,
    response: Response,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
) -> dict:
    """Authenticate an existing user.

    Verifies credentials, creates a new session, and sets the session
    cookie.
    """
    # Clear any existing session first (so switching accounts works cleanly)
    old_token = request.cookies.get(COOKIE_KEY)
    if old_token:
        delete_session(db, old_token)

    stmt = select(User).where(User.username == username)
    user = db.execute(stmt).scalar_one_or_none()

    if user is None or not verify_password(password, user.password_hash):
        return {"success": False, "error": "Invalid username or password"}

    token = create_session(db, user.id)
    _set_session_cookie(response, token)

    return {"success": True}


# ---------------------------------------------------------------------------
# POST /api/auth/logout
# ---------------------------------------------------------------------------

@router.post("/logout")
def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> dict:
    """End the current user session.

    Removes the session from the database and clears the cookie.
    """
    token = request.cookies.get(COOKIE_KEY)
    if token:
        delete_session(db, token)

    response.delete_cookie(
        key=COOKIE_KEY,
        httponly=True,
        samesite="lax",
        secure=True,
    )

    return {"success": True}



# ---------------------------------------------------------------------------
# Account self-service (mirrors website /settings/* — bot-callable)
# ---------------------------------------------------------------------------

from fastapi import HTTPException as _HTTPException  # noqa: E402
from pydantic import BaseModel as _BaseModel  # noqa: E402

from app.auth import require_login as _require_login  # noqa: E402


class _PasswordChangeRequest(_BaseModel):
    old_password: str
    new_password: str


class _DisplayNameRequest(_BaseModel):
    display_name: str | None = None


@router.post("/settings/password")
def settings_change_password(
    payload: _PasswordChangeRequest,
    user: User = Depends(_require_login),
    db: Session = Depends(get_db),
) -> dict:
    """Change the calling user's password.  Same rules as the web form."""
    if not verify_password(payload.old_password, user.password_hash):
        raise _HTTPException(status_code=403, detail="Current password is incorrect.")
    if len(payload.new_password) < 8:
        raise _HTTPException(status_code=400, detail="New password must be at least 8 characters.")
    user.password_hash = hash_password(payload.new_password)
    db.commit()
    return {"success": True}


@router.post("/settings/display-name")
def settings_change_display_name(
    payload: _DisplayNameRequest,
    user: User = Depends(_require_login),
    db: Session = Depends(get_db),
) -> dict:
    """Update the calling user's display name."""
    cleaned = (payload.display_name or "").strip() or None
    user.display_name = cleaned
    db.commit()
    return {"success": True, "display_name": cleaned}
