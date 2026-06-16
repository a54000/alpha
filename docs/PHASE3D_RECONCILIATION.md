# Phase 3D Reconciliation

Generated on: 2026-06-12

## Objective

Identify remaining accounting differences between:

- Phase 2E portfolio backtest
- Phase 3C `hold_to_planned_exit` paper engine replay

Period:

- 2025-01-01 to 2026-06-11

Variants:

- Top 5 Weekly
- Top 10 Weekly

No scoring, recommendations, strategy rules, parameters, filters, or broker APIs were changed.

## Delivered

Script:

- `scripts/run_phase3d_reconciliation.py`

Report:

- `reports/phase3d_reconciliation.json`

## Summary

The remaining mismatch is not caused by entry or exit price differences.

For matched trades:

- entry prices match
- exit prices match

The remaining differences are caused by:

1. Initial state and cash deployment differences entering 2025.
2. Rebalance/capacity alignment differences during warmup.
3. Position sizing differences from reconstructed paper state.
4. Missing and extra trade keys caused by different open-position state at the beginning of the comparison window.

## First Divergence Date

| Variant | First Divergence | Phase 2E Normalized Equity | Paper Normalized NAV | Delta |
| --- | --- | ---: | ---: | ---: |
| Top 5 Weekly | 2025-01-02 | 1.002346 | 1.000000 | 0.002346 |
| Top 10 Weekly | 2025-01-02 | 1.007702 | 0.998811 | 0.008892 |

The divergence begins immediately after the comparison window opens. This indicates an initial-state mismatch rather than a late-period accounting drift.

## Trade-Level Reconciliation

### Top 5 Weekly

| Check | Count |
| --- | ---: |
| Phase 2E trades | 81 |
| Paper trades | 75 |
| Matched trades | 15 |
| Phase 2E trades missing from paper | 66 |
| Extra paper trades | 60 |
| Price mismatches | 0 |
| Quantity mismatches | 15 |
| Affected symbols | 91 |

### Top 10 Weekly

| Check | Count |
| --- | ---: |
| Phase 2E trades | 160 |
| Paper trades | 150 |
| Matched trades | 61 |
| Phase 2E trades missing from paper | 99 |
| Extra paper trades | 89 |
| Price mismatches | 0 |
| Quantity mismatches | 61 |
| Affected symbols | 110 |

## Price Validation

Matched trades show:

- `price_mismatch_count = 0` for Top 5
- `price_mismatch_count = 0` for Top 10

Conclusion:

Entry and exit price lookup is aligned between the paper replay and Phase 2E for matched trades.

## Position Sizing Differences

Matched trades still show quantity differences:

- Top 5: 15 matched trades with quantity differences
- Top 10: 61 matched trades with quantity differences

Examples:

Top 5:

| Symbol | Entry | Exit | Phase 2E Entry Value | Paper Entry Value |
| --- | --- | --- | ---: | ---: |
| ASTERDM | 2024-12-03 | 2025-01-01 | 453,795 | 200,000 |
| ASIANPAINT | 2024-12-03 | 2025-01-01 | 453,795 | 200,000 |
| BAJAJ-AUTO | 2024-12-03 | 2025-01-01 | 453,795 | 200,000 |

Top 10:

| Symbol | Entry | Exit | Phase 2E Entry Value | Paper Entry Value |
| --- | --- | --- | ---: | ---: |
| ASTERDM | 2024-12-03 | 2025-01-01 | 250,369 | 100,000 |
| ASIANPAINT | 2024-12-03 | 2025-01-01 | 250,369 | 100,000 |
| BAJAJ-AUTO | 2024-12-03 | 2025-01-01 | 222,512 | 100,000 |

Root cause:

Phase 2E entered these positions with an already-grown equity base from the full backtest run. The Phase 3C replay warmup starts fresh on 2024-12-01 with 1,000,000 capital, so the reconstructed position values are smaller.

## Missing And Extra Trades

