# RS Formula Decision Document

**Date:** 2026-06-11  
**Purpose:** Document implementation decisions for Relative Strength (RS) formulas  
**Status:** Updated (Formula Changed from Ratio to Subtraction)

---

# Specification Review

## Documented Formulas

### FEATURE_REGISTRY.yaml
```yaml
rs_vs_nifty_20d:
  formula: "stock_return_20d / nifty500_return_20d"
  notes: "Values > 1.0 = outperforming Nifty500"

rs_vs_nifty_60d:
  formula: "stock_return_60d / nifty500_return_60d"
```

### INDICATOR_SPEC.md
```markdown
Formula: stock_return_Nd / nifty500_return_Nd
  where: return_Nd = (close_today - close_N_days_ago) / close_N_days_ago

Interpretation:
  > 1.0 : outperforming the index
  < 1.0 : underperforming the index
  > 1.2 : strong outperformance
```

---

# Implementation Decisions

## Decision 1: Benchmark Index Selection

**Chosen Index:** Nifty500 Total Return Index (^CRSLDX) from yfinance

**Rationale:**
- Total return index includes dividends, providing true investor return comparison
- Matches specification requirement for Nifty500 benchmark
- Widely available via yfinance API
- Industry standard for relative strength calculations

**Symbol Mapping:**
- Internal name: "NIFTY500"
- yfinance ticker: "^CRSLDX"
- Stored in: `INDEX_SYMBOL_MAP` in `app/loaders/index_loader.py`

---

## Decision 2: Return Calculation Method

**Formula Implemented (UPDATED):**
```
rs_vs_nifty_Nd = stock_return_Nd - nifty500_return_Nd

where:
  stock_return_Nd = (close_today - close_N_days_ago) / close_N_days_ago
  nifty500_return_Nd = (index_close_today - index_close_N_days_ago) / index_close_N_days_ago
```

**Implementation Details:**
- Uses pandas `pct_change(N)` for both stock and index returns
- Aligns index close prices with stock dates using `reindex()` before computing returns
- Computes returns on aligned data to ensure date consistency
- Uses subtraction instead of division for numerical stability
- Handles missing index data with fallback to absolute returns (should not occur in production)

**Code Location:** `app/indicators/compute_features.py`, lines 269-290

---

## Decision 2.1: Formula Change (Ratio → Subtraction)

**Original Formula (REJECTED):**
```
rs_vs_nifty_Nd = stock_return_Nd / nifty500_return_Nd
```

**New Formula (ADOPTED):**
```
rs_vs_nifty_Nd = stock_return_Nd - nifty500_return_Nd
```

**Rationale for Change:**

### Issue with Ratio Formula

The ratio formula (`stock_return / index_return`) is numerically unstable due to:

1. **Division by Near-Zero:** When index returns are close to zero, the ratio becomes extremely large
   - Example: stock_return = 0.02, index_return = 0.0001 → RS = 200 (unrealistic)
   - Example: stock_return = 0.02, index_return = -0.0001 → RS = -200 (unrealistic)

2. **Database Overflow:** Large ratios exceed database column precision
   - Column: `rs_vs_nifty_20d Numeric(8, 4)` (max value: 9999.9999)
   - Observed values: 103.9263, 22535.9365, -12437.9038, -11547.3124
   - These values cause numeric field overflow errors

3. **Interpretation Issues:** Ratio values are not intuitive
   - Ratio = 1.0 means stock matches benchmark
   - Ratio = 2.0 means stock outperformed by 100% (rare)
   - Ratio = 0.5 means stock underperformed by 50% (rare)
   - Extreme values (> 10 or < 0.1) are common due to near-zero denominators

### Advantages of Subtraction Formula

The subtraction formula (`stock_return - index_return`) is numerically stable:

1. **No Division by Zero:** Subtraction cannot cause division-by-zero errors
   - Result is always finite if inputs are finite
   - No special handling needed for zero returns

2. **Bounded Output:** Result is bounded by return ranges
   - Stock returns typically: -0.20 to +0.20 (-20% to +20%)
   - Index returns typically: -0.10 to +0.10 (-10% to +10%)
   - RS range typically: -0.30 to +0.30 (-30% to +30%)
   - Fits easily in Numeric(8, 4) column

