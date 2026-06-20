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
| CAGR | 26.05% |
| Total return | 150.15% |
| Max drawdown | -19.50% |
| Sharpe | 1.15 |
| Sortino | 1.49 |
| Profit factor | 1.56 |
| Win rate | 55.65% |
| Closed trades | 478 |
| Average cash | 9.59% |

## Financial-Year Returns

| FY | Return | Max DD |
| --- | ---: | ---: |
| FY2022-23 | -1.00% | -16.35% |
| FY2023-24 | 71.10% | -19.50% |
| FY2024-25 | 4.73% | -18.88% |
| FY2025-26 | -4.32% | -19.27% |
| FY2026-27 | 27.42% | -3.76% |

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
