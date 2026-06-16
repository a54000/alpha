# Portfolio Backtest Results

Date: 2026-06-11

## Objective

Evaluate realistic portfolio performance for:

- V1 Swing
- Swing V2
- Swing V2.1

Goal:

Determine whether Swing V2.1 improvements survive portfolio construction.

## Outputs

- `reports/portfolio_backtest_results.json`
- `reports/portfolio_equity_curves.csv`

## Methodology

Backtester:

```text
PortfolioBacktesterV1
```

Portfolio rules:

- Top 10 recommendations
- Equal weight target allocation
- Weekly rebalance
- Signal after EOD close
- Entry at next-trading-day open
- Exit at close after 20 trading days
- Replace exited positions using the current weekly ranking
- Track cash
- No leverage
- No transaction costs

Implementation note:

Weekly rebalance uses the first available recommendation date in each ISO week. Existing positions are held until their 20-trading-day exit; weekly ranking is used to fill open slots.

## Headline Results

| Model | Total Return | CAGR | Max Drawdown | Sharpe | Sortino | Volatility |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| V1 Swing | 5.89% | 3.07% | -28.89% | 0.284 | 0.371 | 19.61% |
| Swing V2 | 8.91% | 4.61% | -17.34% | 0.343 | 0.456 | 23.91% |
| Swing V2.1 | 14.82% | 7.59% | -19.43% | 0.521 | 0.810 | 17.32% |

## Trade And Portfolio Metrics

| Model | Closed Trades | Win Rate | Profit Factor | Turnover | Avg Holding Period |
| --- | ---: | ---: | ---: | ---: | ---: |
| V1 Swing | 189 | 48.15% | 1.127 | 37.66x | 20.00 |
| Swing V2 | 210 | 47.62% | 1.138 | 41.69x | 20.00 |
| Swing V2.1 | 210 | 48.10% | 1.253 | 41.64x | 20.00 |

## Sector Concentration

| Model | Top Sector | Top Sector Avg Weight | Top 3 Sector Avg Weight |
| --- | --- | ---: | ---: |
| V1 Swing | Financial Services | 17.25% | 38.44% |
| Swing V2 | Financial Services | 19.93% | 38.14% |
| Swing V2.1 | Financial Services | 21.09% | 42.26% |

V2.1 has the highest sector concentration among the three models. The top sector remains Financial Services.

## Final Equity

Initial capital:

```text
1,000,000
```

| Model | Final Equity |
| --- | ---: |
| V1 Swing | 1,058,902.94 |
| Swing V2 | 1,089,060.67 |
| Swing V2.1 | 1,148,242.74 |

## Interpretation

V2.1 survives portfolio construction.

Compared with V1 and Swing V2, V2.1 produced:

- highest total return
- highest CAGR
- highest Sharpe ratio
- highest Sortino ratio
- highest profit factor
- lowest volatility
- highest final equity

The main caveat is drawdown:

- V2 max drawdown: `-17.34%`
- V2.1 max drawdown: `-19.43%`

So V2.1 improves most risk-adjusted metrics, but it does not produce the lowest drawdown.

## Does V2.1 Improvement Survive?

Yes.

The model-level improvement survives realistic portfolio construction under the current assumptions.

V2.1 improves total return versus:

- V1 by `+8.93 percentage points`
- V2 by `+5.92 percentage points`

V2.1 improves CAGR versus:

- V1 by `+4.52 percentage points`
- V2 by `+2.98 percentage points`

V2.1 improves profit factor versus:

- V1 by `+0.126`
- V2 by `+0.115`

## Caveats

This is still a research backtest.

Known caveats:

- No transaction costs
- No slippage
- No brokerage, STT, or stamp duty
- No point-in-time universe correction
- High survivorship-bias risk remains
- Weekly rebalance is simplified to first available recommendation date per week
- Existing positions are not force-rebalanced to exact 10% weights each week
- Cash can remain idle if not enough valid replacements are available
- No stop-loss or target exit logic
- No dynamic rank-decay exit
- No benchmark portfolio comparison in this report

## Verdict

Swing V2.1 remains the leading research model after portfolio construction.

Status:

```text
V2.1 survives portfolio construction.
Research-only, not production-approved.
```

Recommended next validation:

1. Add transaction costs and slippage.
2. Add point-in-time universe correction.
3. Add benchmark equity curve comparison.
4. Test sector exposure caps for V2.1.
