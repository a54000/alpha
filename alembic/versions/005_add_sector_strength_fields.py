"""Add persisted sector strength fields to sector_daily."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def _has_column(inspector, table_name: str, column_name: str) -> bool:
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    additions = [
        ("return_1m", sa.Numeric(8, 4)),
        ("return_3m", sa.Numeric(8, 4)),
        ("return_6m", sa.Numeric(8, 4)),
        ("sector_score", sa.Numeric(8, 4)),
        ("sector_rank", sa.Integer()),
    ]
    for column_name, column_type in additions:
        if not _has_column(inspector, "sector_daily", column_name):
            op.add_column("sector_daily", sa.Column(column_name, column_type))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    for column_name in ["sector_rank", "sector_score", "return_6m", "return_3m", "return_1m"]:
        if _has_column(inspector, "sector_daily", column_name):
            op.drop_column("sector_daily", column_name)
