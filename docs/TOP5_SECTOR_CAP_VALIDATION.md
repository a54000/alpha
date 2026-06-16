# Top 5 Sector Cap Validation

Date: 2026-06-11

## Objective

Validate whether Top 5 Weekly plus a maximum of 2 positions per sector is superior to existing Swing V2.1 portfolio structures.

Model:

```text
swing_v2_1
```

Rules held constant:

- Weekly rebalance
- Next-trading-day open entry
- Close exit after 20 trading days
- Equal weighting
- No leverage
- No transaction costs
- No factor changes
- No scoring changes

Output:

- `reports/top5_sector_cap_validation.json`

Alpha definition:

```text
Variant minus Top 10 Weekly baseline
```

## Results

| Structure | CAGR | Total Return | Sharpe | Sortino | Max Drawdown | Profit Factor | Win Rate | Turnover |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Top 10 Weekly | 7.59% | 14.82% | 0.521 | 0.810 | -19.43% | 1.253 | 48.10% | 41.64x |
| Top 5 Weekly | 9.60% | 18.91% | 0.594 | 0.941 | -22.33% | 1.331 | 50.48% | 41.72x |
| Top 10 Weekly + Max 2 Per Sector | 9.53% | 18.76% | 0.609 | 0.973 | -20.85% | 1.306 | 47.62% | 41.50x |
| Top 5 Weekly + Max 2 Per Sector | 8.23% | 16.11% | 0.528 | 0.837 | -22.40% | 1.290 | 50.48% | 41.69x |

## Alpha Versus Top 10 Weekly

| Structure | CAGR Alpha | Return Alpha | Sharpe Alpha | Sortino Alpha | Drawdown Change | PF Alpha |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Top 10 Weekly | 0.00 pp | 0.00 pp | 0.000 | 0.000 | 0.00 pp | 0.000 |
| Top 5 Weekly | +2.01 pp | +4.09 pp | +0.072 | +0.131 | -2.90 pp | +0.078 |
| Top 10 Weekly + Max 2 Per Sector | +1.94 pp | +3.93 pp | +0.088 | +0.163 | -1.43 pp | +0.054 |
| Top 5 Weekly + Max 2 Per Sector | +0.64 pp | +1.29 pp | +0.006 | +0.027 | -2.97 pp | +0.038 |

## Sector Concentration

| Structure | Top Sector | Top Sector Avg Weight | Top 3 Sector Avg Weight |
| --- | --- | ---: | ---: |
| Top 10 Weekly | Financial Services | 21.09% | 42.26% |
| Top 5 Weekly | Financial Services | 18.59% | 41.12% |
| Top 10 Weekly + Max 2 Per Sector | Financial Services | 15.49% | 34.28% |
| Top 5 Weekly + Max 2 Per Sector | Financial Services | 16.06% | 37.92% |

The max-2 sector rule reduces average Financial Services exposure for both Top 10 and Top 5.

For Top 10:

- Financial Services average weight falls from 21.09% to 15.49%.
- Top 3 sector weight falls from 42.26% to 34.28%.
- Sharpe improves from 0.521 to 0.609.

For Top 5:

- Financial Services average weight falls from 18.59% to 16.06%.
- Top 3 sector weight falls from 41.12% to 37.92%.
- Sharpe falls from 0.594 to 0.528.

## Sector Contribution

### Top 5 Weekly

| Sector | Trades | Total PnL | Net PnL Share | Avg Return | Win Rate |
| --- | ---: | ---: | ---: | ---: | ---: |
| Financial Services | 22 | 177,941.43 | 94.08% | 4.27% | 63.64% |
| Energy | 4 | 71,165.45 | 37.62% | 8.98% | 100.00% |
| Pharma | 17 | 60,672.02 | 32.08% | 1.58% | 58.82% |
| Healthcare Services | 8 | 59,457.57 | 31.43% | 3.81% | 75.00% |
| Cement & Cement Products | 6 | 26,617.63 | 14.07% | 2.45% | 66.67% |

### Top 5 Weekly + Max 2 Per Sector

| Sector | Trades | Total PnL | Net PnL Share | Avg Return | Win Rate |
| --- | ---: | ---: | ---: | ---: | ---: |
| Energy | 4 | 68,700.99 | 42.64% | 8.98% | 100.00% |
| Pharma | 16 | 67,059.39 | 41.63% | 1.89% | 56.25% |
| Healthcare Services | 9 | 60,111.72 | 37.31% | 3.54% | 77.78% |
| Financial Services | 19 | 59,350.51 | 36.84% | 1.87% | 52.63% |
| Automobile | 10 | 58,976.75 | 36.61% | 2.98% | 60.00% |

The cap successfully reduces realized Financial Services dependency in Top 5. However, it also removes or replaces the highest-quality Financial Services winners that drove the uncapped Top 5 portfolio.

## Research Questions

### 1. Which portfolio structure is best overall?

Best risk-adjusted structure:

```text
Top 10 Weekly + Max 2 Per Sector
```

It has the highest Sharpe and Sortino:

- Sharpe: 0.609
- Sortino: 0.973

Best return structure:

```text
Top 5 Weekly
```

It has the highest CAGR, total return, and profit factor:

- CAGR: 9.60%
- Total return: 18.91%
- Profit factor: 1.331

### 2. Does sector capping improve risk-adjusted returns?

For Top 10, yes.

Top 10 Weekly + Max 2 Per Sector improves Sharpe from 0.521 to 0.609 and Sortino from 0.810 to 0.973.

For Top 5, no.

Top 5 Weekly + Max 2 Per Sector reduces Sharpe from 0.594 to 0.528 and CAGR from 9.60% to 8.23%.

### 3. Does sector capping reduce dependency on Financial Services?

Yes.

The cap reduces average Financial Services exposure and realized Financial Services PnL contribution. The reduction is especially meaningful for Top 5, where Financial Services net PnL share falls from 94.08% to 36.84%.

### 4. Does Top 5 + Max 2 Per Sector become the new champion portfolio?

No.

Top 5 + Max 2 Per Sector is not superior to existing structures. It is more diversified, but it underperforms uncapped Top 5 and also underperforms Top 10 + Max 2 Per Sector on Sharpe and Sortino.

## Verdict

Top 5 Weekly + Max 2 Per Sector should not become the new champion portfolio.

Updated structure view:

| Role | Structure |
| --- | --- |
| Best return candidate | Top 5 Weekly |
| Best risk-adjusted candidate | Top 10 Weekly + Max 2 Per Sector |
| Current stable baseline | Top 10 Weekly |
| Rejected as champion | Top 5 Weekly + Max 2 Per Sector |

The sector cap is valuable, but it works better with Top 10 than Top 5. The Top 5 model appears to need freedom to concentrate in the strongest names; capping it reduces the very concentration that created its return advantage.

## Caveats

This is research only.

Known caveats:

- No transaction costs
- No slippage
- No liquidity impact
- No point-in-time universe correction
- High survivorship-bias risk remains
- Sector cap is applied at entry time, not with daily forced rebalancing
- Capped variants can look through rank 50 to fill eligible slots
- Historical period is limited

## Next Step

Carry forward two candidates for further structural validation:

1. Top 5 Weekly for return maximization.
2. Top 10 Weekly + Max 2 Per Sector for risk-adjusted robustness.

Do not promote Top 5 Weekly + Max 2 Per Sector as champion.

