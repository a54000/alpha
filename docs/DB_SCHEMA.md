# Database Schema

## Engine: PostgreSQL + TimescaleDB

TimescaleDB is used for `prices` and `features_daily` because they are
time-series tables with millions of rows. All other tables use standard
PostgreSQL.

---

## Table: prices

Raw OHLCV. Never modified after insert.

```sql
CREATE TABLE prices (
    symbol      VARCHAR(20)  NOT NULL,
    date        DATE         NOT NULL,
    open        NUMERIC(12,2),
    high        NUMERIC(12,2),
    low         NUMERIC(12,2),
    close       NUMERIC(12,2),
    volume      BIGINT,
    PRIMARY KEY (symbol, date)
);

SELECT create_hypertable('prices', 'date');
CREATE INDEX ON prices (symbol, date DESC);
```

---

## Table: features_daily

**The heart of the platform.** Pre-computed indicators for every symbol
every day. Never recalculate in the scoring layer — read from here.

```sql
CREATE TABLE features_daily (
    symbol              VARCHAR(20)  NOT NULL,
    date                DATE         NOT NULL,

    -- Momentum
    rsi_14              NUMERIC(6,2),
    rsi_9               NUMERIC(6,2),
    macd_line           NUMERIC(10,4),
    macd_signal         NUMERIC(10,4),
    macd_hist           NUMERIC(10,4),
    macd_hist_prev      NUMERIC(10,4),    -- yesterday's histogram

    -- Trend
    adx_14              NUMERIC(6,2),
    adx_prev            NUMERIC(6,2),
    ema_5               NUMERIC(12,2),
    ema_13              NUMERIC(12,2),
    ema_20              NUMERIC(12,2),
    ema_50              NUMERIC(12,2),
    ema_150             NUMERIC(12,2),
    ema_200             NUMERIC(12,2),

    -- Volatility
    atr_14              NUMERIC(10,4),
    bb_upper            NUMERIC(12,2),
    bb_mid              NUMERIC(12,2),
    bb_lower            NUMERIC(12,2),
    bb_width            NUMERIC(8,4),     -- (upper-lower)/mid
    bb_width_20avg      NUMERIC(8,4),     -- 20-day avg of bb_width
    bb_pct              NUMERIC(6,4),     -- where close sits in band (0-1)

    -- Volume
    volume_20avg        BIGINT,
    volume_ratio        NUMERIC(8,2),     -- today / 20-day avg

    -- Breakout signals
    high_52w            NUMERIC(12,2),
    low_52w             NUMERIC(12,2),
    pct_from_52w_high   NUMERIC(6,2),     -- negative = below high
    distance_from_52w_high NUMERIC(6,2),   -- absolute distance from 52W high
    pct_from_52w_low    NUMERIC(6,2),
    is_52w_breakout     BOOLEAN,

    -- Stochastic
    stoch_k             NUMERIC(6,2),
    stoch_d             NUMERIC(6,2),

    -- Relative strength (computed vs Nifty500 index)
    rs_vs_nifty_20d     NUMERIC(8,4),     -- stock return / nifty return
    rs_vs_nifty_60d     NUMERIC(8,4),
    rs_rank_pct         NUMERIC(6,2),     -- percentile rank in NSE500

    -- Sector relative strength
    rs_vs_sector_20d    NUMERIC(8,4),
    sector              VARCHAR(50),

    PRIMARY KEY (symbol, date)
);

SELECT create_hypertable('features_daily', 'date');
CREATE INDEX ON features_daily (symbol, date DESC);
CREATE INDEX ON features_daily (date, rs_rank_pct DESC);  -- for fast ranking
```

---

## Table: fundamentals

Quarterly financials. One row per symbol per quarter.

