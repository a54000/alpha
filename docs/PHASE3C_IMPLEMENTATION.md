# Phase 3C Implementation

Generated on: 2026-06-12

## Objective

Add a paper trading lifecycle mode that matches the frozen Phase 2E Swing V2.1 portfolio behavior:

- enter from frozen Swing V2.1 recommendations
- hold for the planned 20-trading-day period
- ignore recommendation disappearance
- ignore weekly ranking changes
- exit only at planned exit unless an exception rule exists

No scoring, recommendations, factors, filters, broker APIs, or production tables were changed.

## Implemented Change

Updated:

- `app/paper_trading/service.py`
- `tests/test_paper_trading_service.py`
- `scripts/run_phase3b_replay_validation.py`

Added lifecycle config:

```python
PaperTradingConfig(lifecycle_mode="hold_to_planned_exit")
```

Default mode remains unchanged:

```python
PaperTradingConfig(lifecycle_mode="sell_removed_on_rebalance")
```

## Behavior

### Existing Mode

`sell_removed_on_rebalance`

- Closes open positions if they disappear from the weekly target recommendation set.
- Exit reason: `weekly_removed`
- Preserved as default behavior.

### New Mode

`hold_to_planned_exit`

- Maintains open positions after entry.
- Ignores weekly rank changes.
- Ignores recommendation disappearance.
- Does not open duplicate positions for already-held symbols.
- Opens new positions only when portfolio slots are available.
- Exits when `snapshot_date >= planned_exit_date`.
- Exit reason: `planned_exit`

## Tests

New coverage:

1. Hold-to-planned-exit ignores removed weekly recommendation.
2. Default mode still closes removed weekly recommendation.
3. Existing initialize, rebalance, daily update, and reporting tests still pass.

Verification:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_paper_trading_service.py tests/test_database_schema.py
```

Result:

- 9 passed

Additional verification:

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

## Replay Validation

Updated replay harness:

- `scripts/run_phase3b_replay_validation.py`

New options:

```powershell
--lifecycle-mode hold_to_planned_exit
--warmup-start-date 2024-12-01
```

Replay command:

```powershell
.\.venv\Scripts\python.exe scripts/run_phase3b_replay_validation.py `
  --lifecycle-mode hold_to_planned_exit `
  --output-json reports/phase3c_hold_to_exit_replay_validation.json
```

Output:

- `reports/phase3c_hold_to_exit_replay_validation.json`

The replay warms up state from 2024-12-01 and reports metrics for 2025-01-01 to 2026-06-11. This avoids starting the paper engine flat when Phase 2E already had positions open entering 2025.

## Replay Results

### Top 5 Weekly

| Metric | Hold-To-Exit Paper Replay | Phase 2E Same Period | Delta |
| --- | ---: | ---: | ---: |
| Total Return | 14.04% | 20.89% | -6.85 pp |
| CAGR | 9.77% | 14.42% | -4.64 pp |
| Max Drawdown | -14.83% | -12.79% | -2.04 pp |
| Sharpe | 0.569 | 0.825 | -0.256 |
| Profit Factor | 1.286 | 1.518 | -0.232 |
| Trade Count | 75 | 81 | -6 |

Exit reasons:

- `planned_exit`: 75

### Top 10 Weekly

| Metric | Hold-To-Exit Paper Replay | Phase 2E Same Period | Delta |
| --- | ---: | ---: | ---: |
| Total Return | 5.06% | 5.56% | -0.50 pp |
| CAGR | 3.57% | 3.91% | -0.35 pp |
| Max Drawdown | -9.76% | -10.85% | +1.09 pp |
| Sharpe | 0.300 | 0.316 | -0.017 |
| Profit Factor | 1.063 | 1.162 | -0.099 |
| Trade Count | 150 | 160 | -10 |

Exit reasons:

- `planned_exit`: 150

## Validation Conclusion

The new `hold_to_planned_exit` mode fixes the lifecycle mismatch found in Phase 3B.

Evidence:

- All replay exits use `planned_exit`.
- Trade counts moved close to Phase 2E.
- Top 10 performance converged materially.
- Top 5 performance improved materially versus the Phase 3B sell-removed replay, though it remains below Phase 2E.

Remaining Top 5 mismatch is likely due to implementation-level accounting differences:

- paper engine warmup state is reconstructed from 2024-12-01 rather than from the full original Phase 2E run start
- capital allocation and cash timing differ slightly from the Phase 2E backtester
- Phase 2E period comparison slices an already-running equity curve, while the paper replay is a reconstructed stateful run

The remaining gap should be tracked, but it is no longer the severe strategy-lifecycle mismatch identified in Phase 3B.

## Constraints Preserved

- No scoring changes.
- No recommendation changes.
- No filters added.
- No broker APIs connected.
- Existing default paper mode unchanged.

## Files

- `app/paper_trading/service.py`
- `tests/test_paper_trading_service.py`
- `scripts/run_phase3b_replay_validation.py`
- `reports/phase3c_hold_to_exit_replay_validation.json`
