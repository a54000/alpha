# Phase 5.4.1 Migration Execution Plan

Date: 2026-06-12

Scope: execution checklist for upgrading the research database from Alembic revision `007` to `014`. This is a plan only. No migrations were run, no database objects were created, and no data was modified.

## Objective

Safely bring the research database schema up to the application expectation required by the Swing Research Cockpit:

- current revision: `007`
- target revision: `014`
- current blockers: missing paper trading tables and Phase 4B pipeline tracking columns

## Backup Requirement

Take a full research database backup before running any migration.

Recommended command pattern:

```powershell
pg_dump `
  --format=custom `
  --file "D:\nse-research-app\backups\nse_research_platform_pre_007_to_014.dump" `
  "postgresql://postgres:<password>@localhost:5432/nse_research_platform"
```

Also capture a schema-only snapshot:

```powershell
pg_dump `
  --schema-only `
  --file "D:\nse-research-app\backups\nse_research_platform_pre_007_to_014_schema.sql" `
  "postgresql://postgres:<password>@localhost:5432/nse_research_platform"
```

Do not proceed without a restorable backup.

## Pre-Migration Checks

Run these read-only checks before migration.

### Confirm Target Database

```sql
SELECT current_database();
```

Expected:

```text
nse_research_platform
```

### Confirm Alembic Revision

```powershell
alembic current
```

Expected:

```text
007
```

### Confirm Migration Chain

```powershell
alembic history
```

Expected chain:

```text
007 -> 008 -> 009 -> 010 -> 011 -> 012 -> 013 -> 014
```

### Confirm Existing Blocker State

```sql
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_name IN (
    'paper_portfolios',
    'paper_positions',
    'paper_trades',
    'paper_daily_snapshots',
    'pipeline_runs'
  )
ORDER BY table_name;
```

Expected before upgrade:

```text
pipeline_runs
```

```sql
SELECT column_name
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name = 'pipeline_runs'
ORDER BY ordinal_position;
```

Expected before upgrade:

```text
run_id
job_name
run_date
start_time
end_time
status
rows_processed
error_message
```

### Confirm Row Counts for Risk Review

```sql
SELECT COUNT(*) AS pipeline_runs_rows FROM pipeline_runs;
SELECT COUNT(*) AS daily_scores_rows FROM daily_scores;
```

Known audit result:

```text
pipeline_runs_rows = 0
```

`daily_scores` may be larger; revisions `008` and `009` alter it by adding nullable columns.

## Migration Order

Run one revision at a time:

```powershell
alembic upgrade 008
alembic upgrade 009
alembic upgrade 010
alembic upgrade 011
alembic upgrade 012
alembic upgrade 013
alembic upgrade 014
```

After each step, run:

```powershell
alembic current
```

Stop immediately if the reported revision does not match the target step.

## Migration Details

### Revision 008

File:

```text
alembic/versions/008_add_v2_score_columns.py
```

Purpose:

- Add V2 score columns to `daily_scores`.

Tables affected:

- `daily_scores`

Columns added:

- `swing_v2_score NUMERIC(5, 1) NULL`
- `position_v2_score NUMERIC(5, 1) NULL`

Indexes added:

- none

Constraints added:

- none

Data migration impact:

- No data values are changed.
- Existing rows receive null values for the new columns.
- May take an access-exclusive lock briefly on `daily_scores`.

Rollback risk:

- Downgrade drops both columns.
- Any values later populated in these columns would be lost.

Validation SQL:

```sql
SELECT column_name, data_type, numeric_precision, numeric_scale
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name = 'daily_scores'
  AND column_name IN ('swing_v2_score', 'position_v2_score')
ORDER BY column_name;
```

Expected:

```text
position_v2_score
swing_v2_score
```

### Revision 009

File:

```text
alembic/versions/009_add_swing_v2_1_score.py
```

Purpose:

- Add Swing V2.1 score column to `daily_scores`.

Tables affected:

- `daily_scores`

Columns added:

- `swing_v2_1_score NUMERIC(5, 1) NULL`

Indexes added:

- none

Constraints added:

- none

Data migration impact:

- No data values are changed.
- Existing rows receive null values for the new column.
- May briefly lock `daily_scores`.

Rollback risk:

- Downgrade drops `swing_v2_1_score`.
- Any future stored V2.1 scores would be lost.

Validation SQL:

```sql
SELECT column_name, data_type, numeric_precision, numeric_scale
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name = 'daily_scores'
  AND column_name = 'swing_v2_1_score';
```

Expected:

```text
swing_v2_1_score
```

### Revision 010

File:

```text
alembic/versions/010_create_security_master.py
```

Purpose:

- Create canonical security master foundation.

Tables affected:

- creates `security_master`

Columns added:

- `security_id`
- `canonical_symbol`
- `canonical_name`
- `isin_current`
- `exchange`
- `instrument_type`
- `status`
- `first_seen_date`
- `last_seen_date`
- `created_from_source`
- `review_status`
- `notes`
- `created_at`
- `updated_at`

Indexes added:

- `ix_security_master_canonical_symbol`
- `ix_security_master_status`
- `ix_security_master_review_status`
- `uq_security_master_exchange_isin_current`, unique partial index where `isin_current IS NOT NULL`

Constraints added:

- `ck_security_master_status`
- `ck_security_master_review_status`
- `ck_security_master_seen_date_order`

Data migration impact:

- Creates an empty table.
- Does not load or modify production symbol data.

Rollback risk:

- Downgrade drops `security_master`.
- If any securities are later loaded, downgrade would delete that data.
- Migration `011` depends on this table.

Validation SQL:

```sql
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_name = 'security_master';

SELECT indexname
FROM pg_indexes
WHERE schemaname = 'public'
  AND tablename = 'security_master'
ORDER BY indexname;
```

Expected:

```text
security_master
ix_security_master_canonical_symbol
ix_security_master_review_status
ix_security_master_status
uq_security_master_exchange_isin_current
```

### Revision 011

File:

```text
alembic/versions/011_create_security_alias_and_lineage.py
```

Purpose:

- Create alias and corporate-action lineage infrastructure.

Tables affected:

- creates `security_symbol_alias`
- creates `security_corporate_action_lineage`

Columns added to `security_symbol_alias`:

- `alias_id`
- `security_id`
- `source`
- `symbol`
- `normalized_symbol`
- `valid_from`
- `valid_to`
- `is_primary_for_source`
- `alias_reason`
- `confidence`
- `review_status`
- `notes`
- `created_at`
- `updated_at`

Columns added to `security_corporate_action_lineage`:

- `event_id`
- `event_date`
- `event_type`
- `from_security_id`
- `to_security_id`
- `ratio`
- `source_reference`
- `review_status`
- `notes`
- `created_at`
- `updated_at`

Indexes added:

- `ix_security_symbol_alias_source_symbol`
- `ix_security_symbol_alias_security_dates`
- `ix_security_symbol_alias_normalized_symbol`
- `ix_security_symbol_alias_review_status`
- `ix_security_lineage_event_date`
- `ix_security_lineage_from_security_id`
- `ix_security_lineage_to_security_id`
- `ix_security_lineage_review_status`

Constraints added:

- `uq_security_symbol_alias_source_symbol_from`
- alias source/reason/confidence/review-status check constraints
- alias valid date order check
- lineage event type/review-status check constraints
- lineage has at least one security check
- foreign keys to `security_master.security_id`

Data migration impact:

- Creates empty infrastructure tables.
- Does not populate aliases or lineage.

Rollback risk:

- Downgrade drops both tables.
- Any future alias or lineage review work would be lost.

Validation SQL:

```sql
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_name IN (
    'security_symbol_alias',
    'security_corporate_action_lineage'
  )
ORDER BY table_name;

SELECT indexname, tablename
FROM pg_indexes
WHERE schemaname = 'public'
  AND tablename IN (
    'security_symbol_alias',
    'security_corporate_action_lineage'
  )
ORDER BY tablename, indexname;
```

Expected:

```text
security_corporate_action_lineage
security_symbol_alias
```

### Revision 012

File:

```text
alembic/versions/012_create_paper_trading_tables.py
```

Purpose:

- Create paper trading infrastructure.

Tables affected:

- creates `paper_portfolios`
- creates `paper_positions`
- creates `paper_trades`
- creates `paper_daily_snapshots`

Columns added to `paper_portfolios`:

- `portfolio_id`
- `name`
- `strategy`
- `portfolio_size`
- `initial_capital`
- `cash`
- `current_nav`
- `benchmark_symbol`
- `status`
- `created_at`
- `updated_at`

Columns added to `paper_positions`:

- `position_id`
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
- `created_at`
- `updated_at`

Columns added to `paper_trades`:

- `trade_id`
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
- `created_at`

Columns added to `paper_daily_snapshots`:

- `snapshot_id`
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
- `created_at`

Indexes added:

- `ix_paper_positions_portfolio_status`
- `ix_paper_positions_symbol`
- `ix_paper_trades_portfolio_exit`
- `ix_paper_trades_symbol`
- `ix_paper_snapshots_portfolio_date`

