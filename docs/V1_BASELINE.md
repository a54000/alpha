# V1 Baseline Document

**Date:** 2026-06-11  
**Version:** 1.0 (FROZEN)  
**Purpose:** Establish baseline for all future V2 research and implementation comparisons

---

# Executive Summary

## Current Status of V1

V1 represents the initial implementation of the NSE Research Platform, featuring three scoring models (Swing, Positional, Long-Term), a complete feature computation pipeline, sector rotation analysis, and backtesting infrastructure. The platform is functionally complete but has been validated to underperform the Nifty500 benchmark.

## Backtest Verdict

**UNDERPERFORMS_BENCHMARK**

Both Swing and Positional recommendation models underperform the Nifty500 benchmark across all tested horizons. The models show negative average returns, sub-50% win rates, and profit factors below 1.0, indicating that current scoring rules do not generate alpha.

## Benchmark Comparison

**Swing Model (20-day horizon):**
- Model Return: -0.42%
- Benchmark Return (^CRSLDX): -0.29%
- Alpha: -0.13%
- Verdict: Underperforms

**Positional Model (3-month horizon):**
- Model Return: -2.07%
- Benchmark Return (^CRSLDX): -1.80%
- Alpha: -0.27%
- Verdict: Underperforms

## Major Strengths

1. **Complete Infrastructure:** Full data pipeline from ingestion to backtesting
2. **Clean Architecture:** Well-separated concerns (features, scoring, backtesting)
3. **Comprehensive Feature Set:** 30+ technical indicators computed daily
4. **Sector Rotation:** Daily sector strength computation and ranking
5. **Cross-Sectional Ranking:** Proper implementation of percentile-based ranking
6. **Database Design:** Normalized schema with proper constraints
7. **Test Coverage:** Unit tests for core functionality
8. **Documentation:** Extensive specification and validation documents

## Major Weaknesses

1. **Poor Predictive Performance:** Models underperform benchmark by 0.13-0.27% per period
2. **Broken Relative Strength:** RS features compute absolute returns instead of relative strength
3. **No Score Differentiation:** Higher scores do not correlate with better performance
4. **Sub-50% Win Rates:** Most horizons show win rates below 50%
5. **Missing Benchmark Infrastructure:** No Nifty500 index data storage or ingestion
6. **No Transaction Costs:** Backtest ignores slippage, brokerage, STT, stamp duty
7. **Limited Exit Logic:** Fixed-horizon returns only, no stop-loss or target-based exits
8. **Survivorship Bias:** Does not account for NSE500 composition changes over time

---

# Architecture Snapshot

## Data Pipeline Stages

```
1. Data Ingestion
   ├─ Fetch stock prices from external source
   ├─ Validate and clean data
   └─ Store in prices_daily table

2. Feature Computation
   ├─ Compute technical indicators for each symbol
   ├─ Store in features_daily table
   └─ Apply cross-sectional rankings (rs_rank_pct)

3. Sector Strength Computation
   ├─ Compute sector returns (1M, 3M, 6M)
   ├─ Rank sectors by performance
   └─ Store in sector_daily table

4. Scoring
   ├─ Compute swing_score for all symbols
   ├─ Compute position_score for all symbols
   ├─ Compute lt_score for all symbols
   └─ Store in daily_scores table

5. Recommendation Generation
   ├─ Rank symbols by score within each model
   ├─ Apply eligibility filters
   ├─ Generate top-N recommendations
   └─ Store in recommendation_history table

6. Backtesting
   ├─ Load historical recommendations
   ├─ Compute forward returns
   ├─ Calculate performance metrics
   └─ Generate backtest reports
```

## features_daily

**Purpose:** Store daily computed technical indicators for all symbols

**Schema:**
- Primary Key: (symbol, date)
- 30+ technical indicator columns
- Eligibility flags (is_eligible)
- Sector assignment
- Relative strength features (broken implementation)

**Key Columns:**
- Trend: ema_5, ema_13, ema_20, ema_50, ema_150, ema_200, adx_14, adx_prev
- Momentum: rsi_14, rsi_9, macd_line, macd_signal, macd_hist, macd_hist_prev, stoch_k, stoch_d
- Volatility: atr_14, bb_upper, bb_mid, bb_lower, bb_width, bb_width_20avg, bb_pct
- Volume: volume_20avg, volume_ratio
- Breakout: high_52w, low_52w, pct_from_52w_high, distance_from_52w_high, pct_from_52w_low, is_52w_breakout
- Relative Strength: rs_vs_nifty_20d, rs_vs_nifty_60d, rs_rank_pct (BROKEN)
- Eligibility: is_eligible, avg_traded_value, sector

