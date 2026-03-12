"""
Travelers Exchange — Database Engine & Session Management
"""

import os
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings


# Ensure the parent directory for the database file exists
os.makedirs(os.path.dirname(settings.DB_PATH) or ".", exist_ok=True)

# SQLite engine with check_same_thread disabled for FastAPI's async context
engine = create_engine(
    f"sqlite:///{settings.DB_PATH}",
    connect_args={"check_same_thread": False},
    echo=False,
)

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """SQLAlchemy 2.0 declarative base for all ORM models."""
    pass


def init_db() -> None:
    """Create all tables defined by models that inherit from Base.

    This must be called AFTER all model modules have been imported so that
    Base.metadata is fully populated.
    """
    Base.metadata.create_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that provides a database session.

    Yields a SQLAlchemy Session and ensures it is closed after the request,
    even if an exception occurs.

    Usage:
        @app.get("/example")
        def example(db: Session = Depends(get_db)):
            ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
