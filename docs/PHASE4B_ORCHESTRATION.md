# Phase 4B Orchestration

Generated on: 2026-06-12

## Objective

Create a controlled daily orchestrator for the frozen Swing V2.1 paper trading workflow.

## Entry Point

```powershell
python scripts/run_full_daily_pipeline.py --business-date 2026-06-12 --portfolio-id 1
```

Dry run:

```powershell
python scripts/run_full_daily_pipeline.py --business-date 2026-06-12 --portfolio-id 1 --dry-run
```

Resume from prior successful steps:

```powershell
python scripts/run_full_daily_pipeline.py --business-date 2026-06-12 --portfolio-id 1 --resume
```

Start from a specific step:

```powershell
python scripts/run_full_daily_pipeline.py --business-date 2026-06-12 --portfolio-id 1 --from-step feature_generation
```

## Pipeline Order

1. `angel_data_sync`
2. `market_data_validation`
3. `daily_bar_refresh`
4. `feature_generation`
5. `swing_v2_1_scoring`
6. `recommendation_generation`
7. `decision_journal_capture`
8. `paper_portfolio_update`
9. `monitoring_report_generation`

## Step Mapping

| Step | Command |
|---|---|
| `angel_data_sync` | `scripts/sync_angel_daily_data.py` |
| `market_data_validation` | `scripts/run_phase2a_pilot_infrastructure.py` |
| `daily_bar_refresh` | `scripts/run_phase2a1_daily_bar_cleaning.py` |
| `feature_generation` | `scripts/run_phase2b_pilot_feature_generation.py` |
| `swing_v2_1_scoring` | `scripts/run_phase2c_pilot_scoring.py` |
| `recommendation_generation` | `scripts/run_phase2d_pilot_recommendations.py` |
| `decision_journal_capture` | `scripts/capture_recommendation_decision_journal.py` |
| `paper_portfolio_update` | `app.paper_trading.daily_update` |
| `monitoring_report_generation` | `scripts/generate_daily_paper_report.py` |

## Pipeline Run Tracking

Phase 4B adds step-level run tracking to `pipeline_runs`.

Required fields:

- `run_id`
- `business_date`
- `step_name`
- `status`
- `started_at`
- `completed_at`
- `error_message`

The existing legacy fields are preserved for compatibility:

- `job_name`
- `run_date`
- `start_time`
- `end_time`
- `rows_processed`

Each `(business_date, step_name)` is unique. Rerunning a step updates the existing row rather than duplicating it.

## Failure Behavior

If any step returns a non-zero exit code:

1. The step is marked `failed`.
2. The error tail is stored in `error_message`.
3. Downstream steps are not executed.
4. The final JSON summary is still written.
5. The script exits non-zero.

This prevents recommendations, paper updates, or monitoring reports from being generated after a failed upstream dependency.

## Resume Behavior

With `--resume`, the orchestrator checks `pipeline_runs` for the same `business_date`.

- Steps already marked `success` are skipped.
- The first incomplete or failed step is executed.
- Downstream steps run normally after that.
- Step outputs are deterministic report paths, so reruns replace the previous report files instead of creating uncontrolled duplicates.

## From-Step Behavior

`--from-step` starts execution at the selected step and includes all later steps.

Allowed values:

- `angel_data_sync`
- `market_data_validation`
- `daily_bar_refresh`
- `feature_generation`
- `swing_v2_1_scoring`
- `recommendation_generation`
- `decision_journal_capture`
- `paper_portfolio_update`
- `monitoring_report_generation`

Use this only after confirming upstream state is valid for the business date.

## Dry Run

`--dry-run` does not execute subprocess steps and does not write `pipeline_runs`.

It does write the final JSON execution summary so the planned command sequence can be reviewed.

Default output:

```text
reports/phase4b_full_daily_pipeline_<business_date>.json
```

## Final Execution Summary

The orchestrator writes:

```text
reports/phase4b_full_daily_pipeline_<business_date>.json
```

The summary includes:

- business date
- dry-run flag
- resume flag
- from-step value
- step statuses
- return codes
- stdout/stderr tails
- frozen-strategy constraints

## Paper Update

Paper update is explicit through `--portfolio-id`.

Use `--rebalance-paper` only when the business date should perform the weekly rebalance:

```powershell
python scripts/run_full_daily_pipeline.py --business-date 2026-06-12 --portfolio-id 1 --rebalance-paper
```

The paper update uses the existing `hold_to_planned_exit` service behavior. No broker APIs are connected.

## Constraints

Phase 4B does not:

- change strategy
- change scoring
- change recommendation generation
- add factors
- optimize parameters
- connect broker APIs
- place orders

## Verification

Focused tests:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_phase4b_orchestration.py
```

Compile check:

```powershell
.\.venv\Scripts\python.exe -m py_compile scripts/run_full_daily_pipeline.py
```
