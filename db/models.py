"""Database model definitions for the NSE Research Platform.

Reads:
  - No runtime data; only schema declarations

Writes:
  - SQLAlchemy metadata for Alembic and tests

Does not:
  - Implement ingestion, scoring, backtesting, or API logic
"""

from __future__ import annotations

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Integer, JSON, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class SymbolMaster(Base):
    __tablename__ = "symbol_master"

    symbol: Mapped[str] = mapped_column(String(20), primary_key=True)
    company_name: Mapped[str | None] = mapped_column(String(100))
    sector: Mapped[str | None] = mapped_column(String(50))
    subsector: Mapped[str | None] = mapped_column(String(50))
    nse500: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    nse500_from_date: Mapped[object | None] = mapped_column(Date)
    nse500_to_date: Mapped[object | None] = mapped_column(Date)


class SecurityMaster(Base):
    __tablename__ = "security_master"

    security_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    canonical_symbol: Mapped[str] = mapped_column(String(40), nullable=False)
    canonical_name: Mapped[str | None] = mapped_column(Text)
    isin_current: Mapped[str | None] = mapped_column(String(20))
    exchange: Mapped[str] = mapped_column(String(20), nullable=False, default="NSE")
    instrument_type: Mapped[str] = mapped_column(String(30), nullable=False, default="equity")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="active")
    first_seen_date: Mapped[object | None] = mapped_column(Date)
    last_seen_date: Mapped[object | None] = mapped_column(Date)
    created_from_source: Mapped[str | None] = mapped_column(String(50))
    review_status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[object | None] = mapped_column(DateTime)
    updated_at: Mapped[object | None] = mapped_column(DateTime)


class SecuritySymbolAlias(Base):
    __tablename__ = "security_symbol_alias"

    alias_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    security_id: Mapped[int] = mapped_column(ForeignKey("security_master.security_id"), nullable=False)
    source: Mapped[str] = mapped_column(String(30), nullable=False)
    symbol: Mapped[str] = mapped_column(String(40), nullable=False)
    normalized_symbol: Mapped[str] = mapped_column(String(40), nullable=False)
    valid_from: Mapped[object | None] = mapped_column(Date)
    valid_to: Mapped[object | None] = mapped_column(Date)
    is_primary_for_source: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    alias_reason: Mapped[str] = mapped_column(String(40), nullable=False)
    confidence: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    review_status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[object | None] = mapped_column(DateTime)
    updated_at: Mapped[object | None] = mapped_column(DateTime)

    __table_args__ = (
        UniqueConstraint("source", "symbol", "valid_from", name="uq_security_symbol_alias_source_symbol_from"),
        CheckConstraint("valid_to IS NULL OR valid_from IS NULL OR valid_to >= valid_from", name="ck_security_symbol_alias_date_order"),
    )


class SecurityCorporateActionLineage(Base):
    __tablename__ = "security_corporate_action_lineage"

    event_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_date: Mapped[object | None] = mapped_column(Date)
    event_type: Mapped[str] = mapped_column(String(40), nullable=False)
    from_security_id: Mapped[int | None] = mapped_column(ForeignKey("security_master.security_id"))
    to_security_id: Mapped[int | None] = mapped_column(ForeignKey("security_master.security_id"))
    ratio: Mapped[float | None] = mapped_column(Numeric(18, 8))
    source_reference: Mapped[str | None] = mapped_column(Text)
    review_status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[object | None] = mapped_column(DateTime)
    updated_at: Mapped[object | None] = mapped_column(DateTime)

    __table_args__ = (
        CheckConstraint("from_security_id IS NOT NULL OR to_security_id IS NOT NULL", name="ck_security_lineage_has_security"),
    )


class PricesDaily(Base):
    __tablename__ = "prices_daily"

    symbol: Mapped[str] = mapped_column(ForeignKey("symbol_master.symbol"), primary_key=True)
    date: Mapped[object] = mapped_column(Date, primary_key=True)
    open: Mapped[float | None] = mapped_column(Numeric(12, 2))
    high: Mapped[float | None] = mapped_column(Numeric(12, 2))
    low: Mapped[float | None] = mapped_column(Numeric(12, 2))
    close: Mapped[float | None] = mapped_column(Numeric(12, 2))
    volume: Mapped[int | None] = mapped_column(Integer)

    __table_args__ = (UniqueConstraint("symbol", "date", name="uq_prices_daily_symbol_date"),)


