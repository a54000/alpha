# Phase 2G Walk Forward Validation

Generated on: 2026-06-12

## Objective

Validate Swing V2.1 portfolio stability across independent time segments using Phase 2E outputs.

Inputs:

- `reports/phase2e_trade_ledger.csv`
- `reports/phase2e_equity_curves.csv`
- `reports/phase2e_portfolio_metrics.json`

Output:

- `reports/phase2g_walk_forward.json`

No scoring, parameters, filters, or production tables were changed.

## Implemented Script

`scripts/run_phase2g_walk_forward_validation.py`

The script slices existing Phase 2E equity curves and trade ledger rows into fixed walk-forward periods:

| Period | Start | End |
| --- | --- | --- |
| Period 1 | 2022-05-25 | 2023-12-31 |
| Period 2 | 2024-01-01 | 2025-06-30 |
| Period 3 | 2025-07-01 | 2026-06-11 |

Variants evaluated:

- Top 5 Weekly
- Top 10 Weekly

## Results

### Top 5 Weekly

| Period | Total Return | CAGR | Sharpe | Max Drawdown | Profit Factor | Monthly Win Rate | Trades |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Period 1 | 46.70% | 27.78% | 1.514 | -12.31% | 1.927 | 63.16% | 85 |
| Period 2 | 55.94% | 35.56% | 1.721 | -16.38% | 2.416 | 76.47% | 80 |
| Period 3 | 15.73% | 17.20% | 1.049 | -8.78% | 1.752 | 54.55% | 53 |

Top 5 remains positive in all three periods. Period 3 is weaker than the first two periods, but the edge does not disappear.

### Top 10 Weekly

| Period | Total Return | CAGR | Sharpe | Max Drawdown | Profit Factor | Monthly Win Rate | Trades |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Period 1 | 65.82% | 38.19% | 1.889 | -12.91% | 2.454 | 68.42% | 170 |
| Period 2 | 52.79% | 33.68% | 1.276 | -13.83% | 2.408 | 70.59% | 155 |
| Period 3 | 0.10% | 0.11% | 0.085 | -9.42% | 1.019 | 45.45% | 106 |

Top 10 stays barely positive in Period 3, but its edge nearly vanishes in the final segment.

## Stability Summary

| Metric | Top 5 Weekly | Top 10 Weekly |
| --- | ---: | ---: |
| Positive CAGR periods | 3 / 3 | 3 / 3 |
| Positive Sharpe periods | 3 / 3 | 3 / 3 |
| Profit factor > 1 periods | 3 / 3 | 3 / 3 |
| Minimum CAGR | 17.20% | 0.11% |
| Maximum CAGR | 35.56% | 38.19% |
| CAGR range | 18.36 pp | 38.08 pp |
| Worst max drawdown | -16.38% | -13.83% |

## Findings

### 1. Is performance consistent across periods?

Partially.

Both variants are positive across all periods, but performance is materially weaker in Period 3.

Top 5 is more consistent by CAGR:

- Period CAGR range: 18.36 percentage points
- Minimum period CAGR: 17.20%

Top 10 has larger dispersion:

- Period CAGR range: 38.08 percentage points
- Minimum period CAGR: 0.11%

### 2. Does edge disappear in any segment?

No, not by the formal criteria:

- No period has negative CAGR.
- No period has negative Sharpe.
- No period has profit factor below 1.

However, Top 10 Weekly's Period 3 edge is economically close to flat:

- CAGR: 0.11%
- Sharpe: 0.085
- Profit factor: 1.019
- Monthly win rate: 45.45%

That is a warning flag, even though it does not technically fail.

### 3. Is Top 5 or Top 10 more stable?

Top 5 is more stable by return persistence.

Top 10 is more stable by drawdown.

Practical interpretation:

- Use **Top 5 Weekly** when prioritizing persistent alpha.
- Use **Top 10 Weekly** when prioritizing drawdown control and broader diversification.

## Decision

The walk-forward validation supports continuing Swing V2.1 validation.

Recommended interpretation:

1. Top 5 Weekly remains the stronger alpha structure.
2. Top 10 Weekly remains the safer baseline, but its final-period performance is weak.
3. Period 3 should be investigated in a later diagnostics phase before promoting any structure to production.

## Caveats

- The periods are calendar splits, not expanding-window retrains, because no model fitting occurs.
- Metrics are sliced from existing Phase 2E portfolio curves and trades.
- No benchmark-relative market regime adjustment is included here.
- Transaction costs are not applied in this walk-forward split.

## Acceptance Confirmation

- Scoring unchanged.
- No parameter optimization.
- No filters added.
- No production table modifications.
- Walk-forward JSON generated.
