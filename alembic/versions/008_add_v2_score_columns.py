"""Add V2 score columns to daily_scores."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def _has_column(inspector, table_name: str, column_name: str) -> bool:
    return column_name in {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _has_column(inspector, "daily_scores", "swing_v2_score"):
        op.add_column("daily_scores", sa.Column("swing_v2_score", sa.Numeric(5, 1), nullable=True))
    if not _has_column(inspector, "daily_scores", "position_v2_score"):
        op.add_column("daily_scores", sa.Column("position_v2_score", sa.Numeric(5, 1), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _has_column(inspector, "daily_scores", "position_v2_score"):
        op.drop_column("daily_scores", "position_v2_score")
    if _has_column(inspector, "daily_scores", "swing_v2_score"):
        op.drop_column("daily_scores", "swing_v2_score")
