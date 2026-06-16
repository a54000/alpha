# Sector Rotation ADX - Strategy Specification

---

## Document Purpose

This is the single source of truth for the current Sector Rotation ADX /
Rolling 10 strategy rules.

Any code that generates recommendations, sizes positions, computes planned
exits, or reconstructs historical trades must implement the rules written here.
If code and this document conflict, this document wins. Fix the code or create
a clearly named experiment variant.

This document describes the current preferred post-fix strategy. It does not
approve live trading.

---

## Performance Gate

Every production-candidate variant must clear these minimum gates:

```text
Minimum CAGR        > 15%
Minimum Sharpe      > 1.0
Minimum Profit Fact > 1.2
Maximum Drawdown    better than -20%
```

Any result below 15% CAGR after known execution and bias fixes is considered a
failed production candidate. It may remain as a research artifact, but it must
not proceed to paper/live deployment as the preferred strategy.

Target zone:

```text
CAGR                > 20%
Sharpe              > 1.3 preferred, > 1.5 ideal
Max Drawdown        better than -15% preferred
Profit Factor       > 1.5
Win Rate            > 52%
```

---

## Strategy: Sector Rotation ADX / Rolling 10

### When It Runs

The current production-candidate version runs weekly from frozen Swing V2.1
recommendations.

There is no adopted market-regime gate yet.

Research result:

```text
Nifty ADX > 20
AND Nifty close > SMA50
AND 2+ sectors positive
```

was tested and rejected as too restrictive because it blocked profitable 2024
sector-momentum signals.

Any future regime gate must be implemented as a named experiment first.

### Instruments

NSE delivery stocks, long only.

No short selling of delivery stocks is allowed. No futures or options exposure
is part of the current strategy.

### Universe

Current validated universe:

```text
Pilot exact-match Angel/NSE research universe
Source: pilot_phase2a
```

Data source:

```text
angel_data.ohlcv_15min
        |
        v
pilot_phase2a.daily_bars_clean
```

Production/paper source selection is configurable, but the current validated
research source is:

```text
PAPER_TRADING_DATA_SOURCE = pilot_phase2a
```

---

## Signal Generation

### Signal Source

Signals come from frozen Swing V2.1 scores and recommendations:

```text
pilot_phase2a.features_daily
        |
        v
pilot_phase2a.scores_daily
        |
        v
pilot_phase2a.recommendations_daily
```

Do not recalculate signals inside the portfolio engine.

### Required Stock Eligibility

A stock can be considered only if it has production-parity feature availability
and a valid Swing V2.1 score.

Current Rolling 10 research variant additionally requires:

```text
swing_v2_1_score >= 70
ema200_extension > 0
```

Interpretation:

```text
ema200_extension > 0 means price is above EMA200.
```

This condition was added after analysis showed better Top 5 behavior when long
entries are restricted to stocks trading above EMA200.

### Final Ranking

Recommendations are ranked globally, not sector-by-sector.

Sort order:

```text
1. Higher swing_v2_1_score first
2. Symbol ascending as deterministic tie-break
```

The strategy does not first select the best stock within every sector. Sector
strength is a scoring input; final ranking is cross-sectional across the full
eligible universe.

---

## Sector Strength

### Sector Return Calculation

Sector returns are equal-weight averages of constituent stock returns.

For each sector and date:

```text
return_1m = mean(close_today / close_21_sessions_ago  - 1)
return_3m = mean(close_today / close_63_sessions_ago  - 1)
return_6m = mean(close_today / close_126_sessions_ago - 1)
```

Only symbols with valid current and lookback closes are included in the average.
This is not market-cap weighted.

### Sector Score

```text
sector_score = 0.20 * return_1m
             + 0.50 * return_3m
             + 0.30 * return_6m
```

### Sector Ranks

For each date:

```text
rank_3m        = rank sectors by return_3m descending
rank_composite = rank sectors by sector_score descending
sector_rank    = rank_composite
```

Swing V2.1 uses:

```text
sector_rank_3m
```

### Sector Points