**Computation:** Daily via `app/indicators/compute_features.py`
**Warm-up Period:** 300 trading days
**Update Frequency:** Daily

## sector_daily

**Purpose:** Store daily sector performance metrics and rankings

**Schema:**
- Primary Key: (sector, date)
- 19 canonical sectors
- Return calculations (1M, 3M, 6M)
- Composite scoring
- Cross-sectional rankings

**Key Columns:**
- Returns: return_1m, return_3m, return_6m, sector_return_1m, sector_return_3m, sector_return_6m
- Scoring: sector_score, composite_score
- Rankings: sector_rank, rank_3m, rank_composite
- Metadata: stock_count

**Computation:** Daily via `app/sectors/compute_sector_strength.py`
**Method:** Equal-weighted average of all NSE500 stocks in sector
**Scoring Formula:** return_1m * 0.20 + return_3m * 0.50 + return_6m * 0.30

## daily_scores

**Purpose:** Store daily scores for all symbols across three models

**Schema:**
- Primary Key: (symbol, date)
- Model version tracking
- Component breakdown scores
- Risk management metrics

**Key Columns:**
- Final Scores: swing_score, position_score, lt_score
- Swing Components: swing_trend, swing_momentum, swing_volume, swing_breakout, swing_rs
- Risk Metrics: stop_loss, target_1, target_2, target_3, rr_ratio
- Versioning: model_version_id

**Computation:** Daily via scoring engine (not fully implemented in V1)
**Update Frequency:** Daily

## recommendation_history

**Purpose:** Store historical recommendations for backtesting and analysis

**Schema:**
- Primary Key: (date, model, symbol)
- Recommendation metadata
- Entry/exit tracking
- Performance attribution

**Key Columns:**
- Identification: date, model, rank, symbol, score
- Entry: entry_price, stop_loss, target_1, rr_ratio
- Features at Entry: rsi_14, adx_14, volume_ratio, rs_rank_pct, sector_rank, bb_width_ratio
- Exit: exit_date, exit_price, exit_reason, return_pct, holding_days
- Reasoning: reason_codes (JSON)

**Generation:** Daily via recommendation engine
**Top-N Limits:** Swing (20), Positional (20), Long-Term (20)

## backtesting

**Purpose:** Validate predictive performance of recommendation models

**Implementation:** `app/backtesting/run_backtest.py`

**Capabilities:**
- Load historical recommendations
- Compute forward returns (5d, 10d, 20d, 1M, 3M, 6M)
- Calculate performance metrics (win rate, avg return, profit factor)
- Benchmark comparison (^CRSLDX)
- Score bucket analysis
- JSON report generation

**Limitations:**
- No transaction costs
- Close-to-close entry assumption (should be next-day-open)
- Fixed-horizon returns only (no dynamic exits)
- No survivorship bias correction
- No risk-adjusted metrics (Sharpe, Sortino, Calmar)

---

# Scoring Models

## Swing Scoring Model

**Horizon:** 5–30 days  
**Composition:** 100% technical  
**Output Column:** swing_score

### Factors

**Trend (30 points)**
- ADX strength + direction (20 pts)
- EMA short-term alignment (10 pts)

**Momentum (30 points)**
- RSI (15 pts)
- MACD histogram (10 pts)
- Stochastic (5 pts)

**Volume (20 points)**
- Volume ratio (20 pts)

**Breakout (10 points)**
- 52-week high proximity (6 pts)
- Bollinger squeeze (4 pts)

**Relative Strength (10 points)**
- RS rank percentile (10 pts)

### Weights

| Component | Max pts | Sub-signals |
|-----------|---------|-------------|
| Trend | 30 | ADX strength (20) + EMA alignment (10) |
| Momentum | 30 | RSI (15) + MACD histogram (10) + Stochastic (5) |
| Volume | 20 | Volume ratio (20) |
| Breakout | 10 | 52-week high proximity (6) + Bollinger squeeze (4) |
| Relative Strength | 10 | RS rank percentile (10) |
| **Total** | **100** | |

### Thresholds

**ADX strength + direction (20 pts):**
- adx_14 >= 35 AND adx_14 > adx_prev: 20 pts
- adx_14 >= 25 AND adx_14 > adx_prev: 14 pts
- adx_14 >= 25 AND adx_14 <= adx_prev: 8 pts
- adx_14 >= 20: 4 pts
- adx_14 < 20: 0 pts

**EMA short-term alignment (10 pts):**
- close > ema_5 AND ema_5 > ema_13: 10 pts
- close > ema_13: 6 pts
- close > ema_20: 3 pts
- close <= ema_20: 0 pts

