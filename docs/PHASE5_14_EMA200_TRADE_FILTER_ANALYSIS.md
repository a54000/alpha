# Phase 5.14 EMA200 Trade Filter Analysis

## Objective

Analyze whether the five-year Swing V2.1 pilot trades performed better when the stock was above its daily EMA200.

This is analysis only. No scoring, recommendation, portfolio, or database logic was changed.

## Method

- Trade source: `reports/phase2e_trade_ledger.csv`.
- Feature source: `pilot_phase2a.features_daily`.
- Price path source: `pilot_phase2a.daily_bars_clean`.
- Primary classification: signal-date close versus signal-date EMA200.
- Diagnostic classification: entry-date close versus entry-date EMA200.

Signal-date classification is the actionable version because the strategy enters on the next trading day's open.

## Results By Signal-Date EMA200

### top10_weekly

| Bucket | Trades | Win Rate | Avg Return | Median Return | Total PnL | Profit Factor | Avg MAE | Avg MFE | Avg EMA200 Ext |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| above_ema200 | 267 | 58.05% | 2.30% | 1.18% | 914,802 | 1.69 | -6.07% | 8.78% | 14.34% |
| below_or_equal_ema200 | 164 | 59.76% | 2.31% | 1.27% | 623,096 | 1.99 | -5.56% | 8.77% | -13.61% |
| unknown | 0 | n/a | n/a | n/a | 0 | n/a | n/a | n/a | n/a |

### top10_weekly_max2_sector

| Bucket | Trades | Win Rate | Avg Return | Median Return | Total PnL | Profit Factor | Avg MAE | Avg MFE | Avg EMA200 Ext |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| above_ema200 | 265 | 55.47% | 2.34% | 0.60% | 891,552 | 1.71 | -6.11% | 9.04% | 13.80% |
| below_or_equal_ema200 | 163 | 58.90% | 1.87% | 1.44% | 475,273 | 1.67 | -6.34% | 8.58% | -14.03% |
| unknown | 0 | n/a | n/a | n/a | 0 | n/a | n/a | n/a | n/a |

### top5_weekly

| Bucket | Trades | Win Rate | Avg Return | Median Return | Total PnL | Profit Factor | Avg MAE | Avg MFE | Avg EMA200 Ext |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| above_ema200 | 143 | 62.94% | 2.98% | 2.14% | 1,346,581 | 2.21 | -5.65% | 8.94% | 14.50% |
| below_or_equal_ema200 | 75 | 57.33% | 1.26% | 1.25% | 323,560 | 1.52 | -5.98% | 7.81% | -13.24% |
| unknown | 0 | n/a | n/a | n/a | 0 | n/a | n/a | n/a | n/a |

## Interpretation

For Top 5 Weekly, above-EMA200 trades show stronger average return and profit factor than below/equal-EMA200 trades. This supports testing an EMA200-positive gate in a V2.2 experiment, but it should be confirmed with a full portfolio resimulation before changing rules.

## Caveats

- This is a trade cohort analysis, not a full portfolio resimulation with replacement picks.
- Filtering below-EMA200 trades would change cash deployment and may alter portfolio-level CAGR/drawdown.
- Signal-date EMA200 is the correct no-lookahead gate; entry-date classification is diagnostic only.
- Transaction costs are not included in the Phase 2E trade ledger.