class FeaturesDaily(Base):
    __tablename__ = "features_daily"

    symbol: Mapped[str] = mapped_column(ForeignKey("symbol_master.symbol"), primary_key=True)
    date: Mapped[object] = mapped_column(Date, primary_key=True)
    sector: Mapped[str | None] = mapped_column(String(50))
    is_eligible: Mapped[bool | None] = mapped_column(Boolean, default=True)
    avg_traded_value: Mapped[float | None] = mapped_column(Numeric(16, 2))
    rsi_14: Mapped[float | None] = mapped_column(Numeric(6, 2))
    rsi_9: Mapped[float | None] = mapped_column(Numeric(6, 2))
    macd_line: Mapped[float | None] = mapped_column(Numeric(10, 4))
    macd_signal: Mapped[float | None] = mapped_column(Numeric(10, 4))
    macd_hist: Mapped[float | None] = mapped_column(Numeric(10, 4))
    macd_hist_prev: Mapped[float | None] = mapped_column(Numeric(10, 4))
    adx_14: Mapped[float | None] = mapped_column(Numeric(6, 2))
    adx_prev: Mapped[float | None] = mapped_column(Numeric(6, 2))
    ema_5: Mapped[float | None] = mapped_column(Numeric(12, 2))
    ema_13: Mapped[float | None] = mapped_column(Numeric(12, 2))
    ema_20: Mapped[float | None] = mapped_column(Numeric(12, 2))
    ema_50: Mapped[float | None] = mapped_column(Numeric(12, 2))
    ema_150: Mapped[float | None] = mapped_column(Numeric(12, 2))
    ema_200: Mapped[float | None] = mapped_column(Numeric(12, 2))
    atr_14: Mapped[float | None] = mapped_column(Numeric(10, 4))
    bb_upper: Mapped[float | None] = mapped_column(Numeric(12, 2))
    bb_mid: Mapped[float | None] = mapped_column(Numeric(12, 2))
    bb_lower: Mapped[float | None] = mapped_column(Numeric(12, 2))
    bb_width: Mapped[float | None] = mapped_column(Numeric(8, 4))
    bb_width_20avg: Mapped[float | None] = mapped_column(Numeric(8, 4))
    bb_pct: Mapped[float | None] = mapped_column(Numeric(6, 4))
    volume_20avg: Mapped[int | None] = mapped_column(Integer)
    volume_ratio: Mapped[float | None] = mapped_column(Numeric(8, 2))
    high_52w: Mapped[float | None] = mapped_column(Numeric(12, 2))
    low_52w: Mapped[float | None] = mapped_column(Numeric(12, 2))
    pct_from_52w_high: Mapped[float | None] = mapped_column(Numeric(6, 2))
    distance_from_52w_high: Mapped[float | None] = mapped_column(Numeric(6, 2))
    pct_from_52w_low: Mapped[float | None] = mapped_column(Numeric(6, 2))
    is_52w_breakout: Mapped[bool | None] = mapped_column(Boolean)
    stoch_k: Mapped[float | None] = mapped_column(Numeric(6, 2))
    stoch_d: Mapped[float | None] = mapped_column(Numeric(6, 2))
    rs_vs_nifty_20d: Mapped[float | None] = mapped_column(Numeric(8, 4))
    rs_vs_nifty_60d: Mapped[float | None] = mapped_column(Numeric(8, 4))
    rs_rank_pct: Mapped[float | None] = mapped_column(Numeric(6, 2))
    rs_vs_sector_20d: Mapped[float | None] = mapped_column(Numeric(8, 4))

    __table_args__ = (UniqueConstraint("symbol", "date", name="uq_features_daily_symbol_date"),)


