"""Single-password admin auth with in-memory cookie sessions.

Not hardened against a determined attacker, but fine for one admin with a
strong password behind HTTPS (NPM terminates TLS in front of the container).
Tokens live in a process-local dict with a TTL; a container restart logs
everyone out, which is acceptable here.
"""

import os
import secrets
import time

from fastapi import HTTPException, Request, Response

ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "changeme")
COOKIE_NAME = "gf_admin"
SESSION_TTL_SECONDS = int(os.environ.get("ADMIN_SESSION_TTL", str(7 * 24 * 3600)))
# Secure cookie by default (production is HTTPS). Set GF_COOKIE_SECURE=0 for
# local http:// testing so the browser will actually store the cookie.
COOKIE_SECURE = os.environ.get("GF_COOKIE_SECURE", "1") not in ("0", "false", "False", "")

# token -> expiry epoch seconds
_sessions: dict[str, float] = {}


def verify_password(password: str) -> bool:
    return secrets.compare_digest(password or "", ADMIN_PASSWORD)


def create_session() -> str:
    token = secrets.token_urlsafe(32)
    _sessions[token] = time.time() + SESSION_TTL_SECONDS
    return token


def destroy_session(token: str | None) -> None:
    if token:
        _sessions.pop(token, None)


def _is_valid(token: str | None) -> bool:
    if not token:
        return False
    expiry = _sessions.get(token)
    if expiry is None:
        return False
    if expiry < time.time():
        _sessions.pop(token, None)
        return False
    return True


def set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        max_age=SESSION_TTL_SECONDS,
        httponly=True,
        samesite="lax",
        secure=COOKIE_SECURE,
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(key=COOKIE_NAME, path="/")


def require_admin(request: Request) -> None:
    """FastAPI dependency — raises 401 unless a valid admin cookie is present."""
    token = request.cookies.get(COOKIE_NAME)
    if not _is_valid(token):
        raise HTTPException(status_code=401, detail="Admin authentication required.")
