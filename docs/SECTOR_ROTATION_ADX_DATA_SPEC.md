# Sector Rotation ADX - Data Specification

---

## Data Sources

### Primary Historical Source: `angel_data`

Historical OHLCV data from Angel One SmartAPI, stored in PostgreSQL.

This is the primary source for:

```text
1. 15-minute candles
2. daily bar aggregation
3. feature generation
4. Swing V2.1 scoring
5. recommendation generation
6. portfolio backtesting
7. paper trading market prices
```

### Live / Incremental Source: Angel One SmartAPI

Daily operations use Angel SmartAPI to fetch only missing 15-minute candles.

Incremental sync entry point:

```text
scripts/sync_angel_daily_data.py
```

Instrument token source:

```text
config/angel_symbol_token_map.csv
```

### Research Database

The research database stores:

```text
1. security master
2. symbol aliases
3. paper portfolios
4. paper positions
5. paper trades
6. pipeline run tracking
7. recommendation decision journal
```

The research DB is not the primary source for Angel candles.

---

## Database Layout

```text
PostgreSQL
|
|-- angel_data
|   |-- ohlcv_15min
|   |-- fetch_progress
|   |-- pilot_phase2a.daily_bars
|   |-- pilot_phase2a.daily_bars_clean
|   |-- pilot_phase2a.features_daily
|   |-- pilot_phase2a.sector_daily
|   |-- pilot_phase2a.scores_daily
|   |-- pilot_phase2a.recommendations_daily
|
|-- nse_research_platform
|   |-- security_master
|   |-- security_symbol_alias
|   |-- paper_portfolios
|   |-- paper_positions
|   |-- paper_trades
|   |-- paper_daily_snapshots
|   |-- pipeline_runs
|   |-- recommendation_decision_journal
```

---

## Raw 15-Minute OHLCV Schema

### Table: `angel_data.ohlcv_15min`

```text
Column      Type              Description
------------------------------------------------------------
datetime    timestamptz        Bar timestamp
symbol      text               NSE/Angel trading symbol
open        numeric(12,2)      Bar open
high        numeric(12,2)      Bar high
low         numeric(12,2)      Bar low
close       numeric(12,2)      Bar close
volume      bigint             Bar volume
```

Primary key:

```text
(symbol, datetime)
```

Expected regular-session bars:

```text
09:15 to 15:15
25 bars per full trading day
```

Important execution mapping:

```text
Entry fill = OPEN of 09:15 bar on entry date
Exit fill  = CLOSE of 15:15 bar on planned exit date
```

---

## Daily Bar Schema

### Table: `pilot_phase2a.daily_bars_clean`

```text
Column      Description
------------------------------------------------------------
symbol      NSE/Angel symbol
date        Trading date
open        First valid intraday open, normally 09:15 open
high        Max intraday high
low         Min intraday low
close       Last complete-session close, normally 15:15 close
volume      Sum of intraday volume
```

The cleaned table is a deterministic layer over raw/pilot daily bars.

Rules:

```text
1. Do not modify raw 15-minute candles.
2. Preserve lineage for repaired or rejected rows.
3. Use cleaned daily bars for features, scores, recommendations, and backtests.
```

---

## Feature Schema

### Table: `pilot_phase2a.features_daily`

```text
Column                  Description
------------------------------------------------------------
symbol                  Trading symbol
date                    Trading date
sector                  Sector classification
open                    Daily open
high                    Daily high
low                     Daily low
close                   Daily close
volume                  Daily volume
ema_50                  50-period EMA of close
ema_200                 200-period EMA of close
ema200_extension        (close - ema_200) / ema_200
prior_20d_return        close / close.shift(20) - 1
adx_14                  Wilder-style ADX14
adx_prev                Previous ADX value
sector_rank             Composite sector rank
sector_rank_3m          Sector rank by 3-month return
sector_composite_rank   Composite sector rank
history_days            Available history rows
has_ema200_warmup       Boolean maturity flag
has_prior20_warmup      Boolean maturity flag
has_adx_warmup          Boolean maturity flag
generated_at            Feature generation timestamp
```

Feature rules:

```text
1. Features must be computed from daily_bars_clean.
2. Rolling/EMA calculations must be forward-only.
3. Feature values on date T must not use data after T.
4. Warmup rows may exist, but scoring eligibility must handle maturity.
```

---

