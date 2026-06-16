# Phase 1B Review Queue Analysis

Objective: analyze `reports/phase1b_manual_review_queue.csv`.

Scope:

- Research only.
- Do not load data.
- Do not modify databases.
- Do not insert aliases.

Inputs:

- `reports/phase1b_manual_review_queue.csv`
- `reports/phase1b_alias_proposals.csv`
- `reports/phase1b_security_master_proposals.csv`
- `reports/angel_symbol_mapping.csv`

## Executive Summary

The review queue contains 393 unique review items.

The safest auto-load set is the exact-match group:

- Auto-load-safe securities: 285
- Research universe denominator: 501
- Estimated safe auto-load percentage: 56.89%
- Proposal denominator: 494 proposed securities
- Auto-load-safe share of proposals: 57.69%

Everything else should remain out of production until reviewed.

## Summary Statistics

### Review Queue

| Metric | Count |
| --- | ---: |
| Review queue rows | 393 |
| Unique review securities/items | 393 |
| High-priority review items | 19 |
| Medium-priority review items | 374 |

### Review Items By Category

| Category | Count | Priority | Meaning |
| --- | ---: | --- | --- |
| `angel_only` | 193 | medium | Angel symbol exists, but no research symbol maps to it. Requires universe membership decision. |
| `unmatched` | 181 | medium | Research symbol has no safe Angel candidate. Requires missing/rename/delisting review. |
| `potential` | 12 | high | Weak one-to-one candidate exists. High false-positive risk. |
| `ambiguous` | 7 | high | Multiple candidates exist. Must not be auto-mapped. |

### Alias Proposal Confidence

| Confidence | Alias records | Interpretation |
| --- | ---: | --- |
| high | 570 | Exact research/Angel aliases. Production-load candidate after final preflight. |
| medium | 32 | Known rename aliases. Needs validity dates before production load. |
| pending | 193 | Angel-only alias proposals. Needs universe membership decision. |

### Proposed Security Review Status

| Review status | Securities | Interpretation |
| --- | ---: | --- |
| approved | 285 | Exact-match securities. Conservative auto-load set. |
| needs_review | 209 | Renames, Angel-only securities, and other non-exact cases. |

## High-Confidence Mappings

High-confidence mappings are exact research-to-Angel symbol matches.

Current count:

- 285 securities
- 570 alias records, one research alias and one Angel alias per security

Recommended handling:

- Eligible for the first controlled production load after preflight.
- Still validate duplicate aliases and foreign keys before inserting.
- Do not infer index membership from these aliases.

## Medium-Confidence Mappings

Medium-confidence mappings are `known_rename` alias proposals.

Current count:

- 16 securities
- 32 alias records

Examples from current mapping work:

- `KALPATPOWR -> KPIL`
- `WABCOINDIA -> ZFCVINDIA`
- `SRTRANSFIN -> SHRIRAMFIN`
- `TATAGLOBAL -> TATACONSUM`
- `INFRATEL -> INDUSTOWER`
- `RNAM -> NAM-INDIA`
- `MAHINDCIE -> CIEINDIA`

Recommended handling:

- Do not auto-load as approved.
- Require `valid_from` and `valid_to` decisions.
- Require corporate-action reference or manual approval.
- Load only after review status can be upgraded from `needs_review` to `approved` or `pending_dates` with explicit policy.

## Low-Confidence Mappings

Low-confidence mappings are `potential` cases.

Current count:

- 12 review items

Current cases:

| Research symbol | Candidate |
| --- | --- |
| `ASHOKA` | `ASHOKLEY` |
| `ASTRAZEN` | `ASTRAL` |
| `IDFC` | `IDFCFIRSTB` |
| `JSLHISAR` | `JSL` |
| `LTI` | `LT` |
| `PTC` | `PTCIL` |
| `PVR` | `PVRINOX` |
| `RAIN` | `RAINBOW` |
| `SHRIRAMCIT` | `SHRIRAMFIN` |
| `STAR` | `STARHEALTH` |
| `WELSPUNIND` | `WELSPUNLIV` |
| `ZYDUSWELL` | `ZYDUSLIFE` |

Recommended handling:

- Manual review only.
- Assume false positive until proven otherwise.
- Do not load into `security_symbol_alias` without source evidence.

## Corporate-Action Lineage Cases

These are cases where aliasing alone may be unsafe because the event may involve merger, demerger, acquisition, share-class change, or parent/subsidiary confusion.

Primary lineage review categories:

- `known_rename`: 16 medium-confidence cases need event dates.
- `potential`: 12 weak cases need source evidence.
- `ambiguous`: 7 cases must be resolved through lineage, not string matching.
- subset of `unmatched`: legacy/delisted/merged names identified in prior audits.

