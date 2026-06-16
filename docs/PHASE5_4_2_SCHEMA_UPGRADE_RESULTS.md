# Phase 5.4.2 Schema Upgrade Results

Date: 2026-06-12

Scope: controlled research database schema upgrade from Alembic revision `007` to `014`. No strategy logic, scoring logic, recommendation generation, Angel data, feature rebuilds, backtests, broker connections, or order placement were performed.

## Summary

Result: successful.

Previous revision:

```text
007
```

Final revision:

```text
014
```

Upgrade method:

- staged Alembic upgrades
- validation after every revision
- stopped API processes before migration
- no manual schema patching

## Pre-Flight Results

### Alembic Revision

```text
007
```

### Database Connectivity

Research DB:

```text
database: nse_research_platform
user: postgres
status: connected
```

Angel DB:

```text
database: angel_data
user: postgres
status: connected
```

### Application Environment

Required variables were present:

- `DATABASE_URL`
- `ANGEL_DATABASE_URL`
- `PAPER_PORTFOLIO_ID`

Configured values resolved to separate databases:

- `DATABASE_URL` -> `nse_research_platform`
- `ANGEL_DATABASE_URL` -> `angel_data`

### Git Working Tree Status

Git status could not be checked because `D:\nse-research-app` is not currently a Git repository:

```text
fatal: not a git repository (or any of the parent directories): .git
```

### API Process Handling

Existing FastAPI processes were stopped before migration.

## Backup Details

Backup type:

```text
pg_dump custom format
```

Database:

```text
nse_research_platform
```

Backup file:

```text
D:\nse-research-app\backups\nse_research_platform_pre_007_to_014_20260612_220013.dump
```

Backup timestamp:

```text
2026-06-12 22:00:13
```

Backup size:

```text
30,006,058 bytes
```

Note: the first backup attempt hung with a 0-byte file because `pg_dump` was waiting for authentication. That process was stopped, the empty file was removed, and the successful backup was created using noninteractive password handling from `.env`.

## Migration Results

### 007 -> 008

Migration:

```text
008_add_v2_score_columns.py
```

Status:

```text
success
```

Validation:

| Check | Expected | Actual | Result |
| --- | ---: | ---: | --- |
| Alembic revision | `008` | `008` | pass |
| `daily_scores` V2 columns | 2 | 2 | pass |

Columns verified:

- `daily_scores.swing_v2_score`
- `daily_scores.position_v2_score`

### 008 -> 009

Migration:

```text
009_add_swing_v2_1_score.py
```

Status:

```text
success
```

Validation:

| Check | Expected | Actual | Result |
| --- | ---: | ---: | --- |
| Alembic revision | `009` | `009` | pass |
| `daily_scores.swing_v2_1_score` | 1 | 1 | pass |

### 009 -> 010

Migration:

```text
010_create_security_master.py
```

Status:

```text
success
```

Validation:

| Check | Expected | Actual | Result |
| --- | ---: | ---: | --- |
| Alembic revision | `010` | `010` | pass |
| `security_master` table | 1 | 1 | pass |

### 010 -> 011

Migration:

```text
011_create_security_alias_and_lineage.py
```

Status:

```text
success
```

Validation:

| Check | Expected | Actual | Result |
| --- | ---: | ---: | --- |
| Alembic revision | `011` | `011` | pass |
| Alias and lineage tables | 2 | 2 | pass |

Tables verified:

- `security_symbol_alias`
- `security_corporate_action_lineage`

### 011 -> 012

Migration:

```text
012_create_paper_trading_tables.py
```

Status:

```text
success
```

Validation:

| Check | Expected | Actual | Result |
| --- | ---: | ---: | --- |
| Alembic revision | `012` | `012` | pass |
| Paper trading tables | 4 | 4 | pass |

Tables verified:

- `paper_portfolios`
- `paper_positions`
- `paper_trades`
- `paper_daily_snapshots`

### 012 -> 013

Migration:

```text
013_add_daily_pipeline_step_tracking.py
```

Status:

```text
success
```

Validation:

| Check | Expected | Actual | Result |
| --- | ---: | ---: | --- |
| Alembic revision | `013` | `013` | pass |
| Pipeline required columns | 6 | 6 | pass |
| Pipeline indexes | 2 | 2 | pass |

