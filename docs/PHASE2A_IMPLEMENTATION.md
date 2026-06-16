# Phase 2A Implementation

Objective: build five-year validation pilot infrastructure.

Scope implemented:

- Exact-match universe extraction.
- Angel source validation framework.
- Daily-bar aggregation framework.
- Daily-bar validation framework.
- Pilot reporting framework.

Scope not implemented:

- No production research tables modified.
- No features rebuilt.
- No scores generated.
- No recommendations generated.
- No backtests run.
- No security master data loaded.
- No application cutover.

## Delivered Files

- `scripts/run_phase2a_pilot_infrastructure.py`
- `reports/phase2a_pilot_data_quality.json`
- `reports/phase2a_daily_bar_coverage.csv`
- `reports/phase2a_daily_bar_issues.csv`
- `docs/PHASE2A_IMPLEMENTATION.md`

## Pilot Schema Objects

Created in `angel_data`, not in the production research database:

```text
pilot_phase2a.exact_match_universe
pilot_phase2a.daily_bars
```

### `pilot_phase2a.exact_match_universe`

Purpose: stores the 285 exact-match securities selected from Phase 1B alias proposals.

Columns:

- `security_proposal_id`
- `research_symbol`
- `angel_symbol`
- `loaded_at`

### `pilot_phase2a.daily_bars`

Purpose: stores Angel-derived daily OHLCV bars for the 285 exact-match symbols.

Columns:

- `symbol`
- `date`
- `open`
- `high`
- `low`
- `close`
- `volume`
- `bar_count`
- `first_bar_at`
- `last_bar_at`
- `has_opening_bar`
- `has_closing_bar`
- `is_partial_day`
- `source_table`
- `created_at`

Primary key:

- `symbol, date`

Indexes:

- `date`
- `symbol, date`

## Run Command

```powershell
.\.venv\Scripts\python.exe scripts\run_phase2a_pilot_infrastructure.py
```

The script requires:

- `DATABASE_URL` in `.env`, or `ANGEL_DATABASE_URL`
- `reports/phase1b_alias_proposals.csv`
- readable `angel_data.ohlcv_15min`

## Exact-Match Universe

Selection rule:

```text
alias_reason = exact
confidence = high
review_status = approved
source aliases include both research and angel
research_symbol = angel_symbol
```

Extracted universe:

```text
285 securities
```

No potential mappings, ambiguous mappings, renames, unmatched symbols, or Angel-only symbols were used.

## Aggregation Rules

Source:

```text
angel_data.ohlcv_15min
```

Session filter:

```text
09:15 <= datetime::time <= 15:15
```

Daily OHLCV derivation:

- `open`: first 15-minute bar open by timestamp.
- `high`: max intraday high.
- `low`: min intraday low.
- `close`: last 15-minute bar close by timestamp.
- `volume`: sum of intraday volume.
- `bar_count`: count of included 15-minute bars.
- `has_opening_bar`: first bar is `09:15`.
- `has_closing_bar`: last bar is `15:15`.
- `is_partial_day`: bar count below 25.

No forward-filling or synthetic bars are used.

## Aggregation Result

Run completed successfully.

Summary:

| Metric | Value |
| --- | ---: |
| Exact-match securities | 285 |
| Aggregated daily rows | 345,618 |
| Symbols with daily bars | 285 |
| Earliest daily date | 2021-06-14 |
| Latest daily date | 2026-06-12 |
| Source duplicate groups | 0 |
| Source duplicate extra rows | 0 |
| Source duplicate affected symbols | 0 |
| Null-volume daily rows | 0 |
| Zero-volume daily rows | 0 |

## Data-Quality Results

Daily-bar validation summary:

| Check | Count |
| --- | ---: |
| Partial daily bars | 1,021 |
| Missing opening-bar days | 287 |
| Missing closing-bar days | 852 |
| Invalid OHLC daily rows | 46 |
| Null-volume daily rows | 0 |
| Zero-volume daily rows | 0 |

Issue rows exported:

```text
reports/phase2a_daily_bar_issues.csv
```

Issue counts:

| Issue type | Rows |
| --- | ---: |
| missing_closing_bar | 573 |
| missing_opening_bar | 287 |
| partial_day | 161 |
| invalid_ohlc | 46 |

