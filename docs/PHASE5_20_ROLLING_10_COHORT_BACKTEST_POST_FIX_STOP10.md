# Rolling Cohort Backtest

## Rules

- Entry: up to Top 5 each week.
- Eligibility: score >= 70 and price > EMA200.
- Position size: calculated as equity at open / 10.
- Max open positions: 10.
- Exit: planned exit after 20 trading days.
- Stop loss: 10.00% max loss per trade, triggered by daily low and exited at stop price.
- No rank-drop exits.
- No transaction costs.

## Results

- CAGR: 22.38%
- Total return: 122.17%
- Max drawdown: -19.24%
- Sharpe: 1.22
- Profit factor: 1.67
- Win rate: 54.57%
- Trades: 449
- Turnover: 89.14
- Average open positions: 7.82
- Average cash percentage: 21.84%
- Average slot utilization: 78.24%

## Baseline Comparison

| Metric | Baseline Max-5 Hold | Rolling 20 Cohort | Delta |
| --- | ---: | ---: | ---: |
| CAGR | 28.18% | 22.38% | -5.80% |
| Total Return | 167.01% | 122.17% | -44.84% |
| Max Drawdown | -16.38% | -19.24% | -2.86% |
| Sharpe | 1.50 | 1.22 | -0.28 |
| Profit Factor | 2.07 | 1.67 | -0.40 |
| Win Rate | 61.01% | 54.57% | -6.44% |
| Turnover | 86.68 | 89.14 | 2.46 |