**RSI (15 pts):**
- 55 <= rsi_14 <= 68: 15 pts
- 50 <= rsi_14 < 55: 9 pts
- 68 < rsi_14 <= 75: 7 pts
- 45 <= rsi_14 < 50: 4 pts
- rsi_14 > 75: 2 pts
- rsi_14 < 45: 0 pts

**MACD histogram (10 pts):**
- macd_hist > 0 AND macd_hist > macd_hist_prev: 10 pts
- macd_hist > 0 AND macd_hist <= macd_hist_prev: 5 pts
- macd_hist < 0 AND macd_hist > macd_hist_prev: 3 pts
- macd_hist < 0 AND macd_hist <= macd_hist_prev: 0 pts

**Stochastic (5 pts):**
- stoch_k > stoch_d AND 50 <= stoch_k <= 80: 5 pts
- stoch_k > stoch_d AND stoch_k < 50: 3 pts
- stoch_k > stoch_d AND stoch_k > 80: 1 pts
- stoch_k <= stoch_d: 0 pts

**Volume ratio (20 pts):**
- volume_ratio >= 3.0: 20 pts
- volume_ratio >= 2.0: 15 pts
- volume_ratio >= 1.5: 10 pts
- volume_ratio >= 1.2: 5 pts
- volume_ratio < 1.2: 0 pts

**52-week high proximity (6 pts):**
- pct_from_52w_high >= -2: 6 pts
- pct_from_52w_high >= -5: 4 pts
- pct_from_52w_high >= -10: 2 pts
- pct_from_52w_high < -10: 0 pts

**Bollinger squeeze (4 pts):**
- bb_width < bb_width_20avg * 0.70: 4 pts
- bb_width < bb_width_20avg * 0.85: 2 pts
- bb_width >= bb_width_20avg: 0 pts

**RS rank percentile (10 pts):**
- rs_rank_pct >= 90: 10 pts
- rs_rank_pct >= 75: 7 pts
- rs_rank_pct >= 60: 4 pts
- rs_rank_pct >= 50: 2 pts
- rs_rank_pct < 50: 0 pts

### Scoring Ranges

| Score | Band |
|-------|------|
| 90–100 | Exceptional Opportunity |
| 80–89 | Strong Opportunity |
| 70–79 | Worth Watching |
| 60–69 | Weak Signal |
| < 60 | Not Eligible for Top-20 outputs |

---

## Positional Scoring Model

**Horizon:** 1–6 months  
**Composition:** 40% trend + 30% relative strength + 20% sector + 10% volume  
**Output Column:** position_score

### Factors

**Trend (40 points)**
- EMA Stage 2 alignment (25 pts)
- ADX medium-term (15 pts)

**Relative Strength (30 points)**
- RS rank 20-day (18 pts)
- RS vs Nifty 60-day (12 pts)

**Sector Strength (20 points)**
- Sector 3-month rank (20 pts)

**Volume (10 points)**
- Volume ratio (10 pts)

### Weights

| Component | Max pts | Sub-signals |
|-----------|---------|-------------|
| Trend | 40 | EMA Stage 2 alignment (25) + ADX medium-term (15) |
| Relative Strength | 30 | RS rank 20-day (18) + RS vs Nifty 60-day (12) |
| Sector Strength | 20 | Sector 3-month rank (20) |
| Volume | 10 | Volume ratio (10) |
| **Total** | **100** | |

### Thresholds

**EMA Stage 2 alignment (25 pts):**
- close > ema_50 AND ema_50 > ema_150 AND ema_150 > ema_200: 25 pts
- close > ema_50 AND close > ema_200: 16 pts
- close > ema_200 only: 8 pts
- close < ema_200: 0 pts

**ADX medium-term (15 pts):**
- adx_14 >= 30 AND adx_14 > adx_prev: 15 pts
- adx_14 >= 25: 9 pts
- adx_14 >= 20: 4 pts
- adx_14 < 20: 0 pts

**RS rank percentile — 20-day (18 pts):**
- rs_rank_pct >= 85: 18 pts
- rs_rank_pct >= 70: 12 pts
- rs_rank_pct >= 55: 6 pts
- rs_rank_pct < 55: 0 pts

**RS vs Nifty — 60-day (12 pts):**
- rs_vs_nifty_60d >= 1.20: 12 pts
- rs_vs_nifty_60d >= 1.10: 8 pts
- rs_vs_nifty_60d >= 1.00: 4 pts
- rs_vs_nifty_60d < 1.00: 0 pts

