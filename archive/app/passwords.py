"""
Password hashing — stdlib PBKDF2-HMAC-SHA256.

Format stored in archive_user.password_hash:
    pbkdf2$<iterations>$<salt_b64>$<hash_b64>

We avoid bcrypt / argon2 to keep the dependency surface minimal. PBKDF2
at 600_000 iterations meets OWASP's 2024 guidance for SHA-256 and runs
in <100ms on the Pi 5 (acceptable for an interactive login).

Constant-time comparison via secrets.compare_digest defends against
timing attacks.
"""

from __future__ import annotations

import base64
import hashlib
import secrets

ITERATIONS = 600_000
SALT_BYTES = 16
HASH_BYTES = 32


def hash_password(plaintext: str) -> str:
    salt = secrets.token_bytes(SALT_BYTES)
    dk = hashlib.pbkdf2_hmac(
        "sha256",
        plaintext.encode("utf-8"),
        salt,
        ITERATIONS,
        dklen=HASH_BYTES,
    )
    return f"pbkdf2${ITERATIONS}${_b64(salt)}${_b64(dk)}"


def verify_password(plaintext: str, stored: str) -> bool:
    """Constant-time verification. Returns False on any malformed input."""
    if not stored or not stored.startswith("pbkdf2$"):
        return False
    try:
        _, iter_s, salt_b64, hash_b64 = stored.split("$")
        iters = int(iter_s)
        salt = _b64d(salt_b64)
        expected = _b64d(hash_b64)
    except (ValueError, TypeError):
        return False
    dk = hashlib.pbkdf2_hmac(
        "sha256",
        plaintext.encode("utf-8"),
        salt,
        iters,
        dklen=len(expected),
    )
    return secrets.compare_digest(dk, expected)


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode("ascii")


def _b64d(s: str) -> bytes:
    # Restore padding
    pad = (-len(s)) % 4
    return base64.urlsafe_b64decode(s + ("=" * pad))