Top 5 examples missing from paper:

- COALINDIA, entry 2024-12-24, exit 2025-01-22
- BERGEPAINT, entry 2024-12-24, exit 2025-01-22
- HFCL, entry 2025-01-28, exit 2025-02-24
- SRF, entry 2025-01-28, exit 2025-02-24
- OFSS, entry 2025-02-04, exit 2025-03-05

Top 5 examples extra in paper:

- BRITANNIA, entry 2024-12-03, exit 2025-01-01
- NTPC, entry 2024-12-03, exit 2025-01-01
- ASTRAL, entry 2025-01-07, exit 2025-02-03
- PIIND, entry 2025-01-07, exit 2025-02-03
- AIAENG, entry 2025-02-11, exit 2025-03-12

This confirms that the paper engine and Phase 2E do not have identical open-position state entering the comparison window.

## Reconciliation By Requested Area

### 1. Position Sizing Differences

Present.

Matched trades use the same prices but different quantities and entry values. This is caused by different capital bases and cash deployment state during the warmup period.

### 2. Entry Price Differences

Not found.

Matched trade entry prices align.

### 3. Exit Price Differences

Not found.

Matched trade exit prices align.

### 4. Cash Deployment Timing

Present.

The paper replay starts with a reconstructed cash state. Phase 2E's 2025 slice inherits an already-running portfolio from 2022-05-25.

### 5. Weekly Rebalance Date Alignment

Partially present.

The weekly replay dates are valid, but the set of open positions at each rebalance differs because the replay is not initialized from the Phase 2E pre-2025 state.

### 6. Overlapping Positions

Present as a state effect.

Both systems avoid duplicate same-symbol positions, but the different starting open-position set changes which slots are available in later weeks.

### 7. Portfolio Capacity Constraints

Present.

Because open slots differ, the engines admit different recommendations even with the same rank list and holding-period rule.

### 8. Fee/Slippage Application Timing

Not a driver.

Fees and slippage are zero in the paper replay. Phase 2E also did not include transaction costs in the gross backtest.

## Root Cause Classification

### Top 5 Weekly

| Category | Severity | Evidence |
| --- | --- | --- |
| Rebalance date or capacity alignment | High | 66 Phase 2E trades missing from paper and 60 extra paper trades |
| Position sizing and cash timing | Medium | 15 matched trades have quantity differences |
| Initial state or cash deployment | Medium | First divergence on 2025-01-02 |

### Top 10 Weekly

| Category | Severity | Evidence |
| --- | --- | --- |
| Rebalance date or capacity alignment | High | 99 Phase 2E trades missing from paper and 89 extra paper trades |
| Position sizing and cash timing | Medium | 61 matched trades have quantity differences |
| Initial state or cash deployment | Medium | First divergence on 2025-01-02 |

## Conclusion

Phase 3C fixed the lifecycle mismatch, but Phase 3D shows the replay is still not a perfect Phase 2E reproduction because it reconstructs state from a short warmup rather than importing the exact Phase 2E portfolio state.

The paper engine is directionally correct:

- hold-to-planned-exit behavior works
- planned exits are used
- entry and exit prices align for matched trades
- Top 10 metrics converge closely

The remaining Top 5 gap is primarily a state reconstruction and capacity/sizing issue, not a scoring, recommendation, or price issue.

## Recommended Next Step

For exact reconciliation, add one of the following:

1. **Full-period replay mode**
   - Replay from the Phase 2E start date, 2022-05-25, then compare only the 2025-01-01 to 2026-06-11 slice.

2. **State import mode**
   - Seed paper positions, cash, and NAV from a Phase 2E snapshot immediately before 2025-01-01.

Option 1 is cleaner and should be preferred.

## Acceptance Confirmation

- No scoring changes.
- No recommendation changes.
- No strategy rule changes.
- No parameter optimization.
- No broker APIs connected.
- Reconciliation JSON generated.