```sql
CREATE TABLE fundamentals (
    symbol              VARCHAR(20)  NOT NULL,
    quarter             VARCHAR(10)  NOT NULL,   -- '2024Q3'
    announced_date      DATE,                    -- when results were published

    -- P&L
    revenue_cr          NUMERIC(14,2),
    pat_cr              NUMERIC(14,2),
    ebitda_cr           NUMERIC(14,2),
    eps                 NUMERIC(10,2),

    -- Margins
    pat_margin_pct      NUMERIC(6,2),
    ebitda_margin_pct   NUMERIC(6,2),

    -- Returns
    roe                 NUMERIC(6,2),
    roce                NUMERIC(6,2),

    -- Balance sheet
    debt_equity         NUMERIC(8,2),
    current_ratio       NUMERIC(6,2),

    -- Valuation (point-in-time PE etc. — snapshot at announcement)
    pe_ratio            NUMERIC(8,2),
    pb_ratio            NUMERIC(8,2),
    market_cap_cr       NUMERIC(14,2),

    -- Shareholding
    promoter_pct        NUMERIC(6,2),
    fii_pct             NUMERIC(6,2),
    dii_pct             NUMERIC(6,2),
    mf_pct              NUMERIC(6,2),

    -- Growth (QoQ and YoY computed on insert)
    revenue_yoy_pct     NUMERIC(8,2),
    pat_yoy_pct         NUMERIC(8,2),
    eps_yoy_pct         NUMERIC(8,2),

    PRIMARY KEY (symbol, quarter)
);

-- IMPORTANT: 5-day lag rule
-- Never use fundamentals where announced_date > signal_date - 5
-- This prevents look-ahead bias in backtesting
```

---

## Table: daily_scores

Output of all three models. One row per symbol per day.

```sql
CREATE TABLE daily_scores (
    symbol              VARCHAR(20)  NOT NULL,
    date                DATE         NOT NULL,

    -- Model scores
    swing_score         NUMERIC(5,1),
    position_score      NUMERIC(5,1),
    lt_score            NUMERIC(5,1),

    -- Score component breakdown (for explainability)
    swing_momentum      NUMERIC(5,1),
    swing_volume        NUMERIC(5,1),
    swing_breakout      NUMERIC(5,1),
    swing_rs            NUMERIC(5,1),

    -- Risk levels
    stop_loss           NUMERIC(12,2),
    target_1            NUMERIC(12,2),
    target_2            NUMERIC(12,2),
    target_3            NUMERIC(12,2),
    rr_ratio            NUMERIC(5,2),

    PRIMARY KEY (symbol, date)
);
```

---

## Table: recommendation_history

**Critical for retrospective analysis.** Every daily ranking snapshot, forever.

```sql
CREATE TABLE recommendation_history (
    id                  SERIAL PRIMARY KEY,
    date                DATE         NOT NULL,
    model               VARCHAR(20)  NOT NULL,   -- 'swing'|'positional'|'lt'
    rank                INTEGER      NOT NULL,
    symbol              VARCHAR(20)  NOT NULL,

    score               NUMERIC(5,1),
    entry_price         NUMERIC(12,2),
    stop_loss           NUMERIC(12,2),
    target_1            NUMERIC(12,2),
    rr_ratio            NUMERIC(5,2),

    -- Key features at time of signal (for future research)
    rsi_14              NUMERIC(6,2),
    adx_14              NUMERIC(6,2),
    volume_ratio        NUMERIC(8,2),
    rs_rank_pct         NUMERIC(6,2),
    sector_rank         INTEGER,
    bb_width_ratio      NUMERIC(8,4),   -- bb_width / bb_width_20avg
    reason_codes        TEXT[],         -- e.g. ARRAY['vol_spike','52w_high','ema_stack']

    -- Outcome (filled in retrospectively by backtest runner)
    exit_date           DATE,
    exit_price          NUMERIC(12,2),
    exit_reason         VARCHAR(30),   -- 'stop_loss'|'target_1'|'max_hold'|'rank_decay'
    return_pct          NUMERIC(8,4),
    holding_days        INTEGER
);

CREATE INDEX ON recommendation_history (date, model, rank);
CREATE INDEX ON recommendation_history (symbol, date);
-- Enables queries like: "show me stocks ranked top-10 for 5+ consecutive days"
```

---

## Table: sector_master

Sector taxonomy. Static reference table.

```sql
CREATE TABLE sector_master (
    symbol              VARCHAR(20)  PRIMARY KEY,
    company_name        VARCHAR(100),
    sector              VARCHAR(50),
    subsector           VARCHAR(50),
    nse500              BOOLEAN DEFAULT TRUE,
    nse500_from_date    DATE,           -- when added to index
    nse500_to_date      DATE            -- NULL if currently in index
);
```

