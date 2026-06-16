"""Create security alias and lineage tables."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "011"
down_revision = "010"
branch_labels = None
depends_on = None


ALIAS_SOURCES = ("research", "angel", "nse", "yfinance", "manual")
ALIAS_REASONS = (
    "exact",
    "rename",
    "vendor_format",
    "merger",
    "demerger",
    "delisting",
    "listing",
    "manual_override",
    "unknown",
)
CONFIDENCE_VALUES = ("pending", "low", "medium", "high", "approved", "rejected")
REVIEW_STATUS_VALUES = ("pending", "approved", "rejected", "needs_review", "pending_dates")
EVENT_TYPES = (
    "rename",
    "merger",
    "demerger",
    "acquisition",
    "delisting",
    "suspension",
    "share_class_change",
    "listing",
    "unknown",
)


def _has_table(inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _has_table(inspector, "security_symbol_alias"):
        op.create_table(
            "security_symbol_alias",
            sa.Column("alias_id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("security_id", sa.Integer(), sa.ForeignKey("security_master.security_id"), nullable=False),
            sa.Column("source", sa.String(length=30), nullable=False),
            sa.Column("symbol", sa.String(length=40), nullable=False),
            sa.Column("normalized_symbol", sa.String(length=40), nullable=False),
            sa.Column("valid_from", sa.Date(), nullable=True),
            sa.Column("valid_to", sa.Date(), nullable=True),
            sa.Column("is_primary_for_source", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("alias_reason", sa.String(length=40), nullable=False),
            sa.Column("confidence", sa.String(length=20), nullable=False, server_default="pending"),
            sa.Column("review_status", sa.String(length=30), nullable=False, server_default="pending"),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.UniqueConstraint("source", "symbol", "valid_from", name="uq_security_symbol_alias_source_symbol_from"),
            sa.CheckConstraint(f"source IN {ALIAS_SOURCES}", name="ck_security_symbol_alias_source"),
            sa.CheckConstraint(f"alias_reason IN {ALIAS_REASONS}", name="ck_security_symbol_alias_reason"),
            sa.CheckConstraint(f"confidence IN {CONFIDENCE_VALUES}", name="ck_security_symbol_alias_confidence"),
            sa.CheckConstraint(f"review_status IN {REVIEW_STATUS_VALUES}", name="ck_security_symbol_alias_review_status"),
            sa.CheckConstraint(
                "valid_to IS NULL OR valid_from IS NULL OR valid_to >= valid_from",
                name="ck_security_symbol_alias_date_order",
            ),
        )

    if not _has_table(inspector, "security_corporate_action_lineage"):
        op.create_table(
            "security_corporate_action_lineage",
            sa.Column("event_id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("event_date", sa.Date(), nullable=True),
            sa.Column("event_type", sa.String(length=40), nullable=False),
            sa.Column("from_security_id", sa.Integer(), sa.ForeignKey("security_master.security_id"), nullable=True),
            sa.Column("to_security_id", sa.Integer(), sa.ForeignKey("security_master.security_id"), nullable=True),
            sa.Column("ratio", sa.Numeric(18, 8), nullable=True),
            sa.Column("source_reference", sa.Text(), nullable=True),
            sa.Column("review_status", sa.String(length=30), nullable=False, server_default="pending"),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.CheckConstraint(f"event_type IN {EVENT_TYPES}", name="ck_security_lineage_event_type"),
            sa.CheckConstraint(f"review_status IN {REVIEW_STATUS_VALUES}", name="ck_security_lineage_review_status"),
            sa.CheckConstraint(
                "from_security_id IS NOT NULL OR to_security_id IS NOT NULL",
                name="ck_security_lineage_has_security",
            ),
        )

    op.create_index(
        "ix_security_symbol_alias_source_symbol",
        "security_symbol_alias",
        ["source", "symbol"],
        if_not_exists=True,
    )
    op.create_index(
        "ix_security_symbol_alias_security_dates",
        "security_symbol_alias",
        ["security_id", "valid_from", "valid_to"],
        if_not_exists=True,
    )
    op.create_index(
        "ix_security_symbol_alias_normalized_symbol",
        "security_symbol_alias",
        ["normalized_symbol"],
        if_not_exists=True,
    )
    op.create_index(
        "ix_security_symbol_alias_review_status",
        "security_symbol_alias",
        ["review_status"],
        if_not_exists=True,
    )
    op.create_index(
        "ix_security_lineage_event_date",
        "security_corporate_action_lineage",
        ["event_date"],
        if_not_exists=True,
    )
    op.create_index(
        "ix_security_lineage_from_security_id",
        "security_corporate_action_lineage",
        ["from_security_id"],
        if_not_exists=True,
    )
    op.create_index(
        "ix_security_lineage_to_security_id",
        "security_corporate_action_lineage",
        ["to_security_id"],
        if_not_exists=True,
    )
    op.create_index(
        "ix_security_lineage_review_status",
        "security_corporate_action_lineage",
        ["review_status"],
        if_not_exists=True,
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _has_table(inspector, "security_corporate_action_lineage"):
        op.drop_index("ix_security_lineage_review_status", table_name="security_corporate_action_lineage", if_exists=True)
        op.drop_index("ix_security_lineage_to_security_id", table_name="security_corporate_action_lineage", if_exists=True)
        op.drop_index("ix_security_lineage_from_security_id", table_name="security_corporate_action_lineage", if_exists=True)
        op.drop_index("ix_security_lineage_event_date", table_name="security_corporate_action_lineage", if_exists=True)
        op.drop_table("security_corporate_action_lineage")

    if _has_table(inspector, "security_symbol_alias"):
        op.drop_index("ix_security_symbol_alias_review_status", table_name="security_symbol_alias", if_exists=True)
        op.drop_index("ix_security_symbol_alias_normalized_symbol", table_name="security_symbol_alias", if_exists=True)
        op.drop_index("ix_security_symbol_alias_security_dates", table_name="security_symbol_alias", if_exists=True)
        op.drop_index("ix_security_symbol_alias_source_symbol", table_name="security_symbol_alias", if_exists=True)
        op.drop_table("security_symbol_alias")