**Sector 3-month rank (20 pts):**
- sector_3m_rank == 1: 20 pts
- sector_3m_rank == 2: 17 pts
- sector_3m_rank == 3: 14 pts
- sector_3m_rank 4–5: 10 pts
- sector_3m_rank 6–8: 5 pts
- sector_3m_rank >= 9: 0 pts

**Volume ratio (10 pts):**
- volume_ratio >= 2.0: 10 pts
- volume_ratio >= 1.5: 7 pts
- volume_ratio >= 1.2: 4 pts
- volume_ratio < 1.2: 0 pts

### Scoring Ranges

| Score | Band |
|-------|------|
| 90–100 | Exceptional Opportunity |
| 80–89 | Strong Opportunity |
| 70–79 | Worth Watching |
| 60–69 | Weak Signal |
| < 60 | Not Eligible for Top-20 outputs |

---

## Long-Term Scoring Model

**Horizon:** 1–3 years  
**Composition:** 40% growth + 30% quality + 15% valuation + 15% price trend  
**Output Column:** lt_score

### Current Implementation Status

**Status:** NOT FULLY IMPLEMENTED

The Long-Term model is defined in specification documents but lacks:
- Fundamental data ingestion pipeline
- Scoring engine implementation
- Recommendation generation
- Backtesting integration

### Missing Dependencies

**Fundamental Data:**
- No fundamentals table populated with quarterly data
- No revenue, PAT, equity, debt data
- No PE ratio computation
- No sector median PE calculation
- No announced_date tracking for 5-day lag rule

**Scoring Engine:**
- No lt_score computation logic implemented
- No fundamental feature integration
- No 5-day lag rule enforcement

**Recommendation Engine:**
- No Long-Term recommendation generation
- No top-N ranking for lt_score
- No recommendation_history entries for lt_model

### Factors (Defined but Not Implemented)

**Growth Quality (40 points)**
- Revenue CAGR 3Y (20 pts)
- PAT CAGR 3Y (20 pts)

**Business Quality (30 points)**
- ROE (12 pts)
- ROCE (12 pts)
- Debt/Equity (6 pts)

**Valuation (15 points)**
- PE vs sector median (15 pts)

**Price Trend (15 points)**
- EMA 200 position (9 pts)
- RS vs Nifty 60d (6 pts)

### Weights (Specification Only)

| Component | Max pts | Sub-signals |
|-----------|---------|-------------|
| Growth Quality | 40 | Revenue CAGR 3Y (20) + PAT CAGR 3Y (20) |
| Business Quality | 30 | ROE (12) + ROCE (12) + Debt/Equity (6) |
| Valuation | 15 | PE vs sector median (15) |
| Price Trend | 15 | EMA 200 position (9) + RS vs Nifty 60d (6) |
| **Total** | **100** | |

### Thresholds (Specification Only)

**Revenue CAGR 3-year (20 pts):**
- revenue_cagr_3y >= 25%: 20 pts
- revenue_cagr_3y >= 18%: 14 pts
- revenue_cagr_3y >= 12%: 8 pts
- revenue_cagr_3y >= 6%: 3 pts
- revenue_cagr_3y < 6%: 0 pts

**PAT CAGR 3-year (20 pts):**
- pat_cagr_3y >= 25%: 20 pts
- pat_cagr_3y >= 18%: 14 pts
- pat_cagr_3y >= 10%: 8 pts
- pat_cagr_3y >= 5%: 3 pts
- pat_cagr_3y < 5%: 0 pts

**ROE (12 pts):**
- roe >= 25%: 12 pts
- roe >= 18%: 8 pts
- roe >= 12%: 4 pts
- roe < 12%: 0 pts

**ROCE (12 pts):**
- roce >= 25%: 12 pts
- roce >= 18%: 8 pts
- roce >= 12%: 4 pts
- roce < 12%: 0 pts

**Debt / Equity (6 pts):**
- debt_equity <= 0.2: 6 pts
- debt_equity <= 0.5: 4 pts
- debt_equity <= 1.0: 2 pts
- debt_equity > 1.0: 0 pts

**PE Relative to Sector Median (15 pts):**
- pe_relative <= 0.70 (30% discount): 15 pts
- pe_relative <= 0.85 (15% discount): 11 pts
- pe_relative <= 1.00 (at par): 7 pts
- pe_relative <= 1.20 (20% premium): 3 pts
- pe_relative > 1.20: 0 pts

**EMA 200 position (9 pts):**
- close > ema_200 AND pct_from_52w_high >= -20%: 9 pts
- close > ema_200: 5 pts
- close < ema_200: 0 pts

