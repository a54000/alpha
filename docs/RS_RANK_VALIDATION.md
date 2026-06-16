# RS Rank Validation Report

**Date:** 2026-06-11  
**Features Audited:** rs_vs_nifty_20d, rs_vs_nifty_60d, rs_rank_pct  
**Purpose:** Validate implementation against specification and identify defects

---

## Specification

### FEATURE_REGISTRY.yaml

```yaml
rs_vs_nifty_20d:
  source: prices
  formula: "stock_return_20d / nifty500_return_20d"
  refresh: daily
  used_by: [swing_model, positional_model]
  notes: "Values > 1.0 = outperforming Nifty500"

rs_vs_nifty_60d:
  source: prices
  formula: "stock_return_60d / nifty500_return_60d"
  refresh: daily
  used_by: [positional_model, lt_model]

rs_rank_pct:
  source: prices
  formula: "PERCENTILE_RANK(rs_vs_nifty_20d) across NSE500 on that date"
  refresh: daily
  used_by: [swing_model, positional_model, lt_model, recommendation_history]
```

### INDICATOR_SPEC.md

```markdown
### RS vs Nifty 500

Formula: stock_return_Nd / nifty500_return_Nd
  where: return_Nd = (close_today - close_N_days_ago) / close_N_days_ago

Variants: rs_vs_nifty_20d, rs_vs_nifty_60d
Min history: 60 periods

Interpretation:
  > 1.0 : outperforming the index
  < 1.0 : underperforming the index
  > 1.2 : strong outperformance

Nifty500 reference: fetch ^CRSLDX or NIFTY500 index from yfinance

### RS Rank Percentile (Cross-Sectional)

Formula: PERCENT_RANK(rs_vs_nifty_20d) across all NSE500 on same date

Output: rs_rank_pct (0–100)
  100 = strongest relative strength in NSE500
  50  = median
  0   = weakest

IMPORTANT: This is a cross-sectional computation.
  All 500 stocks must have rs_vs_nifty_20d computed BEFORE
  this rank can be calculated for any single stock.

Compute sequence:
  1. Compute rs_vs_nifty_20d for all 500 stocks
  2. Rank all 500 stocks by rs_vs_nifty_20d
  3. Write rs_rank_pct for each stock

Library: pandas DataFrame.rank(pct=True) * 100
```

---

## Implementation

### compute_features.py

#### rs_vs_nifty_20d Calculation (Line 244)

```python
result["rs_vs_nifty_20d"] = close.pct_change(20)
```

**Actual Formula:** `stock_return_20d` (absolute return)  
**Specified Formula:** `stock_return_20d / nifty500_return_20d` (relative return)

#### rs_vs_nifty_60d Calculation (Line 245)

```python
result["rs_vs_nifty_60d"] = close.pct_change(60)
```

**Actual Formula:** `stock_return_60d` (absolute return)  
**Specified Formula:** `stock_return_60d / nifty500_return_60d` (relative return)

#### rs_rank_pct Calculation (Lines 78-85)

```python
def compute_rs_rank_pct(rs_vs_nifty_20d: pd.Series) -> pd.Series:
    """Cross-sectional percentile rank (0-100) for one trading date."""
    
    valid = rs_vs_nifty_20d.dropna()
    if valid.empty:
        return pd.Series(index=rs_vs_nifty_20d.index, dtype="float64")
    ranks = valid.rank(pct=True, method="average") * 100
    return ranks.reindex(rs_vs_nifty_20d.index)
```

**Actual Formula:** `PERCENTILE_RANK(rs_vs_nifty_20d)`  
**Specified Formula:** `PERCENTILE_RANK(rs_vs_nifty_20d) across NSE500`  
**Implementation:** Uses pandas `rank(pct=True, method="average") * 100`

#### Cross-Sectional Application (Lines 260-291)