Constraints added:

- foreign keys to `paper_portfolios.portfolio_id`
- foreign keys from paper symbols to `symbol_master.symbol`
- `ck_paper_portfolios_size_positive`
- `ck_paper_portfolios_initial_capital_positive`
- `ck_paper_portfolios_cash_nonnegative`
- `ck_paper_positions_entry_price_positive`
- `ck_paper_positions_quantity_positive`
- `ck_paper_positions_capital_nonnegative`
- `ck_paper_positions_status`
- `ck_paper_trades_entry_price_positive`
- `ck_paper_trades_exit_price_positive`
- `ck_paper_trades_quantity_positive`
- `uq_paper_daily_snapshots_portfolio_date`

Data migration impact:

- Creates empty paper trading tables.
- Does not initialize a portfolio.
- Does not create paper positions/trades/snapshots.

Rollback risk:

- Downgrade drops all paper trading tables.
- Any future paper trading state would be deleted.

Validation SQL:

```sql
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

SELECT tablename, indexname
FROM pg_indexes
WHERE schemaname = 'public'
  AND tablename LIKE 'paper_%'
ORDER BY tablename, indexname;
```

Expected:

```text
paper_daily_snapshots
paper_portfolios
paper_positions
paper_trades
```

### Revision 013

File:

```text
alembic/versions/013_add_daily_pipeline_step_tracking.py
```

Purpose:

- Add Phase 4B step-level daily pipeline tracking.

Tables affected:

- `pipeline_runs`

Columns added if table already exists:

- `business_date DATE NULL`
- `step_name VARCHAR(80) NULL`
- `started_at TIMESTAMP NULL`
- `completed_at TIMESTAMP NULL`

If `pipeline_runs` does not exist, the migration creates it with:

- `run_id`
- `business_date`
- `step_name`
- `status`
- `started_at`
- `completed_at`
- `error_message`

Indexes added:

- `uq_pipeline_runs_business_date_step_name`, unique index on `(business_date, step_name)`
- `ix_pipeline_runs_business_date_status`, index on `(business_date, status)`

Constraints added:

- unique index on `(business_date, step_name)`

Data migration impact:

- Backfills new fields from legacy columns:
  - `business_date = run_date`
  - `step_name = job_name`
  - `started_at = start_time`
  - `completed_at = end_time`
- Audit found `pipeline_runs` has `0` rows, so expected data movement is effectively none.

Rollback risk:

- Downgrade drops the two indexes and new columns.
- Future Phase 4B run history would lose step-level fields.

Validation SQL:

```sql
SELECT column_name
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name = 'pipeline_runs'
  AND column_name IN (
    'business_date',
    'step_name',
    'status',
    'error_message',
    'started_at',
    'completed_at'
  )
ORDER BY column_name;

SELECT indexname
FROM pg_indexes
WHERE schemaname = 'public'
  AND tablename = 'pipeline_runs'
  AND indexname IN (
    'uq_pipeline_runs_business_date_step_name',
    'ix_pipeline_runs_business_date_status'
  )
ORDER BY indexname;
```

Expected columns:

```text
business_date
completed_at
error_message
started_at
status
step_name
```

Expected indexes:

```text
ix_pipeline_runs_business_date_status
uq_pipeline_runs_business_date_step_name
```

### Revision 014

File:

```text
alembic/versions/014_create_recommendation_decision_journal.py
```

Purpose:

- Create recommendation decision journal for explanation snapshots.

Tables affected:

- creates `recommendation_decision_journal`

Columns added:

- `journal_id`
- `business_date`
- `symbol`
- `rank`
- `score`
- `recommendation_type`
- `sector`
- `feature_snapshot_json`
- `created_at`

Indexes added:

- `ix_recommendation_decision_journal_symbol_date`
- `ix_recommendation_decision_journal_date_rank`

Constraints added:

- `uq_recommendation_decision_journal_date_symbol_type`

Data migration impact:

- Creates empty journal table.
- Does not backfill explanation snapshots.

Rollback risk:

- Downgrade drops the journal table.
- Any captured recommendation explanation snapshots would be lost.

Validation SQL:

```sql
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_name = 'recommendation_decision_journal';

SELECT column_name
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name = 'recommendation_decision_journal'
ORDER BY ordinal_position;
```

Expected:

```text
recommendation_decision_journal
```

## Validation SQL After Each Step

After every migration:

```sql
SELECT version_num FROM alembic_version;
```

Expected value should match the revision just applied.

After `008`:

```sql
SELECT COUNT(*)
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name = 'daily_scores'
  AND column_name IN ('swing_v2_score', 'position_v2_score');
```

