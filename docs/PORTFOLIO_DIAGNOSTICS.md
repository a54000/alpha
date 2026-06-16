# Portfolio Diagnostics

Date: 2026-06-11

## Objective

Understand why Swing V2.1 outperforms in the realistic portfolio backtest.

Model analyzed:

```text
Swing V2.1
Sector Rank + ADX
EMA200 Extension <= 25%
Prior 20d Return <= 15%
Top 10 portfolio
Weekly rebalance
Next-day open entry
20-trading-day holding period
```

Output:

- `reports/portfolio_diagnostics.json`

## Portfolio Summary

| Metric | Value |
| --- | ---: |
| Closed trades | 210 |
| Average holding period | 20.00 trading days |
| Turnover | 41.64x |
| Average position changes per rebalance | 4.67 |
| Largest average sector exposure | 21.09% |
| Largest sector | Financial Services |
| Largest single-stock exposure estimate | 10.00% |

Interpretation:

Swing V2.1 is a high-turnover monthly holding model implemented through weekly replacement. The average rebalance changes about 4 to 5 positions, which is realistic operationally but not yet cost-adjusted. Transaction costs and slippage remain material open risks.

## Sector Concentration

| Sector | Trades | Total PnL | Avg Return | Win Rate |
| --- | ---: | ---: | ---: | ---: |
| Financial Services | 50 | 104,027.66 | 2.22% | 52.00% |
| Energy | 10 | 85,537.84 | 8.95% | 90.00% |
| Automobile | 14 | 56,535.56 | 4.15% | 57.14% |
| Pharma | 26 | 44,477.01 | 1.58% | 53.85% |
| Cement & Cement Products | 10 | 35,885.28 | 3.98% | 70.00% |
| Healthcare Services | 12 | 25,119.73 | 2.10% | 66.67% |
| Industrial Manufacturing | 12 | -699.96 | -0.08% | 41.67% |
| Metals | 17 | -1,600.14 | -0.02% | 41.18% |
| Telecom | 4 | -11,550.22 | -3.08% | 25.00% |

Financial Services is the largest contributor by absolute PnL and also the largest average portfolio exposure. However, Energy contributed unusually strong returns from only 10 trades, so sector contribution is not purely proportional to trade count.

The top sector contributed about 70.17% of total net PnL. That is a concentration warning. V2.1 is not solely a one-sector model, but the realized portfolio result is meaningfully dependent on Financial Services and Energy doing well.

## Factor Contribution

Factor contribution here is bucket-based trade contribution, not isolated causal attribution. It should be read as diagnostic evidence, not as a replacement for ablation testing.

### ADX Buckets

| ADX Bucket | Trades | Total PnL | Avg Return | Win Rate |
| --- | ---: | ---: | ---: | ---: |
| 35-40 | 78 | 139,118.36 | 1.83% | 50.00% |
| 30-35 | 47 | 88,759.62 | 2.03% | 53.19% |
| 25-30 | 4 | -134.63 | -0.06% | 75.00% |
| 40+ | 81 | -79,500.61 | -0.97% | 41.98% |

This is an important finding.

ADX helps the model, but the portfolio evidence does not support a simple "higher ADX is always better" interpretation. The 30-40 ADX range drove most positive contribution. ADX above 40 was negative in this portfolio run, suggesting that extremely strong trend readings may include exhaustion or sharp downtrend/mean-reversion risk even after entry filters.

### Sector Rank Buckets

| Sector Rank Bucket | Trades | Total PnL | Avg Return | Win Rate |
| --- | ---: | ---: | ---: | ---: |
| Rank 2 | 25 | 86,184.85 | 3.59% | 60.00% |
| Rank 1 | 50 | 50,662.55 | 1.08% | 48.00% |
| Rank 3 | 26 | 46,527.38 | 1.90% | 53.85% |
| Rank 6-8 | 29 | 8,819.41 | 0.27% | 48.28% |
| Unknown | 10 | -6,013.62 | -0.60% | 50.00% |
| Rank 9+ | 26 | -11,264.29 | -0.44% | 42.31% |
| Rank 4-5 | 44 | -26,673.54 | -0.55% | 40.91% |

The strongest contribution came from sectors ranked 1-3, especially rank 2. This supports the main V2.1 design decision: sector rank is carrying meaningful portfolio-level signal. Lower-ranked sector buckets were weak or negative.

## Monthly Return Distribution

| Best Months | Return |
| --- | ---: |
| 2026-04 | 12.18% |
| 2025-03 | 10.73% |
| 2026-02 | 6.61% |
| 2025-04 | 5.54% |
| 2026-05 | 5.20% |

| Worst Months | Return |
| --- | ---: |
| 2025-02 | -10.75% |
| 2024-12 | -7.36% |
| 2026-03 | -5.34% |
| 2025-08 | -3.78% |
| 2025-01 | -3.32% |

Monthly hit rate:

```text
50.00% positive months
12 negative months
```

V2.1 performance is not smooth month to month. The full-period outperformance comes from large positive months overpowering frequent negative months.

## Rolling Returns

### Best Rolling 3-Month Windows

| Ending Month | Return |
| --- | ---: |
| 2026-06 | 17.62% |
| 2025-05 | 15.15% |
| 2026-04 | 13.65% |
| 2026-05 | 13.48% |
| 2025-12 | 6.52% |

