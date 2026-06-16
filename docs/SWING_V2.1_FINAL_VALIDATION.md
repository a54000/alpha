# Swing V2.1 Final Validation

**Date:** 2026-06-11

**Objective:** Validate whether the simplified Swing model using Sector Rank + ADX is superior to all prior Swing variants discovered so far.

**Scope:** Research only. Production scoring was not modified.

---

## Inputs

Primary files:

- `reports/v1_clean_backtest_results.json`
- `reports/v2_backtest_results.json`
- `reports/swing_factor_pruning_results.json`
- `reports/swing_core_model_validation_results.json`
- `reports/swing_v21_final_validation_results.json`

Primary horizon:

- `return_20d`

Execution assumption:

- next-trading-day open entry
- fixed-horizon close exit
- benchmark aligned to each trade's entry/exit window

Score bucket performance was computed from each model's actual backtest trade list. It does not use the older defective date-range score bucket method.

---

## Compared Models

| # | Model | Description |
|---:|---|---|
| 1 | V1 Swing | Clean V1 baseline with remediated execution |
| 2 | Swing V2 | Implemented Swing V2 |
| 3 | Swing V2 minus EMA + Volume | Pruned Swing V2 core: Sector Rank + BB Width + ADX |
| 4 | Sector Rank + ADX | Simplified Swing V2.1 research candidate |

---

## Overall Results

| Model | Recommendation Count | Valid Count | Avg Return | Win Rate | Profit Factor | Alpha |
|---|---:|---:|---:|---:|---:|---:|
| V1 Swing | 2,045 | 1,911 | -0.5329% | 43.43% | 0.8850 | -0.1948% |
| Swing V2 | 7,189 | 6,870 | -0.0987% | 46.83% | 0.9767 | 0.1762% |
| Swing V2 minus EMA + Volume | 9,478 | 9,078 | 0.1484% | 49.00% | 1.0377 | 0.2056% |
| Sector Rank + ADX | 8,999 | 8,613 | 0.2216% | 49.51% | 1.0590 | 0.3936% |

Sector Rank + ADX is the best model in this comparison on:

- average return
- win rate
- profit factor
- alpha

It has slightly fewer recommendations than the pruned three-factor model, but still produces far more recommendations than V1 Swing.

---

## Top Score Bucket Performance

Top bucket means the highest populated score bucket. For all four models, the highest populated bucket is `90-100`.

| Model | Top Bucket | Trades | Valid | Avg Return | Win Rate | Profit Factor |
|---|---|---:|---:|---:|---:|---:|
| V1 Swing | 90-100 | 38 | 35 | 0.4291% | 34.29% | 1.0960 |
| Swing V2 | 90-100 | 354 | 337 | 1.3292% | 50.74% | 1.3162 |
| Swing V2 minus EMA + Volume | 90-100 | 1,842 | 1,746 | 1.2684% | 54.47% | 1.3736 |
| Sector Rank + ADX | 90-100 | 1,966 | 1,829 | 1.6887% | 56.53% | 1.5904 |

Sector Rank + ADX has the strongest top bucket by:

- average return
- win rate
- profit factor
- sample size versus V1 and Swing V2

---

## Score Bucket Notes

### V1 Swing

V1's top bucket is small:

- only 38 trades
- win rate only 34.29%
- positive average return due to payoff skew, not consistency

The lower `70-74` bucket is materially better than the middle buckets, so V1 score ranking is not reliable.

### Swing V2

Swing V2 improves top-bucket behavior:

- top bucket avg return: 1.3292%
- top bucket win rate: 50.74%
- top bucket profit factor: 1.3162

However, middle buckets remain weak.

### Swing V2 Minus EMA + Volume

The pruned three-factor core improves overall performance and keeps a strong top bucket.

Its `90-100` bucket:

- avg return: 1.2684%
- win rate: 54.47%
- profit factor: 1.3736

