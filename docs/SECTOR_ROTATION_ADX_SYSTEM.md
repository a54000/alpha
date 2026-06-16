# Sector Rotation ADX - Rolling 10 Trading System
### "Follow sector strength. Enter stock momentum. Hold with discipline."

---

## What Is This System?

This is a long-only NSE equity swing trading system built around sector
rotation and stock-level momentum. It ranks sectors by rolling performance,
scores individual stocks using Swing V2.1 factors, and builds a rolling
10-slot portfolio from the highest-ranked weekly opportunities.

The system is designed for delivery-style equity trading, not intraday scalping.
Entries occur at the next trading session open after a signal. Positions are
held for a planned 20 regular trading sessions unless an experimental stop-loss
variant is explicitly tested.

---

## Core Philosophy

Market leadership often clusters by sector. Instead of looking for isolated
stock breakouts, this system first asks:

1. Which sectors are showing relative strength?
2. Which stocks inside or around those sectors have clean momentum?
3. Which candidates are not excessively extended?
4. How can capital stay deployed without overconcentrating in one signal week?

The strategy does not try to predict macro direction directly. It follows
observable sector leadership and stock-level trend strength, then uses a rolling
portfolio construction so capital is deployed across multiple weekly cohorts.

---

## Current Strategy Definition

| Component | Rule |
|-----------|------|
| Universe | Pilot exact-match Angel/NSE research universe |
| Data source | `angel_data.pilot_phase2a.daily_bars_clean` |
| Signal model | Frozen Swing V2.1 |
| Entry timing | Next trading session open after signal date |
| Exit timing | 15:15 close equivalent daily close after 20 regular sessions |
| Holding period | 20 regular trading sessions, entry day counts as day 1 |
| Portfolio construction | Rolling 10 slots |
| Weekly entries | Up to top 5 qualifying stocks per week |
| Re-entry | Same-symbol re-entry blocked while held and blocked on same exit date |
| Special sessions | Excluded from hold-day counting |
| Current preferred variant | Rolling 10 baseline, post-fix |

---

## Signal Factors

| Factor | Purpose |
|--------|---------|
| Sector rank 3m | Rewards stocks from strong 3-month sectors |
| ADX 14 | Confirms stock-level directional momentum |
| EMA200 extension | Blocks excessive upside extension |
| Prior 20-day return | Blocks excessive short-term run-up |
| Price above EMA200 | Applied in Rolling 10 research variant |

The system does not rank stocks within each sector first. Each stock receives a
global Swing V2.1 score, where sector strength is one scoring input. Final
recommendations are ranked globally.

---

## Sector Strength Calculation

For each sector, the engine calculates equal-weight average constituent returns:

```text
return_1m = average stock return over 21 trading sessions
return_3m = average stock return over 63 trading sessions
return_6m = average stock return over 126 trading sessions
```

Then:

```text
sector_score = 0.20 * return_1m
             + 0.50 * return_3m
             + 0.30 * return_6m
```

Swing V2.1 primarily uses `sector_rank_3m` for sector points:

| Sector 3m Rank | Points |
|----------------|-------:|
| 1 | 10 |
| 2 | 8 |
| 3 | 6 |
| 4-5 | 4 |
| 6-8 | 2 |
| 9+ | 0 |

Example: if SBIN belongs to `FINANCIAL SERVICES` and that sector ranks 12th by
3-month sector return, SBIN receives `0` sector strength points even if SBIN's
own stock momentum is acceptable.

---

## Performance Targets

| Metric | Minimum Threshold | Target |
|--------|------------------:|-------:|
| CAGR | > 15% | > 20% |
| Max Drawdown | better than -20% | better than -15% |
| Sharpe Ratio | > 1.0 | > 1.5 |
| Profit Factor | > 1.2 | > 1.5 |
| Win Rate | > 45% | > 52% |
| Average Hold | around 20 sessions | stable |

Any portfolio construction that falls below 15% CAGR after bias and execution
fixes should be considered failed or experimental only.

---

## Current Validated Results

Post-fix Rolling 10 baseline:

| Metric | Result |
|--------|-------:|
| CAGR | 26.38% |
| Total Return | 152.30% |
| Max Drawdown | -18.64% |
| Sharpe Ratio | 1.20 |
| Sortino Ratio | 1.52 |
| Profit Factor | 1.84 |
| Win Rate | 57.71% |
| Closed Trades | 428 |

Year-by-year post-fix returns:

| Year | Return |
|------|-------:|
| 2022 partial | 23.17% |
| 2023 | 35.93% |
| 2024 | 56.61% |
| 2025 | -4.38% |
| 2026 partial | -1.59% |

Important interpretation:

- The system remains profitable after fixing special-session hold counting.
- 2024 is the largest return contributor.
- 2025 is the main weak regime.
- Sharpe is above the minimum floor but below the desired target.

---

## Diagnostics Completed

| Diagnostic | Finding |
|------------|---------|
| Entry fill audit | Clean: next session 09:15 open matched |
| Exit fill audit | Clean bar, but day counter needed correction |
| Special-session fix | Applied: known special sessions excluded |
| Same-day re-entry fix | Applied: ALKEM overlap removed |
| 10% stop variant | Not a clear upgrade |
| Nifty regime gate | Too restrictive; blocked good 2024 trades |
| Regime gate culprit | Nifty ADX lagged sector momentum |

