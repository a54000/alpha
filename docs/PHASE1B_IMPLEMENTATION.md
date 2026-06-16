# Phase 1B Implementation

Objective: create alias and symbol-lineage infrastructure.

Scope implemented:

- Added Phase 1B migration.
- Added ORM models.
- Added schema and constraint test coverage.
- Did not modify existing production tables.
- Did not migrate existing symbol data.
- Did not perform alias reconciliation.
- Did not cut over application code.
- Did not integrate Angel data.

## Delivered Files

- `alembic/versions/011_create_security_alias_and_lineage.py`
- `db/models.py`
- `tests/test_database_schema.py`
- `docs/PHASE1B_IMPLEMENTATION.md`

## New Tables

### `security_symbol_alias`

Purpose: source-specific symbol aliases with validity dates.

Columns:

| Column | Type | Notes |
| --- | --- | --- |
| `alias_id` | integer | Primary key, autoincrement |
| `security_id` | integer | Foreign key to `security_master.security_id` |
| `source` | varchar(30) | research, angel, nse, yfinance, manual |
| `symbol` | varchar(40) | Source symbol |
| `normalized_symbol` | varchar(40) | Matching helper only |
| `valid_from` | date | Optional |
| `valid_to` | date | Optional |
| `is_primary_for_source` | boolean | Default false |
| `alias_reason` | varchar(40) | exact, rename, vendor_format, etc. |
| `confidence` | varchar(20) | pending, low, medium, high, approved, rejected |
| `review_status` | varchar(30) | pending, approved, rejected, needs_review, pending_dates |
| `notes` | text | Optional |
| `created_at` | timestamp | Optional |
| `updated_at` | timestamp | Optional |

Constraints and indexes:

- Foreign key to `security_master`
- Unique constraint on `(source, symbol, valid_from)`
- Check constraint on source values
- Check constraint on alias reason values
- Check constraint on confidence values
- Check constraint on review status values
- Check constraint that `valid_to >= valid_from` when both are present
- Index on `(source, symbol)`
- Index on `(security_id, valid_from, valid_to)`
- Index on `normalized_symbol`
- Index on `review_status`

### `security_corporate_action_lineage`

Purpose: explicit security-to-security event lineage.

Columns:

| Column | Type | Notes |
| --- | --- | --- |
| `event_id` | integer | Primary key, autoincrement |
| `event_date` | date | Optional |
| `event_type` | varchar(40) | rename, merger, demerger, etc. |
| `from_security_id` | integer | Optional foreign key to `security_master` |
| `to_security_id` | integer | Optional foreign key to `security_master` |
| `ratio` | numeric(18,8) | Optional |
| `source_reference` | text | Optional |
| `review_status` | varchar(30) | pending, approved, rejected, needs_review, pending_dates |
| `notes` | text | Optional |
| `created_at` | timestamp | Optional |
| `updated_at` | timestamp | Optional |

Constraints and indexes:

- Foreign keys to `security_master`
- Check constraint on event type values
- Check constraint on review status values
- Check constraint requiring at least one of `from_security_id` or `to_security_id`
- Index on `event_date`
- Index on `from_security_id`
- Index on `to_security_id`
- Index on `review_status`

## Migration

Revision:

```text
011_create_security_alias_and_lineage
```

Alembic metadata:

```text
revision = "011"
down_revision = "010"
```

Upgrade creates only:

- `security_symbol_alias`
- `security_corporate_action_lineage`

Downgrade drops only those two Phase 1B tables and their indexes.

## Validation SQL

Run after upgrade:

```sql
SELECT table_name
FROM information_schema.tables
WHERE table_name IN (
  'security_master',
  'security_symbol_alias',
  'security_corporate_action_lineage'
)
ORDER BY table_name;
```

Expected:

```text
security_corporate_action_lineage
security_master
security_symbol_alias
```

Check Phase 1B tables are empty:

```sql
SELECT COUNT(*) AS alias_rows FROM security_symbol_alias;
SELECT COUNT(*) AS lineage_rows FROM security_corporate_action_lineage;
```

Expected for infrastructure-only Phase 1B:

```text
0
0
```

Check alias columns:

```sql
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'security_symbol_alias'
ORDER BY ordinal_position;
```

Check lineage columns:

```sql
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'security_corporate_action_lineage'
ORDER BY ordinal_position;
```

Check constraints:

```sql
SELECT conname
FROM pg_constraint
WHERE conrelid IN (
  'security_symbol_alias'::regclass,
  'security_corporate_action_lineage'::regclass
)
ORDER BY conname;
```

Check indexes:

```sql
SELECT tablename, indexname
FROM pg_indexes
WHERE tablename IN (
  'security_symbol_alias',
  'security_corporate_action_lineage'
)
ORDER BY tablename, indexname;
```

Check existing production tables were not structurally changed by Phase 1B:

```sql
SELECT table_name
FROM information_schema.tables
WHERE table_name IN (
  'symbol_master',
  'prices_daily',
  'features_daily',
  'daily_scores',
  'recommendation_history'
)
ORDER BY table_name;
```

## Upgrade Commands

For a database already at revision `010`:

```powershell
.\.venv\Scripts\alembic.exe upgrade 011
```

or:

```powershell
.\.venv\Scripts\alembic.exe upgrade head
```

Important:

Only use `upgrade head` if the database is already at `010`. If the database is still at `007`, `upgrade head` also applies `008`, `009`, and `010`.

## Downgrade Commands

From revision `011` back to `010`:

```powershell
.\.venv\Scripts\alembic.exe downgrade 010
```

Then re-upgrade:

```powershell
.\.venv\Scripts\alembic.exe upgrade 011
```

## Rollback Instructions

Preferred rollback:

```powershell
.\.venv\Scripts\alembic.exe downgrade 010
```

Manual emergency rollback:

```sql
DROP TABLE IF EXISTS security_corporate_action_lineage;
DROP TABLE IF EXISTS security_symbol_alias;
```

Because Phase 1B does not seed aliases or lineage rows, rollback should remove only empty infrastructure tables immediately after deployment.

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
4 passed
```

## Existing Application Behavior

No existing code path reads or writes:

- `security_symbol_alias`
- `security_corporate_action_lineage`

No existing production table was altered by revision `011`.

No ETL, scoring, recommendation, backtest, or dashboard code was cut over to alias or lineage tables.

## Not Implemented In Phase 1B

- Alias seeding
- Alias reconciliation
- Angel symbol integration
- Corporate-action event population
- `security_id` columns on production tables
- NSE500 membership history
- Daily-bar aggregation
- Feature recomputation
- Swing V2.1 rerun
