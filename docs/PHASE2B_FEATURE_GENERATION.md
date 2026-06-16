# Phase 2B Feature Generation

Generated on: 2026-06-12

## Objective

Phase 2B creates pilot-only feature infrastructure for the five-year Swing V2.1 validation using `pilot_phase2a.daily_bars_clean`.

This phase generated features only. It did not generate scores, recommendations, or backtests, and it did not modify production feature tables.

## Inputs

- `angel_data.pilot_phase2a.daily_bars_clean`
- Research database `symbol_master` for sector metadata
- Swing V2.1 scoring dependency review in `app/scoring/compute_scores.py`
- Production feature definition review in `app/indicators/compute_features.py`

## Implemented Script

`scripts/run_phase2b_pilot_feature_generation.py`

The script:

1. Loads cleaned pilot daily bars from `angel_data`.
2. Loads sector metadata from the research database.
3. Computes symbol-level features by symbol/date.
4. Computes sector-level returns and ranks by date.
5. Writes pilot-only feature tables in `angel_data.pilot_phase2a`.
6. Writes validation reports under `reports/`.

## Pilot Schema Objects

### `pilot_phase2a.features_daily`

Primary key: `(symbol, date)`

Columns:

- `symbol`
- `date`
- `sector`
- `open`
- `high`
- `low`
- `close`
- `volume`
- `ema_50`
- `ema_200`
- `ema200_extension`
- `prior_20d_return`
- `adx_14`
- `adx_prev`
- `sector_rank`
- `sector_rank_3m`
- `sector_composite_rank`
- `history_days`
- `has_ema200_warmup`
- `has_prior20_warmup`
- `has_adx_warmup`
- `generated_at`

Indexes:

- `ix_phase2b_features_date`
- `ix_phase2b_features_symbol_date`

### `pilot_phase2a.sector_daily`

Primary key: `(date, sector)`

Columns:

- `date`
- `sector`
- `return_1m`
- `return_3m`
- `return_6m`
- `sector_score`
- `sector_rank`
- `rank_3m`
- `rank_composite`
- `stock_count`
- `generated_at`

Indexes:

- `ix_phase2b_sector_date`

## Feature Definitions

### EMA50

Computed per symbol as:

```text
close.ewm(span=50, adjust=False).mean()
```

### EMA200

Computed per symbol as:

```text
close.ewm(span=200, adjust=False).mean()
```

### EMA200 Extension

Computed per symbol/date as:

```text
(close - ema_200) / ema_200
```

### Prior 20d Return

Computed per symbol as:

```text
close / close.shift(20) - 1
```

### ADX

Computed per symbol using the same Wilder-style EWM method used by production feature generation:

- true range from high/low/previous close
- directional movement from high/low changes
- Wilder EWM smoothing with `alpha = 1 / 14`
- `adx_prev` as the prior trading row's `adx_14`

### Sector Rank Inputs

For each sector/date:

- `return_1m`: mean symbol return over 21 trading rows
- `return_3m`: mean symbol return over 63 trading rows
- `return_6m`: mean symbol return over 126 trading rows
- `sector_score`: weighted blend of 1m, 3m, and 6m returns
- `rank_3m`: per-date rank of `return_3m`, lower is stronger
- `rank_composite`: per-date rank of `sector_score`, lower is stronger

Swing V2.1 consumes the 3-month sector rank path, equivalent to production `SectorDaily.rank_3m`.

## Swing V2.1 Dependency Coverage

The scoring code shows direct Swing V2.1 requirements:

- `close`
- `ema_200`
- `prior_20d_return`
- `adx_14`
- `adx_prev`
- `sector_rank_3m`

The phase also generated `ema_50` and `ema200_extension` because they were explicitly requested and support pilot diagnostics.

## Validation Results

Reports created:

- `reports/phase2b_feature_validation.json`
- `reports/phase2b_feature_coverage_by_symbol.csv`
- `reports/phase2b_feature_null_rates.csv`

Summary:

- Feature rows: 344,597
- Symbols: 285
- Date range: 2021-06-14 to 2026-06-11
- Sector rows: 20,944
- Sectors: 17
- Feature dates: 1,232

Null-rate analysis:

| Feature | Null rows | Null pct |
| --- | ---: | ---: |
| `ema_50` | 0 | 0.0000% |
| `ema_200` | 0 | 0.0000% |
| `ema200_extension` | 0 | 0.0000% |
| `prior_20d_return` | 5,700 | 1.6541% |
| `adx_14` | 374 | 0.1085% |
| `adx_prev` | 659 | 0.1912% |
| `sector_rank_3m` | 0 | 0.0000% |

Lookback sufficiency:

- Rows with EMA200 warmup: 288,070
- Rows with prior-20d warmup: 338,897
- Rows with ADX warmup: 336,902

The nulls in prior-20d return and ADX are expected warmup effects. They should be handled by the scoring phase as unavailable early-history features, not repaired.

## Symbols With Shortest Feature Histories

The shortest pilot histories are:

| Symbol | Rows | First date | Last date | EMA200-ready rows |
| --- | ---: | --- | --- | ---: |
| WIPRO | 44 | 2021-12-13 | 2022-02-11 | 0 |
| TATASTEEL | 166 | 2021-06-14 | 2022-02-10 | 0 |
| TATACHEM | 207 | 2021-06-14 | 2022-04-12 | 8 |
| YESBANK | 410 | 2021-06-14 | 2025-08-14 | 211 |
| ZEEL | 695 | 2021-06-14 | 2026-06-11 | 496 |

These rows remain in the pilot feature table because Phase 2B is feature generation, not scoring eligibility or backtest filtering.

## Validation Queries

```sql
SELECT
    COUNT(*) AS feature_rows,
    COUNT(DISTINCT symbol) AS symbols,
    MIN(date) AS first_date,
    MAX(date) AS last_date
FROM pilot_phase2a.features_daily;
```

```sql
SELECT
    COUNT(*) AS sector_rows,
    COUNT(DISTINCT sector) AS sectors,
    MIN(date) AS first_date,
    MAX(date) AS last_date
FROM pilot_phase2a.sector_daily;
```

```sql
SELECT
    COUNT(*) AS required_null_rows
FROM pilot_phase2a.features_daily
WHERE ema_50 IS NULL
   OR ema_200 IS NULL
   OR ema200_extension IS NULL
   OR sector_rank_3m IS NULL;
```

Observed result for required null rows: `0`.

## Production Safety

Writes were limited to:

- `angel_data.pilot_phase2a.features_daily`
- `angel_data.pilot_phase2a.sector_daily`
- `reports/phase2b_*`

Production tables were not modified. The research database was read only for `symbol_master` sector metadata.

## Verification Commands

```powershell
.\.venv\Scripts\python.exe scripts/run_phase2b_pilot_feature_generation.py
```

```powershell
.\.venv\Scripts\python.exe -m py_compile scripts/run_phase2b_pilot_feature_generation.py
```

Both commands completed successfully.

## Phase Boundary

Phase 2B ends with pilot features fully populated and validated.

Not performed:

- score generation
- recommendation generation
- backtests
- production feature-table writes
- production code-path cutover
