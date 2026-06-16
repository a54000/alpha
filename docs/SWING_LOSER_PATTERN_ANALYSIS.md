# Swing Loser Pattern Analysis

**Date:** 2026-06-11

**Objective:** Understand why the strongest Swing research model, Sector Rank + ADX, still produces large losing trades.

**Scope:** Research only. Production scoring was not modified. No V2.1 model was created.

## Source Ledgers

- `reports/swing_top10_trade_ledger.csv`
- `reports/swing_top20_trade_ledger.csv`
- Supporting analysis: `reports/swing_loser_pattern_analysis.json`

## Method

For each ledger row, I enriched the trade with signal-date context from `features_daily` and `prices_daily`:

- close vs EMA50
- close vs EMA200
- distance from EMA50 and EMA200
- ADX value
- sector rank
- sector
- prior 20-day return
- prior 60-day return
- trend state at entry

Market regime is defined from benchmark prior 20-day return on the signal date:

| Regime | Definition |
|---|---|
| Bullish | benchmark prior 20d return >= +3% |
| Bearish | benchmark prior 20d return <= -3% |
| Sideways | between -3% and +3% |

I then analyzed:

- worst 100 trades by holding-period return
- worst 100 trades by alpha

Finally, I simulated the requested trend filters directly on the existing trade ledger.


## Top 10 Portfolio

### Overall Ledger

| Metric | Value |
|---|---:|
| Trades | 4726 |
| Valid trades | 4516 |
| Avg return | 0.21% |
| Win rate | 50.47% |
| Profit factor | 1.058 |
| Alpha | 0.29% |

### Worst 100 By Return

| Metric | Value |
|---|---:|
| Count | 100 |
| Below EMA50 | 16.00% |
| Below EMA200 | 18.00% |
| ADX > 30 | 100.00% |
| Close > EMA50 | 84.00% |
| Close > EMA200 | 82.00% |
| EMA50 > EMA200 | 86.00% |
| Avg distance from EMA50 | 12.80% |
| Avg distance from EMA200 | 24.93% |
| Avg prior 20d return | 16.55% |
| Avg prior 60d return | 30.98% |

Sector breakdown:

| Sector | Count |
|---|---:|
| IT | 27 |
| CONSUMER GOODS | 14 |
| FINANCIAL SERVICES | 12 |
| PHARMA | 8 |
| AUTOMOBILE | 6 |
| FERTILISERS & PESTICIDES | 6 |
| INDUSTRIAL MANUFACTURING | 6 |
| TELECOM | 5 |
| TEXTILES | 5 |
| METALS | 4 |
| ENERGY | 2 |
| CEMENT & CEMENT PRODUCTS | 2 |

Market-regime breakdown:

| Regime | Count |
|---|---:|
| Sideways | 66 |
| Bearish | 16 |
| Bullish | 15 |
| Unknown | 3 |

### Worst 100 By Alpha

| Metric | Value |
|---|---:|
| Count | 100 |
| Below EMA50 | 18.00% |
| Below EMA200 | 20.00% |
| ADX > 30 | 99.00% |
| Close > EMA50 | 82.00% |
| Close > EMA200 | 80.00% |
| EMA50 > EMA200 | 78.00% |
| Avg distance from EMA50 | 12.41% |
| Avg distance from EMA200 | 22.20% |
| Avg prior 20d return | 15.43% |
| Avg prior 60d return | 33.76% |

Sector breakdown:

| Sector | Count |
|---|---:|
| IT | 19 |
| INDUSTRIAL MANUFACTURING | 16 |
| CONSUMER GOODS | 14 |
| FINANCIAL SERVICES | 13 |
| METALS | 11 |
| PHARMA | 5 |
| TELECOM | 4 |
| TEXTILES | 4 |
| AUTOMOBILE | 3 |
| CEMENT & CEMENT PRODUCTS | 3 |
| FERTILISERS & PESTICIDES | 3 |
| HEALTHCARE SERVICES | 2 |

Market-regime breakdown:

| Regime | Count |
|---|---:|
| Sideways | 58 |
| Bearish | 20 |
| Bullish | 19 |
| Unknown | 3 |

### Trend Filter Simulation

