# Implementation Roadmap Phase 1

Objective: convert the approved Universe Reconstruction Plan into an executable implementation roadmap.

Scope:

- Roadmap only.
- Do not implement.
- Do not create migrations.
- Do not modify databases.

Inputs:

- `docs/UNIVERSE_RECONSTRUCTION_PLAN.md`
- `docs/ANGEL_SYMBOL_MASTER_FORENSICS.md`
- `docs/ANGEL_SYMBOL_MAPPING_AUDIT.md`

## Phase 1 Overview

Phase 1 creates the identity and universe foundation needed before historical Angel data can be safely aggregated, loaded, or backtested.

Subphases:

- Phase 1A: Security Master Implementation
- Phase 1B: Alias & Symbol Lineage Implementation
- Phase 1C: NSE500 Membership History Framework

Execution principle:

Build new identity and universe structures in parallel with existing `symbol_master`. Do not replace current model inputs until validation proves equivalence or explains differences.

## Global Preconditions

Before implementation starts:

1. Freeze Swing V2.1 model logic.
2. Preserve current reports and backtest outputs as baseline artifacts.
3. Confirm current PostgreSQL backup exists.
4. Confirm `reports/angel_symbol_mapping.csv` is current.
5. Confirm no ETL job will rebuild prices/features during schema migration.

Recommended backup:

```powershell
pg_dump --format=custom --file backups/nse_research_platform_before_phase1.dump nse_research_platform
```

## Phase 1A: Security Master Implementation

Goal: create a stable internal security identity layer without changing existing research behavior.

### 1. Database Changes

Add new security identity tables.

No existing tables should be altered in the first migration except optional metadata comments.

### 2. New Tables

#### `security_master`

Purpose: one row per canonical security lineage node.

Proposed columns:

- `security_id` bigint primary key
- `canonical_symbol` varchar(40) not null
- `canonical_name` text
- `isin_current` varchar(20)
- `exchange` varchar(20) not null default `NSE`
- `instrument_type` varchar(30) not null default `equity`
- `status` varchar(30) not null default `active`
- `first_seen_date` date
- `last_seen_date` date
- `created_from_source` varchar(50)
- `review_status` varchar(30) not null default `pending`
- `notes` text
- `created_at` timestamp
- `updated_at` timestamp

Recommended constraints:

- Unique nullable index on `(exchange, isin_current)` where `isin_current is not null`.
- Index on `canonical_symbol`.
- Check constraint for `status`.
- Check constraint for `review_status`.

### 3. New Columns

None in existing production tables for Phase 1A.

### 4. Migration Sequence

1. Create migration `010_create_security_master`.
2. Create `security_master`.
3. Add constraints and indexes.
4. Deploy migration.
5. Run a separate read-only/staging seed script to propose security rows from:
   - `symbol_master`
   - Angel symbols
   - NSE current equity list
6. Review seed output before inserting into production table.
7. Insert approved initial security rows only after review.

Important: the seed step should be a script, not embedded into the schema migration.

### 5. Validation Checks

Schema validation:

- `security_master` exists.
- Primary key exists.
- Check constraints exist.
- No duplicate `(exchange, isin_current)` where ISIN is present.

Data validation after seed:

- Every `symbol_master.symbol` has either a proposed `security_id` or a review exception.
- Every exact Angel/research match has one proposed security row, not two.
- `canonical_symbol` preserves official NSE punctuation.
- No two active security rows share the same canonical symbol unless explicitly allowed and reviewed.

### 6. Rollback Strategy

Migration rollback:

- Drop `security_master`.

Data rollback:

- Truncate seeded `security_master` rows before dropping if needed.
- Existing `symbol_master`, prices, features, scores, and recommendations remain untouched.

Operational rollback:

- Disable any new scripts that read `security_master`.
- Continue using existing symbol-based workflow.

### 7. Estimated Effort

- Schema migration: 0.5 day
- Seed proposal script: 1 day
- Manual review of initial rows: 1-2 days
- Tests and validation: 1 day

