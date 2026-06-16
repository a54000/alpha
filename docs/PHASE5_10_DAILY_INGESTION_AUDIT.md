# Phase 5.10 Daily Market Data Ingestion Operations Audit

## Objective

Audit how daily Angel SmartAPI market data ingestion is triggered and determine the current operational readiness of the daily paper trading pipeline.

This audit is read-only. No ingestion was run, no Angel API call was made, and no database objects or code paths were modified.

## Summary Finding

Daily ingestion is **partially implemented and manually triggered**.

The repository contains the required building blocks for incremental Angel candle sync, pilot daily-bar refresh, feature generation, scoring, recommendations, paper trading updates, monitoring, and pipeline tracking. However, no active automation was found, the latest downstream pilot data remains at `2026-06-11`, and the market has a newer trading day, `2026-06-12`.

The raw Angel 15-minute table has newer partial data through `2026-06-12 11:45:00+05:30`, but pilot daily bars, features, scores, and recommendations have not advanced beyond `2026-06-11`.

Operational classification:

**C) Partially implemented**

The pipeline can be invoked manually, but it is not currently proven as a fully automated daily process.

## Scripts Audited

### `scripts/sync_angel_daily_data.py`

Purpose:

Incrementally synchronize Angel SmartAPI 15-minute candles into `angel_data.ohlcv_15min`.

Behavior:

- Logs in to Angel SmartAPI using configured credentials.
- Reads tracked symbols from available security universe sources.
- Finds the latest candle per symbol in `ohlcv_15min`.
- Requests only missing 15-minute candles.
- Inserts candles with conflict-safe upsert semantics.
- Writes a sync report to `reports/phase3f_angel_daily_sync.json`.
- Supports dry-run mode.

Symbol source priority:

1. Approved Angel aliases from `security_symbol_alias` joined to `security_master`.
2. `pilot_phase2a.exact_match_universe`, if available.
3. Distinct symbols already present in `ohlcv_15min`.

Conflict behavior:

The script uses `ON CONFLICT (symbol, datetime) DO UPDATE`, so reruns should preserve existing candles and update matching records safely.

Manual command:

```powershell
.\.venv\Scripts\python.exe scripts\sync_angel_daily_data.py --log-level INFO
```

Dry-run command:

```powershell
.\.venv\Scripts\python.exe scripts\sync_angel_daily_data.py --dry-run --symbol-limit 5 --log-level INFO
```

### `scripts/run_daily_paper_cycle.py`

Purpose:

Runs the Phase 3F daily paper trading cycle.

Execution order:

1. Angel candle sync.
2. Phase 2A pilot daily-bar aggregation.
3. Phase 2A.1 daily-bar cleaning.
4. Phase 2B pilot feature generation.
5. Phase 2C pilot scoring.
6. Phase 2D pilot recommendation generation.
7. Paper portfolio daily update.

Manual command:

```powershell
.\.venv\Scripts\python.exe scripts\run_daily_paper_cycle.py --cycle-date 2026-06-12 --portfolio-id 1
```

Dry-run command:

```powershell
.\.venv\Scripts\python.exe scripts\run_daily_paper_cycle.py --cycle-date 2026-06-12 --portfolio-id 1 --dry-run --sync-dry-run
```

Tracking behavior:

This script writes a JSON report to `reports/phase3f_daily_cycle.json`. It does not appear to be the primary writer for the `pipeline_runs` tracking table.

### `scripts/run_full_daily_pipeline.py`

Purpose:

Runs the controlled Phase 4B full daily workflow with pipeline run tracking.

Execution order:

1. `angel_data_sync`
2. `market_data_validation`
3. `daily_bar_refresh`
4. `feature_generation`
5. `swing_v2_1_scoring`
6. `recommendation_generation`
7. `decision_journal_capture`
8. `paper_portfolio_update`
9. `monitoring_report_generation`

Manual command:

```powershell
.\.venv\Scripts\python.exe scripts\run_full_daily_pipeline.py --business-date 2026-06-12 --portfolio-id 1 --rebalance-paper
```

Dry-run command:

```powershell
.\.venv\Scripts\python.exe scripts\run_full_daily_pipeline.py --business-date 2026-06-12 --portfolio-id 1 --dry-run --sync-dry-run
```

Resume command:

```powershell
.\.venv\Scripts\python.exe scripts\run_full_daily_pipeline.py --business-date 2026-06-12 --portfolio-id 1 --resume
```

Start from a specific step:

```powershell
.\.venv\Scripts\python.exe scripts\run_full_daily_pipeline.py --business-date 2026-06-12 --portfolio-id 1 --from-step feature_generation
```

Tracking behavior:

This script records step-level execution into `pipeline_runs` using `business_date` and `step_name`. It stops downstream steps after a failure and supports safe rerun through `--resume` and `--from-step`.

## Automated Execution Mechanism

No active automation was found in the repository or Windows Task Scheduler search.

Evidence reviewed:

- Pipeline scripts exist.
- Documentation describes planned or manual daily execution.
- Repository references mention cron/scheduled daily jobs as planned or target behavior.
- Windows Task Scheduler search found no matching task for:
  - `nse-research-app`
  - `run_full_daily_pipeline`
  - `run_daily_paper_cycle`
  - `sync_angel_daily_data`

Conclusion:

The current daily process appears to require manual invocation. A production-grade scheduler is not currently confirmed.

## Required Environment Variables

### Research Database

Required:

- `DATABASE_URL`

Observed status:

- Configured.

Purpose:

Connects the API, paper trading, and pipeline tracking components to the research database.

### Angel Market Data Database

Required:

- `ANGEL_DATABASE_URL`

Observed status:

- Configured.

Purpose:

Connects ingestion and pilot market-data workflows to the Angel market data database.

### Angel SmartAPI Credentials

Required for live sync:

- `ANGEL_API_KEY`
- `ANGEL_CLIENT_ID`
- `ANGEL_PASSWORD`
- `ANGEL_TOTP_SECRET`

Observed status:

- Configured.

Usage:

`sync_angel_daily_data.py` initializes `SmartConnect`, generates a TOTP value, creates an Angel session, and calls `getCandleData` for missing 15-minute candles.

### Angel Symbol Token Map

Required for live candle fetch:

- `ANGEL_SYMBOL_TOKEN_MAP_JSON`

or:

- `ANGEL_SYMBOL_TOKEN_MAP_FILE`

Observed status:

- Not configured.

Impact:

Live incremental fetch requires Angel symbol tokens. Without a configured token map, the sync script cannot reliably request candles for tracked symbols.

### Paper Trading Configuration

Required:

- `PAPER_PORTFOLIO_ID`
- `PAPER_TRADING_DATA_SOURCE`
- `PAPER_TRADING_PILOT_SCHEMA`

Observed status:

- Configured.

Current source:

- `PAPER_TRADING_DATA_SOURCE=pilot_phase2a`

Purpose:

Aligns paper trading with the frozen Swing V2.1 pilot recommendation and price source.

## Fetch Progress Behavior

### Expected by Current Sync Script

`sync_angel_daily_data.py` expects `fetch_progress` to support these fields:

- `symbol`
- `last_attempt_at`
- `last_success_at`
- `latest_candle_at`
- `status`
- `rows_fetched`
- `rows_upserted`
- `error_message`

### Current Database State

The existing `fetch_progress` table has these fields:

- `symbol`
- `token`
- `status`
- `last_fetched_at`
- `candles_count`
- `error_msg`

Current row count:

- `471`

Current status counts:

| Status | Rows |
| --- | ---: |
| `done` | 435 |
| `retry` | 36 |

Latest progress timestamp:

- `2026-06-12 07:39:28.364098+05:30`

### Finding

There is a schema mismatch between the current `fetch_progress` table and the progress fields expected by the new daily sync script.

Risk:

If live sync is executed against this table without adaptation or migration, progress updates may fail even if candle fetching succeeds.

Classification:

Operational readiness issue.

## Current Data Freshness

### Angel 15-Minute Source

Table:

- `angel_data.ohlcv_15min`

Latest datetime:

- `2026-06-12 11:45:00+05:30`

Distinct symbols:

- `499`

Interpretation:

Angel intraday data has advanced beyond the latest pilot daily data, but appears partial for `2026-06-12`.

### Pilot Clean Daily Bars

Table:

- `pilot_phase2a.daily_bars_clean`

Latest date:

- `2026-06-11`

Rows on latest date:

- `281`

### Pilot Features

Table:

- `pilot_phase2a.features_daily`

Latest date:

- `2026-06-11`

Rows on latest date:

- `281`

### Pilot Scores