class ModelVersion(Base):
    __tablename__ = "model_version"

    version_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    version_tag: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[object | None] = mapped_column(DateTime)
    model: Mapped[str] = mapped_column(String(20), nullable=False)
    weights_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    backtest_cagr: Mapped[float | None] = mapped_column(Numeric(6, 2))
    backtest_sharpe: Mapped[float | None] = mapped_column(Numeric(6, 3))
    is_active: Mapped[bool | None] = mapped_column(Boolean, default=False)


class DailyScores(Base):
    __tablename__ = "daily_scores"

    symbol: Mapped[str] = mapped_column(ForeignKey("symbol_master.symbol"), primary_key=True)
    date: Mapped[object] = mapped_column(Date, primary_key=True)
    model_version_id: Mapped[int | None] = mapped_column(ForeignKey("model_version.version_id"))
    swing_score: Mapped[float | None] = mapped_column(Numeric(5, 1))
    position_score: Mapped[float | None] = mapped_column(Numeric(5, 1))
    lt_score: Mapped[float | None] = mapped_column(Numeric(5, 1))
    swing_v2_score: Mapped[float | None] = mapped_column(Numeric(5, 1))
    swing_v2_1_score: Mapped[float | None] = mapped_column(Numeric(5, 1))
    position_v2_score: Mapped[float | None] = mapped_column(Numeric(5, 1))
    swing_momentum: Mapped[float | None] = mapped_column(Numeric(5, 1))
    swing_volume: Mapped[float | None] = mapped_column(Numeric(5, 1))
    swing_breakout: Mapped[float | None] = mapped_column(Numeric(5, 1))
    swing_rs: Mapped[float | None] = mapped_column(Numeric(5, 1))
    stop_loss: Mapped[float | None] = mapped_column(Numeric(12, 2))
    target_1: Mapped[float | None] = mapped_column(Numeric(12, 2))
    target_2: Mapped[float | None] = mapped_column(Numeric(12, 2))
    target_3: Mapped[float | None] = mapped_column(Numeric(12, 2))
    rr_ratio: Mapped[float | None] = mapped_column(Numeric(5, 2))

    __table_args__ = (UniqueConstraint("symbol", "date", name="uq_daily_scores_symbol_date"),)


class RecommendationHistory(Base):
    __tablename__ = "recommendation_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[object] = mapped_column(Date, nullable=False)
    model: Mapped[str] = mapped_column(String(20), nullable=False)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    symbol: Mapped[str] = mapped_column(ForeignKey("symbol_master.symbol"), nullable=False)
    score: Mapped[float | None] = mapped_column(Numeric(5, 1))
    model_version_id: Mapped[int | None] = mapped_column(ForeignKey("model_version.version_id"))
    entry_price: Mapped[float | None] = mapped_column(Numeric(12, 2))
    stop_loss: Mapped[float | None] = mapped_column(Numeric(12, 2))
    target_1: Mapped[float | None] = mapped_column(Numeric(12, 2))
    rr_ratio: Mapped[float | None] = mapped_column(Numeric(5, 2))
    rsi_14: Mapped[float | None] = mapped_column(Numeric(6, 2))
    adx_14: Mapped[float | None] = mapped_column(Numeric(6, 2))
    volume_ratio: Mapped[float | None] = mapped_column(Numeric(8, 2))
    rs_rank_pct: Mapped[float | None] = mapped_column(Numeric(6, 2))
    sector_rank: Mapped[int | None] = mapped_column(Integer)
    bb_width_ratio: Mapped[float | None] = mapped_column(Numeric(8, 4))
    reason_codes: Mapped[object | None] = mapped_column(JSON)
    exit_date: Mapped[object | None] = mapped_column(Date)
    exit_price: Mapped[float | None] = mapped_column(Numeric(12, 2))
    exit_reason: Mapped[str | None] = mapped_column(String(30))
    return_pct: Mapped[float | None] = mapped_column(Numeric(8, 4))
    holding_days: Mapped[int | None] = mapped_column(Integer)

    __table_args__ = (UniqueConstraint("date", "model", "symbol", name="uq_recommendation_history_date_model_symbol"),)