3. **Intuitive Interpretation:** Subtraction is easier to understand
   - RS = 0.05 means stock outperformed benchmark by 5 percentage points
   - RS = -0.03 means stock underperformed benchmark by 3 percentage points
   - RS = 0.00 means stock matched benchmark performance

4. **Linear Scaling:** Subtraction preserves linear relationships
   - 2x outperformance = 2x RS value
   - Consistent with other momentum factors

### Examples

**Example 1: Positive Benchmark Return**
```
Stock: +8% return (0.08)
Index: +5% return (0.05)

Ratio formula: 0.08 / 0.05 = 1.6 (outperforming)
Subtraction formula: 0.08 - 0.05 = 0.03 (+3 percentage points)
```

**Example 2: Negative Benchmark Return**
```
Stock: +2% return (0.02)
Index: -3% return (-0.03)

Ratio formula: 0.02 / -0.03 = -0.67 (underperforming)
Subtraction formula: 0.02 - (-0.03) = 0.05 (+5 percentage points)
```

**Example 3: Near-Zero Benchmark Return (Problematic for Ratio)**
```
Stock: +2% return (0.02)
Index: +0.01% return (0.0001)

Ratio formula: 0.02 / 0.0001 = 200 (UNREALISTIC, causes overflow)
Subtraction formula: 0.02 - 0.0001 = 0.0199 (+1.99 percentage points)
```

**Example 4: Zero Benchmark Return (Problematic for Ratio)**
```
Stock: +2% return (0.02)
Index: 0% return (0.00)

Ratio formula: 0.02 / 0.00 = INF or NaN (division by zero)
Subtraction formula: 0.02 - 0.00 = 0.02 (+2 percentage points)
```

### Impact on Interpretation

**Old Interpretation (Ratio):**
- RS > 1.0: Outperforming benchmark
- RS < 1.0: Underperforming benchmark
- RS = 1.0: Matching benchmark

**New Interpretation (Subtraction):**
- RS > 0: Outperforming benchmark (positive excess return)
- RS < 0: Underperforming benchmark (negative excess return)
- RS = 0: Matching benchmark (zero excess return)

**Impact on Ranking:**
- Ranking direction unchanged: higher RS = stronger performance
- rs_rank_pct calculation unchanged: percentile rank of RS values
- Scoring logic unchanged: higher rs_rank_pct gets more points

### Migration Notes

**Breaking Change:** This is a breaking change in RS interpretation
- Old RS values (ratio) cannot be directly compared to new RS values (subtraction)
- Historical RS values must be recomputed
- Factor research must be re-run with new formula

**Non-Breaking Aspects:**
- Ranking direction unchanged (higher = better)
- rs_rank_pct calculation unchanged
- Scoring logic unchanged
- Only the RS formula itself changes

---

## Decision 3: Date Alignment

**Approach:** Calendar-based alignment using pandas `reindex()`

**Rationale:**
- Stock and index prices are both stored with date keys
- Using `reindex()` ensures alignment on trading days
- Missing index dates result in NaN returns (handled gracefully)
- Simpler than implementing trading calendar alignment

**Trade-offs:**
- Does not account for non-trading days (holidays, weekends)
- May have slight misalignment if index has different trading calendar
- Acceptable for research phase; can be refined in V2 if needed

---

## Decision 4: Universe Filtering for rs_rank_pct

**Filtering Rules:**
- Only rank symbols where `symbol_master.nse500 = True`
- Only rank symbols where `current_date >= nse500_from_date`
- Only rank symbols where `current_date <= nse500_to_date` OR `nse500_to_date IS NULL`

**Rationale:**
- Matches specification: "across NSE500 on that date"
- Excludes delisted or downgraded stocks
- Excludes stocks not yet added to NSE500
- Uses existing symbol_master metadata

**Code Location:** `app/indicators/compute_features.py`, lines 315-325

---

## Decision 5: Missing Data Handling

**Stock Price Missing:**
- Results in NaN stock return
- Results in NaN rs_vs_nifty value
- Excluded from ranking (dropped before percentile calculation)