**Canonical sector list:**
```
Defence
Railways & Infra
Capital Goods
PSU Banks
Private Banks
NBFCs
IT — Large Cap
IT — Midcap
Pharma
Auto — OEM
Auto Ancillary
FMCG
Retail & Consumer
Chemicals
Metals & Mining
Power & Energy
Real Estate
EMS / Electronics
Telecom
Hospitality
```

---

## Table: portfolio_positions

Your actual holdings. Manual entry.

```sql
CREATE TABLE portfolio_positions (
    id                  SERIAL PRIMARY KEY,
    symbol              VARCHAR(20)  NOT NULL,
    quantity            INTEGER      NOT NULL,
    avg_cost            NUMERIC(12,2) NOT NULL,
    entry_date          DATE         NOT NULL,
    strategy            VARCHAR(20),   -- 'swing'|'positional'|'lt'|'manual'
    stop_loss           NUMERIC(12,2),
    target_1            NUMERIC(12,2),
    notes               TEXT,
    status              VARCHAR(10) DEFAULT 'open',   -- 'open'|'closed'
    exit_date           DATE,
    exit_price          NUMERIC(12,2)
);
```

---

## Table: backtest_runs

Track every backtest execution so results are reproducible.

```sql
CREATE TABLE backtest_runs (
    id                  SERIAL PRIMARY KEY,
    run_date            TIMESTAMP DEFAULT NOW(),
    model               VARCHAR(20),
    start_date          DATE,
    end_date            DATE,
    capital             NUMERIC(14,2),
    portfolio_size      INTEGER,

    -- Results
    total_return_pct    NUMERIC(8,2),
    cagr_pct            NUMERIC(8,2),
    max_drawdown_pct    NUMERIC(8,2),
    win_rate_pct        NUMERIC(8,2),
    sharpe_ratio        NUMERIC(6,3),
    total_trades        INTEGER,
    avg_rr              NUMERIC(6,2),

    -- Benchmark
    nifty_return_pct    NUMERIC(8,2),
    alpha_pct           NUMERIC(8,2),

    config_json         JSONB         -- full config snapshot for reproducibility
);
```

---

## Relationships

```
sector_master ──────────────→ prices
                               ↓
                          features_daily
                               ↓
fundamentals ───────────→ daily_scores ────→ recommendation_history
                               ↓
                     portfolio_positions
                               ↓
                         backtest_runs
```

---

## Table: trade_log

Every executed trade from backtests and live recommendations.
Required for all performance reports.

```sql
CREATE TABLE trade_log (
    trade_id        SERIAL PRIMARY KEY,
    symbol          VARCHAR(20)   NOT NULL,
    strategy        VARCHAR(20)   NOT NULL,   -- 'swing'|'positional'|'lt'
    entry_date      DATE          NOT NULL,
    exit_date       DATE,
    entry_price     NUMERIC(12,2) NOT NULL,
    exit_price      NUMERIC(12,2),
    quantity        INTEGER,
    stop_loss       NUMERIC(12,2),
    target_1        NUMERIC(12,2),
    score_at_entry  NUMERIC(5,1),
    exit_reason     VARCHAR(30),              -- 'stop_loss'|'target_1'|'target_2'|
                                              --  'max_hold'|'score_decay'|'manual'
    pnl_pct         NUMERIC(8,4),
    pnl_inr         NUMERIC(12,2),
    holding_days    INTEGER,
    run_type        VARCHAR(10) DEFAULT 'backtest'  -- 'backtest'|'live'
);

CREATE INDEX ON trade_log (symbol, entry_date);
CREATE INDEX ON trade_log (strategy, entry_date);
CREATE INDEX ON trade_log (run_type, exit_date);
```

---

## Table: model_version

Every version of scoring weights ever used. Enables comparing v1.0 vs v1.1
backtest results against identical historical data.

