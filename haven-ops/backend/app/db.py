"""SQLite engine (WAL) + session factory.

Every connection gets, non-negotiably:
  PRAGMA journal_mode=WAL   -- readers don't block during writes
  PRAGMA busy_timeout=5000  -- wait out a locked db instead of failing instantly
  PRAGMA foreign_keys=ON    -- SQLite defaults FKs OFF per-connection; an FK-off
                               connection is exactly how Haven-UI accumulated
                               years of orphaned rows. Never omit this.
"""
from sqlalchemy import event
from sqlmodel import Session, create_engine

from .config import settings

# The data dir must exist before SQLite can create the db file in it.
settings.data_dir.mkdir(parents=True, exist_ok=True)
settings.upload_dir.mkdir(parents=True, exist_ok=True)

engine = create_engine(
    f"sqlite:///{settings.db_path}",
    connect_args={"check_same_thread": False},
)


@event.listens_for(engine, "connect")
def _set_sqlite_pragmas(dbapi_conn, _record) -> None:
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA journal_mode=WAL")
    cur.execute("PRAGMA busy_timeout=5000")
    cur.execute("PRAGMA foreign_keys=ON")
    cur.close()


def get_session():
    """FastAPI dependency: yields a SQLModel session per request."""
    with Session(engine) as session:
        yield session
