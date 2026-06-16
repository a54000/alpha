# Top Bucket Concentration Analysis

**Date:** 2026-06-11

**Objective:** Determine whether alpha is concentrated in the highest-scoring Swing recommendations.

**Scope:** Research only.

---

## Inputs

Models analyzed:

- V1 Swing
- Swing V2
- Sector Rank + ADX

Supporting artifact:

- `reports/top_bucket_concentration_results.json`

Primary horizon:

- `return_20d`

Execution assumption:

- next-trading-day open entry
- fixed-horizon close exit
- benchmark aligned to trade entry/exit window

---

## Method

This test measures concentration by smaller daily portfolios.

For each model/date, recommendations were sorted by score descending. Then the following slices were backtested:

| Slice | Daily Approximation |
|---|---:|
| Top 5% | top 1 recommendation |
| Top 10% | top 2 recommendations |
| Top 20% | top 4 recommendations |
| Top 30% | top 6 recommendations |
| All | full recommendation set |

This tests whether the model is useful as a ranker, not just as a broad stock-selection engine.

Temporary recommendation rows were inserted for sliced portfolios and deleted after measurement.

---

## V1 Swing

| Slice | Trade Count | Avg Return | Win Rate | Profit Factor | Alpha |
|---|---:|---:|---:|---:|---:|
| Top 5% | 445 | 0.2160% | 46.82% | 1.0493 | 0.3481% |
| Top 10% | 821 | -0.5228% | 43.86% | 0.8866 | -0.2975% |
| Top 20% | 1,379 | -0.9022% | 42.77% | 0.8092 | -0.5922% |
| Top 30% | 1,704 | -0.7893% | 42.79% | 0.8334 | -0.4168% |
| All | 2,045 | -0.5329% | 43.43% | 0.8850 | -0.1948% |

### V1 Interpretation

V1 has some useful signal in the single highest daily recommendation. The top 5% slice is profitable and has positive alpha.

However, performance decays quickly once more recommendations are included:

- Top 10% turns negative.
- Top 20% is worse.
- Top 30% remains weak.

V1 behaves like a weak ranking engine, not a broad stock-selection model.

---

## Swing V2

| Slice | Trade Count | Avg Return | Win Rate | Profit Factor | Alpha |
|---|---:|---:|---:|---:|---:|
| Top 5% | 476 | 0.4312% | 48.25% | 1.0931 | 0.4767% |
| Top 10% | 952 | 0.0448% | 47.92% | 1.0095 | 0.0882% |
| Top 20% | 1,903 | 0.2620% | 48.49% | 1.0601 | 0.3119% |
| Top 30% | 2,827 | 0.2671% | 48.61% | 1.0623 | 0.3314% |
| All | 7,189 | -0.0987% | 46.83% | 0.9767 | 0.1762% |

### Swing V2 Interpretation

Swing V2 has a better concentration profile than V1.

The top 5%, 20%, and 30% slices are all positive with profit factor above 1.0. The full recommendation set falls back below breakeven average return and profit factor.

This indicates weaker lower-ranked recommendations dilute the model, but the dilution is less severe than in V1.

---

## Sector Rank + ADX

| Slice | Trade Count | Avg Return | Win Rate | Profit Factor | Alpha |
|---|---:|---:|---:|---:|---:|
| Top 5% | 477 | 0.5912% | 49.45% | 1.1806 | 0.6447% |
| Top 10% | 953 | 0.5350% | 50.38% | 1.1586 | 0.5926% |
| Top 20% | 1,903 | -0.0113% | 49.31% | 0.9969 | 0.0522% |
| Top 30% | 2,850 | -0.0657% | 49.41% | 0.9822 | 0.0034% |
| All | 8,999 | 0.2216% | 49.51% | 1.0590 | 0.3936% |

### Sector Rank + ADX Interpretation

Sector Rank + ADX shows strong alpha concentration in the highest-scoring recommendations.

The top 5% and top 10% slices are clearly strongest:

- highest average returns
- best profit factors
- strongest alpha
- win rate around or above 50%

Top 20% and top 30% are close to flat. The full set is positive again, likely because the very broad sample includes additional profitable lower-score opportunities, but the cleanest edge is in the highest-score slices.

---

## Cross-Model Comparison

### Top 5%

| Model | Trade Count | Avg Return | Win Rate | Profit Factor | Alpha |
|---|---:|---:|---:|---:|---:|
| V1 Swing | 445 | 0.2160% | 46.82% | 1.0493 | 0.3481% |
| Swing V2 | 476 | 0.4312% | 48.25% | 1.0931 | 0.4767% |
| Sector Rank + ADX | 477 | 0.5912% | 49.45% | 1.1806 | 0.6447% |

Sector Rank + ADX is strongest in the top 5%.

### Top 10%