```sql
CREATE TABLE model_version (
    version_id      SERIAL PRIMARY KEY,
    version_tag     VARCHAR(20) NOT NULL,     -- 'v1.0', 'v1.1', etc.
    created_at      TIMESTAMP DEFAULT NOW(),
    model           VARCHAR(20) NOT NULL,     -- 'swing'|'positional'|'lt'
    weights_json    JSONB       NOT NULL,     -- full snapshot of SIGNAL_WEIGHTS
    notes           TEXT,                     -- reason for change
    backtest_cagr   NUMERIC(6,2),            -- filled after backtest run
    backtest_sharpe NUMERIC(6,3),            -- filled after backtest run
    is_active       BOOLEAN DEFAULT FALSE    -- only one active per model
);

CREATE UNIQUE INDEX ON model_version (model, is_active)
    WHERE is_active = TRUE;                  -- enforces single active version
```


---

## Table: sector_daily_ranks

Output of sector rotation engine. Written before features_daily scoring.

```sql
CREATE TABLE sector_daily_ranks (
    date                DATE        NOT NULL,
    sector              VARCHAR(50) NOT NULL,
    sector_return_1m    NUMERIC(8,4),
    sector_return_3m    NUMERIC(8,4),
    sector_return_6m    NUMERIC(8,4),
    composite_score     NUMERIC(8,4),
    rank_3m             INTEGER,
    rank_composite      INTEGER,        -- used by scoring models
    stock_count         INTEGER,
    PRIMARY KEY (date, sector)
);
```

---

## Amendment: features_daily — additional columns

```sql
-- Add to features_daily:
ALTER TABLE features_daily ADD COLUMN is_eligible       BOOLEAN DEFAULT TRUE;
ALTER TABLE features_daily ADD COLUMN avg_traded_value  NUMERIC(16,2);
-- is_eligible = FALSE if avg_traded_value < 10Cr OR volume_20avg < 100k OR close < 10
-- Ineligible stocks are scored NULL and excluded from rankings
```

---

## Table: universe_snapshot

Daily snapshot of NSE500 membership. Required for survivorship-bias-free
backtesting. Without this, stocks that were removed from the index
(delisted, downgraded) are invisible to historical simulation.

```sql
CREATE TABLE universe_snapshot (
    date        DATE         NOT NULL,
    symbol      VARCHAR(20)  NOT NULL,
    index_name  VARCHAR(20)  NOT NULL DEFAULT 'NSE500',
    PRIMARY KEY (date, symbol, index_name)
);

CREATE INDEX ON universe_snapshot (symbol, date DESC);
```

Populated by: `data/universe.py` — runs daily, snapshots current NSE500 list.
Backtest rule: on any given date D, only symbols present in
`universe_snapshot WHERE date = D` are eligible for ranking.

---

## Table: data_quality_log

Tracks completeness of every data ingestion job. If records_loaded
diverges from records_expected by more than 5%, status = 'partial'.

```sql
CREATE TABLE data_quality_log (
    id                SERIAL PRIMARY KEY,
    date              DATE          NOT NULL,
    job_name          VARCHAR(50)   NOT NULL,
    records_expected  INTEGER,
    records_loaded    INTEGER,
    pct_loaded        NUMERIC(5,2)  GENERATED ALWAYS AS
                        (records_loaded::numeric / NULLIF(records_expected,0) * 100) STORED,
    status            VARCHAR(20)   NOT NULL,  -- 'ok'|'partial'|'failed'
    error_message     TEXT,
    created_at        TIMESTAMP DEFAULT NOW()
);

CREATE INDEX ON data_quality_log (date, job_name);
CREATE INDEX ON data_quality_log (status) WHERE status != 'ok';
```

---

## Table: pipeline_runs

Execution log for every pipeline job. Used to monitor reliability,
detect timing drift (e.g. job finishing after 8AM), and diagnose failures.

```sql
CREATE TABLE pipeline_runs (
    run_id            SERIAL PRIMARY KEY,
    job_name          VARCHAR(50)   NOT NULL,
    run_date          DATE          NOT NULL,
    start_time        TIMESTAMP     NOT NULL,
    end_time          TIMESTAMP,
    status            VARCHAR(20)   NOT NULL,  -- 'running'|'success'|'failed'
    duration_seconds  NUMERIC(8,2)  GENERATED ALWAYS AS
                        (EXTRACT(EPOCH FROM (end_time - start_time))) STORED,
    rows_processed    INTEGER,
    error_message     TEXT
);

CREATE INDEX ON pipeline_runs (run_date, job_name);
CREATE INDEX ON pipeline_runs (status) WHERE status = 'failed';
```
