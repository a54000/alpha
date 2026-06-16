# Swing Core Model Validation

**Date:** 2026-06-11

**Objective:** Validate whether the simplified Swing model using Sector Rank, BB Width, and ADX is responsible for most Swing alpha.

**Scope:** Research only. Production scoring was not modified.

---

## Inputs

Primary files:

- `reports/v2_backtest_results.json`
- `reports/swing_factor_pruning_results.json`
- `reports/swing_core_model_validation_results.json`

Primary horizon:

- `return_20d`

Execution assumption:

- next-trading-day open entry
- fixed-horizon close exit
- benchmark aligned to each trade's entry/exit window

---

## Method

I tested the requested variants:

| Variant | Description |
|---|---|
| A | Current Swing V2 |
| B | Swing V2 minus EMA and Volume |
| C | Sector Rank + BB Width + ADX only |
| D | Sector Rank + BB Width only |
| E | Sector Rank + ADX only |
| F | BB Width + ADX only |

For variants B-F:

1. Recomputed daily candidate scores.
2. Used only the requested factor groups.
3. Rescaled the active factor score to 100.
4. Applied the same `score >= 70` threshold.
5. Selected top 20 recommendations per day.
6. Inserted temporary recommendation rows.
7. Ran the remediated backtest engine.
8. Deleted temporary recommendation rows after measurement.

Score bucket performance was calculated from each backtest's actual trade list, not by rerunning date-range bucket backtests.

---

## Overall Results

| Variant | Trade Count | Valid Count | Avg Return | Win Rate | Profit Factor | Alpha |
|---|---:|---:|---:|---:|---:|---:|
| A. Current Swing V2 | 7,189 | 6,870 | -0.0987% | 46.83% | 0.9767 | 0.1762% |
| B. Swing V2 minus EMA and Volume | 9,478 | 9,078 | 0.1484% | 49.00% | 1.0377 | 0.2056% |
| C. Sector Rank + BB Width + ADX | 9,478 | 9,078 | 0.1484% | 49.00% | 1.0377 | 0.2056% |
| D. Sector Rank + BB Width | 9,500 | 9,100 | 0.0487% | 47.90% | 1.0124 | 0.0958% |
| E. Sector Rank + ADX | 8,999 | 8,613 | 0.2216% | 49.51% | 1.0590 | 0.3936% |
| F. BB Width + ADX | 9,540 | 9,140 | 0.2186% | 48.63% | 1.0554 | 0.2715% |

Variant B and Variant C are identical by construction because removing EMA and Volume from Swing V2 leaves the three-factor core:

```text
Sector Rank + BB Width + ADX
```

---

## Score Bucket Performance

### A. Current Swing V2

| Bucket | Trades | Avg Return | Win Rate | Profit Factor |
|---|---:|---:|---:|---:|
| 70-74 | 2,326 | 0.1183% | 47.36% | 1.0293 |
| 75-79 | 2,522 | -0.6242% | 45.22% | 0.8597 |
| 80-84 | 1,145 | -0.2628% | 46.65% | 0.9381 |
| 85-89 | 842 | 0.4987% | 48.77% | 1.1188 |
| 90-100 | 354 | 1.3292% | 50.74% | 1.3162 |

Current Swing V2 has a strong top bucket, but middle buckets are weak.

### B/C. Sector Rank + BB Width + ADX

| Bucket | Trades | Avg Return | Win Rate | Profit Factor |
|---|---:|---:|---:|---:|
| 70-74 | 298 | 3.4204% | 64.89% | 2.3068 |
| 75-79 | 934 | -0.2092% | 46.80% | 0.9515 |
| 80-84 | 3,123 | -0.1167% | 47.30% | 0.9704 |
| 85-89 | 3,281 | -0.4070% | 46.79% | 0.9041 |
| 90-100 | 1,842 | 1.2684% | 54.47% | 1.3736 |

The three-factor core preserves overall performance and has a strong 90-100 bucket. The bucket curve is not cleanly monotonic.

### D. Sector Rank + BB Width

| Bucket | Trades | Avg Return | Win Rate | Profit Factor |
|---|---:|---:|---:|---:|
| 70-74 | 343 | -0.6976% | 41.69% | 0.8322 |
| 75-79 | 27 | -1.3953% | 30.77% | 0.5853 |
| 80-84 | 3,162 | -1.5952% | 38.70% | 0.6528 |
| 85-89 | 2,440 | 0.2651% | 49.66% | 1.0663 |
| 90-100 | 3,528 | 1.3853% | 55.27% | 1.4146 |

Sector Rank + BB Width has a strong top bucket, but weak lower and middle buckets. Overall performance is positive but weaker than the ADX-containing variants.

### E. Sector Rank + ADX