class RecommendationDecisionJournal(Base):
    __tablename__ = "recommendation_decision_journal"

    journal_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    business_date: Mapped[object] = mapped_column(Date, nullable=False)
    symbol: Mapped[str] = mapped_column(String(40), nullable=False)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    score: Mapped[float | None] = mapped_column(Numeric(10, 4))
    recommendation_type: Mapped[str] = mapped_column(String(40), nullable=False)
    sector: Mapped[str | None] = mapped_column(String(80))
    feature_snapshot_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[object | None] = mapped_column(DateTime)

    __table_args__ = (
        UniqueConstraint(
            "business_date",
            "symbol",
            "recommendation_type",
            name="uq_recommendation_decision_journal_date_symbol_type",
        ),
    )


class SectorDaily(Base):
    __tablename__ = "sector_daily"

    date: Mapped[object] = mapped_column(Date, primary_key=True)
    sector: Mapped[str] = mapped_column(String(50), primary_key=True)
    return_1m: Mapped[float | None] = mapped_column(Numeric(8, 4))
    return_3m: Mapped[float | None] = mapped_column(Numeric(8, 4))
    return_6m: Mapped[float | None] = mapped_column(Numeric(8, 4))
    sector_score: Mapped[float | None] = mapped_column(Numeric(8, 4))
    sector_rank: Mapped[int | None] = mapped_column(Integer)
    sector_return_1m: Mapped[float | None] = mapped_column(Numeric(8, 4))
    sector_return_3m: Mapped[float | None] = mapped_column(Numeric(8, 4))
    sector_return_6m: Mapped[float | None] = mapped_column(Numeric(8, 4))
    composite_score: Mapped[float | None] = mapped_column(Numeric(8, 4))
    rank_3m: Mapped[int | None] = mapped_column(Integer)
    rank_composite: Mapped[int | None] = mapped_column(Integer)
    stock_count: Mapped[int | None] = mapped_column(Integer)

    __table_args__ = (UniqueConstraint("sector", "date", name="uq_sector_daily_sector_date"),)


class PortfolioPositions(Base):
    __tablename__ = "portfolio_positions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(ForeignKey("symbol_master.symbol"), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    avg_cost: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    entry_date: Mapped[object] = mapped_column(Date, nullable=False)
    strategy: Mapped[str | None] = mapped_column(String(20))
    stop_loss: Mapped[float | None] = mapped_column(Numeric(12, 2))
    target_1: Mapped[float | None] = mapped_column(Numeric(12, 2))
    notes: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str | None] = mapped_column(String(10), default="open")
    exit_date: Mapped[object | None] = mapped_column(Date)
    exit_price: Mapped[float | None] = mapped_column(Numeric(12, 2))


class TradeLog(Base):
    __tablename__ = "trade_log"

    trade_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(ForeignKey("symbol_master.symbol"), nullable=False)
    strategy: Mapped[str] = mapped_column(String(20), nullable=False)
    entry_date: Mapped[object] = mapped_column(Date, nullable=False)
    exit_date: Mapped[object | None] = mapped_column(Date)
    entry_price: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    exit_price: Mapped[float | None] = mapped_column(Numeric(12, 2))
    quantity: Mapped[int | None] = mapped_column(Integer)
    stop_loss: Mapped[float | None] = mapped_column(Numeric(12, 2))
    target_1: Mapped[float | None] = mapped_column(Numeric(12, 2))
    score_at_entry: Mapped[float | None] = mapped_column(Numeric(5, 1))
    exit_reason: Mapped[str | None] = mapped_column(String(30))
    pnl_pct: Mapped[float | None] = mapped_column(Numeric(8, 4))
    pnl_inr: Mapped[float | None] = mapped_column(Numeric(12, 2))
    holding_days: Mapped[int | None] = mapped_column(Integer)
    run_type: Mapped[str | None] = mapped_column(String(10), default="backtest")