## Sector Data Schema

### Table: `pilot_phase2a.sector_daily`

```text
Column          Description
------------------------------------------------------------
date            Trading date
sector          Sector name
return_1m       Equal-weight 21-session constituent return
return_3m       Equal-weight 63-session constituent return
return_6m       Equal-weight 126-session constituent return
sector_score    Weighted sector score
sector_rank     Rank by sector_score
rank_3m         Rank by return_3m
rank_composite  Rank by sector_score
stock_count     Number of symbols in sector universe
generated_at    Generation timestamp
```

### Sector Return Calculation

For each sector:

```text
return_1m = mean(close_today / close_21_sessions_ago  - 1)
return_3m = mean(close_today / close_63_sessions_ago  - 1)
return_6m = mean(close_today / close_126_sessions_ago - 1)
```

Only symbols with both current and lookback closes are included.

This is:

```text
equal-weighted
not market-cap weighted
not turnover weighted
```

### Sector Score

```text
sector_score = 0.20 * return_1m
             + 0.50 * return_3m
             + 0.30 * return_6m
```

Swing V2.1 primarily uses:

```text
sector_rank_3m
```

---

## Score Schema

### Table: `pilot_phase2a.scores_daily`

```text
Column                  Description
------------------------------------------------------------
symbol                  Trading symbol
date                    Trading date
sector                  Sector
swing_v2_1_score        Final Swing V2.1 score
adx_points              Stock ADX contribution
sector_points           Sector rank contribution
ema200_extension        EMA200 extension feature
prior_20d_return        Prior 20-session return
sector_rank_3m          Sector rank used by score
history_days            Feature history count
production_eligible     Production-parity eligibility flag
strict_warmup_eligible  Strict warmup eligibility flag
generated_at            Score generation timestamp
```

Scoring must use production-parity Swing V2.1 functions.

Do not add factors to this table without creating a new model/variant.

---

## Recommendation Schema

### Table: `pilot_phase2a.recommendations_daily`

```text
Column      Description
------------------------------------------------------------
date        Recommendation date
model       Model name
rank        Rank within date/model
symbol      Trading symbol
score       Swing V2.1 score
sector      Sector
```

Current model:

```text
swing_v2_1
```

Rolling 10 research variant uses score rows with:

```text
swing_v2_1_score >= 70
ema200_extension > 0
```

and then ranks globally by score.

---

## Symbol and Token Mapping

### Angel Token Map

File:

```text
config/angel_symbol_token_map.csv
```

Schema:

```text
symbol
angel_token
exchange
instrument_type
expiry
```

Validation rules:

```text
1. No missing token for tracked symbols.
2. No duplicate symbol rows.
3. No duplicate token rows for active equity mappings.
4. Exchange must be valid for the instrument.
5. Pilot universe coverage must be reported.
```

### Security Master

Research DB canonical security infrastructure:

```text
security_master
security_symbol_alias
```

Purpose:

```text
1. Normalize symbols.
2. Preserve alias and corporate-action lineage.
3. Separate economic identity from vendor symbol strings.
```

Current strategy still consumes pilot symbols directly. Full security-master
cutover must be handled as a separate migration/cutover phase.

---

## Data Loader and Pipeline Specifications

### `scripts/sync_angel_daily_data.py`

Input:

```text
ANGEL_DATABASE_URL
Angel SmartAPI credentials
config/angel_symbol_token_map.csv
tracked symbol universe
```

Behavior:

```text
1. Login to Angel SmartAPI.
2. For each tracked symbol, find latest candle in ohlcv_15min.
3. Fetch only missing 15-minute candles.
4. Upsert candles conflict-safely.
5. Update fetch progress.
6. Write sync report.
```

Required modes:

```text
--dry-run
--from-date
--to-date
--symbol-limit
```

### Daily Paper Cycle

Entry point:

```text
scripts/run_daily_paper_cycle.py
```

Execution order:

```text
1. sync Angel candles
2. validate latest data
3. update daily bars
4. refresh features
5. compute Swing V2.1 scores
6. generate recommendations
7. update paper portfolio
```

### Full Pipeline Orchestrator

Entry point:

```text
scripts/run_full_daily_pipeline.py
```

Features:

```text
--dry-run
--resume
--from-step
pipeline_runs tracking
stop downstream steps on failure
```

---

## Data Quality Rules

### Mandatory Checks

