# Pipeline Rebuild Report

**Generated:** 2026-06-10  
**Scope:** Full historical regeneration of `features_daily`, `sector_daily`, `daily_scores`, and `recommendation_history` over the available price history (2024-06-10 → 2026-06-09).  
**Audit only** — scoring rules and recommendation thresholds were not modified.

## Regeneration Summary

| Step | Table | Result |
|------|-------|--------|
| 1 | `features_daily` | 434 symbols processed, 214,990 rows written (~402 s) |
| 2 | `sector_daily` | 476 dates processed, 8,567 rows in table |
| 3 | `daily_scores` | 497 dates processed, 214,990 rows in table |
| 4 | `recommendation_history` | 478 dates processed, 8,323 rows written (2,049 swing + 6,274 positional) |

Downstream tables were truncated before regeneration. `symbol_master` and `prices_daily` were left unchanged.

---

## A. Row Counts

| Table | Row Count | Date Range |
|-------|-----------|------------|
| `symbol_master` | 502 | — |
| `prices_daily` | 214,990 | 2024-06-10 → 2026-06-09 |
| `features_daily` | 214,990 | 2024-06-10 → 2026-06-09 |
| `sector_daily` | 8,567 | 2024-07-10 → 2026-06-09 |
| `daily_scores` | 214,990 | 2024-06-10 → 2026-06-09 |
| `recommendation_history` | 8,323 | 2024-07-08 → 2026-06-09 |

`features_daily` row count matches `prices_daily` exactly (one feature row per price row). `sector_daily` starts later due to sector-strength warmup requirements.

---

## B. Feature Population Audit

Total `features_daily` rows: **214,990**

| Field | Total Rows | Populated | Null | Population % |
|-------|------------|-----------|------|--------------|
| `ema_5` | 214,990 | 214,990 | 0 | 100.00% |
| `ema_13` | 214,990 | 214,990 | 0 | 100.00% |
| `ema_150` | 214,990 | 214,990 | 0 | 100.00% |
| `adx_prev` | 214,990 | 213,814 | 1,176 | 99.45% |
| `macd_hist_prev` | 214,990 | 214,556 | 434 | 99.80% |
| `stoch_k` | 214,990 | 207,160 | 7,830 | 96.36% |
| `stoch_d` | 214,990 | 206,284 | 8,706 | 95.95% |
| `bb_width_20avg` | 214,990 | 198,498 | 16,492 | 92.33% |
| `rs_rank_pct` | 214,990 | 206,310 | 8,680 | 95.96% |

Nulls on lagged and rolling indicators (`adx_prev`, `stoch_*`, `bb_width_20avg`, `rs_rank_pct`) are concentrated at the start of each symbol's history and at early cross-sectional dates — expected warmup behavior, not a pipeline gap.

---

## C. Recommendation Audit

Thresholds (unchanged): swing ≥ 70, positional ≥ 65, top 20 per day per model.

### Swing

| Metric | Value |
|--------|-------|
| Total recommendations | 2,049 |
| Distinct dates | 446 |
| Avg recommendations / day | 4.59 |
| Minimum score | 70.0 |
| Maximum score | 100.0 |
| Average score | 75.03 |

### Positional

| Metric | Value |
|--------|-------|
| Total recommendations | 6,274 |
| Distinct dates | 477 |
| Avg recommendations / day | 13.15 |
| Minimum score | 65.0 |
| Maximum score | 100.0 |
| Average score | 72.76 |

Eligibility filter: 159,087 rows with `is_eligible = true` (73.9% of feature rows).

---

## D. Score Distribution

### `swing_score` (214,990 rows)

| Bucket | Count | % of Total |
|--------|-------|------------|
| 0–20 | 53,516 | 24.9% |
| 20–40 | 60,716 | 28.2% |
| 40–60 | 37,385 | 17.4% |
| 60–80 | 7,144 | 3.3% |
| 80–100 | 326 | 0.2% |

Rows with `swing_score ≥ 70`: **2,049** (0.95% of universe)

### `position_score` (214,990 rows)

| Bucket | Count | % of Total |
|--------|-------|------------|
| 0–20 | 65,149 | 30.3% |
| 20–40 | 47,364 | 22.0% |
| 40–60 | 30,167 | 14.0% |
| 60–80 | 15,598 | 7.3% |
| 80–100 | 809 | 0.4% |

Rows with `position_score ≥ 65`: **10,729** (4.99% of universe)

Both models reach a maximum score of **100.0**, confirming the scoring engine is no longer capped by missing feature inputs.

---

## E. Verdict

**READY_FOR_BACKTESTING**

**Rationale:**

1. All six audited tables are populated with consistent date coverage across the full price history.
2. Previously missing feature columns (`ema_5`, `ema_13`, `ema_150`, `adx_prev`, `macd_hist_prev`, `stoch_k`, `stoch_d`, `bb_width_20avg`, `rs_rank_pct`) are now populated at 92–100%; remaining nulls are explainable warmup gaps.
3. `recommendation_history` contains 8,323 recommendations spanning 446–477 trading days for swing and positional models respectively — sufficient history for forward-return backtesting.
4. Scores reach the full 0–100 range; the prior single-recommendation anomaly caused by 100% NULL features is resolved.

**Observation (not blocking):** Swing recommendations are sparse relative to positional (4.6 vs 13.2 per day) because the swing threshold (≥ 70) filters ~99% of scored rows. This is a scoring calibration question for a future tuning pass, not a pipeline integrity issue.