**RS vs Nifty — 60-day (6 pts):**
- rs_vs_nifty_60d >= 1.10: 6 pts
- rs_vs_nifty_60d >= 1.00: 3 pts
- rs_vs_nifty_60d < 1.00: 0 pts

---

# Recommendation Logic

## Swing Recommendation Thresholds

**Eligibility Criteria:**
- is_eligible = TRUE
- swing_score >= 60 (minimum threshold)
- swing_score computed successfully (not NULL)

**Ranking:**
- Rank all eligible symbols by swing_score (descending)
- Select top 20 symbols

**Top-N Limit:** 20 recommendations per day

## Positional Recommendation Thresholds

**Eligibility Criteria:**
- is_eligible = TRUE
- position_score >= 60 (minimum threshold)
- position_score computed successfully (not NULL)

**Ranking:**
- Rank all eligible symbols by position_score (descending)
- Select top 20 symbols

**Top-N Limit:** 20 recommendations per day

## Ranking Logic

**Cross-Sectional Ranking:**
1. Filter to eligible symbols (is_eligible = TRUE)
2. Filter to symbols with valid scores (not NULL)
3. Rank by score in descending order
4. Select top N symbols
5. Assign rank (1 = best, N = worst)

**Score Ties:**
- Not explicitly defined in V1
- Default behavior: undefined (implementation-dependent)

**Rank Persistence:**
- Ranks computed fresh daily
- No carryover from previous day
- No rank decay logic

## Top-N Limits

| Model | Top-N | Minimum Score |
|-------|-------|---------------|
| Swing | 20 | 60 |
| Positional | 20 | 60 |
| Long-Term | 20 | 60 (not implemented) |

**Eligibility Enforcement:**
- If fewer than N symbols meet minimum score threshold, recommend fewer than N
- No minimum recommendation count requirement
- Empty recommendation set is valid if no symbols meet criteria

---

# Backtest Results

## Trade Counts

**Swing Model:**
- 5-day horizon: 2,049 total trades, 2,031 valid (99.1%)
- 10-day horizon: 2,049 total trades, 1,991 valid (97.2%)
- 20-day horizon: 2,049 total trades, 1,916 valid (93.5%)

**Positional Model:**
- 1-month horizon: 6,274 total trades, 5,917 valid (94.3%)
- 3-month horizon: 6,274 total trades, 5,555 valid (88.5%)
- 6-month horizon: 6,274 total trades, 4,452 valid (71.0%)

**Invalid Trades:** Occur when future price data is unavailable (near end of test period)

## Win Rates

**Swing Model:**
- 5-day: 43.2%
- 10-day: 43.7%
- 20-day: 44.7%

**Positional Model:**
- 1-month: 49.7%
- 3-month: 44.6%
- 6-month: 39.5%

**Observation:** Win rates degrade with longer horizons in positional model, suggesting poor medium-term predictive power.

## Average Returns

**Swing Model:**
- 5-day: -0.71%
- 10-day: -0.66%
- 20-day: -0.42%

**Positional Model:**
- 1-month: -0.01% (near breakeven)
- 3-month: -2.07%
- 6-month: -4.81%

**Observation:** All horizons except positional 1-month show negative average returns, meaning models lose money on average.

## Profit Factor

**Swing Model:**
- 5-day: 0.74
- 10-day: 0.80
- 20-day: 0.91

**Positional Model:**
- 1-month: 1.00 (breakeven)
- 3-month: 0.74
- 6-month: 0.57

**Observation:** Profit factors below 1.0 indicate losses exceed gains. Only positional 1-month achieves breakeven (1.00).

## Alpha vs Benchmark

**Swing Model (20-day):**
- Model Return: -0.42%
- Benchmark Return (^CRSLDX): -0.29%
- Alpha: -0.13%
- Verdict: Underperforms

**Positional Model (3-month):**
- Model Return: -2.07%
- Benchmark Return (^CRSLDX): -1.80%
- Alpha: -0.27%
- Verdict: Underperforms

**Benchmark Symbol:** ^CRSLDX (Nifty500 Total Return Index)  
**Benchmark Data:** Complete for test period (2024-07-08 to 2026-06-09)

---

# Factor Research Findings

## ADX

**Classification:** Tier A (Keep / Increase Weight)

**Evidence:**
- Used in both Swing (20 pts) and Positional (15 pts) models
- Trend strength indicator with documented predictive power
- Factor analysis shows positive correlation with forward returns

**Current Usage:**
- Swing: ADX strength + direction (20 pts)
- Positional: ADX medium-term (15 pts)

**Recommendation:** Keep and potentially increase weight in V2 research.

## BB Width

**Classification:** Tier A (Keep / Increase Weight)

