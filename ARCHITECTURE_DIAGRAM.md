# NSE Research Platform - Architecture Diagram

## System Overview

The NSE Research Platform is a quantitative stock research system for Indian equity markets (NSE500). It follows a pipeline architecture that ingests market data, computes technical indicators, generates scores, produces recommendations, and backtests performance.

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           NSE RESEARCH PLATFORM                                  │
│                      Indian Equity Market Analysis System                        │
└─────────────────────────────────────────────────────────────────────────────────┘
```

## High-Level Architecture

```
┌────────────────┐    ┌────────────────┐    ┌────────────────┐
│   External     │    │   Configuration│    │   Database     │
│   Data Sources │    │   (YAML + .env) │    │  (PostgreSQL)  │
└────────┬───────┘    └────────┬───────┘    └────────┬───────┘
         │                     │                     │
         │ yfinance API        │ config.yaml         │
         │ NSE500 CSV          │ .env secrets       │
         └─────────────────────┴─────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                          PIPELINE ORCHESTRATION                                 │
│                    scripts/run_historical_pipeline.py                           │
└─────────────────────────────────────────────────────────────────────────────────┘
                               │
         ┌─────────────────────┼─────────────────────┐
         │                     │                     │
         ▼                     ▼                     ▼
┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐
│  Data Ingestion │   │ Feature Compute │   │  Sector Analysis│
│   Layer         │   │    Layer        │   │     Layer       │
└────────┬────────┘   └────────┬────────┘   └────────┬────────┘
         │                     │                     │
         ▼                     ▼                     ▼
┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐
│  Scoring Engine │   │ Recommendations │   │   Backtesting   │
│     Layer       │   │     Layer       │   │     Layer       │
└─────────────────┘   └─────────────────┘   └─────────────────┘
```

## Detailed Component Architecture

### 1. Data Ingestion Layer (`app/ingestion/`)

```
┌─────────────────────────────────────────────────────────────┐
│                    DATA INGESTION LAYER                     │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────┐    ┌─────────────────┐                │
│  │  SymbolLoader   │    │  PriceLoader    │                │
│  │                 │    │                 │                │
│  │  • Load NSE500  │    │  • yfinance API │                │
│  │    constituents │    │  • OHLCV data   │                │
│  │  • CSV parser   │    │  • Batch fetch  │                │
│  └────────┬────────┘    └────────┬────────┘                │
│           │                      │                          │
│           ▼                      ▼                          │
│  ┌─────────────────┐    ┌─────────────────┐                │
│  │ symbol_master   │    │  prices_daily    │                │
│  │  • symbol       │    │  • symbol       │                │
│  │  • company_name │    │  • date         │                │
│  │  • sector       │    │  • open/high/   │                │
│  │  • nse500 flag  │    │    low/close    │                │
│  └─────────────────┘    │  • volume       │                │
│                         └─────────────────┘                │
│                                                             │
│  ┌─────────────────┐                                        │
│  │ DataValidator   │                                        │
│  │  • Quality      │                                        │
│  │    checks       │                                        │
│  └─────────────────┘                                        │
└─────────────────────────────────────────────────────────────┘
```

### 2. Feature Computation Layer (`app/indicators/`)

```
┌─────────────────────────────────────────────────────────────┐
│                   FEATURE COMPUTATION LAYER                  │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Input: prices_daily + symbol_master                        │
│  Output: features_daily                                     │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              FeatureComputer                         │   │
│  │                                                     │   │
│  │  Technical Indicators Computed:                     │   │
│  │  • RSI (14, 9)                                      │   │
│  │  • MACD (12, 26, 9)                                 │   │
│  │  • ADX (14)                                         │   │
│  │  • EMAs (5, 13, 20, 50, 150, 200)                  │   │
│  │  • Bollinger Bands (20, 2 std)                     │   │
│  │  • ATR (14)                                         │   │
│  │  • Stochastic (14, 3, 3)                           │   │
│  │  • Volume ratios                                   │   │
│  │  • 52-week high/low                                │   │
│  │  • Relative strength vs Nifty                       │   │
│  │  • Eligibility filters (liquidity, price, history)  │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─────────────────┐                                        │
│  │ features_daily  │                                        │
│  │  • 30+ technical│                                        │
│  │    indicators   │                                        │
│  │  • eligibility   │                                        │
│  │  • sector       │                                        │
│  └─────────────────┘                                        │
└─────────────────────────────────────────────────────────────┘
```

### 3. Sector Analysis Layer (`app/sectors/`)

```
┌─────────────────────────────────────────────────────────────┐
│                    SECTOR ANALYSIS LAYER                     │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Input: prices_daily + symbol_master                         │
│  Output: sector_daily                                       │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │           SectorStrengthComputer                     │   │
│  │                                                     │   │
│  │  Sector Metrics:                                    │   │
│  │  • 1-month return (weight: 20%)                     │   │
│  │  • 3-month return (weight: 50%)                     │   │
│  │  • 6-month return (weight: 30%)                     │   │
│  │  • Composite score                                 │   │
│  │  • Sector ranking                                  │   │
│  │  • Stock count per sector                          │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─────────────────┐                                        │
│  │  sector_daily   │                                        │
│  │  • sector       │                                        │
│  │  • returns (1m, │                                        │
│  │    3m, 6m)      │                                        │
│  │  • sector_score │                                        │
│  │  • rankings     │                                        │
│  └─────────────────┘                                        │
└─────────────────────────────────────────────────────────────┘
```

### 4. Scoring Engine Layer (`app/scoring/`)

```
┌─────────────────────────────────────────────────────────────┐
│                     SCORING ENGINE LAYER                     │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Input: features_daily + sector_daily + prices_daily         │
│  Output: daily_scores                                      │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │               ScoreComputer                           │   │
│  │                                                     │   │
│  │  SWING SCORE (max ~100 points):                     │   │
│  │  • ADX trend strength (20 pts)                      │   │
│  │  • EMA alignment (10 pts)                           │   │
│  │  • RSI momentum (15 pts)                            │   │
│  │  • MACD histogram (10 pts)                          │   │
│  │  • Stochastic (5 pts)                               │   │
│  │  • Volume surge (20 pts)                            │   │
│  │  • 52-week proximity (6 pts)                        │   │
│  │  • Bollinger squeeze (4 pts)                       │   │
│  │  • Relative strength rank (10 pts)                  │   │
│  │                                                     │   │
│  │  POSITIONAL SCORE (max ~100 points):                │   │
│  │  • EMA stage (25 pts)                               │   │
│  │  • ADX trend (15 pts)                               │   │
│  │  • RS rank (18 pts)                                 │   │
│  │  • RS vs Nifty (12 pts)                            │   │
│  │  • Sector rank (20 pts)                            │   │
│  │  • Volume (10 pts)                                 │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─────────────────┐                                        │
│  │  daily_scores   │                                        │
│  │  • swing_score  │                                        │
│  │  • position_    │                                        │
│  │    score        │                                        │
│  │  • stop_loss    │                                        │
│  │  • targets      │                                        │
│  │  • rr_ratio     │                                        │
│  └─────────────────┘                                        │
└─────────────────────────────────────────────────────────────┘
```

### 5. Recommendation Layer (`app/recommendations/`)

```
┌─────────────────────────────────────────────────────────────┐
│                   RECOMMENDATION LAYER                      │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Input: daily_scores + features_daily                        │
│  Output: recommendation_history                             │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │          RecommendationGenerator                      │   │
│  │                                                     │   │
│  │  Daily Process:                                     │   │
│  │  1. Filter by eligibility                           │   │
│  │  2. Filter by minimum score                        │   │
│  │  3. Rank by score (descending)                      │   │
│  │  4. Select top N (configurable)                    │   │
│  │  5. Assign ranks (1-N)                              │   │
│  │                                                     │   │
│  │  Swing: min_score=70, top_n=20                     │   │
│  │  Positional: min_score=65, top_n=20                │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─────────────────┐                                        │
│  │recommendation_  │                                        │
│  │    history      │                                        │
│  │  • date         │                                        │
│  │  • model        │                                        │
│  │  • rank         │                                        │
│  │  • symbol       │                                        │
│  │  • score        │                                        │
│  │  • entry_price  │                                        │
│  │  • stop_loss    │                                        │
│  │  • targets      │                                        │
│  └─────────────────┘                                        │
└─────────────────────────────────────────────────────────────┘
```

### 6. Backtesting Layer (`app/backtesting/`)

```
┌─────────────────────────────────────────────────────────────┐
│                     BACKTESTING LAYER                        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Input: recommendation_history + prices_daily               │
│  Output: backtest_runs                                      │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              BacktestRunner                         │   │
│  │                                                     │   │
│  │  Process:                                           │   │
│  │  1. Load historical recommendations                 │   │
│  │  2. Load price history for symbols                 │   │
│  │  3. Calculate forward returns (5d, 10d, 20d)      │   │
│  │     for swing                                       │   │
│  │  4. Calculate forward returns (1m, 3m, 6m)        │   │
│  │     for positional                                  │   │
│  │  5. Compare against benchmark (Nifty500)            │   │
│  │  6. Compute metrics:                               │   │
│  │     - Win rate                                     │   │
│  │     - Average return                               │   │
│  │     - Median return                                │   │
│  │     - Max gain/loss                                │   │
│  │     - Alpha vs benchmark                           │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─────────────────┐                                        │
│  │  backtest_runs  │                                        │
│  │  • model        │                                        │
│  │  • start/end    │                                        │
│  │  • capital      │                                        │
│  │  • total_return │                                        │
│  │  • cagr         │                                        │
│  │  • sharpe       │                                        │
│  │  • win_rate     │                                        │
│  │  • alpha        │                                        │
│  │  • config_json  │                                        │
│  └─────────────────┘                                        │
└─────────────────────────────────────────────────────────────┘
```

## Database Schema

```
┌─────────────────────────────────────────────────────────────┐
│                      DATABASE SCHEMA                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Core Tables:                                               │
│                                                             │
│  ┌─────────────────┐  ┌─────────────────┐                  │
│  │ symbol_master   │  │ prices_daily    │                  │
│  │ • symbol (PK)   │  │ • symbol (FK)   │                  │
│  │ • company_name  │  │ • date (PK)     │                  │
│  │ • sector        │  │ • open          │                  │
│  │ • nse500        │  │ • high          │                  │
│  │                 │  │ • low           │                  │
│  └─────────────────┘  │ • close         │                  │
│                        │ • volume       │                  │
│                        └─────────────────┘                  │
│                                                             │
│  ┌─────────────────┐  ┌─────────────────┐                  │
│  │ features_daily  │  │ daily_scores    │                  │
│  │ • symbol (FK)   │  │ • symbol (FK)   │                  │
│  │ • date (PK)     │  │ • date (PK)     │                  │
│  │ • 30+ indicators│  │ • swing_score   │                  │
│  │ • eligibility   │  │ • position_    │                  │
│  │                 │  │   score         │                  │
│  └─────────────────┘  │ • stop_loss     │                  │
│                        │ • targets       │                  │
│                        └─────────────────┘                  │
│                                                             │
│  ┌─────────────────┐  ┌─────────────────┐                  │
│  │ sector_daily    │  │recommendation_  │                  │
│  │ • date (PK)     │  │    history      │                  │
│  │ • sector (PK)   │  │ • date          │                  │
│  │ • returns       │  │ • model (PK)    │                  │
│  │ • sector_score  │  │ • symbol (FK)   │                  │
│  │ • rankings      │  │ • rank          │                  │
│  └─────────────────┘  │ • score         │                  │
│                        │ • entry_price   │                  │
│  ┌─────────────────┐  │ • stop_loss     │                  │
│  │ model_version   │  │ • targets       │                  │
│  │ • version_id    │  │ • exit_date     │                  │
│  │ • version_tag   │  │ • exit_price    │                  │
│  │ • weights_json  │  │ • return_pct    │                  │
│  │ • is_active     │  └─────────────────┘                  │
│  └─────────────────┘                                        │
│                                                             │
│  ┌─────────────────┐  ┌─────────────────┐                  │
│  │ backtest_runs   │  │ trade_log       │                  │
│  │ • id (PK)       │  │ • trade_id (PK) │                  │
│  │ • model         │  │ • symbol        │                  │
│  │ • start/end     │  │ • strategy      │                  │
│  │ • total_return  │  │ • entry/exit    │                  │
│  │ • cagr          │  │ • pnl_pct       │                  │
│  │ • sharpe        │  │ • holding_days  │                  │
│  │ • alpha         │  └─────────────────┘                  │
│  └─────────────────┘                                        │
│                                                             │
│  Supporting Tables:                                         │
│  • portfolio_positions                                     │
│  • universe_snapshot                                       │
│  • pipeline_runs                                           │
│  • data_quality_log                                        │
└─────────────────────────────────────────────────────────────┘
```

## Data Flow Pipeline

```
┌─────────────────────────────────────────────────────────────┐
│                    DATA FLOW PIPELINE                        │
└─────────────────────────────────────────────────────────────┘

