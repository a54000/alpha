"""Database connection helpers."""

from __future__ import annotations

import os

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

_DATABASE_URL_ENV = "DATABASE_URL"
_DATABASE_URL_MESSAGE = (
    "DATABASE_URL is not set. Copy .env.example to .env and configure your PostgreSQL connection."
)


def load_dotenv() -> None:
    """Load environment variables from a local `.env` file when present."""

    try:
        from dotenv import load_dotenv as _load_dotenv
    except ImportError:
        return

    _load_dotenv()


def get_database_url() -> str:
    """Return the configured PostgreSQL connection URL."""

    load_dotenv()
    database_url = os.environ.get(_DATABASE_URL_ENV)
    if not database_url:
        raise RuntimeError(_DATABASE_URL_MESSAGE)
    return database_url


def build_engine(database_url: str | None = None) -> Engine:
    """Create a SQLAlchemy engine from an explicit URL or `DATABASE_URL`."""

    return create_engine(database_url or get_database_url(), future=True)
