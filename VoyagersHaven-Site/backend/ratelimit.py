"""Tiny in-memory, per-IP rate limiter for public POST endpoints.

Process-local (fine for a single-container deploy). A restart resets counters.
Not a defense against a distributed flood — just enough to keep casual spam and
accidental double-submits off the inbox/DB.
"""

import time
from collections import defaultdict

from fastapi import HTTPException, Request

_hits: dict[str, list[float]] = defaultdict(list)


def check_rate_limit(request: Request, bucket: str, limit: int, window_seconds: int) -> None:
    ip = request.client.host if request.client else "unknown"
    key = f"{bucket}:{ip}"
    now = time.time()
    recent = [t for t in _hits[key] if t > now - window_seconds]
    if len(recent) >= limit:
        raise HTTPException(status_code=429, detail="Too many requests — please wait a moment and try again.")
    recent.append(now)
    _hits[key] = recent