| Filter | Trades | Avg Return | Win Rate | Profit Factor | Alpha |
|---|---:|---:|---:|---:|---:|
| Current | 4726 | 0.21% | 50.47% | 1.058 | 0.29% |
| Filter A: Close > EMA50 | 3237 | -0.70% | 46.66% | 0.830 | -0.13% |
| Filter B: Close > EMA200 | 3243 | -0.56% | 47.43% | 0.862 | -0.02% |
| Filter C: Close > EMA50 and EMA200 | 3145 | -0.67% | 46.94% | 0.837 | -0.07% |
| Filter D: Close > EMA50 and EMA50 > EMA200 | 2639 | -0.78% | 46.92% | 0.816 | -0.05% |
| Filter E: Filter D + ADX > 25 | 2639 | -0.78% | 46.92% | 0.816 | -0.05% |


## Top 20 Portfolio

### Overall Ledger

| Metric | Value |
|---|---:|
| Trades | 9016 |
| Valid trades | 8613 |
| Avg return | 0.22% |
| Win rate | 49.51% |
| Profit factor | 1.059 |
| Alpha | 0.38% |

### Worst 100 By Return

| Metric | Value |
|---|---:|
| Count | 100 |
| Below EMA50 | 36.00% |
| Below EMA200 | 36.00% |
| ADX > 30 | 100.00% |
| Close > EMA50 | 64.00% |
| Close > EMA200 | 64.00% |
| EMA50 > EMA200 | 66.00% |
| Avg distance from EMA50 | 3.27% |
| Avg distance from EMA200 | 8.19% |
| Avg prior 20d return | 5.01% |
| Avg prior 60d return | 10.90% |

Sector breakdown:

| Sector | Count |
|---|---:|
| IT | 19 |
| FINANCIAL SERVICES | 16 |
| ENERGY | 15 |
| INDUSTRIAL MANUFACTURING | 12 |
| CONSUMER GOODS | 10 |
| CONSTRUCTION | 6 |
| TELECOM | 5 |
| METALS | 3 |
| AUTOMOBILE | 3 |
| PHARMA | 3 |
| CEMENT & CEMENT PRODUCTS | 3 |
| CHEMICALS | 2 |

Market-regime breakdown:

| Regime | Count |
|---|---:|
| Sideways | 60 |
| Bearish | 25 |
| Bullish | 11 |
| Unknown | 4 |

### Worst 100 By Alpha

| Metric | Value |
|---|---:|
| Count | 100 |
| Below EMA50 | 38.00% |
| Below EMA200 | 40.00% |
| ADX > 30 | 99.00% |
| Close > EMA50 | 62.00% |
| Close > EMA200 | 60.00% |
| EMA50 > EMA200 | 65.00% |
| Avg distance from EMA50 | 4.99% |
| Avg distance from EMA200 | 10.06% |
| Avg prior 20d return | 6.34% |
| Avg prior 60d return | 14.76% |

Sector breakdown:

| Sector | Count |
|---|---:|
| FINANCIAL SERVICES | 20 |
| IT | 18 |
| ENERGY | 15 |
| INDUSTRIAL MANUFACTURING | 10 |
| CONSUMER GOODS | 10 |
| TELECOM | 4 |
| METALS | 4 |
| PHARMA | 4 |
| FERTILISERS & PESTICIDES | 4 |
| CONSTRUCTION | 3 |
| TEXTILES | 2 |
| AUTOMOBILE | 2 |

Market-regime breakdown:

| Regime | Count |
|---|---:|
| Sideways | 48 |
| Bearish | 36 |
| Bullish | 13 |
| Unknown | 3 |

### Trend Filter Simulation

| Filter | Trades | Avg Return | Win Rate | Profit Factor | Alpha |
|---|---:|---:|---:|---:|---:|
| Current | 9016 | 0.22% | 49.51% | 1.059 | 0.38% |
| Filter A: Close > EMA50 | 5701 | -0.35% | 47.07% | 0.914 | 0.28% |
| Filter B: Close > EMA200 | 5660 | -0.30% | 47.22% | 0.928 | 0.30% |
| Filter C: Close > EMA50 and EMA200 | 5470 | -0.36% | 46.96% | 0.913 | 0.30% |
| Filter D: Close > EMA50 and EMA50 > EMA200 | 4528 | -0.46% | 47.38% | 0.892 | 0.33% |
| Filter E: Filter D + ADX > 25 | 4528 | -0.46% | 47.38% | 0.892 | 0.33% |

