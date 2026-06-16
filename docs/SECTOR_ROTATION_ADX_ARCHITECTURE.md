# Sector Rotation ADX - System Architecture

---

## System Overview

The Sector Rotation ADX system runs as a daily research and paper-trading
pipeline for NSE equities. It synchronizes Angel One market data, refreshes
daily bars and Swing V2.1 features, generates ranked recommendations, updates a
paper portfolio, and publishes monitoring/reporting output to the Research
Cockpit.

The current system is paper-trading and research-only. It does not place broker
orders. Live broker integration is explicitly out of scope until paper-trading
validation is accepted.

---

## Daily Execution Flow

```text
18:30 IST - Daily pipeline trigger
            scripts/run_full_daily_pipeline.py

            1. Angel data sync
               - Fetch only missing 15-minute candles
               - Use config/angel_symbol_token_map.csv
               - Update fetch progress and write sync report

            2. Market data validation
               - Latest trading date available
               - Missing session checks
               - Invalid OHLC checks
               - Zero-volume anomaly checks

            3. Daily bar refresh
               ohlcv_15min
                    |
                    v
               pilot_phase2a.daily_bars
                    |
                    v
               pilot_phase2a.daily_bars_clean

            4. Feature generation
               - EMA50
               - EMA200
               - EMA200 extension
               - ADX14 and ADX previous
               - Prior 20-day return
               - Sector strength and sector ranks

            5. Swing V2.1 scoring
               - Sector rank points
               - Stock ADX points
               - EMA200 extension gate
               - Prior 20-day return gate

            6. Recommendation generation
               - Rank candidates globally
               - Generate daily recommendation rows
               - Capture decision journal snapshots

            7. Paper portfolio update
               - Use configured data source
               - Enter eligible recommendations
               - Hold positions to planned exit
               - Close positions after 20 regular sessions
               - Mark NAV, PnL, cash, exposure

            8. Monitoring report generation
               - Dashboard data freshness
               - Portfolio status
               - Risk metrics
               - Strategy health
```

---

## Component Architecture

```text
                    scripts/run_full_daily_pipeline.py
                         Full Daily Orchestrator
                                  |
          +-----------------------+-----------------------+
          |                       |                       |
          v                       v                       v
 scripts/sync_angel_daily_data.py pipeline_runs      monitoring report
 Angel incremental sync          step tracking       daily_paper_report
          |
          v
 angel_data.ohlcv_15min
 Raw 15-minute candles
          |
          v
 Phase 2A aggregation / cleaning
          |
          v
 pilot_phase2a.daily_bars_clean
 Cleaned daily OHLCV
          |
          v
 scripts/run_phase2b_pilot_feature_generation.py
 Feature engine
          |
          v
 pilot_phase2a.features_daily
          |
          +-------------------------------+
          |                               |
          v                               v
 pilot_phase2a.sector_daily       app/scoring/compute_scores.py
 Sector strength/ranks            Swing V2.1 factor scoring
          |                               |
          +---------------+---------------+
                          |
                          v
          pilot_phase2a.scores_daily
                          |
                          v
          pilot_phase2a.recommendations_daily
                          |
              +-----------+-----------+
              |                       |
              v                       v
 recommendation_decision_journal  app/paper_trading/service.py
 Explanation snapshots            Paper portfolio engine
                                      |
                                      v
             paper_portfolios / paper_positions /
             paper_trades / paper_daily_snapshots
                                      |
                                      v
                         FastAPI dashboard API
                                      |
                                      v
                         Next.js Research Cockpit
```

---

## Data Flow

```text
AngelOne SmartAPI
    |
    v
angel_data.ohlcv_15min
    Raw 15-minute OHLCV
    Primary key: symbol + datetime
    |
    v
Daily aggregation
    Converts 15-minute candles into daily bars
    Applies deterministic OHLCV derivation
    |
    v
pilot_phase2a.daily_bars_clean
    Cleaned daily bar layer
    Original pilot bars are preserved
    |
    v
Feature generation
    Creates:
      ema_50
      ema_200
      ema200_extension
      prior_20d_return
      adx_14
      adx_prev
      sector_rank_3m
      sector_composite_rank
    |
    v
Sector daily table
    Equal-weight sector returns:
      return_1m = 21-session average return
      return_3m = 63-session average return
      return_6m = 126-session average return
      sector_score = 20% 1m + 50% 3m + 30% 6m
    |
    v
Scoring
    swing_v2_1_score
    adx_points
    sector_points
    production eligibility flags
    |
    v
Recommendations
    Ranked global list of candidates
    Stored in pilot_phase2a.recommendations_daily
    |
    v
Paper trading
    Rolling 10-slot portfolio simulation
    No broker order placement
```

---

## Module Responsibilities