Table:

- `pilot_phase2a.scores_daily`

Latest date:

- `2026-06-11`

Rows on latest date:

- `281`

### Pilot Recommendations

Table:

- `pilot_phase2a.recommendations_daily`

Model:

- `swing_v2_1`

Latest date:

- `2026-06-11`

Rows on latest date:

- `8`

## Pipeline Tracking State

Table:

- `pipeline_runs`

Observed row count:

- `8`

Latest business date:

- `2026-06-11`

Latest tracked run:

- Phase 5.6 controlled validation run.

Tracked successful steps:

- `angel_data_sync`
- `market_data_validation`
- `daily_bar_refresh`
- `swing_v2_1_scoring`
- `recommendation_generation`
- `decision_journal_capture`
- `paper_portfolio_update`
- `monitoring_report_generation`

Notable gap:

- `feature_generation` was not present in the tracked step list for the latest run.

Interpretation:

Pipeline tracking exists, but the latest tracked run does not represent a completed automated daily ingestion for `2026-06-12`.

## Freshness Gap

Market newer trading day:

- `2026-06-12`

Latest raw Angel candle:

- `2026-06-12 11:45:00+05:30`

Latest pilot daily bars:

- `2026-06-11`

Latest features:

- `2026-06-11`

Latest scores:

- `2026-06-11`

Latest recommendations:

- `2026-06-11`

Finding:

The downstream research and paper trading data path is one trading day behind the current market context. The raw intraday table has newer data, but the daily transformation and recommendation pipeline has not completed for the newer date.

## Operational Assessment

### Is Ingestion Fully Automated?

No.

No active scheduler or automated daily trigger was found.

### Is Ingestion Manually Triggered?

Yes.

The pipeline can be invoked through the command line using either:

- `scripts/sync_angel_daily_data.py`
- `scripts/run_daily_paper_cycle.py`
- `scripts/run_full_daily_pipeline.py`

### Is Ingestion Partially Implemented?

Yes.

The implementation contains strong components:

- Incremental candle fetching.
- Conflict-safe candle upsert.
- Dry-run support.
- Full daily orchestration script.
- Pipeline run tracking.
- Resume and from-step controls.
- Pilot data source alignment for paper trading.

But operational completion is blocked by:

- No confirmed scheduler.
- Missing Angel token map configuration.
- `fetch_progress` schema mismatch.
- Latest daily bars/features/scores/recommendations stale at `2026-06-11`.
- Latest pipeline tracking does not show a completed run for `2026-06-12`.

## Recommended Next Steps

1. Decide the official daily entrypoint.

Recommended:

```powershell
.\.venv\Scripts\python.exe scripts\run_full_daily_pipeline.py --business-date <YYYY-MM-DD> --portfolio-id 1 --rebalance-paper
```

2. Fix or reconcile `fetch_progress` schema before running live sync.

Options:

- Adapt `sync_angel_daily_data.py` to the existing progress schema.
- Add a migration for the expected progress fields.
- Create a separate Phase 3F progress table if preserving historical downloader progress is required.

3. Configure Angel symbol-token mapping.

Required:

- `ANGEL_SYMBOL_TOKEN_MAP_JSON`

or:

- `ANGEL_SYMBOL_TOKEN_MAP_FILE`

4. Run a dry-run for `2026-06-12`.

Recommended dry-run:

```powershell
.\.venv\Scripts\python.exe scripts\run_full_daily_pipeline.py --business-date 2026-06-12 --portfolio-id 1 --dry-run --sync-dry-run
```

5. Add explicit automation only after dry-run and live manual run are validated.

Suggested mechanism:

- Windows Task Scheduler.

Suggested schedule:

- After market close and after Angel data availability is reliable.

6. Add scheduler-level monitoring.

Minimum checks:

- Latest raw candle date.
- Latest daily bar date.
- Latest recommendation date.
- Latest successful `pipeline_runs` row.
- Monitoring report generated.

## Conclusion

The daily ingestion and paper trading operations layer is implemented as a controllable manual workflow, but it is not yet a fully automated production operation.

The most important blockers before daily production use are:

1. Configure Angel symbol-token mapping.
2. Resolve `fetch_progress` schema mismatch.
3. Validate a full dry-run for `2026-06-12`.
4. Execute one controlled live manual run.
5. Add a scheduler only after the manual path is proven repeatable.

