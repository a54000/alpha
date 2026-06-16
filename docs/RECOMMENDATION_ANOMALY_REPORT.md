# Recommendation Generation Anomaly Report

**Date:** 2026-06-10  
**Scope:** Read-only audit of `recommendation_history` under-population vs `daily_scores`  
**Observed state (PostgreSQL):**

| Table | Rows | Date range |
|-------|------|------------|
| `daily_scores` | 214,990 | 2024-06-10 → 2026-06-09 |
| `recommendation_history` | 1 | 2026-01-29 only |

**Single row:** `positional` rank 1, `HINDCOPPER`, score `67.0`

---

## Executive Summary

**Root cause:** Recommendation generation is working as coded. The anomaly is caused by **minimum score thresholds** (`swing ≥ 70`, `positional ≥ 65`) filtering out virtually all candidates because **computed scores are systematically depressed** due to **incomplete `features_daily` columns** (e.g. `ema_5`, `rs_rank_pct`, `stoch_k`, `adx_prev` are 100% NULL). Across 497 trading days and 214,990 score rows, only **one symbol on one date** meets the positional threshold. Swing never reaches 70 (global max = 48).

This is **not** a bug restricting generation to the latest date, and **not** a sector-join failure in the recommendation layer.

---

## Investigation Findings

### 1. Why only 1 date is processed

`RecommendationGenerator.generate()` iterates **every calendar day** from `start_date` to `end_date` (lines 109–145 in `generate_recommendations.py`).

Default bounds when `recommendation_history` is empty:

- `start_date` = `MIN(daily_scores.date)` → `2024-06-10`
- `end_date` = `MAX(daily_scores.date)` → `2026-06-09`

That is **730 calendar days**. The loop runs for all of them.

However, `dates_processed` increments **only when at least one row is written** for that date:

```python
if date_written:
    dates_processed += 1
```

For 729 of 730 days, `rank_recommendations()` returned an empty list because no symbol met `minimum_score`. Only **2026-01-29** produced a write.

| Metric | Value |
|--------|-------|
| Calendar days iterated | 730 |
| Trading days with `daily_scores` | 497 |
| Dates with any `swing_score ≥ 70` | **0** |
| Dates with any `position_score ≥ 65` | **1** (2026-01-29) |
| Dates written to `recommendation_history` | **1** |

**Conclusion:** All dates were *visited*; only one date *qualified*.

---

### 2. Why only 1 recommendation is written

Per-date logic for each model (`swing`, `positional`):

1. Load candidates from `daily_scores` ⋈ `features_daily` (eligible only)
2. Filter `score >= minimum_score` (`rank_recommendations`, line 74)
3. Take top 20

On **2026-01-29**:

| Model | Threshold | Qualifying symbols | Written |
|-------|-----------|-------------------|---------|
| Swing | ≥ 70 | 0 (max swing = 46) | 0 |
| Positional | ≥ 65 | 1 (`HINDCOPPER` = 67) | 1 |

On all other dates: 0 qualifiers for both models.

**Conclusion:** Threshold filtering, not a persistence bug.

---

### 3. Whether generation is restricted to latest date

**No.**

| Behavior | Code location | Effect |
|----------|---------------|--------|
| `end_date` defaults to latest score date | lines 95–96 | Sets upper bound, not single-date |
| `start_date` defaults to earliest score date (first run) | lines 97–104 | Full history on first run |
| Incremental resume | lines 98–102 | After first row, would start at `latest_rec + 1 day` |
| Single-date restriction | **Not present** | — |

A re-run today would process `2026-01-30 → 2026-06-09` incrementally and still write **0 rows** (no dates qualify).

---

### 4. Whether score thresholds are filtering everything

**Yes — primary cause.**

Configured thresholds (`generate_recommendations.py` lines 39–48):

| Model | `minimum_score` | Global max observed | Dates with ≥1 qualifier |
|-------|-----------------|---------------------|-------------------------|
| Swing | 70.0 | 48.0 | 0 / 497 |
| Positional | 65.0 | 67.0 | 1 / 497 |

Threshold sensitivity (positional):

| Threshold | Dates with ≥1 qualifier |
|-----------|-------------------------|
| ≥ 60 | 7 |
| ≥ 65 | 1 |
| ≥ 70 | 0 |

Score distribution (non-NULL rows, n=159,087):

| Metric | Swing | Positional |
|--------|-------|------------|
| Average | 12.4 | 19.6 |
| Maximum | 48.0 | 67.0 |

55,903 rows have **both** scores NULL (ineligible stocks via `is_eligible = FALSE` in scoring).

---

### 5. Whether rank generation is failing

**No.**

`rank_recommendations()` is functioning correctly (covered by `tests/test_recommendations.py`). On 2026-01-29 it returned exactly one positional candidate. The ranking/top-20 cap was never reached because qualifiers are scarce.

---

### 6. Whether sector joins are removing rows

**No — not in the recommendation layer.**

`RecommendationGenerator._load_candidates()` joins only:

```python
daily_scores ⋈ features_daily ON (symbol, date)
```

It filters `is_eligible IS NOT FALSE`. It does **not** join `sector_daily` or `symbol_master`.

