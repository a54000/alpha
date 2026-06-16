# Phase 1A Implementation

Objective: create the Security Master foundation.

Scope implemented:

- Added Phase 1A migration.
- Added ORM model.
- Added schema test coverage.
- Did not modify existing production tables.
- Did not migrate existing data.
- Did not cut over existing code paths.
- Did not implement aliases, lineage, or NSE500 membership history.

## Delivered Files

- `alembic/versions/010_create_security_master.py`
- `db/models.py`
- `tests/test_database_schema.py`
- `docs/PHASE1A_IMPLEMENTATION.md`

## New Table

### `security_master`

Purpose: one row per canonical security lineage node.

Columns:

| Column | Type | Notes |
| --- | --- | --- |
| `security_id` | integer | Primary key, autoincrement |
| `canonical_symbol` | varchar(40) | Required display/current symbol |
| `canonical_name` | text | Optional display name |
| `isin_current` | varchar(20) | Optional current ISIN |
| `exchange` | varchar(20) | Required, default `NSE` |
| `instrument_type` | varchar(30) | Required, default `equity` |
| `status` | varchar(30) | Required, default `active` |
| `first_seen_date` | date | Optional |
| `last_seen_date` | date | Optional |
| `created_from_source` | varchar(50) | Optional |
| `review_status` | varchar(30) | Required, default `pending` |
| `notes` | text | Optional |
| `created_at` | timestamp | Optional |
| `updated_at` | timestamp | Optional |

Constraints and indexes:

- Primary key on `security_id`
- Check constraint on `status`
- Check constraint on `review_status`
- Check constraint that `last_seen_date >= first_seen_date` when both are present
- Index on `canonical_symbol`
- Index on `status`
- Index on `review_status`
- Partial unique index on `(exchange, isin_current)` where `isin_current IS NOT NULL`

## Migration

Revision:

```text
010_create_security_master
```

Alembic metadata:

```text
revision = "010"
down_revision = "009"
```

Upgrade creates only `security_master` and its indexes/constraints.

Downgrade drops only `security_master` and its indexes.

## Validation Queries

Run after upgrade:

```sql
SELECT table_name
FROM information_schema.tables
WHERE table_name = 'security_master';
```

Expected:

```text
security_master
```

Check columns:

```sql
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'security_master'
ORDER BY ordinal_position;
```

Check row count:

```sql
SELECT COUNT(*) AS security_master_rows
FROM security_master;
```

Expected for Phase 1A:

```text
0
```

Check existing production tables were not structurally changed by this migration:

```sql
SELECT table_name
FROM information_schema.tables
WHERE table_name IN (
  'symbol_master',
  'prices_daily',
  'features_daily',
  'daily_scores',
  'recommendation_history',
  'security_master'
)
ORDER BY table_name;
```

Check constraints:

```sql
SELECT conname
FROM pg_constraint
WHERE conrelid = 'security_master'::regclass
ORDER BY conname;
```

Check indexes:

```sql
SELECT indexname
FROM pg_indexes
WHERE tablename = 'security_master'
ORDER BY indexname;
```

## Upgrade Commands

For a database already at revision `009`:

```powershell
.\.venv\Scripts\alembic.exe upgrade head
```

or:

```powershell
.\.venv\Scripts\alembic.exe upgrade 010
```

Important live database note:

The local PostgreSQL database was observed at Alembic revision `007` during implementation. Upgrading that database directly to `head` would also apply older migrations `008` and `009`, which alter existing production tables. That is outside Phase 1A scope. Bring the database to `009` through the already-approved historical migration path before applying Phase 1A to live PostgreSQL.

## Downgrade Commands

From revision `010` back to `009`:

```powershell
.\.venv\Scripts\alembic.exe downgrade 009
```

Then re-upgrade:

```powershell
.\.venv\Scripts\alembic.exe upgrade 010
```

## Rollback Instructions

Preferred rollback:

```powershell
.\.venv\Scripts\alembic.exe downgrade 009
```

Manual emergency rollback:

```sql
DROP TABLE IF EXISTS security_master;
```

Because Phase 1A does not migrate data or alter production tables, rollback removes only the new empty foundation table.

## Verification Performed

Migration round-trip on isolated SQLite migration database:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_migrations.py --basetemp D:\nse-research-app\.pytest_tmp
```

Result:

```text
1 passed
```

ORM/schema validation:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_database_schema.py
```

Result:

```text
3 passed
```

Package import validation:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_package_imports.py
```

Result during implementation:

```text
1 passed
```

## Existing Application Behavior

No existing code path reads `security_master`.

No existing production table was altered by revision `010`.

No ETL, scoring, recommendation, backtest, or dashboard code was cut over to `security_id`.

## Not Implemented In Phase 1A

- `security_symbol_alias`
- `security_corporate_action_lineage`
- `index_membership_snapshot`
- `index_membership_range`
- `security_id` columns on prices/features/scores/recommendations
- Alias seeding
- NSE500 membership backfill
- Angel data aggregation
- Swing V2.1 rerun
