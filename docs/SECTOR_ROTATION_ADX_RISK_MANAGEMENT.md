# Sector Rotation ADX - Risk Management Specification

---

## Core Risk Philosophy

Risk is managed at four levels:

1. **Signal level** - only trade candidates that pass frozen Swing V2.1 and the
   Rolling 10 eligibility gates.
2. **Position level** - each position receives a fixed slot allocation.
3. **Portfolio level** - maximum open positions, cash, exposure, and sector
   concentration are monitored daily.
4. **System level** - data freshness, pipeline health, and drawdown controls
   can stop new entries.

The current preferred strategy is not a stop-loss system. It is a planned-hold
portfolio system. That makes portfolio-level and system-level risk controls
especially important.

---

## Trade-Level Risk

### Stop Loss

Current preferred baseline:

```text
No intraday stop loss.
No daily stop loss.
No early exit because rank changes.
Exit only at planned 20-session exit.
```

Reason:

```text
The 10% stop-loss variant was tested post-fix.
It produced only a tiny Sharpe improvement while reducing CAGR materially and
slightly worsening max drawdown.
```

Post-fix comparison:

```text
Rolling 10 baseline:
  CAGR          26.38%
  Max DD        -18.64%
  Sharpe        1.20

Rolling 10 + 10% stop:
  CAGR          22.38%
  Max DD        -19.24%
  Sharpe        1.22
```

Verdict:

```text
10% stop is not the preferred risk control.
It may remain as a research variant only.
```

### Planned Exit

Every position has a time-based planned exit.

```text
holding_period = 20 regular trading sessions
entry day counts as day 1
exit = close on 20th regular session
```

Special market sessions do not count as regular sessions.

Excluded sessions:

```text
2022-10-24
2023-11-12
2024-03-02
2024-05-18
2024-11-01
```

### Re-entry Risk Control

Same-symbol re-entry is blocked if:

```text
1. symbol is currently held, OR
2. symbol was closed earlier on the same calendar date
```

This prevents same-day exit/re-entry overlap and avoids impossible live trading
sequencing where a position exits at close but re-enters at the same day's open.

---

## Position-Level Risk

### Position Size Formula

The Rolling 10 portfolio uses fixed slot sizing:

```python
equity_at_open = cash + market_value(open_positions, current_open)
slot_value = equity_at_open / 10
allocation = min(slot_value, available_cash)
quantity = allocation / entry_price
```

This means each new position is intended to use roughly 10% of current portfolio
equity at entry.

### Maximum Position Size

Hard cap:

```text
single_position_target <= 10% of equity_at_open
```

Actual allocation can be lower if cash is limited.

No leverage is used.

No pyramiding is allowed.

Existing positions are not topped up or resized.

### Position Entry Conditions

A candidate is skipped if:

```text
1. portfolio already has 10 open positions,
2. symbol is already held,
3. symbol was closed earlier on the same calendar date,
4. entry open is missing or invalid,
5. available cash is zero,
6. planned exit cannot be calculated,
7. planned exit exceeds the backtest/paper-trading data window.
```

### Per-Symbol Exposure

Maximum concurrent exposure per symbol:

```text
1 open position
```

Re-entry is allowed only after the previous position has exited and at least one
new signal cycle occurs after the exit date.

---

## Portfolio-Level Risk

### Maximum Open Positions

```text
Absolute maximum: 10 open positions
Weekly additions: up to 5 positions
Portfolio construction: rolling weekly cohorts
```

The portfolio is allowed to hold fewer than 10 positions if there are not enough
eligible recommendations or if entry constraints block candidates.

### Cash and Deployment

The system does not force full deployment.

Expected reasons for cash:

```text
1. fewer than 5 qualifying recommendations in a week,
2. duplicate symbols already held,
3. insufficient available slots,
4. entry price unavailable,
5. recent exits and entries not aligned,
6. regime or future filters blocking new entries in experimental variants.
```

Current observed post-fix baseline:

```text
Average open positions: 8.17
Average cash: 18.83%
Average slot utilization: 81.68%
```

### Sector Concentration

Current baseline does not enforce a hard sector cap.

However, sector concentration must be reported in every portfolio result:

```text
top sector average weight
top 3 sectors average weight
sector exposure breakdown
```

Post-fix baseline:

```text
Top sector: Financial Services
Top sector avg weight: ~13.82%
Top 3 sectors avg weight: ~35.48%
```

Future sector caps are research variants only. They must not be added silently
to the preferred baseline.

### Portfolio Heat

Because the preferred baseline has no stop loss, classical heat based on
distance-to-stop is not defined.

For this system, heat is monitored using exposure and drawdown:

```text
gross_equity_exposure = invested_market_value / portfolio_equity
cash_pct              = cash / portfolio_equity
open_position_count   = current open positions
current_drawdown      = equity / rolling_peak - 1
```

If a future stop-loss version is adopted, heat must be redefined as:

```text
sum((entry_price - stop_price) * quantity) / equity
```

---

## Drawdown Management

### Drawdown Levels

```text
Drawdown from peak        Action
------------------------------------------------------------
< 5%                      Normal operation
5% to 10%                 Monitor; no rule change
10% to 15%                Review recent trades and sector exposure
15% to 18%                Warning zone; no new live deployment
> 18%                     Manual review before increasing capital
> 20%                     Strategy fails risk gate; stop deployment review
```

Current post-fix baseline:

```text
Max drawdown = -18.64%
```

Interpretation:

```text
The strategy passes the hard -20% risk gate but sits inside the warning zone.
It is not yet a high-confidence live deployment candidate without paper-trading
confirmation.
```

### Recovery Protocol

After drawdown exceeds 10%:

```text
1. Review last 20 closed trades.
2. Check if losses are concentrated by sector.
3. Check if losses are concentrated by year/regime.
4. Verify data freshness and recommendation quality.
5. Confirm no duplicate/re-entry/calendar errors.
6. Continue paper trading; do not increase capital allocation.
```

After drawdown exceeds 15%:

```text
1. Stop capital increase.
2. Run attribution report.
3. Review open positions by sector and age.
4. Compare current behavior to 2025 weak-regime behavior.
5. Require manual approval before any live deployment.
```

---

## Kill Switch

### Current System Mode

Current mode:

```text
Research + paper trading only
No broker orders
No live capital
```

Therefore the kill switch blocks:

```text
1. new paper entries,
2. daily pipeline continuation after critical failure,
3. dashboard status from showing false healthy state.
```

It does not send broker exit orders because broker order integration is not
implemented.

### Automatic Kill Switch Conditions

New entries should be blocked when any condition is true:

```text
1. Latest market data is stale.
2. Feature generation failed.
3. Recommendation generation failed.
4. Paper portfolio update failed.
5. More than 20% of tracked symbols missing latest daily bars.
6. Zero recommendations when historical distribution suggests abnormality.
7. Current drawdown worse than -20%.
8. Research DB or Angel DB connectivity fails.
9. Pipeline status is failed for the business date.
```

### Manual Kill Switch

Recommended environment variable:

```text
SECTOR_ADX_KILL_SWITCH=1
```

Expected behavior:

```text
No new paper entries.
Existing paper positions remain tracked.
Monitoring reports show kill switch active.
```

If live trading is ever added, this variable must block all new broker orders
immediately.

---

## Data Quality Risk Controls

New recommendations and paper updates must not proceed if:

```text
1. latest market data date is older than expected,
2. daily bars are missing for a large share of universe,
3. OHLC rows are invalid,
4. duplicate bars are detected,
5. zero-volume anomalies exceed threshold,
6. token map coverage is incomplete for tracked symbols,
7. Angel sync fails without a successful prior fresh run.
```

Daily data quality checks must include:

```text
latest 15-minute candle timestamp
latest daily bar date
latest feature date
latest score date
latest recommendation date
latest successful pipeline run
```

---

## Paper Trading Risk Rules

Paper trading must follow the same lifecycle as backtest:

```text
entry = next regular session open
exit = planned 20th regular session close
no early rank-drop exit
no stop loss in baseline
same-day re-entry blocked
special sessions excluded from hold count
```

Paper trading must report:

```text
NAV
cash
invested amount
open positions
realized PnL
unrealized PnL
current drawdown
exposure
sector concentration
turnover
recommendation count
score distribution
```

Minimum paper-trading requirement before live review:

```text
30 trading days minimum
No unresolved pipeline failures
No unexplained recommendation gaps
No data-source mismatch between dashboard and paper engine
```

---

## Margin and Leverage

### Delivery Equity

Current system uses cash equity only:

```text
Buying power = available cash
Leverage = none
Margin = none
Short selling = none
```

### Futures and Options

Not part of this strategy.

Do not add futures/options exposure to this system without a separate strategy
specification and risk model.

---

## Compliance Rules

```text
1. No short selling delivery stocks.
2. No broker API order placement in current system.
3. No live trading before accepted paper validation.
4. No hidden leverage.
5. No strategy changes without named experiment and documentation.
6. No production-table mutation from research experiments.
7. No manual data repair in raw Angel tables.
8. No ignored API/database errors.
```

Corporate-action and survivorship risk:

```text
The Angel data universe is not fully survivorship-bias corrected.
Delisted/removed stocks such as RCOM, DHFL, and PCJEWELLER were not present in
the initial dataset.
This limitation must be disclosed in all long-history validation.
```

---

## Notification Thresholds

Recommended alert levels:

```text
Event                                      Alert Type
------------------------------------------------------------
Pipeline completed successfully            INFO
New recommendations generated              INFO
Paper trades created                       INFO
No recommendations generated               WARNING
Data freshness delayed                     WARNING
Open position count below expected range   WARNING
Sector concentration unusually high        WARNING
Drawdown > 10%                             WARNING
Drawdown > 15%                             CRITICAL
Drawdown > 20%                             CRITICAL / deployment stop
Angel sync failure                         CRITICAL
Research DB failure                        CRITICAL
Paper portfolio update failure             CRITICAL
Kill switch active                         CRITICAL
```

---

## Risk Review Checklist

Before accepting any new variant:

```text
1. Does CAGR remain above 15%?
2. Does max drawdown remain better than -20%?
3. Does Sharpe remain above 1.0?
4. Is 2024 still contributing, or was the return engine destroyed?
5. Did 2025 improve without excessive cash drag?
6. Did trade count remain sufficient?
7. Are blocked trades good or bad?
8. Are costs and slippage reviewed?
9. Are data freshness and source alignment verified?
10. Are all changes documented as a named variant?
```

The current preferred baseline passes minimum gates but has risk caveats:

```text
Sharpe is close to the floor.
Max drawdown is close to the hard limit.
2024 contributes heavily to total return.
2025 behavior is weak.
```

Therefore, the strategy is suitable for continued paper validation and research,
not automatic live deployment.
