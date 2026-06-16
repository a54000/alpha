# Sector Rotation ADX - Backtest Specification

---

## Backtest Engine Design Principles

1. **No look-ahead bias** - signals use only data available on signal date `T`;
   entry occurs at the next regular trading session open.

2. **Execution realism** - entry and exit prices must map back to actual market
   bars. Entry is the 09:15 open equivalent; planned exit is the 15:15 close
   equivalent.

3. **Special-session handling** - known special market sessions are excluded
   from holding-period counts.

4. **Per-symbol isolation** - each symbol's position is tracked independently;
   same-symbol re-entry is blocked while held and on the same calendar date as
   an exit.

5. **Portfolio-level accounting** - cash, open positions, NAV, turnover, and
   sector exposure are tracked daily.

6. **Variant isolation** - every rule change must produce separate output
   files. Do not overwrite the accepted post-fix baseline.

7. **Research traceability** - every backtest must write metrics, equity curve,
   trade ledger, and enough metadata to reconstruct assumptions.

---

## Engine Parameters

```python
initial_capital       = 10_00_000      # Rs 10 lakh default
model                 = "swing_v2_1"
minimum_score         = 70
weekly_picks          = 5
max_open_positions    = 10
holding_period        = 20             # regular sessions, entry = day 1
ema200_gate           = "ema200_extension > 0"
stop_loss_pct         = None           # baseline has no stop
position_size         = equity_at_open / max_open_positions
```

Current preferred variant:

```text
rolling_10_post_fix
```

Current research runner:

```text
scripts/run_rolling_20_cohort_backtest.py
```

Despite the historical script name, the current preferred configuration is:

```text
--max-open-positions 10
--weekly-picks 5
```

---

## Execution Model

### Signal Date

Signals are generated from:

```text
pilot_phase2a.scores_daily
```

Eligible signal rows:

```text
date BETWEEN 2022-05-25 AND 2026-06-11
swing_v2_1_score >= 70
ema200_extension > 0
```

Within each signal date, rows are sorted:

```text
swing_v2_1_score DESC, symbol ASC
```

The top `weekly_picks` rows are considered for the weekly cohort.

### Entry

```text
Signal fires on date T.
Entry date = next regular trading session after T.
Entry price = open on entry date.
```

15-minute audit interpretation:

```text
Entry price = OPEN of 09:15 bar on T+1.
```

Skip entry if:

```text
1. portfolio already has 10 open positions,
2. symbol is already held,
3. symbol was closed earlier on the same calendar date,
4. entry open is missing or invalid,
5. insufficient cash remains,
6. planned exit cannot be computed within test window.
```

### Position Sizing

At each entry date:

```text
equity_at_open = cash + market value of open positions at open
per_position_budget = equity_at_open / max_open_positions
allocation = min(per_position_budget, cash)
shares = allocation / entry_price
```

No leverage.

No pyramiding.

No resizing of existing positions.

### Exit

Baseline exit:

```text
planned_exit_date = 20th regular session from entry date
entry date counts as day 1
exit price = close on planned_exit_date
```

Implementation:

```python
exit_index = entry_index + holding_period - 1
```

15-minute audit interpretation:

```text
Exit price = CLOSE of 15:15 bar on planned_exit_date.
```

### Exit Priority

Baseline:

```text
1. planned_exit
2. forced_final_exit at end of test window
```

10% stop experiment:

```text
1. stop_loss if daily low <= entry_price * (1 - stop_loss_pct)
2. planned_exit
3. forced_final_exit
```

If stop loss is enabled:

```text
stop price = entry_price * (1 - stop_loss_pct)
exit price = stop price
```

The stop variant is not the current preferred strategy.

---

## Trading Calendar Rules

Regular trading sessions are derived from available daily/pilot market data,
then known special sessions are removed.

Excluded special sessions:

```text
2022-10-24
2023-11-12
2024-03-02
2024-05-18
2024-11-01
```

Rules:

```text
1. Special sessions do not count toward the 20-session holding period.
2. Entry on a special session is invalid.
3. Holding-period distance is counted in regular sessions.
4. Backtest output must report holding_days as inclusive regular sessions.
```

This rule was added after audit found special sessions inflated exits by one or
more sessions.

---

## Transaction Cost Model

### Baseline Portfolio Backtest

The Rolling 10 baseline reports gross portfolio performance unless the variant
explicitly says otherwise.

Gross backtest files are used to compare signal/portfolio construction behavior
without mixing in broker-model assumptions.

### Charge-Aware Trade Analysis

On-demand trade analysis applies a Zerodha-style delivery cost model:

```python
brokerage        = 0.0
STT              = 0.1% on delivery turnover model
exchange_charges = turnover based
SEBI_charges     = turnover based
GST              = 18% on brokerage + exchange + SEBI charges
stamp_duty       = buy side
```

Important rule:

```text
Total return in charge-aware reports = profit - charges.
```

Required cost outputs:

```text
brokerage
STT
exchange_charges
GST
SEBI_charges
stamp_duty
total_charges
gross_pnl
net_pnl
net_return_pct
```

Before live deployment, every production-candidate result must be reviewed with
transaction costs and slippage.

---

## Performance Metrics Required in Every Backtest

### Trade-Level Metrics

```text
closed_trades
win_rate
average_trade_return
average_winner
average_loser
profit_factor
largest_winner
largest_loser
average_holding_period
exit_reason_breakdown
turnover
```

Required trade ledger fields:

```text
variant
symbol
sector
signal_date
entry_date
exit_date
entry_price
exit_price
shares
return
pnl
entry_value
exit_value
holding_days
rank
exit_reason
forced_final_exit
```

### Portfolio-Level Metrics

```text
initial_capital
final_equity
total_return
cagr
max_drawdown
sharpe_ratio
sortino_ratio
volatility
profit_factor
win_rate
turnover
average_open_positions
average_cash_pct
average_slot_utilization
sector_concentration
```

### Year-Level Metrics

Every production-candidate report must include:

```text
year
start_equity
end_equity
annual_return_pct
max_drawdown_pct
trade_count
win_rate
average_cash_pct
average_positions
```

Reason:

```text
The post-fix baseline is heavily driven by 2024.
Any new variant must prove it does not simply improve one weak year by killing
the primary return engine.
```

---

## Current Performance Gates

### Preferred Rolling 10 Baseline

Must pass:

```text
cagr                > 15%
max_drawdown        > -20%
sharpe_ratio        > 1.0
profit_factor       > 1.2
win_rate            > 45%
closed_trades       >= 100
```

Current post-fix result:

```text
CAGR                26.38%
Total return        152.30%
Max drawdown        -18.64%
Sharpe              1.20
Sortino             1.52
Profit factor       1.84
Win rate            57.71%
Closed trades       428
```

### Variant Acceptance

A variant is better than baseline only if it improves risk-adjusted behavior
without destroying the core return engine.

Minimum comparison requirements:

```text
1. CAGR remains above 20%, or has a clear risk-reduction justification.
2. Sharpe improves meaningfully, not by noise.
3. Max drawdown improves or stays similar.
4. 2024 return is not destroyed unless drawdown benefit is compelling.
5. 2025 weakness improves without excessive cash drag.
6. Trade count remains sufficient for inference.
```

---

## Validated Variants

| Variant | CAGR | Max DD | Sharpe | Verdict |
|---------|-----:|-------:|-------:|---------|
| Rolling 10 post-fix baseline | 26.38% | -18.64% | 1.20 | Preferred |
| Rolling 10 + 10% stop | 22.38% | -19.24% | 1.22 | Not clear upgrade |
| Nifty ADX/SMA50/breadth gate | 15.67% | -15.00% | 1.25 | Too restrictive |

Year-by-year baseline:

```text
2022 partial       23.17%
2023               35.93%
2024               56.61%
2025               -4.38%
2026 partial       -1.59%
```

---

## Backtest Variants Naming Convention

Format:

```text
{family}_{portfolio}_{change}_{version}
```

Examples:

```text
sradx_rolling10_baseline_postfix
sradx_rolling10_stop10_postfix
sradx_rolling10_regime_nifty_adx20_sma50_breadth2
sradx_rolling10_regime_nifty_adx15
sradx_rolling10_sector_adx_gate
sradx_rolling10_threshold60
sradx_rolling10_rank_drop10_exit
```

Rules:

```text
1. Never overwrite baseline output files.
2. Every experiment gets unique report names.
3. Every experiment must state what changed and what did not change.
4. Parameter sweeps must be limited and documented.
```

---

## Output Files

Recommended output layout:

```text
reports/
|-- {variant}_metrics.json
|-- {variant}_equity_curve.csv
|-- {variant}_trade_ledger.csv
|-- {variant}_weekly_deployment.csv

results/
|-- {variant}_year_by_year.csv
|-- {variant}_diagnostics.json

docs/
|-- {VARIANT_NAME}_BACKTEST_RESULTS.md
```

Current baseline artifacts:

```text
reports/phase5_20_rolling_10_cohort_backtest_post_fix.json
reports/phase5_20_rolling_10_cohort_equity_curve_post_fix.csv
reports/phase5_20_rolling_10_cohort_trade_ledger_post_fix.csv
reports/phase5_20_rolling_10_cohort_weekly_deployment_post_fix.csv
```