Sector data affects **scoring** (`ScoreComputer` loads `sector_daily.rank_3m` for positional scores), not recommendation retrieval. On 2026-01-29, `HINDCOPPER` benefited from sector rank 1 (+20 pts) — sector data **helped** produce the sole qualifying score, not remove it.

Join coverage: **497 / 497** score dates have full `features_daily` join.

---

## Upstream Cause: Incomplete Features Depress Scores

`FeatureComputer` (`app/indicators/compute_features.py`) does not populate several columns required by `SCORING_VALIDATION.md`. On `2026-06-09`, these are **100% NULL** (432/432 symbols):

| Column | Used by | Impact when NULL |
|--------|---------|------------------|
| `ema_5`, `ema_13` | Swing EMA alignment (10 pts) | 0 |
| `ema_150` | Positional Stage 2 EMA (25 pts) | Reduced to partial |
| `adx_prev` | Swing/Pos ADX trend (up to 20 pts) | 0 |
| `macd_hist_prev` | Swing MACD (up to 10 pts) | 0 |
| `stoch_k`, `stoch_d` | Swing stochastic (5 pts) | 0 |
| `bb_width_20avg` | Swing Bollinger squeeze (4 pts) | 0 |
| `rs_rank_pct` | Swing RS (10 pts) + Positional RS (18 pts) | 0 |

Without these, swing scores cannot exceed ~48; positional scores rarely exceed ~64.

**Example — sole qualifier `HINDCOPPER` on 2026-01-29:**

| Feature | Value | Points contributed |
|---------|-------|-------------------|
| `ema_50`, `ema_200` (partial stage) | present | 16 |
| `adx_14` = 42 (no `adx_prev`) | | 9 |
| `rs_vs_nifty_60d` = 1.22 | | 12 |
| `sector rank_3m` = 1 | | 20 |
| `volume_ratio` = 3.2 | | 10 |
| **Total positional** | | **67** |

Missing `rs_rank_pct`, `ema_150`, `stoch_*`, etc. cap swing at 35 on the same date.

---

## Affected Code

| File | Role in anomaly |
|------|-----------------|
| `app/recommendations/generate_recommendations.py` | Applies hard `minimum_score` filters (70/65); iterates all dates; writes only when qualifiers exist |
| `app/indicators/compute_features.py` | Omits key indicator columns → depressed scores |
| `app/scoring/compute_scores.py` | Reads missing features as 0; NULL scores for ineligible |
| `scripts/run_historical_pipeline.py` | Calls `RecommendationGenerator().generate()` with no date override (full range) |
| `db/models.py` | `recommendation_history` schema supports full output; not the limiting factor |

---

## Expected Row Count

| Scenario | Calculation | Expected rows |
|----------|-------------|---------------|
| **Current data + current thresholds** | 1 date × 1 positional qualifier | **1** (matches observed) |
| **Current data, positional ≥ 60** | 7 dates × ~1–few qualifiers | ~7–20 |
| **Healthy features + thresholds 70/65** | 497 days × up to 40 (20 swing + 20 positional) | up to **19,880** |
| **Realistic healthy run** | 497 days × ~10–20 avg qualifiers | **5,000–10,000** |

---

## Fix Recommendations

### Priority 1 — Complete feature pipeline (root fix)

Extend `FeatureComputer` to compute and persist:

- `ema_5`, `ema_13`, `ema_150`
- `adx_prev`, `macd_hist_prev` (lagged values)
- `stoch_k`, `stoch_d`
- `bb_width_20avg`
- `rs_rank_pct` (cross-sectional percentile pass after all symbols computed)

Then re-run: features → sectors → scores → recommendations.

### Priority 2 — Reconcile recommendation thresholds with score reality

Current thresholds (70/65) align with `SCORING_VALIDATION.md` **interpretation bands** ("Worth Watching" at 70+), but `BACKTEST_SPEC.md` states score thresholds are **not** hard entry filters for V1 backtests. Options:

- Lower `minimum_score` to match observed distribution (e.g. swing 40, positional 55) as interim
- Or use top-N ordinal ranking without absolute floor (per `BACKTEST_SPEC.md` entry rules)

### Priority 3 — Iterate trading days only (quality improvement)

Replace calendar-day `_date_range` with distinct `daily_scores.date` values to avoid 233 empty iterations per run. Does not fix row count but improves clarity and performance.

### Priority 4 — Re-run recommendations after fixes

```bash
# After features/scores regenerated:
PYTHONPATH=. python -c "
from db.session import build_session_factory
from app.recommendations.generate_recommendations import RecommendationGenerator
# Clear recommendation_history first if full rebuild needed
report = RecommendationGenerator(build_session_factory()).generate()
print(report)
"
```

---

## Answers to Audit Questions

| # | Question | Answer |
|---|----------|--------|
| 1 | Why only 1 date processed? | All dates iterated; only 1 date had qualifying scores above threshold |
| 2 | Why only 1 recommendation written? | Only `HINDCOPPER` on 2026-01-29 met positional ≥ 65; swing never meets ≥ 70 |
| 3 | Restricted to latest date? | **No** — full range on first run |
| 4 | Score thresholds filtering? | **Yes** — primary cause |
| 5 | Rank generation failing? | **No** |
| 6 | Sector joins removing rows? | **No** in recommendation layer; sector data helps scoring |

---

## Document History

| Date | Change |
|------|--------|
| 2026-06-10 | Initial anomaly audit |
