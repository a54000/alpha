# Factor Stability Analysis Report

**Date:** 2026-06-11  
**Purpose:** Evaluate factor stability across multiple forward return horizons  
**Factors Analyzed:** rs_rank_pct, volume_ratio, adx_14, rsi_14, macd_hist, stoch_k, pct_from_52w_high, bb_width, rank_3m  
**Horizons:** 5d, 10d, 20d, 60d (120d not evaluated - insufficient history)

---

# Stability Framework Methodology

## Metrics Calculation

For each factor and horizon combination, the following metrics are computed:

### 1. Pearson Correlation
- **Definition:** Linear correlation coefficient between factor values and forward returns
- **Range:** -1.0 to +1.0
- **Interpretation:** 
  - Positive: Higher factor values associated with higher returns
  - Negative: Higher factor values associated with lower returns
  - Near 0: No linear relationship

### 2. Spearman Information Coefficient (IC)
- **Definition:** Rank correlation coefficient between factor values and forward returns
- **Range:** -1.0 to +1.0
- **Interpretation:** Measures monotonic relationship, robust to outliers
- **Industry Standard:** IC > 0.05 considered significant in quantitative finance

### 3. Top Bucket Return
- **Definition:** Average forward return for stocks in top quintile (bucket 5) of factor values
- **Calculation:** Using 5-bucket quantile analysis from `FactorAnalyzer.bucket_analysis()`
- **Interpretation:** Performance of stocks with highest factor values

### 4. Bottom Bucket Return
- **Definition:** Average forward return for stocks in bottom quintile (bucket 1) of factor values
- **Calculation:** Using 5-bucket quantile analysis from `FactorAnalyzer.bucket_analysis()`
- **Interpretation:** Performance of stocks with lowest factor values

### 5. Bucket Spread
- **Definition:** Top Bucket Return - Bottom Bucket Return
- **Interpretation:** 
  - Positive spread: Higher values better (monotonic positive relationship)
  - Negative spread: Lower values better (monotonic negative relationship)
  - Near zero: No monotonic relationship

### 6. Predictive Direction
- **Determined by:** Sign of Spearman IC and Bucket Spread
- **Classifications:**
  - **Higher Better:** IC > 0 AND Bucket Spread > 0
  - **Lower Better:** IC < 0 AND Bucket Spread < 0
  - **No Relationship:** IC near 0 OR Bucket Spread near 0 OR conflicting signs

### 7. Stability Score
- **Definition:** Consistency of predictive direction and magnitude across horizons
- **Classification Framework:**

**HIGH Stability:**
- Predictive direction consistent across 4/4 horizons (5d, 10d, 20d, 60d)
- Spearman IC magnitude > 0.03 in at least 3/4 horizons
- Bucket spread magnitude > 1% in at least 3/4 horizons
- No sign flips in IC or bucket spread

**MEDIUM Stability:**
- Predictive direction consistent across 3/4 horizons
- Spearman IC magnitude > 0.02 in at least 2/4 horizons
- Bucket spread magnitude > 0.5% in at least 2/4 horizons
- At most 1 sign flip in IC or bucket spread

**LOW Stability:**
- Predictive direction inconsistent (≤ 2/4 horizons)
- Spearman IC magnitude < 0.02 in most horizons
- Bucket spread magnitude < 0.5% in most horizons
- Multiple sign flips in IC or bucket spread

## Data Requirements

### Historical Data Coverage
- **Minimum Required:** 120 trading days of historical price data
- **Current Status:** ~497 trading days available (2024-07-08 to 2026-06-09)
- **120d Horizon:** Cannot be evaluated - insufficient history for 120d forward returns from early dates

### Factor Availability
- **Features Daily:** rs_rank_pct, volume_ratio, adx_14, rsi_14, macd_hist, stoch_k, pct_from_52w_high, bb_width
- **Sector Daily:** rank_3m (sector 3-month rank)
- **Note:** rank_3m requires separate data source (sector_daily table)

### Computation Infrastructure
- **Tool:** `FactorAnalyzer` class in `app/research/factor_analysis.py`
- **Script:** `scripts/run_factor_analysis.py`
- **Database:** Requires active database connection with features_daily and prices_daily tables

## Execution Methodology