The Nifty ADX/SMA50/breadth gate improved 2025 but destroyed 2024 returns. A
diagnostic showed the gate blocked profitable 2024 signals, especially because
Nifty ADX lagged sector-level momentum bursts.

---

## Architecture

```text
Angel 15-min candles
        |
        v
Daily bar aggregation
        |
        v
Cleaned daily bars
        |
        v
Feature generation
        |
        v
Swing V2.1 scoring
        |
        v
Weekly ranked recommendations
        |
        v
Rolling 10-slot portfolio engine
        |
        v
Paper trading / dashboard / reports
```

---

## Technology Stack

| Component | Technology |
|-----------|------------|
| Language | Python |
| Database | PostgreSQL |
| Market data | Angel One SmartAPI / `angel_data` |
| Feature store | `pilot_phase2a.features_daily` |
| Scores | `pilot_phase2a.scores_daily` |
| Recommendations | `pilot_phase2a.recommendations_daily` |
| Backtesting | Custom Python engine |
| API | FastAPI |
| Frontend | Next.js Research Cockpit |
| Reports | CSV, JSON, Markdown |

---

## Key Data Tables

| Table | Purpose |
|-------|---------|
| `ohlcv_15min` | Raw Angel 15-minute candles |
| `pilot_phase2a.daily_bars_clean` | Cleaned daily OHLCV bars |
| `pilot_phase2a.features_daily` | EMA, ADX, sector rank, momentum features |
| `pilot_phase2a.sector_daily` | Sector return and rank series |
| `pilot_phase2a.scores_daily` | Swing V2.1 stock scores |
| `pilot_phase2a.recommendations_daily` | Ranked recommendations |
| `paper_portfolios` | Paper account metadata |
| `paper_positions` | Open/closed paper positions |
| `paper_trades` | Paper trade ledger |
| `recommendation_decision_journal` | Explainability snapshots |

---

## Documentation Index

| Document | Purpose |
|----------|---------|
| `FIVE_YEAR_VALIDATION_PILOT_PLAN.md` | Long-history validation design |
| `PHASE2E_PORTFOLIO_BACKTEST_RESULTS.md` | Five-year portfolio backtest |
| `PHASE2F_PORTFOLIO_DIAGNOSTICS.md` | Portfolio robustness diagnostics |
| `PHASE2G_WALK_FORWARD_VALIDATION.md` | Walk-forward stability review |
| `PHASE5_20_ROLLING_10_COHORT_BACKTEST_POST_FIX.md` | Post-fix Rolling 10 output |
| `PHASE5_20_ROLLING_10_YEAR_BY_YEAR_POST_FIX.md` | Year-by-year post-fix comparison |
| `PHASE5_25_ROLLING_10_REGIME_GATE_EXPERIMENT.md` | Nifty regime gate experiment |
| `PHASE5_7_SWING_V21_BEHAVIOR_FINDINGS.md` | Frozen strategy behavior notes |

---

## Repository Structure

```text
nse-research-app/
|-- app/
|   |-- api/                         # FastAPI services and dashboard endpoints
|   |-- backtesting/                 # Portfolio backtest engine
|   |-- paper_trading/               # Paper trading service
|   |-- scoring/                     # Swing V2.1 scoring functions
|-- scripts/
|   |-- run_phase2b_pilot_feature_generation.py
|   |-- run_phase2c_pilot_scoring.py
|   |-- run_phase2d_pilot_recommendations.py
|   |-- run_rolling_20_cohort_backtest.py
|   |-- run_rolling_10_regime_gate_experiment.py
|-- frontend/                        # Next.js Research Cockpit
|-- docs/                            # Strategy, audit, and implementation docs
|-- reports/                         # Backtest and pipeline artifacts
|-- results/                         # Diagnostic outputs
|-- tests/                           # Unit/API/frontend integration tests
|-- data/cache/                      # Session calendar cache
```

---

## Current Build Status

```text
Phase 1: Angel data audit and symbol mapping        Complete
Phase 2: Five-year pilot validation                 Complete
Phase 3: Paper trading engine                       Complete
Phase 4: Daily monitoring and orchestration         Complete
Phase 5: Research Cockpit                           Complete
Phase 6: Attribution and trade analysis             Active
Phase 7: Strategy refinement / walk-forward gates   Research
```

---

## Critical Constraints

1. No broker orders from this system until paper trading validation is accepted.

2. Do not change frozen Swing V2.1 scoring without creating a clearly named
   experiment variant.

3. Do not overwrite production research tables from pilot experiments.

4. Do not count special market sessions as regular holding days.

5. Entry date means fill date, not signal date.

6. Same-symbol re-entry is blocked while held and blocked on the same calendar
   date as an exit.

7. Any new filter must be tested against year-by-year behavior, not just CAGR.

8. 2024 outperformance must be treated carefully because it is the largest
   contributor to total return.

---

## Next Research Questions

1. Can a less restrictive regime gate improve 2025 without killing 2024?

2. Should Nifty ADX be replaced by sector-level ADX because index ADX lags
   sector rotation?

3. Is a soft exposure scaling model better than a hard ON/OFF regime gate?

4. Can Sharpe move above 1.3 without reducing CAGR below 20%?

5. Does the strategy remain stable under live paper trading with real daily
   Angel synchronization?