class BacktestRuns(Base):
    __tablename__ = "backtest_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_date: Mapped[object | None] = mapped_column(Date)
    model: Mapped[str | None] = mapped_column(String(20))
    start_date: Mapped[object | None] = mapped_column(Date)
    end_date: Mapped[object | None] = mapped_column(Date)
    capital: Mapped[float | None] = mapped_column(Numeric(14, 2))
    portfolio_size: Mapped[int | None] = mapped_column(Integer)
    total_return_pct: Mapped[float | None] = mapped_column(Numeric(8, 2))
    cagr_pct: Mapped[float | None] = mapped_column(Numeric(8, 2))
    max_drawdown_pct: Mapped[float | None] = mapped_column(Numeric(8, 2))
    win_rate_pct: Mapped[float | None] = mapped_column(Numeric(8, 2))
    sharpe_ratio: Mapped[float | None] = mapped_column(Numeric(6, 3))
    total_trades: Mapped[int | None] = mapped_column(Integer)
    avg_rr: Mapped[float | None] = mapped_column(Numeric(6, 2))
    nifty_return_pct: Mapped[float | None] = mapped_column(Numeric(8, 2))
    alpha_pct: Mapped[float | None] = mapped_column(Numeric(8, 2))
    config_json: Mapped[object | None] = mapped_column(JSON)


class PaperPortfolio(Base):
    __tablename__ = "paper_portfolios"

    portfolio_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    strategy: Mapped[str] = mapped_column(String(40), nullable=False)
    portfolio_size: Mapped[int] = mapped_column(Integer, nullable=False)
    initial_capital: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    cash: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    current_nav: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    benchmark_symbol: Mapped[str | None] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    created_at: Mapped[object | None] = mapped_column(DateTime)
    updated_at: Mapped[object | None] = mapped_column(DateTime)

    __table_args__ = (
        CheckConstraint("portfolio_size > 0", name="ck_paper_portfolios_size_positive"),
        CheckConstraint("initial_capital > 0", name="ck_paper_portfolios_initial_capital_positive"),
        CheckConstraint("cash >= 0", name="ck_paper_portfolios_cash_nonnegative"),
    )


class PaperPosition(Base):
    __tablename__ = "paper_positions"

    position_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    portfolio_id: Mapped[int] = mapped_column(ForeignKey("paper_portfolios.portfolio_id"), nullable=False)
    symbol: Mapped[str] = mapped_column(ForeignKey("symbol_master.symbol"), nullable=False)
    sector: Mapped[str | None] = mapped_column(String(50))
    signal_date: Mapped[object | None] = mapped_column(Date)
    recommendation_rank: Mapped[int | None] = mapped_column(Integer)
    recommendation_score: Mapped[float | None] = mapped_column(Numeric(8, 4))
    entry_date: Mapped[object] = mapped_column(Date, nullable=False)
    entry_price: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    quantity: Mapped[float] = mapped_column(Numeric(18, 8), nullable=False)
    capital_allocated: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    current_price: Mapped[float | None] = mapped_column(Numeric(12, 4))
    market_value: Mapped[float | None] = mapped_column(Numeric(14, 2))
    unrealized_pnl: Mapped[float | None] = mapped_column(Numeric(14, 2))
    planned_exit_date: Mapped[object | None] = mapped_column(Date)
    exit_date: Mapped[object | None] = mapped_column(Date)
    exit_price: Mapped[float | None] = mapped_column(Numeric(12, 4))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open")
    fees: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False, default=0)
    slippage: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False, default=0)
    created_at: Mapped[object | None] = mapped_column(DateTime)
    updated_at: Mapped[object | None] = mapped_column(DateTime)

    __table_args__ = (
        CheckConstraint("entry_price > 0", name="ck_paper_positions_entry_price_positive"),
        CheckConstraint("quantity > 0", name="ck_paper_positions_quantity_positive"),
        CheckConstraint("capital_allocated >= 0", name="ck_paper_positions_capital_nonnegative"),
        CheckConstraint("status IN ('open', 'closed', 'cancelled', 'review')", name="ck_paper_positions_status"),
    )