### `metrics.json` Minimum Schema

```json
{
  "generated_on": "YYYY-MM-DD",
  "mode": "variant_name",
  "rules": {
    "minimum_score": 70,
    "ema200_gate": "ema200_extension > 0",
    "weekly_picks": 5,
    "max_open_positions": 10,
    "holding_period": 20,
    "stop_loss_pct": null,
    "position_size": "equity_at_open / max_open_positions"
  },
  "date_range": {
    "start": "2022-05-25",
    "end": "2026-06-11"
  },
  "deployment_summary": {
    "avg_open_positions": 0,
    "max_open_positions_seen": 0,
    "avg_cash_pct": 0,
    "avg_slot_utilization": 0
  },
  "variants": {
    "rolling_10": {
      "metrics": {
        "total_return": 0,
        "cagr": 0,
        "max_drawdown": 0,
        "sharpe_ratio": 0,
        "sortino_ratio": 0,
        "profit_factor": 0,
        "win_rate": 0,
        "closed_trades": 0
      }
    }
  }
}
```

---

## Required Diagnostics Before Trusting CAGR

Every major production-candidate run must pass or document:

```text
1. Entry fill audit
   Verify signal T enters at T+1 open.

2. Exit fill audit
   Verify planned exit uses correct close on planned exit date.

3. Trading calendar audit
   Verify special sessions are not counted as regular sessions.

4. Same-symbol overlap audit
   Verify no same-day exit/re-entry overlap remains.

5. Year-by-year decomposition
   Verify no single year is the only source of the edge.

6. Transaction cost audit
   Verify costs materially affect CAGR by plausible amount.

7. Blocked-signal quality for gates
   If a gate blocks entries, verify whether blocked trades were good or bad.
```

Completed findings:

```text
Entry fills: clean.
Exit fills: correct bar.
Day counter: fixed.
Same-day overlap: fixed.
Nifty regime gate: blocked good 2024 trades.
```

---

## Anti-Patterns to Avoid

```text
1. Optimisation bias:
   Do not keep changing thresholds until 2024 looks perfect.

2. Full-sample curve fitting:
   Any promising gate must be checked year by year and walk-forward.

3. Ignoring 2025:
   Baseline weakness in 2025 is real and must be monitored.

4. Destroying 2024:
   A filter that fixes 2025 but kills 2024 is not automatically better.

5. Cost omission:
   Gross backtests are useful for signal comparison, but deployment requires
   cost-aware analysis.

6. Silent data failure:
   Empty API/database responses must not be treated as valid no-signal days.

7. Reusing stale recommendations:
   Paper and dashboard layers must point at the same configured data source.

8. Reporting only CAGR:
   Always include drawdown, Sharpe, trade count, yearly return, and cash usage.
```

---

## Reproducibility Commands

Post-fix Rolling 10 baseline:

```powershell
.\.venv\Scripts\python.exe scripts\run_rolling_20_cohort_backtest.py `
  --max-open-positions 10 `
  --weekly-picks 5 `
  --metrics-json reports/phase5_20_rolling_10_cohort_backtest_post_fix.json `
  --equity-csv reports/phase5_20_rolling_10_cohort_equity_curve_post_fix.csv `
  --trades-csv reports/phase5_20_rolling_10_cohort_trade_ledger_post_fix.csv `
  --weekly-csv reports/phase5_20_rolling_10_cohort_weekly_deployment_post_fix.csv `
  --output-md docs/PHASE5_20_ROLLING_10_COHORT_BACKTEST_POST_FIX.md
```

Post-fix 10% stop experiment:

```powershell
.\.venv\Scripts\python.exe scripts\run_rolling_20_cohort_backtest.py `
  --max-open-positions 10 `
  --weekly-picks 5 `
  --stop-loss-pct 0.10 `
  --metrics-json reports/phase5_20_rolling_10_cohort_backtest_post_fix_stop10.json `
  --equity-csv reports/phase5_20_rolling_10_cohort_equity_curve_post_fix_stop10.csv `
  --trades-csv reports/phase5_20_rolling_10_cohort_trade_ledger_post_fix_stop10.csv `
  --weekly-csv reports/phase5_20_rolling_10_cohort_weekly_deployment_post_fix_stop10.csv `
  --output-md docs/PHASE5_20_ROLLING_10_COHORT_BACKTEST_POST_FIX_STOP10.md
```

Rejected Nifty regime gate experiment:

```powershell
.\.venv\Scripts\python.exe scripts\run_rolling_10_regime_gate_experiment.py
```
