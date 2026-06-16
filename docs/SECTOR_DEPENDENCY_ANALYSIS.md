# Sector Dependency Analysis

Date: 2026-06-11

## Objective

Determine whether Swing V2.1 is dependent on Financial Services leadership.

Model under test:

```text
swing_v2_1
```

Portfolio base:

- Top 10 Weekly
- Equal weight
- Next-trading-day open entry
- Close exit after 20 trading days
- No leverage
- No transaction costs

Output:

- `reports/sector_dependency_analysis.json`

## Variants Tested

| Variant | Constraint |
| --- | --- |
| Baseline | No sector constraint |
| Exclude Financial Services | No Financial Services positions |
| Max 30% sector exposure | Entry-time sector cap of 30% |
| Max 20% sector exposure | Entry-time sector cap of 20% |
| Max 2 positions per sector | No more than 2 open positions in any sector |

Implementation note:

Constrained variants can look past the original top 10 recommendations up to rank 50 to fill eligible slots. Sector exposure caps are applied at entry time; the simulator does not force daily sector rebalancing if price drift changes exposure later.

## Headline Results

| Variant | CAGR | Total Return | Sharpe | Max Drawdown | Profit Factor | Win Rate | Trades |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Baseline Top 10 Weekly | 7.59% | 14.82% | 0.521 | -19.43% | 1.253 | 48.10% | 210 |
| Exclude Financial Services | 3.02% | 5.79% | 0.272 | -22.41% | 1.119 | 47.60% | 208 |
| Max 30% Sector Exposure | 3.42% | 6.56% | 0.293 | -18.38% | 1.132 | 46.19% | 210 |
| Max 20% Sector Exposure | 4.98% | 9.62% | 0.377 | -20.85% | 1.173 | 45.71% | 210 |
| Max 2 Positions Per Sector | 9.53% | 18.76% | 0.609 | -20.85% | 1.306 | 47.62% | 210 |

## Sector Exposure

| Variant | Top Sector | Top Sector Avg Weight | Top 3 Sector Avg Weight |
| --- | --- | ---: | ---: |
| Baseline | Financial Services | 21.09% | 42.26% |
| Exclude Financial Services | Consumer Goods | 14.10% | 35.73% |
| Max 30% Sector Exposure | Financial Services | 16.70% | 38.52% |
| Max 20% Sector Exposure | Financial Services | 15.04% | 34.28% |
| Max 2 Positions Per Sector | Financial Services | 15.49% | 34.28% |

The baseline is meaningfully exposed to Financial Services, but its average exposure is not extreme. The larger concern is realized PnL contribution, not just average weight.

## Sector Contribution

### Baseline Top Contributors

| Sector | Trades | Total PnL | Net PnL Share | Avg Return | Win Rate |
| --- | ---: | ---: | ---: | ---: | ---: |
| Financial Services | 50 | 104,027.66 | 70.17% | 2.22% | 52.00% |
| Energy | 10 | 85,537.84 | 57.70% | 8.95% | 90.00% |
| Automobile | 14 | 56,535.56 | 38.14% | 4.15% | 57.14% |
| Pharma | 26 | 44,477.01 | 30.00% | 1.58% | 53.85% |
| Cement & Cement Products | 10 | 35,885.28 | 24.21% | 3.98% | 70.00% |
| Healthcare Services | 12 | 25,119.73 | 16.94% | 2.10% | 66.67% |

Financial Services is the largest baseline contributor. It accounts for about 70.17% of net PnL.

### Excluding Financial Services

| Sector | Trades | Total PnL | Net PnL Share | Avg Return | Win Rate |
| --- | ---: | ---: | ---: | ---: | ---: |
| Energy | 15 | 66,002.62 | 114.07% | 4.98% | 73.33% |
| Automobile | 18 | 57,833.41 | 99.95% | 3.40% | 61.11% |
| Pharma | 30 | 52,489.53 | 90.72% | 1.83% | 53.33% |
| Cement & Cement Products | 12 | 27,497.38 | 47.52% | 2.77% | 66.67% |
| Industrial Manufacturing | 18 | 23,743.32 | 41.04% | 1.58% | 55.56% |
| Metals | 22 | 14,708.72 | 25.42% | 0.91% | 45.45% |