### `scripts/run_full_daily_pipeline.py`
- Controlled top-level daily orchestrator
- Executes each pipeline step in order
- Supports dry-run, resume, and from-step execution
- Writes run status to `pipeline_runs`
- Stops downstream steps on failure
- Does not change strategy logic

### `scripts/sync_angel_daily_data.py`
- Logs into Angel SmartAPI for market data sync
- Reads tracked symbols and Angel tokens
- Fetches only missing 15-minute candles
- Uses conflict-safe inserts
- Tracks progress and API failures
- Supports dry-run and catch-up windows

### `scripts/build_angel_token_map.py`
- Builds `config/angel_symbol_token_map.csv`
- Validates token coverage for the pilot universe
- Reports missing tokens, duplicate symbols, and duplicate tokens
- Does not call trading/order APIs

### Phase 2A Daily Bar Layer
- Reads `angel_data.ohlcv_15min`
- Aggregates daily OHLCV bars
- Applies deterministic cleaning rules
- Writes pilot-only daily bar tables
- Preserves original raw candles

### `scripts/run_phase2b_pilot_feature_generation.py`
- Computes stock-level technical features
- Computes sector-level equal-weight returns and ranks
- Writes `pilot_phase2a.features_daily`
- Writes `pilot_phase2a.sector_daily`
- Uses production-parity feature definitions

### `scripts/run_phase2c_pilot_scoring.py`
- Reads `pilot_phase2a.features_daily`
- Applies frozen Swing V2.1 scoring logic
- Writes `pilot_phase2a.scores_daily`
- Does not tune weights or thresholds

### `scripts/run_phase2d_pilot_recommendations.py`
- Reads daily scores
- Produces ranked Swing V2.1 recommendations
- Writes `pilot_phase2a.recommendations_daily`
- Uses production ranking behavior

### `scripts/capture_recommendation_decision_journal.py`
- Captures explainability snapshots for recommendations
- Stores rank, score, sector, and feature values
- Powers recommendation explanation API

### `app/paper_trading/`
- Maintains paper portfolios, positions, trades, and snapshots
- Supports pilot and production data sources
- Current lifecycle: hold to planned exit
- Does not connect to broker order APIs
- Does not alter scoring or recommendations

### `app/api/`
- FastAPI read-only backend for Research Cockpit
- Exposes dashboard, recommendations, explanation, portfolio, operations,
  research metrics, attribution, and trade-analysis APIs
- Fails clearly on DB configuration errors

### `frontend/`
- Next.js Research Cockpit
- Displays dashboard, recommendations, portfolio, operations, research metrics,
  trade analysis, and rolling portfolio simulation
- Read-only; no trading controls

---

## Portfolio Engine Architecture

```text
Weekly recommendation date T
          |
          v
Entry at next regular trading session open T+1
          |
          v
Allocate equity_at_open / 10 per slot
          |
          v
Hold for 20 regular sessions
          |
          v
Exit at daily close on planned exit date
          |
          v
Record trade, PnL, cash, NAV, and snapshot
```

Rules:

- Maximum open slots: 10
- Weekly new entries: up to top 5
- Entry day counts as day 1
- Known special market sessions are excluded from hold counting
- Same-symbol re-entry is blocked while held
- Same-symbol re-entry is also blocked on the same calendar date as exit
- No intraday broker order handling in current system

---

## Current Configuration

```python
# Strategy / portfolio
MODEL = "swing_v2_1"
MINIMUM_SCORE = 70
EMA200_GATE = "ema200_extension > 0"
WEEKLY_PICKS = 5
MAX_OPEN_POSITIONS = 10
HOLDING_PERIOD = 20

# Sector strength
SECTOR_RETURN_1M_DAYS = 21
SECTOR_RETURN_3M_DAYS = 63
SECTOR_RETURN_6M_DAYS = 126
SECTOR_SCORE_WEIGHTS = {
    "return_1m": 0.20,
    "return_3m": 0.50,
    "return_6m": 0.30,
}

# Sector points
SECTOR_RANK_1_POINTS = 10
SECTOR_RANK_2_POINTS = 8
SECTOR_RANK_3_POINTS = 6
SECTOR_RANK_4_5_POINTS = 4
SECTOR_RANK_6_8_POINTS = 2
SECTOR_RANK_9_PLUS_POINTS = 0

# Execution
ENTRY = "next regular session open"
EXIT = "planned exit date close"
SPECIAL_SESSIONS_EXCLUDED = [
    "2022-10-24",
    "2023-11-12",
    "2024-03-02",
    "2024-05-18",
    "2024-11-01",
]
```

---

## Database Architecture

### Angel Market Data DB

