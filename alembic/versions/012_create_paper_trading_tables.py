"""Create paper trading tables."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "012"
down_revision = "011"
branch_labels = None
depends_on = None


def _has_table(inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _has_table(inspector, "paper_portfolios"):
        op.create_table(
            "paper_portfolios",
            sa.Column("portfolio_id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("name", sa.String(length=80), nullable=False),
            sa.Column("strategy", sa.String(length=40), nullable=False),
            sa.Column("portfolio_size", sa.Integer(), nullable=False),
            sa.Column("initial_capital", sa.Numeric(14, 2), nullable=False),
            sa.Column("cash", sa.Numeric(14, 2), nullable=False),
            sa.Column("current_nav", sa.Numeric(14, 2), nullable=False),
            sa.Column("benchmark_symbol", sa.String(length=40), nullable=True),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.CheckConstraint("portfolio_size > 0", name="ck_paper_portfolios_size_positive"),
            sa.CheckConstraint("initial_capital > 0", name="ck_paper_portfolios_initial_capital_positive"),
            sa.CheckConstraint("cash >= 0", name="ck_paper_portfolios_cash_nonnegative"),
        )

    if not _has_table(inspector, "paper_positions"):
        op.create_table(
            "paper_positions",
            sa.Column("position_id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("portfolio_id", sa.Integer(), sa.ForeignKey("paper_portfolios.portfolio_id"), nullable=False),
            sa.Column("symbol", sa.String(length=20), sa.ForeignKey("symbol_master.symbol"), nullable=False),
            sa.Column("sector", sa.String(length=50), nullable=True),
            sa.Column("signal_date", sa.Date(), nullable=True),
            sa.Column("recommendation_rank", sa.Integer(), nullable=True),
            sa.Column("recommendation_score", sa.Numeric(8, 4), nullable=True),
            sa.Column("entry_date", sa.Date(), nullable=False),
            sa.Column("entry_price", sa.Numeric(12, 4), nullable=False),
            sa.Column("quantity", sa.Numeric(18, 8), nullable=False),
            sa.Column("capital_allocated", sa.Numeric(14, 2), nullable=False),
            sa.Column("current_price", sa.Numeric(12, 4), nullable=True),
            sa.Column("market_value", sa.Numeric(14, 2), nullable=True),
            sa.Column("unrealized_pnl", sa.Numeric(14, 2), nullable=True),
            sa.Column("planned_exit_date", sa.Date(), nullable=True),
            sa.Column("exit_date", sa.Date(), nullable=True),
            sa.Column("exit_price", sa.Numeric(12, 4), nullable=True),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="open"),
            sa.Column("fees", sa.Numeric(12, 4), nullable=False, server_default="0"),
            sa.Column("slippage", sa.Numeric(12, 4), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.CheckConstraint("entry_price > 0", name="ck_paper_positions_entry_price_positive"),
            sa.CheckConstraint("quantity > 0", name="ck_paper_positions_quantity_positive"),
            sa.CheckConstraint("capital_allocated >= 0", name="ck_paper_positions_capital_nonnegative"),
            sa.CheckConstraint("status IN ('open', 'closed', 'cancelled', 'review')", name="ck_paper_positions_status"),
        )

    if not _has_table(inspector, "paper_trades"):
        op.create_table(
            "paper_trades",
            sa.Column("trade_id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("portfolio_id", sa.Integer(), sa.ForeignKey("paper_portfolios.portfolio_id"), nullable=False),
            sa.Column("position_id", sa.Integer(), nullable=True),
            sa.Column("symbol", sa.String(length=20), sa.ForeignKey("symbol_master.symbol"), nullable=False),
            sa.Column("sector", sa.String(length=50), nullable=True),
            sa.Column("signal_date", sa.Date(), nullable=True),
            sa.Column("entry_date", sa.Date(), nullable=False),
            sa.Column("exit_date", sa.Date(), nullable=False),
            sa.Column("entry_price", sa.Numeric(12, 4), nullable=False),
            sa.Column("exit_price", sa.Numeric(12, 4), nullable=False),
            sa.Column("quantity", sa.Numeric(18, 8), nullable=False),
            sa.Column("capital_allocated", sa.Numeric(14, 2), nullable=False),
            sa.Column("proceeds", sa.Numeric(14, 2), nullable=False),
            sa.Column("realized_pnl", sa.Numeric(14, 2), nullable=False),
            sa.Column("return_pct", sa.Numeric(10, 6), nullable=False),
            sa.Column("fees", sa.Numeric(12, 4), nullable=False, server_default="0"),
            sa.Column("slippage", sa.Numeric(12, 4), nullable=False, server_default="0"),
            sa.Column("turnover", sa.Numeric(14, 2), nullable=False),
            sa.Column("exit_reason", sa.String(length=40), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.CheckConstraint("entry_price > 0", name="ck_paper_trades_entry_price_positive"),
            sa.CheckConstraint("exit_price > 0", name="ck_paper_trades_exit_price_positive"),
            sa.CheckConstraint("quantity > 0", name="ck_paper_trades_quantity_positive"),
        )

    if not _has_table(inspector, "paper_daily_snapshots"):
        op.create_table(
            "paper_daily_snapshots",
            sa.Column("snapshot_id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("portfolio_id", sa.Integer(), sa.ForeignKey("paper_portfolios.portfolio_id"), nullable=False),
            sa.Column("date", sa.Date(), nullable=False),
            sa.Column("cash", sa.Numeric(14, 2), nullable=False),
            sa.Column("market_value", sa.Numeric(14, 2), nullable=False),
            sa.Column("nav", sa.Numeric(14, 2), nullable=False),
            sa.Column("realized_pnl", sa.Numeric(14, 2), nullable=False),
            sa.Column("unrealized_pnl", sa.Numeric(14, 2), nullable=False),
            sa.Column("fees", sa.Numeric(12, 4), nullable=False, server_default="0"),
            sa.Column("slippage", sa.Numeric(12, 4), nullable=False, server_default="0"),
            sa.Column("turnover", sa.Numeric(14, 2), nullable=False, server_default="0"),
            sa.Column("benchmark_close", sa.Numeric(12, 4), nullable=True),
            sa.Column("benchmark_return", sa.Numeric(10, 6), nullable=True),
            sa.Column("open_positions", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.UniqueConstraint("portfolio_id", "date", name="uq_paper_daily_snapshots_portfolio_date"),
        )

    op.create_index("ix_paper_positions_portfolio_status", "paper_positions", ["portfolio_id", "status"], if_not_exists=True)
    op.create_index("ix_paper_positions_symbol", "paper_positions", ["symbol"], if_not_exists=True)
    op.create_index("ix_paper_trades_portfolio_exit", "paper_trades", ["portfolio_id", "exit_date"], if_not_exists=True)
    op.create_index("ix_paper_trades_symbol", "paper_trades", ["symbol"], if_not_exists=True)
    op.create_index("ix_paper_snapshots_portfolio_date", "paper_daily_snapshots", ["portfolio_id", "date"], if_not_exists=True)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _has_table(inspector, "paper_daily_snapshots"):
        op.drop_index("ix_paper_snapshots_portfolio_date", table_name="paper_daily_snapshots", if_exists=True)
        op.drop_table("paper_daily_snapshots")
    if _has_table(inspector, "paper_trades"):
        op.drop_index("ix_paper_trades_symbol", table_name="paper_trades", if_exists=True)
        op.drop_index("ix_paper_trades_portfolio_exit", table_name="paper_trades", if_exists=True)
        op.drop_table("paper_trades")
    if _has_table(inspector, "paper_positions"):
        op.drop_index("ix_paper_positions_symbol", table_name="paper_positions", if_exists=True)
        op.drop_index("ix_paper_positions_portfolio_status", table_name="paper_positions", if_exists=True)
        op.drop_table("paper_positions")
    if _has_table(inspector, "paper_portfolios"):
        op.drop_table("paper_portfolios")