Step 1: Symbol Loading
  CSV (NSE500 constituents) → SymbolLoader → symbol_master table

Step 2: Price Ingestion
  yfinance API → PriceLoader → prices_daily table
  (OHLCV data for all symbols + benchmark)

Step 3: Feature Computation
  prices_daily + symbol_master → FeatureComputer → features_daily table
  (30+ technical indicators per symbol per day)

Step 4: Sector Analysis
  prices_daily + symbol_master → SectorStrengthComputer → sector_daily table
  (Sector returns, scores, rankings)

Step 5: Scoring
  features_daily + sector_daily + prices_daily → ScoreComputer → daily_scores table
  (Swing and positional scores with risk levels)

Step 6: Recommendations
  daily_scores + features_daily → RecommendationGenerator → recommendation_history table
  (Top N ranked stocks per strategy per day)

Step 7: Backtesting
  recommendation_history + prices_daily → BacktestRunner → backtest_runs table
  (Performance metrics vs benchmark)
```

## Configuration System

```
┌─────────────────────────────────────────────────────────────┐
│                   CONFIGURATION SYSTEM                      │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  configs/config.yaml (canonical configuration)             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ capital: 1_000_000                                   │   │
│  │ portfolio:                                           │   │
│  │   swing_size: 10                                     │   │
│  │   positional_size: 10                               │   │
│  │ rebalance:                                           │   │
│  │   swing: weekly                                     │   │
│  │   positional: biweekly                              │   │
│  │ ranking:                                             │   │
│  │   swing_top_n: 20                                   │   │
│  │   score_bands: {exceptional: 90, strong: 80, ...}   │   │
│  │ liquidity:                                           │   │
│  │   min_avg_traded_value_20d: 100_000_000              │   │
│  │ risk:                                                │   │
│  │   atr_period: 14                                     │   │
│  │   atr_multiplier: 1.5                                │   │
│  │ indicators:                                          │   │
│  │   rsi_primary: 14                                    │   │
│  │   macd_fast: 12, slow: 26, signal: 9                │   │
│  │ backtest:                                            │   │
│  │   start_date: "2022-01-01"                           │   │
│  │   slippage_pct: 0.002                                │   │
│  │ data:                                                │   │
│  │   price_source: yfinance                             │   │
│  │   nifty500_symbol: "^CRSLDX"                         │   │
│  │ pipeline:                                            │   │
│  │   daily_run_time: "07:00"                            │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  .env (secrets)                                            │
│  DATABASE_URL=postgresql://user:pass@host/db               │
└─────────────────────────────────────────────────────────────┘
```

## Technology Stack

```
┌─────────────────────────────────────────────────────────────┐
│                    TECHNOLOGY STACK                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Core:                                                      │
│  • Python 3.x                                               │
│  • SQLAlchemy (ORM)                                         │
│  • PostgreSQL (database)                                   │
│  • Alembic (migrations)                                    │
│                                                             │
│  Data Processing:                                           │
│  • pandas (data manipulation)                              │
│  • numpy (numerical computing)                             │
│  • pandas-ta (technical indicators)                        │
│                                                             │
│  Data Sources:                                              │
│  • yfinance (market data)                                  │
│  • Screener (fundamentals - planned)                       │
│                                                             │
│  Configuration:                                             │
│  • YAML (custom parser)                                    │
│  • python-dotenv (secrets)                                 │
│                                                             │
│  Testing:                                                   │
│  • pytest                                                  │
│                                                             │
│  UI (planned):                                              │
│  • Streamlit                                                │
└─────────────────────────────────────────────────────────────┘
```

## Key Design Principles

1. **Separation of Concerns**: Each layer has a single responsibility (ingestion, features, scoring, recommendations, backtesting)

2. **Configuration-Driven**: All parameters are in `config.yaml`, no hardcoded values in business logic

3. **Idempotent Operations**: Pipeline steps can be re-run safely using upsert logic

4. **Incremental Processing**: Each step processes only new data since last run

5. **Database-First**: All state persisted in PostgreSQL, no in-memory state

6. **Model Versioning**: Scoring models are versioned for reproducibility

7. **Benchmark Comparison**: All performance measured against Nifty500 benchmark

8. **Multi-Timeframe**: Supports swing (days), positional (weeks/months), and long-term (months) strategies

## Entry Points

1. **Historical Pipeline**: `scripts/run_historical_pipeline.py`
   - One-shot load of historical data
   - Runs all pipeline steps sequentially

2. **Daily Pipeline** (planned): Scheduled cron job
   - Incremental daily updates
   - Runs at configured time (07:00 IST)

3. **Streamlit App** (planned): `streamlit_app/`
   - Interactive dashboard
   - View recommendations, backtest results, sector performance
