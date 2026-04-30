"""
Smoke-suite alert state — tracks consecutive failures per test name and
the last-alert-sent time per webhook.

State file lives at ~/.haven-smoke-state.json. Schema:

    {
      "consecutive_failures": {"<nodeid>": 2, ...},
      "last_alert_at": 1761748800.0
    }

PROPOSAL §5 noise control:
  - P0 failures alert immediately on first failure.
  - P1 failures alert only after 3 consecutive failures.
  - Rate limit: at most one alert per 30s (PROPOSAL §10.13).
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Dict


STATE_FILE = Path(os.environ.get("HAVEN_SMOKE_STATE_FILE",
                                 str(Path.home() / ".haven-smoke-state.json")))

ALERT_RATE_LIMIT_SECONDS = 30
P1_THRESHOLD = 3


def _load() -> dict:
    if not STATE_FILE.exists():
        return {"consecutive_failures": {}, "last_alert_at": 0.0}
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"consecutive_failures": {}, "last_alert_at": 0.0}


def _save(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def record_failure(nodeid: str) -> int:
    """Increment the consecutive failure counter for `nodeid`. Returns the
    new count."""
    state = _load()
    counts: Dict[str, int] = state.setdefault("consecutive_failures", {})
    counts[nodeid] = counts.get(nodeid, 0) + 1
    _save(state)
    return counts[nodeid]


def record_pass(nodeid: str) -> None:
    """Reset the consecutive failure counter for `nodeid`."""
    state = _load()
    counts: Dict[str, int] = state.setdefault("consecutive_failures", {})
    if nodeid in counts:
        del counts[nodeid]
    _save(state)


def should_alert(nodeid: str, is_p1: bool, current_count: int) -> bool:
    """Decide whether a failure warrants an alert.

    P0: alert immediately.
    P1: alert only on the Nth consecutive failure (P1_THRESHOLD).
    """
    if not is_p1:
        return current_count >= 1
    return current_count >= P1_THRESHOLD


def can_send_alert_now() -> bool:
    """Rate limit: refuse to send if the last alert was within the floor."""
    state = _load()
    return time.time() - state.get("last_alert_at", 0.0) >= ALERT_RATE_LIMIT_SECONDS


def mark_alert_sent() -> None:
    state = _load()
    state["last_alert_at"] = time.time()
    _save(state)
