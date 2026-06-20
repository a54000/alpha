# Phase 7B Nifty 500 Expansion Execution

Objective: expand the pilot data universe beyond the original exact-match set toward the token-covered Nifty 500 universe without changing strategy logic.

## Current Status

- Nifty 500 source symbols: 501
- Current pilot-ready symbols: 285
- Token-covered expansion universe prepared: 415
- Symbols requiring Angel historical candle backfill: 129
- Symbols still blocked by missing Angel token / stale symbol mapping: 86
- Batch plan: `reports/nifty500_expansion_batch_plan.json`

## Files Created

- `reports/nifty500_expansion_universe_symbols.csv`
- `reports/nifty500_needs_angel_backfill_symbols.csv`
- `reports/nifty500_backfill_batches/batch_001.csv` through `batch_006.csv`
- `reports/nifty500_backfill_batches/batch_001.txt` through `batch_006.txt`

## Backfill Commands

Dry-run one batch:

```powershell
.\.venv\Scripts\python.exe scripts\run_nifty500_backfill_batches.py `
  --to-date 2026-06-17 `
  --start-batch 1 `
  --end-batch 1
```

Live run all prepared batches:

```powershell
.\.venv\Scripts\python.exe scripts\run_nifty500_backfill_batches.py `
  --to-date 2026-06-17 `
  --execute `
  --sleep-seconds 2 `
  --sleep-between-batches 180 `
  --rate-limit-sleep-seconds 300 `
  --retries 3
```

If Angel returns an access-rate error, stop and resume later from the failed batch:

```powershell
.\.venv\Scripts\python.exe scripts\run_nifty500_backfill_batches.py `
  --to-date 2026-06-17 `
  --execute `
  --start-batch <failed_batch_number> `
  --sleep-seconds 2 `
  --sleep-between-batches 180 `
  --rate-limit-sleep-seconds 300 `
  --retries 3
```

## Pilot Refresh After Backfill

After the 129-symbol candle backfill completes, refresh pilot-only tables:

```powershell
.\.venv\Scripts\python.exe scripts\run_phase2a_pilot_infrastructure.py `
  --universe-csv reports\nifty500_expansion_universe_symbols.csv `
  --output-json reports\nifty500_phase2a_pilot_data_quality.json `
  --coverage-csv reports\nifty500_phase2a_daily_bar_coverage.csv `
  --issues-csv reports\nifty500_phase2a_daily_bar_issues.csv
```

```powershell
.\.venv\Scripts\python.exe scripts\run_phase2a1_daily_bar_cleaning.py `
  --output-json reports\nifty500_phase2a1_cleaning_audit.json `
  --rejected-csv reports\nifty500_phase2a1_rejected_daily_bars.csv `
  --repairs-csv reports\nifty500_phase2a1_repaired_daily_bars.csv
```

```powershell
.\.venv\Scripts\python.exe scripts\run_phase2b_pilot_feature_generation.py `
  --nifty500-csv data\ind_nifty500list.csv `
  --output-json reports\nifty500_phase2b_feature_validation.json `
  --coverage-csv reports\nifty500_phase2b_feature_coverage_by_symbol.csv `
  --nulls-csv reports\nifty500_phase2b_feature_null_rates.csv
```

Then re-run the expansion audit:

```powershell
.\.venv\Scripts\python.exe scripts\audit_nifty500_universe_expansion.py
```

## Validation

Expected post-backfill movement:

- `needs_angel_backfill` should fall toward zero.
- `needs_daily_aggregation` may temporarily rise until Phase 2A refresh runs.
- `needs_feature_generation` may temporarily rise until Phase 2B refresh runs.
- Final usable count should move from 285 toward 415, excluding symbols rejected by cleaning or missing enough usable candles.

## Blocker Observed

Live Angel probe for `ADVENZYMES` reached Angel but returned:

```text
Access denied because of exceeding access rate
```

The script now supports `--rate-limit-sleep-seconds` to pause longer on rate-limit/access-denied responses.

## Constraints Preserved

- No production tables are modified.
- No scoring rules are changed.
- No recommendation logic is changed.
- No broker APIs are used.
- No orders are placed.
