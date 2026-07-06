"""Activity feed — read side of the activity_log audit table.

Every mutation in the app (and every relay from voyagershaven.online) already
writes a row atomically with its change; this exposes the newest slice for
the Bridge feed. Read-only: the log has no update/delete anywhere.
"""
from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from ..db import get_session
from ..models import ActivityLog

router = APIRouter(prefix="/api/activity", tags=["activity"])


@router.get("")
def list_activity(limit: int = 30, session: Session = Depends(get_session)):
    limit = max(1, min(limit, 200))
    rows = session.exec(
        select(ActivityLog).order_by(ActivityLog.id.desc()).limit(limit)
    ).all()
    return rows
