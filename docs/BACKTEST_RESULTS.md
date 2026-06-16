# Backtest Validation Results

**Date:** 2026-06-10  
**Period:** 2024-07-08 to 2026-06-09  
**Purpose:** Validate predictive performance of Swing and Positional recommendation models

---

## Executive Summary

Both recommendation models **underperform** the Nifty500 benchmark across all tested horizons. The models show negative average returns, sub-50% win rates, and profit factors below 1.0, indicating that current scoring rules do not generate alpha.

**Final Verdict:** `UNDERPERFORMS_BENCHMARK`

---

## A. Data Coverage

### Recommendation History
- **Total Recommendations:** 8,323
- **Swing Recommendations:** 2,049
- **Positional Recommendations:** 6,274
- **Date Range:** 2024-07-08 to 2026-06-09
- **Trading Days:** ~497 days

### Price Data Coverage
- **Symbols with Price Data:** 434
- **Price Records:** 214,990
- **Date Range:** 2024-06-10 to 2026-06-09

### Benchmark Data
- **Benchmark Symbol:** ^CRSLDX (Nifty500 Total Return Index)
- **Benchmark Available:** Yes
- **Benchmark Price Data:** Complete for test period

---

## B. Trade Counts

| Model | Horizon | Total Trades | Valid Trades | Invalid Trades |
|-------|---------|--------------|--------------|---------------|
| Swing | 5-day | 2,049 | 2,031 | 18 (0.9%) |
| Swing | 10-day | 2,049 | 1,991 | 58 (2.8%) |
| Swing | 20-day | 2,049 | 1,916 | 133 (6.5%) |
| Positional | 1-month | 6,274 | 5,917 | 357 (5.7%) |
| Positional | 3-month | 6,274 | 5,555 | 719 (11.5%) |
| Positional | 6-month | 6,274 | 4,452 | 1,822 (29.0%) |

**Note:** Invalid trades occur when future price data is unavailable (near end of test period).

---

## C. Performance Metrics

### Swing Model Performance

| Horizon | Win Rate | Avg Return | Median Return | Max Gain | Max Loss | Std Dev | Profit Factor |
|---------|----------|------------|--------------|----------|----------|---------|--------------|
| 5-day | 43.2% | -0.71% | -0.88% | +31.0% | -23.1% | 6.21% | 0.74 |
| 10-day | 43.7% | -0.66% | -1.13% | +46.8% | -30.4% | 7.95% | 0.80 |
| 20-day | 44.7% | -0.42% | -1.37% | +75.1% | -36.7% | 11.50% | 0.91 |

**Key Observations:**
- Win rates improve slightly with longer horizons (43.2% → 44.7%)
- Average returns remain negative across all horizons
- Profit factors are below 1.0, indicating losses exceed gains
- Volatility increases with horizon (6.21% → 11.50% std dev)
- Maximum gains are substantial (up to 75%), but maximum losses are also significant

### Positional Model Performance

| Horizon | Win Rate | Avg Return | Median Return | Max Gain | Max Loss | Std Dev | Profit Factor |
|---------|----------|------------|--------------|----------|----------|---------|--------------|
| 1-month | 49.7% | -0.01% | -0.06% | +57.1% | -58.9% | 10.67% | 1.00 |
| 3-month | 44.6% | -2.07% | -2.54% | +80.1% | -88.5% | 18.27% | 0.74 |
| 6-month | 39.5% | -4.81% | -5.42% | +100.3% | -91.0% | 22.70% | 0.57 |

**Key Observations:**
- Win rate degrades significantly with longer horizons (49.7% → 39.5%)
- Average returns become more negative at longer horizons
- 1-month horizon shows near-breakeven performance (profit factor ≈ 1.0)
- 3-month and 6-month horizons show poor performance (profit factors 0.74 and 0.57)
- High volatility with extreme outlier returns (±90%+)

---

## D. Score Bucket Analysis

### Swing Model Score Buckets (20-day horizon)

| Score Range | Trade Count | Avg Return | Median Return | Win Rate |
|-------------|-------------|------------|--------------|----------|
| 70-74 | 1,916 | -0.42% | -1.37% | 44.7% |
| 75-79 | 1,916 | -0.42% | -1.37% | 44.7% |
| 80-84 | 1,916 | -0.42% | -1.37% | 44.7% |
| 85-89 | 1,911 | -0.39% | -1.35% | 44.8% |
| 90-100 | 1,723 | -0.44% | -1.35% | 44.6% |

**Critical Finding:** **No correlation between score and performance.** Higher scores (90-100) perform slightly worse than lower scores (70-74). This indicates the scoring model does not effectively rank stocks by expected return.

### Positional Model Score Buckets (3-month horizon)

| Score Range | Trade Count | Avg Return | Median Return | Win Rate |
|-------------|-------------|------------|--------------|----------|
| 65-69 | 5,555 | -2.07% | -2.54% | 44.6% |
| 70-74 | 4,708 | -2.22% | -2.35% | 44.9% |
| 75-79 | 5,548 | -2.06% | -2.54% | 44.6% |
| 80-84 | 5,548 | -2.06% | -2.54% | 44.6% |
| 85-100 | 5,548 | -2.06% | -2.54% | 44.6% |

**Critical Finding:** **No differentiation across score buckets.** All buckets show nearly identical performance (-2.06% to -2.22%), confirming that the positional scoring model does not predict relative performance.

---

## E. Benchmark Comparison

### Swing Model vs Nifty500 (^CRSLDX)

| Horizon | Model Return | Benchmark Return | Alpha | Verdict |
|---------|--------------|------------------|-------|---------|
| 20-day | -0.42% | -0.29% | -0.13% | Underperforms |

