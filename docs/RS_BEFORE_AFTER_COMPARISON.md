# RS Before-After Comparison

**Date:** 2026-06-11  
**Purpose:** Compare old RS implementation (absolute momentum) vs new RS implementation (excess return vs benchmark)  
**Status:** Complete

---

# Executive Summary

The RS features have been remediated from absolute momentum to true relative strength using benchmark excess returns. Factor analysis of the corrected rs_rank_pct shows **no predictive improvement** over the old implementation. The corrected RS features continue to show near-zero correlations and poor predictive performance.

**Verdict:** The RS remediation has not improved predictive power. The features remain Tier C (poor predictive performance).

---

# Implementation Comparison

## Old Implementation (V0)

**Formula:**
```python
result["rs_vs_nifty_20d"] = close.pct_change(20)
result["rs_vs_nifty_60d"] = close.pct_change(60)
```

**Interpretation:** Absolute momentum (stock return only)

**Ranking Universe:** All symbols

**Issues:**
- Computed absolute returns instead of relative strength
- No benchmark comparison
- Misleading feature names

---

## New Implementation (V1)

**Formula:**
```python
stock_return_20d = close.pct_change(20)
stock_return_60d = close.pct_change(60)

index_close_aligned = index_close.reindex(close.index)
index_return_20d = index_close_aligned.pct_change(20)
index_return_60d = index_close_aligned.pct_change(60)

result["rs_vs_nifty_20d"] = stock_return_20d - index_return_20d
result["rs_vs_nifty_60d"] = stock_return_60d - index_return_60d
```

**Interpretation:** Excess return vs Nifty500 benchmark (subtraction for stability)

**Ranking Universe:** NSE500 only

**Improvements:**
- True relative strength calculation
- Benchmark comparison with Nifty500
- Numerically stable (subtraction vs ratio)
- Correct ranking universe

---

# Factor Analysis Results

## rs_rank_pct Performance

### Horizon: 5d

| Metric | Value |
|--------|-------|
| Sample Size | 204,140 |
| Pearson Correlation | -0.0073 |
| Spearman IC | -0.0032 |
| Average Return | -0.0003 |
| Median Return | -0.0025 |
| Top Bucket Return | -0.0004 |
| Bottom Bucket Return | 0.0005 |

**Interpretation:** Near-zero correlation, negative predictive signal (worse than random)

---

### Horizon: 10d

| Metric | Value |
|--------|-------|
| Sample Size | 201,970 |
| Pearson Correlation | -0.0060 |
| Spearman IC | -0.0011 |
| Average Return | -0.0005 |
| Median Return | -0.0047 |
| Top Bucket Return | -0.0003 |
| Bottom Bucket Return | 0.0007 |

**Interpretation:** Near-zero correlation, negative predictive signal (worse than random)

---

### Horizon: 20d

| Metric | Value |
|--------|-------|
| Sample Size | 197,630 |
| Pearson Correlation | -0.0032 |
| Spearman IC | 0.0015 |
| Average Return | -0.0015 |
| Median Return | -0.0074 |
| Top Bucket Return | -0.0008 |
| Bottom Bucket Return | -0.0004 |

**Interpretation:** Near-zero correlation, slightly positive IC but still poor

---

### Horizon: 60d

| Metric | Value |
|--------|-------|
| Sample Size | 180,270 |
| Pearson Correlation | 0.0036 |
| Spearman IC | 0.0087 |
| Average Return | -0.0128 |
| Median Return | -0.0278 |
| Top Bucket Return | -0.0122 |
| Bottom Bucket Return | -0.0142 |

**Interpretation:** Near-zero correlation, slightly positive IC but still poor

---

# Comparison Table

## Spearman IC Comparison

| Horizon | Old IC (Estimated) | New IC | Change |
|---------|-------------------|--------|--------|
| 5d | ~0.01 | -0.0032 | -0.0132 (worse) |
| 10d | ~0.01 | -0.0011 | -0.0111 (worse) |
| 20d | ~0.01 | 0.0015 | -0.0085 (worse) |
| 60d | ~0.01 | 0.0087 | -0.0013 (worse) |

**Note:** Old IC values are estimated from previous factor research summary. New IC values are from actual analysis of corrected RS features.

---

## Bucket Spread Comparison

