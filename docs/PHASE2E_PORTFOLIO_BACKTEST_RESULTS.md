# Phase 2E Portfolio Backtest Results

Generated on: 2026-06-12

## Objective

Evaluate Swing V2.1 pilot portfolio performance from 2022-05-25 to 2026-06-11 using:

- `angel_data.pilot_phase2a.recommendations_daily`
- `angel_data.pilot_phase2a.daily_bars_clean`

This phase did not change scoring, recommendations, factors, thresholds, or production tables.

## Implemented Script

`scripts/run_phase2e_pilot_portfolio_backtest.py`

Outputs:

- `reports/phase2e_portfolio_metrics.json`
- `reports/phase2e_equity_curves.csv`
- `reports/phase2e_trade_ledger.csv`
- `reports/phase2e_monthly_returns.csv`

## Portfolio Assumptions

The pilot uses the previous portfolio backtest methodology:

- Signals: EOD recommendations
- Entry: next trading-day open
- Exit: close after 20 trading days
- Rebalance: weekly, first available signal date per ISO week
- Sizing: equal target allocation
- Initial capital: 1,000,000
- Leverage: none
- Transaction costs: not included
- Open positions at the final date: liquidated at final close for trade statistics

Sector-cap variant:

- Maximum 2 open positions per sector
- Candidate ranks considered up to 50

## Variants Tested

| Variant | Portfolio size | Sector constraint |
| --- | ---: | --- |
| `top5_weekly` | 5 | None |
| `top10_weekly` | 10 | None |
| `top10_weekly_max2_sector` | 10 | Max 2 open positions per sector |

## Input Coverage

| Input | Count |
| --- | ---: |
| Recommendation rows | 13,654 |
| Symbols in recommendations | 282 |
| Backtest start | 2022-05-25 |
| Backtest end | 2026-06-11 |

Equity curves contain 997 rows per variant.

## Headline Results

| Variant | Total Return | CAGR | Max Drawdown | Sharpe | Sortino | Profit Factor | Win Rate | Turnover | Trades |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Top 5 Weekly | 167.01% | 28.18% | -16.38% | 1.502 | 2.371 | 2.073 | 61.01% | 86.68x | 218 |
| Top 10 Weekly | 153.79% | 26.54% | -13.83% | 1.251 | 1.628 | 1.994 | 58.70% | 85.67x | 431 |
| Top 10 Weekly + Max 2 Sector | 136.68% | 24.33% | -16.31% | 1.189 | 1.621 | 1.859 | 56.78% | 84.90x | 428 |

## Interpretation

Top 5 Weekly is strongest on:

- CAGR
- total return
- Sharpe
- Sortino
- profit factor
- win rate

Top 10 Weekly is strongest on drawdown:

- Max drawdown: -13.83%

Top 10 Weekly + Max 2 Sector reduces Financial Services concentration but does not improve headline risk-adjusted performance in the pilot.

## Sector Concentration

| Variant | Top sector | Top sector avg weight | Top 3 sector avg weight |
| --- | --- | ---: | ---: |
| Top 5 Weekly | Financial Services | 13.15% | 34.75% |
| Top 10 Weekly | Financial Services | 15.04% | 36.46% |
| Top 10 Weekly + Max 2 Sector | Financial Services | 11.02% | 29.88% |

The sector cap works mechanically: it lowers top-sector and top-three-sector average exposure. In this pilot, that diversification comes with lower CAGR and Sharpe.

## Monthly Return Summary

| Variant | Months measured | Positive months | Best month | Worst month |
| --- | ---: | ---: | ---: | ---: |
| Top 5 Weekly | 49 | 32 | 17.10% | -10.97% |
| Top 10 Weekly | 49 | 31 | 18.40% | -9.31% |
| Top 10 Weekly + Max 2 Sector | 49 | 31 | 18.10% | -9.31% |

Monthly return details are in `reports/phase2e_monthly_returns.csv`.

## Existing 2-Year V2.1 Comparison

The comparison uses existing reports:

- `reports/portfolio_structure_results.json`
- `reports/top5_sector_cap_validation.json`

| Variant | Existing 2Y CAGR | Pilot 5Y CAGR | Delta | Existing Sharpe | Pilot Sharpe | Delta |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Top 5 Weekly | 9.60% | 28.18% | +18.57 pp | 0.594 | 1.502 | +0.909 |
| Top 10 Weekly | 7.59% | 26.54% | +18.95 pp | 0.521 | 1.251 | +0.729 |
| Top 10 Weekly + Max 2 Sector | 9.53% | 24.33% | +14.80 pp | 0.609 | 1.189 | +0.580 |

Drawdown comparison:

| Variant | Existing 2Y Max DD | Pilot 5Y Max DD | Change |
| --- | ---: | ---: | ---: |
| Top 5 Weekly | -22.33% | -16.38% | +5.95 pp |
| Top 10 Weekly | -19.43% | -13.83% | +5.60 pp |
| Top 10 Weekly + Max 2 Sector | -20.85% | -16.31% | +4.54 pp |

The five-year pilot outperforms the existing two-year results materially across return and risk-adjusted metrics. This is a strong validation signal, but it should still be interpreted with the known pilot-universe constraints.

## Caveats

- Transaction costs and slippage are not included.
- The pilot universe is exact-match Angel coverage, not a fully reconstructed point-in-time NSE500 membership history.
- Results may still contain survivorship or universe-selection bias.
- Corporate-action lineage is not fully normalized.
- No optimization was performed; these are fixed production-style portfolio structures.

## Verification

Compile check:

```powershell
.\.venv\Scripts\python.exe -m py_compile scripts/run_phase2e_pilot_portfolio_backtest.py
```

Backtest run:

```powershell
.\.venv\Scripts\python.exe scripts/run_phase2e_pilot_portfolio_backtest.py
```

Generated files:

| File | Purpose |
| --- | --- |
| `reports/phase2e_portfolio_metrics.json` | Metrics, assumptions, and 2Y comparison |
| `reports/phase2e_equity_curves.csv` | Daily equity curve by variant |
| `reports/phase2e_trade_ledger.csv` | Closed trade ledger by variant |
| `reports/phase2e_monthly_returns.csv` | Month-end returns by variant |

Output integrity:

- Equity rows: 2,991 total, 997 per variant
- Trade rows: 1,077 total
- Trade rows by variant:
  - Top 5 Weekly: 218
  - Top 10 Weekly: 431
  - Top 10 Weekly + Max 2 Sector: 428

## Acceptance Confirmation

- No scoring changes.
- No recommendation changes.
- No production table changes.
- No tuning or optimization.
- No new filters introduced.
- Portfolio assumptions documented.

Phase 2E is complete.
