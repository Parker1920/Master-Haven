"""Apply versioned .sql migrations in filename order. No Alembic.

Each migration file (migrations/NNN_description.sql) runs inside ONE
transaction together with its schema_version row, so a failed migration
leaves nothing behind — the version row and the schema change commit or
roll back as a unit. A file is never applied twice and never edited after
it has shipped; fixes are new files.

Run manually:   python -m app.migrate
Also runs automatically at app startup (main.py lifespan).
"""
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .config import settings

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"


def connect(db_path: Path) -> sqlite3.Connection:
    """Raw sqlite3 connection with the non-negotiable pragmas.

    isolation_level=None = autocommit; migrate/seed manage their own
    BEGIN/COMMIT explicitly.
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.isolation_level = None
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def run_migrations(db_path: Path | None = None) -> list[str]:
    """Apply every migration not yet recorded in schema_version."""
    conn = connect(db_path or settings.db_path)
    applied_now: list[str] = []
    try:
        # Bootstrap the tracking table (001_init.sql declares it IF NOT EXISTS
        # too, purely so the schema file reads complete).
        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_version "
            "(version TEXT PRIMARY KEY, applied_at TEXT NOT NULL)"
        )
        done = {row[0] for row in conn.execute("SELECT version FROM schema_version")}

        for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
            if path.name in done:
                continue
            sql = path.read_text(encoding="utf-8")
            try:
                # BEGIN with no COMMIT in the script leaves the transaction
                # open, so the version row below lands atomically with the
                # migration itself.
                conn.executescript("BEGIN;\n" + sql)
                conn.execute(
                    "INSERT INTO schema_version (version, applied_at) VALUES (?, ?)",
                    (path.name, datetime.now(timezone.utc).isoformat(timespec="seconds")),
                )
                conn.execute("COMMIT")
            except Exception:
                conn.execute("ROLLBACK")
                print(f"[migrate] FAILED {path.name} — rolled back")
                raise
            applied_now.append(path.name)
            print(f"[migrate] applied {path.name}")

        if not applied_now:
            print("[migrate] up to date")
        return applied_now
    finally:
        conn.close()


if __name__ == "__main__":
    run_migrations()
