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


def init_db() -> None:
    """Run schema (idempotent) on boot."""
    ensure_dirs()
    schema = SCHEMA_PATH.read_text(encoding="utf-8")
    with db_conn() as conn:
        conn.executescript(schema)
