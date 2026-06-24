"""article catalogue — generic namespaced wiki entity

Revision ID: 0006
Revises: 0005
Create Date: 2026-06-23

The "merge" build: the Travelers Archive gains a wiki CATALOGUE on top of
the existing newsroom / civ-history / inquisition surfaces. This adds the
one thing the app was missing — a generic, namespaced article entity that
powers browse-by-category, the Live/Overview/Sources infobox, the inline
source-quality badges, and the no-markup create/edit flow from the v0.3
design.

One new table: `article`. It backs every authored namespace —
  traveler, creature, ship, tool, base, event, lore, guide, mechanic, item.
Civilizations keep their own richer `civilization` table (rich page + the
live-atlas infobox); the system/planet namespaces are sourced from the
live Haven atlas in a later phase and are never hand-authored here.

Self-contained on purpose: each article carries its infobox rows and its
source list as JSON on the row (`infobox_json` / `sources_json`). That
keeps the catalogue from having to touch the existing
entity_revision / source_citation / watchlist CHECK constraints, so this
migration is a single additive CREATE TABLE with zero rebuild risk.
"""

from typing import Sequence, Union

from alembic import op


revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS article (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            namespace     TEXT NOT NULL,           -- traveler/creature/ship/tool/base/event/lore/guide/mechanic/item
            slug          TEXT NOT NULL UNIQUE,
            title         TEXT NOT NULL,
            subtitle      TEXT,                     -- one-line summary shown under the title
            body          TEXT NOT NULL DEFAULT '', -- markdown
            infobox_json  TEXT,                     -- JSON list of {label, value} — the Overview tab
            sources_json  TEXT,                     -- JSON list of {quality, text, url?} — the Sources tab + badges
            civ_slug      TEXT,                     -- optional cross-link to a civilization
            status        TEXT NOT NULL DEFAULT 'published'
                          CHECK (status IN ('published', 'draft')),
            created_by    INTEGER REFERENCES archive_user(id),
            created_at    TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at    TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            deleted_at    TEXT
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_article_namespace "
        "ON article(namespace) WHERE deleted_at IS NULL"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_article_slug "
        "ON article(slug) WHERE deleted_at IS NULL"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_article_civ "
        "ON article(civ_slug) WHERE deleted_at IS NULL"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS article")
