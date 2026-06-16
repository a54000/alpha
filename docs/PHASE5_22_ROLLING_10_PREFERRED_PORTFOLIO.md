# Phase 5.22 Rolling 10-Slot Preferred Portfolio Construction

## Decision

The current preferred paper portfolio construction is:

| Setting | Value |
| --- | --- |
| Strategy name | `swing_v2_1_rolling_10_slot` |
| Maximum open positions | `10` |
| Weekly candidate intake | Top `5` recommendations |
| Holding mode | `hold_to_planned_exit` |
| Planned holding period | `20` trading days |
| Recommendation source | Frozen Swing V2.1 pilot recommendations |
| Price/feature source | `pilot_phase2a` when `PAPER_TRADING_DATA_SOURCE=pilot_phase2a` |

This supersedes the earlier operational Top 5 paper portfolio construction.

## Rationale

The rolling 10-slot cohort keeps the stronger Top 5 recommendation quality at entry while allowing overlapping 20-trading-day cohorts to remain invested. It addresses the capital-utilization issue in a pure Top 5 structure, where the first weekly cohort can consume all capital and leave no room for later recommendations during the planned holding window.

## Backtest Reference

Research artifact:

- `reports/phase5_20_rolling_10_cohort_backtest.json`
- `docs/PHASE5_20_ROLLING_10_COHORT_BACKTEST.md`

Key observed metrics:

| Metric | Rolling 10-slot |
| --- | ---: |
| CAGR | `29.37%` |
| Total return | `176.72%` |
| Max drawdown | `-18.09%` |
| Sharpe | `1.36` |
| Profit factor | `2.06` |
| Average open positions | `7.85` |
| Average cash | `22.01%` |
| Slot utilization | `78.54%` |

The 8-slot variant had slightly higher headline CAGR, but the 10-slot variant is preferred because it uses capacity more evenly and provides a less aggressive balance between concentration, drawdown, and available cash.

## Operational Defaults

Paper trading defaults now use:

```text
portfolio_size=10
max_candidate_rank=5
strategy=swing_v2_1_rolling_10_slot
lifecycle_mode=hold_to_planned_exit
```

Daily pipeline commands should preserve both controls:

```powershell
.\.venv\Scripts\python.exe scripts\run_full_daily_pipeline.py `
  --business-date 2026-06-12 `
  --portfolio-id 1 `
  --portfolio-size 10 `
  --max-candidate-rank 5 `
  --rebalance-paper
```

For dry-run validation:

```powershell
.\.venv\Scripts\python.exe scripts\run_full_daily_pipeline.py `
  --business-date 2026-06-12 `
  --portfolio-id 1 `
  --portfolio-size 10 `
  --max-candidate-rank 5 `
  --dry-run `
  --sync-dry-run
```

## Scheduler

The daily scheduled task should call:

```powershell
.\scripts\install_daily_pipeline_task.ps1 `
  -StartTime "18:30" `
  -PortfolioId 1 `
  -PortfolioSize 10 `
  -MaxCandidateRank 5 `
  -Replace
```

Use `-DryRun -SyncDryRun` only for scheduler testing. Remove those switches for live daily paper operations.

## Validation

Expected behavior during a rebalance:

1. The engine can hold up to 10 open positions.
2. New entries are selected only from ranks 1 through 5 for that recommendation date.
3. Existing holdings remain open until planned exit under `hold_to_planned_exit`.
4. Allocation target is NAV divided by 10, not NAV divided by 5.
5. No scoring, ranking, or recommendation-generation logic changes are introduced by this portfolio-construction change.

## Constraints

This is a portfolio construction preference only.

Do not change:

- Swing V2.1 scoring factors.
- Recommendation ranking logic.
- EMA200 gate behavior.
- Historical Angel data.
- Broker/API order behavior.
