"""Add persisted breakout fields to features_daily."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def _has_column(inspector, table_name: str, column_name: str) -> bool:
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _has_column(inspector, "features_daily", "distance_from_52w_high"):
        op.add_column("features_daily", sa.Column("distance_from_52w_high", sa.Numeric(6, 2)))

    if not _has_column(inspector, "features_daily", "is_52w_breakout"):
        op.add_column("features_daily", sa.Column("is_52w_breakout", sa.Boolean()))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _has_column(inspector, "features_daily", "is_52w_breakout"):
        op.drop_column("features_daily", "is_52w_breakout")

    if _has_column(inspector, "features_daily", "distance_from_52w_high"):
        op.drop_column("features_daily", "distance_from_52w_high")