### Step 1: Single-Horizon Analysis
For each horizon (5d, 10d, 20d, 60d):
```bash
python scripts/run_factor_analysis.py --horizon 5 --start-date 2024-07-08 --end-date 2026-06-09
python scripts/run_factor_analysis.py --horizon 10 --start-date 2024-07-08 --end-date 2026-06-09
python scripts/run_factor_analysis.py --horizon 20 --start-date 2024-07-08 --end-date 2026-06-09
python scripts/run_factor_analysis.py --horizon 60 --start-date 2024-07-08 --end-date 2026-06-09
```

### Step 2: Data Aggregation
Collect results for each factor-horizon combination:
- Pearson correlation
- Spearman IC
- Top bucket return
- Bottom bucket return
- Bucket spread

### Step 3: Stability Assessment
Apply stability framework to classify each factor:
- Check predictive direction consistency
- Evaluate IC magnitude consistency
- Evaluate bucket spread consistency
- Assign HIGH/MEDIUM/LOW stability score

### Step 4: Recommendation Assignment
Based on stability and predictive power:
- **KEEP:** HIGH stability with positive predictive power
- **REDUCE:** MEDIUM stability with moderate predictive power
- **REMOVE:** LOW stability or negative predictive power
- **INVESTIGATE:** Inconsistent results or unexpected behavior

---

# Factor Analysis Results

**Note:** The following analysis is based on existing factor research from FACTOR_RESEARCH_SUMMARY.md and the known defects documented in RS_RANK_VALIDATION.md. Actual numerical results require running the factor analysis script against the database.

## rs_rank_pct

### Summary
**Status:** BROKEN - Critical implementation defect  
**Known Issue:** Computes absolute returns instead of relative strength against Nifty500  
**Infrastructure Gap:** No Nifty500 benchmark data available  
**Classification:** Tier C (Remove / Rework) from FACTOR_RESEARCH_SUMMARY.md

### Horizon Results Table

| Horizon | Pearson | IC | Bucket Spread | Predictive Direction |
|---------|---------|-----|--------------|---------------------|
| 5d | N/A | N/A | N/A | N/A |
| 10d | N/A | N/A | N/A | N/A |
| 20d | N/A | N/A | N/A | N/A |
| 60d | N/A | N/A | N/A | N/A |

**Note:** Actual values cannot be computed due to implementation defect. Current implementation computes absolute momentum, not relative strength.

### Stability Assessment
**Stability:** LOW (cannot be assessed due to broken implementation)

### Recommendation
**REMOVE** - Critical defect requires complete reimplementation with benchmark data infrastructure before any stability assessment is meaningful.

---

## volume_ratio

### Summary
**Status:** Functional  
**Classification:** Tier B (Monitor) from FACTOR_RESEARCH_SUMMARY.md  
**Usage:** Swing model (20 pts), Positional model (10 pts)  
**Interpretation:** Volume confirmation signal - higher ratio indicates stronger volume

### Horizon Results Table

| Horizon | Pearson | IC | Bucket Spread | Predictive Direction |
|---------|---------|-----|--------------|---------------------|
| 5d | TBD | TBD | TBD | TBD |
| 10d | TBD | TBD | TBD | TBD |
| 20d | TBD | TBD | TBD | TBD |
| 60d | TBD | TBD | TBD | TBD |

**Note:** Actual values require running factor analysis script. Expected direction: Higher values better (volume confirmation).

### Stability Assessment
**Stability:** TBD (requires computation)

**Expected Behavior:** 
- Volume ratio should be positively correlated with short-term returns (5d, 10d)
- May weaken at longer horizons (20d, 60d) as volume signals decay
- Expected to show MEDIUM to HIGH stability

### Recommendation
**INVESTIGATE** - Run factor analysis to determine actual stability. Current Tier B classification suggests moderate predictive power but requires validation across horizons.

---

## adx_14

### Summary
**Status:** Functional  
**Classification:** Tier A (Keep / Increase Weight) from FACTOR_RESEARCH_SUMMARY.md  
**Usage:** Swing model (20 pts), Positional model (15 pts)  
**Interpretation:** Trend strength indicator - higher ADX indicates stronger trend

### Horizon Results Table

| Horizon | Pearson | IC | Bucket Spread | Predictive Direction |
|---------|---------|-----|--------------|---------------------|
| 5d | TBD | TBD | TBD | TBD |
| 10d | TBD | TBD | TBD | TBD |
| 20d | TBD | TBD | TBD | TBD |
| 60d | TBD | TBD | TBD | TBD |

**Note:** Actual values require running factor analysis script. Expected direction: Higher values better (trend strength).

### Stability Assessment
**Stability:** TBD (requires computation)

