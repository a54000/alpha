"""Add index_prices_daily table for benchmark index data."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def _has_table(inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    
    if not _has_table(inspector, "index_prices_daily"):
        op.create_table(
            "index_prices_daily",
            sa.Column("index_name", sa.String(20), primary_key=True),
            sa.Column("date", sa.Date(), primary_key=True),
            sa.Column("open", sa.Numeric(12, 2), nullable=True),
            sa.Column("high", sa.Numeric(12, 2), nullable=True),
            sa.Column("low", sa.Numeric(12, 2), nullable=True),
            sa.Column("close", sa.Numeric(12, 2), nullable=True),
            sa.Column("volume", sa.Integer(), nullable=True),
            sa.UniqueConstraint("index_name", "date", name="uq_index_prices_daily_index_date"),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    
    if _has_table(inspector, "index_prices_daily"):
        op.drop_table("index_prices_daily")