Coverage report exported:

```text
reports/phase2a_daily_bar_coverage.csv
```

Worst missing-day symbols:

| Symbol | Missing trading days |
| --- | ---: |
| `YESBANK` | 628 |
| `ZEEL` | 543 |
| `ZENSARTECH` | 292 |
| `WOCKPHARMA` | 252 |
| `WHIRLPOOL` | 43 |

Worst partial-day symbols:

| Symbol | Partial days |
| --- | ---: |
| `CHOLAHLDNG` | 40 |
| `GILLETTE` | 35 |
| `3MINDIA` | 31 |
| `SUNDARMFIN` | 29 |
| `HONAUT` | 15 |

## Validation SQL

Confirm pilot tables exist:

```sql
SELECT table_schema, table_name
FROM information_schema.tables
WHERE table_schema = 'pilot_phase2a'
ORDER BY table_name;
```

Confirm universe size:

```sql
SELECT COUNT(*) AS exact_match_symbols
FROM pilot_phase2a.exact_match_universe;
```

Expected:

```text
285
```

Confirm daily row count:

```sql
SELECT COUNT(*) AS daily_rows,
       COUNT(DISTINCT symbol) AS symbols,
       MIN(date) AS earliest_date,
       MAX(date) AS latest_date
FROM pilot_phase2a.daily_bars;
```

Expected from this run:

```text
daily_rows = 345618
symbols = 285
earliest_date = 2021-06-14
latest_date = 2026-06-12
```

Confirm production research tables were not modified:

```sql
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_name IN (
    'prices_daily',
    'features_daily',
    'daily_scores',
    'recommendation_history',
    'security_master',
    'security_symbol_alias',
    'security_corporate_action_lineage'
  )
ORDER BY table_name;
```

Confirm no pilot data exists in production daily prices:

```sql
SELECT COUNT(*)
FROM prices_daily
WHERE date < DATE '2024-06-10';
```

This should remain unchanged from the pre-Phase 2A baseline.

Daily OHLC issue query:

```sql
SELECT symbol, date, open, high, low, close
FROM pilot_phase2a.daily_bars
WHERE open IS NULL OR high IS NULL OR low IS NULL OR close IS NULL
   OR high < low OR high < open OR high < close OR low > open OR low > close
   OR open <= 0 OR high <= 0 OR low <= 0 OR close <= 0
ORDER BY symbol, date;
```

Gap/coverage query:

```sql
SELECT *
FROM pilot_phase2a.daily_bars
WHERE is_partial_day
   OR NOT has_opening_bar
   OR NOT has_closing_bar
ORDER BY symbol, date;
```

## Rollback Instructions

Phase 2A only created pilot objects inside `angel_data`.

Preferred rollback:

```sql
DROP SCHEMA IF EXISTS pilot_phase2a CASCADE;
```

Report-file rollback:

Delete if desired:

- `reports/phase2a_pilot_data_quality.json`
- `reports/phase2a_daily_bar_coverage.csv`
- `reports/phase2a_daily_bar_issues.csv`

No production research table rollback is required.

## Verification Performed

Command:

```powershell
.\.venv\Scripts\python.exe scripts\run_phase2a_pilot_infrastructure.py
```

Result:

```text
exact_match_security_count = 285
aggregated_daily_rows = 345618
symbols = 285
source duplicate groups = 0
```

Generated reports:

- `reports/phase2a_pilot_data_quality.json`
- `reports/phase2a_daily_bar_coverage.csv`
- `reports/phase2a_daily_bar_issues.csv`

## Phase 2A Exit Status

Phase 2A infrastructure is complete.

Validated daily bars now exist for the exact-match pilot universe in:

```text
angel_data.pilot_phase2a.daily_bars
```

Before Phase 2B feature rebuild, resolve or explicitly accept:

- 46 invalid OHLC daily rows.
- high missing-day symbols, especially `YESBANK`, `ZEEL`, `ZENSARTECH`, `WOCKPHARMA`.
- partial-day behavior for symbols with repeated partial bars.
- whether missing opening/closing bars should exclude symbol/date from feature generation.

## Not Done

- No feature rebuild.
- No sector rank rebuild.
- No score generation.
- No recommendation generation.
- No backtest.
- No production table insert/update/delete.
- No security master load.