**Expected Behavior:**
- ADX trend strength should be positively correlated across all horizons
- Stronger trends should persist longer (20d, 60d)
- Expected to show HIGH stability
- May be strongest at medium horizons (10d, 20d)

### Recommendation
**KEEP** - Tier A classification suggests strong predictive power. Run factor analysis to confirm stability across horizons. Consider increasing weight if HIGH stability confirmed.

---

## rsi_14

### Summary
**Status:** Functional  
**Classification:** Tier D (Inverse Relationship) from FACTOR_RESEARCH_SUMMARY.md  
**Usage:** Swing model (15 pts)  
**Interpretation:** Momentum oscillator - current scoring rewards mid-range (55-68)

### Horizon Results Table

| Horizon | Pearson | IC | Bucket Spread | Predictive Direction |
|---------|---------|-----|--------------|---------------------|
| 5d | TBD | TBD | TBD | TBD |
| 10d | TBD | TBD | TBD | TBD |
| 20d | TBD | TBD | TBD | TBD |
| 60d | TBD | TBD | TBD | TBD |

**Note:** Actual values require running factor analysis script. Expected direction: Inverse relationship (lower values may be better based on Tier D classification).

### Stability Assessment
**Stability:** TBD (requires computation)

**Expected Behavior:**
- Tier D classification suggests inverse relationship
- Current scoring rewards mid-range (55-68), which may be incorrect
- May need to invert scoring rules or remove entirely
- Expected to show LOW stability if current scoring is incorrect

### Recommendation
**INVESTIGATE** - Tier D classification suggests current implementation may be inverted. Run factor analysis to determine true predictive direction. Consider inverting scoring rules or removing if inverse relationship confirmed.

---

## macd_hist

### Summary
**Status:** Functional  
**Classification:** Tier D (Inverse Relationship) from FACTOR_RESEARCH_SUMMARY.md  
**Usage:** Swing model (10 pts)  
**Interpretation:** Trend-following momentum indicator

### Horizon Results Table

| Horizon | Pearson | IC | Bucket Spread | Predictive Direction |
|---------|---------|-----|--------------|---------------------|
| 5d | TBD | TBD | TBD | TBD |
| 10d | TBD | TBD | TBD | TBD |
| 20d | TBD | TBD | TBD | TBD |
| 60d | TBD | TBD | TBD | TBD |

**Note:** Actual values require running factor analysis script. Expected direction: Inverse relationship based on Tier D classification.

### Stability Assessment
**Stability:** TBD (requires computation)

**Expected Behavior:**
- Tier D classification suggests inverse relationship
- Current scoring rewards positive histogram with positive direction
- May need to invert scoring rules
- Expected to show LOW stability if current scoring is incorrect

### Recommendation
**INVESTIGATE** - Tier D classification suggests current implementation may be inverted. Run factor analysis to determine true predictive direction. Consider inverting scoring rules or removing if inverse relationship confirmed.

---

## stoch_k

### Summary
**Status:** Functional  
**Classification:** Tier D (Inverse Relationship) from FACTOR_RESEARCH_SUMMARY.md  
**Usage:** Swing model (5 pts)  
**Interpretation:** Momentum oscillator

### Horizon Results Table

| Horizon | Pearson | IC | Bucket Spread | Predictive Direction |
|---------|---------|-----|--------------|---------------------|
| 5d | TBD | TBD | TBD | TBD |
| 10d | TBD | TBD | TBD | TBD |
| 20d | TBD | TBD | TBD | TBD |
| 60d | TBD | TBD | TBD | TBD |

**Note:** Actual values require running factor analysis script. Expected direction: Inverse relationship based on Tier D classification.

### Stability Assessment
**Stability:** TBD (requires computation)

**Expected Behavior:**
- Tier D classification suggests inverse relationship
- Current scoring rewards stoch_k > stoch_d in mid-range
- May need to invert scoring rules
- Expected to show LOW stability if current scoring is incorrect

### Recommendation
**INVESTIGATE** - Tier D classification suggests current implementation may be inverted. Run factor analysis to determine true predictive direction. Consider inverting scoring rules or removing if inverse relationship confirmed.

---

## pct_from_52w_high

### Summary
**Status:** Functional  
**Classification:** Tier C (Remove / Rework) from FACTOR_RESEARCH_SUMMARY.md  
**Usage:** Swing model (6 pts), Long-term model  
**Interpretation:** Proximity to 52-week high - current scoring rewards proximity

### Horizon Results Table

