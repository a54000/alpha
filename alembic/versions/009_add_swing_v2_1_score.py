"""Add Swing V2.1 score column."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None


def _has_column(inspector, table_name: str, column_name: str) -> bool:
    return column_name in {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _has_column(inspector, "daily_scores", "swing_v2_1_score"):
        op.add_column("daily_scores", sa.Column("swing_v2_1_score", sa.Numeric(5, 1), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _has_column(inspector, "daily_scores", "swing_v2_1_score"):
        op.drop_column("daily_scores", "swing_v2_1_score")
