"""Add daily pipeline step tracking fields.

Revision ID: 013
Revises: 012
Create Date: 2026-06-12
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "013"
down_revision = "012"
branch_labels = None
depends_on = None


def _has_column(inspector, table_name: str, column_name: str) -> bool:
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("pipeline_runs"):
        op.create_table(
            "pipeline_runs",
            sa.Column("run_id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("business_date", sa.Date(), nullable=False),
            sa.Column("step_name", sa.String(length=80), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False),
            sa.Column("started_at", sa.DateTime()),
            sa.Column("completed_at", sa.DateTime()),
            sa.Column("error_message", sa.Text()),
        )
    else:
        with op.batch_alter_table("pipeline_runs") as batch_op:
            if not _has_column(inspector, "pipeline_runs", "business_date"):
                batch_op.add_column(sa.Column("business_date", sa.Date()))
            if not _has_column(inspector, "pipeline_runs", "step_name"):
                batch_op.add_column(sa.Column("step_name", sa.String(length=80)))
            if not _has_column(inspector, "pipeline_runs", "started_at"):
                batch_op.add_column(sa.Column("started_at", sa.DateTime()))
            if not _has_column(inspector, "pipeline_runs", "completed_at"):
                batch_op.add_column(sa.Column("completed_at", sa.DateTime()))

        op.execute(
            """
            UPDATE pipeline_runs
               SET business_date = COALESCE(business_date, run_date),
                   step_name = COALESCE(step_name, job_name),
                   started_at = COALESCE(started_at, start_time),
                   completed_at = COALESCE(completed_at, end_time)
             WHERE business_date IS NULL
                OR step_name IS NULL
                OR started_at IS NULL
                OR completed_at IS NULL
            """
        )

    op.create_index(
        "uq_pipeline_runs_business_date_step_name",
        "pipeline_runs",
        ["business_date", "step_name"],
        unique=True,
        if_not_exists=True,
    )
    op.create_index(
        "ix_pipeline_runs_business_date_status",
        "pipeline_runs",
        ["business_date", "status"],
        if_not_exists=True,
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("pipeline_runs"):
        return
    op.drop_index("ix_pipeline_runs_business_date_status", table_name="pipeline_runs", if_exists=True)
    op.drop_index("uq_pipeline_runs_business_date_step_name", table_name="pipeline_runs", if_exists=True)
    with op.batch_alter_table("pipeline_runs") as batch_op:
        refreshed = sa.inspect(bind)
        if _has_column(refreshed, "pipeline_runs", "completed_at"):
            batch_op.drop_column("completed_at")
        if _has_column(refreshed, "pipeline_runs", "started_at"):
            batch_op.drop_column("started_at")
        if _has_column(refreshed, "pipeline_runs", "step_name"):
            batch_op.drop_column("step_name")
        if _has_column(refreshed, "pipeline_runs", "business_date"):
            batch_op.drop_column("business_date")