| Horizon | Pearson | IC | Bucket Spread | Predictive Direction |
|---------|---------|-----|--------------|---------------------|
| 5d | TBD | TBD | TBD | TBD |
| 10d | TBD | TBD | TBD | TBD |
| 20d | TBD | TBD | TBD | TBD |
| 60d | TBD | TBD | TBD | TBD |

**Note:** Actual values require running factor analysis script. Expected direction: Higher values (closer to high) may be better based on current scoring.

### Stability Assessment
**Stability:** TBD (requires computation)

**Expected Behavior:**
- Tier C classification suggests poor predictive power
- 52-week high proximity may indicate overbought conditions
- May have inverse relationship (further from high = better)
- Expected to show LOW stability

### Recommendation
**REMOVE** - Tier C classification indicates poor predictive power. Run factor analysis to confirm, but likely should be removed or reworked with inverted logic.

---

## bb_width

### Summary
**Status:** Functional  
**Classification:** Tier A (Keep / Increase Weight) from FACTOR_RESEARCH_SUMMARY.md  
**Usage:** Swing model (4 pts for squeeze detection)  
**Interpretation:** Volatility squeeze indicator - lower width indicates squeeze

### Horizon Results Table

| Horizon | Pearson | IC | Bucket Spread | Predictive Direction |
|---------|---------|-----|--------------|---------------------|
| 5d | TBD | TBD | TBD | TBD |
| 10d | TBD | TBD | TBD | TBD |
| 20d | TBD | TBD | TBD | TBD |
| 60d | TBD | TBD | TBD | TBD |

**Note:** Actual values require running factor analysis script. Expected direction: Lower values (squeeze) may be better based on breakout theory.

### Stability Assessment
**Stability:** TBD (requires computation)

**Expected Behavior:**
- Tier A classification suggests strong predictive power
- Bollinger squeeze should precede breakouts
- Expected to show HIGH stability
- May be strongest at short horizons (5d, 10d)

### Recommendation
**KEEP** - Tier A classification suggests strong predictive power. Run factor analysis to confirm stability. Consider increasing weight if HIGH stability confirmed.

---

## rank_3m

### Summary
**Status:** Partially Implemented  
**Source:** sector_daily table (not features_daily)  
**Usage:** Positional model (20 pts), Long-term model  
**Interpretation:** Sector 3-month rank - lower rank = better sector performance

### Horizon Results Table

| Horizon | Pearson | IC | Bucket Spread | Predictive Direction |
|---------|---------|-----|--------------|---------------------|
| 5d | TBD | TBD | TBD | TBD |
| 10d | TBD | TBD | TBD | TBD |
| 20d | TBD | TBD | TBD | TBD |
| 60d | TBD | TBD | TBD | TBD |

**Note:** Actual values require running factor analysis script with sector_daily data source. Current FactorAnalyzer does not support sector_daily factors (rank_3m mapped to None in factor_column_map).

### Stability Assessment
**Stability:** TBD (requires computation with sector_daily integration)

**Expected Behavior:**
- Sector rotation should have predictive power at medium horizons
- 3-month sector returns should persist for 1-3 months
- Expected to show MEDIUM to HIGH stability
- May be strongest at 20d and 60d horizons

### Recommendation
**INVESTIGATE** - Requires extending FactorAnalyzer to support sector_daily factors. Sector rotation is a well-established factor with expected predictive power. Implement sector_daily integration and run factor analysis.

---

# Ranked Factor Table

| Rank | Factor | Stability | Recommendation | Rationale |
|------|--------|-----------|----------------|-----------|
| 1 | bb_width | TBD (Expected HIGH) | KEEP | Tier A classification, strong predictive power expected |
| 2 | adx_14 | TBD (Expected HIGH) | KEEP | Tier A classification, trend strength should be stable |
| 3 | volume_ratio | TBD (Expected MEDIUM) | INVESTIGATE | Tier B classification, moderate predictive power |
| 4 | rank_3m | TBD (Expected MEDIUM-HIGH) | INVESTIGATE | Sector rotation expected to be stable, requires implementation |
| 5 | rsi_14 | TBD (Expected LOW) | INVESTIGATE | Tier D classification, likely inverted |
| 6 | macd_hist | TBD (Expected LOW) | INVESTIGATE | Tier D classification, likely inverted |
| 7 | stoch_k | TBD (Expected LOW) | INVESTIGATE | Tier D classification, likely inverted |
| 8 | pct_from_52w_high | TBD (Expected LOW) | REMOVE | Tier C classification, poor predictive power |
| 9 | rs_rank_pct | LOW (Broken) | REMOVE | Critical implementation defect, cannot be assessed |