```python
def _apply_rs_rank_pct(self, session, start_date: date, end_date: date) -> int:
    updated = 0
    dates = session.execute(
        select(FeaturesDaily.date)
        .where(FeaturesDaily.date.between(start_date, end_date))
        .distinct()
        .order_by(FeaturesDaily.date)
    ).scalars().all()

    for current_date in dates:
        rows = session.execute(
            select(FeaturesDaily.symbol, FeaturesDaily.rs_vs_nifty_20d)
            .where(FeaturesDaily.date == current_date)
        ).all()
        if not rows:
            continue

        rank_frame = pd.Series(
            {symbol: float(value) if value is not None else math.nan for symbol, value in rows},
            dtype="float64",
        )
        rank_pct = compute_rs_rank_pct(rank_frame)

        for symbol, value in rank_pct.items():
            if pd.isna(value):
                continue
            session.execute(
                update(FeaturesDaily)
                .where(FeaturesDaily.symbol == symbol, FeaturesDaily.date == current_date)
                .values(rs_rank_pct=round(float(value), 2))
            )
            updated += 1
    return updated
```

**Query:** All symbols from `features_daily` for each date  
**Filters:** None (no NSE500 filter, no eligibility filter)  
**Universe:** All symbols in database, not just NSE500

---

## Comparison Table

| Aspect | Specification | Implementation | Status |
|--------|--------------|----------------|--------|
| **rs_vs_nifty_20d Formula** | `stock_return_20d / nifty500_return_20d` | `close.pct_change(20)` | ❌ MISMATCH |
| **rs_vs_nifty_60d Formula** | `stock_return_60d / nifty500_return_60d` | `close.pct_change(60)` | ❌ MISMATCH |
| **rs_rank_pct Formula** | `PERCENTILE_RANK(rs_vs_nifty_20d)` | `rank(pct=True) * 100` | ✅ MATCH |
| **Ranking Direction** | 100 = strongest, 0 = weakest | 100 = strongest, 0 = weakest | ✅ CORRECT |
| **Ranking Universe** | NSE500 only | All symbols in database | ❌ INCORRECT |
| **Missing Value Handling** | Not specified | Drop NaN before ranking, reindex after | ✅ REASONABLE |
| **Benchmark Data Dependency** | Requires Nifty500 prices | No benchmark data used | ❌ MISSING |
| **Look-Ahead Bias** | Not specified | No look-ahead (uses same date data) | ✅ SAFE |

---

## Worked Example

### Scenario

Date: 2026-06-10  
Three stocks in database: RELIANCE.NS, TCS.NS, INFY.NS

### Specification-Expected Calculation

**Step 1: Compute individual stock returns**
```
RELIANCE.NS: close today = 3200, close 20d ago = 3000
  stock_return_20d = (3200 - 3000) / 3000 = 0.0667 (+6.67%)

TCS.NS: close today = 4000, close 20d ago = 3800
  stock_return_20d = (4000 - 3800) / 3800 = 0.0526 (+5.26%)

INFY.NS: close today = 1500, close 20d ago = 1400
  stock_return_20d = (1500 - 1400) / 1400 = 0.0714 (+7.14%)
```

**Step 2: Fetch Nifty500 return**
```
Nifty500: close today = 22000, close 20d ago = 21000
  nifty500_return_20d = (22000 - 21000) / 21000 = 0.0476 (+4.76%)
```

**Step 3: Compute relative strength**
```
RELIANCE.NS: rs_vs_nifty_20d = 0.0667 / 0.0476 = 1.40 (strong outperformance)
TCS.NS: rs_vs_nifty_20d = 0.0526 / 0.0476 = 1.11 (moderate outperformance)
INFY.NS: rs_vs_nifty_20d = 0.0714 / 0.0476 = 1.50 (strong outperformance)
```

