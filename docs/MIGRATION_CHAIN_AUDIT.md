# Migration Chain Audit

Objective: audit Alembic revisions `007`, `008`, `009`, and `010`.

Scope:

- Audit only.
- Do not execute migrations.
- Do not modify databases.

Live database context observed during Phase 1A:

```text
alembic current = 007
alembic head = 010
```

Therefore a direct `upgrade head` from the live database would apply `008`, `009`, and `010`.

## Summary Verdict

The migration chain is structurally safe if deployed in stages.

- `007` creates a new benchmark index price table.
- `008` adds nullable V2 score columns to `daily_scores`.
- `009` adds a nullable Swing V2.1 score column to `daily_scores`.
- `010` creates the new Phase 1A `security_master` table.

None of the migrations intentionally modifies existing row data.

Main caution:

- Downgrading `008` or `009` drops score columns and would delete any values stored in those columns.
- Downgrading `007` drops `index_prices_daily` and would delete benchmark index data.
- Downgrading `010` drops `security_master`; currently Phase 1A does not seed data, but future use would make rollback data-destructive unless backed up.

## Revision 007

File:

- `alembic/versions/007_add_index_prices_daily.py`

Revision metadata:

```text
revision = 007
down_revision = 006
```

### Exact Schema Changes

Creates table `index_prices_daily` if it does not already exist.

Columns:

| Column | Type | Nullability | Notes |
| --- | --- | --- | --- |
| `index_name` | `String(20)` | not null | Primary key |
| `date` | `Date` | not null | Primary key |
| `open` | `Numeric(12,2)` | nullable |  |
| `high` | `Numeric(12,2)` | nullable |  |
| `low` | `Numeric(12,2)` | nullable |  |
| `close` | `Numeric(12,2)` | nullable |  |
| `volume` | `Integer` | nullable |  |

Constraints:

- Primary key: `index_name`, `date`
- Unique constraint: `uq_index_prices_daily_index_date` on `index_name`, `date`

### Reversibility

Reversible at schema level.

Downgrade:

- Drops `index_prices_daily` if it exists.

Data risk:

- Downgrade deletes all benchmark index price rows in `index_prices_daily`.

### Production Data Modification

No existing production table rows are modified.

This migration creates a new table only.

### Application-State Dependency

Low.

The migration checks whether the table exists before creating it. It does not depend on existing row values or application code state.

Application compatibility:

- Safe for existing code paths that do not use `index_prices_daily`.
- Required by code paths that expect benchmark index data in the new table.

## Revision 008

File:

- `alembic/versions/008_add_v2_score_columns.py`

Revision metadata:

```text
revision = 008
down_revision = 007
```

### Exact Schema Changes

Adds nullable columns to `daily_scores` if missing:

| Column | Type | Nullability |
| --- | --- | --- |
| `swing_v2_score` | `Numeric(5,1)` | nullable |
| `position_v2_score` | `Numeric(5,1)` | nullable |

### Reversibility

Reversible at schema level.

Downgrade:

- Drops `position_v2_score` if present.
- Drops `swing_v2_score` if present.

Data risk:

- Downgrade deletes any stored V2 score values.

### Production Data Modification

No existing row data is updated, deleted, or inserted.

However, this migration alters existing production table `daily_scores`.

Because both columns are nullable, upgrade should not require a backfill and should not block existing rows.

### Application-State Dependency

Low to medium.

The migration does not depend on row state, but application code that writes or reads V2 score columns depends on this migration being applied.

Safe for existing V1 code paths because nullable columns do not change existing column semantics.

## Revision 009

File:

- `alembic/versions/009_add_swing_v2_1_score.py`

Revision metadata:

```text
revision = 009
down_revision = 008
```

### Exact Schema Changes

Adds nullable column to `daily_scores` if missing:

| Column | Type | Nullability |
| --- | --- | --- |
| `swing_v2_1_score` | `Numeric(5,1)` | nullable |

### Reversibility

Reversible at schema level.

Downgrade:

- Drops `swing_v2_1_score` if present.

Data risk:

- Downgrade deletes any stored Swing V2.1 score values.

### Production Data Modification

No existing row data is updated, deleted, or inserted.

However, this migration alters existing production table `daily_scores`.

Because the column is nullable, upgrade should not require a backfill and should not block existing rows.

### Application-State Dependency

Low to medium.

The migration does not depend on row state, but any code that reads or writes `swing_v2_1_score` requires this migration.

Safe for existing code paths that ignore the new column.

## Revision 010

File:

- `alembic/versions/010_create_security_master.py`

Revision metadata:

```text
revision = 010
down_revision = 009
```

### Exact Schema Changes

Creates table `security_master` if it does not already exist.

Columns:

| Column | Type | Nullability | Default |
| --- | --- | --- | --- |
| `security_id` | `Integer` | not null | autoincrement primary key |
| `canonical_symbol` | `String(40)` | not null | none |
| `canonical_name` | `Text` | nullable | none |
| `isin_current` | `String(20)` | nullable | none |
| `exchange` | `String(20)` | not null | `NSE` |
| `instrument_type` | `String(30)` | not null | `equity` |
| `status` | `String(30)` | not null | `active` |
| `first_seen_date` | `Date` | nullable | none |
| `last_seen_date` | `Date` | nullable | none |
| `created_from_source` | `String(50)` | nullable | none |
| `review_status` | `String(30)` | not null | `pending` |
| `notes` | `Text` | nullable | none |
| `created_at` | `DateTime` | nullable | none |
| `updated_at` | `DateTime` | nullable | none |

Constraints:

- Primary key on `security_id`
- `ck_security_master_status`
- `ck_security_master_review_status`
- `ck_security_master_seen_date_order`

Indexes:

- `ix_security_master_canonical_symbol`
- `ix_security_master_status`
- `ix_security_master_review_status`
- `uq_security_master_exchange_isin_current`, unique partial index where `isin_current IS NOT NULL`

### Reversibility

Reversible at schema level.

Downgrade:

- Drops indexes.
- Drops `security_master`.

Data risk:

- Downgrade deletes any `security_master` rows if data has been inserted.
- Under current Phase 1A scope, no data is seeded, so rollback should be low risk immediately after deployment.

### Production Data Modification

No existing production tables are altered.

No existing row data is updated, deleted, or inserted.

This migration creates a new table only.

### Application-State Dependency

Low.

The migration does not depend on existing application state.

Existing code paths do not read `security_master`, so deploying `010` should not change application behavior.

## Chain-Level Observations

### Idempotency Guards

All four migrations include schema-inspection guards:

- `007`: checks table existence.
- `008`: checks column existence.
- `009`: checks column existence.
- `010`: checks table existence.

This reduces risk when local environments have drift, but it does not replace proper Alembic revision control.

### Reversibility

All four migrations include downgrades.

Reversibility is schema-level only. Downgrades for `007`, `008`, `009`, and `010` can delete data stored in objects introduced by those revisions.

### Production Data Modification

None of the migrations runs `UPDATE`, `DELETE`, `INSERT`, or data backfill SQL.

Schema impact:

- `007`: new table only.
- `008`: alters existing production table `daily_scores`.
- `009`: alters existing production table `daily_scores`.
- `010`: new table only.

### Application-State Dependencies

No migration depends on specific row counts, data values, model versions, or pipeline state.

Application-code dependencies are forward-facing:

- V2 scoring code expects `008`.
- Swing V2.1 score code expects `009`.
- Security master Phase 1A code/docs expect `010`.

## Safe Upgrade Path From Live Revision 007

Because live is at `007`, do not jump blindly to `head` without acknowledging that `008` and `009` alter `daily_scores`.

Recommended staged path:

### Stage 0: Preflight

Commands:

```powershell
.\.venv\Scripts\alembic.exe current
.\.venv\Scripts\alembic.exe heads
```

Expected:

```text
current = 007
head = 010
```

Backup:

```powershell
pg_dump --format=custom --file backups/nse_research_platform_before_008_010.dump nse_research_platform
```

Preflight validation SQL:

```sql
SELECT column_name
FROM information_schema.columns
WHERE table_name = 'daily_scores'
  AND column_name IN ('swing_v2_score', 'position_v2_score', 'swing_v2_1_score')
ORDER BY column_name;
```

Expected before `008`/`009`:

- Either no rows, or rows if schema drift already exists.

### Stage 1: Apply Revision 008

Command:

```powershell
.\.venv\Scripts\alembic.exe upgrade 008
```

Validate:

```sql
SELECT column_name, numeric_precision, numeric_scale, is_nullable
FROM information_schema.columns
WHERE table_name = 'daily_scores'
  AND column_name IN ('swing_v2_score', 'position_v2_score')
ORDER BY column_name;
```

Rollback if needed:

```powershell
.\.venv\Scripts\alembic.exe downgrade 007
```

Caution: rollback drops the two V2 score columns and any data in them.

### Stage 2: Apply Revision 009

Command:

```powershell
.\.venv\Scripts\alembic.exe upgrade 009
```

Validate:

```sql
SELECT column_name, numeric_precision, numeric_scale, is_nullable
FROM information_schema.columns
WHERE table_name = 'daily_scores'
  AND column_name = 'swing_v2_1_score';
```

Rollback if needed:

```powershell
.\.venv\Scripts\alembic.exe downgrade 008
```

Caution: rollback drops `swing_v2_1_score` and any data in it.

### Stage 3: Apply Revision 010

Command:

```powershell
.\.venv\Scripts\alembic.exe upgrade 010
```

Validate:

```sql
SELECT table_name
FROM information_schema.tables
WHERE table_name = 'security_master';
```

```sql
SELECT COUNT(*) AS security_master_rows
FROM security_master;
```

Expected:

```text
security_master_rows = 0
```

Rollback if needed:

```powershell
.\.venv\Scripts\alembic.exe downgrade 009
```

Caution: rollback drops `security_master`.

## Recommended Staged Deployment Sequence

1. Announce schema maintenance window.
2. Confirm application is not running an ETL or score recomputation job.
3. Take PostgreSQL backup.
4. Run `alembic current` and confirm `007`.
5. Apply `008`.
6. Validate `daily_scores.swing_v2_score` and `daily_scores.position_v2_score`.
7. Smoke-test existing dashboard/backtest import paths.
8. Apply `009`.
9. Validate `daily_scores.swing_v2_1_score`.
10. Smoke-test Swing V2.1 scripts that expect the column.
11. Apply `010`.
12. Validate empty `security_master`.
13. Run focused tests:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_database_schema.py
.\.venv\Scripts\python.exe -m pytest tests/test_package_imports.py
```

14. Record migration version:

```powershell
.\.venv\Scripts\alembic.exe current
```

Expected final:

```text
010
```

## Recommendation

Proceed with staged upgrades rather than a blind `upgrade head`.

The safest path from live `007` is:

```text
007 -> 008 -> validate -> 009 -> validate -> 010 -> validate
```

This separates the production-table changes in `008` and `009` from the new-table-only Phase 1A change in `010`.

No data migration should be run as part of this chain. Seed or reconciliation scripts for `security_master` should remain a later, separately reviewed step.