| Model | Trade Count | Avg Return | Win Rate | Profit Factor | Alpha |
|---|---:|---:|---:|---:|---:|
| V1 Swing | 821 | -0.5228% | 43.86% | 0.8866 | -0.2975% |
| Swing V2 | 952 | 0.0448% | 47.92% | 1.0095 | 0.0882% |
| Sector Rank + ADX | 953 | 0.5350% | 50.38% | 1.1586 | 0.5926% |

Sector Rank + ADX remains strongest at top 10%.

### Top 20%

| Model | Trade Count | Avg Return | Win Rate | Profit Factor | Alpha |
|---|---:|---:|---:|---:|---:|
| V1 Swing | 1,379 | -0.9022% | 42.77% | 0.8092 | -0.5922% |
| Swing V2 | 1,903 | 0.2620% | 48.49% | 1.0601 | 0.3119% |
| Sector Rank + ADX | 1,903 | -0.0113% | 49.31% | 0.9969 | 0.0522% |

At top 20%, Swing V2 is stronger than Sector Rank + ADX. This suggests Sector Rank + ADX's edge is more concentrated in the very top ranks.

### Top 30%

| Model | Trade Count | Avg Return | Win Rate | Profit Factor | Alpha |
|---|---:|---:|---:|---:|---:|
| V1 Swing | 1,704 | -0.7893% | 42.79% | 0.8334 | -0.4168% |
| Swing V2 | 2,827 | 0.2671% | 48.61% | 1.0623 | 0.3314% |
| Sector Rank + ADX | 2,850 | -0.0657% | 49.41% | 0.9822 | 0.0034% |

At top 30%, Swing V2 is again stronger.

### All Recommendations

| Model | Trade Count | Avg Return | Win Rate | Profit Factor | Alpha |
|---|---:|---:|---:|---:|---:|
| V1 Swing | 2,045 | -0.5329% | 43.43% | 0.8850 | -0.1948% |
| Swing V2 | 7,189 | -0.0987% | 46.83% | 0.9767 | 0.1762% |
| Sector Rank + ADX | 8,999 | 0.2216% | 49.51% | 1.0590 | 0.3936% |

Across the full recommendation set, Sector Rank + ADX is best.

---

## Research Questions

### 1. Is Performance Concentrated In The Highest Scores?

Yes.

The clearest evidence is Sector Rank + ADX:

- Top 5% avg return: `0.5912%`
- Top 10% avg return: `0.5350%`
- Top 20% avg return: `-0.0113%`
- Top 30% avg return: `-0.0657%`

V1 also shows top-score concentration, but it breaks down after top 5%.

Swing V2 is more distributed than Sector Rank + ADX, but the full set still underperforms its top 5/20/30 slices.

### 2. Are Weaker Recommendations Diluting Overall Model Returns?

Yes.

For V1, adding recommendations beyond the top 5% sharply dilutes returns.

For Swing V2, the full set underperforms the top 5%, top 20%, and top 30% slices.

For Sector Rank + ADX, the top 5% and top 10% slices are clearly superior to top 20% and top 30%. The full set remains positive, but lower-ranked recommendations reduce the quality of the portfolio if the goal is concentrated alpha.

### 3. Does A Smaller Portfolio Outperform The Full Recommendation Set?

Yes for concentrated alpha.

Best smaller portfolios:

| Model | Best Slice | Avg Return | Profit Factor | Alpha |
|---|---|---:|---:|---:|
| V1 Swing | Top 5% | 0.2160% | 1.0493 | 0.3481% |
| Swing V2 | Top 5% / Top 30% | 0.4312% / 0.2671% | 1.0931 / 1.0623 | 0.4767% / 0.3314% |
| Sector Rank + ADX | Top 5% | 0.5912% | 1.1806 | 0.6447% |

The best concentrated slice overall is Sector Rank + ADX top 5%.

### 4. Is The Model A Ranking Engine Rather Than A Broad Stock-Selection Engine?

Mostly yes.

The highest-score recommendations carry a disproportionate share of alpha. That means the model is better used for ranking and portfolio concentration than as a broad "buy every qualifying recommendation" selector.

This is especially true for:

- V1 Swing
- Sector Rank + ADX

Swing V2 is somewhat broader, but still shows dilution in the full recommendation set.

---

## Practical Implication

For future implementation research, the portfolio size matters as much as the scoring formula.

The current top-20 daily recommendation style may be too broad for alpha extraction. A smaller portfolio, especially top 1-2 names per day for Sector Rank + ADX, appears materially stronger.

Potential future validation:

- top 1 per day
- top 2 per day
- top 3 per day
- top 5 per day
- position overlap and holding-period portfolio simulation
- transaction costs and slippage

---

## Final Verdict

Alpha is concentrated in the highest-scoring recommendations.

The strongest concentration result is:

```text
Sector Rank + ADX, top 5%
```

This supports the view that the Swing model is primarily a ranking engine, not a broad stock-selection engine.

No production scoring was modified.
