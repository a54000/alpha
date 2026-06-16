# Transaction Cost Stress Test

Date: 2026-06-12

## Objective

Determine whether Swing V2.1 remains economically viable after realistic trading costs.

Model:

```text
swing_v2_1
```

Portfolio structures:

- Top 5 Weekly
- Top 10 Weekly
- Top 10 Weekly + Max 2 Positions Per Sector

Output:

- `reports/transaction_cost_stress_test.json`

## Methodology

The existing portfolio backtest framework was used to generate gross portfolio paths and completed trades.

Cost overlay:

```text
Net trade return = gross trade return - round_trip_cost
```

Cost is applied once per completed trade using entry value and recognized on the trade exit date in the adjusted equity curve.

Cost scenarios:

| Scenario | Round-Trip Cost |
| --- | ---: |
| Baseline | 0.00% |
| Low | 0.10% |
| Moderate | 0.25% |
| High | 0.50% |
| Very High | 0.75% |
| Extreme | 1.00% |

Benchmark:

```text
NIFTY500 from index_prices_daily
2024-07-10 to 2026-06-09
Benchmark return: -3.26%
```

Alpha definition:

```text
Cost-adjusted portfolio total return - NIFTY500 total return
```

## Top 5 Weekly

| Cost | Total Return | CAGR | Sharpe | Sortino | Max Drawdown | Profit Factor | Alpha vs Nifty500 | Avg Trade Return |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0.00% | 18.91% | 9.60% | 0.594 | 0.941 | -22.33% | 1.331 | 22.18% | 0.91% |
| 0.10% | 16.83% | 8.59% | 0.540 | 0.858 | -22.68% | 1.290 | 20.09% | 0.81% |
| 0.25% | 13.71% | 7.04% | 0.460 | 0.731 | -23.22% | 1.230 | 16.97% | 0.66% |
| 0.50% | 8.51% | 4.42% | 0.326 | 0.520 | -24.13% | 1.137 | 11.77% | 0.41% |
| 0.75% | 3.31% | 1.74% | 0.195 | 0.311 | -25.54% | 1.052 | 6.57% | 0.16% |
| 1.00% | -1.89% | -1.01% | 0.067 | 0.105 | -27.19% | 0.974 | 1.37% | -0.09% |

Thresholds:

- Break-even total return cost: 0.91%
- Alpha disappears: not reached by 1.00%
- CAGR turns negative: 0.91%

## Top 10 Weekly

| Cost | Total Return | CAGR | Sharpe | Sortino | Max Drawdown | Profit Factor | Alpha vs Nifty500 | Avg Trade Return |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0.00% | 14.82% | 7.59% | 0.521 | 0.810 | -19.43% | 1.253 | 18.08% | 0.76% |
| 0.10% | 12.75% | 6.56% | 0.462 | 0.719 | -19.78% | 1.216 | 16.01% | 0.66% |
| 0.25% | 9.63% | 4.99% | 0.374 | 0.582 | -20.30% | 1.162 | 12.89% | 0.51% |
| 0.50% | 4.44% | 2.33% | 0.228 | 0.355 | -21.43% | 1.079 | 7.70% | 0.26% |
| 0.75% | -0.75% | -0.40% | 0.084 | 0.130 | -22.90% | 1.002 | 2.51% | 0.01% |
| 1.00% | -5.95% | -3.19% | -0.058 | -0.089 | -25.90% | 0.932 | -2.69% | -0.24% |

Thresholds:

- Break-even total return cost: 0.71%
- Alpha disappears: 0.87%
- CAGR turns negative: 0.71%

## Top 10 Weekly + Max 2 Positions Per Sector

| Cost | Total Return | CAGR | Sharpe | Sortino | Max Drawdown | Profit Factor | Alpha vs Nifty500 | Avg Trade Return |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0.00% | 18.76% | 9.53% | 0.609 | 0.973 | -20.85% | 1.306 | 22.02% | 0.98% |
| 0.10% | 16.61% | 8.47% | 0.551 | 0.881 | -21.42% | 1.271 | 19.87% | 0.88% |
| 0.25% | 13.38% | 6.88% | 0.464 | 0.742 | -22.28% | 1.219 | 16.64% | 0.73% |
| 0.50% | 8.01% | 4.16% | 0.320 | 0.512 | -23.70% | 1.138 | 11.27% | 0.48% |
| 0.75% | 2.63% | 1.39% | 0.178 | 0.283 | -25.14% | 1.063 | 5.89% | 0.23% |
| 1.00% | -2.74% | -1.46% | 0.038 | 0.060 | -26.58% | 0.994 | 0.52% | -0.02% |

Thresholds:

- Break-even total return cost: 0.87%
- Alpha disappears: not reached by 1.00%
- CAGR turns negative: 0.87%

## Cross-Structure Comparison

