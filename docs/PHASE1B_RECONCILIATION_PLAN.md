# Phase 1B Reconciliation Plan

Objective: populate the new Security Master infrastructure using existing research symbols and Angel symbols.

Scope:

- Prepare reconciliation process only.
- Dry-run mode only.
- No production inserts.
- No production updates.
- No database writes.
- No application cutover.

Inputs:

- `security_master`
- `security_symbol_alias`
- `reports/angel_symbol_mapping.csv`
- `docs/ANGEL_SYMBOL_MASTER_FORENSICS.md`

## Delivered Script

Dry-run command:

```powershell
.\.venv\Scripts\python.exe scripts\run_phase1b_reconciliation_dry_run.py
```

Script:

- `scripts/run_phase1b_reconciliation_dry_run.py`

Dry-run outputs:

- `reports/phase1b_reconciliation_dry_run.json`
- `reports/phase1b_security_master_proposals.csv`
- `reports/phase1b_alias_proposals.csv`
- `reports/phase1b_manual_review_queue.csv`

The script reads PostgreSQL and CSV inputs, then writes proposal files only. It does not insert, update, or delete database rows.

## Dry-Run Result

Generated on: 2026-06-12.

Summary:

| Metric | Value |
| --- | ---: |
| Mapping CSV rows | 694 |
| Research symbols seen | 501 |
| Angel symbols seen | 499 |
| Proposed `security_master` records | 494 |
| Proposed alias records | 795 |
| Manual-review items | 393 |
| Database writes | 0 |

Mapping status counts:

| Status | Count |
| --- | ---: |
| exact | 285 |
| known_rename | 16 |
| potential | 12 |
| ambiguous | 7 |
| unmatched | 181 |
| angel_only | 193 |

Production-seedable classes in this first pass:

- `exact`
- `known_rename`
- `normalized_match`, if present later

Review-only classes:

- `potential`
- `ambiguous`
- `unmatched`
- `angel_only`

## Initial security_master Records Required

The dry-run proposes one `security_master` record per canonical security candidate.

Rules:

- `exact`: canonical symbol is the research/Angel symbol.
- `known_rename`: canonical symbol is the Angel symbol.
- `normalized_match`: canonical symbol is the Angel symbol.
- `angel_only`: canonical symbol is the Angel symbol, but review is required before production insertion.

Dry-run proposed:

```text
494 security_master records
```

These are proposals only. They should not be inserted until reviewed.

## Alias Records Required

Alias proposal rules:

- `exact`: create one research alias and one Angel alias pointing to the same proposed security.
- `known_rename`: create one research alias and one Angel alias, both marked for review because validity dates are still needed.
- `normalized_match`: create research and Angel aliases marked as vendor-format style mapping.
- `angel_only`: create one Angel alias proposal and put item in manual review.

Dry-run proposed:

```text
795 alias records
```

No aliases were loaded.

## Confidence Levels

| Mapping status | Alias reason | Confidence | Review status |
| --- | --- | --- | --- |
| exact | exact | high | approved |
| known_rename | rename | medium | needs_review |
| normalized_match | vendor_format | medium | needs_review |
| potential | unknown | low | review queue only |
| ambiguous | unknown | pending | review queue only |
| unmatched | unknown | pending | review queue only |
| angel_only | unknown | pending | review queue only |

Important:

- `known_rename` is not final until `valid_from` and `valid_to` are reviewed.
- `angel_only` symbols should not be inserted into production without an NSE500 membership decision.
- `ambiguous` symbols must never be auto-loaded.

## Manual-Review Queue

The dry-run writes:

```text
reports/phase1b_manual_review_queue.csv
```

Queue categories:

- `potential`: high priority because a tempting but weak match exists.
- `ambiguous`: high priority because multiple candidates exist.
- `unmatched`: medium priority because no safe candidate exists.
- `angel_only`: medium priority because these may represent current NSE names missing from the research universe.

Review decisions should be one of:

- approve alias
- reject alias
- needs corporate-action lineage
- exclude from current reconstruction
- pending external evidence

## Safe Loading Order

This is the future production loading order. It has not been executed.

