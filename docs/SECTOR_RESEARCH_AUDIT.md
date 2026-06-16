# Sector Research Direction Audit

**Date:** 2026-06-11  
**Scope:** Audit `scripts/run_sector_factor_research.py` and the sector research analyzer directionality.  
**Status:** Audit only. No code changes made.

---

## Executive Summary

The sector research code ranks all factor buckets in ascending numeric order.

That means:

- `bucket_1` always contains the **lowest factor values**.
- `bucket_5` always contains the **highest factor values**.
- `top_bucket_return` always means `bucket_5`, not "best sector bucket".
- `bottom_bucket_return` always means `bucket_1`, not "worst sector bucket".

This is correct mechanically, but interpretation differs by factor.

For `rank_3m`, lower values are stronger sectors. Therefore:

- `bucket_1` = strongest sectors
- `bucket_5` = weakest sectors
- Negative Spearman IC = better-ranked sectors tend to have higher forward returns
- Negative bucket spread = strongest sectors outperform weakest sectors

For raw sector return fields, higher values are stronger by raw trailing return. Therefore:

- `bucket_1` = weakest trailing-return sectors
- `bucket_5` = strongest trailing-return sectors
- Positive Spearman IC would support return momentum
- Negative Spearman IC suggests lower trailing-return sectors outperformed, i.e. mean reversion

No factor values are inverted before computation in the current code.

---

## Code Path Reviewed

### Runner

`scripts/run_sector_factor_research.py` passes these factors to `SectorFactorAnalyzer`:

- `rank_3m`
- `sector_return_1m`
- `sector_return_3m`
- `sector_return_6m`

The runner does not transform or invert factor values.

### Sector Analyzer

`app/research/sector_factor_analysis.py` maps factors directly:

```python
FACTOR_COLUMNS = {
    "rank_3m": SectorDaily.rank_3m,
    "sector_return_1m": SectorDaily.sector_return_1m,
    "sector_return_3m": SectorDaily.sector_return_3m,
    "sector_return_6m": SectorDaily.sector_return_6m,
}
```

Values are converted to floats and passed unchanged into `FactorAnalyzer.factor_summary()` and `FactorAnalyzer.bucket_analysis()`.

### Bucket Logic

`FactorAnalyzer.bucket_analysis()` sorts by factor value in ascending order:

```python
paired.sort(key=lambda x: x[0])
```

Then the first slice becomes `bucket_1`, and the last slice becomes `bucket_5`.

`FactorAnalyzer.factor_summary()` assigns:

```python
top_bucket_return = bucket_results["bucket_5"]["average_return"]
bottom_bucket_return = bucket_results["bucket_1"]["average_return"]
```

Therefore "top" and "bottom" are numeric-factor terms, not strategy-strength terms.

---

## Direction Audit By Factor

| Factor | Strongest Sectors By Definition | Weakest Sectors By Definition | `bucket_1` Contains | `bucket_5` Contains | Invert Before Interpretation? |
|---|---|---|---|---|---|
| `rank_3m` | Lowest rank values, especially rank 1 | Highest rank values | Strongest sectors | Weakest sectors | Yes, interpret direction inversely |
| `sector_return_1m` | Highest 1M sector returns | Lowest 1M sector returns | Weakest trailing-return sectors | Strongest trailing-return sectors | No |
| `sector_return_3m` | Highest 3M sector returns | Lowest 3M sector returns | Weakest trailing-return sectors | Strongest trailing-return sectors | No |
| `sector_return_6m` | Highest 6M sector returns | Lowest 6M sector returns | Weakest trailing-return sectors | Strongest trailing-return sectors | No |

---

## Spearman IC Interpretation

### `rank_3m`

`rank_3m` is ordinal and lower is better.

Interpretation:

- **Negative IC:** stronger sectors, meaning lower rank numbers, are associated with higher forward returns.
- **Positive IC:** weaker sectors, meaning higher rank numbers, are associated with higher forward returns.

For `rank_3m`, the generated results show negative IC across all horizons:

| Horizon | Spearman IC | Interpretation |
|---|---:|---|
| 5d | -0.0347 | Stronger-ranked sectors outperform |
| 10d | -0.0523 | Stronger-ranked sectors outperform |
| 20d | -0.0683 | Stronger-ranked sectors outperform |
| 60d | -0.0310 | Stronger-ranked sectors outperform |

This interpretation is correct only if we remember that lower rank is stronger.

### `sector_return_1m`

Higher values mean stronger raw 1-month sector returns.

Interpretation:

- **Positive IC:** high 1M return sectors continue to outperform.
- **Negative IC:** low 1M return sectors outperform high 1M return sectors.

Generated ICs are negative across all horizons, so the results do not support simple 1M sector momentum.

### `sector_return_3m`

