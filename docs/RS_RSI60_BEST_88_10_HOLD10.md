# Relative Strength + 60-Minute RSI Experiment

Research-only test. No production strategy, recommendation, paper-trading, or database state was changed.

## Setup

- Signal: 88-session stock return minus Nifty 50 88-session return.
- Improvement: relative-strength spread higher than 10 sessions ago and higher than the prior session.
- Entry filter: 60-minute RSI14 below 60 on the signal day.
- Minimum relative-strength spread: 0.0.
- Construction: Rolling 10, top 5 weekly candidates, 10:30 next-session entry, 20 trading-day planned exit.

## Results

| Metric | Value |
| --- | ---: |
| CAGR | 23.24% |
| Total return | 128.74% |
| Max drawdown | -24.35% |
| Sharpe | 1.13 |
| Sortino | 1.42 |
| Profit factor | 1.38 |
| Win rate | 53.40% |
| Closed trades | 897 |
| Average cash | 19.18% |

## Financial-Year Returns

| FY | Return | Max DD |
| --- | ---: | ---: |
| FY2022-23 | -13.27% | -17.23% |
| FY2023-24 | 96.19% | -15.43% |
| FY2024-25 | 16.61% | -22.46% |
| FY2025-26 | -5.50% | -17.50% |
| FY2026-27 | 20.09% | -4.82% |

## Interpretation

This experiment tests whether stock-level relative-strength acceleration plus a non-overheated intraday RSI filter can stand on its own.
It should be compared with SectorEdge 10 before considering any promotion.

## Artifacts

- `results\rs_rsi60_best_88_10_hold10\signals.csv`
- `results\rs_rsi60_best_88_10_hold10\trades.csv`
- `results\rs_rsi60_best_88_10_hold10\equity_curve.csv`
- `results\rs_rsi60_best_88_10_hold10\financial_year_returns.csv`
- `results\rs_rsi60_best_88_10_hold10\entry_log.csv`