| Cost | Best Total Return | Best CAGR | Best Sharpe | Best Profit Factor |
| ---: | --- | --- | --- | --- |
| 0.00% | Top 5 Weekly | Top 5 Weekly | Top 10 + Max 2 Sector | Top 5 Weekly |
| 0.10% | Top 5 Weekly | Top 5 Weekly | Top 10 + Max 2 Sector | Top 5 Weekly |
| 0.25% | Top 5 Weekly | Top 5 Weekly | Top 10 + Max 2 Sector | Top 5 Weekly |
| 0.50% | Top 5 Weekly | Top 5 Weekly | Top 5 Weekly | Top 10 + Max 2 Sector |
| 0.75% | Top 5 Weekly | Top 5 Weekly | Top 5 Weekly | Top 10 + Max 2 Sector |
| 1.00% | Top 5 Weekly | Top 5 Weekly | Top 5 Weekly | Top 10 + Max 2 Sector |

## Research Questions

### 1. Break-even transaction cost for each portfolio

| Portfolio | Break-Even Round-Trip Cost |
| --- | ---: |
| Top 5 Weekly | 0.91% |
| Top 10 Weekly | 0.71% |
| Top 10 Weekly + Max 2 Sector | 0.87% |

Top 5 Weekly has the highest total-return break-even threshold.

### 2. Cost level where alpha disappears

| Portfolio | Alpha Disappears |
| --- | ---: |
| Top 5 Weekly | Not reached by 1.00% |
| Top 10 Weekly | 0.87% |
| Top 10 Weekly + Max 2 Sector | Not reached by 1.00% |

Important caveat:

Alpha survives longer partly because NIFTY500 return was negative over the same period. Positive alpha does not necessarily mean positive investable return.

### 3. Cost level where CAGR becomes negative

| Portfolio | Negative CAGR Threshold |
| --- | ---: |
| Top 5 Weekly | 0.91% |
| Top 10 Weekly | 0.71% |
| Top 10 Weekly + Max 2 Sector | 0.87% |

At 1.00% round-trip cost, all three structures have negative CAGR.

### 4. Which portfolio is most resilient to trading friction?

Best overall resilience:

```text
Top 5 Weekly
```

Reason:

- highest break-even cost
- strongest total return under all tested cost levels
- alpha remains positive through 1.00%

Best risk-adjusted resilience at modest costs:

```text
Top 10 Weekly + Max 2 Positions Per Sector
```

Reason:

- best Sharpe at 0.00%, 0.10%, and 0.25%
- best Sortino at modest cost levels
- alpha remains positive through 1.00%

### 5. Does Swing V2.1 remain investable after realistic Indian trading costs?

Conditionally yes.

At realistic low-to-moderate round-trip costs of 0.10% to 0.25%, Swing V2.1 remains economically viable:

- Top 5 Weekly CAGR remains 8.59% at 0.10% and 7.04% at 0.25%.
- Top 10 + Max 2 Sector CAGR remains 8.47% at 0.10% and 6.88% at 0.25%.
- Profit factors remain above 1.20 at 0.25% for Top 5 and Top 10 + Max 2 Sector.

At high costs of 0.50%, the model still produces positive CAGR, but edge is much thinner.

At 0.75% to 1.00%, investability becomes questionable or fails:

- Top 10 Weekly CAGR turns negative by 0.75%.
- Top 5 Weekly and Top 10 + Max 2 Sector turn negative by 1.00%.
- Profit factors approach or fall below 1.0.

## Verdict

Swing V2.1 survives realistic low-to-moderate transaction costs, but it is not robust to very high friction.

Current interpretation:

```text
Swing V2.1 remains economically viable if actual round-trip cost stays near
0.10%-0.25%. It becomes fragile above 0.50% and fails as an investable
strategy near 0.75%-1.00%, depending on structure.
```

Preferred structures after cost stress:

| Role | Structure |
| --- | --- |
| Return resilience | Top 5 Weekly |
| Risk-adjusted resilience | Top 10 Weekly + Max 2 Positions Per Sector |
| Least resilient | Top 10 Weekly |

## Caveats

This is research only.

Known limitations:

- Costs are applied as a simplified round-trip percentage.
- Exact trade-date brokerage, taxes, bid-ask spread, and slippage are not modeled separately.
- Cost is recognized on exit date, not split between entry and exit.
- Liquidity impact is not modeled.
- Benchmark comparison uses broad NIFTY500 over the portfolio date span, not a trade-matched benchmark portfolio.
- Survivorship-bias and point-in-time universe risks remain.
- Historical period is limited.

## Next Step

Before production consideration, replace the simplified cost overlay with a detailed Indian cost model:

- brokerage
- STT
- exchange transaction charges
- SEBI charges
- stamp duty
- GST
- bid-ask spread
- slippage by liquidity bucket