class PaperTrade(Base):
    __tablename__ = "paper_trades"

    trade_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    portfolio_id: Mapped[int] = mapped_column(ForeignKey("paper_portfolios.portfolio_id"), nullable=False)
    position_id: Mapped[int | None] = mapped_column(Integer)
    symbol: Mapped[str] = mapped_column(ForeignKey("symbol_master.symbol"), nullable=False)
    sector: Mapped[str | None] = mapped_column(String(50))
    signal_date: Mapped[object | None] = mapped_column(Date)
    entry_date: Mapped[object] = mapped_column(Date, nullable=False)
    exit_date: Mapped[object] = mapped_column(Date, nullable=False)
    entry_price: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    exit_price: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    quantity: Mapped[float] = mapped_column(Numeric(18, 8), nullable=False)
    capital_allocated: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    proceeds: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    realized_pnl: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    return_pct: Mapped[float] = mapped_column(Numeric(10, 6), nullable=False)
    fees: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False, default=0)
    slippage: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False, default=0)
    turnover: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    exit_reason: Mapped[str] = mapped_column(String(40), nullable=False)
    created_at: Mapped[object | None] = mapped_column(DateTime)

    __table_args__ = (
        CheckConstraint("entry_price > 0", name="ck_paper_trades_entry_price_positive"),
        CheckConstraint("exit_price > 0", name="ck_paper_trades_exit_price_positive"),
        CheckConstraint("quantity > 0", name="ck_paper_trades_quantity_positive"),
    )


class PaperDailySnapshot(Base):
    __tablename__ = "paper_daily_snapshots"

    snapshot_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    portfolio_id: Mapped[int] = mapped_column(ForeignKey("paper_portfolios.portfolio_id"), nullable=False)
    date: Mapped[object] = mapped_column(Date, nullable=False)
    cash: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    market_value: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    nav: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    realized_pnl: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    unrealized_pnl: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    fees: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False, default=0)
    slippage: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False, default=0)
    turnover: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    benchmark_close: Mapped[float | None] = mapped_column(Numeric(12, 4))
    benchmark_return: Mapped[float | None] = mapped_column(Numeric(10, 6))
    open_positions: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[object | None] = mapped_column(DateTime)

    __table_args__ = (UniqueConstraint("portfolio_id", "date", name="uq_paper_daily_snapshots_portfolio_date"),)


class UniverseSnapshot(Base):
    __tablename__ = "universe_snapshot"

    date: Mapped[object] = mapped_column(Date, primary_key=True)
    symbol: Mapped[str] = mapped_column(ForeignKey("symbol_master.symbol"), primary_key=True)
    index_name: Mapped[str] = mapped_column(String(20), primary_key=True, default="NSE500")


class PipelineRuns(Base):
    __tablename__ = "pipeline_runs"

    run_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    business_date: Mapped[object | None] = mapped_column(Date)
    step_name: Mapped[str | None] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    started_at: Mapped[object | None] = mapped_column(DateTime)
    completed_at: Mapped[object | None] = mapped_column(DateTime)
    error_message: Mapped[str | None] = mapped_column(Text)
    job_name: Mapped[str | None] = mapped_column(String(50))
    run_date: Mapped[object | None] = mapped_column(Date)
    start_time: Mapped[object | None] = mapped_column(DateTime)
    end_time: Mapped[object | None] = mapped_column(DateTime)
    rows_processed: Mapped[int | None] = mapped_column(Integer)

    __table_args__ = (
        UniqueConstraint("business_date", "step_name", name="uq_pipeline_runs_business_date_step_name"),
    )


class IndexPricesDaily(Base):
    __tablename__ = "index_prices_daily"

    index_name: Mapped[str] = mapped_column(String(20), primary_key=True)
    date: Mapped[object] = mapped_column(Date, primary_key=True)
    open: Mapped[float | None] = mapped_column(Numeric(12, 2))
    high: Mapped[float | None] = mapped_column(Numeric(12, 2))
    low: Mapped[float | None] = mapped_column(Numeric(12, 2))
    close: Mapped[float | None] = mapped_column(Numeric(12, 2))
    volume: Mapped[int | None] = mapped_column(Integer)

    __table_args__ = (UniqueConstraint("index_name", "date", name="uq_index_prices_daily_index_date"),)


class DataQualityLog(Base):
    __tablename__ = "data_quality_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[object] = mapped_column(Date, nullable=False)
    job_name: Mapped[str] = mapped_column(String(50), nullable=False)
    records_expected: Mapped[int | None] = mapped_column(Integer)
    records_loaded: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[object | None] = mapped_column(DateTime)
