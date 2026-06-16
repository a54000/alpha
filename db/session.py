"""Session helpers for the database layer."""

from __future__ import annotations

from sqlalchemy.orm import Session, sessionmaker

from db.connection import build_engine, get_database_url


def build_session_factory(database_url: str | None = None) -> sessionmaker[Session]:
    """Create a SQLAlchemy session factory bound to PostgreSQL."""

    engine = build_engine(database_url)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


__all__ = ["build_session_factory", "get_database_url"]