Ambiguous cases:

| Research symbol | Candidates |
| --- | --- |
| `AEGISCHEM` | `AEGISLOG`, `AEGISVOPAK` |
| `BAJAJCON` | `BAJAJ-AUTO`, `BAJAJFINSV`, `BAJAJHFL`, `BAJAJHLDNG` |
| `BAJAJELEC` | `BAJAJ-AUTO`, `BAJAJFINSV`, `BAJAJHFL`, `BAJAJHLDNG` |
| `GODREJAGRO` | `GODREJCP`, `GODREJIND`, `GODREJPROP` |
| `HDFC` | `HDFCAMC`, `HDFCBANK`, `HDFCLIFE` |
| `L&TFH` | `LT`, `LTF` |
| `TATACOFFEE` | `TATACAP`, `TATACHEM`, `TATACOMM`, `TATACONSUM` |

Recommended handling:

- Create lineage decisions separately from alias decisions.
- Do not collapse demergers or mergers into a single alias row without a reviewed event model.

## Alias-Only Cases

Alias-only cases are `angel_only` symbols.

Current count:

- 193

Meaning:

- Angel has the symbol.
- Research universe does not map to it.
- Prior forensics found all 193 are present in the official NSE equity list.

Recommended handling:

- Do not load directly as active NSE500 members.
- First decide whether each belongs in a refreshed universe snapshot.
- Then create `security_master` and Angel alias records as reviewed current securities.

## Top Review Categories

1. Exact-match preflight: 285 securities can be auto-loaded after final validation.
2. Known renames: 16 securities need event-date review.
3. Ambiguous mappings: 7 high-risk cases need human lineage decisions.
4. Potential mappings: 12 likely false-positive-prone cases.
5. Angel-only symbols: 193 current NSE-listed symbols require universe membership decision.
6. Unmatched research symbols: 181 require missing/legacy/delisting review.

## Recommended Review Workflow

### Step 1: Auto-Load Candidate Approval

Review exact-match proposal sample.

If clean:

- Approve the 285 exact-match securities for future controlled load.
- Keep load separate from this analysis phase.

### Step 2: Known Rename Review

For each known rename:

1. Confirm source symbol.
2. Confirm target Angel/NSE symbol.
3. Confirm event date.
4. Decide whether it is a true rename, merger, demerger, or share-class change.
5. Assign alias validity dates.

### Step 3: Ambiguous Review

Resolve the 7 ambiguous cases with source evidence.

Allowed decisions:

- approve one candidate
- reject all candidates
- create lineage event
- exclude from reconstruction

### Step 4: Potential Mapping Review

Treat all 12 as suspect.

Most should likely be rejected unless exchange/corporate-action evidence proves continuity.

### Step 5: Angel-Only Universe Review

Classify 193 Angel-only symbols:

- current NSE500 member
- current NSE equity but not NSE500
- IPO/new listing
- successor of stale research symbol
- exclude

### Step 6: Unmatched Research Review

Classify 181 unmatched research symbols:

- genuinely missing Angel coverage
- stale legacy symbol
- delisted/merged/suspended
- needs alternate source
- exclude

## Estimated Manual Effort

| Work item | Count | Estimated time per item | Estimated effort |
| --- | ---: | ---: | ---: |
| Exact-match sample QA | 285 | sample only | 0.5 day |
| Known rename review | 16 | 10-20 min | 0.5 day |
| Ambiguous mapping review | 7 | 20-45 min | 0.5 day |
| Potential mapping review | 12 | 10-20 min | 0.5 day |
| Angel-only universe classification | 193 | 2-5 min | 1-2 days |
| Unmatched research classification | 181 | 2-5 min | 1-2 days |

Total estimate:

- Fast pass: 3-4 working days
- Careful pass with source references and dates: 5-7 working days

## Auto-Load Safety Estimate

Conservative auto-load-safe set:

```text
285 exact-match securities
```

Percentage of current research universe:

```text
285 / 501 = 56.89%
```

Percentage of proposed security records:

```text
285 / 494 = 57.69%
```

Do not auto-load:

- `known_rename`, until dates are reviewed
- `potential`
- `ambiguous`
- `unmatched`
- `angel_only`

## Final Recommendation

Proceed with a two-lane review:

1. Prepare a controlled future load for the 285 exact matches.
2. Run manual review on the 209 non-exact proposed securities and 393 review queue items before loading any aliases beyond exact matches.

No production inserts should occur until the exact-match load plan, validation SQL, and rollback script are reviewed separately.
