# Backtest Execution Audit

**Date:** 2026-06-11

**Scope:** Audit recommendation backtest execution assumptions for signal timing, entry price, exit price, and look-ahead bias.

**Code reviewed:**

- `app/backtesting/run_backtest.py`
- `app/recommendations/generate_recommendations.py`
- `app/scoring/compute_scores.py`
- `app/indicators/compute_features.py`
- `tests/test_backtesting.py`

**Docs reviewed:**

- `docs/BACKTEST_SPEC.md`
- `docs/CODEX_WORKING_RULES.md`
- `docs/BACKTEST_RESULTS.md`
- `docs/V1_BASELINE.md`
- `docs/PHASE6_READINESS_REPORT.md`

---

## Executive Summary

The current recommendation backtest uses same-day close-to-future-close returns.

That means:

- signal date = recommendation date
- signal inputs include same-day EOD features and same-day close
- entry price = close on the recommendation date
- exit price = close after a fixed number of trading days
- no next-day-open execution is applied
- no stop-loss, target, rank-decay, or portfolio-level exit simulation is applied

This creates a material look-ahead/execution bias for any result interpreted as tradable live performance. The signal is generated from EOD data for date `T`, but the backtest assumes entry at the close of `T`. In real trading, that close is not available before the signal is known.

The project specification requires next-day-open execution. Therefore, existing recommendation-level backtest results should be treated as rough close-to-close research only, not execution-valid backtests.

---

## 1. Signal Generation Timestamp

### What The Code Does

The recommendation date is copied from `daily_scores.date`.

`RecommendationGenerator.generate()` loads candidates for `current_date` from `daily_scores` joined to `features_daily`:

```python
.where(DailyScores.date == current_date)
```

It then persists recommendations with:

```python
"date": current_date
```

`daily_scores` are generated from same-date `features_daily` joined to same-date `prices_daily.close`:

```python
select(FeaturesDaily, PricesDaily.close)
.join(PricesDaily, (FeaturesDaily.symbol == PricesDaily.symbol) & (FeaturesDaily.date == PricesDaily.date))
.where(FeaturesDaily.date == current_date)
```

The feature pipeline computes indicators using the close, high, low, open, and volume for that same date. Examples include:

- EMAs from same-date close
- RSI from same-date close
- MACD from same-date close
- stochastic from same-date high/low/close
- volume ratio from same-date volume
- 52-week high proximity from same-date close/high

### Interpretation

The recommendation dated `T` is an end-of-day signal for date `T`.

It should be treated as known only after all date `T` OHLCV data is available. Operationally, that means it is actionable at the earliest on the next trading session, not at the date `T` close.

### Verdict

**Signal timestamp:** EOD after close on recommendation date `T`.

**Execution implication:** Entry should be next trading day open, or another explicitly delayed execution price.

---

## 2. Entry Price Used

### What The Code Does

`BacktestRunner.run()` loads close prices only:

```python
select(PricesDaily.symbol, PricesDaily.date, PricesDaily.close)
```

For each recommendation, the entry price is:

```python
entry_price = symbol_history["prices"].get(recommendation.date)
```

Because `_load_price_history()` stores only `PricesDaily.close`, this entry price is the close on the recommendation date.

The return helper also uses the recommendation date as the entry date:

```python
trade_return = forward_trading_day_return(
    symbol_history["prices"],
    symbol_history["dates"],
    recommendation.date,
    periods,
)
```

Inside `forward_trading_day_return()`:

```python
entry_price = prices_by_date[entry_date]
```

### Verdict

**Entry price used:** same-day close on recommendation date `T`.

This conflicts with `docs/BACKTEST_SPEC.md`, which states that the signal fires EOD and entry should be next-day open.

---

## 3. Exit Price Used

### What The Code Does

The backtest uses fixed forward trading-day horizons:

Swing:

- `return_5d`
- `return_10d`
- `return_20d`

Positional:

- `return_1m` = 21 trading days
- `return_3m` = 63 trading days
- `return_6m` = 126 trading days

Exit price is selected in `forward_trading_day_return()`:

```python
exit_index = entry_index + periods_forward
exit_price = prices_by_date[sorted_dates[exit_index]]
```

Because `prices_by_date` contains close prices only, the exit price is the close on the fixed-horizon exit date.

### What Is Not Modeled

The implemented backtest does not use:

- next-day-open entry
- stop-loss exit
- target exit
- trailing stop
- rank-decay exit
- max holding exit at next-day open
- rebalance schedule
- capital allocation across active positions
- slippage, brokerage, STT, stamp duty, or market impact

### Verdict

**Exit price used:** fixed-horizon close after N trading days from recommendation date.

This is a close-to-close forward return study, not the full execution model described in `docs/BACKTEST_SPEC.md`.

---

## 4. Look-Ahead Bias Assessment

### Confirmed Bias

The current implementation has execution look-ahead bias.

Reason:

1. Features for date `T` require date `T` market data, including close and volume.
2. Scores and recommendations for date `T` are based on those features.
3. Backtest entry is also the close of date `T`.
4. A live trader cannot know the final EOD signal and also buy at that already-completed close.

This does not necessarily mean the factor calculations themselves use future data. Most technical features appear to use current and historical values only. The issue is the execution timestamp: signal availability and entry price are on the same close.

### Bias Type

| Area | Bias? | Reason |
|---|---:|---|
| Technical feature calculation | Not confirmed | Indicators use current and historical OHLCV, not future bars. |
| Signal availability | Yes for execution | Signal is EOD but treated as tradable at same close. |
| Entry price | Yes | Same-day close is used after same-day close data is needed for signal. |
| Exit price | Partial realism issue | Fixed close exits are not look-ahead if horizon is fixed, but not realistic execution. |
| Benchmark comparison | Internally comparable but not tradable | Benchmark is also close-to-close, so alpha may be internally consistent but still execution unrealistic. |

### Severity

**High for execution-valid backtests.**

Existing results should not be presented as live-tradable performance because the entry assumption is not achievable.

**Moderate for exploratory research.**

Close-to-close forward returns can still be useful for factor exploration if clearly labeled as such.

---

## 5. Specification Divergence

`docs/BACKTEST_SPEC.md` requires:

- signal fires EOD
- entry at next morning open
- stop-loss, rank-decay, max-holding, and target rules

`docs/CODEX_WORKING_RULES.md` also states that same-day close execution is invalid for backtests.

The current implementation instead uses:

- recommendation-date close entry
- fixed-horizon close exit
- no dynamic exits
- no portfolio simulation

This divergence was already noted in `docs/PHASE6_READINESS_REPORT.md` and `docs/BACKTEST_RESULTS.md`. This audit confirms it from code.

---

## 6. Tests Reviewed

`tests/test_backtesting.py` currently validates the implemented close-to-close behavior.

For example, `test_forward_return_uses_trading_day_offsets()` expects a 5-day return from price at `entry_date` to price at `entry_date + 5 trading days`.

`test_swing_backtest_persists_horizon_returns_and_metrics()` seeds recommendations on `entry_date` and expects returns calculated from that same date's close.

These tests are useful for the current implementation, but they do not enforce the project specification. There are no tests proving next-day-open entry behavior.

---

## 7. Impact On Existing Research

Affected outputs:

- `reports/backtest_validation_results.json`
- `docs/BACKTEST_RESULTS.md`
- `docs/V1_BASELINE.md`
- V2 proposal/risk docs that cite V1 backtest performance

Recommended interpretation:

- Existing recommendation backtests are close-to-close forward-return studies.
- They are not execution-valid trading backtests.
- Negative V1 results are still concerning because the biased entry assumption may have made results look better than realistic execution.
- Any V2 improvement must be validated under next-day-open execution before being trusted.

---

## Proposed Fixes

Do not implement these as part of this audit. They are proposed remediation steps only.

### 1. Make Signal And Execution Dates Explicit

For each recommendation:

- `signal_date = recommendation.date`
- `entry_date = next_trading_day_after(signal_date)`
- `entry_price = PricesDaily.open` on `entry_date`

### 2. Use Open Prices In Backtest Loader

Load at least:

- `date`
- `open`
- `high`
- `low`
- `close`

This is required for next-day-open entry and future stop/target simulation.

### 3. Add A Dedicated Execution Return Helper

Example intended behavior:

```python
entry_date = next_trading_date_after(signal_date)
entry_price = open_by_date[entry_date]
exit_date = trading_date_n_days_after(entry_date, holding_period)
exit_price = close_by_date[exit_date]
```

For a fully spec-compliant backtest, max-holding exits should also use the configured execution price, likely next-day open after the exit trigger.

### 4. Add Tests For Look-Ahead Prevention

Add tests that fail if:

- entry uses same-day close
- recommendation date and entry date are identical
- open price differs from prior close and the backtest ignores open
- insufficient next-day open data still produces a valid trade

### 5. Clearly Label Research Modes

Separate two modes:

- `close_to_close_research`: useful for quick factor/score studies
- `execution_backtest`: uses next-day-open and tradeable assumptions

Only `execution_backtest` should be used for deployment decisions.

---

## Audit Verdict

| Check | Result |
|---|---|
| Signal generation timestamp | EOD on recommendation date `T` |
| Entry price used | Same-day close on `T` |
| Exit price used | Fixed-horizon close after N trading days |
| Look-ahead bias possible | Yes, confirmed for entry execution |
| Spec compliance | Not compliant with `BACKTEST_SPEC.md` |
| Existing backtest usability | Exploratory close-to-close research only |

The current backtest should not be used as a live-trading performance estimate. Before V2 is accepted, recommendation-level results must be regenerated using next-day-open entry and clearly documented exit assumptions.