### Worst Rolling 3-Month Windows

| Ending Month | Return |
| --- | ---: |
| 2025-02 | -18.59% |
| 2025-09 | -8.25% |
| 2025-01 | -7.92% |
| 2024-12 | -5.40% |
| 2026-03 | -4.70% |

### Best Rolling 6-Month Windows

| Ending Month | Return |
| --- | ---: |
| 2026-05 | 14.25% |
| 2026-06 | 13.87% |
| 2026-04 | 11.82% |
| 2025-08 | 10.23% |
| 2026-02 | 6.94% |

### Worst Rolling 6-Month Windows

| Ending Month | Return |
| --- | ---: |
| 2025-02 | -16.14% |
| 2025-03 | -7.65% |
| 2025-01 | -7.41% |
| 2025-05 | -5.94% |
| 2025-04 | -3.25% |

The model has meaningful bad rolling windows. The worst 3-month and 6-month windows both end in February 2025, showing drawdown clustering around that regime.

## Winners And Losers

Top winners were led by:

| Symbol | Sector | Signal Date | Return | PnL | ADX | Sector Rank |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| CAPLIPOINT | Pharma | 2024-08-12 | 25.21% | 25,059.46 | 35.39 | 1 |
| SHILPAMED | Pharma | 2026-05-04 | 24.41% | 26,781.45 | 44.12 | 6 |
| CHOLAFIN | Financial Services | 2026-04-06 | 22.46% | 22,260.23 | 45.34 | 8 |
| JKTYRE | Automobile | 2025-10-13 | 22.12% | 20,851.25 | 37.59 | 2 |
| INDUSINDBK | Financial Services | 2025-04-01 | 21.84% | 20,905.12 | 49.28 | 2 |

The full top 50 winners and top 50 losers are available in `reports/portfolio_diagnostics.json`.

The top 10 winners contributed about 137.82% of total net PnL. This does not mean only 10 trades made money; it means the largest winners more than offset the aggregate drag from losing trades. Portfolio alpha is therefore meaningfully winner-dependent.

## Diagnostic Answers

### 1. Is performance driven by a small number of trades?

Partly yes.

The top 10 winners contributed more than total net PnL because losses offset a large portion of gross gains. This is normal for trend-following style portfolios, but it means performance depends on capturing enough large winners and avoiding cost/slippage erosion.

### 2. Is performance driven by one sector?

Partly yes.

Financial Services is the largest exposure and largest PnL contributor. The sector contributed about 70.17% of net PnL. Energy also added a large contribution from fewer trades. The model is not exclusively one-sector, but sector concentration is material.

### 3. Is performance stable across time?

Moderately, not fully.

The model produced strong full-period results and strong positive rolling windows, but only 50% of months were positive. Worst rolling returns were:

- 3-month: -18.59%
- 6-month: -16.14%

Performance is regime-sensitive and drawdowns can cluster.

### 4. Is turnover realistic?

Operationally yes, cost-adjusted unknown.

Average position changes per rebalance were 4.67 for a 10-stock portfolio. This is manageable, but total turnover of 41.64x is high. The current portfolio backtest does not include brokerage, taxes, spreads, slippage, or liquidity impact, so net deployable performance is not yet proven.

### 5. Are drawdowns concentrated?

Yes.

The worst monthly and rolling-window returns cluster around late 2024 to early 2025, especially the rolling windows ending February 2025. This suggests drawdown risk is regime-specific rather than evenly distributed.

## Why Swing V2.1 Outperforms

The evidence suggests V2.1 outperforms because:

1. Sector Rank focuses the portfolio into stronger sectors.
2. ADX selects stocks with active trend behavior, but the best realized range is ADX 30-40 rather than ADX 40+.
3. Entry-quality filters reduce extended-entry damage versus earlier broad ranking models.
4. The portfolio captures several large winners with 15-25% holding-period returns.
5. The model allows enough turnover to rotate into new leadership.

The same evidence also shows the weaknesses:

1. Net returns depend heavily on large winners.
2. Sector concentration is meaningful.
3. ADX above 40 may be risky.
4. Monthly consistency is limited.
5. Cost-adjusted performance is still untested.

## Caveats

This is a research diagnostic, not a production approval.

Known limitations:

- No transaction costs
- No slippage
- No liquidity impact
- No tax or brokerage assumptions
- Current survivorship-bias concerns still apply
- Factor contribution is bucket-based, not isolated causal attribution
- Largest single-stock exposure is estimated from equal-weight portfolio design
- Sector contribution uses realized closed-trade PnL, not exact daily attribution
- Drawdown attribution is based on equity curve windows, not position-level daily factor decomposition

## Verdict

Swing V2.1 outperformance survives portfolio diagnostics, but the edge is not uniformly distributed.

Current conclusion:

```text
V2.1 outperforms because Sector Rank + moderate ADX + entry-quality controls
capture enough large winners while avoiding some weak sector/trend setups.
```

Risk conclusion:

```text
The model is winner-dependent, sector-concentrated, and high-turnover.
It requires transaction-cost, slippage, liquidity, and point-in-time universe
validation before production consideration.
```

