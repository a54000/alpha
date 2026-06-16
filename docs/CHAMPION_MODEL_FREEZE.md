# Champion Model Freeze

Date: 2026-06-11

## Objective

Freeze Swing V2.1 as the current champion research model before further model development.

This document is a research checkpoint. It does not approve production deployment.

## Champion Model

```text
swing_v2_1
```

Model components:

- Sector Rank
- ADX
- EMA200 Extension <= 25%
- Prior 20d Return <= 15%

Execution assumptions:

- Signal after EOD close
- Entry at next-trading-day open
- Exit at close after 20 trading days
- Equal weighting in portfolio simulations
- No leverage

## Freeze Decision

Swing V2.1 is frozen as the current champion research model.

Explicit decision:

```text
No further factor development should occur until structural validation is completed.
```

This means no new factors, factor weights, entry filters, or model variants should be added until the open structural research items are addressed.

## Portfolio Structures Under Consideration

Two structures remain under active structural validation:

| Structure | Status | Interpretation |
| --- | --- | --- |
| Top 10 Weekly | Current robust baseline | Lower concentration, lower drawdown than Top 5 |
| Top 5 Weekly | Leading return candidate | Higher CAGR and Sharpe, but less robust and more concentrated |

Top 10 Weekly remains the safer research baseline. Top 5 Weekly is the leading candidate for concentrated alpha extraction, but it is not yet structurally approved.

## Trade-Level Results

Primary 20-day recommendation-level backtest:

| Model | Trade Count | Valid Count | Avg Return | Win Rate | Profit Factor | Alpha |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| V1 Swing | 2,045 | 1,911 | -0.5329% | 43.43% | 0.8850 | -0.1948% |
| Swing V2 | 7,189 | 6,870 | -0.0987% | 46.83% | 0.9767 | 0.1762% |
| Swing V2.1 | 7,241 | 7,056 | 0.4244% | 50.77% | 1.1283 | 0.4107% |

Trade-level conclusion:

Swing V2.1 improved average return, win rate, profit factor, and benchmark-relative alpha versus both V1 Swing and Swing V2.

## Portfolio-Level Results

Top 10 Weekly portfolio comparison:

| Model | Total Return | CAGR | Max Drawdown | Sharpe | Sortino | Profit Factor |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| V1 Swing | 5.89% | 3.07% | -28.89% | 0.284 | 0.371 | 1.127 |
| Swing V2 | 8.91% | 4.61% | -17.34% | 0.343 | 0.456 | 1.138 |
| Swing V2.1 | 14.82% | 7.59% | -19.43% | 0.521 | 0.810 | 1.253 |

Portfolio-level conclusion:

Swing V2.1 survives portfolio construction and remains the strongest implemented Swing research model by CAGR, total return, Sharpe, Sortino, and profit factor.

Main caveat:

Swing V2.1 does not have the lowest drawdown. Swing V2 had lower max drawdown in the Top 10 Weekly portfolio test.

## Portfolio Structure Results

Swing V2.1 structure comparison:

| Variant | CAGR | Total Return | Max Drawdown | Sharpe | Sortino | Profit Factor | Turnover |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Top 5 Weekly | 9.60% | 18.91% | -22.33% | 0.594 | 0.941 | 1.331 | 41.72x |
| Top 10 Weekly | 7.59% | 14.82% | -19.43% | 0.521 | 0.810 | 1.253 | 41.64x |
| Top 5 Biweekly | 8.52% | 16.71% | -22.19% | 0.428 | 0.491 | 1.376 | 36.04x |
| Top 10 Biweekly | 4.40% | 8.47% | -12.36% | 0.334 | 0.406 | 1.189 | 35.11x |
| Top 5 Monthly | -10.01% | -18.06% | -30.61% | -0.409 | -0.549 | 0.778 | 33.43x |
| Top 10 Monthly | -2.27% | -4.25% | -21.16% | -0.034 | -0.044 | 0.961 | 31.76x |

Structure conclusion:

Top 5 Weekly maximized CAGR, total return, Sharpe, and Sortino. Top 10 Biweekly minimized drawdown but sacrificed too much return. Monthly rebalancing was not supported by current evidence.

## Time-Split Validation

Top 5 Weekly versus Top 10 Weekly:

| Period | Dates | Top 10 CAGR | Top 5 CAGR | Top 5 CAGR Alpha | Interpretation |
| --- | --- | ---: | ---: | ---: | --- |
| First third | 2024-07-10 to 2025-02-21 | -15.53% | -18.03% | -2.50 pp | Top 5 underperformed |
| Middle third | 2025-02-24 to 2025-10-15 | 7.59% | 14.67% | +7.08 pp | Top 5 outperformed |
| Final third | 2025-10-16 to 2026-06-09 | 36.80% | 40.54% | +3.74 pp | Top 5 outperformed |

