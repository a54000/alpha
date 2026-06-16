CREATE TABLE symbol_master (
    symbol VARCHAR(20) PRIMARY KEY,
    company_name VARCHAR(100),
    sector VARCHAR(50),
    subsector VARCHAR(50),
    nse500 BOOLEAN NOT NULL DEFAULT TRUE,
    nse500_from_date DATE,
    nse500_to_date DATE
);

CREATE TABLE model_version (
    version_id SERIAL PRIMARY KEY,
    version_tag VARCHAR(20) NOT NULL,
    created_at TIMESTAMP,
    model VARCHAR(20) NOT NULL,
    weights_json JSONB NOT NULL,
    notes TEXT,
    backtest_cagr NUMERIC(6,2),
    backtest_sharpe NUMERIC(6,3),
    is_active BOOLEAN DEFAULT FALSE
);

CREATE TABLE prices_daily (
    symbol VARCHAR(20) NOT NULL REFERENCES symbol_master(symbol),
    date DATE NOT NULL,
    open NUMERIC(12,2),
    high NUMERIC(12,2),
    low NUMERIC(12,2),
    close NUMERIC(12,2),
    volume INTEGER,
    PRIMARY KEY (symbol, date),
    CONSTRAINT uq_prices_daily_symbol_date UNIQUE (symbol, date)
);

CREATE TABLE features_daily (
    symbol VARCHAR(20) NOT NULL REFERENCES symbol_master(symbol),
    date DATE NOT NULL,
    sector VARCHAR(50),
    is_eligible BOOLEAN DEFAULT TRUE,
    avg_traded_value NUMERIC(16,2),
    rsi_14 NUMERIC(6,2),
    rsi_9 NUMERIC(6,2),
    macd_line NUMERIC(10,4),
    macd_signal NUMERIC(10,4),
    macd_hist NUMERIC(10,4),
    macd_hist_prev NUMERIC(10,4),
    adx_14 NUMERIC(6,2),
    adx_prev NUMERIC(6,2),
    ema_5 NUMERIC(12,2),
    ema_13 NUMERIC(12,2),
    ema_20 NUMERIC(12,2),
    ema_50 NUMERIC(12,2),
    ema_150 NUMERIC(12,2),
    ema_200 NUMERIC(12,2),
    atr_14 NUMERIC(10,4),
    bb_upper NUMERIC(12,2),
    bb_mid NUMERIC(12,2),
    bb_lower NUMERIC(12,2),
    bb_width NUMERIC(8,4),
    bb_width_20avg NUMERIC(8,4),
    bb_pct NUMERIC(6,4),
    volume_20avg INTEGER,
    volume_ratio NUMERIC(8,2),
    high_52w NUMERIC(12,2),
    low_52w NUMERIC(12,2),
    pct_from_52w_high NUMERIC(6,2),
    pct_from_52w_low NUMERIC(6,2),
    stoch_k NUMERIC(6,2),
    stoch_d NUMERIC(6,2),
    rs_vs_nifty_20d NUMERIC(8,4),
    rs_vs_nifty_60d NUMERIC(8,4),
    rs_rank_pct NUMERIC(6,2),
    rs_vs_sector_20d NUMERIC(8,4),
    PRIMARY KEY (symbol, date),
    CONSTRAINT uq_features_daily_symbol_date UNIQUE (symbol, date)
);

CREATE TABLE sector_daily (
    date DATE NOT NULL,
    sector VARCHAR(50) NOT NULL,
    sector_return_1m NUMERIC(8,4),
    sector_return_3m NUMERIC(8,4),
    sector_return_6m NUMERIC(8,4),
    composite_score NUMERIC(8,4),
    rank_3m INTEGER,
    rank_composite INTEGER,
    stock_count INTEGER,
    PRIMARY KEY (date, sector),
    CONSTRAINT uq_sector_daily_sector_date UNIQUE (sector, date)
);