The model remains profitable without Financial Services, but much weaker:

- CAGR falls from 7.59% to 3.02%.
- Sharpe falls from 0.521 to 0.272.
- Profit factor falls from 1.253 to 1.119.
- Max drawdown worsens from -19.43% to -22.41%.

This means Financial Services leadership is not the only source of edge, but it is a major contributor.

### Max 2 Positions Per Sector

| Sector | Trades | Total PnL | Net PnL Share | Avg Return | Win Rate |
| --- | ---: | ---: | ---: | ---: | ---: |
| Financial Services | 37 | 81,560.96 | 43.48% | 2.33% | 51.35% |
| Healthcare Services | 17 | 80,759.52 | 43.05% | 4.96% | 70.59% |
| Pharma | 21 | 70,678.17 | 37.68% | 3.17% | 57.14% |
| Automobile | 16 | 52,617.31 | 28.05% | 3.27% | 50.00% |
| Energy | 13 | 44,022.04 | 23.47% | 3.47% | 69.23% |
| Industrial Manufacturing | 17 | 27,808.28 | 14.83% | 1.73% | 52.94% |

The max-2 sector rule produced the best overall performance while reducing dependence on Financial Services. This is the strongest result in the analysis.

## Research Questions

### 1. Does the edge survive without Financials?

Yes, but weakly.

The no-Financials portfolio remained positive:

- CAGR: 3.02%
- Profit factor: 1.119

However, performance deteriorated materially versus baseline. The edge survives without Financial Services, but Financial Services leadership meaningfully improves the model.

### 2. Does diversification improve risk-adjusted returns?

Yes, but only with the right rule.

The best diversification rule was:

```text
Max 2 positions per sector
```

It improved:

- CAGR from 7.59% to 9.53%
- Sharpe from 0.521 to 0.609
- Profit factor from 1.253 to 1.306

Simple exposure caps did not improve risk-adjusted returns. The 30% and 20% caps reduced concentration but also reduced CAGR and Sharpe versus baseline.

### 3. Is current performance concentrated in one sector?

Partly yes.

Baseline performance is not exclusively dependent on Financial Services, but Financial Services is the largest contributor and represents a large share of net PnL.

Important distinction:

- Average Financial Services exposure: 21.09%
- Financial Services share of net PnL: 70.17%

So the concentration is more visible in realized contribution than in average portfolio weight.

### 4. Is sector concentration helping or hurting robustness?

Both.

Financial Services concentration helped baseline returns, but it creates robustness risk. Removing Financial Services weakens the model, which confirms dependency. However, limiting each sector to 2 positions improved performance and reduced single-sector dependency.

Best current interpretation:

```text
Sector concentration helped historical performance, but uncontrolled sector
crowding is not required. A max-2 positions-per-sector rule may improve robustness.
```

## Verdict

Swing V2.1 is partially dependent on Financial Services leadership.

The edge survives without Financial Services, but it is much weaker. That means Financial Services is not the only source of alpha, but it has been a major contributor in the current research window.

Best tested sector-control rule:

```text
Max 2 positions per sector
```

This rule improved CAGR, Sharpe, and profit factor while reducing Financial Services contribution share. It should be carried forward for structural validation.

## Caveats

This is research only.

Known caveats:

- No transaction costs
- No slippage
- No liquidity impact
- No point-in-time universe correction
- High survivorship-bias risk remains
- Sector constraints use current sector labels
- Sector caps are applied at entry time, not through daily forced rebalancing
- Constrained variants look through ranks up to 50, so they are not pure top-10-only portfolios
- Results cover a limited historical period

## Next Research

Recommended next steps:

1. Test max-2 positions per sector on Top 5 Weekly.
2. Add transaction costs and slippage to sector-constrained portfolios.
3. Re-run sector dependency after point-in-time universe correction.
4. Test Financial Services cap instead of full exclusion.
5. Run regime analysis to identify when Financial Services dependency appears.