1. Confirm database is at Phase 1B migration head.
2. Backup database.
3. Load only reviewed `security_master` records.
4. Validate `security_master` row counts and duplicate canonical symbols.
5. Load `exact` aliases.
6. Validate `exact` aliases resolve one research and one Angel alias per security.
7. Load reviewed `known_rename` aliases only after validity dates are attached.
8. Keep `potential`, `ambiguous`, `unmatched`, and `angel_only` out of production until reviewed.
9. Produce reconciliation validation report.
10. Do not cut over application code until a separate readiness review.

## Validation Queries

Current infrastructure emptiness check:

```sql
SELECT COUNT(*) AS security_master_rows FROM security_master;
SELECT COUNT(*) AS alias_rows FROM security_symbol_alias;
SELECT COUNT(*) AS lineage_rows FROM security_corporate_action_lineage;
```

Expected before loading:

```text
security_master_rows = 0
alias_rows = 0
lineage_rows = 0
```

After a future reviewed load, validate duplicate current identifiers:

```sql
SELECT exchange, isin_current, COUNT(*)
FROM security_master
WHERE isin_current IS NOT NULL
GROUP BY exchange, isin_current
HAVING COUNT(*) > 1;
```

Validate duplicate source aliases:

```sql
SELECT source, symbol, valid_from, COUNT(*)
FROM security_symbol_alias
GROUP BY source, symbol, valid_from
HAVING COUNT(*) > 1;
```

Validate alias foreign keys:

```sql
SELECT a.alias_id
FROM security_symbol_alias a
LEFT JOIN security_master s ON s.security_id = a.security_id
WHERE s.security_id IS NULL;
```

Validate date order:

```sql
SELECT alias_id, source, symbol, valid_from, valid_to
FROM security_symbol_alias
WHERE valid_to IS NOT NULL
  AND valid_from IS NOT NULL
  AND valid_to < valid_from;
```

Validate unreviewed rename aliases:

```sql
SELECT alias_id, source, symbol, review_status, valid_from, valid_to
FROM security_symbol_alias
WHERE alias_reason = 'rename'
  AND review_status <> 'approved';
```

Validate no application cutover has occurred:

```sql
SELECT table_name, column_name
FROM information_schema.columns
WHERE column_name = 'security_id'
  AND table_name IN (
    'prices_daily',
    'features_daily',
    'daily_scores',
    'recommendation_history'
  );
```

Expected during Phase 1B reconciliation prep:

```text
no rows
```

## Rollback Strategy

Because this phase is dry-run only, rollback means deleting generated proposal files if they are not wanted.

Generated files:

- `reports/phase1b_reconciliation_dry_run.json`
- `reports/phase1b_security_master_proposals.csv`
- `reports/phase1b_alias_proposals.csv`
- `reports/phase1b_manual_review_queue.csv`

No database rollback is required because no database writes occur.

Future production load rollback strategy:

1. Load data with a batch identifier, if batch columns are added later.
2. If no batch identifier exists, snapshot tables before load.
3. Roll back aliases before securities.
4. Never delete a security row that is referenced by aliases or lineage rows.
5. Keep application code on old symbol paths until reconciliation is validated.

## Dry-Run Safety Guarantees

The dry-run script:

- Uses `SELECT` queries only.
- Does not import ORM sessions for insertion.
- Does not call `session.add`.
- Does not call `session.commit`.
- Does not execute `INSERT`, `UPDATE`, `DELETE`, `ALTER`, or `CREATE`.
- Writes only local report files.

## Dependencies

- Phase 1A migration exists.
- Phase 1B migration exists.
- `reports/angel_symbol_mapping.csv` is current.
- `angel_data.ohlcv_15min` is readable.
- Current research database is readable.
- Manual review policy exists for ambiguous and renamed symbols.

## Exit Criteria

This reconciliation prep phase is complete when:

- Dry-run script executes successfully.
- Proposal CSVs are generated.
- Manual-review queue is generated.
- Database row counts remain unchanged.
- No production aliases or securities are inserted.
- Reviewers can inspect proposal files and approve a later controlled load.

## Non-Goals

This phase does not:

- Populate `security_master`.
- Populate `security_symbol_alias`.
- Populate `security_corporate_action_lineage`.
- Reconcile symbols in production.
- Integrate Angel into ETL.
- Add `security_id` to prices, features, scores, or recommendations.
- Rebuild daily bars.
- Re-run backtests.
