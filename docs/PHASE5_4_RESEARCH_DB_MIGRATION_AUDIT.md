# Phase 5.4 Research DB Migration Audit

Date: 2026-06-12

Scope: read-only audit of the research database schema against Alembic history, `db/models.py`, Phase 3A paper trading infrastructure, and Phase 4B pipeline tracking expectations. No migrations were run. No tables, columns, data, application code, scoring, recommendations, or strategy logic were modified.

## Executive Summary

The research database is behind the application schema.

Current live Alembic revision:

```text
007
```

Available Alembic head:

```text
014
```

The current blocker is explained by missing migrations:

| Missing object | Expected source | Migration required |
| --- | --- | --- |
| `paper_portfolios` | Phase 3A / `db.models.PaperPortfolio` | `012_create_paper_trading_tables.py` |
| `paper_positions` | Phase 3A / `db.models.PaperPosition` | `012_create_paper_trading_tables.py` |
| `paper_trades` | Phase 3A / `db.models.PaperTrade` | `012_create_paper_trading_tables.py` |
| `paper_daily_snapshots` | Phase 3A / `db.models.PaperDailySnapshot` | `012_create_paper_trading_tables.py` |
| `pipeline_runs.business_date` | Phase 4B / `db.models.PipelineRuns` | `013_add_daily_pipeline_step_tracking.py` |
| `pipeline_runs.step_name` | Phase 4B / `db.models.PipelineRuns` | `013_add_daily_pipeline_step_tracking.py` |
| `pipeline_runs.started_at` | Phase 4B / `db.models.PipelineRuns` | `013_add_daily_pipeline_step_tracking.py` |
| `pipeline_runs.completed_at` | Phase 4B / `db.models.PipelineRuns` | `013_add_daily_pipeline_step_tracking.py` |

The existing `pipeline_runs.status` and `pipeline_runs.error_message` columns are already present from the older schema.

Recommended safe upgrade path:

```powershell
alembic upgrade 008
alembic upgrade 009
alembic upgrade 010
alembic upgrade 011
alembic upgrade 012
alembic upgrade 013
alembic upgrade 014
```

Or, after backup and review:

```powershell
alembic upgrade head
```

Because the live revision is `007`, the minimum migrations needed for the current cockpit blocker are `012` and `013`, but Alembic must apply the full linear chain through `008`, `009`, `010`, and `011` first.

## Alembic State

### Current Revision

Command:

```powershell
alembic current
```

Result:

```text
007
```

### Available History

Command:

```powershell
alembic history
```

Result:

```text
013 -> 014 (head), Create recommendation decision journal.
012 -> 013, Add daily pipeline step tracking fields.
011 -> 012, Create paper trading tables.
010 -> 011, Create security alias and lineage tables.
009 -> 010, Create security master table.
008 -> 009, Add Swing V2.1 score column.
007 -> 008, Add V2 score columns to daily_scores.
006 -> 007, Add index_prices_daily table for benchmark index data.
005 -> 006, Add model_version_id to recommendation_history.
004 -> 005, Add persisted sector strength fields to sector_daily.
003 -> 004, Add persisted breakout fields to features_daily.
002 -> 003, Configure TimescaleDB hypertables for large time-series tables.
001 -> 002, Add indexes and additional constraints.
<base> -> 001, Create initial database tables.
```

Expected revision for current application code:

```text
014
```

## Live Schema Findings

Read-only information schema checks were run against the configured research database.

### Required Tables

| Table | Exists in live DB | Expected source |
| --- | --- | --- |
| `paper_portfolios` | No | Migration `012`, Phase 3A |
| `paper_positions` | No | Migration `012`, Phase 3A |
| `paper_trades` | No | Migration `012`, Phase 3A |
| `paper_daily_snapshots` | No | Migration `012`, Phase 3A |
| `pipeline_runs` | Yes | Initial schema plus migration `013` updates |

Live query result for the requested tables:

```text
alembic_version
pipeline_runs
```

No paper trading tables exist.

### `pipeline_runs` Columns

Live `pipeline_runs` columns:

| Column | Type | Nullable |
| --- | --- | --- |
| `run_id` | integer | no |
| `job_name` | character varying | no |
| `run_date` | date | no |
| `start_time` | timestamp without time zone | no |
| `end_time` | timestamp without time zone | yes |
| `status` | character varying | no |
| `rows_processed` | integer | yes |
| `error_message` | text | yes |

Required Phase 4B columns:

| Column | Exists | Notes |
| --- | --- | --- |
| `business_date` | No | Added by migration `013` |
| `step_name` | No | Added by migration `013` |
| `status` | Yes | Existing legacy column reused |
| `error_message` | Yes | Existing legacy column reused |
| `completed_at` | No | Added by migration `013` |

Additional Phase 4B column:

| Column | Exists | Notes |
| --- | --- | --- |
| `started_at` | No | Added by migration `013` |

Live `pipeline_runs` row count:

```text
0
```

This lowers upgrade risk for migration `013`, because its backfill from legacy `run_date/job_name/start_time/end_time` has no existing rows to transform.

## Expected Schema Sources

### `db/models.py`

Relevant ORM models:

- `PaperPortfolio` -> `paper_portfolios`
- `PaperPosition` -> `paper_positions`
- `PaperTrade` -> `paper_trades`
- `PaperDailySnapshot` -> `paper_daily_snapshots`
- `PipelineRuns` -> `pipeline_runs`

The current application expects the Phase 3A paper trading tables and Phase 4B step-level pipeline tracking columns.

### Phase 3A

Phase 3A introduced paper trading infrastructure:

