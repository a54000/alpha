# Feature Validation Report

**Date:** 2026-06-11
**Purpose:** Validate that features_daily values match independently recomputed indicator values from prices_daily

---

## Executive Summary

- **PASS:** 10 indicators
- **WARN:** 0 indicators
- **FAIL:** 3 indicators

## Indicator-by-Indicator Results

### adx_14

- **Status:** FAIL
- **Sample Count:** 50
- **Mean Absolute Error:** 0.357178
- **Max Absolute Error:** 1.257153
- **Match Percentage:** 2.00%
- **Tolerance:** 1.00%

**Mismatches (49):**

| Symbol | Date | Computed | Stored | Error |
|--------|------|----------|--------|-------|
| ACC | 2026-06-03 | 16.9794 | 14.6700 | 0.1574 |
| 3MINDIA | 2026-06-03 | 23.7747 | 13.4100 | 0.7729 |
| ACC | 2026-06-04 | 16.1829 | 14.9600 | 0.0817 |
| ABB | 2026-06-05 | 49.7809 | 23.2100 | 1.1448 |
| AIAENG | 2026-06-05 | 43.4859 | 31.8800 | 0.3641 |
| AIAENG | 2026-06-03 | 36.9836 | 27.7500 | 0.3327 |
| ADANIPORTS | 2026-06-08 | 21.6578 | 24.3400 | 0.1102 |
| ABB | 2026-06-04 | 50.0576 | 23.1300 | 1.1642 |
| AIAENG | 2026-06-04 | 40.0012 | 29.6900 | 0.3473 |
| ABB | 2026-06-03 | 50.8991 | 22.9400 | 1.2188 |
| ... | ... | ... | ... | ... | (39 more) |

### bb_width

- **Status:** FAIL
- **Sample Count:** 50
- **Mean Absolute Error:** 0.025912
- **Max Absolute Error:** 0.026490
- **Match Percentage:** 0.00%
- **Tolerance:** 1.00%

**Mismatches (50):**

| Symbol | Date | Computed | Stored | Error |
|--------|------|----------|--------|-------|
| ACC | 2026-06-03 | 0.0753 | 0.0734 | 0.0258 |
| 3MINDIA | 2026-06-03 | 0.1047 | 0.1020 | 0.0264 |
| ACC | 2026-06-04 | 0.0726 | 0.0708 | 0.0258 |
| ABB | 2026-06-05 | 0.2162 | 0.2107 | 0.0260 |
| AIAENG | 2026-06-05 | 0.3014 | 0.2938 | 0.0260 |
| AIAENG | 2026-06-03 | 0.2696 | 0.2628 | 0.0260 |
| ADANIPORTS | 2026-06-08 | 0.0723 | 0.0705 | 0.0259 |
| ABB | 2026-06-04 | 0.2121 | 0.2068 | 0.0257 |
| AIAENG | 2026-06-04 | 0.2870 | 0.2797 | 0.0262 |
| ABB | 2026-06-03 | 0.2132 | 0.2078 | 0.0260 |
| ... | ... | ... | ... | ... | (40 more) |

### ema_200

- **Status:** FAIL
- **Sample Count:** 50
- **Mean Absolute Error:** 0.010237
- **Max Absolute Error:** 0.022502
- **Match Percentage:** 50.00%
- **Tolerance:** 1.00%

**Mismatches (25):**

| Symbol | Date | Computed | Stored | Error |
|--------|------|----------|--------|-------|
| ACC | 2026-06-03 | 1597.3300 | 1623.8900 | 0.0164 |
| ACC | 2026-06-04 | 1594.8770 | 1621.1700 | 0.0162 |
| ABB | 2026-06-05 | 5961.7195 | 6095.6900 | 0.0220 |
| AIAENG | 2026-06-05 | 3733.4718 | 3772.6400 | 0.0104 |
| AIAENG | 2026-06-03 | 3715.6902 | 3755.6500 | 0.0106 |
| ABB | 2026-06-04 | 5949.6011 | 6084.9200 | 0.0222 |
| AIAENG | 2026-06-04 | 3724.4544 | 3764.0200 | 0.0105 |
| ABB | 2026-06-03 | 5937.4765 | 6074.1600 | 0.0225 |
| ADANIGREEN | 2026-06-08 | 1082.2652 | 1105.7100 | 0.0212 |
| AAVAS | 2026-06-08 | 1425.7436 | 1443.7200 | 0.0125 |
| ... | ... | ... | ... | ... | (15 more) |

