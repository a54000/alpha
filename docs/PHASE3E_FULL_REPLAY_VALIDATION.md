# Phase 3E Full Historical Paper Replay Validation

Generated on: 2026-06-12

## Objective

Replay the paper trading engine from the same historical start date used by the Phase 2E portfolio backtest, then compare the validation slice against prior Phase 2E results.

## Scope

- Replay period: 2022-05-25 to 2026-06-11
- Comparison slice: 2025-01-01 to 2026-06-11
- Strategies: Top 5 Weekly, Top 10 Weekly
- Paper mode: `hold_to_planned_exit`
- Exit behavior: positions are held until the planned holding period completes
- Warmup behavior: paper engine initialized from 2022-05-25 so the 2025 comparison slice starts with full historical state

## Deliverables

- Main report: `reports/phase3e_full_replay.json`
- Raw replay output: `reports/phase3e_full_replay_raw.json`
- Reconciliation output: `reports/phase3e_full_replay_reconciliation.json`

## Constraints Preserved

- No strategy changes
- No scoring changes
- No recommendation changes
- No portfolio rule changes
- No broker API connections

## Metric Comparison

### Top 5 Weekly

| Metric | Paper Replay | Phase 2E | Delta |
|---|---:|---:|---:|
| Total Return | 17.47% | 20.89% | -3.42 pp |
| CAGR | 12.11% | 14.42% | -2.31 pp |
| Max Drawdown | -13.07% | -12.79% | -0.28 pp |
| Sharpe | 0.686 | 0.825 | -0.139 |
| Profit Factor | 1.385 | 1.518 | -0.133 |
| Trade Count | 75 | 81 | -6 |

### Top 10 Weekly

| Metric | Paper Replay | Phase 2E | Delta |
|---|---:|---:|---:|
| Total Return | 7.99% | 5.56% | +2.44 pp |
| CAGR | 5.61% | 3.91% | +1.70 pp |
| Max Drawdown | -12.33% | -10.85% | -1.49 pp |
| Sharpe | 0.421 | 0.316 | +0.105 |
| Profit Factor | 1.193 | 1.162 | +0.031 |
| Trade Count | 148 | 160 | -12 |

## Position History and Trade Matching

### Top 5 Weekly

- Phase 2E trades in slice: 81
- Paper trades in slice: 75
- Matched trades: 18
- Match rate vs Phase 2E: 22.22%
- Match rate vs paper replay: 24.00%
- Missing from paper: 63
- Extra in paper: 57
- Entry/exit price mismatches on matched trades: 0
- Quantity mismatches on matched trades: 18
- Affected symbols: 81

### Top 10 Weekly

- Phase 2E trades in slice: 160
- Paper trades in slice: 148
- Matched trades: 70
- Match rate vs Phase 2E: 43.75%
- Match rate vs paper replay: 47.30%
- Missing from paper: 90
- Extra in paper: 78
- Entry/exit price mismatches on matched trades: 0
- Quantity mismatches on matched trades: 70
- Affected symbols: 102

## First Divergence

| Strategy | First Divergence Date | Phase 2E Normalized Equity | Paper Normalized NAV | Absolute Delta |
|---|---:|---:|---:|---:|
| Top 5 Weekly | 2025-01-02 | 1.002346 | 1.001282 | 0.001064 |
| Top 10 Weekly | 2025-01-02 | 1.007702 | 0.999954 | 0.007749 |

The full historical replay removes the obvious 2025-only initial-state mismatch by letting positions, cash, and lifecycle state evolve from 2022-05-25. However, the validation slice still diverges immediately on 2025-01-02, so a residual accounting or scheduling difference remains.

## Root Cause Classification

### High Severity: Rebalance Date or Capacity Alignment

The largest mismatch is trade identity. Top 5 has 63 Phase 2E trades missing from paper and 57 extra paper trades. Top 10 has 90 missing and 78 extra. This indicates the two engines are still selecting or admitting different trades, even under the same `hold_to_planned_exit` lifecycle.

Likely areas:

- Weekly rebalance date selection
- Recommendation date versus entry date alignment
- Capacity handling when existing planned-exit positions overlap new recommendations
- Treatment of unavailable prices on intended entry or exit dates

### Medium Severity: Position Sizing and Cash Timing

All matched trades have quantity differences. Top 5 has 18 quantity mismatches across 18 matched trades. Top 10 has 70 quantity mismatches across 70 matched trades.

This points to a sizing formula or cash deployment difference rather than a price source difference.

Likely areas:

- Equal-weight allocation denominator
- Whether cash from same-day exits is reusable for same-day entries
- Rounding behavior for share quantities
- Fee/slippage timing relative to sizing
- NAV basis used for allocation

### Medium Severity: Residual Initial State or Cash Deployment

Both strategies diverge on 2025-01-02 despite the full-period replay start. The divergence is small for Top 5 and larger for Top 10, but it appears before the first major 2025 rebalance activity.

This suggests the accumulated state entering 2025 is still not identical to Phase 2E. The most plausible causes are overlapping positions, cash deployment timing, or different earlier admission decisions rather than missing warmup history.

## Interpretation

Phase 3E confirms that replaying from the Phase 2E start date is necessary but not sufficient for exact parity.

The good signal is that matched trades have no price mismatches. That means the paper engine and Phase 2E are using compatible market prices for trades that line up. The remaining gap is concentrated in portfolio mechanics:

- which positions are opened,
- when capacity becomes available,
- how quantities are sized,
- and how cash is recycled across exits and entries.

Top 10 remains closer in performance directionally, but trade-level parity is still incomplete. Top 5 remains below Phase 2E performance and has the weaker trade matching rate.

## Conclusion

The Phase 3E full historical replay materially improves the validation setup by eliminating the prior short-window initial-state flaw, but it does not fully reconcile the paper engine with Phase 2E.

The remaining mismatch is not caused by scoring, recommendations, or price selection. It is most likely caused by differences between the Phase 2E backtester and the paper engine in weekly rebalance alignment, capacity handling, cash reuse, and quantity sizing.

Before using the paper engine as a live validation proxy for the frozen Swing V2.1 backtest, the next reconciliation step should compare the two engines on a rebalance-by-rebalance basis from 2022-05-25, including:

- open positions before rebalance,
- available cash before and after exits,
- recommendations considered,
- positions admitted or skipped,
- allocation base,
- rounded quantity,
- fees/slippage deducted,
- resulting cash and NAV.
