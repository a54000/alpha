# Market Regime Analysis

Date: 2026-06-12

## Objective

Determine how Swing V2.1 behaves across different market environments and whether performance is regime-dependent.

Model:

```text
swing_v2_1
```

Portfolio structures:

- Top 5 Weekly
- Top 10 Weekly
- Top 10 Weekly + Max 2 Positions Per Sector

Output:

- `reports/market_regime_analysis.json`

## Methodology

Regime assignment:

- Trade-level metrics use the trade entry date.
- Portfolio-level trend metrics use daily portfolio returns grouped by that day's trend regime.
- Alpha is average trade return minus matched NIFTY500 return from entry open to exit close.

Trend regimes:

- Bull Trend: NIFTY500 close > 200 DMA and 60-day index return > 0
- Bear Trend: NIFTY500 close < 200 DMA and 60-day index return < 0
- Neutral: all remaining dates

Breadth regimes:

- Strong Breadth: more than 70% of universe stocks above EMA200
- Neutral Breadth: 30% to 70%
- Weak Breadth: less than 30%

Volatility regimes:

- Low Volatility: bottom 25% of NIFTY500 20-day realized volatility
- Normal Volatility: middle 50%
- High Volatility: top 25%

Regime date counts:

| Regime Type | Bucket | Days |
| --- | --- | ---: |
| Trend | Bull Trend | 141 |
| Trend | Bear Trend | 68 |
| Trend | Neutral | 261 |
| Breadth | Strong Breadth | 13 |
| Breadth | Neutral Breadth | 356 |
| Breadth | Weak Breadth | 107 |
| Volatility | Low Volatility | 113 |
| Volatility | Normal Volatility | 244 |
| Volatility | High Volatility | 113 |

Early dates without enough 200-DMA warmup are classified as neutral.

## Part A - Trend Regime

### Trade-Level Results

| Portfolio | Regime | Trades | Avg Return | Win Rate | Profit Factor | Alpha | Total PnL |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Top 5 Weekly | Bear | 10 | 7.87% | 100.00% | Inf | 3.93% | 166,970 |
| Top 5 Weekly | Bull | 30 | 1.09% | 50.00% | 1.396 | 0.75% | 65,549 |
| Top 5 Weekly | Neutral | 65 | -0.24% | 43.08% | 0.926 | 0.25% | -43,374 |
| Top 10 Weekly | Bear | 27 | 6.29% | 77.78% | 7.456 | 4.25% | 170,751 |
| Top 10 Weekly | Bull | 65 | -0.07% | 40.00% | 0.977 | -0.07% | -5,301 |
| Top 10 Weekly | Neutral | 118 | -0.05% | 45.76% | 0.985 | 0.62% | -17,207 |
| Top 10 + Max 2 Sector | Bear | 27 | 6.22% | 77.78% | 5.927 | 4.18% | 177,291 |
| Top 10 + Max 2 Sector | Bull | 65 | 0.10% | 40.00% | 1.031 | 0.10% | 1,723 |
| Top 10 + Max 2 Sector | Neutral | 118 | 0.26% | 44.92% | 1.071 | 0.72% | 8,559 |

### Portfolio-Level Trend Results

| Portfolio | Regime | Days | Total Return | CAGR | Sharpe |
| --- | --- | ---: | ---: | ---: | ---: |
| Top 5 Weekly | Bear | 68 | 3.83% | 14.94% | 0.729 |
| Top 5 Weekly | Bull | 141 | 15.83% | 30.03% | 1.915 |
| Top 5 Weekly | Neutral | 266 | -0.77% | -0.73% | 0.061 |
| Top 10 Weekly | Bear | 68 | -0.57% | -2.09% | 0.016 |
| Top 10 Weekly | Bull | 141 | 10.72% | 19.96% | 1.578 |
| Top 10 Weekly | Neutral | 266 | 4.70% | 4.45% | 0.329 |
| Top 10 + Max 2 Sector | Bear | 68 | -4.44% | -15.49% | -0.595 |
| Top 10 + Max 2 Sector | Bull | 141 | 11.36% | 21.20% | 1.554 |
| Top 10 + Max 2 Sector | Neutral | 266 | 12.03% | 11.36% | 0.672 |

Interpretation:

Trade-level profits are strongest in bear-trend entries, but portfolio-level returns are strongest during bull-trend days. This is not contradictory: trades entered during bear-trend regimes can exit into rebounds, while daily portfolio returns are earned across later days.

Neutral regimes are the main weakness, especially for Top 5 Weekly.

## Part B - Market Breadth Regime

| Portfolio | Breadth Regime | Trades | Avg Return | Win Rate | Profit Factor | Alpha | Total PnL |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Top 5 Weekly | Strong | 5 | -0.93% | 40.00% | 0.755 | 0.88% | -9,319 |
| Top 5 Weekly | Neutral | 75 | 0.67% | 46.67% | 1.238 | 1.43% | 103,423 |
| Top 5 Weekly | Weak | 25 | 2.02% | 64.00% | 1.832 | -1.33% | 95,042 |
| Top 10 Weekly | Strong | 10 | -0.60% | 50.00% | 0.843 | 1.21% | -6,014 |
| Top 10 Weekly | Neutral | 148 | -0.09% | 42.57% | 0.972 | 0.88% | -14,585 |
| Top 10 Weekly | Weak | 52 | 3.43% | 63.46% | 2.650 | 0.76% | 168,842 |
| Top 10 + Max 2 Sector | Strong | 10 | -0.60% | 50.00% | 0.843 | 1.21% | -6,014 |
| Top 10 + Max 2 Sector | Neutral | 148 | -0.45% | 40.54% | 0.878 | 0.52% | -77,290 |
| Top 10 + Max 2 Sector | Weak | 52 | 5.34% | 67.31% | 4.285 | 2.17% | 270,877 |

