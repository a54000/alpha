# Universe Reconstruction Plan

Objective: design a canonical security master for the NSE Research Platform.

Scope:

- Architecture proposal only.
- Do not modify databases.
- Do not create tables.
- Do not run migrations.
- Do not rebuild data.

Inputs used:

- Existing `symbol_master`
- Angel universe from `angel_data.ohlcv_15min`
- `reports/angel_symbol_mapping.csv`
- `docs/ANGEL_SYMBOL_MASTER_FORENSICS.md`
- NSE current equity list research
- `docs/SURVIVORSHIP_BIAS_ASSESSMENT.md`

## Executive Proposal

The platform should stop treating `symbol` as the canonical security identity.

The canonical identity should be a stable internal `security_id`, with exchange/vendor symbols stored as time-valid aliases. NSE500 membership should be represented as dated snapshots and/or validity ranges, not as a static boolean.

Target principles:

- `security_id` identifies the economic security through time.
- `symbol` identifies how a security traded on a specific venue/vendor during a specific date range.
- `isin` should be captured when available, but should not be the sole primary identifier because ISIN can change across certain corporate actions.
- Corporate-action lineage should be explicit, not inferred from string replacement.
- Universe membership should be point-in-time and reproducible.

## Why This Is Needed

Current findings:

- Current `symbol_master` has 501 NSE500 symbols but no populated `nse500_from_date` or `nse500_to_date`.
- `universe_snapshot` has only one snapshot date.
- Angel has 499 symbols and all 193 Angel-only symbols validate as current NSE-listed.
- Current raw research-to-Angel mapping coverage is 313 of 501, or 62.48%.
- The low mapping coverage is mostly caused by stale research universe, corporate-action lineage, and missing aliases, not broad Angel data absence.

This creates two risks:

- Survivorship bias: historical tests use a current/static universe rather than true point-in-time membership.
- Symbol identity drift: renamed, merged, demerged, or delisted securities are misclassified as missing data.

## Canonical Security Identifier

Recommended canonical identifier:

```text
security_id
```

Properties:

- Internal immutable surrogate key.
- Never reused.
- Assigned once per economic security lineage node.
- Used as the future primary join key for prices, features, scores, recommendations, and portfolio results.

Recommended supporting identifiers:

- `isin`: official identifier when available.
- `exchange`: usually `NSE`.
- `instrument_type`: equity, DVR, REIT, INVIT, ETF, etc.
- `canonical_symbol`: current preferred NSE trading symbol for display.
- `canonical_name`: current company/security name for display.
- `status`: active, suspended, delisted, merged, renamed, demerged, unknown.

Do not use raw `symbol` as canonical identity. Symbols are mutable labels.

## Proposed Logical Model

This is a design only; no tables should be created yet.

### security_master

One row per canonical security lineage node.

Suggested fields:

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

Purpose:

- Stable identity for research.
- Current display fields.
- High-level security lifecycle status.

### security_symbol_alias

One row per symbol alias over a validity period.

Suggested fields:

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

Sources:

- `research`
- `angel`
- `nse`
- `yfinance`
- `manual`

Alias reasons:

- exact
- rename
- vendor_format
- merger
- demerger
- delisting
- listing
- manual_override

Examples:

| security_id | source | symbol | valid_from | valid_to | reason |
| --- | --- | --- | --- | --- | --- |
| internal | research | `KALPATPOWR` | unknown | rename date | rename |
| internal | angel | `KPIL` | rename date | null | rename |
| internal | research | `TATAGLOBAL` | unknown | rename date | rename |
| internal | angel | `TATACONSUM` | rename date | null | rename |
| internal | research | `GET&D` | unknown | unknown | vendor_format |
| internal | angel | `GVT&D` | unknown | null | vendor_format |

### security_corporate_action_lineage

Explicit security-to-security relationships.

Suggested fields:

- `event_id`
- `event_date`
- `event_type`
- `from_security_id`
- `to_security_id`
- `ratio`
- `notes`
- `source_url_or_reference`
- `review_status`

Event types:

- rename
- merger
- demerger
- acquisition
- delisting
- suspension
- share_class_change
- listing

Purpose:

- Prevent unsafe one-to-one symbol rewrites.
- Preserve difficult cases like `PEL`, `JUBILANT`, `MAXINDIA`, `HDFC`, and `TATACOFFEE`.

### index_membership_snapshot

One row per security per index snapshot date.

Suggested fields:

- `snapshot_date`
- `index_name`
- `security_id`
- `symbol_as_published`
- `source`
- `source_file_hash`
- `ingested_at`

Purpose:

- Reconstruct point-in-time NSE500 membership.
- Preserve what the index provider published on each date.

### index_membership_range

Derived from snapshots for efficient historical joins.

Suggested fields:

- `index_name`
- `security_id`
- `valid_from`
- `valid_to`
- `entry_snapshot_date`
- `exit_snapshot_date`
- `derivation_run_id`

Purpose:

- Fast point-in-time universe filtering.
- Backtests can ask: was this security in NSE500 on the signal date?

## How Research Symbols Map To Angel Symbols

Mapping should be date-aware and source-aware.

Current classes:

- `exact`: same symbol in research and Angel.
- `known_rename`: reviewed or seeded rename candidate.
- `potential`: weak string candidate; not production-safe.
- `ambiguous`: multiple possible candidates.
- `unmatched`: no safe candidate.
- `angel_only`: Angel symbol absent from current research universe.

Architecture rule:

- Exact mappings can become aliases after basic validation.
- Known renames can become aliases only after validity dates are reviewed.
- Potential mappings should remain pending.
- Ambiguous mappings require corporate-action lineage review.
- Angel-only symbols should be considered candidates for a refreshed current universe, not discarded.

