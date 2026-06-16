# RS Data Validation Report

**Date:** 2026-06-11  
**Purpose:** Validate RS feature recomputation results  
**Status:** FAILED - Critical Implementation Bug

---

# Issue Summary

**Status:** ❌ FAILED - Critical Bug Identified

**Problem:** RS feature recomputation failed with numeric field overflow error. The RS values being computed are extremely large (e.g., rs_vs_nifty_20d = 103.92632365742867, rs_vs_nifty_60d = 22535.936569900285), which exceed the database column precision of Numeric(8, 4) that can only hold values less than 10^4.

**Expected Behavior:** RS values should be around 1.0 (e.g., 1.2 for 20% outperformance, 0.8 for 20% underperformance).

**Actual Behavior:** RS values are 100-20000x larger than expected.

---

# Root Cause Analysis

## Manual Calculation Test

Using actual data from the database:

**Index Data (NIFTY500):**
- 2026-06-09: close=22370.15
- 2026-05-06: close=23133.40 (20 days ago)

**Stock Data (TRENT):**
- 2026-06-09: close=2771.30
- 2026-05-06: close=2859.87 (20 days ago)

**Manual Calculation:**
- Index 20d return: (22370.15 - 23133.40) / 23133.40 = -0.01867 (-1.87%)
- Stock 20d return: (2771.30 - 2859.87) / 2859.87 = 0.02626 (+2.63%)
- RS (stock/index): 0.02626 / -0.01867 = -1.41

**Result:** Manual calculation produces reasonable RS value of -1.41.

**Conclusion:** The data is correct, but the implementation has a bug.

---

# Implementation Bug Analysis

## Suspected Issue

The RS calculation in `compute_features.py` may have a bug in the data alignment or return calculation logic. The values being produced (100-20000x expected) suggest one of the following:

1. **Index data loading issue:** The index data may not be loaded correctly or aligned properly
2. **Return calculation issue:** The pct_change() may be computing returns incorrectly
3. **Division issue:** The division may be using wrong values (e.g., dividing by very small numbers)
4. **Data type issue:** The data may be in different units (e.g., index in points, stock in rupees)

## Database Column Constraint

**Column Definition:** `rs_vs_nifty_20d: Mapped[float | None] = mapped_column(Numeric(8, 4))`

**Constraint:** Numeric(8, 4) can hold values up to 9999.9999

**Error:** Values like 22535.936569900285 exceed this limit

**Impact:** Cannot store computed RS values in current schema.

---

# Index Data Quality

## Null Values

**Finding:** 1 null close price in index data (2026-06-10)

**Impact:** This null will cause NaN returns for dates that reference it, which is handled gracefully. This is not the root cause of the overflow issue.

## Data Range

**Index Close Range:** ~22000-23000 (Nifty500 Total Return Index)

**Stock Close Range:** ~2700-2900 (TRENT)

**Note:** These are in different units (index points vs stock price), but this is correct for relative strength calculation since we use percentage returns, not absolute prices.

---

# Immediate Actions Required

## 1. Debug Implementation

**Priority:** CRITICAL

**Action:** Add detailed logging to the RS calculation in `compute_features.py` to identify:
- Actual index_close values
- Actual stock close values
- Computed index returns
- Computed stock returns
- Final RS values

**Goal:** Identify where the calculation goes wrong.

## 2. Fix Implementation

**Priority:** CRITICAL

**Action:** Once the bug is identified, fix the RS calculation logic.

**Expected Fix:** RS values should be in range 0.5-2.0 for normal market conditions.

## 3. Consider Schema Change

**Priority:** MEDIUM

**Action:** If the RS formula is correct but produces larger values than expected, consider:
- Increasing column precision to Numeric(12, 4) or similar
- Or capping RS values at a reasonable maximum (e.g., 10.0)

**Note:** This should only be done if the formula is correct and the large values are legitimate.

---

# Deployment Readiness

**Status:** ❌ NOT READY

**Blocking Issue:** RS calculation produces values that exceed database column precision.

**Risk:** HIGH - Cannot proceed with feature recomputation until this is fixed.

**Recommendation:** 
1. Debug and fix the RS calculation implementation
2. Re-run feature recomputation
3. Validate RS values are in expected range
4. Proceed with factor analysis

---

# Next Steps

1. Add logging to compute_features.py RS calculation
2. Run feature recomputation with logging enabled
3. Analyze logs to identify the bug
4. Fix the implementation
5. Retry feature recomputation
6. Validate RS values
7. Proceed with factor analysis

---

**Report Version:** 1.0  
**Last Updated:** 2026-06-11  
**Validation Status:** FAILED - Critical Bug
