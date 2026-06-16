"""Create security master table."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None


STATUS_VALUES = ("active", "suspended", "delisted", "merged", "renamed", "demerged", "unknown")
REVIEW_STATUS_VALUES = ("pending", "approved", "rejected", "needs_review")


def _has_table(inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _has_table(inspector, "security_master"):
        op.create_table(
            "security_master",
            sa.Column("security_id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("canonical_symbol", sa.String(length=40), nullable=False),
            sa.Column("canonical_name", sa.Text(), nullable=True),
            sa.Column("isin_current", sa.String(length=20), nullable=True),
            sa.Column("exchange", sa.String(length=20), nullable=False, server_default="NSE"),
            sa.Column("instrument_type", sa.String(length=30), nullable=False, server_default="equity"),
            sa.Column("status", sa.String(length=30), nullable=False, server_default="active"),
            sa.Column("first_seen_date", sa.Date(), nullable=True),
            sa.Column("last_seen_date", sa.Date(), nullable=True),
            sa.Column("created_from_source", sa.String(length=50), nullable=True),
            sa.Column("review_status", sa.String(length=30), nullable=False, server_default="pending"),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.CheckConstraint(
                f"status IN {STATUS_VALUES}",
                name="ck_security_master_status",
            ),
            sa.CheckConstraint(
                f"review_status IN {REVIEW_STATUS_VALUES}",
                name="ck_security_master_review_status",
            ),
            sa.CheckConstraint(
                "last_seen_date IS NULL OR first_seen_date IS NULL OR last_seen_date >= first_seen_date",
                name="ck_security_master_seen_date_order",
            ),
        )

    op.create_index(
        "ix_security_master_canonical_symbol",
        "security_master",
        ["canonical_symbol"],
        unique=False,
        if_not_exists=True,
    )
    op.create_index(
        "ix_security_master_status",
        "security_master",
        ["status"],
        unique=False,
        if_not_exists=True,
    )
    op.create_index(
        "ix_security_master_review_status",
        "security_master",
        ["review_status"],
        unique=False,
        if_not_exists=True,
    )
    op.create_index(
        "uq_security_master_exchange_isin_current",
        "security_master",
        ["exchange", "isin_current"],
        unique=True,
        if_not_exists=True,
        postgresql_where=sa.text("isin_current IS NOT NULL"),
        sqlite_where=sa.text("isin_current IS NOT NULL"),
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _has_table(inspector, "security_master"):
        op.drop_index("uq_security_master_exchange_isin_current", table_name="security_master", if_exists=True)
        op.drop_index("ix_security_master_review_status", table_name="security_master", if_exists=True)
        op.drop_index("ix_security_master_status", table_name="security_master", if_exists=True)
        op.drop_index("ix_security_master_canonical_symbol", table_name="security_master", if_exists=True)
        op.drop_table("security_master")