Higher values mean stronger raw 3-month sector returns.

Interpretation:

- **Positive IC:** high 3M return sectors continue to outperform.
- **Negative IC:** low 3M return sectors outperform high 3M return sectors.

Generated ICs are negative across all horizons, so the results suggest mean reversion rather than raw 3M sector momentum.

### `sector_return_6m`

Higher values mean stronger raw 6-month sector returns.

Interpretation:

- **Positive IC:** high 6M return sectors continue to outperform.
- **Negative IC:** low 6M return sectors outperform high 6M return sectors.

Generated ICs are negative across all horizons, with strongest negative values at 20d and 60d. This suggests pronounced mean reversion in raw 6M sector returns.

---

## Bucket Interpretation

### `rank_3m`

Because `bucket_1` has the lowest numeric values:

- `bucket_1` = strongest sectors
- `bucket_5` = weakest sectors

Therefore, for `rank_3m`:

```text
strong_sector_spread = bucket_1_return - bucket_5_return
```

The stored `bucket_spread` is:

```text
bucket_5_return - bucket_1_return
```

So for `rank_3m`, a negative stored `bucket_spread` means the strongest sectors outperformed.

### Raw Sector Return Factors

For `sector_return_1m`, `sector_return_3m`, and `sector_return_6m`:

- `bucket_1` = lowest trailing sector returns
- `bucket_5` = highest trailing sector returns

Therefore, for raw sector return factors:

```text
momentum_spread = bucket_5_return - bucket_1_return
```

This is the same as the stored `bucket_spread`.

For these factors, a negative stored `bucket_spread` means high trailing-return sectors underperformed low trailing-return sectors.

---

## Findings

### Finding 1: Bucket construction is mechanically consistent

The code consistently assigns buckets by ascending factor value. There is no accidental descending sort and no hidden inversion.

### Finding 2: `rank_3m` needs inverse interpretation

`rank_3m` is a rank, not a return. Lower values are better. The generated report correctly notes this in the interpretation notes, but the generic labels "Top Bucket" and "Bottom Bucket" can be confusing.

For `rank_3m`, `bucket_1` is the strongest sector bucket.

### Finding 3: Raw sector return results should not be described as bullish momentum

For `sector_return_1m`, `sector_return_3m`, and `sector_return_6m`, the negative ICs and negative bucket spreads mean high raw trailing-return sectors did not outperform. These results are more consistent with mean reversion than momentum.

### Finding 4: No code-level inversion is currently required for analysis

No factor values must be inverted to calculate Pearson, Spearman, or buckets. However, reporting and interpretation should use factor-specific direction labels.

For future scoring, inversion may be useful if the model wants all scoring inputs to mean "higher is better":

- `rank_3m` could be converted to an inverse rank score.
- Raw sector returns should not be converted to bullish scores without separate evidence.

---

## Answers To Requested Checks

### 1. Which bucket represents strongest sectors?

| Factor | Strongest Sector Bucket |
|---|---|
| `rank_3m` | `bucket_1` |
| `sector_return_1m` | `bucket_5` |
| `sector_return_3m` | `bucket_5` |
| `sector_return_6m` | `bucket_5` |

### 2. Which bucket represents weakest sectors?

| Factor | Weakest Sector Bucket |
|---|---|
| `rank_3m` | `bucket_5` |
| `sector_return_1m` | `bucket_1` |
| `sector_return_3m` | `bucket_1` |
| `sector_return_6m` | `bucket_1` |

### 3. Whether `bucket_1` is lowest values or highest values

`bucket_1` is always the lowest numeric factor values.

### 4. Whether Spearman IC sign interpretation is correct

It is correct if interpreted factor by factor:

- For `rank_3m`, negative IC is favorable for sector leadership because lower rank is stronger.
- For raw sector return fields, negative IC is unfavorable for momentum and suggests lower trailing-return sectors did better.

### 5. Whether factor values should be inverted before interpretation

For analysis:

- `rank_3m`: not required computationally, but interpretation must be inverted.
- `sector_return_1m`: no inversion.
- `sector_return_3m`: no inversion.
- `sector_return_6m`: no inversion.

For future scoring:

- `rank_3m` should likely be transformed into a "higher is better" sector score.
- Raw sector returns should not be used as bullish higher-is-better scores based on current evidence.

---

## Recommendation

Keep the current research output as mechanically valid, but interpret it with factor-specific direction.

For future reports, avoid generic labels like "Top Bucket" for `rank_3m` unless the report clarifies that "top" means highest numeric value, not strongest sector. A clearer report would include:

- `lowest_value_bucket_return`
- `highest_value_bucket_return`
- `strongest_sector_bucket`
- `weakest_sector_bucket`
- `leadership_spread`

No code changes were made as part of this audit.
