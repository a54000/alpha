# Phase 2F Portfolio Diagnostics

Generated on: 2026-06-12

## Objective

Validate whether five-year Swing V2.1 pilot portfolio performance is structurally robust.

Inputs:

- `reports/phase2e_portfolio_metrics.json`
- `reports/phase2e_trade_ledger.csv`
- `reports/phase2e_monthly_returns.csv`
- `reports/phase2e_equity_curves.csv`

Output:

- `reports/phase2f_portfolio_diagnostics.json`

No scoring, recommendations, parameters, or filters were changed.

## Diagnostic Script

`scripts/run_phase2f_portfolio_diagnostics.py`

The script reads Phase 2E outputs only and computes:

- winner concentration
- PnL distribution
- sector PnL and exposure dependency
- portfolio-regime performance
- transaction cost sensitivity
- monthly stability and losing streaks

## Headline View

| Portfolio | Robustness Verdict | Main Strength | Main Risk |
| --- | --- | --- | --- |
| Top 5 Weekly | Strong but concentrated | Best CAGR, Sharpe, Sortino, PF | More dependent on top winners |
| Top 10 Weekly | Strongest balance | Lowest drawdown, broad trade base | Lower return than Top 5 |
| Top 10 Weekly + Max 2 Sector | Diversified but weaker | Lower sector exposure concentration | Lower return and Sharpe |

The five-year results are structurally encouraging, but not risk-free. Top 5 Weekly is the performance leader; Top 10 Weekly is the more stable production candidate.

## Winner Concentration

| Portfolio | Top 10 Winners / Net PnL | Top 20 Winners / Net PnL | Top 10 Winners / Gross Profit | Top 20 Winners / Gross Profit |
| --- | ---: | ---: | ---: | ---: |
| Top 5 Weekly | 47.21% | 78.48% | 23.18% | 38.54% |
| Top 10 Weekly | 37.61% | 62.94% | 16.59% | 27.77% |
| Top 10 Weekly + Max 2 Sector | 39.85% | 67.41% | 16.35% | 27.65% |

Top 5 Weekly is meaningfully more dependent on a small set of winners. This does not invalidate the result, but it means the portfolio needs stronger out-of-sample and transaction-cost validation before being treated as the default production structure.

Top 10 Weekly and Top 10 Weekly + Max 2 Sector are less winner-concentrated.

## PnL By Sector

### Top 5 Weekly

| Sector | PnL Share Of Net | Trades | Win Rate |
| --- | ---: | ---: | ---: |
| Industrial Manufacturing | 22.66% | 29 | 72.41% |
| Pharma | 14.79% | 18 | 66.67% |
| Energy | 14.38% | 15 | 80.00% |
| Metals | 13.35% | 17 | 58.82% |
| Healthcare Services | 9.69% | 12 | 58.33% |

### Top 10 Weekly

| Sector | PnL Share Of Net | Trades | Win Rate |
| --- | ---: | ---: | ---: |
| Energy | 25.65% | 26 | 88.46% |
| Pharma | 17.77% | 30 | 66.67% |
| Industrial Manufacturing | 13.45% | 57 | 64.91% |
| Consumer Goods | 12.58% | 50 | 60.00% |
| Automobile | 10.89% | 44 | 63.64% |

### Top 10 Weekly + Max 2 Sector

| Sector | PnL Share Of Net | Trades | Win Rate |
| --- | ---: | ---: | ---: |
| Energy | 26.56% | 28 | 78.57% |
| Industrial Manufacturing | 24.05% | 46 | 71.74% |
| Automobile | 16.31% | 40 | 67.50% |
| Healthcare Services | 13.31% | 26 | 73.08% |
| Consumer Goods | 11.80% | 48 | 56.25% |

Sector PnL is not solely dependent on Financial Services. In fact, Energy, Industrial Manufacturing, Pharma, Automobile, and Consumer Goods explain much of the realized profit.

## Exposure Concentration

| Portfolio | Top Exposure Sector | Top Sector Avg Weight | Top 3 Sector Avg Weight |
| --- | --- | ---: | ---: |
| Top 5 Weekly | Financial Services | 13.15% | 34.75% |
| Top 10 Weekly | Financial Services | 15.04% | 36.46% |
| Top 10 Weekly + Max 2 Sector | Financial Services | 11.02% | 29.88% |

The sector cap reduces exposure concentration as designed. However, it does not improve return, drawdown, Sharpe, or profit factor in the five-year pilot.

## Market Regime Performance

Regimes were classified from each portfolio's own equity curve:

- Bull: rolling 60-trading-day portfolio return above zero
- Bear: rolling 60-trading-day portfolio return below zero
- Warmup: insufficient 60-day history
- Volatility: rolling 20-day realized portfolio volatility quartiles
- Drawdown regimes: high watermark, drawdown, and drawdown below -10%

### Trend Regimes

