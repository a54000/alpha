"""Create recommendation decision journal.

Revision ID: 014
Revises: 013
Create Date: 2026-06-12
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "014"
down_revision = "013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("recommendation_decision_journal"):
        op.create_table(
            "recommendation_decision_journal",
            sa.Column("journal_id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("business_date", sa.Date(), nullable=False),
            sa.Column("symbol", sa.String(length=40), nullable=False),
            sa.Column("rank", sa.Integer(), nullable=False),
            sa.Column("score", sa.Numeric(10, 4)),
            sa.Column("recommendation_type", sa.String(length=40), nullable=False),
            sa.Column("sector", sa.String(length=80)),
            sa.Column("feature_snapshot_json", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.UniqueConstraint(
                "business_date",
                "symbol",
                "recommendation_type",
                name="uq_recommendation_decision_journal_date_symbol_type",
            ),
        )
    op.create_index(
        "ix_recommendation_decision_journal_symbol_date",
        "recommendation_decision_journal",
        ["symbol", "business_date"],
        if_not_exists=True,
    )
    op.create_index(
        "ix_recommendation_decision_journal_date_rank",
        "recommendation_decision_journal",
        ["business_date", "rank"],
        if_not_exists=True,
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table("recommendation_decision_journal"):
        op.drop_index("ix_recommendation_decision_journal_date_rank", table_name="recommendation_decision_journal", if_exists=True)
        op.drop_index("ix_recommendation_decision_journal_symbol_date", table_name="recommendation_decision_journal", if_exists=True)
        op.drop_table("recommendation_decision_journal")
