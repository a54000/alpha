# Backtest Remediation Plan

**Date:** 2026-06-11

**Objective:** Eliminate execution look-ahead bias from recommendation backtests.

**Scope:** Planning document only. No code changes are implemented here.

---

## Executive Summary

The current recommendation backtest enters trades at the signal-date close. This is not executable because the recommendation is generated from end-of-day data that includes the same close.

The required remediation is to shift execution to the next trading day's open:

- signal date: date `T`
- signal availability: after market close on `T`
- entry date: next trading day after `T`
- entry price: open on entry date

After this change, all recommendation-level performance numbers must be regenerated. Existing backtest results should remain classified as close-to-close research, not execution-valid performance.

---

## Current Behavior

Current backtest behavior:

| Item | Current Behavior |
|---|---|
| Signal date | `recommendation_history.date` |
| Signal inputs | Same-date EOD features and same-date close |
| Entry date | Same as signal date |
| Entry price | `prices_daily.close` on signal date |
| Exit date | `signal_date + N trading days` |
| Exit price | `prices_daily.close` on fixed-horizon exit date |
| Benchmark | Close-to-close from same signal date |

Problem:

The signal is known only after the close, but the backtest assumes the trade can enter at that same close. That creates execution look-ahead bias.

---

## Required Behavior

Required backtest behavior:

| Item | Required Behavior |
|---|---|
| Signal date | `recommendation_history.date` |
| Signal availability | After close on signal date |
| Entry date | Next available trading day after signal date |
| Entry price | `prices_daily.open` on entry date |
| Exit horizon start | Entry date, not signal date |
| Exit date | `entry_date + N trading days`, or strategy-specific exit date |
| Exit price | Explicitly defined by exit rule |
| Benchmark | Matched to the same entry date and exit date logic |

For the fixed-horizon research backtest, the first remediation can use:

```text
entry_date = next_trading_day_after(signal_date)
entry_price = open(entry_date)
exit_date = trading_day_n_after(entry_date, horizon)
exit_price = close(exit_date)
return = exit_price / entry_price - 1
```

This does not yet implement the full `BACKTEST_SPEC.md` portfolio simulator, but it removes the immediate same-close look-ahead bias.

---

## Required Code Changes

### 1. Recommendation Backtest

Affected area:

- `app/backtesting/run_backtest.py`

Required changes:

1. Load full OHLC data instead of close-only data.
2. Preserve a sorted trading calendar per symbol.
3. For each recommendation, find the next available trading date after `recommendation.date`.
4. Use that date as `entry_date`.
5. Use `prices_daily.open` on `entry_date` as `entry_price`.
6. Skip or mark invalid any recommendation without a next-trading-day open.
7. Store both `signal_date` and `entry_date` in trade-level results.

Current trade result fields are not sufficient because `entry_date` currently means the recommendation date. The report should distinguish:

- `signal_date`
- `entry_date`
- `entry_price`
- `exit_date`
- `exit_price`

Recommended first-stage behavior:

- Keep fixed holding horizons.
- Start horizon counting from actual entry date.
- Continue using close on exit date unless implementing full open-based exits at the same time.

---

### 2. Benchmark Comparison

Affected area:

- benchmark branch inside `BacktestRunner.run()`

Required changes:

Benchmark returns must use the same execution window as the recommendation trade.

Current benchmark behavior is close-to-close from recommendation date. Required behavior:

```text
benchmark_entry_date = trade.entry_date
benchmark_entry_price = benchmark.open(benchmark_entry_date)
benchmark_exit_date = trade.exit_date
benchmark_exit_price = benchmark.close(benchmark_exit_date)
benchmark_return = benchmark_exit_price / benchmark_entry_price - 1
```

Important rules:

1. Benchmark entry date must match stock entry date.
2. Benchmark exit date must match stock exit date for that horizon.
3. If benchmark open or close is unavailable, benchmark return should be `None`.
4. Alpha should only be calculated when both stock return and benchmark return are valid.

This keeps alpha comparable after execution timing changes.

---

### 3. Horizon Calculations

Affected areas:

- `forward_trading_day_return()`
- horizon loops in `BacktestRunner.run()`
- tests in `tests/test_backtesting.py`

Current behavior:

```text
exit_index = signal_date_index + periods_forward
```

Required behavior:

```text
entry_index = index_of(next_trading_day_after(signal_date))
exit_index = entry_index + periods_forward
```

This means a `20d` swing return becomes:

- enter at open on first trading day after signal
- exit at close 20 trading days after entry

Decision needed before implementation:

Should `20d` mean 20 trading sessions including the entry day or 20 full sessions after entry?

Recommended convention:

- `exit_index = entry_index + horizon_days`
- This measures from entry open to close after `horizon_days` completed trading-day steps.
- Keep this convention consistent for stock and benchmark.

---

### 4. Performance Metrics

Affected areas:

- `aggregate_metrics()`
- persisted `BacktestRuns.config_json`
- `reports/backtest_validation_results.json`
- docs that summarize backtest output

Required metric changes:

1. Track skipped trades separately.
2. Report counts clearly:
   - `recommendation_count`
   - `entered_count`
   - `valid_return_count`
   - `skipped_no_entry_open`
   - `skipped_no_exit_price`
