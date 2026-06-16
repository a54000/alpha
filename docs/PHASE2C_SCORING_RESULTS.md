# Phase 2C Scoring Results

Generated on: 2026-06-12

## Objective

Generate pilot-only Swing V2.1 scores using production-parity scoring logic.

Inputs:

- `angel_data.pilot_phase2a.features_daily`
- `docs/PHASE2C_SCORING_UNIVERSE_DECISION.md`
- `docs/PHASE2B_PRODUCTION_PARITY_AUDIT.md`

Official scoring start date: **2022-05-25**

This phase generated pilot scores only. It did not generate recommendations, run backtests, or modify production tables.

## Implemented Script

`scripts/run_phase2c_pilot_scoring.py`

The script imports and applies the production scoring function:

```python
from app.scoring.compute_scores import compute_swing_v2_1_score
```

It also imports production component scorers for audit columns:

```python
score_swing_v2_adx
score_swing_v2_sector
```

No new factors, weights, thresholds, or research-only filters were introduced.

## Pilot Scoring Table

Created and populated:

`angel_data.pilot_phase2a.scores_daily`

Primary key:

- `(symbol, date)`

Columns:

- `symbol`
- `date`
- `sector`
- `swing_v2_1_score`
- `adx_points`
- `sector_points`
- `ema200_extension`
- `prior_20d_return`
- `sector_rank_3m`
- `history_days`
- `production_eligible`
- `strict_warmup_eligible`
- `generated_at`

Indexes:

- `ix_phase2c_scores_date`
- `ix_phase2c_scores_symbol_date`

## Production-Parity Logic

Swing V2.1 score eligibility is controlled by production `compute_swing_v2_1_score`.

The production function returns a score only when:

- `close` is non-null
- `ema_200` is non-null
- `ema_200` is not zero
- `prior_20d_return` is non-null
- `ema200_extension <= 0.25`
- `prior_20d_return <= 0.15`

ADX and sector rank are applied exactly through production component scoring:

- `score_swing_v2_adx(adx_14, adx_prev)`
- `score_swing_v2_sector(sector_rank_3m)`

Null ADX or null sector rank would score zero under production behavior rather than blocking the row. In the Phase 2C scoring window, production-eligible rows had the needed ADX and sector rank values available.

## Reports Created

- `reports/phase2c_scoring_validation.json`
- `reports/phase2c_scoring_coverage_by_date.csv`
- `reports/phase2c_scoring_coverage_by_month.csv`
- `reports/phase2c_score_distribution_by_date.csv`
- `reports/phase2c_scoring_coverage_by_symbol.csv`

## Scoring Summary

| Metric | Value |
| --- | ---: |
| Input feature rows from start date | 279,405 |
| Pilot score rows written | 279,405 |
| Production-eligible scored rows | 235,934 |
| Symbols seen | 282 |
| Symbols scored | 282 |
| First score date | 2022-05-25 |
| Last score date | 2026-06-11 |
| Minimum score | 0.000000 |
| Median score | 22.857143 |
| Maximum score | 100.000000 |

## First Dates

| Date | Feature rows | Production eligible | Strict warmup eligible | Scored rows | Median score | Max score |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 2022-05-25 | 279 | 275 | 271 | 275 | 22.857143 | 100.000000 |
| 2022-05-26 | 279 | 274 | 270 | 274 | 28.571429 | 100.000000 |
| 2022-05-27 | 278 | 272 | 268 | 272 | 28.571429 | 100.000000 |
| 2022-05-30 | 279 | 272 | 268 | 272 | 22.857143 | 100.000000 |
| 2022-05-31 | 278 | 266 | 262 | 266 | 22.857143 | 100.000000 |

## Latest Dates

| Date | Feature rows | Production eligible | Strict warmup eligible | Scored rows | Median score | Max score |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 2026-06-04 | 281 | 255 | 255 | 255 | 11.428571 | 82.857143 |
| 2026-06-05 | 281 | 257 | 257 | 257 | 11.428571 | 77.142857 |
| 2026-06-08 | 281 | 263 | 263 | 263 | 11.428571 | 77.142857 |
| 2026-06-09 | 281 | 257 | 257 | 257 | 17.142857 | 77.142857 |
| 2026-06-10 | 281 | 258 | 258 | 258 | 11.428571 | 82.857143 |
| 2026-06-11 | 281 | 264 | 264 | 264 | 14.285714 | 77.142857 |