Estimated total: 3-5 working days.

### 8. Dependencies

- Current `symbol_master`
- Angel symbol list
- NSE current equity list
- `reports/angel_symbol_mapping.csv`
- PostgreSQL backup

## Phase 1B: Alias & Symbol Lineage Implementation

Goal: model source-specific symbols, renames, vendor naming differences, and corporate-action lineage without overwriting symbols in place.

### 1. Database Changes

Add alias and lineage tables.

Existing production tables remain unchanged in this phase.

### 2. New Tables

#### `security_symbol_alias`

Purpose: source-specific symbol aliases with validity dates.

Proposed columns:

- `alias_id` bigint primary key
- `security_id` bigint not null references `security_master(security_id)`
- `source` varchar(30) not null
- `symbol` varchar(40) not null
- `normalized_symbol` varchar(40) not null
- `valid_from` date
- `valid_to` date
- `is_primary_for_source` boolean not null default false
- `alias_reason` varchar(40) not null
- `confidence` varchar(20) not null default `pending`
- `review_status` varchar(30) not null default `pending`
- `notes` text
- `created_at` timestamp
- `updated_at` timestamp

Recommended constraints:

- Foreign key to `security_master`.
- Unique constraint on `(source, symbol, valid_from)`.
- Check `valid_to is null or valid_to >= valid_from`.
- Check constraints for `source`, `alias_reason`, `confidence`, and `review_status`.
- Index on `(source, symbol)`.
- Index on `(security_id, valid_from, valid_to)`.
- Index on `normalized_symbol`.

#### `security_corporate_action_lineage`

Purpose: explicit relationships between security identities.

Proposed columns:

- `event_id` bigint primary key
- `event_date` date
- `event_type` varchar(40) not null
- `from_security_id` bigint references `security_master(security_id)`
- `to_security_id` bigint references `security_master(security_id)`
- `ratio` numeric(18,8)
- `source_reference` text
- `review_status` varchar(30) not null default `pending`
- `notes` text
- `created_at` timestamp
- `updated_at` timestamp

Recommended constraints:

- At least one of `from_security_id` or `to_security_id` is not null.
- Check constraints for `event_type` and `review_status`.
- Index on `event_date`.
- Index on `from_security_id`.
- Index on `to_security_id`.

### 3. New Columns

None in existing production price/feature/scoring tables yet.

Optional later columns, not Phase 1B:

- `prices_daily.security_id`
- `features_daily.security_id`
- `daily_scores.security_id`
- `recommendation_history.security_id`

These should be deferred until alias validation passes.

### 4. Migration Sequence

1. Create migration `011_create_security_alias_and_lineage`.
2. Create `security_symbol_alias`.
3. Create `security_corporate_action_lineage`.
4. Add indexes and constraints.
5. Deploy migration.
6. Generate alias proposal file from `reports/angel_symbol_mapping.csv`.
7. Insert only approved alias classes:
   - `exact`
   - reviewed `known_rename`
8. Keep `potential`, `ambiguous`, and unresolved `unmatched` cases in a review file, not production aliases.
9. Insert lineage rows only for reviewed corporate actions.

### 5. Validation Checks

Alias validation:

- Every `exact` mapping has one research alias and one Angel alias pointing to the same `security_id`.
- Each `known_rename` has validity dates or explicit `review_status = pending_dates`.
- No `ambiguous` mapping is inserted as approved.
- No alias has overlapping date ranges for the same `source, symbol` unless explicitly reviewed.
- `normalized_symbol` is derived consistently.

Lineage validation:

- Rename events connect one security continuity or one alias transition, according to the reviewed rule.
- Demergers and mergers are represented as lineage events, not simple alias replacements.
- `PEL`, `JUBILANT`, `MAXINDIA`, `HDFC`, and similar cases stay pending until reviewed.

Cross-source validation:

- `KALPATPOWR -> KPIL`
- `WABCOINDIA -> ZFCVINDIA`
- `SRTRANSFIN -> SHRIRAMFIN`
- `TATAGLOBAL -> TATACONSUM`
- `INFRATEL -> INDUSTOWER`
- `RNAM -> NAM-INDIA`
- `MAHINDCIE -> CIEINDIA`

These should resolve as known rename aliases only after review dates are attached.

### 6. Rollback Strategy

Migration rollback:

- Drop `security_corporate_action_lineage`.
- Drop `security_symbol_alias`.

Data rollback:

- Delete rows by migration/seed batch id if batch metadata is added.
- Otherwise truncate alias and lineage tables.

Operational rollback:

- Existing pipeline remains symbol-based.
- New alias tables are ignored by production jobs until cutover.

### 7. Estimated Effort

- Schema migration: 1 day
- Alias proposal loader: 1-2 days
- Review workflow/reporting: 1-2 days
- Validation tests: 1-2 days
- Manual review: 2-5 days depending on unresolved symbols

Estimated total: 6-11 working days.

### 8. Dependencies

- Phase 1A completed.
- Approved initial `security_master` rows.
- Current `reports/angel_symbol_mapping.csv`.
- Manual review policy for renames, mergers, demergers, and delistings.
- Access to NSE/BSE corporate-action references or trusted symbol-history data.

## Phase 1C: NSE500 Membership History Framework

Goal: support point-in-time NSE500 membership and remove dependence on `symbol_master.nse500 = true` as a historical universe proxy.

### 1. Database Changes

Add membership snapshot and derived range tables.

Do not alter recommendation, scoring, or backtest logic in this phase.

### 2. New Tables

#### `index_membership_snapshot`

Purpose: raw point-in-time index constituent membership.

Proposed columns:

- `snapshot_date` date not null
- `index_name` varchar(30) not null
- `security_id` bigint references `security_master(security_id)`
- `symbol_as_published` varchar(40) not null
- `company_name_as_published` text
- `source` varchar(50) not null
- `source_file_hash` varchar(128)
- `review_status` varchar(30) not null default `pending`
- `notes` text
- `ingested_at` timestamp

Recommended primary key:

- `(snapshot_date, index_name, symbol_as_published, source)`

Recommended indexes:

- `(index_name, snapshot_date)`
- `(security_id, snapshot_date)`
- `(review_status)`

#### `index_membership_range`

Purpose: derived efficient date-valid universe membership.

Proposed columns:

- `index_name` varchar(30) not null
- `security_id` bigint not null references `security_master(security_id)`
- `valid_from` date not null
- `valid_to` date
- `entry_snapshot_date` date
- `exit_snapshot_date` date
- `derivation_run_id` varchar(80)
- `created_at` timestamp

Recommended constraints:

- Primary key on `(index_name, security_id, valid_from)`.
- Check `valid_to is null or valid_to >= valid_from`.
- Index on `(index_name, valid_from, valid_to)`.
- Index on `(security_id, valid_from, valid_to)`.

### 3. New Columns

None in existing production tables during Phase 1C.

Possible later columns:

- `universe_snapshot.security_id`
- `symbol_master.security_id`

These should be deferred until membership framework validation passes.

### 4. Migration Sequence

1. Create migration `012_create_index_membership_history`.
2. Create `index_membership_snapshot`.
3. Create `index_membership_range`.
4. Add constraints and indexes.
5. Deploy migration.
6. Build a snapshot ingestion script that loads snapshots into staging or new tables.
7. Ingest current NSE500 snapshot first.
8. Compare current snapshot to existing `universe_snapshot`.
9. Ingest one historical snapshot.
10. Derive membership ranges from two or more snapshots.
11. Validate point-in-time membership queries.

### 5. Validation Checks

Snapshot validation:

- Snapshot row count is close to expected NSE500 membership count.
- Every published symbol resolves to a `security_id` or a review exception.
- Source file hash is stored.
- Duplicate published symbols are flagged.

