# Rolling Cohort Backtest

## Rules

- Entry: up to Top 5 each week.
- Eligibility: score >= 70 and price > EMA200.
- Position size: calculated as equity at open / 10.
- Max open positions: 10.
- Exit: planned exit after 20 trading days.
- Stop loss: none.
- No rank-drop exits.
- No transaction costs.

## Results

- CAGR: 26.38%
- Total return: 152.30%
- Max drawdown: -18.64%
- Sharpe: 1.20
- Profit factor: 1.84
- Win rate: 57.71%
- Trades: 428
- Turnover: 84.86
- Average open positions: 8.17
- Average cash percentage: 18.83%
- Average slot utilization: 81.68%

## Baseline Comparison

| Metric | Baseline Max-5 Hold | Rolling 20 Cohort | Delta |
| --- | ---: | ---: | ---: |
| CAGR | 28.18% | 26.38% | -1.79% |
| Total Return | 167.01% | 152.30% | -14.71% |
| Max Drawdown | -16.38% | -18.64% | -2.27% |
| Sharpe | 1.50 | 1.20 | -0.30 |
| Profit Factor | 2.07 | 1.84 | -0.23 |
| Win Rate | 61.01% | 57.71% | -3.30% |
| Turnover | 86.68 | 84.86 | -1.82 |