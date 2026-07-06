"""Activity log — every create/update/delete/generate writes a row.

log_activity() only session.add()s: the caller commits, so the audit row
lands atomically with the change it describes (or not at all).
"""
from datetime import datetime, timezone

from sqlmodel import Session

from ..models import ActivityLog


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def log_activity(
    session: Session,
    entity: str,
    entity_id: int | None,
    action: str,
    detail: str | None = None,
    actor: str = "parker",  # Phase 1: tailnet = Parker; real actor arrives with auth tiers
) -> None:
    session.add(ActivityLog(
        ts=now_iso(), actor=actor, entity=entity,
        entity_id=entity_id, action=action, detail=detail,
    ))