**Step 4: Cross-sectional rank across NSE500**
```
Assume 500 stocks ranked by rs_vs_nifty_20d:
INFY.NS at percentile 95 → rs_rank_pct = 95
RELIANCE.NS at percentile 85 → rs_rank_pct = 85
TCS.NS at percentile 75 → rs_rank_pct = 75
```

### Actual Implementation Calculation

**Step 1: Compute absolute returns (no benchmark)**
```
RELIANCE.NS: rs_vs_nifty_20d = 0.0667 (+6.67%)
TCS.NS: rs_vs_nifty_20d = 0.0526 (+5.26%)
INFY.NS: rs_vs_nifty_20d = 0.0714 (+7.14%)
```

**Step 2: Cross-sectional rank across ALL symbols**
```
Assume 1000 symbols in database (not just NSE500):
INFY.NS at percentile 90 → rs_rank_pct = 90
RELIANCE.NS at percentile 80 → rs_rank_pct = 80
TCS.NS at percentile 70 → rs_rank_pct = 70
```

### Key Differences

| Aspect | Specification | Implementation |
|--------|--------------|----------------|
| **Input values** | Relative to Nifty500 (1.40, 1.11, 1.50) | Absolute returns (0.0667, 0.0526, 0.0714) |
| **Interpretation** | > 1.0 = outperforming | > 0 = positive return |
| **Ranking universe** | 500 NSE500 stocks | All symbols in database |
| **Ranking result** | Percentile of relative strength | Percentile of absolute momentum |

---

## Verification Results

### 1. Formula Matches Specification

**rs_vs_nifty_20d:** ❌ **FAIL**
- Specified: `stock_return_20d / nifty500_return_20d`
- Implemented: `close.pct_change(20)` (absolute return only)
- Missing: Division by Nifty500 return

**rs_vs_nifty_60d:** ❌ **FAIL**
- Specified: `stock_return_60d / nifty500_return_60d`
- Implemented: `close.pct_change(60)` (absolute return only)
- Missing: Division by Nifty500 return

**rs_rank_pct:** ✅ **PASS**
- Specified: `PERCENTILE_RANK(rs_vs_nifty_20d)`
- Implemented: `rank(pct=True, method="average") * 100`
- Note: Correct formula, but uses wrong input data

### 2. Ranking Direction is Correct

**Status:** ✅ **CORRECT**

**Verification:**
- Higher percentile = higher rank = stronger signal
- 100 = strongest, 0 = weakest
- Matches scoring rules (>= 90 gets max points)
- Pandas `rank(pct=True)` returns 0-1 range, multiplied by 100

### 3. Ranking Universe is Correct

**Status:** ❌ **INCORRECT**

**Specification:** "across NSE500 on that date"

**Implementation:** All symbols from `features_daily` table

**Query Analysis:**
```python
select(FeaturesDaily.symbol, FeaturesDaily.rs_vs_nifty_20d)
.where(FeaturesDaily.date == current_date)
```

**Missing Filters:**
- No join to `symbol_master` to check `nse500 = True`
- No date range check for `nse500_from_date` / `nse500_to_date`
- No filter for `is_eligible = True`

**Impact:**
- Ranks across entire database, not just NSE500
- May include delisted stocks, non-NSE500 stocks, ineligible stocks
- Percentile values computed on wrong universe

### 4. Missing Value Handling

**Status:** ✅ **REASONABLE**

**Implementation:**
```python
valid = rs_vs_nifty_20d.dropna()
if valid.empty:
    return pd.Series(index=rs_vs_nifty_20d.index, dtype="float64")
ranks = valid.rank(pct=True, method="average") * 100
return ranks.reindex(rs_vs_nifty_20d.index)
```

**Behavior:**
- Drops NaN values before ranking
- Computes ranks only on valid values
- Reindexes to original index (NaN positions preserved)
- Symbols with missing `rs_vs_nifty_20d` receive NaN `rs_rank_pct`

**Scoring Engine Handling:**
- NULL features score 0 (not error)
- Ineligible stocks receive NULL score
- Correct behavior for missing data