## Score Distribution

| Score bucket | Rows |
| --- | ---: |
| `0` | 51,504 |
| `(0,20]` | 65,172 |
| `(20,40]` | 62,724 |
| `(40,60]` | 33,071 |
| `(60,80]` | 18,894 |
| `(80,100]` | 4,569 |

The distribution is consistent with the production formula because Swing V2.1 is composed only of ADX and sector-rank points after overextension gates are applied.

## Monthly Coverage Highlights

| Month | Trading days | Avg scored rows | Min scored rows | Max scored rows | Avg score |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2022-05 | 5 | 271.80 | 266 | 275 | 28.307934 |
| 2022-06 | 22 | 266.18 | 237 | 275 | 27.490111 |
| 2022-07 | 21 | 239.95 | 198 | 274 | 23.895811 |
| 2025-12 | 22 | 268.45 | 263 | 274 | 26.627519 |
| 2026-01 | 20 | 267.55 | 258 | 276 | 29.073225 |
| 2026-03 | 19 | 272.11 | 252 | 279 | 32.508960 |
| 2026-06 | 9 | 258.11 | 255 | 264 | 17.744006 |

Lowest scored-symbol dates:

| Date | Scored symbols |
| --- | ---: |
| 2024-07-03 | 134 |
| 2024-02-07 | 152 |
| 2024-07-04 | 153 |
| 2024-02-19 | 155 |
| 2024-02-06 | 156 |

Highest scored-symbol dates:

| Date | Scored symbols |
| --- | ---: |
| 2025-02-14 | 280 |
| 2025-03-10 | 280 |
| 2025-02-28 | 279 |
| 2025-03-04 | 279 |
| 2025-03-13 | 279 |

Coverage varies by date because production Swing V2.1 excludes overextended securities using EMA200 extension and prior 20-day return filters.

## Verification

Compile check:

```powershell
.\.venv\Scripts\python.exe -m py_compile scripts/run_phase2c_pilot_scoring.py
```

Scoring run:

```powershell
.\.venv\Scripts\python.exe scripts/run_phase2c_pilot_scoring.py
```

Database verification:

```sql
SELECT
    COUNT(*) AS rows,
    COUNT(*) FILTER (WHERE swing_v2_1_score IS NOT NULL) AS scored_rows,
    COUNT(DISTINCT symbol) AS symbols,
    COUNT(DISTINCT symbol) FILTER (WHERE swing_v2_1_score IS NOT NULL) AS scored_symbols,
    MIN(date),
    MAX(date),
    MIN(swing_v2_1_score),
    percentile_cont(0.5) WITHIN GROUP (ORDER BY swing_v2_1_score),
    MAX(swing_v2_1_score)
FROM pilot_phase2a.scores_daily;
```

Observed:

- Rows: 279,405
- Scored rows: 235,934
- Symbols: 282
- Scored symbols: 282
- Date range: 2022-05-25 to 2026-06-11
- Score range: 0.000000 to 100.000000
- Median score: 22.857143

Parity assertion:

```sql
SELECT
    COUNT(*) FILTER (
        WHERE production_eligible AND swing_v2_1_score IS NULL
    ) AS eligible_without_score,
    COUNT(*) FILTER (
        WHERE NOT production_eligible AND swing_v2_1_score IS NOT NULL
    ) AS ineligible_with_score,
    COUNT(*) FILTER (
        WHERE production_eligible
          AND (swing_v2_1_score < 0 OR swing_v2_1_score > 100)
    ) AS out_of_range_scores
FROM pilot_phase2a.scores_daily;
```

Observed:

- Eligible rows without score: 0
- Ineligible rows with score: 0
- Out-of-range scores: 0

## Production Safety

Writes were limited to:

- `angel_data.pilot_phase2a.scores_daily`
- `reports/phase2c_*`

Production tables were not modified.

Not performed:

- recommendations
- backtests
- production score writes
- production feature changes
- scoring formula changes

## Phase Boundary

Phase 2C is complete once pilot scores are generated and validated.

Next phases may use these scores for recommendation simulation or backtesting, but those were intentionally not performed in Phase 2C.
