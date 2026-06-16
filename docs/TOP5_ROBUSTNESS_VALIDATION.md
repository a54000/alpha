# Top 5 Robustness Validation

Date: 2026-06-11

## Objective

Determine whether Top 5 Weekly outperformance is robust versus Top 10 Weekly for Swing V2.1.

Models compared:

- Top 10 Weekly
- Top 5 Weekly

Rules held constant:

- Swing V2.1 scoring
- Weekly rebalance
- Next-trading-day open entry
- Close exit after 20 trading days
- Equal weighting
- No leverage

Output:

- `reports/top5_robustness_validation.json`

Alpha definition:

```text
Top 5 Weekly minus Top 10 Weekly
```

## Headline Results

| Metric | Top 10 Weekly | Top 5 Weekly | Top 5 Alpha |
| --- | ---: | ---: | ---: |
| CAGR | 7.59% | 9.60% | +2.01 pp |
| Total Return | 14.82% | 18.91% | +4.09 pp |
| Sharpe | 0.521 | 0.594 | +0.072 |
| Max Drawdown | -19.43% | -22.33% | -2.90 pp |
| Profit Factor | 1.253 | 1.331 | +0.078 |
| Closed Trades | 210 | 105 | -105 |

Top 5 Weekly improves return, Sharpe, and profit factor, but the improvement comes with a deeper drawdown.

## Time-Split Performance

| Period | Dates | Top 10 CAGR | Top 5 CAGR | CAGR Alpha | Top 10 Sharpe | Top 5 Sharpe | PF Alpha |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| First third | 2024-07-10 to 2025-02-21 | -15.53% | -18.03% | -2.50 pp | -0.818 | -0.898 | -0.048 |
| Middle third | 2025-02-24 to 2025-10-15 | 7.59% | 14.67% | +7.08 pp | 0.545 | 0.841 | +0.114 |
| Final third | 2025-10-16 to 2026-06-09 | 36.80% | 40.54% | +3.74 pp | 1.868 | 1.984 | +0.411 |

Top 5 does not outperform consistently across all time splits. It underperformed in the first third, then strongly outperformed in the middle and final thirds.

This means the outperformance is not uniformly robust across the whole sample. It is concentrated after the early drawdown regime.

## Rolling Window Summary

| Window | Count | Top 5 Positive Alpha Windows | Hit Rate | Best CAGR Alpha | Worst CAGR Alpha |
| --- | ---: | ---: | ---: | ---: | ---: |
| Rolling 6-month | 18 | 11 | 61.11% | +13.54 pp | -9.72 pp |
| Rolling 12-month | 12 | 10 | 83.33% | +9.58 pp | -1.77 pp |

Interpretation:

- Six-month robustness is moderate, not conclusive.
- Twelve-month robustness is stronger.
- Top 5 outperformance becomes more reliable over longer evaluation windows.
- Shorter windows still show meaningful periods where Top 5 underperforms Top 10.

## Sector Concentration

### Top 5 Weekly Sector Contribution

| Sector | Trades | Total PnL | Net PnL Share | Avg Return | Win Rate |
| --- | ---: | ---: | ---: | ---: | ---: |
| Financial Services | 22 | 177,941.43 | 94.08% | 4.27% | 63.64% |
| Energy | 4 | 71,165.45 | 37.62% | 8.98% | 100.00% |
| Pharma | 17 | 60,672.02 | 32.08% | 1.58% | 58.82% |
| Healthcare Services | 8 | 59,457.57 | 31.43% | 3.81% | 75.00% |
| Cement & Cement Products | 6 | 26,617.63 | 14.07% | 2.45% | 66.67% |
| Automobile | 9 | 20,798.28 | 11.00% | 1.16% | 44.44% |

### Top 10 Weekly Sector Contribution

| Sector | Trades | Total PnL | Net PnL Share | Avg Return | Win Rate |
| --- | ---: | ---: | ---: | ---: | ---: |
| Financial Services | 50 | 104,027.66 | 70.17% | 2.22% | 52.00% |
| Energy | 10 | 85,537.84 | 57.70% | 8.95% | 90.00% |
| Automobile | 14 | 56,535.56 | 38.14% | 4.15% | 57.14% |
| Pharma | 26 | 44,477.01 | 30.00% | 1.58% | 53.85% |
| Cement & Cement Products | 10 | 35,885.28 | 24.21% | 3.98% | 70.00% |
| Healthcare Services | 12 | 25,119.73 | 16.94% | 2.10% | 66.67% |

