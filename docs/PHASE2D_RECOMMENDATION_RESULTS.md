# Phase 2D Recommendation Results

Generated on: 2026-06-12

## Objective

Generate pilot-only Swing V2.1 recommendations using production recommendation logic.

Inputs:

- `angel_data.pilot_phase2a.scores_daily`
- production recommendation logic in `app/recommendations/generate_recommendations.py`

This phase generated pilot recommendation rows only. It did not run backtests, perform portfolio simulation, generate trades, or modify production tables.

## Implemented Script

`scripts/run_phase2d_pilot_recommendations.py`

The script imports production recommendation objects:

```python
from app.recommendations.generate_recommendations import (
    SWING_V2_1_RECOMMENDATION_CONFIG,
    rank_recommendations,
)
```

No ranking rules, thresholds, portfolio sizes, or filters were changed.

## Production Logic Applied

Production Swing V2.1 recommendation config:

| Field | Value |
| --- | --- |
| Recommendation type | `swing_v2_1` |
| Score field | `swing_v2_1_score` |
| Minimum score | `70.0` |
| Top N | `20` |
| Ranking | score descending, symbol ascending for ties |

Pilot equivalent:

- Candidates are rows in `pilot_phase2a.scores_daily` with non-null `swing_v2_1_score`.
- Qualified candidates require `swing_v2_1_score >= 70`.
- Recommendations are capped at 20 per date.
- Ties are broken by symbol ascending, matching `rank_recommendations`.

The production generator also excludes `FeaturesDaily.is_eligible IS false`. The pilot score table has no false eligibility flag because the Phase 2 pilot universe is already pre-filtered and production-eligible scoring was handled in Phase 2C.

## Pilot Recommendation Table

Created and populated:

`angel_data.pilot_phase2a.recommendations_daily`

Primary key:

- `(date, model, symbol)`

Unique rank constraint:

- `(date, model, rank)`

Columns:

- `date`
- `model`
- `rank`
- `symbol`
- `score`
- `sector`
- `adx_points`
- `sector_points`
- `ema200_extension`
- `prior_20d_return`
- `sector_rank_3m`
- `production_eligible`
- `strict_warmup_eligible`
- `generated_at`

Indexes:

- `ix_phase2d_recommendations_date`
- `ix_phase2d_recommendations_symbol`

## Reports Created

- `reports/phase2d_recommendation_validation.json`
- `reports/phase2d_recommendation_coverage_by_date.csv`
- `reports/phase2d_recommendations_by_symbol.csv`
- `reports/phase2d_recommendation_score_distribution.csv`

## Recommendation Summary

| Metric | Value |
| --- | ---: |
| Score dates seen | 998 |
| Recommendation dates | 990 |
| Recommendation rows | 13,654 |
| Symbols recommended | 282 |
| First recommendation date | 2022-05-25 |
| Last recommendation date | 2026-06-11 |
| Minimum recommendation score | 70.0 |
| Top N cap | 20 |
| Average recommendations per score date | 13.68 |
| Score dates with zero recommendations | 8 |

The 8 zero-recommendation dates are valid production behavior: no symbol reached the minimum score of 70 on those dates.

## Score Distribution Of Recommendations

| Score bucket | Rows |
| --- | ---: |
| `[70,80)` | 9,091 |
| `[80,90)` | 3,353 |
| `[90,100]` | 1,210 |

Overall recommendation score range:

- Minimum: 71.428571
- Median: 77.142857
- Maximum: 100.000000

## Coverage By Date

First generated dates:

| Date | Scored rows | Qualified rows | Recommendations | Expected recommendations | Median recommendation score |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2022-05-25 | 275 | 34 | 20 | 20 | 75.714286 |
| 2022-05-26 | 274 | 41 | 20 | 20 | 77.142857 |
| 2022-05-27 | 272 | 27 | 20 | 20 | 72.857143 |
| 2022-05-30 | 272 | 20 | 20 | 20 | 71.428571 |
| 2022-05-31 | 266 | 18 | 18 | 18 | 77.142857 |

Latest generated dates:

| Date | Scored rows | Qualified rows | Recommendations | Expected recommendations | Median recommendation score |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2026-06-04 | 255 | 4 | 4 | 4 | 74.285714 |
| 2026-06-05 | 257 | 10 | 10 | 10 | 72.857143 |
| 2026-06-08 | 263 | 13 | 13 | 13 | 71.428571 |
| 2026-06-09 | 257 | 10 | 10 | 10 | 71.428571 |
| 2026-06-10 | 258 | 7 | 7 | 7 | 71.428571 |
| 2026-06-11 | 264 | 8 | 8 | 8 | 71.428571 |

