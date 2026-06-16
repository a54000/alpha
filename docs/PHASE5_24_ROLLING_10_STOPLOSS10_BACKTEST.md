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

- CAGR: 26.53%
- Total return: 153.49%
- Max drawdown: -17.30%
- Sharpe: 1.43
- Profit factor: 1.89
- Win rate: 55.18%
- Trades: 415
- Turnover: 82.35
- Average open positions: 7.61
- Average cash percentage: 24.13%
- Average slot utilization: 76.13%

## Baseline Comparison

| Metric | Baseline Max-5 Hold | Rolling 20 Cohort | Delta |
| --- | ---: | ---: | ---: |
| CAGR | 28.18% | 26.53% | -1.64% |
| Total Return | 167.01% | 153.49% | -13.53% |
| Max Drawdown | -16.38% | -17.30% | -0.93% |
| Sharpe | 1.50 | 1.43 | -0.07 |
| Profit Factor | 2.07 | 1.89 | -0.18 |
| Win Rate | 61.01% | 55.18% | -5.83% |
| Turnover | 86.68 | 82.35 | -4.33 |