3. Compute win rate using valid executed returns only.
4. Compute average return using valid executed returns only.
5. Compute alpha using matched stock and benchmark windows only.
6. Recompute profit factor using executed trade returns only.

The output should make it impossible to confuse recommendation count with valid executed trade count.

---

## Test Plan

Add tests before trusting new results:

| Test | Purpose |
|---|---|
| Entry uses next open | Fail if same-day close is used |
| Different open/close prices | Prove backtest uses open for entry |
| Missing next open | Trade is skipped or invalid |
| Horizon starts from entry date | Exit date is based on entry date, not signal date |
| Benchmark aligned to trade window | Benchmark uses same entry/exit dates |
| Alpha skips missing benchmark | No alpha from mismatched data |
| Persisted report includes signal and entry dates | Output is auditable |

Suggested fixture:

- Signal date close = 100
- Next-day open = 110
- Future close = 121

Old close-to-close return would be `21%`.

Correct next-open-to-close return would be `10%`.

This makes the bias visible in a simple unit test.

---

## Expected Impact

The direction of impact is expected to be negative versus current reported performance because same-day close entry is usually an optimistic assumption for EOD signals.

Actual magnitude must be measured after implementation and rerun.

### Win Rate

Expected impact: **decrease or remain similar**

Reason:

- Gap-ups after bullish EOD signals will raise entry price and reduce forward returns.
- Some marginal winners under close-to-close measurement may become losers after next-day-open entry.
- Gap-down entries could improve some trades, but momentum/breakout signals often suffer from buying after overnight repricing.

Estimated qualitative impact:

| Model | Expected Direction |
|---|---|
| Swing | Down |
| Positional | Slightly down to down |

Swing is likely more sensitive because shorter horizons have less time to absorb entry slippage.

### Average Return

Expected impact: **decrease**

Reason:

- Entry price moves from signal close to next-day open.
- For bullish recommendations, favorable overnight movement is no longer captured as profit.
- Opening gaps become part of entry cost rather than return.

Expected sensitivity:

| Model | Expected Sensitivity |
|---|---|
| Swing | High |
| Positional | Moderate |

Average returns are already weak in current V1 reports, so realistic execution may make them worse.

### Alpha

Expected impact: **uncertain but likely lower if recommendations gap up more than benchmark**

Reason:

- Benchmark must also shift to next-open entry, so some market-wide overnight gap effect is neutralized.
- Alpha worsens if selected stocks have stronger positive overnight gaps than the benchmark after signal generation.
- Alpha may improve if selected stocks gap down less than the benchmark, but this should not be assumed.

Expected direction:

| Case | Alpha Impact |
|---|---|
| Stocks gap up more than benchmark | Lower alpha |
| Stocks gap similar to benchmark | Similar alpha |
| Stocks gap down less than benchmark | Higher alpha |

Given the models favor momentum, breakout, and high score names, the conservative expectation is lower alpha.

### Profit Factor

Expected impact: **decrease**

Reason:

- Average winning trade size may shrink when entry moves to next-day open.
- Some small winners may become small losers.
- Gross profit likely falls faster than gross loss unless gap-down entry benefits offset it.

Expected sensitivity:

| Model | Expected Sensitivity |
|---|---|
| Swing | High |
| Positional | Moderate |

---

## Reporting Changes Required

After remediation, all backtest reports should explicitly state:

```text
Signal timing: EOD
Entry timing: next trading day open
Exit timing: fixed horizon close, unless otherwise specified
Benchmark timing: matched entry/exit window
Transaction costs: included/not included
Portfolio simulation: included/not included
```

Affected docs to regenerate or annotate:

- `docs/BACKTEST_RESULTS.md`
- `docs/V1_BASELINE.md`
- `docs/V2_RISK_REVIEW.md`
- `docs/SCORING_V2_PROPOSAL.md`
- `reports/backtest_validation_results.json`

---

## Implementation Order

Recommended sequence:

1. Add tests that describe next-day-open behavior.
2. Update backtest price loading to include OHLC.
3. Add helper to find next trading day after signal date.
4. Add execution-aware return helper.
5. Update stock return calculation.
6. Update benchmark return calculation using matched dates.
7. Update trade result output fields.
8. Update aggregate metrics count fields.
9. Rerun validation backtests.
10. Regenerate research docs.

---

## Acceptance Criteria

The remediation is complete when:

1. No recommendation trade can enter on the same date as an EOD signal.
2. Entry price is `prices_daily.open` on the next trading day.
3. Horizon exits are calculated from entry date.
4. Benchmark returns use the same entry and exit dates as each stock trade.
5. Reports expose signal date, entry date, entry price, exit date, and exit price.
6. Tests fail if same-day close entry is reintroduced.
7. V1 and V2 validation reports are regenerated under the corrected assumption.

---

## Planning Verdict

The remediation is mandatory before trusting recommendation-level performance. The current backtest is useful as a close-to-close research approximation, but it should not be used for deployment decisions.

Expected performance impact is conservative:

| Metric | Expected Direction |
|---|---|
| Win rate | Lower or similar |
| Average return | Lower |
| Alpha | Likely lower, but benchmark alignment must confirm |
| Profit factor | Lower |

Once fixed, V1 should be rebaselined and V2 should be compared only against the corrected execution-valid baseline.
