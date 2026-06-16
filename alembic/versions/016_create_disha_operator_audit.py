"""Create Disha operator audit table.

Revision ID: 016
Revises: 015
Create Date: 2026-06-15
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "016"
down_revision = "015"
branch_labels = None
depends_on = None


def _has_table(inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _has_table(inspector, "disha_operator_audit"):
        op.create_table(
            "disha_operator_audit",
            sa.Column("audit_id", sa.String(length=80), primary_key=True),
            sa.Column("event_time", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("action", sa.String(length=80), nullable=False),
            sa.Column("status", sa.String(length=40), nullable=False),
            sa.Column("confirmation_status", sa.String(length=40), nullable=True),
            sa.Column("source", sa.String(length=80), nullable=False, server_default="api"),
            sa.Column("summary", sa.Text(), nullable=False),
            sa.Column("raw_payload", sa.JSON(), nullable=False),
        )

    op.create_index("ix_disha_operator_audit_time", "disha_operator_audit", ["event_time"], if_not_exists=True)
    op.create_index("ix_disha_operator_audit_action_status", "disha_operator_audit", ["action", "status"], if_not_exists=True)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _has_table(inspector, "disha_operator_audit"):
        op.drop_index("ix_disha_operator_audit_action_status", table_name="disha_operator_audit", if_exists=True)
        op.drop_index("ix_disha_operator_audit_time", table_name="disha_operator_audit", if_exists=True)
        op.drop_table("disha_operator_audit")