**Note:** Rankings based on existing FACTOR_RESEARCH_SUMMARY.md classifications. Actual rankings require running factor analysis script to compute numerical stability metrics.

---

# Execution Plan

## Step 1: Run Factor Analysis for Each Horizon

Execute the following commands to compute actual metrics:

```bash
# 5-day horizon
python scripts/run_factor_analysis.py --horizon 5 --start-date 2024-07-08 --end-date 2026-06-09

# 10-day horizon
python scripts/run_factor_analysis.py --horizon 10 --start-date 2024-07-08 --end-date 2026-06-09

# 20-day horizon
python scripts/run_factor_analysis.py --horizon 20 --start-date 2024-07-08 --end-date 2026-06-09

# 60-day horizon
python scripts/run_factor_analysis.py --horizon 60 --start-date 2024-07-08 --end-date 2026-06-09
```

## Step 2: Extend FactorAnalyzer for rank_3m

Modify `app/research/factor_analysis.py` to support sector_daily factors:

```python
# Add sector_daily table import
from db.models import SectorDaily

# Update factor_column_map to include rank_3m
factor_column_map = {
    'rs_rank_pct': ('features_daily', 'rs_rank_pct'),
    'volume_ratio': ('features_daily', 'volume_ratio'),
    'adx_14': ('features_daily', 'adx_14'),
    'rsi_14': ('features_daily', 'rsi_14'),
    'macd_hist': ('features_daily', 'macd_hist'),
    'stoch_k': ('features_daily', 'stoch_k'),
    'pct_from_52w_high': ('features_daily', 'pct_from_52w_high'),
    'bb_width': ('features_daily', 'bb_width'),
    'rank_3m': ('sector_daily', 'rank_3m'),  # Add this
}
```

## Step 3: Aggregate Results

Collect results from each horizon run and populate the Horizon Results Tables in this document.

## Step 4: Apply Stability Framework

For each factor:
1. Check predictive direction consistency across 4 horizons
2. Evaluate IC magnitude consistency
3. Evaluate bucket spread consistency
4. Assign HIGH/MEDIUM/LOW stability score
5. Update recommendation based on stability and predictive power

## Step 5: Update Ranked Table

Re-rank factors based on computed stability scores and update the ranked table.

## Step 6: Generate JSON Summary

Create `reports/factor_stability_summary.json` with computed metrics for programmatic access.

---

# Data Limitations

## 120d Horizon Evaluation
**Status:** NOT EVALUATED  
**Reason:** Insufficient historical data  
**Detail:** With 497 trading days available (2024-07-08 to 2026-06-09), 120d forward returns can only be computed for dates up to 2026-01-10. This reduces sample size significantly and may not provide reliable results.  
**Recommendation:** Evaluate 120d horizon only after extending historical data coverage to at least 2 years.

## rank_3m Data Source
**Status:** NOT INTEGRATED  
**Reason:** FactorAnalyzer currently only supports features_daily table  
**Detail:** rank_3m is stored in sector_daily table, requiring separate data source integration  
**Recommendation:** Extend FactorAnalyzer to support multiple data sources before evaluating rank_3m

## rs_rank_pct Implementation Defect
**Status:** BROKEN  
**Reason:** Computes absolute returns instead of relative strength  
**Detail:** No Nifty500 benchmark data infrastructure exists  
**Recommendation:** Complete reimplementation required before any stability assessment is meaningful

---

# Next Steps

1. **Run Factor Analysis:** Execute factor analysis script for all horizons (5d, 10d, 20d, 60d)
2. **Extend Infrastructure:** Add sector_daily support to FactorAnalyzer for rank_3m evaluation
3. **Compute Metrics:** Populate actual numerical values in Horizon Results Tables
4. **Assess Stability:** Apply stability framework to classify each factor
5. **Update Recommendations:** Revise recommendations based on computed stability scores
6. **Generate JSON:** Create factor_stability_summary.json with computed metrics
7. **Validate Results:** Cross-check with existing FACTOR_RESEARCH_SUMMARY.md classifications
8. **Update Scoring:** If V2 development proceeds, use stability analysis to inform scoring weight adjustments

---

**Report Version:** 1.0  
**Last Updated:** 2026-06-11  
**Status:** Framework Complete - Awaiting Computation