Expected:

```text
2
```

After `009`:

```sql
SELECT COUNT(*)
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name = 'daily_scores'
  AND column_name = 'swing_v2_1_score';
```

Expected:

```text
1
```

After `010`:

```sql
SELECT COUNT(*)
FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_name = 'security_master';
```

Expected:

```text
1
```

After `011`:

```sql
SELECT COUNT(*)
FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_name IN ('security_symbol_alias', 'security_corporate_action_lineage');
```

Expected:

```text
2
```

After `012`:

```sql
SELECT COUNT(*)
FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_name IN (
    'paper_portfolios',
    'paper_positions',
    'paper_trades',
    'paper_daily_snapshots'
  );
```

Expected:

```text
4
```

After `013`:

```sql
SELECT COUNT(*)
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name = 'pipeline_runs'
  AND column_name IN (
    'business_date',
    'step_name',
    'started_at',
    'completed_at'
  );
```

Expected:

```text
4
```

After `014`:

```sql
SELECT COUNT(*)
FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_name = 'recommendation_decision_journal';
```

Expected:

```text
1
```

## Rollback Procedure

Rollback should be staged and stop at the last known good revision.

Example rollback from `014` to `013`:

```powershell
alembic downgrade 013
```

Example rollback from `014` to current original state:

```powershell
alembic downgrade 007
```

Before any rollback after application use, export affected tables:

```sql
COPY recommendation_decision_journal TO STDOUT WITH CSV HEADER;
COPY paper_daily_snapshots TO STDOUT WITH CSV HEADER;
COPY paper_trades TO STDOUT WITH CSV HEADER;
COPY paper_positions TO STDOUT WITH CSV HEADER;
COPY paper_portfolios TO STDOUT WITH CSV HEADER;
```

Rollback data-loss summary:

| Downgrade past revision | Data/infrastructure removed |
| --- | --- |
| `014` | recommendation decision journal snapshots |
| `013` | Phase 4B pipeline step fields and indexes |
| `012` | paper portfolios, positions, trades, snapshots |
| `011` | security alias and lineage tables |
| `010` | security master table |
| `009` | `daily_scores.swing_v2_1_score` |
| `008` | `daily_scores.swing_v2_score`, `daily_scores.position_v2_score` |

## Post-Upgrade Smoke Tests

After reaching revision `014`, restart the API and run:

```powershell
Invoke-WebRequest http://127.0.0.1:8000/health -UseBasicParsing
Invoke-WebRequest http://127.0.0.1:8000/recommendations/latest?model=swing_v2_1"&"limit=5 -UseBasicParsing
Invoke-WebRequest http://127.0.0.1:8000/pipeline/status -UseBasicParsing
Invoke-WebRequest http://127.0.0.1:8000/portfolio -UseBasicParsing
```

Expected:

- `/health` returns a JSON response rather than failing on missing tables.
- `/recommendations/latest` continues returning live Angel recommendations.
- `/pipeline/status` no longer fails because `business_date` is missing.
- `/portfolio` no longer fails because paper tables are absent.
- `/portfolio` may still be empty until a paper portfolio is initialized.

Frontend smoke test:

```powershell
Invoke-WebRequest http://127.0.0.1:3000/ -UseBasicParsing
Invoke-WebRequest http://127.0.0.1:3000/recommendations -UseBasicParsing
Invoke-WebRequest http://127.0.0.1:3000/portfolio -UseBasicParsing
Invoke-WebRequest http://127.0.0.1:3000/operations -UseBasicParsing
Invoke-WebRequest http://127.0.0.1:3000/research -UseBasicParsing
```

Expected:

- All frontend routes return HTTP 200.
- Dashboard and Operations may show degraded state until a pipeline run is recorded.
- Portfolio may show empty state until a paper portfolio exists.

## Go / No-Go Checklist

Go only if all are true:

- Backup exists and restore path is known.
- `DATABASE_URL` points to `nse_research_platform`, not `angel_data`.
- `alembic current` returns `007`.
- API/pipeline processes are stopped.
- No manual schema changes are pending outside Alembic.

No-go if any are true:

- Backup is missing.
- Alembic current revision is not `007`.
- `DATABASE_URL` points to the wrong database.
- There are unreviewed manually created versions of `paper_*`, `security_*`, or `recommendation_decision_journal` tables.
- The application is actively writing to the research database.

## Final Recommendation

Use staged migration execution from `008` through `014`, with validation after each revision.

Do not manually create tables. Do not skip intermediate revisions. Do not run paper trading writes until the upgrade reaches `014` and smoke tests pass.
