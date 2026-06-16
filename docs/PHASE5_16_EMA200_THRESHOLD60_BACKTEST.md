# Phase 5.16 EMA200 Threshold 60 Backtest

## Objective

Research-only test of lowering Swing V2.1 recommendation threshold to 60 while requiring price above EMA200.

## Rules

- Score threshold: `>= 60`.
- EMA200 gate: `ema200_extension > 0`.
- Portfolio: Top 5 Weekly.
- Entry: next trading day open.
- Exit: close after 20 trading days.
- No transaction costs.
- No production tables modified.

## Results

- Total return: 51.02%
- CAGR: 10.98%
- Max drawdown: -32.41%
- Sharpe: 0.52
- Sortino: 0.66
- Profit factor: 1.34
- Win rate: 52.97%
- Closed trades: 219
- Final equity: 1,510,223

## Baseline Comparison

| Metric | Baseline Top 5 V2.1 | EMA200 + Threshold 60 | Delta |
| --- | ---: | ---: | ---: |
| Total Return | 167.01% | 51.02% | -115.99% |
| CAGR | 28.18% | 10.98% | -17.19% |
| Max Drawdown | -16.38% | -32.41% | -16.04% |
| Sharpe | 1.50 | 0.52 | -0.98 |
| Profit Factor | 2.07 | 1.34 | -0.73 |
| Win Rate | 61.01% | 52.97% | -8.04% |

## Interpretation

This is a replacement-aware portfolio backtest using generated research recommendations, not a change to the active production strategy.