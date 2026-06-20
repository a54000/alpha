# Relative Strength + 60-Minute RSI Experiment

Research-only test. No production strategy, recommendation, paper-trading, or database state was changed.

## Setup

- Signal: 66-session stock return minus Nifty 50 66-session return.
- Improvement: relative-strength spread higher than 5 sessions ago and higher than the prior session.
- Entry filter: 60-minute RSI14 below 60 on the signal day.
- Construction: Rolling 10, top 5 weekly candidates, 10:30 next-session entry, 20 trading-day planned exit.

## Results

| Metric | Value |
| --- | ---: |
| CAGR | 7.97% |
| Total return | 35.51% |
| Max drawdown | -37.82% |
| Sharpe | 0.40 |
| Sortino | 0.50 |
| Profit factor | 1.18 |
| Win rate | 49.27% |
| Closed trades | 481 |
| Average cash | 8.92% |

## Financial-Year Returns

| FY | Return | Max DD |
| --- | ---: | ---: |
| FY2022-23 | -15.95% | -27.80% |
| FY2023-24 | 56.25% | -18.25% |
| FY2024-25 | -7.72% | -28.76% |
| FY2025-26 | -2.96% | -17.43% |
| FY2026-27 | 8.69% | -4.10% |

## Interpretation

This experiment tests whether stock-level relative-strength acceleration plus a non-overheated intraday RSI filter can stand on its own.
It should be compared with SectorEdge 10 before considering any promotion.

## Artifacts

- `results/rs_rsi60_experiment/summary.json`
- `results/rs_rsi60_experiment/signals.csv`
- `results/rs_rsi60_experiment/trades.csv`
- `results/rs_rsi60_experiment/equity_curve.csv`
- `results/rs_rsi60_experiment/financial_year_returns.csv`
- `results/rs_rsi60_experiment/entry_log.csv`