| Portfolio | Bull Total Return | Bear Total Return | Warmup Total Return |
| --- | ---: | ---: | ---: |
| Top 5 Weekly | 171.19% | -12.89% | 12.92% |
| Top 10 Weekly | 198.78% | -23.26% | 10.65% |
| Top 10 Weekly + Max 2 Sector | 167.60% | -19.65% | 9.38% |

The portfolios are strongly pro-cyclical. Most wealth creation happens during bull portfolio regimes, while bear regimes detract.

### Volatility Regimes

| Portfolio | High Vol Return | Normal Vol Return | Low Vol Return |
| --- | ---: | ---: | ---: |
| Top 5 Weekly | 72.59% | 57.06% | -1.59% |
| Top 10 Weekly | 57.43% | 25.28% | 28.64% |
| Top 10 Weekly + Max 2 Sector | 38.68% | 41.70% | 19.68% |

Top 5 benefits most from high-volatility rebound periods. Top 10 is more balanced across volatility regimes.

### Drawdown Dates

| Portfolio | Worst Drawdown Date | Worst Drawdown |
| --- | --- | ---: |
| Top 5 Weekly | 2025-03-13 | -16.38% |
| Top 10 Weekly | 2025-03-03 | -13.83% |
| Top 10 Weekly + Max 2 Sector | 2025-03-03 | -16.31% |

Top 10 Weekly is the cleanest drawdown profile.

## Transaction Cost Sensitivity

Zerodha-style delivery assumption used for diagnostics:

- Brokerage: zero for delivery
- STT: equity delivery STT is 0.1% as documented by Zerodha support
- Additional exchange, GST, SEBI, stamp, and operational charges are approximated through a sensitivity curve rather than a single fixed claim
- Base sensitivity point: 23 bps round-trip

Official references:

- [Zerodha brokerage calculator](https://zerodha.com/brokerage-calculator/)
- [Zerodha STT explanation](https://support.zerodha.com/category/account-opening/resident-individual/ri-charges/articles/how-is-the-securities-transaction-tax-stt-calculated)

| Portfolio | Gross Total Return | Net Total Return At 23 bps | Net CAGR At 23 bps | Break-Even Round-Trip Cost |
| --- | ---: | ---: | ---: | ---: |
| Top 5 Weekly | 167.01% | 147.08% | 25.69% | 192.68 bps |
| Top 10 Weekly | 153.79% | 134.09% | 23.98% | 179.52 bps |
| Top 10 Weekly + Max 2 Sector | 136.68% | 117.16% | 21.65% | 160.99 bps |

All three structures survive realistic delivery-style friction in this approximation. Top 5 has the highest cost cushion, but also the highest concentration.

## Portfolio Stability

| Portfolio | Monthly Win Rate | Longest Monthly Losing Streak | Longest Daily Losing Streak |
| --- | ---: | ---: | ---: |
| Top 5 Weekly | 65.31% | 3 | 8 |
| Top 10 Weekly | 63.27% | 3 | 8 |
| Top 10 Weekly + Max 2 Sector | 63.27% | 3 | 10 |

Worst months:

| Portfolio | Worst Month | Return |
| --- | --- | ---: |
| Top 5 Weekly | 2025-02 | -10.97% |
| Top 10 Weekly | 2024-03 | -9.31% |
| Top 10 Weekly + Max 2 Sector | 2024-03 | -9.31% |

Top 5 has the best monthly win rate but the worst single month.

## Cross-Portfolio Comparison

Top 5 Weekly:

- Best return and Sharpe.
- Strongest cost cushion.
- Highest winner concentration.
- Worst single month.

Top 10 Weekly:

- Best drawdown profile.
- Better diversification than Top 5.
- Lower winner concentration.
- Slightly lower return than Top 5.

Top 10 Weekly + Max 2 Sector:

- Best exposure diversification.
- Lower Financial Services average weight.
- Does not improve drawdown or Sharpe versus Top 10 in this pilot.

## Structural Robustness Verdict

The five-year Swing V2.1 pilot is structurally robust enough to continue to the next validation phase, with one important distinction:

- **Top 5 Weekly is the performance leader.**
- **Top 10 Weekly is the sturdier baseline.**
- **Top 10 Weekly + Max 2 Sector is useful as a diversification sensitivity, but not the best default.**

The strongest production-candidate interpretation is:

1. Use Top 10 Weekly as the baseline portfolio structure.
2. Track Top 5 Weekly as the aggressive/high-conviction variant.
3. Keep Max 2 Sector as a risk-control sensitivity, not as the default, unless future out-of-sample results show better drawdown or Sharpe.

## Caveats

- Regime labels are portfolio-derived because Phase 2F was constrained to Phase 2E artifacts; no external NIFTY500 regime series was introduced.
- Transaction-cost estimates are sensitivity approximations, not broker contract-note simulations.
- The pilot still inherits exact-match universe constraints from the Angel data workflow.
- No point-in-time NSE500 membership reconstruction has been applied.
- No optimization or parameter tuning was performed.

## Acceptance Confirmation

- Scoring unchanged.
- Recommendations unchanged.
- No optimization.
- No new filters.
- Diagnostics generated from Phase 2E artifacts only.