### rsi_14

- **Status:** PASS
- **Sample Count:** 50
- **Mean Absolute Error:** 0.000047
- **Max Absolute Error:** 0.000117
- **Match Percentage:** 100.00%
- **Tolerance:** 1.00%

### macd

- **Status:** PASS
- **Sample Count:** 50
- **Mean Absolute Error:** 0.000003
- **Max Absolute Error:** 0.000048
- **Match Percentage:** 100.00%
- **Tolerance:** 1.00%

### macd_signal

- **Status:** PASS
- **Sample Count:** 50
- **Mean Absolute Error:** 0.000003
- **Max Absolute Error:** 0.000020
- **Match Percentage:** 100.00%
- **Tolerance:** 1.00%

### macd_hist

- **Status:** PASS
- **Sample Count:** 50
- **Mean Absolute Error:** 0.000018
- **Max Absolute Error:** 0.000345
- **Match Percentage:** 100.00%
- **Tolerance:** 1.00%

### atr_14

- **Status:** PASS
- **Sample Count:** 50
- **Mean Absolute Error:** 0.000001
- **Max Absolute Error:** 0.000005
- **Match Percentage:** 100.00%
- **Tolerance:** 1.00%

### ema_5

- **Status:** PASS
- **Sample Count:** 50
- **Mean Absolute Error:** 0.000002
- **Max Absolute Error:** 0.000016
- **Match Percentage:** 100.00%
- **Tolerance:** 1.00%

### ema_13

- **Status:** PASS
- **Sample Count:** 50
- **Mean Absolute Error:** 0.000002
- **Max Absolute Error:** 0.000019
- **Match Percentage:** 100.00%
- **Tolerance:** 1.00%

### ema_20

- **Status:** PASS
- **Sample Count:** 50
- **Mean Absolute Error:** 0.000002
- **Max Absolute Error:** 0.000014
- **Match Percentage:** 100.00%
- **Tolerance:** 1.00%

### ema_50

- **Status:** PASS
- **Sample Count:** 50
- **Mean Absolute Error:** 0.000015
- **Max Absolute Error:** 0.000040
- **Match Percentage:** 100.00%
- **Tolerance:** 1.00%

### ema_150

- **Status:** PASS
- **Sample Count:** 50
- **Mean Absolute Error:** 0.004434
- **Max Absolute Error:** 0.009190
- **Match Percentage:** 100.00%
- **Tolerance:** 1.00%

---

## Mismatch Summary

**Total Mismatches:** 124

**Symbols Affected (10):**
- 3MINDIA: 10 mismatches
- AAVAS: 15 mismatches
- ABB: 15 mismatches
- ACC: 15 mismatches
- ADANIGREEN: 14 mismatches
- ADANIPORTS: 10 mismatches
- ADANIPOWER: 10 mismatches
- AIAENG: 15 mismatches
- APLAPOLLO: 10 mismatches
- AUBANK: 10 mismatches

**Dates Affected (5):**
- 2026-06-03: 25 mismatches
- 2026-06-04: 25 mismatches
- 2026-06-05: 25 mismatches
- 2026-06-08: 25 mismatches
- 2026-06-09: 24 mismatches

---

## Overall Verdict

**Verdict:** FAIL

3 indicator(s) failed validation with material deviations.

---

## Methodology

1. Selected 10 liquid NSE symbols based on recent trading activity.
2. Selected 5 dates per symbol from the most recent 6 months.
3. Loaded raw OHLCV data from prices_daily.
4. Independently recomputed indicators using standard formulas.
5. Compared against stored values in features_daily.

## Tolerance Thresholds

- **PASS:** Match percentage >= 95% (tolerance: 1.0%)
- **WARN:** Match percentage >= 80% (tolerance: 5.0%)
- **FAIL:** Match percentage < 80%

## Recommendations

1. **Investigate Failed Indicators:** Review calculation logic for indicators that failed validation.
2. **Check Data Quality:** Verify price data quality for affected symbols and dates.
3. **Recompute Features:** If calculation errors found, recompute features_daily for affected period.
4. **Re-run Validation:** After fixes, re-run validation to confirm corrections.

---

**Report Generated:** 2026-06-11
**Validation Script:** scripts/run_feature_validation.py