### 5. Dependency on Benchmark/Index Data

**Status:** ❌ **MISSING**

**Specification Requirements:**
- Nifty500 index prices required
- Fetch from yfinance (^CRSLDX or NIFTY500)
- Compute index return over same period

**Implementation Reality:**
- No index price storage table exists
- No index data ingestion pipeline
- No yfinance integration
- No reference to Nifty500 ticker in code

**Infrastructure Gap:**
- Missing: `index_prices_daily` table
- Missing: Index data fetching module
- Missing: Index return calculation function
- Missing: Calendar alignment logic (trading days vs calendar days)

**Impact:**
- Cannot compute true relative strength
- Feature is fundamentally broken
- Documentation promises unimplemented functionality

### 6. Look-Ahead Bias Risk

**Status:** ✅ **SAFE**

**Analysis:**

**Ranking Computation:**
- Runs after all individual features computed for date
- Uses only `rs_vs_nifty_20d` values from the same date
- No future data used in ranking calculation

**Underlying Data:**
- `close.pct_change(20)` uses historical prices only
- No look-ahead in return calculation
- Standard pandas operation, time-safe

**Pipeline Order:**
```python
# In generate() method:
1. Compute individual features for all symbols (lines 119-128)
2. Commit individual features (line 137)
3. Apply cross-sectional ranks (line 133)
```

**Conclusion:** No look-ahead bias in ranking computation. However, since the underlying `rs_vs_nifty_20d` is computed incorrectly (not relative to Nifty500), the bias question is moot for the intended feature.

---

## Verdict

### Overall Assessment

**CRITICAL DEFECT IDENTIFIED**

The relative strength features (`rs_vs_nifty_20d`, `rs_vs_nifty_60d`, `rs_rank_pct`) are fundamentally broken due to:

1. **Formula Mismatch:** Features compute absolute momentum instead of relative strength
2. **Missing Infrastructure:** No Nifty500 benchmark data exists in the system
3. **Wrong Universe:** Cross-sectional ranking includes all symbols, not just NSE500
4. **Misleading Names:** Feature names imply relative strength but compute absolute returns

### Severity

**CRITICAL** - The features are actively degrading model performance

**Evidence:**
- Factor analysis classification: Tier C (Remove / Rework)
- Poor predictive power confirmed in FACTOR_RESEARCH_SUMMARY.md
- Features used in all three scoring models (28 total points allocated)
- Current implementation provides no relative strength information

### Impact

**Scoring Models Affected:**
- **Swing Model:** 10 points (10% of total score)
- **Positional Model:** 18 points (18% of total score)
- **Long-Term Model:** 6 points (6% of total score via rs_vs_nifty_60d)

**Total Impact:** 34 points across all models

**Current State:**
- Models are using a broken signal
- Absolute momentum ranked cross-sectionally has low predictive power
- Feature names mislead users about what is being measured

---

## Recommended Action

### Immediate (Priority 1)

**1. Disable rs_rank_pct in All Scoring Models**
- Set rs_rank_pct weight to 0 in swing, positional, and long-term models
- Set rs_vs_nifty_60d weight to 0 in long-term model
- Rationale: Stop active performance degradation

**2. Reallocate Weights Temporarily**
- Swing: Increase RSI from 15 to 20, MACD from 10 to 15
- Positional: Increase EMA alignment from 25 to 30, ADX from 15 to 20
- Long-Term: Increase ROE from 12 to 15, ROCE from 12 to 15
- Rationale: Compensate for removed relative strength signals

### Short-Term (Priority 2)

**3. Implement Sector-Relative Strength**
- Leverage existing `sector_daily` infrastructure
- Compute `rs_vs_sector_20d = stock_return_20d / sector_return_20d`
- Add cross-sectional ranking for sector-relative values
- Rationale: Medium implementation effort, likely Tier B performance