**Evidence:**
- Bollinger Band width as volatility squeeze indicator
- Used in Swing model (4 pts for squeeze detection)
- Factor analysis shows positive correlation with forward returns

**Current Usage:**
- Swing: Bollinger squeeze (4 pts)
- Derived from bb_width and bb_width_20avg

**Recommendation:** Keep and potentially increase weight in V2 research.

## Volume Ratio

**Classification:** Tier B (Monitor)

**Evidence:**
- Volume confirmation signal
- Used in Swing (20 pts) and Positional (10 pts) models
- Factor analysis shows moderate predictive power

**Current Usage:**
- Swing: Volume ratio (20 pts)
- Positional: Volume ratio (10 pts)

**Recommendation:** Monitor performance, consider weight adjustment in V2.

## RSI

**Classification:** Tier D (Inverse Relationship)

**Evidence:**
- Momentum oscillator with inverse relationship to returns
- Used in Swing model (15 pts)
- Factor analysis shows negative or weak correlation

**Current Usage:**
- Swing: RSI (15 pts) with sweet spot 55-68

**Recommendation:** Investigate inverse relationship, consider removing or inverting in V2.

## MACD

**Classification:** Tier D (Inverse Relationship)

**Evidence:**
- Trend-following momentum indicator
- Used in Swing model (10 pts for histogram direction)
- Factor analysis shows negative or weak correlation

**Current Usage:**
- Swing: MACD histogram (10 pts)

**Recommendation:** Investigate inverse relationship, consider removing or inverting in V2.

## Stochastic

**Classification:** Tier D (Inverse Relationship)

**Evidence:**
- Momentum oscillator
- Used in Swing model (5 pts)
- Factor analysis shows negative or weak correlation

**Current Usage:**
- Swing: Stochastic (5 pts)

**Recommendation:** Investigate inverse relationship, consider removing or inverting in V2.

## RS Rank

**Classification:** Tier C (Remove / Rework)

**Evidence:**
- Cross-sectional relative strength ranking
- Used in Swing (10 pts), Positional (18 pts), Long-Term (6 pts)
- Factor analysis shows poor predictive power
- **CRITICAL DEFECT:** Implementation computes absolute returns instead of relative strength

**Current Usage:**
- Swing: RS rank percentile (10 pts)
- Positional: RS rank percentile (18 pts)
- Long-Term: RS vs Nifty 60d (6 pts)

**Defects:**
- Formula mismatch: computes absolute returns, not relative to Nifty500
- Missing infrastructure: no Nifty500 benchmark data
- Wrong universe: ranks all symbols, not just NSE500

**Recommendation:** IMMEDIATE REMEDIATION REQUIRED. Disable in all models, implement true relative strength with benchmark data.

## 52W High Distance

**Classification:** Tier C (Remove / Rework)

**Evidence:**
- Proximity to 52-week high as breakout signal
- Used in Swing model (6 pts) and Long-Term model
- Factor analysis shows poor predictive power

**Current Usage:**
- Swing: 52-week high proximity (6 pts)
- Long-Term: EMA 200 position + 52W high proximity (9 pts)

**Recommendation:** Consider removing or reworking in V2 research.

---

# Known Defects

## CONFIRMED DEFECTS

### RS Implementation Defect

**Severity:** CRITICAL

**Description:**
The relative strength features (rs_vs_nifty_20d, rs_vs_nifty_60d, rs_rank_pct) compute absolute returns instead of relative strength against Nifty500 benchmark.

**Evidence:**
- Specification: `stock_return_Nd / nifty500_return_Nd`
- Implementation: `close.pct_change(N)` (absolute return only)
- No Nifty500 data fetched or used in calculation
- Documentation promises unimplemented functionality

**Impact:**
- Features provide no relative strength information
- Models use broken signal (34 total points allocated)
- Factor analysis confirms Tier C (poor predictive performance)
- Actively degrading model performance

**Affected Components:**
- Swing model: 10 points (rs_rank_pct)
- Positional model: 18 points (rs_rank_pct) + 12 points (rs_vs_nifty_60d)
- Long-Term model: 6 points (rs_vs_nifty_60d)

**Remediation Required:**
- Disable rs_rank_pct in all scoring models immediately
- Implement Nifty500 benchmark data infrastructure
- Fix formula to compute true relative strength
- Re-validate after correction

### Ranking Universe Defect

**Severity:** HIGH

**Description:**
Cross-sectional ranking queries all symbols from features_daily table, not just NSE500 as specified.

**Evidence:**
- Specification: "across NSE500 on that date"
- Implementation: No filter by symbol_master.nse500 = True
- No date range validation for nse500_from_date / nse500_to_date
- No filter for is_eligible = True

