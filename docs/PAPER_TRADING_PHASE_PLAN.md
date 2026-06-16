# Paper Trading Phase Plan

Generated on: 2026-06-12

## Objective

Design the paper trading validation phase for the frozen Swing V2.1 strategy.

This is a design-only plan. It does not create tables, modify code, run migrations, connect broker APIs, or change the model.

## Frozen Strategy

Primary strategy:

- Model: `swing_v2_1`
- Portfolio: Top 5 Weekly
- Rebalance: weekly
- Entry: next trading-day open after recommendation signal
- Exit: close after 20 trading days, unless an operational rule closes the position for tracking purposes
- Weighting: equal target allocation
- Leverage: none

Secondary comparison:

- Top 10 Weekly
- Same signal, entry, exit, and accounting assumptions
- Tracked as a shadow portfolio for stability comparison only

No model changes are allowed during paper trading.

## Daily Recommendation Generation Flow

Daily EOD pipeline:

1. Ingest daily OHLCV data after market close.
2. Run existing feature generation.
3. Run existing Swing V2.1 scoring.
4. Run existing `swing_v2_1` recommendation generation.
5. Persist daily recommendations.
6. Select weekly rebalance candidates only on the first valid signal date of each week.
7. Produce next-session paper order list.

Top 5 primary selection:

- Sort recommendations by production rank.
- Select ranks 1 through 5.
- Do not add filters.
- Do not override names manually except through a documented operational blocklist for non-tradable events, if approved separately.

Top 10 shadow selection:

- Sort recommendations by production rank.
- Select ranks 1 through 10.
- Track separately from Top 5.

## Entry Date Handling

Signal date:

- The date recommendations are generated after market close.

Entry date:

- The next trading day after the signal date.
- Entry price for paper accounting should be the actual next-day open where available.
- If open price is missing, mark the order as `not_filled_data_missing`.
- If the security is halted or not tradable, mark as `not_filled_not_tradable`.

Paper fills:

- Default fill assumption: next-day open.
- Also record observed high, low, close, and VWAP if available for slippage analysis.
- Do not use same-day close as entry.

## Exit Handling

Planned exit:

- Exit at close after 20 trading days from entry.
- Use the security's trading calendar where possible.

Exit price:

- Default paper fill assumption: planned exit date close.
- If close is missing, use the next available close and mark `exit_delayed_data_missing`.

Operational exits:

- For paper trading, record but do not optimize special exits.
- If a symbol becomes untradable, suspended, delisted, or corporate-action affected, flag it for manual review and preserve the original planned exit.

## Position Tracking

Track positions independently for:

- `swing_v2_1_top5_weekly`
- `swing_v2_1_top10_weekly_shadow`

Position state machine:

| State | Meaning |
| --- | --- |
| `planned` | Recommendation selected, entry order scheduled |
| `open` | Paper entry filled |
| `closed` | Planned exit filled |
| `cancelled` | Entry not filled |
| `review` | Requires operational review |

Position fields:

- strategy
- symbol
- sector
- signal date
- recommendation rank
- recommendation score
- planned entry date
- actual entry date
- entry price
- target allocation
- paper quantity
- planned exit date
- actual exit date
- exit price
- position status
- reason codes

## Portfolio Accounting

Accounting assumptions:

- Initial paper capital should be fixed before launch.
- Recommended starting capital: 1,000,000 INR notional per strategy.
- Equal target allocation by portfolio size.
- No leverage.
- Cash earns zero interest unless benchmark policy explicitly adds cash yield later.

Top 5 allocation:

- Target position value = current portfolio equity / 5.

Top 10 allocation:

- Target position value = current portfolio equity / 10.

Weekly rebalance behavior:

- Existing open positions are not force-sold on rebalance.
- New recommendations fill only available slots.
- A duplicate symbol already held should not open a second position.
- Mature positions exit on their planned exit date.

## Realized Vs Unrealized PnL

Daily portfolio valuation should include:

- Cash
- Open position market value
- Realized PnL from closed trades
- Unrealized PnL from open positions
- Total equity

Realized PnL:

- Computed after exit fill.
- Include transaction costs in net realized PnL.

Unrealized PnL:

- Mark open positions to latest close.
- Track gross and net estimate separately.

Daily reporting:

- gross daily return
- net daily return
- realized PnL
- unrealized PnL
- cash percentage
- number of open positions
- missed fills

## Slippage Tracking

Record slippage for every paper fill:

Entry slippage:

- `entry_fill_price - reference_open`
- percentage of reference open

Exit slippage:

- `exit_fill_price - reference_close`
- percentage of reference close

For pure paper fills, initial fill price may equal reference price. Still store slippage fields so live-readiness dashboards and future broker-paper integrations can compare expected vs executable prices.

Recommended slippage diagnostics:

- average entry slippage
- average exit slippage
- worst entry slippage
- worst exit slippage
- slippage by symbol
- slippage by liquidity bucket
- slippage by gap-up/gap-down open

## Transaction Cost Tracking

Track both gross and net performance.

Cost components:

- brokerage
- STT
- exchange transaction charges
- GST
- SEBI charges
- stamp duty
- other statutory charges

Initial cost model:

- Use a Zerodha-style delivery approximation.
- Store each component separately.
- Store total round-trip cost in INR and basis points.

Required outputs:

- gross PnL
- net PnL
- total costs
- cost drag percentage
- cost drag by symbol
- cost drag by month

## Benchmark Comparison

Benchmarks:

- Primary: NIFTY 500 total return proxy where available
- Secondary: NIFTY 50
- Cash benchmark: zero-return cash

Benchmark methodology:

- Compare daily portfolio equity return vs benchmark close-to-close return.
- Track cumulative return, excess return, volatility, Sharpe, drawdown, and hit rate.
- Also compare trade-level returns against benchmark return from entry date to exit date.

Required benchmark metrics:

- portfolio total return
- benchmark total return
- alpha
- daily beta
- correlation
- tracking error
- information ratio
- max drawdown comparison

## Live Monitoring Metrics

Daily monitoring:

- recommendations generated successfully
- selected Top 5 and Top 10 names
- planned entries for next session
- positions opened
- positions closed
- missed fills
- cash balance
- gross equity
- net equity
- gross and net daily return
- drawdown
- open risk by sector
- open risk by symbol

Weekly monitoring:

- recommendation turnover
- position turnover
- realized win rate
- average trade return
- profit factor
- top contributors
- worst detractors
- sector exposure
- strategy vs benchmark

Monthly monitoring:

- monthly return
- monthly win/loss
- maximum monthly drawdown
- cost drag
- slippage summary
- deviation from backtest expectations

## Required Database Objects

Design-only proposed objects:

1. `paper_trading_run`
   - run id
   - strategy name
   - start date
   - initial capital
   - portfolio size
   - status
   - notes

2. `paper_recommendation_snapshot`
   - run id
   - signal date
   - model
   - symbol
   - rank
   - score
   - sector
   - selected flag
   - selection reason

3. `paper_orders`
   - order id
   - run id
   - symbol
   - side
   - planned date
   - reference price
   - paper fill price
   - fill status
   - slippage
   - reason code

4. `paper_positions`
   - position id
   - run id
   - symbol
   - sector
   - signal date
   - entry date
   - entry price
   - quantity
   - planned exit date
   - exit date
   - exit price
   - status

5. `paper_portfolio_daily`
   - run id
   - date
   - cash
   - market value
   - total equity
   - realized PnL
   - unrealized PnL
   - gross return
   - net return
   - drawdown

6. `paper_trade_ledger`
   - run id
   - symbol
   - entry and exit details
   - gross return
   - net return
   - costs
   - slippage
   - holding days

7. `paper_benchmark_daily`
   - date
   - benchmark
   - close
   - daily return
   - cumulative return

8. `paper_alerts`
   - alert id
   - run id
   - alert date
   - severity
   - category
   - message
   - status

## Required Scripts

Design-only proposed scripts:

1. `scripts/run_daily_swing_v21_pipeline.py`
   - existing production scoring and recommendation flow
   - no model changes

2. `scripts/generate_paper_orders.py`
   - converts selected recommendations into planned paper orders

3. `scripts/mark_paper_fills.py`
   - records next-day open fills and planned close exits

4. `scripts/update_paper_portfolio_daily.py`
   - marks open positions to market
   - updates cash, equity, PnL, and drawdown

5. `scripts/reconcile_paper_trading.py`
   - validates orders, fills, positions, and cash accounting

6. `scripts/generate_paper_trading_report.py`
   - daily, weekly, and monthly paper reports

7. `scripts/check_paper_trading_alerts.py`
   - emits operational and performance alerts

## Alert And Reporting Requirements

Operational alerts:

- recommendations not generated
- fewer than expected recommendations
- missing next-day open
- missing exit close
- duplicate open position
- cash accounting mismatch
- position exceeds target allocation tolerance
- stale price data

Risk alerts:

- drawdown exceeds 5%, 10%, or 15%
- sector exposure exceeds configured monitoring threshold
- single-name exposure exceeds target tolerance
- three consecutive losing weeks
- monthly loss exceeds backtest worst-month expectation

Performance alerts:

- rolling 20-trade win rate below 40%
- rolling profit factor below 1.0
- net alpha negative for 2 consecutive months
- slippage above expected threshold
- transaction cost drag above expected threshold

Reports:

- daily EOD paper trading report
- weekly rebalance report
- monthly performance report
- exception report
- benchmark comparison report

## Success Criteria

Minimum operational success:

- Daily pipeline completes on at least 95% of trading days.
- No unreconciled cash or position breaks remain open beyond one trading day.
- Entry and exit fills are recorded for at least 98% of planned paper orders.
- All missed fills have reason codes.

Minimum performance success:

- Top 5 Weekly remains net positive after costs.
- Top 5 Weekly does not exceed a 15% drawdown during paper trading.
- Top 5 Weekly rolling profit factor remains above 1.2 after at least 30 closed trades.
- Top 5 Weekly net alpha vs NIFTY 500 is positive over the paper period.
- Top 10 Weekly shadow does not materially outperform Top 5 on both return and drawdown at the same time.

Stability success:

- No month with unexplained operational PnL discrepancy.
- No persistent degradation in recommendation count.
- Slippage and cost drag stay within documented assumptions.

## Minimum Duration Before Capital Deployment

Minimum paper trading duration: **6 months**.

Minimum trade sample before capital deployment:

- At least 60 closed Top 5 trades.
- At least 100 closed Top 10 shadow trades.
- At least one full drawdown/recovery cycle or a documented low-volatility exception.

Preferred validation duration: **9 to 12 months**.

Capital deployment should not begin only because the calendar duration has passed. Both time and trade-count requirements should be satisfied.

## Phase Exit Decision

At the end of paper trading, produce:

- paper trading performance report
- operational reliability report
- cost and slippage report
- benchmark comparison
- recommendation stability report
- go/no-go recommendation

Decision options:

1. Proceed to limited capital deployment.
2. Extend paper trading.
3. Keep model frozen but adjust execution operations.
4. Reject live deployment pending further research.

Any model, factor, threshold, or portfolio-rule change must end the frozen paper-trading validation and start a new validation cycle.
