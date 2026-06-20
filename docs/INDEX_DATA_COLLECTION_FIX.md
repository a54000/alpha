# Index Data Collection Fix

Date: 2026-06-18

## Objective

Fix benchmark index collection so the application uses NIFTY500 data, not NIFTY50, and so the benchmark series stays current beyond 2026-06-10.

## Findings

- Benchmark storage table: `index_prices_daily`
- Application benchmark symbol: `NIFTY500`
- NIFTY500 yfinance ticker: `^CRSLDX`
- NIFTY50 yfinance ticker is now available as `NIFTY50 -> ^NSEI`, but it is not the default benchmark.
- Existing data stopped at 2026-06-10 because `scripts/backfill_index_data.py` used a hard-coded end date of 2026-06-11 and yfinance treats `end` as exclusive.
- One existing NIFTY500 row had a null close because the loader used conflict-do-nothing, so reruns could not repair existing rows.

## Changes Made

1. `app/loaders/index_loader.py`
   - Keeps `NIFTY500 -> ^CRSLDX` as the default benchmark mapping.
   - Adds explicit `NIFTY50 -> ^NSEI` mapping for diagnostics only.
   - Treats loader `end_date` as inclusive.
   - Stores yfinance cache under `.cache/yfinance`.
   - Uses conflict-safe upsert/update so refreshes can repair null or stale rows.
   - Fails clearly if yfinance returns no rows.

2. `scripts/backfill_index_data.py`
   - Adds CLI arguments:
     - `--index-name`
     - `--start-date`
     - `--end-date`
   - Defaults to `NIFTY500`.

3. `scripts/validate_index_data.py`
   - Can now run directly from PowerShell without manually setting `PYTHONPATH`.

4. `scripts/run_full_daily_pipeline.py`
   - Adds `index_data_refresh` after `angel_data_sync`.
   - Defaults benchmark refresh to `NIFTY500`.
   - Refreshes from business date minus 10 calendar days through business date.

## Validation

Command:

```powershell
.\.venv\Scripts\python.exe scripts\backfill_index_data.py --index-name NIFTY500 --start-date 2026-06-10 --end-date 2026-06-18
```

Result:

- Rows upserted: 7

Command:

```powershell
.\.venv\Scripts\python.exe scripts\validate_index_data.py
```

Result:

- Row count: 498
- Min date: 2024-06-10
- Max date: 2026-06-18
- Null close prices: 0

API-level benchmark check:

- Benchmark symbol: `NIFTY500`
- Latest available benchmark date: 2026-06-18

## Daily Operations

Manual benchmark-only refresh:

```powershell
.\.venv\Scripts\python.exe scripts\backfill_index_data.py --index-name NIFTY500 --start-date 2026-06-10 --end-date 2026-06-18
```

Full daily pipeline now includes benchmark refresh:

```powershell
.\.venv\Scripts\python.exe scripts\run_full_daily_pipeline.py --business-date 2026-06-18 --portfolio-id 1 --portfolio-size 10 --max-candidate-rank 5 --rebalance-paper
```

Dry-run verification:

```powershell
.\.venv\Scripts\python.exe scripts\run_full_daily_pipeline.py --business-date 2026-06-18 --portfolio-id 1 --dry-run --sync-dry-run
```

## Notes

- NIFTY500 remains the benchmark used by dashboard and paper portfolio reporting.
- NIFTY50 is only mapped for explicit diagnostics and should not be used for the main dashboard benchmark.
- The current benchmark table is refreshed through 2026-06-18, but paper snapshot `benchmark_close` updates only when the paper portfolio update step runs.