Interpretation:

Swing V2.1 does not require strong breadth. In this sample, strong breadth has very few observations and produced negative average returns. Weak breadth produced the strongest trade results, especially for Top 10 + Max 2 Sector.

This suggests the model may be capturing leadership rotation or rebound behavior when broad participation is weak, rather than simply benefiting from broad market strength.

## Part C - Volatility Regime

| Portfolio | Volatility Regime | Trades | Avg Return | Win Rate | Profit Factor | Alpha | Total PnL |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Top 5 Weekly | Low | 30 | 1.96% | 50.00% | 2.171 | 1.15% | 116,831 |
| Top 5 Weekly | Normal | 45 | -0.40% | 42.22% | 0.888 | 1.20% | -51,628 |
| Top 5 Weekly | High | 30 | 1.84% | 63.33% | 1.712 | -0.34% | 123,942 |
| Top 10 Weekly | Low | 57 | 0.64% | 43.86% | 1.235 | 0.57% | 33,960 |
| Top 10 Weekly | Normal | 100 | -0.47% | 44.00% | 0.863 | 0.79% | -60,258 |
| Top 10 Weekly | High | 53 | 3.20% | 60.38% | 2.302 | 1.35% | 174,541 |
| Top 10 + Max 2 Sector | Low | 57 | 0.68% | 43.86% | 1.264 | 0.61% | 36,716 |
| Top 10 + Max 2 Sector | Normal | 97 | -1.13% | 39.18% | 0.734 | 0.24% | -134,955 |
| Top 10 + Max 2 Sector | High | 56 | 4.92% | 66.07% | 3.464 | 2.59% | 285,812 |

Interpretation:

Normal volatility is the main destroyer. High volatility is strongest for the Top 10 structures, especially Top 10 + Max 2 Sector. Top 5 performs well in both low and high volatility but loses in normal volatility.

## Final Analysis

### 1. Which regime generates most profits?

At trade level:

- Trend: Bear-trend entries generated the strongest average returns and PnL.
- Breadth: Weak breadth generated the strongest performance.
- Volatility: High volatility generated the strongest performance for Top 10 and Top 10 + Max 2 Sector.

For portfolio-level daily returns, bull-trend days produced the strongest CAGR for all three structures.

### 2. Which regime destroys performance?

The main destructive regimes are:

- Neutral trend for Top 5 Weekly.
- Neutral breadth for Top 10 + Max 2 Sector.
- Normal volatility for all three structures.

Strong breadth also performed poorly, but only 13 days were classified as strong breadth, so that result is less reliable.

### 3. Does Swing V2.1 require a trending market?

Partly, but not in the obvious way.

Portfolio-level returns are strongest during bull-trend days, so favorable trend helps. However, trade entries during bear-trend regimes produced strong average returns, likely because trades caught rebounds. The model does not simply require a bull market at entry.

### 4. Does Swing V2.1 require strong breadth?

No.

The strongest trade results came during weak breadth, not strong breadth. This is a strong warning against assuming a broad-participation filter would automatically improve performance.

### 5. Does volatility materially affect results?

Yes.

Volatility regime materially changes results. High volatility was highly favorable for Top 10 structures, while normal volatility was weak or negative. Top 5 was more balanced but still lost in normal volatility.

### 6. Is there evidence supporting a future market-regime filter?

Yes, but only for further research.

Evidence supports investigating:

- avoiding or reducing exposure during normal-volatility regimes
- distinguishing bear-trend rebound setups from true downtrend continuation
- using weak-breadth leadership/rebound conditions rather than simple strong-breadth filters

This evidence is not sufficient to implement a filter yet.

### 7. Would a simple "Nifty500 above 200 DMA" filter likely improve robustness?

Not clearly.

A simple above-200-DMA filter might improve portfolio-level trend exposure, because bull-trend days had strong daily returns. But it would likely remove many profitable bear-trend entry trades. The trade-level evidence does not support a naive "only trade when Nifty500 is above 200 DMA" rule.

## Verdict

Swing V2.1 is regime-dependent.

Current finding:

```text
The model benefits from bull-trend portfolio days, but the strongest trade entries
often occur during weak breadth, high volatility, or bear-trend rebound regimes.
```

Do not implement a market filter yet.

Most promising future research:

1. Rebound-versus-breakdown classification inside bear-trend regimes.
2. Weak-breadth leadership filters.
3. High-volatility continuation versus reversal analysis.
4. Normal-volatility avoidance tests.
5. Portfolio-level trend exposure controls rather than simple entry exclusion.

## Caveats

This is research only.

Known limitations:

- Historical period is short.
- Early dates are neutral because 200-DMA warmup is unavailable.
- Breadth uses current available universe data and inherits survivorship-bias risk.
- Alpha is trade-level matched NIFTY500 alpha, not a full benchmark portfolio simulation.
- Regime classification is measured, not implemented.
- No market filter was created.
- No scoring or recommendation logic was modified.

