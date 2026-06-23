"""haven atlas sync — live civ stats from the main Haven backend

Revision ID: 0005
Revises: 0004
Create Date: 2026-06-22

The unified-archive build: the Travelers Archive now pulls LIVE figures
from the main Haven control-room API (havenmap.online) so a civilization
page can show "Member systems / Discoveries / Contributors — live from the
atlas" instead of hand-typed numbers that rot.

This migration adds:
- `civilization.haven_tag` — explicit mapping from an archive civ to a
  Haven community discord_tag. Nullable; when unset the sync/read layer
  falls back to fuzzy name matching.
- `atlas_community_stat` — one cached row per Haven community, refreshed
  by the background sync job from GET /api/public/community-overview.
- `atlas_summary` — single-row global totals (systems/discoveries/
  communities/contributors) for the masthead "live" stat strip.
- `haven_sync_run` — a log of each sync attempt (ok/error/count) so the
  admin UI can show "last synced N min ago" and surface failures.

All data here is a CACHE of the main Haven DB — it is rebuilt on every
sync and is safe to wipe. No data is authored here.
"""

from typing import Sequence, Union

from alembic import op


revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- map archive civ -> Haven community tag (nullable) ------------
    op.execute("ALTER TABLE civilization ADD COLUMN haven_tag TEXT")
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_civ_haven_tag "
        "ON civilization(haven_tag) WHERE haven_tag IS NOT NULL"
    )

    # --- per-community cached atlas figures --------------------------
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS atlas_community_stat (
            tag                 TEXT PRIMARY KEY,   -- Haven discord_tag, verbatim
            tag_norm            TEXT NOT NULL,      -- lowercase-alphanumeric, for matching
            display_name        TEXT,
            total_systems       INTEGER NOT NULL DEFAULT 0,
            total_discoveries   INTEGER NOT NULL DEFAULT 0,
            unique_contributors INTEGER NOT NULL DEFAULT 0,
            manual_systems      INTEGER NOT NULL DEFAULT 0,
            extractor_systems   INTEGER NOT NULL DEFAULT 0,
            synced_at           TEXT NOT NULL
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_atlas_stat_norm "
        "ON atlas_community_stat(tag_norm)"
    )

    # --- single-row global totals ------------------------------------
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS atlas_summary (
            id                  INTEGER PRIMARY KEY CHECK (id = 1),
            total_systems       INTEGER NOT NULL DEFAULT 0,
            total_discoveries   INTEGER NOT NULL DEFAULT 0,
            total_communities   INTEGER NOT NULL DEFAULT 0,
            total_contributors  INTEGER NOT NULL DEFAULT 0,
            synced_at           TEXT NOT NULL
        )
        """
    )

    # --- sync run log ------------------------------------------------
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS haven_sync_run (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            source              TEXT NOT NULL,
            started_at          TEXT NOT NULL,
            finished_at         TEXT,
            ok                  INTEGER NOT NULL DEFAULT 0 CHECK (ok IN (0, 1)),
            communities_synced  INTEGER NOT NULL DEFAULT 0,
            error               TEXT
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_sync_run_started "
        "ON haven_sync_run(started_at DESC)"
    )


def downgrade() -> None:
    # SQLite can't easily DROP COLUMN before 3.35 and these tables are a
    # disposable cache — leave them in place on downgrade.
    op.execute("DROP TABLE IF EXISTS haven_sync_run")
    op.execute("DROP TABLE IF EXISTS atlas_summary")
    op.execute("DROP TABLE IF EXISTS atlas_community_stat")
