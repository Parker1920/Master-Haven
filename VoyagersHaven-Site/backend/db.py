"""SQLite connection + one-time schema initialization.

Paths come from the environment (set by docker-compose) with local-dev
fallbacks so the app behaves identically inside the container and on a desktop.

  DATA_DIR  base data directory   (container: /data)
  DB_PATH   sqlite file           (default: {DATA_DIR}/voyagers_haven.db)

The data dir lives OUTSIDE the repo on the host so `git pull` and container
rebuilds never touch the SQLite DB (same pattern as Haven Control Room and
Grand Festival).
"""

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


def _resolve_data_dir() -> Path:
    # Container sets DATA_DIR=/data. Local dev falls back to a gitignored folder.
    return Path(os.environ.get("DATA_DIR") or (BASE_DIR.parent / "data-local"))


DATA_DIR = _resolve_data_dir()
DB_PATH = Path(os.environ.get("DB_PATH") or (DATA_DIR / "voyagers_haven.db"))
SCHEMA_PATH = BASE_DIR / "schema.sql"


def ensure_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


@contextmanager
def db_conn():
    """Context-managed connection: commits on success, rolls back on error."""
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_db():
    """FastAPI dependency. Yields a connection, commits on a clean return."""
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _ensure_columns(conn) -> None:
    """Add columns introduced after a DB was first created (CREATE TABLE IF NOT
    EXISTS won't alter an existing table). Idempotent."""
    pay_cols = {row[1] for row in conn.execute("PRAGMA table_info(payments)").fetchall()}
    if "item_label" not in pay_cols:
        # For merch payments: a human label like "Cartographer Tee ×2".
        conn.execute("ALTER TABLE payments ADD COLUMN item_label TEXT")
    inv_cols = {row[1] for row in conn.execute("PRAGMA table_info(invoices)").fetchall()}
    if "inquiry_id" not in inv_cols:
        # Links an invoice back to the "Start a project" inquiry it came from, so
        # the admin can trace one lead: inquiry -> invoice -> receipt, end to end.
        conn.execute("ALTER TABLE invoices ADD COLUMN inquiry_id INTEGER")
    if "receipt_url" not in inv_cols:
        # Stripe receipt URL, captured on payment (live mode) for the "receipt" link.
        conn.execute("ALTER TABLE invoices ADD COLUMN receipt_url TEXT")


def _seed_sample_products(conn) -> None:
    """Seed a few placeholder products the first time so the shop isn't empty
    while iterating on layout. Real products are managed from the admin console.
    Skipped in live mode so the production shop starts empty (no fake products)."""
    if os.environ.get("STRIPE_MODE", "simulated").strip().lower() == "live":
        return
    count = conn.execute("SELECT COUNT(*) AS c FROM products").fetchone()["c"]
    if count:
        return
    samples = [
        ("Cartographer Tee", "Soft cotton tee with the cosmic-compass mark. Chart the galaxy in style.", 2800, 1, 1, 10),
        ("Voyager Sticker Pack", "Six die-cut vinyl stickers — glyphs, the compass, and the wordmark.", 900, 1, 1, 20),
        ("Cosmic Compass Enamel Pin", "Hard-enamel pin of the Voyager's Haven mark. Teal on black nickel.", 1200, 1, 1, 30),
        ("Haven Supporter — Digital Badge", "A thank-you digital badge + wallpaper pack. No shipping.", 500, 1, 0, 40),
    ]
    conn.executemany(
        """INSERT INTO products (name, description, price_cents, active, requires_shipping, sort_order)
           VALUES (?, ?, ?, ?, ?, ?)""",
        samples,
    )


def init_db() -> None:
    """Run schema (idempotent) on boot, backfill columns, seed sample products."""
    ensure_dirs()
    schema = SCHEMA_PATH.read_text(encoding="utf-8")
    with db_conn() as conn:
        conn.executescript(schema)
        _ensure_columns(conn)
        _seed_sample_products(conn)