**Impact:**
- Ranks across entire database, not just NSE500
- May include delisted stocks, non-NSE500 stocks, ineligible stocks
- Percentile values computed on wrong universe
- Violates specification requirements

**Affected Components:**
- rs_rank_pct computation
- All cross-sectional ranking operations

**Remediation Required:**
- Add NSE500 filter to ranking queries
- Add date range validation for NSE500 membership
- Consider adding eligibility filter
- Re-compute historical rankings after fix

### Missing Benchmark Infrastructure

**Severity:** HIGH

**Description:**
No infrastructure exists to store or fetch Nifty500 benchmark data required for relative strength calculation.

**Evidence:**
- No index_prices_daily table in schema
- No index data ingestion pipeline
- No yfinance integration for index data
- No calendar alignment logic for trading days

**Impact:**
- Cannot compute true relative strength
- Cannot implement documented formula
- Feature is fundamentally broken
- Documentation promises unimplemented functionality

**Affected Components:**
- rs_vs_nifty_20d computation
- rs_vs_nifty_60d computation
- All relative strength features

**Remediation Required:**
- Create index_prices_daily table
- Implement index data ingestion pipeline
- Add calendar alignment logic
- Update feature computation to use index returns

## RESEARCH HYPOTHESES

### Inverse Relationship of Momentum Oscillators

**Hypothesis:** RSI, MACD, and Stochastic show inverse relationship to forward returns, suggesting current scoring thresholds may be inverted.

**Evidence:**
- Factor analysis classifies all three as Tier D (inverse relationship)
- Current scoring rewards mid-range values (e.g., RSI 55-68)
- May need to invert scoring rules or remove these signals

**Status:** RESEARCH HYPOTHESIS - Requires validation in V2

### Sector-Relative vs Benchmark-Relative Strength

**Hypothesis:** Sector-relative strength (stock_return / sector_return) may provide better predictive power than benchmark-relative strength (stock_return / index_return).

**Evidence:**
- Sector data infrastructure exists (sector_daily table)
- Sector-relative strength not implemented in V1
- Benchmark-relative strength broken due to missing infrastructure

**Status:** RESEARCH HYPOTHESIS - Requires implementation and comparison in V2

### Score Bucket Analysis Data Processing Error

**Hypothesis:** Score bucket analysis shows identical results across multiple buckets, suggesting a data processing error in the backtest script.

**Evidence:**
- Swing bucket analysis: All buckets (70-74, 75-79, 80-84) show identical results
- Positional bucket analysis: Multiple buckets show identical results
- Suggests script may be reusing same backtest results instead of running separate backtests per bucket

**Status:** RESEARCH HYPOTHESIS - Requires investigation in V2

---

# Known Limitations

## No Transaction Costs

**Description:** Backtest does not account for slippage, brokerage, STT, or stamp duty.

**Impact:** Real-world performance would be worse than reported.

**Estimated Impact:** Per BACKTEST_SPEC.md, total round-trip costs are approximately 0.50%. This would further reduce already-negative returns.

**Status:** Known limitation, not addressed in V1

## Close-to-Close Assumption

**Description:** Backtest uses close price on signal date as entry price.

**Specification:** BACKTEST_SPEC.md specifies next-day-open execution to avoid look-ahead bias.

**Impact:** Current implementation may overstate performance by using close prices instead of next-day-open.

**Status:** Known limitation, not addressed in V1

## Limited Exit Logic

**Description:** Backtest measures fixed-horizon returns only (5d, 10d, 20d, 1M, 3M, 6M).

**Reality:** Production system would use stop-loss, rank-decay, and target-based exits.

**Impact:** Fixed-horizon returns may not reflect actual trading system performance.

**Status:** Known limitation, not addressed in V1

## Survivorship Bias

**Description:** NSE500 composition changes over time. Stocks that were delisted or downgraded are not represented in historical backtests.

**Impact:** Performance may appear better than reality since failed stocks are excluded.

**Mitigation:** Future versions should use universe_snapshot table to ensure survivorship-bias-free backtesting.

**Status:** Known limitation, not addressed in V1

## No Risk-Adjusted Metrics

**Description:** Backtest does not calculate Sharpe ratio, Sortino ratio, Calmar ratio as specified in BACKTEST_SPEC.md.

**Impact:** Cannot assess risk-adjusted performance.

**Status:** Known limitation, not addressed in V1

## No Drawdown Analysis

**Description:** Backtest does not calculate max drawdown duration or drawdown distribution.

**Impact:** Cannot assess downside risk characteristics.

**Status:** Known limitation, not addressed in V1