```text
sector_rank_3m == 1       -> 10 points
sector_rank_3m == 2       -> 8 points
sector_rank_3m == 3       -> 6 points
sector_rank_3m in 4, 5    -> 4 points
sector_rank_3m in 6..8    -> 2 points
sector_rank_3m >= 9       -> 0 points
missing sector rank       -> 0 points
```

Example:

```text
SBIN sector: FINANCIAL SERVICES
FINANCIAL SERVICES sector_rank_3m on 2026-06-12: 12
SBIN sector points: 0
```

---

## Swing V2.1 Scoring Inputs

The current score uses:

```text
1. sector_rank_3m
2. adx_14
3. adx_prev
4. ema200_extension
5. prior_20d_return
```

Important behavior:

```text
The model blocks excessive upside extension.
The model blocks excessive prior 20-day run-up.
The frozen model does not inherently block negative 20-day return.
The frozen model does not inherently require price above EMA200.
```

The Rolling 10 research variant adds the explicit `ema200_extension > 0` filter
before portfolio construction.

---

## Entry Rules

### Signal Date

Recommendations are generated on date `T`.

### Entry Date

Entry occurs on the next regular trading session after signal date:

```text
entry_date = next_regular_session_after(T)
```

### Entry Price

Entry fill uses:

```text
open price on entry_date
```

In 15-minute audit terms:

```text
OPEN of 09:15 bar on T+1
```

The daily bar open must match that 09:15 open.

### Entry Capacity

On each weekly entry date:

```text
Take up to top 5 recommendations.
Do not exceed 10 open positions total.
Skip symbols already held.
Skip symbols closed earlier on the same calendar date.
Skip symbols with missing or invalid entry open.
```

---

## Portfolio Construction

Current preferred structure:

```text
Rolling 10-slot portfolio
```

Rules:

```text
Max open positions        = 10
Weekly entries            = up to 5
Position allocation       = equity_at_open / 10
Rebalance frequency       = weekly signal cohort
Existing positions        = not sold because rank changes
Holding lifecycle         = hold to planned exit
```

Capital is not fully deployed immediately. The strategy builds exposure through
overlapping weekly cohorts.

Average cash can be non-zero because:

```text
1. fewer than 5 qualifying recommendations may appear,
2. some slots may already be full,
3. duplicate held symbols are skipped,
4. unavailable prices are skipped,
5. planned exits and new entries do not always align perfectly.
```

---

## Exit Rules

### Planned Exit

Every position exits after 20 regular trading sessions.

```text
entry day counts as day 1
exit_date = 20th regular session from entry_date
```

Implementation rule:

```python
exit_index = entry_index + holding_period - 1
```

### Exit Price

Exit fill uses:

```text
close price on planned_exit_date
```

In 15-minute audit terms:

```text
CLOSE of 15:15 bar on planned_exit_date
```

If an early-close/special case is introduced later, the system must explicitly
log the last available bar used. Current validated pilot bars use the normal
daily close equivalent.

### Special Sessions

Known special market sessions do not count as regular holding sessions.

Excluded sessions:

```text
2022-10-24
2023-11-12
2024-03-02
2024-05-18
2024-11-01
```

This rule exists because counting special sessions caused exits to occur late
in the original backtest.

### Re-entry

Same-symbol re-entry is allowed only after the prior position is fully closed
and not on the same calendar date as the exit.

Blocked cases:

```text
symbol currently in open positions
symbol closed earlier on current entry date
```

This prevents same-day exit/re-entry overlap.

---

## Stop Loss

Current preferred baseline:

```text
No stop loss.
```

The tested 10% stop variant is not the preferred version.

Post-fix comparison:

```text
Rolling 10 baseline CAGR        26.38%
Rolling 10 + 10% stop CAGR      22.38%
Baseline Sharpe                 1.20
10% stop Sharpe                 1.22
```

Verdict:

```text
10% stop is not a clear upgrade.
It reduces CAGR materially and does not improve drawdown enough.
```

Any stop-loss rule must remain an experiment variant unless separately
approved.

---

## Market Regime Gate

Current preferred baseline:

```text
No adopted hard market regime gate.
```

Rejected experiment:

```text
Nifty 50 ADX14 > 20
AND Nifty 50 close > SMA50
AND at least 2 sectors have positive 3-month return
```

Result:

```text
Baseline CAGR      26.38%
Regime-gated CAGR  15.67%
Baseline 2024      56.61%
Regime-gated 2024   3.36%
```

Diagnostic finding:

```text
Gate blocked profitable 2024 signals.
Primary culprit was Nifty ADX lagging sector momentum.
```

Any future regime work must be a named research experiment, likely testing:

```text
1. lower Nifty ADX threshold,
2. sector-level ADX,
3. soft exposure scaling,
4. SMA200 or confirmed-downtrend filters instead of SMA50.
```

---

## Transaction Costs

Backtests currently distinguish between gross research results and charge-aware
trade-analysis reports.

For on-demand trade analysis, Zerodha-style delivery costs are calculated as:

```text
brokerage        = 0
STT              = delivery equity rate
exchange charges = turnover-based
SEBI charges     = turnover-based
GST              = on brokerage + exchange + SEBI charges
stamp duty       = buy side
```

Production-candidate performance should always be reviewed with costs and
slippage before live deployment.

---

## Validated Post-Fix Performance

Preferred variant:

```text
Rolling 10 baseline, post special-session and same-day re-entry fixes
```

Metrics:

```text
CAGR              26.38%
Total return      152.30%
Max drawdown      -18.64%
Sharpe            1.20
Sortino           1.52
Profit factor     1.84
Win rate          57.71%
Closed trades     428
```

Year-by-year:

```text
2022 partial      23.17%
2023              35.93%
2024              56.61%
2025              -4.38%
2026 partial      -1.59%
```

Interpretation:

```text
The strategy clears CAGR and drawdown gates.
Sharpe clears the minimum but is close to the floor.
2024 is the largest return contributor.
2025 is the main weakness.
```

---

## What Is Not Allowed

```text
1. Short selling delivery stocks.
2. Changing Swing V2.1 scoring without a named experiment.
3. Changing recommendation ranking without a named experiment.
4. Counting special sessions as regular hold days.
5. Same-day same-symbol exit and re-entry.
6. Entering at signal-day close.
7. Exiting at a future/unavailable bar.
8. Copying pilot data into production tables as a shortcut.
9. Silently ignoring database or data freshness failures.
10. Proceeding to live trading without accepted paper-trading validation.
```

---

## Indicator Reference

All indicators are precomputed in the feature pipeline. Strategy and portfolio
code should consume stored values instead of recalculating ad hoc.

| Column | Meaning | Source |
|--------|---------|--------|
| `open` | Daily open from 09:15 bar | `daily_bars_clean` |
| `high` | Daily high | `daily_bars_clean` |
| `low` | Daily low | `daily_bars_clean` |
| `close` | Daily close / 15:15 close equivalent | `daily_bars_clean` |
| `volume` | Daily summed volume | `daily_bars_clean` |
| `ema_50` | 50-period EMA of close | `features_daily` |
| `ema_200` | 200-period EMA of close | `features_daily` |
| `ema200_extension` | `(close - ema_200) / ema_200` | `features_daily` |
| `prior_20d_return` | `close / close.shift(20) - 1` | `features_daily` |
| `adx_14` | Wilder-style ADX14 | `features_daily` |
| `adx_prev` | Previous ADX value | `features_daily` |
| `sector_rank_3m` | Sector rank by 3-month return | `features_daily` |
| `sector_composite_rank` | Sector rank by composite score | `features_daily` |

---

## Research Variants Registry

| Variant | Status | Verdict |
|---------|--------|---------|
| Rolling 10 baseline | Preferred | Clears gates |
| Rolling 10 + 10% stop | Tested | Not a clear upgrade |
| Nifty ADX/SMA50/breadth gate | Tested | Too restrictive |
| Weekly replacement Variant B | Research | Not preferred |
| Raw rank drops below 10 exit | Research | Not preferred |
| Threshold 60 score variant | Research | Requires caution |

New variants must be named, documented, and compared year-by-year against the
post-fix Rolling 10 baseline.