Top 5 is more dependent on Financial Services than Top 10. Financial Services contributes 94.08% of Top 5 net PnL versus 70.17% for Top 10.

This is a serious robustness caveat. Top 5 outperformance is not purely broad-based; it depends heavily on selecting the best Financial Services winners during this period.

Average exposure, however, is not more concentrated in Financial Services:

| Metric | Top 10 Weekly | Top 5 Weekly |
| --- | ---: | ---: |
| Largest average sector exposure | 21.09% | 18.59% |
| Top 3 average sector exposure | 42.26% | 41.12% |

So the risk is realized PnL concentration more than average sector-weight concentration.

## Transaction-Cost Sensitivity

Cost model:

```text
Estimated cost drag = turnover * cost_bps_per_traded_notional
```

This is an approximation. It does not model exact trade-date costs or bid-ask spread timing.

| Cost / Traded Notional | Top 10 Net CAGR | Top 5 Net CAGR | Top 5 Net CAGR Alpha | Top 10 Net Return | Top 5 Net Return |
| --- | ---: | ---: | ---: | ---: | ---: |
| 0 bps | 7.59% | 9.60% | +2.01 pp | 14.82% | 18.91% |
| 10 bps | 5.51% | 7.55% | +2.04 pp | 10.66% | 14.74% |
| 25 bps | 2.31% | 4.41% | +2.09 pp | 4.41% | 8.49% |
| 50 bps | -3.22% | -1.03% | +2.19 pp | -6.00% | -1.94% |
| 75 bps | -9.05% | -6.75% | +2.30 pp | -16.41% | -12.37% |
| 100 bps | -15.24% | -12.80% | +2.43 pp | -26.82% | -22.80% |

Because Top 5 and Top 10 have very similar turnover, Top 5 retains relative alpha after costs. But absolute performance is cost-sensitive:

- At 10 bps, Top 5 remains meaningfully positive.
- At 25 bps, Top 5 remains positive but much weaker.
- At 50 bps, both variants become negative on this approximate cost model.

So Top 5 survives modest transaction costs, but not high friction.

## Research Questions

### 1. Does Top 5 outperform consistently?

No.

Top 5 outperforms in headline metrics and in most 12-month windows, but not in every period. It underperformed in the first third and in 38.89% of rolling 6-month windows.

### 2. Is outperformance concentrated in one period?

Partly yes.

The first third was negative for both variants, and Top 5 was worse. Most of the Top 5 advantage appears in the middle and final thirds.

That means Top 5 outperformance is not purely one-month luck, but it is regime-dependent.

### 3. Is outperformance driven by one sector?

Partly yes.

Financial Services dominates Top 5 realized PnL contribution. Top 5 is not structurally more exposed to Financial Services by average weight, but its realized returns are heavily dependent on that sector.

### 4. Does it survive transaction costs?

Yes at modest costs, no at high costs.

Top 5 retains relative alpha versus Top 10 because both have similar turnover. However, absolute returns degrade quickly. At 50 bps per traded notional, both variants become negative in the approximate model.

## Verdict

Top 5 Weekly remains the stronger research structure, but robustness is not complete.

Validated:

- Better full-period CAGR
- Better full-period Sharpe
- Better full-period profit factor
- Stronger 12-month rolling robustness
- Relative alpha survives modest transaction-cost assumptions

Caveats:

- Underperformed in the first third
- Worse max drawdown than Top 10
- Only 61.11% positive alpha hit rate in rolling 6-month windows
- Realized PnL heavily depends on Financial Services
- Absolute returns are highly sensitive to transaction costs

Current conclusion:

```text
Top 5 Weekly is a promising but not fully robust upgrade over Top 10 Weekly.
It should remain the leading candidate, but only with explicit concentration,
cost, slippage, and regime-risk controls before production consideration.
```

