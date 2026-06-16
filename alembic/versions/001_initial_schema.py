"""Create initial database tables."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "symbol_master",
        sa.Column("symbol", sa.String(length=20), primary_key=True),
        sa.Column("company_name", sa.String(length=100)),
        sa.Column("sector", sa.String(length=50)),
        sa.Column("subsector", sa.String(length=50)),
        sa.Column("nse500", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("nse500_from_date", sa.Date()),
        sa.Column("nse500_to_date", sa.Date()),
    )

    op.create_table(
        "model_version",
        sa.Column("version_id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("version_tag", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime()),
        sa.Column("model", sa.String(length=20), nullable=False),
        sa.Column("weights_json", sa.JSON(), nullable=False),
        sa.Column("notes", sa.Text()),
        sa.Column("backtest_cagr", sa.Numeric(6, 2)),
        sa.Column("backtest_sharpe", sa.Numeric(6, 3)),
        sa.Column("is_active", sa.Boolean(), server_default=sa.false()),
    )

    op.create_table(
        "prices_daily",
        sa.Column("symbol", sa.String(length=20), sa.ForeignKey("symbol_master.symbol"), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("open", sa.Numeric(12, 2)),
        sa.Column("high", sa.Numeric(12, 2)),
        sa.Column("low", sa.Numeric(12, 2)),
        sa.Column("close", sa.Numeric(12, 2)),
        sa.Column("volume", sa.Integer()),
        sa.PrimaryKeyConstraint("symbol", "date"),
        sa.UniqueConstraint("symbol", "date", name="uq_prices_daily_symbol_date"),
    )

    op.create_table(
        "features_daily",
        sa.Column("symbol", sa.String(length=20), sa.ForeignKey("symbol_master.symbol"), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("sector", sa.String(length=50)),
        sa.Column("is_eligible", sa.Boolean(), server_default=sa.true()),
        sa.Column("avg_traded_value", sa.Numeric(16, 2)),
        sa.Column("rsi_14", sa.Numeric(6, 2)),
        sa.Column("rsi_9", sa.Numeric(6, 2)),
        sa.Column("macd_line", sa.Numeric(10, 4)),
        sa.Column("macd_signal", sa.Numeric(10, 4)),
        sa.Column("macd_hist", sa.Numeric(10, 4)),
        sa.Column("macd_hist_prev", sa.Numeric(10, 4)),
        sa.Column("adx_14", sa.Numeric(6, 2)),
        sa.Column("adx_prev", sa.Numeric(6, 2)),
        sa.Column("ema_5", sa.Numeric(12, 2)),
        sa.Column("ema_13", sa.Numeric(12, 2)),
        sa.Column("ema_20", sa.Numeric(12, 2)),
        sa.Column("ema_50", sa.Numeric(12, 2)),
        sa.Column("ema_150", sa.Numeric(12, 2)),
        sa.Column("ema_200", sa.Numeric(12, 2)),
        sa.Column("atr_14", sa.Numeric(10, 4)),
        sa.Column("bb_upper", sa.Numeric(12, 2)),
        sa.Column("bb_mid", sa.Numeric(12, 2)),
        sa.Column("bb_lower", sa.Numeric(12, 2)),
        sa.Column("bb_width", sa.Numeric(8, 4)),
        sa.Column("bb_width_20avg", sa.Numeric(8, 4)),
        sa.Column("bb_pct", sa.Numeric(6, 4)),
        sa.Column("volume_20avg", sa.Integer()),
        sa.Column("volume_ratio", sa.Numeric(8, 2)),
        sa.Column("high_52w", sa.Numeric(12, 2)),
        sa.Column("low_52w", sa.Numeric(12, 2)),
        sa.Column("pct_from_52w_high", sa.Numeric(6, 2)),
        sa.Column("pct_from_52w_low", sa.Numeric(6, 2)),
        sa.Column("stoch_k", sa.Numeric(6, 2)),
        sa.Column("stoch_d", sa.Numeric(6, 2)),
        sa.Column("rs_vs_nifty_20d", sa.Numeric(8, 4)),
        sa.Column("rs_vs_nifty_60d", sa.Numeric(8, 4)),
        sa.Column("rs_rank_pct", sa.Numeric(6, 2)),
        sa.Column("rs_vs_sector_20d", sa.Numeric(8, 4)),
        sa.PrimaryKeyConstraint("symbol", "date"),
        sa.UniqueConstraint("symbol", "date", name="uq_features_daily_symbol_date"),
    )

    op.create_table(
        "sector_daily",
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("sector", sa.String(length=50), nullable=False),
        sa.Column("sector_return_1m", sa.Numeric(8, 4)),
        sa.Column("sector_return_3m", sa.Numeric(8, 4)),
        sa.Column("sector_return_6m", sa.Numeric(8, 4)),
        sa.Column("composite_score", sa.Numeric(8, 4)),
        sa.Column("rank_3m", sa.Integer()),
        sa.Column("rank_composite", sa.Integer()),
        sa.Column("stock_count", sa.Integer()),
        sa.PrimaryKeyConstraint("date", "sector"),
        sa.UniqueConstraint("sector", "date", name="uq_sector_daily_sector_date"),
    )

    op.create_table(
        "daily_scores",
        sa.Column("symbol", sa.String(length=20), sa.ForeignKey("symbol_master.symbol"), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("model_version_id", sa.Integer(), sa.ForeignKey("model_version.version_id")),
        sa.Column("swing_score", sa.Numeric(5, 1)),
        sa.Column("position_score", sa.Numeric(5, 1)),
        sa.Column("lt_score", sa.Numeric(5, 1)),
        sa.Column("swing_momentum", sa.Numeric(5, 1)),
        sa.Column("swing_volume", sa.Numeric(5, 1)),
        sa.Column("swing_breakout", sa.Numeric(5, 1)),
        sa.Column("swing_rs", sa.Numeric(5, 1)),
        sa.Column("stop_loss", sa.Numeric(12, 2)),
        sa.Column("target_1", sa.Numeric(12, 2)),
        sa.Column("target_2", sa.Numeric(12, 2)),
        sa.Column("target_3", sa.Numeric(12, 2)),
        sa.Column("rr_ratio", sa.Numeric(5, 2)),
        sa.PrimaryKeyConstraint("symbol", "date"),
        sa.UniqueConstraint("symbol", "date", name="uq_daily_scores_symbol_date"),
    )

    op.create_table(
        "recommendation_history",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("model", sa.String(length=20), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("symbol", sa.String(length=20), sa.ForeignKey("symbol_master.symbol"), nullable=False),
        sa.Column("score", sa.Numeric(5, 1)),
        sa.Column("entry_price", sa.Numeric(12, 2)),
        sa.Column("stop_loss", sa.Numeric(12, 2)),
        sa.Column("target_1", sa.Numeric(12, 2)),
        sa.Column("rr_ratio", sa.Numeric(5, 2)),
        sa.Column("rsi_14", sa.Numeric(6, 2)),
        sa.Column("adx_14", sa.Numeric(6, 2)),
        sa.Column("volume_ratio", sa.Numeric(8, 2)),
        sa.Column("rs_rank_pct", sa.Numeric(6, 2)),
        sa.Column("sector_rank", sa.Integer()),
        sa.Column("bb_width_ratio", sa.Numeric(8, 4)),
        sa.Column("reason_codes", sa.JSON()),
        sa.Column("exit_date", sa.Date()),
        sa.Column("exit_price", sa.Numeric(12, 2)),
        sa.Column("exit_reason", sa.String(length=30)),
        sa.Column("return_pct", sa.Numeric(8, 4)),
        sa.Column("holding_days", sa.Integer()),
        sa.UniqueConstraint("date", "model", "symbol", name="uq_recommendation_history_date_model_symbol"),
    )

    op.create_table(
        "portfolio_positions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("symbol", sa.String(length=20), sa.ForeignKey("symbol_master.symbol"), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("avg_cost", sa.Numeric(12, 2), nullable=False),
        sa.Column("entry_date", sa.Date(), nullable=False),
        sa.Column("strategy", sa.String(length=20)),
        sa.Column("stop_loss", sa.Numeric(12, 2)),
        sa.Column("target_1", sa.Numeric(12, 2)),
        sa.Column("notes", sa.Text()),
        sa.Column("status", sa.String(length=10), server_default="open"),
        sa.Column("exit_date", sa.Date()),
        sa.Column("exit_price", sa.Numeric(12, 2)),
    )

    op.create_table(
        "trade_log",
        sa.Column("trade_id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("symbol", sa.String(length=20), sa.ForeignKey("symbol_master.symbol"), nullable=False),
        sa.Column("strategy", sa.String(length=20), nullable=False),
        sa.Column("entry_date", sa.Date(), nullable=False),
        sa.Column("exit_date", sa.Date()),
        sa.Column("entry_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("exit_price", sa.Numeric(12, 2)),
        sa.Column("quantity", sa.Integer()),
        sa.Column("stop_loss", sa.Numeric(12, 2)),
        sa.Column("target_1", sa.Numeric(12, 2)),
        sa.Column("score_at_entry", sa.Numeric(5, 1)),
        sa.Column("exit_reason", sa.String(length=30)),
        sa.Column("pnl_pct", sa.Numeric(8, 4)),
        sa.Column("pnl_inr", sa.Numeric(12, 2)),
        sa.Column("holding_days", sa.Integer()),
        sa.Column("run_type", sa.String(length=10), server_default="backtest"),
    )

    op.create_table(
        "backtest_runs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("run_date", sa.Date()),
        sa.Column("model", sa.String(length=20)),
        sa.Column("start_date", sa.Date()),
        sa.Column("end_date", sa.Date()),
        sa.Column("capital", sa.Numeric(14, 2)),
        sa.Column("portfolio_size", sa.Integer()),
        sa.Column("total_return_pct", sa.Numeric(8, 2)),
        sa.Column("cagr_pct", sa.Numeric(8, 2)),
        sa.Column("max_drawdown_pct", sa.Numeric(8, 2)),
        sa.Column("win_rate_pct", sa.Numeric(8, 2)),
        sa.Column("sharpe_ratio", sa.Numeric(6, 3)),
        sa.Column("total_trades", sa.Integer()),
        sa.Column("avg_rr", sa.Numeric(6, 2)),
        sa.Column("nifty_return_pct", sa.Numeric(8, 2)),
        sa.Column("alpha_pct", sa.Numeric(8, 2)),
        sa.Column("config_json", sa.JSON()),
    )

    op.create_table(
        "universe_snapshot",
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("symbol", sa.String(length=20), sa.ForeignKey("symbol_master.symbol"), nullable=False),
        sa.Column("index_name", sa.String(length=20), nullable=False, server_default="NSE500"),
        sa.PrimaryKeyConstraint("date", "symbol", "index_name"),
    )

    op.create_table(
        "pipeline_runs",
        sa.Column("run_id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("job_name", sa.String(length=50), nullable=False),
        sa.Column("run_date", sa.Date(), nullable=False),
        sa.Column("start_time", sa.DateTime(), nullable=False),
        sa.Column("end_time", sa.DateTime()),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("rows_processed", sa.Integer()),
        sa.Column("error_message", sa.Text()),
    )

    op.create_table(
        "data_quality_log",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("job_name", sa.String(length=50), nullable=False),
        sa.Column("records_expected", sa.Integer()),
        sa.Column("records_loaded", sa.Integer()),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("error_message", sa.Text()),
        sa.Column("created_at", sa.DateTime()),
    )


def downgrade() -> None:
    for table_name in [
        "data_quality_log",
        "pipeline_runs",
        "universe_snapshot",
        "backtest_runs",
        "trade_log",
        "portfolio_positions",
        "recommendation_history",
        "daily_scores",
        "sector_daily",
        "features_daily",
        "prices_daily",
        "model_version",
        "symbol_master",
    ]:
        op.drop_table(table_name)