## Research Questions

### 1. Did ADX Identify Strong Downtrends Rather Than Strong Uptrends?

Not primarily.

In the worst 100 trades by return:

- Top 10: `84%` were above EMA50 and `82%` were above EMA200.
- Top 20: `64%` were above EMA50 and `64%` were above EMA200.
- `100%` of the worst-return trades had ADX > 30 in both ledgers.

ADX did identify strong trends, but many losing trades were still in apparent uptrends by simple EMA tests. The issue is not simply that ADX was selecting obvious downtrends.

### 2. Were Losers Predominantly Below EMA50?

No.

Worst 100 by return:

- Top 10 below EMA50: `16%`
- Top 20 below EMA50: `36%`

Most large losers were not below EMA50 at signal date.

### 3. Were Losers Predominantly Below EMA200?

No.

Worst 100 by return:

- Top 10 below EMA200: `18%`
- Top 20 below EMA200: `36%`

Most large losers were not below EMA200 at signal date.

### 4. Were Losers Extended Far Above Moving Averages?

Yes, especially in the Top 10 ledger.

Worst 100 by return:

- Top 10 average distance from EMA50: `12.80%`
- Top 10 average distance from EMA200: `24.93%`
- Top 10 average prior 20d return: `16.55%`
- Top 10 average prior 60d return: `30.98%`

This suggests late-entry or extension risk. The model often bought stocks already far above moving averages after strong prior moves.

Top 20 losers were less extended but still positive on average before entry.

### 5. Were Losers Concentrated In Specific Sectors?

Yes.

Worst-return sectors:

- Top 10: IT, Consumer Goods, Financial Services, Pharma, Automobile.
- Top 20: IT, Financial Services, Energy, Industrial Manufacturing, Consumer Goods.

Worst-alpha sectors also show repeated weakness in IT and Consumer Goods.

### 6. Were Losers Concentrated In Specific Market Regimes?

Mostly in sideways regimes, with meaningful bearish exposure.

Worst 100 by return:

- Top 10: 66 sideways, 16 bearish, 15 bullish.
- Top 20: 60 sideways, 25 bearish, 11 bullish.

The loser problem is not limited to broad bear markets. Sideways regimes are the largest category, suggesting failed continuation after strong stock/sector moves.

### 7. Did Sector Rank Remain Strong While Individual Stock Trend Deteriorated?

Often yes.

The trade selection required strong sector rank and high ADX, but many losers were individually extended rather than weak by EMA position. That means sector rank could remain favorable while individual stock continuation risk deteriorated.

A sector can stay strong while a specific stock is late in its move or vulnerable to mean reversion.

### 8. Would A Simple Trend-Direction Filter Have Prevented These Trades?

No. The tested filters made performance worse.

For Top 20:

- Current avg return: `0.22%`, profit factor `1.059`, alpha `0.38%`
- Filter C, Close > EMA50 and EMA200: avg return `-0.36%`, profit factor `0.913`, alpha `0.30%`
- Filter D, Close > EMA50 and EMA50 > EMA200: avg return `-0.46%`, profit factor `0.892`, alpha `0.33%`

The filters removed many trades but did not improve results. This argues against a simple EMA trend-direction filter.

## Interpretation

The large losses are not mainly caused by missing basic trend-direction confirmation.

The evidence points more toward:

1. **Late trend / extension risk**: losers were often above EMA50/EMA200 and had strong prior 20d/60d returns.
2. **Sideways-regime failure**: many losers occurred when the broader market was neither strongly bullish nor bearish.
3. **Sector-level strength not guaranteeing stock-level continuation**: sector rank can remain strong while individual stock payoff becomes asymmetric or mean-reverting.
4. **High ADX without entry timing control**: ADX > 30 was common in the worst losers, so ADX strength alone can include exhausted trends.

## Recommendations

Do not add the tested simple EMA trend filters to production scoring.

Better research candidates are:

- extension caps, such as maximum distance above EMA50/EMA200,
- prior-return exhaustion filters,
- regime filter for sideways markets,
- sector-level risk caps,
- stock-level pullback or reset condition before entry,
- stop-loss or dynamic exit simulation.

A simple `Close > EMA50` or `Close > EMA200` rule does not solve the loser problem and materially worsens the tested ledger performance.

No production scoring was modified.