| Horizon | Old Spread (Estimated) | New Spread | Change |
|---------|----------------------|------------|--------|
| 5d | ~0.001 | -0.0009 | -0.0019 (worse) |
| 10d | ~0.002 | -0.0010 | -0.0030 (worse) |
| 20d | ~0.003 | -0.0004 | -0.0034 (worse) |
| 60d | ~0.005 | 0.0020 | -0.0030 (worse) |

**Note:** Bucket spread = Top Bucket Return - Bottom Bucket Return. Negative spread means top bucket underperformed bottom bucket (inverted relationship).

---

# Predictive Improvement Assessment

## Correlation Analysis

**Old Implementation:** Estimated Spearman IC ~0.01 (poor but slightly positive)

**New Implementation:** Actual Spearman IC ranges from -0.0032 to 0.0087 (near-zero to poor)

**Verdict:** **NO IMPROVEMENT** - The corrected RS features show similar or worse predictive power compared to the old implementation.

---

## Monotonicity Analysis

**Expected:** Higher rs_rank_pct should correlate with higher forward returns (monotonic relationship)

**Actual:** 
- 5d: Top bucket return (-0.0004) < Bottom bucket return (0.0005) - INVERTED
- 10d: Top bucket return (-0.0003) < Bottom bucket return (0.0007) - INVERTED
- 20d: Top bucket return (-0.0008) < Bottom bucket return (-0.0004) - INVERTED
- 60d: Top bucket return (-0.0122) > Bottom bucket return (-0.0142) - CORRECT but both negative

**Verdict:** **NO MONOTONICITY IMPROVEMENT** - The relationship remains inverted or non-monotonic for most horizons.

---

## Stability Analysis

**Old Implementation:** Consistently poor across horizons (Tier C)

**New Implementation:** Consistently poor across horizons (Tier C)

**Verdict:** **NO STABILITY IMPROVEMENT** - The features remain consistently poor across all horizons.

---

# Root Cause Analysis

## Why Did Remediation Not Improve Predictive Power?

### 1. Market Regime

The Nifty500 benchmark may not be the appropriate benchmark for individual stock relative strength. Reasons:
- Nifty500 is a broad market index
- Individual stock performance may not correlate with broad market movements
- Sector-specific benchmarks may be more appropriate
- The relationship between stock returns and index returns may be weak

### 2. Formula Choice

The subtraction formula (`stock_return - index_return`) may not capture relative strength effectively:
- Subtraction assumes linear relationship between stock and index returns
- May not account for volatility differences
- May not capture beta-adjusted relative strength
- Alternative formulas (e.g., beta-adjusted, risk-adjusted) may be more effective

### 3. Time Horizon

The 20d and 60d horizons may not be optimal for relative strength:
- Short-term relative strength may be more predictive
- Long-term relative strength may be more predictive
- The chosen horizons may not match the market regime

### 4. Universe Definition

Ranking within NSE500 may not be optimal:
- NSE500 includes stocks from diverse sectors
- Sector-relative strength may be more predictive
- Market-cap-weighted ranking may be more appropriate

### 5. Feature Redundancy

The RS features may be redundant with other momentum features:
- Absolute momentum (20d, 60d returns) already in the model
- RS may not provide incremental information
- The model may already capture momentum through other features

---

# Recommendations

## Immediate Actions

1. **DO NOT DEPLOY** - The corrected RS features do not show predictive improvement
2. **REMOVE RS WEIGHT** - Reduce or remove RS weight from scoring models
3. **KEEP OLD DATA** - Maintain historical RS data for comparison if needed

## Future Research

1. **Sector-Relative Strength** - Test sector-relative strength instead of market-relative
2. **Alternative Formulas** - Test beta-adjusted, risk-adjusted, or ratio-based formulas
3. **Different Horizons** - Test shorter (5d, 10d) or longer (120d, 250d) horizons
4. **Alternative Benchmarks** - Test Nifty50, Nifty100, or sector indices as benchmarks
5. **Feature Selection** - Test if RS provides incremental information beyond existing momentum features

---

# Conclusion

The RS remediation has successfully corrected the implementation defect (absolute momentum → true relative strength), but has not improved predictive power. The corrected RS features continue to show near-zero correlations and poor predictive performance across all horizons.

**Final Verdict:** REMOVE - The RS features should be removed from the model due to lack of predictive power.

---

**Report Version:** 1.0  
**Last Updated:** 2026-06-11  
**Analysis Status:** COMPLETE
