"""Create Disha application tables.

Revision ID: 015
Revises: 014
Create Date: 2026-06-15
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "015"
down_revision = "014"
branch_labels = None
depends_on = None


def _has_table(inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _has_table(inspector, "disha_users"):
        op.create_table(
            "disha_users",
            sa.Column("user_id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("email", sa.String(length=255), nullable=False),
            sa.Column("display_name", sa.String(length=120), nullable=False),
            sa.Column("role", sa.String(length=40), nullable=False, server_default="viewer"),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("TRUE")),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.UniqueConstraint("email", name="uq_disha_users_email"),
        )

    if not _has_table(inspector, "disha_signals"):
        op.create_table(
            "disha_signals",
            sa.Column("signal_id", sa.String(length=80), primary_key=True),
            sa.Column("scan_date", sa.Date(), nullable=False),
            sa.Column("symbol", sa.String(length=40), nullable=False),
            sa.Column("sleeve", sa.String(length=40), nullable=False),
            sa.Column("signal_type", sa.String(length=40), nullable=False),
            sa.Column("entry_signal", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
            sa.Column("market_regime", sa.String(length=40), nullable=True),
            sa.Column("market_gate", sa.Boolean(), nullable=True),
            sa.Column("close_price", sa.Numeric(14, 4), nullable=True),
            sa.Column("source_file", sa.Text(), nullable=False),
            sa.Column("raw_payload", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.UniqueConstraint("scan_date", "symbol", "sleeve", "signal_type", name="uq_disha_signals_scan_symbol_sleeve_type"),
        )

    if not _has_table(inspector, "disha_positions"):
        op.create_table(
            "disha_positions",
            sa.Column("position_id", sa.String(length=80), primary_key=True),
            sa.Column("trade_id", sa.String(length=80), nullable=True),
            sa.Column("sleeve", sa.String(length=40), nullable=True),
            sa.Column("symbol", sa.String(length=40), nullable=False),
            sa.Column("entry_date", sa.Date(), nullable=True),
            sa.Column("entry_price", sa.Numeric(14, 4), nullable=True),
            sa.Column("shares", sa.Integer(), nullable=True),
            sa.Column("planned_exit_date", sa.Date(), nullable=True),
            sa.Column("stop_loss", sa.Numeric(14, 4), nullable=True),
            sa.Column("status", sa.String(length=40), nullable=False, server_default="OPEN"),
            sa.Column("exit_date", sa.Date(), nullable=True),
            sa.Column("exit_price", sa.Numeric(14, 4), nullable=True),
            sa.Column("pnl", sa.Numeric(14, 4), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("source_file", sa.Text(), nullable=False),
            sa.Column("raw_payload", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        )

    if not _has_table(inspector, "disha_portfolio_snapshots"):
        op.create_table(
            "disha_portfolio_snapshots",
            sa.Column("snapshot_id", sa.String(length=80), primary_key=True),
            sa.Column("snapshot_date", sa.Date(), nullable=True),
            sa.Column("sessions_logged", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("scanner_reconciliations", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("mf_sweep_events", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("fill_checks", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("open_positions_logged", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("ready", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
            sa.Column("source_file", sa.Text(), nullable=False),
            sa.Column("raw_payload", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        )

    if not _has_table(inspector, "disha_paper_events"):
        op.create_table(
            "disha_paper_events",
            sa.Column("event_id", sa.String(length=120), primary_key=True),
            sa.Column("event_date", sa.Date(), nullable=True),
            sa.Column("session", sa.Integer(), nullable=True),
            sa.Column("event_type", sa.String(length=60), nullable=False),
            sa.Column("symbol", sa.String(length=40), nullable=True),
            sa.Column("action", sa.String(length=80), nullable=True),
            sa.Column("status", sa.String(length=60), nullable=True),
            sa.Column("source_file", sa.Text(), nullable=False),
            sa.Column("raw_payload", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        )

    op.create_index("ix_disha_signals_scan_date", "disha_signals", ["scan_date"], if_not_exists=True)
    op.create_index("ix_disha_signals_symbol", "disha_signals", ["symbol"], if_not_exists=True)
    op.create_index("ix_disha_positions_symbol_status", "disha_positions", ["symbol", "status"], if_not_exists=True)
    op.create_index("ix_disha_paper_events_date_type", "disha_paper_events", ["event_date", "event_type"], if_not_exists=True)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _has_table(inspector, "disha_paper_events"):
        op.drop_index("ix_disha_paper_events_date_type", table_name="disha_paper_events", if_exists=True)
        op.drop_table("disha_paper_events")
    if _has_table(inspector, "disha_portfolio_snapshots"):
        op.drop_table("disha_portfolio_snapshots")
    if _has_table(inspector, "disha_positions"):
        op.drop_index("ix_disha_positions_symbol_status", table_name="disha_positions", if_exists=True)
        op.drop_table("disha_positions")
    if _has_table(inspector, "disha_signals"):
        op.drop_index("ix_disha_signals_symbol", table_name="disha_signals", if_exists=True)
        op.drop_index("ix_disha_signals_scan_date", table_name="disha_signals", if_exists=True)
        op.drop_table("disha_signals")
    if _has_table(inspector, "disha_users"):
        op.drop_table("disha_users")

