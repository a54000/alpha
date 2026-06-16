# Phase 5.17 Weekly Replacement Variant B

## Objective

Research-only test of weekly replacement using a Top 10 retention band.

## Rules

- Entry candidates: Top 5, score >= 70, price > EMA200.
- Weekly review: keep existing holdings if they remain in current Top 10.
- Exit: next rebalance open if rank drops outside Top 10.
- Replacement: fill open slots from current Top 5.
- Max open positions: 5.
- No transaction costs.
- No production tables modified.

## Results

- Total return: 97.34%
- CAGR: 18.77%
- Max drawdown: -22.79%
- Sharpe: 1.10
- Sortino: 1.55
- Profit factor: 1.37
- Win rate: 49.07%
- Closed trades: 589
- Turnover: 232.29
- Final equity: 1,973,413

## Baseline Comparison

| Metric | Baseline Top 5 V2.1 | Variant B | Delta |
| --- | ---: | ---: | ---: |
| Total Return | 167.01% | 97.34% | -69.67% |
| CAGR | 28.18% | 18.77% | -9.41% |
| Max Drawdown | -16.38% | -22.79% | -6.42% |
| Sharpe | 1.50 | 1.10 | -0.40 |
| Profit Factor | 2.07 | 1.37 | -0.71 |
| Win Rate | 61.01% | 49.07% | -11.94% |
| Turnover | 86.68 | 232.29 | 145.61 |