Columns verified:

- `pipeline_runs.business_date`
- `pipeline_runs.step_name`
- `pipeline_runs.started_at`
- `pipeline_runs.completed_at`
- `pipeline_runs.status`
- `pipeline_runs.error_message`

Indexes verified:

- `uq_pipeline_runs_business_date_step_name`
- `ix_pipeline_runs_business_date_status`

### 013 -> 014

Migration:

```text
014_create_recommendation_decision_journal.py
```

Status:

```text
success
```

Validation:

| Check | Expected | Actual | Result |
| --- | ---: | ---: | --- |
| Alembic revision | `014` | `014` | pass |
| `recommendation_decision_journal` table | 1 | 1 | pass |

## Final Schema Validation

Final Alembic revision:

```text
014
```

Paper trading tables:

```text
paper_daily_snapshots
paper_portfolios
paper_positions
paper_trades
```

Pipeline tracking columns:

```text
business_date
completed_at
error_message
started_at
status
step_name
```

Decision journal table:

```text
recommendation_decision_journal
```

Post-upgrade row counts:

| Object | Rows |
| --- | ---: |
| `paper_portfolios` | 0 |
| `pipeline_runs` | 0 |
| `recommendation_decision_journal` | 0 |

These zero row counts are expected because this phase was schema-only.

## Post-Upgrade Smoke Checks

FastAPI was restarted with `.env` values after migration.

### Backend/API

| Endpoint | Result | Notes |
| --- | --- | --- |
| `/health` | 200 | Status `degraded` because `PAPER_PORTFOLIO_ID=1` is configured but no portfolio row exists yet |
| `/dashboard` | 200 | Shows live market/freshness dates and empty portfolio summary |
| `/recommendations/latest?model=swing_v2_1&limit=5` | 200 | Returns live Angel recommendations dated 2026-06-11 |
| `/portfolio` | 200 | Empty portfolio payload, no schema error |
| `/pipeline/status` | 200 | Live latest candle/features/recommendation dates, no schema error |
| `/research/metrics` | 200 | Research reports available |

Observed live data after upgrade:

```text
latest_candle_at: 2026-06-12T11:45:00+05:30
latest_feature_date: 2026-06-11
latest_recommendation_date: 2026-06-11
recommendation source: pilot_phase2a.recommendations_daily
```

### Frontend

| Route | Result |
| --- | --- |
| `/` | 200 |
| `/recommendations` | 200 |
| `/recommendations/ELGIEQUIP/explanation` | 200 |
| `/portfolio` | 200 |
| `/operations` | 200 |
| `/research` | 200 |

## Failures

No migration failures occurred.

One non-migration issue remains:

- `/health` is `degraded` because `PAPER_PORTFOLIO_ID=1` does not yet exist in `paper_portfolios`.
- This is expected after schema-only migration because no paper portfolio was initialized.

## Rollback Instructions

Use Alembic rollback only if required. Do not manually patch schema.

Rollback one revision:

```powershell
alembic downgrade 013
```

Rollback to the original pre-upgrade revision:

```powershell
alembic downgrade 007
```

Restore from backup if a full database restore is required:

```powershell
pg_restore `
  --clean `
  --if-exists `
  --dbname "postgresql://postgres:<password>@localhost:5432/nse_research_platform" `
  "D:\nse-research-app\backups\nse_research_platform_pre_007_to_014_20260612_220013.dump"
```

Rollback risks:

| Downgrade past revision | Impact |
| --- | --- |
| `014` | Drops `recommendation_decision_journal` |
| `013` | Drops Phase 4B pipeline tracking columns/indexes |
| `012` | Drops paper trading tables |
| `011` | Drops security alias and lineage tables |
| `010` | Drops security master |
| `009` | Drops `daily_scores.swing_v2_1_score` |
| `008` | Drops V2 score columns |

Because no paper portfolio, pipeline run, or journal rows existed immediately after migration, rollback data risk is currently low for revisions `012` through `014`. Risk increases once paper trading and journal capture start writing rows.

## Next Operational Step

Initialize or replay a paper portfolio so `PAPER_PORTFOLIO_ID=1` resolves to an actual `paper_portfolios` row. Until then, `/health` correctly reports `degraded` while DB connectivity and schema are healthy.
