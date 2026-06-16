# Phase 5.5 Paper Portfolio Initialization

Date: 2026-06-12

Scope: initialize the first paper trading portfolio using existing paper trading infrastructure. No scoring, recommendation generation, strategy rules, broker integration, order placement, or trading logic were changed.

## Objective

Create the first active paper portfolio row so the Swing Research Cockpit can resolve the configured `PAPER_PORTFOLIO_ID` and report healthy paper portfolio status.

## Existing Infrastructure Reviewed

Files reviewed:

- `app/paper_trading/service.py`
- `db/models.py`
- `tests/test_paper_trading_service.py`

Existing service:

- `PaperTradingService.initialize_portfolio(...)`
- `PaperTradingConfig`

Tables used:

- `paper_portfolios`
- `paper_positions`
- `paper_trades`
- `paper_daily_snapshots`

The service already supports creating a portfolio shell with initial capital, cash, NAV, strategy, benchmark, and status. It did not include duplicate prevention, so the new script adds idempotency around the service.

## Script Added

```text
scripts/initialize_paper_portfolio.py
```

The script:

- loads `.env` through existing DB helpers
- reads `DATABASE_URL`
- reads configured `PAPER_PORTFOLIO_ID`
- checks whether that portfolio already exists
- checks for an active portfolio with the same name and strategy
- creates a portfolio only if no matching portfolio exists
- prints created or reused portfolio id

Default configuration:

| Field | Value |
| --- | --- |
| Name | `Swing V2.1 Rolling 10 Slot Paper` |
| Strategy | `swing_v2_1_rolling_10_slot` |
| Portfolio size | `10` |
| Initial capital | `1000000.0` |
| Benchmark | `NIFTY500` |
| Lifecycle mode | `hold_to_planned_exit` |
| Status | `active` |

## Required Environment Variables

```text
DATABASE_URL
ANGEL_DATABASE_URL
PAPER_PORTFOLIO_ID
```

For initialization, `DATABASE_URL` must point to the research database:

```text
nse_research_platform
```

`PAPER_PORTFOLIO_ID` should match the portfolio id intended for the cockpit. In this run:

```text
PAPER_PORTFOLIO_ID=1
```

## Initialization Command

```powershell
.\.venv\Scripts\python.exe scripts\initialize_paper_portfolio.py
```

Initial run result:

```text
created portfolio_id=1
name=Swing V2.1 Rolling 10 Slot Paper
strategy=swing_v2_1_rolling_10_slot
initial_capital=1000000.0
benchmark_symbol=NIFTY500
lifecycle_mode=hold_to_planned_exit
```

Rerun result:

```text
reused portfolio_id=1 reason=configured_id
name=Swing V2.1 Rolling 10 Slot Paper
strategy=swing_v2_1_rolling_10_slot
cash=1000000.00
current_nav=1000000.00
```

## Rerun Behavior

The script is idempotent.

Rerun order:

1. If `--portfolio-id` is provided, reuse that portfolio if it exists.
2. Otherwise, if `PAPER_PORTFOLIO_ID` exists in the environment, reuse that portfolio if it exists.
3. Otherwise, reuse the first active portfolio matching name and strategy.
4. Only create a new portfolio if no configured or matching portfolio exists.

This prevents duplicate active portfolios for routine reruns.

## Validation Queries

Portfolio row:

```sql
SELECT portfolio_id, name, strategy, portfolio_size, initial_capital,
       cash, current_nav, benchmark_symbol, status, created_at
FROM paper_portfolios
ORDER BY portfolio_id;
```

Expected row:

```text
portfolio_id: 1
name: Swing V2.1 Rolling 10 Slot Paper
strategy: swing_v2_1_rolling_10_slot
portfolio_size: 10
initial_capital: 1000000.00
cash: 1000000.00
current_nav: 1000000.00
benchmark_symbol: NIFTY500
status: active
```

Position/trade/snapshot state immediately after initialization:

```sql
SELECT COUNT(*) FROM paper_positions WHERE portfolio_id = 1;
SELECT COUNT(*) FROM paper_trades WHERE portfolio_id = 1;
SELECT COUNT(*) FROM paper_daily_snapshots WHERE portfolio_id = 1;
```

Expected:

```text
0
0
0
```

This phase creates the portfolio shell only.

## API Verification

### Health

```text
GET /health
```

Result:

```json
{
  "status": "ok",
  "research_db": {
    "connected": true,
    "database": "nse_research_platform"
  },
  "angel_db": {
    "connected": true,
    "database": "angel_data"
  },
  "paper_portfolio": {
    "configured": true,
    "portfolio_id": 1,
    "exists": true,
    "status": "active"
  }
}
```

### Portfolio

```text
GET /portfolio
```

Result includes:

```json
{
  "summary": {
    "portfolio_id": 1,
    "name": "Swing V2.1 Rolling 10 Slot Paper",
    "strategy": "swing_v2_1_rolling_10_slot",
    "portfolio_size": 10,
    "initial_capital": 1000000.0,
    "cash": 1000000.0,
    "current_nav": 1000000.0,
    "benchmark_symbol": "NIFTY500",
    "status": "active"
  },
  "positions": [],
  "trades": []
}
```

### Dashboard

```text
GET /dashboard
```

Result includes portfolio summary instead of an empty portfolio object:

```json
{
  "portfolio": {
    "portfolio_id": 1,
    "name": "Swing V2.1 Rolling 10 Slot Paper",
    "current_nav": 1000000.0,
    "cash": 1000000.0
  }
}
```

## Tests

Focused tests:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_paper_trading_service.py tests/test_phase5_5_paper_portfolio_initialization.py
```

Result:

```text
6 passed
```

## Current State

Paper portfolio initialized:

```text
portfolio_id=1
status=active
cash=1000000.00
current_nav=1000000.00
```

Cockpit health:

```text
ok
```

No positions, trades, or snapshots were created in this phase.

## Next Step

Run the paper trading daily cycle or historical replay only when explicitly approved. That later step may create positions, trades, and daily snapshots according to the frozen Swing V2.1 paper trading workflow.