Range validation:

- Current active range count matches current snapshot after review exclusions.
- A new IPO has no membership before listing/snapshot entry date.
- A delisted or removed constituent has `valid_to` populated.
- Membership ranges do not overlap for the same `security_id, index_name`.

Backtest-readiness validation:

- Query can answer: "Which securities were in NSE500 on date D?"
- Query can answer: "Was security X in NSE500 on signal date D?"
- Results differ appropriately across two historical snapshot dates.

### 6. Rollback Strategy

Migration rollback:

- Drop `index_membership_range`.
- Drop `index_membership_snapshot`.

Data rollback:

- Delete snapshots by `source_file_hash` or `ingested_at` batch.
- Rebuild ranges from remaining snapshots.

Operational rollback:

- Continue using existing `universe_snapshot` and `symbol_master.nse500` until new framework is validated.

### 7. Estimated Effort

- Schema migration: 1 day
- Snapshot ingestion script: 1-2 days
- Range derivation script: 1-2 days
- Validation tests: 1-2 days
- Historical source collection: 2-10 days depending on availability

Estimated total: 6-15 working days.

### 8. Dependencies

- Phase 1A completed.
- Phase 1B has enough aliases to resolve current and historical snapshot symbols.
- Trusted source for current and historical NSE500 membership snapshots.
- Policy for unresolved snapshot symbols.

## End-To-End Migration Order

Recommended sequence:

1. Backup current database.
2. Implement Phase 1A schema only.
3. Validate empty `security_master`.
4. Generate security seed proposal.
5. Review and seed approved security rows.
6. Implement Phase 1B schema only.
7. Validate empty alias and lineage tables.
8. Generate alias proposal from mapping CSV.
9. Insert approved exact and reviewed rename aliases.
10. Keep ambiguous/potential/unmatched cases outside production aliases.
11. Implement Phase 1C schema only.
12. Validate empty membership tables.
13. Ingest current NSE500 snapshot.
14. Reconcile current NSE500 snapshot against existing `universe_snapshot`.
15. Ingest at least one historical NSE500 snapshot.
16. Derive membership ranges.
17. Validate point-in-time membership queries.
18. Produce a Phase 1 readiness report.

## Phase 1 Exit Criteria

Phase 1 is complete when:

- `security_master` exists and contains reviewed initial securities.
- Exact research/Angel mappings resolve to one `security_id`.
- Approved rename mappings are represented as aliases with review status and date policy.
- Ambiguous mappings are not silently mapped.
- Current NSE500 snapshot resolves to `security_id` with exceptions documented.
- At least one historical snapshot is represented.
- Membership ranges can answer point-in-time universe queries.
- Existing symbol-based production jobs still run unchanged.

## Explicit Non-Goals

Phase 1 does not:

- Aggregate Angel 15-minute data.
- Load derived daily bars.
- Recompute features.
- Recompute sector ranks.
- Recompute scores.
- Re-run Swing V2.1.
- Change portfolio backtests.
- Replace production joins with `security_id`.

## Main Risks

| Risk | Mitigation |
| --- | --- |
| Incorrect one-to-one mapping across merger/demerger | Require lineage review and validity dates. |
| Breaking existing symbol-based jobs | Keep new tables parallel and unused by production until cutover. |
| Historical NSE500 snapshots unavailable | Start with current snapshot plus any available archival snapshots; document gaps. |
| Overconfidence in normalized symbols | Use normalized symbols only for candidate generation, never canonical identity. |
| Manual review bottleneck | Prioritize exact matches, high-liquidity unmatched names, and high-confidence renames first. |

## Recommended First Implementation Ticket

Title: Create security master schema and seed proposal report.

Deliverables:

- Migration draft for `security_master`.
- Read-only seed proposal script.
- Report listing proposed `security_id`, canonical symbol, source evidence, and review status.
- Tests validating schema constraints.

Do not insert into production until the proposal report is reviewed.