## Market Regime

**Description:** Test period (2024-2026) may not represent different market regimes (bull, bear, sideways).

**Impact:** Performance may vary significantly across different market conditions.

**Status:** Known limitation, not addressed in V1

---

# V1 Conclusions

## What Worked

1. **Infrastructure:** Complete data pipeline from ingestion to backtesting
2. **Feature Computation:** 30+ technical indicators computed reliably daily
3. **Sector Rotation:** Daily sector strength computation and ranking functional
4. **Cross-Sectional Ranking:** Proper implementation of percentile-based ranking methodology
5. **Database Design:** Normalized schema with proper constraints and relationships
6. **Test Coverage:** Unit tests for core functionality provide regression protection
7. **Documentation:** Extensive specification documents provide clear requirements
8. **Architecture:** Clean separation of concerns enables modular development

## What Failed

1. **Predictive Performance:** Models underperform Nifty500 benchmark by 0.13-0.27% per period
2. **Relative Strength:** RS features fundamentally broken (absolute returns instead of relative strength)
3. **Score Differentiation:** Higher scores do not correlate with better performance
4. **Win Rates:** Most horizons show sub-50% win rates
5. **Factor Selection:** Multiple momentum oscillators (RSI, MACD, Stochastic) show inverse relationships
6. **Benchmark Infrastructure:** No Nifty500 data storage or ingestion
7. **Transaction Costs:** Backtest ignores real-world trading costs
8. **Exit Logic:** Fixed-horizon returns only, no dynamic exit strategies

## What Remains Unknown

1. **True Relative Strength:** Predictive power of correctly implemented relative strength unknown
2. **Sector-Relative Strength:** Whether sector-relative strength outperforms benchmark-relative
3. **Market Regime Dependence:** How models perform across bull, bear, and sideways markets
4. **Fundamental Factors:** Long-Term model not implemented, fundamental factor predictive power unknown
5. **Machine Learning:** Whether ML-based feature selection would improve performance
6. **Alternative Indicators:** Whether other technical indicators would provide better signals
7. **Optimal Weights:** Whether current scoring weights are optimal or need rebalancing
8. **Dynamic Exits:** Impact of stop-loss, rank-decay, and target-based exits on performance

---

# Change Control

## V1 Freeze Status

**EFFECTIVE DATE:** 2026-06-11

**STATUS:** FROZEN

V1 is now frozen and serves as the baseline for all future V2 research and implementation. No modifications to V1 code, schema, scoring rules, or configurations are permitted.

## V2 Development

All future changes belong to V2 and must:

1. **Compare Against Baseline:** All V2 results must be compared against this V1 baseline document
2. **Document Improvements:** Clearly document how V2 improves upon V1
3. **Maintain Compatibility:** V2 may break V1 compatibility but must provide migration path
4. **Version Tracking:** Use model_version_id to track scoring model versions
5. **Backtest Comparison:** Run identical backtests on V1 and V2 for direct comparison

## Baseline Comparison Metrics

When evaluating V2 changes, compare against V1 baseline on:

**Performance Metrics:**
- Win rate (5d, 10d, 20d, 1M, 3M, 6M)
- Average return (5d, 10d, 20d, 1M, 3M, 6M)
- Profit factor (5d, 10d, 20d, 1M, 3M, 6M)
- Alpha vs benchmark (20d, 3M)
- Score differentiation (correlation between score and return)

**Infrastructure Metrics:**
- Data completeness
- Feature computation accuracy
- Scoring engine correctness
- Backtest realism (transaction costs, exit logic)

**Defect Resolution:**
- RS implementation defect resolved
- Ranking universe defect resolved
- Benchmark infrastructure implemented
- Transaction costs implemented
- Exit logic implemented

## Success Criteria for V2

V2 is considered successful if it achieves:

1. **Positive Alpha:** Outperforms Nifty500 benchmark on primary horizons
2. **Win Rate > 50%:** Consistently picks winners more often than losers
3. **Score Differentiation:** Higher scores correlate with better performance
4. **Defect Resolution:** All V1 confirmed defects resolved
5. **Realistic Backtesting:** Transaction costs and exit logic implemented
6. **Risk-Adjusted Returns:** Positive Sharpe ratio and acceptable drawdowns

## Version Control

**V1 Branch:** main (frozen at commit 2026-06-11)  
**V2 Branch:** development (active development)  
**Baseline Reference:** This document (docs/V1_BASELINE.md)

**Migration Path:** V2 to provide migration scripts for database schema changes and data transformations.

---

**Document Version:** 1.0  
**Last Updated:** 2026-06-11  
**Next Review:** Upon V2 completion