Time-split conclusion:

Top 5 Weekly is not consistently superior across all periods. It underperformed in the first third and then outperformed in the middle and final thirds. This makes Top 5 a promising candidate, not a fully validated structure.

## Robustness Validation

Rolling window validation:

| Window | Count | Top 5 Positive Alpha Windows | Hit Rate | Best CAGR Alpha | Worst CAGR Alpha |
| --- | ---: | ---: | ---: | ---: | ---: |
| Rolling 6-month | 18 | 11 | 61.11% | +13.54 pp | -9.72 pp |
| Rolling 12-month | 12 | 10 | 83.33% | +9.58 pp | -1.77 pp |

Robustness conclusion:

Top 5 Weekly is stronger over 12-month windows than 6-month windows. Shorter-window robustness is moderate and not conclusive.

Transaction-cost sensitivity:

| Cost / Traded Notional | Top 10 Net CAGR | Top 5 Net CAGR | Top 5 Net CAGR Alpha |
| --- | ---: | ---: | ---: |
| 0 bps | 7.59% | 9.60% | +2.01 pp |
| 10 bps | 5.51% | 7.55% | +2.04 pp |
| 25 bps | 2.31% | 4.41% | +2.09 pp |
| 50 bps | -3.22% | -1.03% | +2.19 pp |

Cost conclusion:

Top 5 retains relative alpha versus Top 10 under approximate cost assumptions, but absolute performance deteriorates quickly. At 50 bps per traded notional, both Top 5 and Top 10 become negative.

## Known Risks

### Survivorship Bias

Risk level: High.

The system may be using current or surviving universe membership rather than fully point-in-time historical NSE500 membership. If delisted or excluded historical stocks are missing, factor research, recommendations, and portfolio backtests may overstate performance.

### Financial Sector Concentration

Risk level: High.

Financial Services is the largest contributor in both Top 10 and Top 5 portfolio diagnostics. Top 5 Weekly is especially dependent on Financial Services realized PnL:

- Top 5 Financial Services PnL share of net PnL: 94.08%
- Top 10 Financial Services PnL share of net PnL: 70.17%

This creates sector dependency risk. The model may be partly capturing a Financial Services regime rather than broad stock-selection skill.

### Transaction Costs

Risk level: High.

Current backtests exclude:

- brokerage
- STT
- stamp duty
- exchange charges
- bid-ask spread
- slippage
- liquidity impact

Turnover is high, around 41x in the weekly portfolio tests. Cost-adjusted returns must be validated before any production decision.

### Limited Historical Period

Risk level: High.

The implemented research window is approximately July 2024 through June 2026. This is too short to fully validate performance across market cycles, liquidity regimes, sector rotations, and bear-market stress.

## Open Research

No additional factor development should begin until the following structural validation items are completed.

1. Historical NSE500 membership

Validate the universe using date-valid membership. Confirm whether historical excluded, removed, or delisted stocks are represented. Re-run factor, recommendation, and portfolio tests on point-in-time membership.

2. Sector dependency analysis

Quantify whether Swing V2.1 alpha survives with:

- Financial Services capped
- Financial Services excluded
- sector-neutral ranking
- max sector exposure rules
- sector contribution by regime

3. Cost-adjusted performance

Add realistic cost assumptions:

- brokerage
- STT
- stamp duty
- exchange charges
- spread
- slippage
- liquidity filters

Then re-run Top 10 Weekly and Top 5 Weekly portfolio simulations.

4. Regime analysis

Evaluate performance by market regime:

- rising market
- falling market
- sideways market
- high volatility
- low volatility
- sector rotation
- drawdown recovery

The first-third underperformance of Top 5 Weekly must be understood before final structure approval.

## Freeze Rules

Until structural validation is completed:

- Do not add new Swing factors.
- Do not tune Swing factor weights.
- Do not add new entry filters.
- Do not create V2.2 or V3 factor variants.
- Do not optimize thresholds further.
- Do not treat Top 5 Weekly as production-approved.

Allowed work:

- point-in-time universe validation
- sector dependency testing
- cost and slippage simulation
- liquidity constraints
- regime analysis
- portfolio structure validation
- drawdown attribution

## Final Status

Champion research model:

```text
Swing V2.1
Sector Rank + ADX
EMA200 Extension <= 25%
Prior 20d Return <= 15%
```

Champion baseline structure:

```text
Top 10 Weekly
```

Leading concentrated structure:

```text
Top 5 Weekly
```

Final freeze statement:

```text
Swing V2.1 is frozen as the current champion research model.
No further factor development should occur until structural validation is completed.
The next research phase must focus on survivorship bias, sector dependency,
transaction costs, and regime robustness.
```

