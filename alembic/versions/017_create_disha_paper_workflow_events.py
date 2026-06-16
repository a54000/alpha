"""Create Disha paper workflow events table.

Revision ID: 017
Revises: 016
Create Date: 2026-06-15
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "017"
down_revision = "016"
branch_labels = None
depends_on = None


def _has_table(inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _has_table(inspector, "disha_paper_workflow_events"):
        op.create_table(
            "disha_paper_workflow_events",
            sa.Column("workflow_event_id", sa.String(length=80), primary_key=True),
            sa.Column("event_time", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("session", sa.Integer(), nullable=False),
            sa.Column("event_date", sa.Date(), nullable=False),
            sa.Column("workflow_type", sa.String(length=60), nullable=False),
            sa.Column("status", sa.String(length=40), nullable=False),
            sa.Column("symbol", sa.String(length=40), nullable=True),
            sa.Column("notes", sa.Text(), nullable=False),
            sa.Column("raw_payload", sa.JSON(), nullable=False),
        )

    op.create_index("ix_disha_paper_workflow_events_date", "disha_paper_workflow_events", ["event_date"], if_not_exists=True)
    op.create_index("ix_disha_paper_workflow_events_type", "disha_paper_workflow_events", ["workflow_type", "status"], if_not_exists=True)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _has_table(inspector, "disha_paper_workflow_events"):
        op.drop_index("ix_disha_paper_workflow_events_type", table_name="disha_paper_workflow_events", if_exists=True)
        op.drop_index("ix_disha_paper_workflow_events_date", table_name="disha_paper_workflow_events", if_exists=True)
        op.drop_table("disha_paper_workflow_events")
