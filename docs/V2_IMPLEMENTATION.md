# V2 Implementation

**Date:** 2026-06-11

**Status:** Implemented and backtested

**Primary inputs:**

- `docs/SCORING_V2_PROPOSAL.md`
- `docs/V2_FACTOR_DECISION_MATRIX.md`

---

## Summary

V2 scoring was implemented as a separate versioned path alongside V1.

V1 scoring logic, V1 recommendation generation, factor calculations, and existing public APIs were preserved.

New V2 models:

- `swing_v2`
- `positional_v2`

V2 results were exported to:

```text
reports/v2_backtest_results.json
```

---

## Storage

V2 scores are stored separately from V1 scores in `daily_scores`.

New columns:

- `swing_v2_score`
- `position_v2_score`

Files changed:

- `db/models.py`
- `alembic/versions/008_add_v2_score_columns.py`

The V2 runner also defensively ensures these columns exist before backfill so the local database can run even if Alembic is not available in the active environment.

---

## Scoring Implementation

File changed:

- `app/scoring/compute_scores.py`

New functions:

- `compute_swing_v2_score()`
- `compute_position_v2_score()`

The original V1 functions remain unchanged:

- `compute_swing_score()`
- `compute_position_score()`

### Swing V2

Implemented factors:

| Factor | Weight |
|---|---:|
| ADX strength / direction | 25 |
| EMA short-term alignment | 10 |
| BB Width absolute | 25 |
| BB Width relative expansion | 15 |
| Volume ratio | 15 |
| Sector rank | 10 |
| **Total** | **100** |

Removed from V2 Swing scoring:

- RSI
- MACD histogram
- Stochastic
- 52-week-high proximity
- `rs_rank_pct`

### Positional V2

Implemented factors:

| Factor | Weight |
|---|---:|
| EMA Stage 2 alignment | 22 |
| ADX medium-term | 18 |
| Sector 3-month rank | 30 |
| BB Width | 15 |
| Volume ratio | 10 |
| Eligibility / liquidity guard | 5 |
| **Total** | **100** |

Removed from V2 Positional scoring:

- `rs_rank_pct`
- `rs_vs_nifty_60d`

Sector rank is interpreted correctly: lower `rank_3m` is stronger and receives more points.

---

## Score Backfill

File changed:

- `app/scoring/compute_scores.py`

`ScoreComputer.generate()` now computes V2 scores in addition to V1 scores.

For existing `daily_scores` rows, it updates only:

- `swing_v2_score`
- `position_v2_score`

It does not rewrite existing V1 score values.

Backfill range used:

```text
2024-06-10 to 2026-06-09
```

Backfill result:

| Metric | Value |
|---|---:|
| Symbols processed | 214,990 |
| Dates processed | 497 |
| Rows updated/written | 214,990 |
| Non-null Swing V2 scores | 159,087 |
| Non-null Positional V2 scores | 159,087 |

---

## Recommendation Generation

File changed:

- `app/recommendations/generate_recommendations.py`

New recommendation configs:

- `SWING_V2_RECOMMENDATION_CONFIG`
- `POSITIONAL_V2_RECOMMENDATION_CONFIG`

New method:

- `RecommendationGenerator.generate_v2()`

V2 recommendations are stored in the existing `recommendation_history` table with separate model names:

- `swing_v2`
- `positional_v2`

Existing V1 recommendation generation remains available through:

- `RecommendationGenerator.generate()`

V2 recommendation result:

| Metric | Value |
|---|---:|
| Dates processed | 478 |
| Swing V2 recommendations | 7,200 |
| Positional V2 recommendations | 8,277 |
| Rows written | 15,477 |

---

## Backtesting

File changed:

- `app/backtesting/run_backtest.py`

Backtest configs were added for:

- `swing_v2`
- `positional_v2`

They reuse the same horizon definitions as their corresponding V1 models:

- Swing V2: 5d, 10d, 20d
- Positional V2: 1m, 3m, 6m

The remediated next-trading-day-open execution logic is used for V2 backtests.

---

## Pipeline Script

File added:

- `scripts/run_v2_backtest.py`

The script performs:

1. Ensure V2 score columns exist.
2. Backfill V2 scores.
3. Clear existing V2 recommendation rows.
4. Generate V2 recommendations.
5. Run `swing_v2` backtest.
6. Run `positional_v2` backtest.
7. Export `reports/v2_backtest_results.json`.

Command used:

```powershell
$env:PYTHONPATH='D:\nse-research-app'; .\.venv\Scripts\python.exe scripts\run_v2_backtest.py
```

---

## V2 Backtest Results

Results file:

```text
reports/v2_backtest_results.json
```

### Swing V2

| Horizon | Trades | Valid | Win Rate | Avg Return | Median Return | Profit Factor | Alpha |
|---|---:|---:|---:|---:|---:|---:|---:|
| 5d | 7,189 | 7,123 | 46.10% | -0.17% | -0.46% | 0.929 | 0.01% |
| 10d | 7,189 | 7,040 | 46.56% | -0.05% | -0.56% | 0.985 | 0.10% |
| 20d | 7,189 | 6,870 | 46.83% | -0.10% | -0.77% | 0.977 | 0.18% |

Primary horizon:

```text
swing_v2 return_20d avg_return = -0.0009874856575023884
swing_v2 return_20d alpha = 0.0017623950215106528
```

### Positional V2

| Horizon | Trades | Valid | Win Rate | Avg Return | Median Return | Profit Factor | Alpha |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1m | 8,261 | 7,850 | 50.54% | 0.16% | 0.12% | 1.041 | 0.32% |
| 3m | 8,261 | 7,119 | 43.91% | -2.40% | -2.61% | 0.704 | -1.00% |
| 6m | 8,261 | 5,873 | 40.52% | -3.87% | -4.43% | 0.625 | -2.24% |

Primary horizon:

```text
positional_v2 return_3m avg_return = -0.02399160015266012
positional_v2 return_3m alpha = -0.0099577845432777
```

---

## Verification

Focused tests passed:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_scoring_engine.py tests\test_recommendations.py tests\test_backtesting.py
```

Result:

```text
43 passed
```

Full test suite status remains limited by environment dependencies already observed earlier:

- missing `pandas` in the active `.venv`
- incomplete Alembic import for migration tests

---

## Scope Preserved

The following were not changed:

- V1 scoring functions
- V1 scoring weights
- V1 recommendation model names
- V1 recommendation generation API
- factor calculations
- sector factor calculations
- feature calculations
- existing V1 backtest horizons

---

## Known Notes

The V2 implementation uses researched EOD factors only. It does not add intraday logic, transaction costs, dynamic exits, or portfolio simulation.

The generated V2 results are standalone. No V1 comparison is made in this document.