| Bucket | Trades | Avg Return | Win Rate | Profit Factor |
|---|---:|---:|---:|---:|
| 70-74 | 2,338 | -0.4571% | 44.22% | 0.8877 |
| 75-79 | 1,991 | 0.6024% | 51.82% | 1.1595 |
| 80-84 | 1,777 | -0.4266% | 49.10% | 0.8964 |
| 85-89 | 927 | -0.6734% | 44.33% | 0.8345 |
| 90-100 | 1,966 | 1.6887% | 56.53% | 1.5904 |

Sector Rank + ADX has the best overall results and the strongest 90-100 bucket.

### F. BB Width + ADX

| Bucket | Trades | Avg Return | Win Rate | Profit Factor |
|---|---:|---:|---:|---:|
| 70-74 | 22 | 8.3911% | 81.82% | 6.9564 |
| 75-79 | 394 | 1.9062% | 61.17% | 1.6458 |
| 80-84 | 408 | 2.8381% | 59.44% | 2.0228 |
| 85-89 | 1,953 | 0.0821% | 48.11% | 1.0203 |
| 90-100 | 6,763 | -0.0300% | 47.26% | 0.9926 |

BB Width + ADX performs well overall but has inverted score-bucket behavior: the highest score bucket is not the strongest bucket.

---

## Research Questions

### 1. What Is The Minimum-Factor Swing Model That Preserves Performance?

The minimum-factor model that preserves and improves performance is:

```text
Sector Rank + ADX
```

Variant E has the best overall metrics:

- avg return: `0.2216%`
- win rate: `49.51%`
- profit factor: `1.0590`
- alpha: `0.3936%`

It beats the three-factor core on all headline metrics except trade count.

### 2. Does Sector Rank Carry Most Of The Alpha?

Sector Rank is important, but it does not carry all alpha by itself.

Evidence:

- Variant E, Sector Rank + ADX, has the highest alpha: `0.3936%`.
- Variant F, BB Width + ADX without Sector Rank, still has positive alpha: `0.2715%`.
- Variant D, Sector Rank + BB Width without ADX, has lower alpha: `0.0958%`.

Interpretation:

Sector Rank contributes strongly when paired with ADX. However, ADX also carries meaningful alpha when paired with BB Width.

**Answer:** Sector Rank is a major alpha contributor, but not the only one. The strongest alpha comes from the Sector Rank + ADX pairing.

### 3. Is ADX Necessary?

ADX appears necessary for the best Swing core performance.

Evidence:

- Sector Rank + BB Width without ADX: alpha `0.0958%`, profit factor `1.0124`.
- Sector Rank + ADX without BB Width: alpha `0.3936%`, profit factor `1.0590`.
- BB Width + ADX without Sector Rank: alpha `0.2715%`, profit factor `1.0554`.

Both ADX-containing two-factor variants outperform the no-ADX two-factor variant.

**Answer:** Yes. ADX appears necessary for preserving most of the Swing alpha.

### 4. Is BB Width Necessary?

BB Width is not necessary for preserving performance in this test.

Evidence:

- Sector Rank + ADX without BB Width is the best overall model.
- Adding BB Width to create the three-factor core lowers alpha and profit factor versus Sector Rank + ADX.
- BB Width + ADX performs well, but its score bucket behavior is poor because the 90-100 bucket underperforms lower buckets.

**Answer:** No. BB Width is useful in some combinations, but it is not necessary and may dilute the cleaner Sector Rank + ADX signal.

### 5. Are There Interaction Effects Between BB Width And ADX?

Yes. The BB Width + ADX pair works well on headline metrics:

- avg return: `0.2186%`
- profit factor: `1.0554`
- alpha: `0.2715%`

But the score buckets are not healthy:

- 70-74, 75-79, and 80-84 buckets have strong returns.
- 90-100 bucket is slightly negative.

This suggests BB Width and ADX together can identify profitable setups, but the score scaling may over-reward extreme values. High combined BB/ADX may represent late or crowded volatility expansion.

**Answer:** Yes. BB Width and ADX interact positively at moderate scores but negatively at the highest score bucket.

---

## Conclusions

1. The three-factor core, Sector Rank + BB Width + ADX, does preserve most of Swing V2 performance.
2. The simpler two-factor model, Sector Rank + ADX, performs better than the three-factor core.
3. ADX appears necessary.
4. BB Width is not necessary for the best-performing minimum-factor model.
5. Sector Rank is a major contributor, especially when paired with ADX.
6. BB Width + ADX has interaction effects: strong overall performance but weak top-score bucket behavior.

---

## Research Recommendation

Do not modify production scoring from this document.

If a future approved implementation step is requested, the next Swing research candidate should be:

```text
Sector Rank + ADX
```

BB Width should remain under investigation as:

- a secondary filter,
- a capped score component,
- or a moderate-range condition rather than an always-higher-is-better score.

No production scoring changes were made.