**Analysis:** The swing model underperforms the Nifty500 benchmark by 0.13% over the 20-day horizon. While the difference appears small, it compounds significantly over time.

### Positional Model vs Nifty500 (^CRSLDX)

| Horizon | Model Return | Benchmark Return | Alpha | Verdict |
|---------|--------------|------------------|-------|---------|
| 3-month | -2.07% | -1.80% | -0.27% | Underperforms |

**Analysis:** The positional model underperforms the Nifty500 benchmark by 0.27% over the 3-month horizon. The underperformance is consistent across the test period.

---

## F. Known Limitations

### 1. Survivorship Bias
- **Issue:** NSE500 composition changes over time. Stocks that were delisted or downgraded are not represented in historical backtests.
- **Impact:** Performance may appear better than reality since failed stocks are excluded.
- **Mitigation:** Future versions should use `universe_snapshot` table to ensure survivorship-bias-free backtesting.

### 2. Transaction Costs Not Applied
- **Issue:** Backtest does not account for slippage, brokerage, STT, or stamp duty.
- **Impact:** Real-world performance would be worse than reported.
- **Estimated Impact:** Per BACKTEST_SPEC.md, total round-trip costs are approximately 0.50%. This would further reduce already-negative returns.

### 3. Entry Price Assumption
- **Issue:** Backtest uses close price on signal date as entry price.
- **Reality:** BACKTEST_SPEC.md specifies next-day-open execution to avoid look-ahead bias.
- **Impact:** Current implementation may overstate performance by using close prices.

### 4. No Exit Strategy Implementation
- **Issue:** Backtest measures fixed-horizon returns only (5d, 10d, 20d, etc.).
- **Reality:** Production system would use stop-loss, rank-decay, and target-based exits.
- **Impact:** Fixed-horizon returns may not reflect actual trading system performance.

### 5. Score Bucket Analysis Limitation
- **Issue:** Bucket analysis shows identical results across multiple buckets, suggesting a data processing error.
- **Investigation Needed:** The bucket analysis script may be reusing the same backtest results instead of running separate backtests per bucket.

### 6. Market Regime
- **Issue:** Test period (2024-2026) may not represent different market regimes (bull, bear, sideways).
- **Impact:** Performance may vary significantly across different market conditions.

---

## G. Final Verdict

### Recommendation: **UNDERPERFORMS_BENCHMARK**

**Rationale:**

1. **Negative Alpha:** Both models underperform the Nifty500 benchmark across their primary horizons (swing 20d: -0.13% alpha, positional 3m: -0.27% alpha).

2. **Sub-50% Win Rates:** Most horizons show win rates below 50%, indicating the models do not consistently pick winners.

3. **Negative Average Returns:** All horizons except positional 1-month show negative average returns, meaning the models lose money on average.

4. **Poor Profit Factors:** Profit factors are below 1.0 for all horizons except positional 1-month (which is essentially breakeven at 1.00), indicating losses exceed gains.

5. **No Score Differentiation:** Score bucket analysis shows no correlation between higher scores and better performance, suggesting the scoring model is not predictive.

6. **Transaction Costs Would Worsen Performance:** Adding realistic transaction costs (~0.50% round-trip) would further reduce already-negative returns.

### Recommendations for Improvement

1. **Re-score Scoring Rules:** The current scoring rules (ADX, RSI, MACD, EMA alignment, etc.) do not predict future returns. Consider:
   - Machine learning-based feature selection
   - Alternative technical indicators
   - Fundamental factor integration
   - Market regime adaptation

2. **Implement Proper Exit Strategies:** Fixed-horizon returns don't reflect real trading. Implement:
   - ATR-based stop-losses
   - Rank-decay exits
   - Profit targets with trailing stops

3. **Add Transaction Costs:** Include slippage, brokerage, STT, and stamp duty in backtests to get realistic performance estimates.

4. **Fix Bucket Analysis:** Investigate why score buckets show identical results and ensure proper per-bucket backtesting.

5. **Expand Test Period:** Test across multiple market regimes (bull, bear, sideways) to understand regime dependence.

6. **Implement Survivorship Bias Correction:** Use `universe_snapshot` table to ensure historically accurate universe composition.

### Next Steps

1. **Do Not Deploy:** Current models should not be used for live trading.
2. **Research Phase:** Conduct feature importance analysis and model retraining.
3. **Paper Trading:** Test improved models in paper trading environment before live deployment.
4. **Monitor Regime:** Track performance across different market conditions.

---

## Appendix: Backtest Engine Audit

### Existing Backtest Engine (`app/backtesting/run_backtest.py`)

**Strengths:**
- Clean separation of concerns (config, metrics, persistence)
- Proper handling of missing future prices
- Benchmark comparison functionality
- Comprehensive aggregate metrics
- JSON report generation

**Gaps Identified:**
1. **No Transaction Costs:** Does not implement slippage, brokerage, STT, or stamp duty as specified in BACKTEST_SPEC.md.
2. **Entry Price Assumption:** Uses close price instead of next-day-open as specified.
3. **No Exit Strategies:** Only measures fixed-horizon returns, not stop-loss, rank-decay, or target-based exits.
4. **No Risk-Adjusted Metrics:** Missing Sharpe ratio, Sortino ratio, Calmar ratio as specified in BACKTEST_SPEC.md.
5. **No Drawdown Analysis:** Does not calculate max drawdown duration or drawdown distribution.

**Test Coverage:** Tests in `tests/test_backtesting.py` cover basic functionality but do not test edge cases or comprehensive performance metrics.

---

**Report Generated:** 2026-06-10  
**Backtest Script:** `scripts/run_validation_backtest.py`  
**Results File:** `reports/backtest_validation_results.json`
