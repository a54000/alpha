# Phase 5.1 Recommendation Decision Journal

Generated on: 2026-06-12

## Objective

Store read-only explainability snapshots for every frozen Swing V2.1 recommendation.

## Table

`recommendation_decision_journal`

Fields:

- `journal_id`
- `business_date`
- `symbol`
- `rank`
- `score`
- `recommendation_type`
- `sector`
- `feature_snapshot_json`
- `created_at`

Uniqueness:

- `(business_date, symbol, recommendation_type)`

## Captured Feature Snapshot

The snapshot stores:

- `sector_rank_3m`
- `adx_14`
- `ema_200`
- `ema200_extension`
- `prior_20d_return`
- `final_score`

These are copied from already-generated features and recommendations. The journal does not calculate new factors and does not change scoring.

## Capture Script

```powershell
.\.venv\Scripts\python.exe scripts/capture_recommendation_decision_journal.py --business-date 2026-06-12
```

Dry run:

```powershell
.\.venv\Scripts\python.exe scripts/capture_recommendation_decision_journal.py --business-date 2026-06-12 --dry-run
```

The Phase 4B full daily pipeline now runs `decision_journal_capture` after recommendation generation and before paper portfolio update.

## API

```text
GET /recommendations/{symbol}/explanation
```

Query parameters:

- `recommendation_type`, default `swing_v2_1`
- `business_date`, optional

The API reads `recommendation_decision_journal` first. If the journal has not been populated yet, it falls back to the current pilot recommendation and feature tables.

## Dashboard

The Recommendations page links each symbol to:

```text
/recommendations/{symbol}/explanation
```

The explanation page shows rank, score, sector rank, ADX, EMA200, EMA200 extension, prior 20-day return, source, and creation time.

## Constraints

Phase 5.1 does not:

- modify scoring
- modify ranking
- add factors
- change strategy rules
- connect broker APIs
- place orders
