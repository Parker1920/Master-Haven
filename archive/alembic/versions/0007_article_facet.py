"""article facets — structured, filterable attributes per catalogue article

Revision ID: 0007
Revises: 0006
Create Date: 2026-06-23

The catalogue's filter engine. Each authored section (Starships, Fauna,
Flora, Minerals, Civilizations, …) gets custom filters; this table stores
the structured, indexable values that power them.

One row per (article, facet key, value) so multi-select facets and fast
filtering both work — e.g. a fauna article with two genera and one
temperament is three rows. The per-namespace facet SCHEMA (which keys and
which option values each section offers) lives in code at app/facets.py;
this table just holds the chosen values.

Free-form `infobox_json` / `sources_json` on `article` stay as-is for
display extras; this table is the queryable layer underneath.
"""

from typing import Sequence, Union

from alembic import op


revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS article_facet (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            article_id  INTEGER NOT NULL REFERENCES article(id) ON DELETE CASCADE,
            key         TEXT NOT NULL,       -- facet key, e.g. 'genus', 'class', 'biome'
            value       TEXT NOT NULL        -- one selected value
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_article_facet_article ON article_facet(article_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_article_facet_kv ON article_facet(key, value)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS article_facet")
