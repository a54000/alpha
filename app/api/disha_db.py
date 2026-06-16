"""Disha application table metadata used by the API facade and sync bridge."""

from __future__ import annotations

import sqlalchemy as sa


metadata = sa.MetaData()


disha_users = sa.Table(
    "disha_users",
    metadata,
    sa.Column("user_id", sa.Integer(), primary_key=True, autoincrement=True),
    sa.Column("email", sa.String(length=255), nullable=False),
    sa.Column("display_name", sa.String(length=120), nullable=False),
    sa.Column("role", sa.String(length=40), nullable=False, server_default="viewer"),
    sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("TRUE")),
    sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    sa.Column("updated_at", sa.DateTime(), nullable=True),
    sa.UniqueConstraint("email", name="uq_disha_users_email"),
)


disha_signals = sa.Table(
    "disha_signals",
    metadata,
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


disha_positions = sa.Table(
    "disha_positions",
    metadata,
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


disha_portfolio_snapshots = sa.Table(
    "disha_portfolio_snapshots",
    metadata,
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


disha_paper_events = sa.Table(
    "disha_paper_events",
    metadata,
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


disha_operator_audit = sa.Table(
    "disha_operator_audit",
    metadata,
    sa.Column("audit_id", sa.String(length=80), primary_key=True),
    sa.Column("event_time", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    sa.Column("action", sa.String(length=80), nullable=False),
    sa.Column("status", sa.String(length=40), nullable=False),
    sa.Column("confirmation_status", sa.String(length=40), nullable=True),
    sa.Column("source", sa.String(length=80), nullable=False, server_default="api"),
    sa.Column("summary", sa.Text(), nullable=False),
    sa.Column("raw_payload", sa.JSON(), nullable=False),
)


disha_paper_workflow_events = sa.Table(
    "disha_paper_workflow_events",
    metadata,
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


def create_disha_tables(engine: sa.Engine) -> None:
    """Create only the Disha application tables for tests/local bootstrap."""

    metadata.create_all(
        engine,
        tables=[
            disha_users,
            disha_signals,
            disha_positions,
            disha_portfolio_snapshots,
            disha_paper_events,
            disha_operator_audit,
            disha_paper_workflow_events,
        ],
    )
