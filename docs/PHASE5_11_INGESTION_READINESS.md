# Phase 5.11 Daily Market Data Pipeline Readiness

## Objective

Make the Angel daily market-data ingestion path operationally ready without changing Swing V2.1 strategy, scoring, recommendation generation, or paper trading lifecycle rules.

## Implemented Changes

### Symbol-Token Mapping

Created:

```text
config/angel_symbol_token_map.csv
```

Required columns:

| Column | Purpose |
| --- | --- |
| `symbol` | Angel/NSE symbol used by the pipeline |
| `angel_token` | Angel SmartAPI symbol token |
| `exchange` | Angel exchange code, normally `NSE` |

The daily sync script now reads this file by default. It can also be overridden with:

```powershell
--token-map-csv path\to\angel_symbol_token_map.csv
```

or:

```powershell
$env:ANGEL_SYMBOL_TOKEN_MAP_CSV="path\to\angel_symbol_token_map.csv"
```

Validation added:

- Missing required CSV column detection.
- Missing symbol/token row detection.
- Duplicate symbol detection.
- Duplicate token detection.
- Missing token detection for tracked symbols before live Angel login.

Dry-run mode reports missing token counts without calling Angel.

### Fetch Progress Compatibility

`scripts/sync_angel_daily_data.py` now supports both progress table shapes.

Current readiness fields tracked:

- `symbol`
- latest successful fetch timestamp
- status
- error
- updated timestamp or equivalent timestamp available in the existing schema

Supported schemas:

Current legacy downloader schema:

```text
symbol
token
status
last_fetched_at
candles_count
error_msg
```

Newer Phase 3F schema:

```text
symbol
last_attempt_at
last_success_at
latest_candle_at
status
rows_fetched
rows_upserted
error_message
```

The script detects the available schema and updates the compatible fields. It no longer assumes the new Phase 3F shape when the legacy table already exists.

### Catch-Up Mode

`scripts/sync_angel_daily_data.py` supports explicit catch-up windows:

```powershell
--from-date 2026-06-12
--to-date 2026-06-13T16:00:00+05:30
```

Example dry-run catch-up:

```powershell
.\.venv\Scripts\python.exe scripts\sync_angel_daily_data.py --dry-run --from-date 2026-06-12 --to-date 2026-06-13T16:00:00+05:30 --symbol-limit 10
```

Example live catch-up:

```powershell
.\.venv\Scripts\python.exe scripts\sync_angel_daily_data.py --from-date 2026-06-12 --to-date 2026-06-13T16:00:00+05:30
```

Live catch-up will fail before Angel login if tracked symbols are missing tokens.

## Required Environment Variables

Research database:

```powershell
DATABASE_URL
```

Angel market-data database:

```powershell
ANGEL_DATABASE_URL
```

Angel SmartAPI:

```powershell
ANGEL_API_KEY
ANGEL_CLIENT_ID
ANGEL_PASSWORD
ANGEL_TOTP_SECRET
```

Optional token-map override:

```powershell
ANGEL_SYMBOL_TOKEN_MAP_CSV
```

Paper trading:

```powershell
PAPER_PORTFOLIO_ID
PAPER_TRADING_DATA_SOURCE
PAPER_TRADING_PILOT_SCHEMA
```

## Setup Steps

1. Populate the token map.

Edit:

```text
config/angel_symbol_token_map.csv
```

Example:

```csv
symbol,angel_token,exchange
RELIANCE,2885,NSE
TCS,11536,NSE
```

2. Run a dry-run validation.

```powershell
.\.venv\Scripts\python.exe scripts\sync_angel_daily_data.py --dry-run --symbol-limit 20 --log-level INFO
```

3. Run a catch-up dry-run for the missing market day.

```powershell
.\.venv\Scripts\python.exe scripts\sync_angel_daily_data.py --dry-run --from-date 2026-06-12 --to-date 2026-06-13T16:00:00+05:30 --log-level INFO
```

4. Run the full daily pipeline dry-run.

```powershell
.\.venv\Scripts\python.exe scripts\run_full_daily_pipeline.py --business-date 2026-06-12 --portfolio-id 1 --dry-run --sync-dry-run
```

5. After validation, run the live sync or full daily pipeline manually.

```powershell
.\.venv\Scripts\python.exe scripts\run_full_daily_pipeline.py --business-date 2026-06-12 --portfolio-id 1 --rebalance-paper
```

## Daily Run Command

Recommended controlled daily entrypoint:

```powershell
.\.venv\Scripts\python.exe scripts\run_full_daily_pipeline.py --business-date <YYYY-MM-DD> --portfolio-id 1 --rebalance-paper
```

For a sync-only catch-up:

```powershell
.\.venv\Scripts\python.exe scripts\sync_angel_daily_data.py --from-date <YYYY-MM-DD> --to-date <YYYY-MM-DDTHH:MM:SS+05:30>
```

## Failure Recovery

### Missing Token Failure

Symptom:

The sync script fails with missing Angel tokens.

Recovery:

1. Add missing symbols to `config/angel_symbol_token_map.csv`.
2. Re-run with `--dry-run`.
3. Re-run the sync or full pipeline.

### Duplicate Token or Duplicate Symbol Failure

Symptom:

The sync script fails while validating the CSV.

Recovery:

1. Remove duplicate rows from `config/angel_symbol_token_map.csv`.
2. Verify each active symbol maps to one Angel token.
3. Re-run dry-run validation.

### Progress Table Compatibility Failure

Symptom:

The script reports an unsupported `fetch_progress` schema.

Recovery:

1. Inspect `fetch_progress` columns.
2. Confirm whether it matches the legacy downloader schema or Phase 3F schema.
3. Add an explicit compatibility branch before live execution if a third shape is present.

Do not manually patch progress rows as a substitute for a schema fix.

### Partial Pipeline Failure

Recovery:

Use the full orchestrator resume controls:

```powershell
.\.venv\Scripts\python.exe scripts\run_full_daily_pipeline.py --business-date <YYYY-MM-DD> --portfolio-id 1 --resume
```

or:

```powershell
.\.venv\Scripts\python.exe scripts\run_full_daily_pipeline.py --business-date <YYYY-MM-DD> --portfolio-id 1 --from-step <step_name>
```

## Verification

Tests added for:

- CSV token-map loading.
- Duplicate token-map validation.
- Missing-token detection.
- Catch-up argument parsing.
- Legacy `fetch_progress` compatibility routing.

Recommended test command:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_phase3f_daily_pipeline.py
```

## Automation Status

No scheduler was added in this phase.

The pipeline is now prepared for manual daily operation and future scheduling, but scheduled execution should only be added after:

1. Token map is fully populated.
2. Dry-run validation passes.
3. One live manual daily run succeeds.
4. Recovery and rerun behavior is verified.