## Top Recommended Symbols

| Symbol | Recommendation count | First date | Last date | Best rank | Avg rank | Avg score |
| --- | ---: | --- | --- | ---: | ---: | ---: |
| ATUL | 125 | 2022-05-25 | 2026-05-15 | 1 | 6.10 | 78.0343 |
| AIAENG | 116 | 2022-06-20 | 2026-06-08 | 1 | 5.01 | 82.6355 |
| HONAUT | 111 | 2022-05-25 | 2026-06-08 | 1 | 7.58 | 80.5148 |
| BAJFINANCE | 108 | 2022-11-24 | 2025-10-27 | 1 | 7.68 | 79.7354 |
| CRISIL | 105 | 2023-02-09 | 2026-03-27 | 1 | 7.02 | 77.9592 |
| WHIRLPOOL | 103 | 2022-08-05 | 2026-01-14 | 4 | 13.23 | 72.3717 |
| MRF | 99 | 2022-06-22 | 2026-02-02 | 1 | 10.35 | 76.9697 |
| ACC | 97 | 2022-09-06 | 2026-03-30 | 1 | 8.92 | 75.7879 |
| HINDALCO | 97 | 2022-06-13 | 2026-06-04 | 1 | 5.64 | 85.0074 |
| BLUEDART | 96 | 2022-07-08 | 2026-04-07 | 1 | 8.63 | 76.3095 |

## Monthly Coverage Examples

Early months:

| Month | Recommendation rows | Recommendation dates | Symbols |
| --- | ---: | ---: | ---: |
| 2022-05 | 98 | 5 | 39 |
| 2022-06 | 404 | 22 | 68 |
| 2022-07 | 248 | 21 | 67 |
| 2022-08 | 362 | 20 | 89 |
| 2022-09 | 287 | 22 | 70 |

Latest months:

| Month | Recommendation rows | Recommendation dates | Symbols |
| --- | ---: | ---: | ---: |
| 2026-02 | 204 | 21 | 52 |
| 2026-03 | 371 | 19 | 79 |
| 2026-04 | 88 | 13 | 43 |
| 2026-05 | 130 | 19 | 38 |
| 2026-06 | 61 | 9 | 19 |

## Verification

Compile check:

```powershell
.\.venv\Scripts\python.exe -m py_compile scripts/run_phase2d_pilot_recommendations.py
```

Recommendation run:

```powershell
.\.venv\Scripts\python.exe scripts/run_phase2d_pilot_recommendations.py
```

Database summary:

```sql
SELECT
    COUNT(*) AS rows,
    COUNT(DISTINCT date) AS dates,
    COUNT(DISTINCT symbol) AS symbols,
    MIN(date) AS first_date,
    MAX(date) AS last_date,
    MIN(score) AS min_score,
    percentile_cont(0.5) WITHIN GROUP (ORDER BY score) AS median_score,
    MAX(score) AS max_score
FROM pilot_phase2a.recommendations_daily;
```

Observed:

- Rows: 13,654
- Dates: 990
- Symbols: 282
- Date range: 2022-05-25 to 2026-06-11
- Score range: 71.428571 to 100.000000
- Median score: 77.142857

Production-count parity assertion:

```sql
WITH qualified AS (
    SELECT date, COUNT(*) AS q
    FROM pilot_phase2a.scores_daily
    WHERE swing_v2_1_score >= 70
    GROUP BY date
),
recs AS (
    SELECT date, COUNT(*) AS r
    FROM pilot_phase2a.recommendations_daily
    GROUP BY date
)
SELECT
    COUNT(*) FILTER (WHERE COALESCE(r, 0) <> LEAST(20, q)) AS mismatch_dates
FROM qualified
LEFT JOIN recs USING (date);
```

Observed:

- Mismatch dates: 0

Additional validation:

| Check | Result |
| --- | ---: |
| Count mismatch dates | 0 |
| Rank mismatch dates | 0 |
| Recommendations below minimum score | 0 |
| Dates above top N | 0 |
| Rank out-of-range rows | 0 |
| Rank gap dates | 0 |

## Production Safety

Writes were limited to:

- `angel_data.pilot_phase2a.recommendations_daily`
- `reports/phase2d_*`

Production tables were not modified.

Not performed:

- backtests
- portfolio simulation
- trade generation
- production recommendation writes
- recommendation logic changes

## Phase Boundary

Phase 2D is complete once pilot recommendations are generated and validated.

The next phase may consume these recommendations for backtesting or portfolio simulation, but neither was performed here.