This confirms that removing EMA and Volume improves the model without damaging the top-score bucket.

### Sector Rank + ADX

Sector Rank + ADX has the best overall top bucket:

- avg return: 1.6887%
- win rate: 56.53%
- profit factor: 1.5904

It also has a good `75-79` bucket, but weaker `80-84` and `85-89` buckets. This means the model is not perfectly monotonic, but its highest-confidence bucket is the strongest bucket among all tested variants.

---

## Research Questions

### 1. Is Sector Rank + ADX The Best Swing Model Discovered So Far?

Yes.

It has the best headline metrics:

| Metric | Sector Rank + ADX |
|---|---:|
| Avg Return | 0.2216% |
| Win Rate | 49.51% |
| Profit Factor | 1.0590 |
| Alpha | 0.3936% |

It also has the strongest top score bucket:

| Top Bucket Metric | Sector Rank + ADX |
|---|---:|
| Avg Return | 1.6887% |
| Win Rate | 56.53% |
| Profit Factor | 1.5904 |

**Answer:** Yes, Sector Rank + ADX is the best Swing model found so far in this research sequence.

### 2. Does It Outperform V1?

Yes.

Compared with V1 Swing:

| Metric | V1 Swing | Sector Rank + ADX | Difference |
|---|---:|---:|---:|
| Avg Return | -0.5329% | 0.2216% | +0.7545 pp |
| Win Rate | 43.43% | 49.51% | +6.07 pp |
| Profit Factor | 0.8850 | 1.0590 | +0.1740 |
| Alpha | -0.1948% | 0.3936% | +0.5884 pp |
| Recommendation Count | 2,045 | 8,999 | +6,954 |

**Answer:** Yes, it outperforms V1 clean on every requested metric.

### 3. Does It Outperform Swing V2?

Yes.

Compared with Swing V2:

| Metric | Swing V2 | Sector Rank + ADX | Difference |
|---|---:|---:|---:|
| Avg Return | -0.0987% | 0.2216% | +0.3204 pp |
| Win Rate | 46.83% | 49.51% | +2.68 pp |
| Profit Factor | 0.9767 | 1.0590 | +0.0823 |
| Alpha | 0.1762% | 0.3936% | +0.2173 pp |
| Recommendation Count | 7,189 | 8,999 | +1,810 |

**Answer:** Yes, it outperforms Swing V2 on every requested metric.

### 4. Is BB Width Adding Enough Value To Justify Complexity?

No, not in the current Swing research sequence.

The pruned three-factor model, Sector Rank + BB Width + ADX, performs well:

- avg return: 0.1484%
- profit factor: 1.0377
- alpha: 0.2056%

But removing BB Width and keeping only Sector Rank + ADX improves:

- avg return
- win rate
- profit factor
- alpha
- top bucket avg return
- top bucket profit factor

BB Width may still have value as:

- a secondary diagnostic,
- a capped filter,
- or a different non-linear condition.

But the current implementation does not justify BB Width as a required Swing scoring factor.

**Answer:** No. BB Width does not add enough value to justify complexity in the best current Swing model.

### 5. Should Sector Rank + ADX Become The Official Swing V2.1 Candidate?

Yes, as a research candidate.

It should become the official Swing V2.1 candidate for the next implementation step because it is:

- simpler than Swing V2,
- better than V1,
- better than Swing V2,
- better than the three-factor core,
- aligned with the strongest current evidence,
- easier to explain and monitor.

This document does not implement it.

**Answer:** Yes. Sector Rank + ADX should become the official Swing V2.1 candidate.

---

## Final Verdict

Sector Rank + ADX is the strongest Swing model discovered so far.

It outperforms V1 Swing, Swing V2, and Swing V2 minus EMA + Volume across the requested metrics. It also has the strongest top score bucket.

Recommendation:

```text
Adopt Sector Rank + ADX as the official Swing V2.1 candidate for a future implementation step.
```

No production scoring changes were made.