**Index Price Missing:**
- Results in NaN index return
- Results in NaN rs_vs_nifty value (division by NaN)
- Excluded from ranking

**Division by Zero:**
- Index return of 0 replaced with `pd.NA` before division
- Results in NaN rs_vs_nifty value
- Excluded from ranking

**Fallback Behavior:**
- If index_prices is None or empty, falls back to absolute returns
- This is a safety measure; should not occur in production
- Logs would indicate missing index data

---

# Implementation Summary

## Files Modified

1. **db/models.py**
   - Added `IndexPricesDaily` model
   - Columns: index_name, date, open, high, low, close, volume

2. **alembic/versions/007_add_index_prices_daily.py**
   - Migration to create index_prices_daily table
   - Includes unique constraint on (index_name, date)

3. **app/loaders/index_loader.py**
   - New file for index data ingestion
   - Supports NIFTY500 via ^CRSLDX ticker
   - Methods: load(), backfill(), incremental_update()

4. **app/loaders/__init__.py**
   - New file for loaders package

5. **app/indicators/compute_features.py**
   - Added IndexPricesDaily import
   - Added `_load_index_frame()` method
   - Modified `generate()` to load index prices
   - Modified `_compute_symbol_features()` to accept index_prices
   - Updated RS calculation to use benchmark returns
   - Updated `_apply_rs_rank_pct()` to filter NSE500 universe

6. **tests/test_index_loader.py**
   - New test file for index_loader
   - Tests: symbol map, upsert, backfill, incremental update

---

## Formula Comparison

| Aspect | Old Implementation (V0) | New Implementation (V1) |
|--------|-------------------|-------------------|
| **rs_vs_nifty_20d** | `close.pct_change(20)` | `stock_return_20d - nifty500_return_20d` |
| **rs_vs_nifty_60d** | `close.pct_change(60)` | `stock_return_60d - nifty500_return_60d` |
| **Benchmark Data** | None | Nifty500 Total Return Index (^CRSLDX) |
| **Interpretation** | Absolute momentum | Excess return vs benchmark |
| **Ranking Universe** | All symbols | NSE500 only |
| **Value > 0** | Positive return | Outperforming benchmark |
| **Value < 0** | Negative return | Underperforming benchmark |
| **Typical Range** | -0.20 to +0.20 | -0.30 to +0.30 |

**Note:** The original V1 implementation attempted to use a ratio formula (`stock_return / index_return`), but this was rejected due to numerical instability and database overflow issues. The subtraction formula was adopted instead.

---

# Validation Requirements

## Pre-Deployment Validation

1. **Index Data Loading**
   - Verify NIFTY500 data loads successfully
   - Check date range coverage matches stock data
   - Validate no gaps in index data

2. **RS Calculation**
   - Verify rs_vs_nifty values > 0 for outperforming stocks
   - Verify rs_vs_nifty values < 0 for underperforming stocks
   - Verify rs_vs_nifty values are in expected range (-0.30 to +0.30)
   - Check for NaN values and ensure proper handling

3. **Ranking Universe**
   - Verify ranking only includes NSE500 symbols
   - Verify exclusion of delisted stocks
   - Verify exclusion of pre-NSE500 stocks

4. **Cross-Sectional Ranking**
   - Verify percentile ranks are 0-100 range
   - Verify 100 = strongest, 0 = weakest
   - Verify sum of ranks equals NSE500 count

---

# Future Considerations

## Potential Enhancements

1. **Trading Calendar Alignment**
   - Implement proper trading calendar alignment
   - Handle index holidays vs stock holidays
   - Use pandas business day offsets

2. **Multiple Benchmarks**
   - Support sector-relative strength
   - Support custom benchmarks
   - Allow benchmark selection per factor

3. **Alternative RS Definitions**
   - Log returns instead of arithmetic returns
   - Risk-adjusted relative strength
   - Sector-relative vs benchmark-relative comparison

4. **Data Quality Monitoring**
   - Alerts for missing index data
   - Validation of index data freshness
   - Automated backfill scheduling

---

**Document Version:** 1.0  
**Last Updated:** 2026-06-11  
**Next Review:** After RS factor research completion
