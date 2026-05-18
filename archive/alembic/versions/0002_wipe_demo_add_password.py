"""wipe demo content + add password_hash column

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-18

Two things in this migration:

1. **Delete all Phase 2 demo content.** Identified by:
   - archive_user.discord_id LIKE 'seed-%' (the 8 personas)
   - civilization.slug IN (the 10 demo slugs)
   - story.slug IN (the 9 demo slugs)
   - inquisition.numeral IN ('XLV', 'XLVI', 'XLVII')
   Also cascades to story_civilization, inquisition_author,
   inquisition_civilization, draft, draft_coauthor, draft_civilization,
   draft_comment, notification, watchlist, entity_revision, audit_log
   rows that reference these IDs.

   Any real content created by users (post Phase 5a deploy) has different
   discord_ids/slugs and is preserved.

2. **Add archive_user.password_hash column.** Nullable. Set by
   `POST /api/v1/auth/set-password`. Required for any user with
   is_admin=1 or is_editor=1 before they can perform privileged
   actions (enforced in app/deps.py).

This migration is idempotent — running it twice deletes nothing the
second time (the rows are already gone), and `ADD COLUMN IF NOT EXISTS`
semantics are emulated by checking PRAGMA before adding.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Slugs/numerals identifying Phase 2 demo content. Hard-coded because
# we know exactly what was seeded — see archive/app/seed.py for the
# canonical lists. Keeping them inline avoids importing app code from
# inside a migration (which alembic runs in a stripped context).
DEMO_CIV_SLUGS = [
    "galactic-hub", "voyagers-haven", "eyfert-khannate", "fas",
    "atlas-foundation", "hadsh", "lazarus", "hub-cartographers",
    "old-travelers-guild", "the-archivist",
]
DEMO_STORY_SLUGS = [
    "haven-keeper-postal", "hub-restructure", "atlas-gathering",
    "khannate-fas-trade", "quicksilver-skirmish-3", "hadsh-v3",
    "haven-feature", "keeper-retold", "why-hub-waited",
]
DEMO_INQ_NUMERALS = ["XLV", "XLVI", "XLVII"]


def _quoted_list(values: list[str]) -> str:
    """Build a SQL list literal: ['a','b'] -> "'a','b'"."""
    return ",".join(f"'{v}'" for v in values)


def upgrade() -> None:
    # --- delete demo content --------------------------------------
    # FK cascades handle most of the dependent rows (per the schema's
    # ON DELETE CASCADE on draft_*, story_civilization, etc.). We do
    # the parent deletes in dependency-safe order: comments/votes →
    # children → top-level rows.

    civ_list = _quoted_list(DEMO_CIV_SLUGS)
    story_list = _quoted_list(DEMO_STORY_SLUGS)
    inq_list = _quoted_list(DEMO_INQ_NUMERALS)

    # Drafts published from demo (none should exist, but defensive)
    op.execute("DELETE FROM draft_comment WHERE draft_id IN ("
               "  SELECT id FROM draft WHERE author_id IN ("
               "    SELECT id FROM archive_user WHERE discord_id LIKE 'seed-%'"
               "  )"
               ")")
    op.execute("DELETE FROM draft_coauthor WHERE user_id IN ("
               "  SELECT id FROM archive_user WHERE discord_id LIKE 'seed-%'"
               ")")
    op.execute("DELETE FROM draft_civilization WHERE draft_id IN ("
               "  SELECT id FROM draft WHERE author_id IN ("
               "    SELECT id FROM archive_user WHERE discord_id LIKE 'seed-%'"
               "  )"
               ")")
    op.execute("DELETE FROM draft WHERE author_id IN ("
               "  SELECT id FROM archive_user WHERE discord_id LIKE 'seed-%'"
               ")")

    # Stories tagged with demo civs / authored by demo users
    op.execute("DELETE FROM story_civilization WHERE story_id IN ("
               f"  SELECT id FROM story WHERE slug IN ({story_list})"
               ")")
    op.execute(f"DELETE FROM story WHERE slug IN ({story_list})")

    # Inquisitions
    op.execute("DELETE FROM inquisition_author WHERE inquisition_id IN ("
               f"  SELECT id FROM inquisition WHERE numeral IN ({inq_list})"
               ")")
    op.execute("DELETE FROM inquisition_civilization WHERE inquisition_id IN ("
               f"  SELECT id FROM inquisition WHERE numeral IN ({inq_list})"
               ")")
    op.execute(f"DELETE FROM inquisition WHERE numeral IN ({inq_list})")

    # Civilizations
    op.execute(f"DELETE FROM civilization WHERE slug IN ({civ_list})")

    # Demo personas (8 archive_user rows)
    # Cascades: notifications, watchlist, audit_log (no FK cascade on
    # these — they reference archive_user but it's a soft ref). Drop
    # those first so SET NULL on FKs doesn't leave dangling pointers.
    op.execute("DELETE FROM notification WHERE user_id IN ("
               "  SELECT id FROM archive_user WHERE discord_id LIKE 'seed-%'"
               ")")
    op.execute("DELETE FROM watchlist WHERE user_id IN ("
               "  SELECT id FROM archive_user WHERE discord_id LIKE 'seed-%'"
               ")")
    op.execute("DELETE FROM audit_log WHERE user_id IN ("
               "  SELECT id FROM archive_user WHERE discord_id LIKE 'seed-%'"
               ")")
    op.execute("DELETE FROM entity_revision WHERE changed_by_id IN ("
               "  SELECT id FROM archive_user WHERE discord_id LIKE 'seed-%'"
               ")")
    op.execute("DELETE FROM archive_user WHERE discord_id LIKE 'seed-%'")

    # --- add password_hash column ---------------------------------
    # SQLite doesn't support ADD COLUMN IF NOT EXISTS directly; we
    # introspect first so re-running this migration on a DB that
    # already has the column doesn't crash.
    bind = op.get_bind()
    cols = [r[1] for r in bind.execute(sa.text("PRAGMA table_info(archive_user)")).fetchall()]
    if "password_hash" not in cols:
        op.execute("ALTER TABLE archive_user ADD COLUMN password_hash TEXT")


def downgrade() -> None:
    # Not supported. Re-seeding the demo data is `python -m app.seed`
    # with ARCHIVE_SEED=demo set. The password_hash column stays.
    pass