**4. Validate Sector-Relative Implementation**
- Run factor analysis on sector-relative features
- Backtest scoring models with sector-relative signals
- Compare against baseline (no relative strength)
- Rationale: Validate predictive power before production

### Medium-Term (Priority 3)

**5. Implement Benchmark-Relative Strength**
- Create `index_prices_daily` table for Nifty500 data
- Implement index data ingestion pipeline (yfinance)
- Update feature computation to use index returns
- Rationale: True relative strength measurement, likely Tier A performance

**6. Validate Benchmark-Relative Implementation**
- Run factor analysis on corrected features
- Backtest scoring models with benchmark-relative signals
- Compare sector-relative vs benchmark-relative performance
- Rationale: Determine optimal relative strength definition

### Long-Term (Priority 4)

**7. Fix Ranking Universe**
- Add NSE500 filter to cross-sectional ranking query
- Filter by `symbol_master.nse500 = True`
- Add date range validation for `nse500_from_date` / `nse500_to_date`
- Rationale: Ensure ranking matches specification

**8. Update Documentation**
- Update FEATURE_REGISTRY.yaml to reflect final implementation
- Update INDICATOR_SPEC.md if formula changes
- Add data requirements documentation
- Rationale: Ensure documentation matches implementation

---

## Appendix: Data Quality Issues

### Current Data Gaps

1. **No Index Price Storage**
   - Missing: Table for Nifty500 historical prices
   - Impact: Cannot compute benchmark-relative returns
   - Required: `index_prices_daily` table

2. **No Index Data Ingestion**
   - Missing: Pipeline to fetch Nifty500 prices
   - Impact: No source for benchmark data
   - Required: yfinance integration or similar

3. **No Calendar Alignment**
   - Missing: Logic to align stock and index trading calendars
   - Impact: Potential mismatch in return periods
   - Required: Trading day calendar handling

4. **No Data Validation**
   - Missing: Checks for missing or stale index data
   - Impact: Silent failures in relative strength calculation
   - Required: Data quality monitoring and alerts

### Recommended Schema Addition

```sql
CREATE TABLE index_prices_daily (
    index_name VARCHAR(20) NOT NULL,
    date DATE NOT NULL,
    open NUMERIC(12,2),
    high NUMERIC(12,2),
    low NUMERIC(12,2),
    close NUMERIC(12,2),
    volume INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (index_name, date)
);

CREATE INDEX idx_index_prices_date ON index_prices_daily(date);
CREATE INDEX idx_index_prices_name ON index_prices_daily(index_name);
```

### Recommended Ingestion Module

```python
# app/ingestion/fetch_index_data.py
def fetch_nifty500_prices(start_date: date, end_date: date) -> pd.DataFrame:
    """Fetch Nifty500 index prices from yfinance."""
    ticker = yfinance.Ticker("^CRSLDX")  # or "NIFTY500.NS"
    data = ticker.history(start=start_date, end=end_date)
    return data

def store_index_prices(session, index_name: str, prices: pd.DataFrame):
    """Store index prices in database."""
    for date, row in prices.iterrows():
        session.add(IndexPricesDaily(
            index_name=index_name,
            date=date,
            open=row['Open'],
            high=row['High'],
            low=row['Low'],
            close=row['Close'],
            volume=row['Volume']
        ))
    session.commit()
```

---

## Conclusion

The relative strength features are critically broken and require immediate remediation. The current implementation computes absolute momentum instead of relative strength, ranks across the wrong universe, and lacks the necessary benchmark data infrastructure.

**Recommended Path Forward:**
1. Disable current implementation immediately
2. Implement sector-relative strength as intermediate solution
3. Implement benchmark-relative strength for true relative strength
4. Fix ranking universe to match NSE500 specification
5. Update documentation to reflect final implementation

**Expected Outcome:** Properly implemented relative strength signals should improve predictive power from Tier C to Tier A/B, enhancing performance across all three scoring models.
