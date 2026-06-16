# Phase 3B Replay Validation

Generated on: 2026-06-12

## Objective

Replay historical frozen Swing V2.1 recommendations through the new Phase 3A paper trading engine and compare accounting/performance against Phase 2E portfolio backtest results.

Replay period:

- 2025-01-01 to 2026-06-11

Strategies:

- Top 5 Weekly
- Top 10 Weekly

No scoring, recommendation generation, parameters, broker APIs, or production tables were modified.

## Delivered

Script:

- `scripts/run_phase3b_replay_validation.py`

Report:

- `reports/phase3b_replay_validation.json`

This script builds an in-memory replay database, seeds frozen pilot recommendations and pilot prices, then runs the Phase 3A `PaperTradingService`.

## Inputs

Replay inputs:

- `pilot_phase2a.recommendations_daily`
- `pilot_phase2a.daily_bars_clean`

Comparison inputs:

- `reports/phase2e_equity_curves.csv`
- `reports/phase2e_trade_ledger.csv`
- `reports/phase2e_portfolio_metrics.json`

## Replay Summary

| Strategy | Snapshots | Rebalance Dates | Paper Trades | First Rebalance | Last Rebalance |
| --- | ---: | ---: | ---: | --- | --- |
| Top 5 Weekly | 356 | 76 | 255 | 2025-01-01 | 2026-06-08 |
| Top 10 Weekly | 356 | 76 | 446 | 2025-01-01 | 2026-06-08 |

Exit reasons:

| Strategy | Weekly Removed | Planned Exit |
| --- | ---: | ---: |
| Top 5 Weekly | 255 | 0 |
| Top 10 Weekly | 443 | 3 |

## Performance Comparison

### Top 5 Weekly

| Metric | Paper Engine Replay | Phase 2E Same Period | Delta |
| --- | ---: | ---: | ---: |
| Total Return | -3.35% | 20.89% | -24.24 pp |
| CAGR | -2.39% | 14.42% | -16.81 pp |
| Max Drawdown | -28.44% | -12.79% | -15.65 pp |
| Sharpe | -0.016 | 0.825 | -0.841 |
| Profit Factor | 0.997 | 1.518 | -0.521 |
| Trade Count | 255 | 81 | +174 |

### Top 10 Weekly

| Metric | Paper Engine Replay | Phase 2E Same Period | Delta |
| --- | ---: | ---: | ---: |
| Total Return | -4.24% | 5.56% | -9.79 pp |
| CAGR | -3.03% | 3.91% | -6.94 pp |
| Max Drawdown | -18.85% | -10.85% | -8.00 pp |
| Sharpe | -0.082 | 0.316 | -0.398 |
| Profit Factor | 0.973 | 1.162 | -0.189 |
| Trade Count | 446 | 160 | +286 |

## Mismatch Identified

The paper engine output does **not** match Phase 2E.

Primary cause:

- Phase 3A paper workflow closes positions removed from the weekly recommendation set at rebalance.
- Phase 2E portfolio backtest keeps existing positions until the planned 20-trading-day exit, unless their holding period has completed.

This creates materially different behavior:

- much higher turnover
- many more closed trades
- shorter effective holding periods
- worse realized PnL
- worse drawdowns
- weaker Sharpe and profit factor

The mismatch is therefore a workflow-methodology mismatch, not a scoring or recommendation mismatch.

## Accounting Validation

The replay engine successfully exercised:

- portfolio initialization
- recommendation capture from frozen `swing_v2_1`
- weekly rebalance scheduling
- simulated entry creation
- quantity calculation
- NAV snapshots
- mark-to-market updates
- realized PnL on exits
- unrealized PnL on open positions
- turnover capture
- fees and slippage fields

Fees and slippage remained zero because Phase 3A infrastructure has fields for tracking them but does not yet apply a cost model.

## Recommendation

Before using the paper engine as a live-readiness proxy for Phase 2E results, align its rebalance semantics with the validated portfolio methodology.

Required Phase 3C decision:

1. Keep Phase 3A's current rebalance behavior as an intentional live paper trading rule, accepting that it is **not** Phase 2E parity.
2. Or add a `hold_to_planned_exit` mode so paper trading matches Phase 2E before live validation begins.

For paper trading validation of the frozen strategy, option 2 is recommended.

Reason:

- The frozen Top 5/Top 10 results were validated under the 20-trading-day holding methodology.
- Changing to weekly sell-removed behavior changes the strategy.
- The user explicitly requested no recommendation or strategy changes.

## Acceptance Confirmation

- Scoring unchanged.
- Recommendation generation unchanged.
- No optimization.
- No broker APIs connected.
- No production tables modified.
- Replay report generated.

## Files

- `scripts/run_phase3b_replay_validation.py`
- `reports/phase3b_replay_validation.json`