- `paper_portfolios`
- `paper_positions`
- `paper_trades`
- `paper_daily_snapshots`

Alembic migration:

```text
012_create_paper_trading_tables.py
```

### Phase 4B

Phase 4B introduced controlled daily orchestration tracking:

- `pipeline_runs.business_date`
- `pipeline_runs.step_name`
- `pipeline_runs.started_at`
- `pipeline_runs.completed_at`
- `pipeline_runs.error_message`
- unique index on `(business_date, step_name)`
- index on `(business_date, status)`

Alembic migration:

```text
013_add_daily_pipeline_step_tracking.py
```

## Missing Migrations

Live revision:

```text
007
```

Missing migrations:

| Revision | Purpose | Required for current blocker |
| --- | --- | --- |
| `008` | Add V2 score columns to `daily_scores` | Not directly, but required in chain |
| `009` | Add `swing_v2_1_score` to `daily_scores` | Not directly, but required in chain |
| `010` | Create security master table | Not directly, but required in chain |
| `011` | Create security alias and lineage tables | Not directly, but required in chain |
| `012` | Create paper trading tables | Yes |
| `013` | Add Phase 4B pipeline tracking fields | Yes |
| `014` | Create recommendation decision journal | Required for explanation journal path; current explanation fallback can use Angel pilot data |

## Safe Upgrade Path

### Preflight

1. Stop API and paper pipeline processes.
2. Confirm the target DB is the research DB:

```sql
SELECT current_database();
```

Expected:

```text
nse_research_platform
```

3. Take a database backup.
4. Confirm the live revision:

```powershell
alembic current
```

Expected current value before upgrade:

```text
007
```

5. Confirm no accidental use of `ANGEL_DATABASE_URL` for Alembic. Alembic should target only `DATABASE_URL`.

### Staged Upgrade

Recommended staged sequence:

```powershell
alembic upgrade 008
alembic upgrade 009
alembic upgrade 010
alembic upgrade 011
alembic upgrade 012
alembic upgrade 013
alembic upgrade 014
```

Rationale:

- Provides a checkpoint after each revision.
- Makes failures easier to isolate.
- Avoids jumping through unrelated schema changes blindly.

### Post-Upgrade Validation

After upgrade, run read-only checks:

```sql
SELECT version_num FROM alembic_version;

SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_name IN (
    'paper_portfolios',
    'paper_positions',
    'paper_trades',
    'paper_daily_snapshots'
  )
ORDER BY table_name;

SELECT column_name
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name = 'pipeline_runs'
  AND column_name IN (
    'business_date',
    'step_name',
    'status',
    'error_message',
    'completed_at',
    'started_at'
  )
ORDER BY column_name;
```

Expected:

- Alembic revision `014`
- All four paper tables exist
- All requested pipeline columns exist

### Application Validation

After schema upgrade and API restart:

```powershell
Invoke-WebRequest http://127.0.0.1:8000/health -UseBasicParsing
Invoke-WebRequest http://127.0.0.1:8000/portfolio -UseBasicParsing
Invoke-WebRequest http://127.0.0.1:8000/pipeline/status -UseBasicParsing
```

Expected:

- `/health` should no longer fail due to missing paper tables.
- `/pipeline/status` should no longer fail due to missing `business_date`.
- `/portfolio` may still be empty if no paper portfolio row has been initialized, but it should not fail because the table is absent.

## Rollback Considerations

Rollback is possible through Alembic downgrades, but should be treated carefully.

### Revision `014`

Downgrade drops:

- `recommendation_decision_journal`

Risk:

- Any captured explanation snapshots would be lost.

### Revision `013`

Downgrade drops:

- `ix_pipeline_runs_business_date_status`
- unique index on `(business_date, step_name)`
- `completed_at`
- `started_at`
- `step_name`
- `business_date`

Risk:

- Phase 4B orchestration history would lose new step-level fields.
- Current live `pipeline_runs` has zero rows, so rollback risk is low before operational runs populate the table.

### Revision `012`

Downgrade drops:

- `paper_daily_snapshots`
- `paper_trades`
- `paper_positions`
- `paper_portfolios`

Risk:

- Any paper portfolio state, positions, trade ledger, and daily snapshots would be deleted.
- If rollback is needed after paper trading starts, export these tables first.

### Revisions `010` and `011`

Downgrade would remove security master, aliases, and lineage infrastructure.

Risk:

- Later symbol/security mapping work would be removed.

### Revisions `008` and `009`

Downgrade removes V2 score columns from `daily_scores`.

Risk:

- Any generated V2/V2.1 score values in production `daily_scores` would be removed.

## Risk Assessment

Current row/data risk appears low for the immediate blockers:

- `pipeline_runs` exists but has `0` rows.
- Paper trading tables do not exist yet.

Main upgrade risks:

- Revisions `008` and `009` add columns to `daily_scores`; verify table size and lock tolerance before applying in a live trading window.
- Revisions `010` and `011` create security master and alias infrastructure; ensure names do not collide with manually created tables.
- Revision `012` has foreign keys from paper tables to `symbol_master.symbol`, so `symbol_master` must exist.
- Revision `013` is designed to handle existing legacy `pipeline_runs` shape and backfill from `run_date`, `job_name`, `start_time`, and `end_time`.

## Recommendation

Proceed with a staged Alembic upgrade from `007` to `014` after taking a database backup.

Minimum required for the current Cockpit API blockers:

- Apply through `012` for paper trading tables.
- Apply through `013` for pipeline tracking columns.

Recommended target:

- Apply through `014`, because it is the current Alembic head and supports the recommendation decision journal endpoint.

No manual table creation is recommended. Use Alembic only.
