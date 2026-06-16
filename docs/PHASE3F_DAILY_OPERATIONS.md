# Phase 3F Daily Operations

Generated on: 2026-06-12

## Objective

Convert Angel SmartAPI ingestion into an incremental daily pipeline that supports the frozen Swing V2.1 paper trading workflow.

## New Entry Points

- `scripts/sync_angel_daily_data.py`
- `scripts/run_daily_paper_cycle.py`
- `app.paper_trading.daily_update`

## Execution Sequence

Run the full daily cycle with:

```powershell
python scripts/run_daily_paper_cycle.py --cycle-date 2026-06-12
```

To include paper portfolio marking, pass an existing portfolio id:

```powershell
python scripts/run_daily_paper_cycle.py --cycle-date 2026-06-12 --portfolio-id 1
```

The runner executes:

1. `sync_angel_daily_data.py`
2. Phase 2A latest source validation and daily aggregation
3. Phase 2A.1 daily bar cleaning
4. Phase 2B pilot feature refresh
5. Phase 2C Swing V2.1 score computation
6. Phase 2D recommendation generation
7. Existing paper portfolio update, only when `--portfolio-id` is supplied

## Angel Sync Configuration

Required live SmartAPI environment variables:

```text
ANGEL_API_KEY
ANGEL_CLIENT_ID
ANGEL_PASSWORD
ANGEL_TOTP_SECRET
```

Database configuration:

```text
ANGEL_DATABASE_URL
```

or:

```text
DATABASE_URL
```

When only `DATABASE_URL` is present, the script derives the Angel database URL by replacing the database name with `angel_data`.

Symbol token configuration:

```text
ANGEL_SYMBOL_TOKEN_MAP_JSON
```

or:

```text
ANGEL_SYMBOL_TOKEN_MAP_FILE
```

The token map must be a JSON object:

```json
{
  "RELIANCE": "2885",
  "TCS": "11536"
}
```

Credentials and token maps are intentionally not stored in source code.

## Dependencies

Runtime dependencies:

- PostgreSQL access to `angel_data`
- `ohlcv_15min` with a unique constraint or index on `(symbol, datetime)`
- `fetch_progress` permissions for live sync progress tracking
- SmartAPI Python package for live Angel login
- `pyotp` for TOTP generation
- SQLAlchemy database connectivity
- Existing Phase 2A, Phase 2A.1, Phase 2B, Phase 2C, and Phase 2D scripts
- Existing `PaperTradingService` and paper trading tables for portfolio updates

Operational dependencies:

- Angel token map for tracked symbols
- Approved `security_symbol_alias` records, or `pilot_phase2a.exact_match_universe` fallback
- Valid `PAPER_PORTFOLIO_ID` or explicit `--portfolio-id` when paper portfolio marking is required
- No broker order credentials are needed or used

## Incremental Fetch Behavior

For each tracked symbol, the sync script:

1. Reads the latest existing candle from `ohlcv_15min`.
2. Starts the next request at `latest_candle + 15 minutes`.
3. Falls back to a short bootstrap lookback only when a symbol has no existing candles.
4. Requests candles in bounded chunks.
5. Writes using `ON CONFLICT (symbol, datetime) DO UPDATE`.
6. Updates `fetch_progress`.

This prevents full-history redownloads during normal daily operation.

## Tracked Symbol Source

Symbols are read in this order:

1. Approved Angel aliases from `security_symbol_alias` joined to active `security_master` records.
2. `pilot_phase2a.exact_match_universe` as the current pilot fallback.
3. Distinct symbols already present in `ohlcv_15min`.

This keeps Phase 3F compatible with the current pilot state while allowing the canonical security master to take over later.

## Rerun Behavior

The sync step is idempotent:

- Existing candles are preserved.
- Matching `(symbol, datetime)` rows are updated with the latest vendor values.
- Missing candles after the latest stored timestamp are requested.
- `fetch_progress` is overwritten with the latest status for each symbol.

The downstream pilot scripts are currently batch-style refreshes of pilot-only objects. They do not modify production scoring, recommendation, or price tables, but they may truncate and rebuild pilot schema outputs.

## Idempotency Rules

Angel candle sync:

- Re-running the same day is safe.
- Already stored candles are matched on `(symbol, datetime)`.
- Existing rows are updated with the latest vendor OHLCV values.
- New rows are inserted.
- No full-history fetch is performed unless `--from-date` is intentionally supplied.

Daily bars and derived artifacts:

- Phase 2A/2B/2C/2D pilot components rebuild pilot-only outputs.
- Production scoring and recommendation tables are not modified by this Phase 3F flow.
- Paper portfolio updates should be run once per cycle date per portfolio unless a rerun is intentional.

Dry run:

- `run_daily_paper_cycle.py --dry-run` does not execute subprocess steps.
- `sync_angel_daily_data.py --dry-run` reads symbol/latest-candle state and writes only the JSON report.
- Sync dry-run does not create or update `fetch_progress`.
- Sync dry-run does not call Angel and does not write candles.

## Failure Recovery

Per-symbol Angel API failures are isolated:

- A failing symbol records `failed` in `fetch_progress`.
- Other symbols continue.
- The final sync report returns a non-zero exit when any symbol fails.

Recommended recovery:

1. Inspect `reports/phase3f_angel_daily_sync.json`.
2. Identify failed symbols and error messages.
3. Re-run after fixing credentials, token map, rate limits, or API availability.
4. Use `--symbol-limit` for small validation runs.
5. Use `--dry-run` before a live retry when investigating date windows.

Partial failure handling:

- The daily runner stops at the first failed step.
- Completed prior steps remain available for inspection through their reports.
- Failed steps can be rerun after correction because sync is conflict-safe and pilot outputs are rebuildable.
- If Angel sync partially fails, do not proceed to scoring for live paper decisions until the missing symbols are reviewed or explicitly accepted.
- If validation fails after sync, investigate `phase3f_daily_bar_issues.csv` before refreshing features.

## Data Quality Checks

The daily cycle produces:

- `reports/phase3f_latest_data_validation.json`
- `reports/phase3f_daily_bar_coverage.csv`
- `reports/phase3f_daily_bar_issues.csv`
- `reports/phase3f_daily_bar_cleaning.json`
- `reports/phase3f_daily_bar_repairs.csv`
- `reports/phase3f_daily_bar_rejected_rows.csv`
- `reports/phase3f_feature_validation.json`
- `reports/phase3f_scoring_validation.json`
- `reports/phase3f_recommendation_validation.json`
- `reports/phase3f_daily_cycle.json`

Review checks:

- Latest candle date by symbol
- Missing opening bars
- Missing closing bars
- Partial sessions
- Invalid OHLC rows
- Feature null rates
- Scoring coverage by date
- Recommendation counts by date
- Paper NAV and open position counts

## Data Freshness Checks

Minimum freshness checks before using recommendations:

- `ohlcv_15min` latest timestamp should include the latest expected trading session for tracked symbols.
- Daily aggregation should produce a row for the latest trading date.
- Cleaned daily bars should not reject a broad cluster of symbols on the latest date.
- Feature validation should show non-null Swing V2.1 required fields for the latest eligible universe.
- Recommendation count should match the frozen production recommendation logic.
- Paper portfolio snapshot date should equal the requested `--cycle-date`.

Freshness warning indicators:

- Many symbols missing the latest session
- Latest candle is older than one expected trading day
- Widespread zero volume on active symbols
- Large jump in rejected daily rows
- Recommendation count drops sharply versus recent runs

## Logging

The Angel sync script uses Python logging and accepts:

```powershell
python scripts/sync_angel_daily_data.py --log-level INFO
```

Useful levels:

- `INFO`: normal daily operation
- `WARNING`: noisy vendor responses or suspicious partial completion
- `DEBUG`: troubleshooting request windows and symbol selection

The daily cycle writes a structured execution report with each step, command, status, return code, and stdout/stderr tails.

## Paper Portfolio Update

Paper update is opt-in:

```powershell
python scripts/run_daily_paper_cycle.py --cycle-date 2026-06-12 --portfolio-id 1
```

The update uses `hold_to_planned_exit` mode and calls the existing `PaperTradingService`. It does not connect broker APIs and does not place orders.

By default, the update marks the portfolio to market for the cycle date. Use the lower-level entry point with `--rebalance` when the day should also trigger a weekly rebalance:

```powershell
python -m app.paper_trading.daily_update --cycle-date 2026-06-12 --portfolio-id 1 --rebalance
```

## Dry Runs

Full cycle dry run:

```powershell
python scripts/run_daily_paper_cycle.py --cycle-date 2026-06-12 --dry-run
```

Angel sync dry run:

```powershell
python scripts/sync_angel_daily_data.py --dry-run --symbol-limit 5
```

The sync dry run reports request windows without calling Angel or writing candles.

## Constraints

Phase 3F preserves the frozen strategy boundary:

- No broker order APIs
- No orders
- No scoring changes
- No recommendation changes
- No factor changes
- No strategy rule changes
- No historical full redownload during normal operation
