"""Configure TimescaleDB hypertables for large time-series tables."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


TIME_SERIES_TABLES = [
    "prices_daily",
    "features_daily",
    "daily_scores",
    "recommendation_history",
    "sector_daily",
]


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    try:
        bind.execution_options(isolation_level="AUTOCOMMIT").exec_driver_sql(
            "CREATE EXTENSION IF NOT EXISTS timescaledb"
        )
    except Exception:
        return
    for table_name in TIME_SERIES_TABLES:
        op.execute(sa.text(f"SELECT create_hypertable('{table_name}', 'date', if_not_exists => TRUE)"))


def downgrade() -> None:
    return
