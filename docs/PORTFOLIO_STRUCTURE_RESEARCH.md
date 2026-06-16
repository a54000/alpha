# Portfolio Structure Research

Date: 2026-06-11

## Objective

Determine the optimal portfolio construction approach for Swing V2.1.

Model under test:

```text
swing_v2_1
```

Rules held constant:

- Swing V2.1 scoring
- Next-trading-day open entry
- Close exit after 20 trading days
- Equal weighting
- No leverage
- No transaction costs
- No slippage

Output:

- `reports/portfolio_structure_results.json`

## Variants Tested

1. Top 5 / Weekly Rebalance
2. Top 10 / Weekly Rebalance
3. Top 5 / Biweekly Rebalance
4. Top 10 / Biweekly Rebalance
5. Top 5 / Monthly Rebalance
6. Top 10 / Monthly Rebalance

Implementation note:

The rebalance date uses the first available recommendation date in the selected period. Existing positions are not force-sold at rebalance; rebalance ranking fills open slots after positions exit.

## Results

| Variant | CAGR | Total Return | Max Drawdown | Sharpe | Sortino | Profit Factor | Turnover | Avg Hold | Trades |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Top 5 Weekly | 9.60% | 18.91% | -22.33% | 0.594 | 0.941 | 1.331 | 41.72x | 20.00 | 105 |
| Top 10 Weekly | 7.59% | 14.82% | -19.43% | 0.521 | 0.810 | 1.253 | 41.64x | 20.00 | 210 |
| Top 5 Biweekly | 8.52% | 16.71% | -22.19% | 0.428 | 0.491 | 1.376 | 36.04x | 20.01 | 90 |
| Top 10 Biweekly | 4.40% | 8.47% | -12.36% | 0.334 | 0.406 | 1.189 | 35.11x | 20.01 | 176 |
| Top 5 Monthly | -10.01% | -18.06% | -30.61% | -0.409 | -0.549 | 0.778 | 33.43x | 20.00 | 84 |
| Top 10 Monthly | -2.27% | -4.25% | -21.16% | -0.034 | -0.044 | 0.961 | 31.76x | 20.00 | 159 |

## Winners By Objective

| Objective | Best Variant | Value |
| --- | --- | ---: |
| Highest CAGR | Top 5 Weekly | 9.60% |
| Highest Total Return | Top 5 Weekly | 18.91% |
| Highest Sharpe | Top 5 Weekly | 0.594 |
| Highest Sortino | Top 5 Weekly | 0.941 |
| Highest Profit Factor | Top 5 Biweekly | 1.376 |
| Lowest Max Drawdown | Top 10 Biweekly | -12.36% |
| Lowest Turnover | Top 10 Monthly | 31.76x |

## Interpretation

### Concentration

Top 5 weekly outperformed Top 10 weekly:

- CAGR improved by 2.01 percentage points.
- Total return improved by 4.09 percentage points.
- Sharpe improved by 0.072.
- Profit factor improved from 1.253 to 1.331.

This supports the earlier top-bucket concentration research. Swing V2.1 behaves more like a ranking engine than a broad stock-selection engine. Concentrating into the highest-ranked recommendations improved returns and risk-adjusted performance.

Tradeoff:

Top 5 weekly also had a deeper max drawdown:

- Top 5 weekly: -22.33%
- Top 10 weekly: -19.43%

So concentration improved return quality but increased drawdown risk.

### Rebalance Frequency

Weekly rebalancing was superior for returns and Sharpe.

For Top 10:

- Weekly CAGR: 7.59%
- Biweekly CAGR: 4.40%
- Monthly CAGR: -2.27%

For Top 5:

- Weekly CAGR: 9.60%
- Biweekly CAGR: 8.52%
- Monthly CAGR: -10.01%

Monthly rebalancing was materially worse in this sample. The model appears to need frequent enough refreshes to capture changing leadership and avoid stale ranking exposure.

### Turnover

Lower rebalance frequency did reduce turnover:

- Top 10 weekly: 41.64x
- Top 10 biweekly: 35.11x
- Top 10 monthly: 31.76x

But lower turnover did not improve Sharpe or CAGR. The reduction in trade frequency came at the cost of worse selection quality.

The exception is drawdown:

Top 10 biweekly had the best max drawdown at -12.36%. This suggests slower replacement may reduce downside exposure, but it also gives up too much return.

## Research Questions

### 1. Does concentration improve returns?

Yes.

Top 5 weekly outperformed Top 10 weekly on CAGR, total return, Sharpe, Sortino, and profit factor. Concentration improved the model's ability to extract alpha from the highest-ranked V2.1 recommendations.

### 2. Does lower turnover improve risk-adjusted performance?

No, not in this test.

Biweekly and monthly variants reduced turnover, but Sharpe generally deteriorated. Lower turnover alone did not improve risk-adjusted performance because it reduced the freshness of ranking exposure.

### 3. Is monthly rebalancing superior to weekly?

No.

Monthly rebalancing was the weakest cadence. Both monthly variants produced negative total return and negative Sharpe. This is strong evidence against monthly rebalance for the current Swing V2.1 structure.

### 4. What portfolio structure maximizes Sharpe?

```text
Top 5 / Weekly Rebalance
```

Sharpe:

```text
0.594
```

### 5. What portfolio structure maximizes CAGR?

```text
Top 5 / Weekly Rebalance
```

CAGR:

```text
9.60%
```

## Recommendation

Current best research structure:

```text
Top 5 / Weekly Rebalance
```

Reason:

- highest CAGR
- highest total return
- highest Sharpe
- highest Sortino
- strong profit factor
- supports prior evidence that alpha is concentrated in the highest-ranked names

Risk-adjusted alternative:

```text
Top 10 / Biweekly Rebalance
```

Reason:

- lowest max drawdown
- lower turnover than weekly

But this alternative materially sacrifices return and Sharpe.

## Caveats

This is research only.

Important caveats:

- No transaction costs
- No slippage
- No liquidity impact
- No brokerage or tax assumptions
- No point-in-time universe correction
- Survivorship-bias risk remains
- Top 5 portfolio increases single-name concentration
- Weekly Top 5 has worse drawdown than Weekly Top 10
- Monthly underperformance may be sample-specific, but current evidence is strongly negative

## Verdict

Swing V2.1 performs best as a concentrated weekly-rebalanced portfolio.

Current conclusion:

```text
Top 5 Weekly is the leading portfolio construction candidate.
```

Production readiness:

```text
Not production-approved.
Needs transaction-cost, slippage, liquidity, and survivorship-bias validation.
```

