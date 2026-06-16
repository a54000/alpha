# Phase 3A Implementation

Generated on: 2026-06-12

## Objective

Create paper trading infrastructure for the frozen Swing V2.1 strategy.

Frozen strategy:

- Primary: Top 5 Weekly
- Shadow: Top 10 Weekly
- Model: `swing_v2_1`

This phase adds infrastructure only. It does not connect broker APIs, place orders, run live trading, modify scoring, modify recommendation logic, or change factors.

## Delivered Files

Migration:

- `alembic/versions/012_create_paper_trading_tables.py`

ORM models:

- `PaperPortfolio`
- `PaperPosition`
- `PaperTrade`
- `PaperDailySnapshot`

Service modules:

- `app/paper_trading/__init__.py`
- `app/paper_trading/service.py`

Tests:

- `tests/test_paper_trading_service.py`
- Updated `tests/test_database_schema.py`

## Database Objects

### `paper_portfolios`

Tracks configured paper portfolios.

Key fields:

- `portfolio_id`
- `name`
- `strategy`
- `portfolio_size`
- `initial_capital`
- `cash`
- `current_nav`
- `benchmark_symbol`
- `status`

### `paper_positions`

Tracks open and closed paper positions.

Key fields:

- `portfolio_id`
- `symbol`
- `sector`
- `signal_date`
- `recommendation_rank`
- `recommendation_score`
- `entry_date`
- `entry_price`
- `quantity`
- `capital_allocated`
- `current_price`
- `market_value`
- `unrealized_pnl`
- `planned_exit_date`
- `exit_date`
- `exit_price`
- `status`
- `fees`
- `slippage`

### `paper_trades`

Tracks realized paper trades after positions close.

Key fields:

- `portfolio_id`
- `position_id`
- `symbol`
- `sector`
- `signal_date`
- `entry_date`
- `exit_date`
- `entry_price`
- `exit_price`
- `quantity`
- `capital_allocated`
- `proceeds`
- `realized_pnl`
- `return_pct`
- `fees`
- `slippage`
- `turnover`
- `exit_reason`

### `paper_daily_snapshots`

Tracks daily portfolio NAV and accounting.

Key fields:

- `portfolio_id`
- `date`
- `cash`
- `market_value`
- `nav`
- `realized_pnl`
- `unrealized_pnl`
- `fees`
- `slippage`
- `turnover`
- `benchmark_close`
- `benchmark_return`
- `open_positions`

## Service Workflow

Implemented service:

```python
PaperTradingService
```

Configuration:

```python
PaperTradingConfig(
    strategy="swing_v2_1_top5_weekly",
    recommendation_model="swing_v2_1",
    portfolio_size=5,
    initial_capital=1_000_000.0,
    holding_period=20,
    benchmark_symbol="NIFTY500",
)
```

### Initialize Portfolio

```python
initialize_portfolio(name, config)
```

Creates a paper portfolio with initial cash and NAV.

### Weekly Rebalance

```python
rebalance_weekly(portfolio_id, signal_date, config)
```

Reads existing production recommendations from `recommendation_history` for the frozen `swing_v2_1` model.

Behavior:

- Uses production-generated recommendation rows.
- Selects recommendations by rank.
- Opens simulated entries on the next trading-day open.
- Uses equal target allocation.
- Does not place broker orders.
- Closes open positions removed from the target weekly set using simulated exit prices.

### Daily Update

```python
update_daily(portfolio_id, snapshot_date)
```

Behavior:

- Closes positions whose planned exit date has arrived.
- Marks open positions to latest close.
- Updates unrealized PnL.
- Updates realized PnL.
- Writes or updates a daily NAV snapshot.
- Tracks benchmark close and benchmark return when `index_prices_daily` contains the configured benchmark.

### Performance Report

```python
performance_report(portfolio_id)
```

Returns summary metrics from paper snapshots and closed trades:

- NAV
- total return
- realized PnL
- unrealized PnL
- win rate
- profit factor

## Historical One-Day Verification

The test suite verifies a minimal historical one-day paper flow:

1. Seed symbols.
2. Seed frozen `swing_v2_1` recommendations.
3. Seed next-day prices.
4. Initialize a paper portfolio.
5. Run weekly rebalance.
6. Run one daily mark-to-market update.
7. Confirm positions and NAV snapshot are created.

This verifies that a paper portfolio can be initialized and updated without broker integration.

## Constraints Preserved

No scoring changes:

- The service consumes existing `recommendation_history`; it does not compute scores.

No recommendation changes:

- The service uses generated recommendation rank/order.

No factor changes:

- No feature computation is touched.

No broker integration:

- Entries and exits are simulated from local price data.

No live trading:

- No order placement, API keys, or broker calls exist in this implementation.

## Verification

Commands run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_database_schema.py tests/test_paper_trading_service.py
```

Result:

- 7 passed

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_migrations.py --basetemp D:\nse-research-app\.pytest_tmp
```

Result:

- 1 passed

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_package_imports.py
```

Result:

- 1 passed

```powershell
.\.venv\Scripts\python.exe -m py_compile app/paper_trading/service.py
```

Result:

- passed

## Rollback

Alembic downgrade from revision `012` drops:

- `paper_daily_snapshots`
- `paper_trades`
- `paper_positions`
- `paper_portfolios`

No production scoring, recommendation, feature, or price tables are modified by the migration.

## Phase Boundary

Phase 3A is complete when:

- paper trading tables exist as migration and ORM models
- a portfolio can be initialized
- one historical daily update can be simulated
- tests pass

Later phases may add scheduled jobs, dashboards, broker-paper integration, or live monitoring. Those are intentionally not included in Phase 3A.