| Object | Purpose |
|--------|---------|
| `ohlcv_15min` | Raw 15-minute Angel candles |
| `fetch_progress` | Incremental sync tracking |
| `pilot_phase2a.daily_bars` | Pilot daily aggregation output |
| `pilot_phase2a.daily_bars_clean` | Cleaned daily bars |
| `pilot_phase2a.features_daily` | Feature store |
| `pilot_phase2a.sector_daily` | Sector strength table |
| `pilot_phase2a.scores_daily` | Swing V2.1 scores |
| `pilot_phase2a.recommendations_daily` | Ranked recommendations |

### Research DB

| Object | Purpose |
|--------|---------|
| `security_master` | Canonical securities |
| `security_symbol_alias` | Symbol aliases |
| `paper_portfolios` | Paper account metadata |
| `paper_positions` | Open and closed positions |
| `paper_trades` | Paper trade ledger |
| `paper_daily_snapshots` | NAV and PnL snapshots |
| `pipeline_runs` | Orchestration status |
| `recommendation_decision_journal` | Explanation snapshots |

---

## Scheduling and Operations

Current operational entry point:

```powershell
.\.venv\Scripts\python.exe scripts\run_full_daily_pipeline.py `
  --business-date YYYY-MM-DD `
  --portfolio-id 1
```

Dry-run:

```powershell
.\.venv\Scripts\python.exe scripts\run_full_daily_pipeline.py `
  --business-date YYYY-MM-DD `
  --portfolio-id 1 `
  --dry-run `
  --sync-dry-run
```

Windows task scheduling is supported through the repository PowerShell installer,
but the scheduled task must use a valid Windows run level (`Limited` or
`Highest`). The pipeline is designed to be idempotent and resumable.

---

## Research Cockpit APIs

| Endpoint | Purpose |
|----------|---------|
| `GET /health` | API, research DB, Angel DB, portfolio status |
| `GET /dashboard` | NAV, PnL, recommendations, freshness |
| `GET /recommendations/latest` | Latest Swing V2.1 recommendations |
| `GET /recommendations/{symbol}/explanation` | Decision journal explanation |
| `GET /portfolio` | Paper portfolio state |
| `GET /trades` | Paper trade ledger |
| `GET /pipeline/status` | Latest orchestration status |
| `GET /research/metrics` | Backtest and validation summaries |
| `GET /portfolio/attribution` | Performance attribution |
| `POST /research/trade-analysis/run` | On-demand historical trade analysis |
| `GET /research/trade-analysis/{report_id}` | Trade-analysis report lookup |

---

## Error Handling Strategy

```text
Configuration errors:
  Fail at startup with clear message.

Database errors:
  Return proper API error status.
  Do not silently convert DB failures into empty payloads.

Angel API errors:
  Retry with logging.
  Mark symbol progress as failed.
  Continue other symbols where safe.

Data validation failures:
  Write report.
  Stop downstream steps if freshness or OHLC quality is unsafe.

Pipeline step failure:
  Mark failed step in pipeline_runs.
  Stop downstream steps.
  Allow resume from failed or selected step.

Paper trading errors:
  Do not place orders.
  Preserve portfolio state.
  Report skipped symbols and reasons.
```

---

## Monitoring and Alerts

Daily reports include:

- Data freshness
- Last successful sync
- Feature generation status
- Recommendation generation status
- NAV, cash, invested amount
- Realized and unrealized PnL
- Open positions
- Drawdown
- Exposure and sector concentration
- Recommendation count and score distribution
- Top-ranked stocks
- Pipeline failures and stale-data warnings

Alert conditions:

- Missing latest market data
- Zero recommendations
- Abnormal recommendation count
- Excessive concentration
- Drawdown threshold breach
- Pipeline failure
- Database connectivity failure

---

## Deployment Modes

| Mode | Behavior |
|------|----------|
| Research | Run backtests, diagnostics, reports |
| Dry-run daily | Execute pipeline without data mutation |
| Paper trading | Update simulated positions and NAV |
| Live trading | Not implemented / not permitted yet |

Live trading requires a separate approval phase, broker order API integration,
order-risk controls, kill switch, and at least 30 trading days of accepted paper
trading results.

---

## Non-Negotiable Architecture Constraints

1. Strategy scoring and recommendation logic must remain frozen unless a new
   experiment variant is explicitly created.

2. Pilot data must not be copied into production tables as a shortcut.

3. Raw Angel candles must not be overwritten or repaired in place.

4. Daily-bar cleaning must preserve lineage for repaired or rejected rows.

5. Paper trading must not connect to broker order APIs.

6. The dashboard must remain read-only.

7. Any new filter must be tested year by year before adoption.

8. Special market sessions must not count as regular holding days.

9. Same-day exit and re-entry for the same symbol is blocked.

10. Operational failures must be visible, not silently swallowed.