CREATE TABLE daily_scores (
    symbol VARCHAR(20) NOT NULL REFERENCES symbol_master(symbol),
    date DATE NOT NULL,
    model_version_id INTEGER REFERENCES model_version(version_id),
    swing_score NUMERIC(5,1),
    position_score NUMERIC(5,1),
    lt_score NUMERIC(5,1),
    swing_momentum NUMERIC(5,1),
    swing_volume NUMERIC(5,1),
    swing_breakout NUMERIC(5,1),
    swing_rs NUMERIC(5,1),
    stop_loss NUMERIC(12,2),
    target_1 NUMERIC(12,2),
    target_2 NUMERIC(12,2),
    target_3 NUMERIC(12,2),
    rr_ratio NUMERIC(5,2),
    PRIMARY KEY (symbol, date),
    CONSTRAINT uq_daily_scores_symbol_date UNIQUE (symbol, date)
);

CREATE TABLE recommendation_history (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL,
    model VARCHAR(20) NOT NULL,
    rank INTEGER NOT NULL,
    symbol VARCHAR(20) NOT NULL REFERENCES symbol_master(symbol),
    score NUMERIC(5,1),
    entry_price NUMERIC(12,2),
    stop_loss NUMERIC(12,2),
    target_1 NUMERIC(12,2),
    rr_ratio NUMERIC(5,2),
    rsi_14 NUMERIC(6,2),
    adx_14 NUMERIC(6,2),
    volume_ratio NUMERIC(8,2),
    rs_rank_pct NUMERIC(6,2),
    sector_rank INTEGER,
    bb_width_ratio NUMERIC(8,4),
    reason_codes JSONB,
    exit_date DATE,
    exit_price NUMERIC(12,2),
    exit_reason VARCHAR(30),
    return_pct NUMERIC(8,4),
    holding_days INTEGER,
    CONSTRAINT uq_recommendation_history_date_model_symbol UNIQUE (date, model, symbol)
);

CREATE TABLE portfolio_positions (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL REFERENCES symbol_master(symbol),
    quantity INTEGER NOT NULL,
    avg_cost NUMERIC(12,2) NOT NULL,
    entry_date DATE NOT NULL,
    strategy VARCHAR(20),
    stop_loss NUMERIC(12,2),
    target_1 NUMERIC(12,2),
    notes TEXT,
    status VARCHAR(10) DEFAULT 'open',
    exit_date DATE,
    exit_price NUMERIC(12,2)
);

CREATE TABLE trade_log (
    trade_id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL REFERENCES symbol_master(symbol),
    strategy VARCHAR(20) NOT NULL,
    entry_date DATE NOT NULL,
    exit_date DATE,
    entry_price NUMERIC(12,2) NOT NULL,
    exit_price NUMERIC(12,2),
    quantity INTEGER,
    stop_loss NUMERIC(12,2),
    target_1 NUMERIC(12,2),
    score_at_entry NUMERIC(5,1),
    exit_reason VARCHAR(30),
    pnl_pct NUMERIC(8,4),
    pnl_inr NUMERIC(12,2),
    holding_days INTEGER,
    run_type VARCHAR(10) DEFAULT 'backtest'
);

CREATE TABLE backtest_runs (
    id SERIAL PRIMARY KEY,
    run_date TIMESTAMP,
    model VARCHAR(20),
    start_date DATE,
    end_date DATE,
    capital NUMERIC(14,2),
    portfolio_size INTEGER,
    total_return_pct NUMERIC(8,2),
    cagr_pct NUMERIC(8,2),
    max_drawdown_pct NUMERIC(8,2),
    win_rate_pct NUMERIC(8,2),
    sharpe_ratio NUMERIC(6,3),
    total_trades INTEGER,
    avg_rr NUMERIC(6,2),
    nifty_return_pct NUMERIC(8,2),
    alpha_pct NUMERIC(8,2),
    config_json JSONB
);

CREATE TABLE universe_snapshot (
    date DATE NOT NULL,
    symbol VARCHAR(20) NOT NULL REFERENCES symbol_master(symbol),
    index_name VARCHAR(20) NOT NULL DEFAULT 'NSE500',
    PRIMARY KEY (date, symbol, index_name)
);

CREATE TABLE pipeline_runs (
    run_id SERIAL PRIMARY KEY,
    job_name VARCHAR(50) NOT NULL,
    run_date DATE NOT NULL,
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP,
    status VARCHAR(20) NOT NULL,
    rows_processed INTEGER,
    error_message TEXT
);

CREATE TABLE data_quality_log (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL,
    job_name VARCHAR(50) NOT NULL,
    records_expected INTEGER,
    records_loaded INTEGER,
    status VARCHAR(20) NOT NULL,
    error_message TEXT,
    created_at TIMESTAMP
);
