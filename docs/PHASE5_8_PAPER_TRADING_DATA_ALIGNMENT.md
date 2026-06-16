# Phase 5.8 Paper Trading Data Source Alignment

Generated on: 2026-06-13

## Objective

Align paper trading reads with the frozen Swing V2.1 pilot data source without copying pilot data into production tables.

The issue was:

- Research Cockpit recommendations read from `angel_data.pilot_phase2a.recommendations_daily`.
- Paper trading read from research `recommendation_history` and `prices_daily`.
- Result: recommendations were visible in the UI, but the paper portfolio had no holdings or trades.

## Implementation

Added a configurable data-source layer:

- `app/paper_trading/data_source.py`

Supported sources:

| Source | Recommendations | Prices | Status |
| --- | --- | --- | --- |
| `PILOT_PHASE2A` | `pilot_phase2a.recommendations_daily` | `pilot_phase2a.daily_bars_clean` | Default for local paper trading |
| `PRODUCTION` | `recommendation_history` | `prices_daily` | Preserved existing behavior |

Environment configuration:

```text
PAPER_TRADING_DATA_SOURCE=pilot_phase2a
PAPER_TRADING_PILOT_SCHEMA=pilot_phase2a
```

CLI override:

```powershell
.\.venv\Scripts\python.exe -m app.paper_trading.daily_update --cycle-date 2026-06-11 --portfolio-id 1 --portfolio-size 10 --max-candidate-rank 5 --rebalance --data-source pilot_phase2a
```

## Lifecycle Preservation

The paper trading lifecycle remains unchanged:

- signal date uses Swing V2.1 recommendations
- entry date is the next available trading day after signal date
- entry price uses next trading day open
- exits use planned holding period
- `hold_to_planned_exit` behavior is unchanged
- cash handling is unchanged
- paper positions, trades, and snapshots are still written only to paper trading tables

Only read sources changed.

## Validation Output

Paper update now reports:

- data source
- recommendation date used
- price date used
- symbols considered
- symbols entered
- symbols skipped and reason

Example validation for 2026-06-11:

```json
{
  "step": "rebalance_weekly",
  "data_source": "PILOT_PHASE2A",
  "recommendation_date_used": "2026-06-11",
  "price_date_used": null,
  "symbols_considered": [
    "ELGIEQUIP",
    "NATCOPHARM",
    "CENTRALBK",
    "CONCOR",
    "EIDPARRY"
  ],
  "symbols_entered": [],
  "symbols_skipped": [
    {"symbol": "ELGIEQUIP", "reason": "no_next_trading_day"},
    {"symbol": "NATCOPHARM", "reason": "no_next_trading_day"},
    {"symbol": "CENTRALBK", "reason": "no_next_trading_day"},
    {"symbol": "CONCOR", "reason": "no_next_trading_day"},
    {"symbol": "EIDPARRY", "reason": "no_next_trading_day"}
  ]
}
```

This confirms the source alignment is working: the engine now sees the same top recommendations visible in the UI.

## Current Operational Nuance

The latest pilot recommendation date is `2026-06-11`.

The latest cleaned daily bar date is also `2026-06-11`.

Because the frozen lifecycle enters on the next available trading day open, a `2026-06-11` signal cannot create positions until `pilot_phase2a.daily_bars_clean` contains a date after `2026-06-11`.

Therefore, the current no-holdings state is no longer caused by data-source mismatch. It is caused by missing next-day cleaned daily bars for entry.

## Tests

Added coverage in:

- `tests/test_paper_trading_service.py`

Cases:

1. Pilot source generates positions when recommendations and next-day prices exist.
2. Production source still works.
3. Production and pilot sources produce the same lifecycle result when fed the same recommendations and prices.
4. Data-source environment normalization supports `pilot_phase2a` and `production`.

Verification:

```text
8 passed
```

## Files Changed

- `app/paper_trading/data_source.py`
- `app/paper_trading/service.py`
- `app/paper_trading/daily_update.py`
- `tests/test_paper_trading_service.py`
- `.env`

## Acceptance Confirmation

- Swing V2.1 scoring unchanged.
- Recommendation generation unchanged.
- No pilot data copied into production tables.
- No duplicate datasets created.
- Paper trading lifecycle unchanged.
- Broker APIs not connected.
- Orders not placed.
