import os

import pytest

from db.connection import get_database_url


def test_get_database_url_requires_env(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(RuntimeError, match="DATABASE_URL is not set"):
        get_database_url()


def test_get_database_url_reads_env(monkeypatch):
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+psycopg2://surindersingh@localhost:5433/nse_research_platform",
    )
    assert get_database_url() == os.environ["DATABASE_URL"]
