# Phase 5.24 Rolling 10-Slot Stop-Loss 10% Backtest Findings

## Objective

Test the current preferred rolling 10-slot portfolio construction with a maximum per-trade loss of 10%.

## Variant Tested

Rules:

- Entry: up to Top 5 recommendations each week.
- Eligibility: score >= 70 and price > EMA200.
- Maximum open positions: 10.
- Position size: equity at open / 10.
- Planned holding period: 20 trading days.
- Stop loss: 10% max loss per trade.
- Stop-loss trigger: daily low <= 10% below entry price.
- Stop-loss execution price: entry price * 0.90.
- No scoring changes.
- No recommendation changes.
- No production table changes.

## Results

| Metric | Rolling 10 Baseline | Rolling 10 + 10% Stop | Delta |
| --- | ---: | ---: | ---: |
| CAGR | 29.37% | 26.53% | -2.84 pp |
| Total return | 176.72% | 153.49% | -23.23 pp |
| Final equity | 2,767,223 | 2,534,884 | -232,339 |
| Max drawdown | -18.09% | -17.30% | +0.79 pp |
| Sharpe | 1.36 | 1.43 | +0.08 |
| Sortino | 1.76 | 1.88 | +0.11 |
| Profit factor | 2.06 | 1.89 | -0.17 |
| Win rate | 56.78% | 55.18% | -1.60 pp |
| Closed trades | 391 | 415 | +24 |

## Exit Breakdown

| Exit reason | Count |
| --- | ---: |
| Stop loss | 75 |
| Planned exit | 340 |
| Forced final exit | 0 |

## Interpretation

The 10% stop-loss improves the risk-adjusted ratios slightly:

- Sharpe improves from `1.36` to `1.43`.
- Sortino improves from `1.76` to `1.88`.
- Max drawdown improves from `-18.09%` to `-17.30%`.

But the improvement in drawdown is small relative to the return given up:

- CAGR falls by `2.84` percentage points.
- Total return falls by `23.23` percentage points.
- Final equity falls by about `232k` on `1,000,000` starting capital.
- Profit factor weakens from `2.06` to `1.89`.

## Finding

A hard 10% stop-loss is not clearly attractive for the rolling 10-slot construction.

It cuts some losing trades earlier and slightly smooths volatility, but it also interrupts trades that may recover before the planned 20-trading-day exit. The drawdown reduction is too small to justify the return drag as a default rule.

## Recommendation

Do not promote 10% stop-loss to the preferred portfolio construction yet.

Better next experiments:

1. Test wider stops: 12%, 15%.
2. Test close-based stop instead of intraday-low trigger.
3. Test stop only after first 3-5 holding days.
4. Test sector or volatility-conditioned stops.

## Artifacts

- `reports/phase5_24_rolling_10_stoploss10_backtest.json`
- `reports/phase5_24_rolling_10_stoploss10_summary.json`
- `reports/phase5_24_rolling_10_stoploss10_trade_ledger.csv`
- `reports/phase5_24_rolling_10_stoploss10_equity_curve.csv`
- `reports/phase5_24_rolling_10_stoploss10_weekly_deployment.csv`
