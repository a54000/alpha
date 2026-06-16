"""Add model_version_id to recommendation_history."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def _has_column(inspector, table_name: str, column_name: str) -> bool:
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not _has_column(inspector, "recommendation_history", "model_version_id"):
        op.add_column(
            "recommendation_history",
            sa.Column("model_version_id", sa.Integer()),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if _has_column(inspector, "recommendation_history", "model_version_id"):
        op.drop_column("recommendation_history", "model_version_id")