Current mapping status after top rename fixes:

- Research symbols: 501
- Angel symbols: 499
- Mapped research symbols: 313
- Exact matches: 285
- Known rename mappings: 16
- Potential mappings: 12
- Ambiguous mappings: 7
- Unmatched research symbols: 181
- Angel-only symbols: 193

## Corporate-Action Rename Handling

Do not overwrite old symbols in place.

Correct handling:

1. Create one `security_id` when the economic security remains continuous through a rename.
2. Add multiple aliases with valid date ranges.
3. Preserve source-specific symbols.
4. Use the alias valid on the requested date when fetching or joining data.
5. Record lineage events when the continuity is not purely a rename.

Rename example:

```text
security_id: SEC_INTERNAL_001
research alias: TATAGLOBAL, valid_to = rename date
angel alias: TATACONSUM, valid_from = rename date
corporate_action_lineage: rename
```

Demerger or merger example:

```text
old security_id: PEL legacy
new security_id: PIRAMALENT / PIRAMALFIN lineage nodes
corporate_action_lineage: demerger
mapping status: ambiguous until reviewed
```

This distinction matters because a simple symbol replacement can create false history and corrupt backtests.

## Future NSE500 Membership Storage

NSE500 membership should be stored as point-in-time snapshots first.

Recommended practice:

- Store every available NSE500 constituent file as a snapshot.
- Retain the published symbol and company name exactly as received.
- Resolve each published symbol to `security_id` through aliases.
- Mark unresolved symbols with review status instead of dropping them.
- Derive membership ranges from snapshots after ingestion.

Backtest rule:

```text
For signal_date D, the eligible universe is securities with
index_name = NSE500 and valid_from <= D and (valid_to is null or valid_to >= D).
```

Do not depend on:

- `symbol_master.nse500 = true`
- current Angel symbols alone
- current NSE equity list alone

Those are useful source facts, not a historical membership model.

## Migration Path From Current symbol_master

This is a design path only.

### Phase 1: Read-Only Reconciliation

Inputs:

- Current `symbol_master`
- `universe_snapshot`
- Angel symbols
- NSE current equity list
- `reports/angel_symbol_mapping.csv`

Outputs:

- Candidate `security_master` rows
- Candidate alias rows
- Candidate unresolved-review list

No production table changes.

### Phase 2: Review Alias Candidates

Priority order:

1. Exact matches.
2. Known rename mappings already identified.
3. High-confidence formatting cases: `GET&D -> GVT&D`, `GEPIL -> GPIL`.
4. Angel-only current NSE-listed symbols missing from research universe.
5. Ambiguous corporate-action cases.
6. Delisted, suspended, merged, or extinct symbols.

Review outcome:

- approved
- rejected
- needs corporate-action event
- exclude from research

### Phase 3: Build Non-Production Staging Tables

Only after review, create staging tables for:

- securities
- aliases
- lineage
- membership snapshots
- membership ranges

Staging tables should not be used by scoring or backtests until validated.

### Phase 4: Backfill security_id In Parallel

Add `security_id` into non-production/staging versions of:

- prices
- features
- scores
- recommendations
- backtest ledgers

Keep `symbol` for auditability and display.

### Phase 5: Validate Historical Universe Behavior

Validation checks:

- A renamed security resolves to the correct source symbol on each date.
- A delisted security is not present after its valid-to date.
- A new IPO is not present before its listing date.
- NSE500 entry/exit dates are respected.
- Swing V2.1 results can be reproduced over the current period before extending history.

### Phase 6: Cutover

Only after staging validation:

- Use `security_id` as the internal join key.
- Keep `symbol` as a display/source field.
- Require point-in-time membership filters for historical research.

## Canonical Symbol Format

Recommended:

- Canonical display symbol should be the current NSE trading symbol.
- Preserve NSE punctuation where official: `BAJAJ-AUTO`, `MCDOWELL-N`, `ARE&M`, `GVT&D`.
- Store normalized symbol only as a helper field for matching.
- Never use normalized symbol as a primary key.

Example:

| Field | Value |
| --- | --- |
| `canonical_symbol` | `GVT&D` |
| `normalized_symbol` | `GVTD` |
| `source` | `nse` / `angel` |
| `alias_reason` | vendor_format |

## Open Design Questions

1. Should `security_id` continuity survive mergers, or should mergers always create new security IDs with lineage links?
2. Should historical prices for renamed securities be stored under source symbol and resolved at query time, or rewritten into canonical `security_id` in staging?
3. Which source should be authoritative for historical NSE500 membership: NSE files, third-party index history, or manually reconstructed snapshots?
4. How should partial histories be handled for IPOs that listed after the start of the research window?
5. Should delisted historical constituents be retained if Angel has no data but another source does?

## Acceptance Criteria

The reconstructed universe design is ready for implementation only when:

- Every research and Angel symbol has one of: approved alias, rejected alias, unresolved review, or excluded status.
- Current NSE500 membership can be reproduced from an external/current source.
- At least two historical NSE500 snapshots can be represented and diffed.
- Corporate-action lineage is represented separately from aliases.
- Backtests can filter by point-in-time universe membership.
- Swing V2.1 logic remains unchanged during universe reconstruction.

## Final Recommendation

Adopt `security_id` as the canonical platform identity and move all source symbols into a date-valid alias layer. Treat NSE500 membership as point-in-time data, not a static property of a symbol.

The current `symbol_master` should become an input to reconstruction, not the final source of truth. Angel appears suitable as a price/source-symbol universe, but not as a standalone security master. A reliable platform needs all three layers: security identity, source aliases, and historical index membership.
