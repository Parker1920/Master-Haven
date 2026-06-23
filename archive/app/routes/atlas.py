"""
Atlas — live data synced from the main Haven control-room API.

Read:
  GET  /api/v1/atlas/summary       global totals for the masthead strip
  GET  /api/v1/atlas/sync/status   last sync run + current sync config

Write:
  POST /api/v1/atlas/sync          force a sync now (admin only)

Per-civ live figures are served by GET /api/v1/civilizations/{slug}/atlas
(see routes/civilizations.py) so the civ infobox can call a focused
endpoint. All numbers here are a cache of Haven's DB, refreshed by the
background job in app/services/haven_sync.py.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..config import get_settings
from ..deps import get_db, require_admin
from ..models.schemas import AtlasSummary, Envelope, SyncRunStatus
from ..services.haven_sync import sync_haven_atlas

router = APIRouter(prefix="/api/v1/atlas", tags=["atlas"])


def _last_run_status(db: Session) -> SyncRunStatus:
    settings = get_settings()
    row = db.execute(
        text(
            "SELECT source, started_at, finished_at, ok, communities_synced, error "
            "FROM haven_sync_run ORDER BY id DESC LIMIT 1"
        )
    ).first()
    return SyncRunStatus(
        source=row.source if row else None,
        started_at=row.started_at if row else None,
        finished_at=row.finished_at if row else None,
        ok=bool(row.ok) if row else None,
        communities_synced=row.communities_synced if row else None,
        error=row.error if row else None,
        enabled=settings.haven_sync_enabled,
        interval_minutes=settings.haven_sync_interval_min,
        api_base=settings.haven_api_base,
    )


@router.get("/summary", response_model=Envelope[AtlasSummary])
def atlas_summary(db: Session = Depends(get_db)):
    """Global atlas totals (systems / discoveries / communities /
    contributors), cached from Haven. Empty zeros until the first sync."""
    row = db.execute(
        text(
            "SELECT total_systems, total_discoveries, total_communities, "
            "total_contributors, synced_at FROM atlas_summary WHERE id = 1"
        )
    ).first()
    if not row:
        return Envelope(data=AtlasSummary())
    return Envelope(data=AtlasSummary(
        total_systems=row.total_systems,
        total_discoveries=row.total_discoveries,
        total_communities=row.total_communities,
        total_contributors=row.total_contributors,
        synced_at=row.synced_at,
    ))


@router.get("/sync/status", response_model=Envelope[SyncRunStatus])
def atlas_sync_status(db: Session = Depends(get_db)):
    """Last sync attempt + the live sync configuration. Public read so the
    home/admin UI can show 'synced N min ago' or a failure banner."""
    return Envelope(data=_last_run_status(db))


@router.post("/sync", response_model=Envelope[SyncRunStatus])
def atlas_sync_now(
    db: Session = Depends(get_db),
    _user: dict = Depends(require_admin),
):
    """Force a sync immediately. Admin only. Runs synchronously (a couple
    of seconds against a healthy Haven) and returns the resulting status."""
    sync_haven_atlas()
    return Envelope(data=_last_run_status(db))