Reject or stop downstream processing if:

```text
1. high < low
2. open outside [low, high]
3. close outside [low, high]
4. negative price
5. negative volume
6. missing latest trading date for required universe
7. duplicate symbol/datetime raw candle rows
8. token map missing required symbols
```

### Warning Checks

Log and report:

```text
1. volume = 0 on a trading session
2. incomplete 15-minute session
3. missing 09:15 opening bar
4. missing 15:15 closing bar
5. price gap suggesting unadjusted corporate action
6. symbol with short history
7. sudden > 20% daily move
8. sector with too few valid constituents
```

### Minimum Data Requirements

```text
EMA200:              200 rows preferred
prior_20d_return:    20 prior rows
ADX14:               sufficient Wilder warmup
sector_return_1m:    21-session lookback
sector_return_3m:    63-session lookback
sector_return_6m:    126-session lookback
pilot scoring start: documented in Phase 2C
```

---

## Data Refresh Schedule

Recommended daily schedule:

```text
18:30 IST
  Run full daily pipeline after market data should be available.

Daily pipeline:
  scripts/run_full_daily_pipeline.py

Dry-run command:
  .\.venv\Scripts\python.exe scripts\run_full_daily_pipeline.py `
    --business-date YYYY-MM-DD `
    --portfolio-id 1 `
    --dry-run `
    --sync-dry-run

Live paper command:
  .\.venv\Scripts\python.exe scripts\run_full_daily_pipeline.py `
    --business-date YYYY-MM-DD `
    --portfolio-id 1
```

Scheduling on Windows should use Task Scheduler with a valid run level:

```text
Limited
```

or:

```text
Highest
```

Do not use invalid run levels such as `LeastPrivilege`.

---

## Corporate Actions Handling

Current known limitation:

```text
The Angel historical dataset may not be fully corporate-action adjusted.
```

Required checks:

```text
1. inspect visible split/bonus gaps,
2. compare suspicious price drops against corporate-action history,
3. flag unadjusted symbols,
4. avoid deriving conclusions from uncorrected discontinuities.
```

Important:

```text
Do not manually repair raw ohlcv_15min rows.
Use cleaned/derived layers with lineage if a repair framework is approved.
```

For current strategy research, corporate-action risk must be disclosed in
backtest interpretation.

---

## Survivorship Bias Handling

Current known limitation:

```text
The Angel dataset is not fully survivorship-bias corrected.
```

Observed missing examples:

```text
RCOM
DHFL
PCJEWELLER
```

Implication:

```text
Long-history backtests may overstate robustness if delisted or removed symbols
are absent from historical universes.
```

Required disclosure:

```text
Every five-year strategy report must state that the pilot universe is not fully
survivorship-bias corrected unless missing historical constituents are loaded.
```

---

## Backtesting Data Rules

```text
1. Signals on date T use only data available through T.
2. Entry occurs at open of next regular session T+1.
3. Exit occurs at close on planned regular-session exit date.
4. Special sessions are excluded from holding-period counts.
5. Existing positions complete planned hold unless variant says otherwise.
6. No future recommendations are visible to earlier dates.
7. No production tables are modified by research backtests.
8. Every research variant writes separate artifacts.
```

Look-ahead controls:

```text
1. Feature formulas must be rolling/forward-only.
2. Recommendation generation groups by date.
3. Portfolio engine must not access future rank changes for current entries.
4. Trade reconstruction must use entry and exit dates only.
```

---

## Data Freshness Rules

Dashboard and paper trading must expose:

```text
latest 15-minute candle timestamp
latest daily bar date
latest feature date
latest score date
latest recommendation date
latest pipeline run status
paper portfolio status
```

Freshness states:

```text
GREEN   all current
YELLOW  delayed but recoverable
RED     stale or failed
```

Do not convert database failures into empty successful API responses.

---

## Adding New Data Sources

When adding new data:

```text
1. Document the source and schema here.
2. Add validation checks.
3. Keep raw data immutable where possible.
4. Store derived data separately from raw data.
5. Add freshness reporting.
6. Update strategy spec only if signal logic changes.
7. Add tests for loader and validation behavior.
```

Examples of future sources:

```text
Nifty50/Nifty500 benchmark data
corporate actions feed
NSE bhavcopy
official index membership history
sector-level benchmark indices
```

Any new source used for signal generation must be point-in-time safe.
