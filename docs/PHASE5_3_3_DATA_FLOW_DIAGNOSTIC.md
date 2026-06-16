# Phase 5.3.3 Data Flow Diagnostic

Date: 2026-06-12

Scope: read-only diagnostic. No strategy, scoring, recommendation generation, database records, backend logic, or frontend code were modified.

## Executive Summary

The cockpit shows `n/a` values and no recommendations because the API is returning empty payloads. The frontend is mostly mapping those payloads correctly.

Primary root cause: the FastAPI cockpit process is not using a valid pair of database connections.

Evidence:

- The live API returns empty dashboard, recommendations, portfolio, and pipeline data.
- The shell environment has no `DATABASE_URL`, `ANGEL_DATABASE_URL`, or `PAPER_PORTFOLIO_ID`.
- The repo `.env` contains only `DATABASE_URL`, and it points to `angel_data`, not the research platform database.
- The `.env` URL could not authenticate from this session.
- Instantiating `CockpitReadService` with no database environment loaded reproduces the exact live API payloads.
- The API service catches DB exceptions and returns empty objects/lists, so missing or invalid DB connectivity appears as `n/a` rather than a visible API error.

Secondary issue: even if `.env` were loaded, `DATABASE_URL` currently points at `angel_data`; the cockpit expects `DATABASE_URL` to be the research database and `ANGEL_DATABASE_URL` to be the Angel database.

Expected historical pilot data exists according to prior generated reports:

- `angel_data.pilot_phase2a.scores_daily`: 279,405 rows, last score date 2026-06-11.
- `angel_data.pilot_phase2a.recommendations_daily`: 13,654 rows, last recommendation date 2026-06-11.
- Latest generated recommendation dates include 2026-06-11 with 8 recommendations.

The API is not reaching that data in the current runtime.

## Live API Payloads

### `GET /recommendations/latest?model=swing_v2_1&limit=50`

Current response:

```json
{
  "date": null,
  "model": "swing_v2_1",
  "source": "recommendation_history",
  "recommendations": []
}
```

Interpretation:

- API first tried `pilot_phase2a.recommendations_daily` through `angel_engine`.
- That returned `None`, most likely because `angel_engine` is `None` or the query failed.
- API then fell back to `recommendation_history` through `research_engine`.
- That also returned `None`.
- Empty recommendation list is therefore produced by backend data access, not frontend rendering.

### `GET /dashboard`

Current response:

```json
{
  "portfolio": {},
  "risk": {},
  "benchmark": {},
  "system_health": {
    "latest_candle_at": null,
    "latest_feature_date": null,
    "latest_recommendation_date": null,
    "steps": 0,
    "failed_steps": 0,
    "status": "unknown"
  },
  "research": {
    "phase2e_available": true,
    "phase2e_keys": [
      "generated_on",
      "mode",
      "model",
      "date_range",
      "production_tables_modified",
      "scoring_changed",
      "recommendations_changed",
      "backtest_inputs",
      "methodology",
      "variants"
    ],
    "walk_forward_available": true,
    "phase3e_available": true
  },
  "read_only": true
}
```

Interpretation:

- Portfolio/risk/benchmark come from `/portfolio`, which is empty.
- System health comes from `/pipeline/status`, which has null dates.
- Research data appears because it is read from JSON reports in `reports/`, not from the database.

### `GET /portfolio`

Current response:

```json
{
  "summary": {},
  "positions": [],
  "trades": [],
  "risk": {},
  "benchmark": {}
}
```

Interpretation:

- API did not find a default `paper_portfolios.portfolio_id`.
- This is consistent with no research DB connection, no `PAPER_PORTFOLIO_ID`, or missing paper portfolio rows.

### `GET /pipeline/status`

Current response:

```json
{
  "summary": {
    "latest_candle_at": null,
    "latest_feature_date": null,
    "latest_recommendation_date": null,
    "steps": 0,
    "failed_steps": 0,
    "status": "unknown"
  },
  "steps": [],
  "monitoring_reports": [
    {
      "name": "daily_paper_report_2026-06-12.md",
      "path": "D:\\nse-research-app\\reports\\daily_paper_report_2026-06-12.md",
      "modified_at": "2026-06-12"
    }
  ]
}
```

Interpretation:

- Monitoring report data is file-based and available.
- Pipeline run rows and latest market/feature/recommendation dates are DB-backed and unavailable.

## Frontend Trace

### Dashboard Page

File: `frontend/app/page.tsx`

API calls:

- `/dashboard`
- `/pipeline/status`

Field mapping:

| UI field | Frontend source | Current API value | UI result |
| --- | --- | --- | --- |
| NAV | `data.portfolio?.nav ?? data.portfolio?.current_nav` | missing | `n/a` |
| Realized PnL | `data.portfolio?.realized_pnl` | missing | `n/a` |
| Drawdown | `data.risk?.drawdown` | missing | `n/a` |
| Benchmark Return | `data.benchmark?.return` | missing | `n/a` |
| Latest candle | `data.system_health?.latest_candle_at` | null | `n/a` |
| Latest recommendations | `data.system_health?.latest_recommendation_date` | null | `n/a` |

Frontend verdict:

- Mapping is correct for the current API contract.
- Dashboard displays `n/a` because `/dashboard` contains empty objects and null dates.

### Recommendations Page

File: `frontend/app/recommendations/page.tsx`

API call:

- `/recommendations/latest?model=swing_v2_1&limit=50`

Field mapping:

| UI field | Frontend source | Current API value | UI result |
| --- | --- | --- | --- |
| Page date | `data.date` | null | `n/a` |
| Rows | `data.recommendations` | `[]` | empty state |
| Symbol links | `row.symbol` | no rows | none |

Frontend verdict:

- Mapping is correct.
- Recommendations are absent because the API returns an empty list.

### Portfolio Page

File: `frontend/app/portfolio/page.tsx`

API call:

- `/portfolio`

Field mapping:

| UI field | Frontend source | Current API value | UI result |
| --- | --- | --- | --- |
| NAV | `data.summary.nav ?? data.summary.current_nav` | missing | `n/a` |
| Cash | `data.summary.cash` | missing | `n/a` |
| Exposure | `data.risk.exposure` | missing | `n/a` |
| Open Positions | `data.summary.open_positions ?? data.positions.length` | `0` | `0` |
| Holdings | `data.positions` | `[]` | no holdings |
| Recent trades | `data.trades` | `[]` | no trades |

Frontend verdict:

- Mapping is correct for the current payload.
- Empty portfolio state originates in the API/database layer.

## Backend Trace

File: `app/api/dashboard_service.py`

### Recommendation Query Path

Function: `latest_recommendations`

Query order:

1. `angel_engine`:

```sql
SELECT MAX(date)
FROM pilot_phase2a.recommendations_daily
WHERE model = :model
```

2. If no latest pilot recommendation date, fallback to `research_engine`:

```sql
SELECT MAX(date)
FROM recommendation_history
WHERE model = :model
```

Current behavior:

- Both return `None`.
- API returns empty recommendations.

Why this likely happens:

- `angel_engine` is not connected.
- `research_engine` is not connected.
- Or both queries fail and are swallowed by `_scalar`.

### Dashboard Query Path

Function: `dashboard`

Data sources:

- `portfolio()` for portfolio/risk/benchmark.
- `pipeline_status()` for system health.
- `research_metrics()` for report-file summaries.

Current behavior:

- DB-backed portfolio and system health are empty.
- Report-backed research summary is populated.

### Portfolio Query Path

Function: `portfolio`

Query order:

1. `_default_portfolio_id()`
   - uses `PAPER_PORTFOLIO_ID`, if set
   - otherwise queries `SELECT MAX(portfolio_id) FROM paper_portfolios`
2. If no portfolio id, returns empty payload.

Current behavior:

- No portfolio id is found.
- API returns empty portfolio.

### Pipeline Status Query Path

Function: `pipeline_status`

Queries:

```sql
SELECT business_date, step_name, status, started_at, completed_at, error_message
FROM pipeline_runs
WHERE business_date = (SELECT MAX(business_date) FROM pipeline_runs)
```

```sql
SELECT MAX(datetime) FROM ohlcv_15min
```

```sql
SELECT MAX(date) FROM pilot_phase2a.features_daily
```

```sql
SELECT MAX(date) FROM pilot_phase2a.recommendations_daily
```

Current behavior:

- All DB-backed values are null/empty.
- File-backed monitoring reports are populated.

## Environment Findings

Current shell environment:

- `DATABASE_URL`: not set
- `ANGEL_DATABASE_URL`: not set
- `PAPER_PORTFOLIO_ID`: not set

Repo `.env`:

```text
DATABASE_URL=postgresql+psycopg2://surindersingh:***@localhost:5432/angel_data
```

Issues:

1. `app/api/dashboard_service.py` does not load `.env` by itself.
2. Even if `.env` is loaded, `DATABASE_URL` points to `angel_data`.
3. `ANGEL_DATABASE_URL` is not separately configured.
4. The `.env` database URL failed authentication from this session.

Expected cockpit configuration:

```text
DATABASE_URL=postgresql+psycopg2://<user>:<password>@localhost:5432/nse_research_platform
ANGEL_DATABASE_URL=postgresql+psycopg2://<user>:<password>@localhost:5432/angel_data
PAPER_PORTFOLIO_ID=<valid paper_portfolios.portfolio_id>
```

## Database Content Findings

Direct database inspection could not be completed from this session because the `.env` database credentials failed authentication:

```text
password authentication failed for user "surindersingh"
```

However, prior phase reports indicate expected pilot data was generated in `angel_data.pilot_phase2a`:

| Table | Reported rows | Latest date |
| --- | ---: | --- |
| `pilot_phase2a.scores_daily` | 279,405 | 2026-06-11 |
| `pilot_phase2a.recommendations_daily` | 13,654 | 2026-06-11 |

Reported latest recommendation counts:

| Date | Recommendations |
| --- | ---: |
| 2026-06-04 | 4 |
| 2026-06-05 | 10 |
| 2026-06-08 | 13 |
| 2026-06-09 | 10 |
| 2026-06-10 | 7 |
| 2026-06-11 | 8 |

This means the cockpit should not be empty if it is connected to the same Angel database used during Phase 2D.

## Where Data Becomes Empty

The first empty point is the API service database access layer:

- `CockpitReadService.research_engine`
- `CockpitReadService.angel_engine`

When these engines are `None`, or when their queries fail, `_scalar()` returns `None` and `_mappings()` returns `[]`.

Those graceful fallbacks produce:

- no latest recommendation date
- no latest score/feature dates
- no latest candle date
- no pipeline run rows
- no paper portfolio id
- no portfolio snapshots

The frontend receives these empty payloads and renders `n/a` correctly.

## Is the DB Missing Records?

Not proven.

The live API behaves as if DB records are missing, but the stronger evidence is that the API cannot reach a usable database connection:

- Running service with no DB environment reproduces the exact API output.
- `.env` is not loaded by the API service automatically.
- `.env` points `DATABASE_URL` to the wrong database for the research engine.
- `.env` authentication failed from this session.
- Prior reports indicate pilot recommendation records should exist.

Therefore, the primary diagnosis is connection/configuration failure, not confirmed missing records.

## Is API Mapping Wrong?

Partially.

The API query intent is broadly correct:

- Latest recommendations prefer `angel_data.pilot_phase2a.recommendations_daily`.
- Dashboard system health reads Angel candles/features/recommendations.
- Portfolio reads paper trading tables from the research database.

But there are two API-layer robustness issues:

1. The API silently swallows database connection and query failures.
2. The API does not expose whether `research_engine` or `angel_engine` is disconnected.

This makes configuration problems look like legitimate empty data.

## Is Frontend Mapping Wrong?

No material frontend mapping bug was found for these symptoms.

The frontend shows `n/a` because the API returns:

- `{}` for portfolio/risk/benchmark
- `null` for latest dates
- `[]` for recommendations/positions/trades

The recommendations page correctly requests:

```text
/recommendations/latest?model=swing_v2_1&limit=50
```

The dashboard and portfolio pages also use the expected API endpoints.

## Exact Fix Recommendation

Recommended fix sequence:

1. Correct environment separation:

```text
DATABASE_URL=postgresql+psycopg2://<research_user>:<password>@localhost:5432/nse_research_platform
ANGEL_DATABASE_URL=postgresql+psycopg2://<angel_user>:<password>@localhost:5432/angel_data
PAPER_PORTFOLIO_ID=<valid portfolio id>
```

2. Ensure the FastAPI process actually loads those values:

- Start uvicorn from a shell where the variables are set, or
- load `.env` before creating `CockpitReadService`, or
- use a process manager that injects the environment.

3. Verify DB connectivity with read-only checks:

```sql
SELECT current_database();
SELECT COUNT(*), MAX(date) FROM pilot_phase2a.recommendations_daily;
SELECT COUNT(*), MAX(date) FROM pilot_phase2a.scores_daily;
SELECT COUNT(*), MAX(datetime) FROM ohlcv_15min;
SELECT COUNT(*), MAX(business_date) FROM pipeline_runs;
SELECT COUNT(*), MAX(portfolio_id) FROM paper_portfolios;
SELECT COUNT(*), MAX(date) FROM paper_daily_snapshots;
```

4. Add cockpit diagnostics or logging for DB connection failures:

- Do not let `_scalar()` and `_mappings()` silently hide all DB errors during cockpit operation.
- At minimum, expose a read-only health field such as `research_db_connected` and `angel_db_connected`.

5. Restart FastAPI after environment correction.

Expected API result after correction:

- `/recommendations/latest?model=swing_v2_1&limit=50` should return latest pilot recommendation date, likely 2026-06-11 if connected to the Phase 2D Angel database.
- `/dashboard` should show latest candle/feature/recommendation dates.
- `/portfolio` should populate only if paper trading tables contain portfolio rows and `PAPER_PORTFOLIO_ID` resolves correctly.

## Acceptance Criteria for Follow-Up

The issue should be considered fixed when:

- `GET /pipeline/status` shows non-null `latest_recommendation_date`.
- `GET /recommendations/latest?model=swing_v2_1&limit=50` returns non-empty `recommendations`.
- `GET /dashboard` shows non-null system health dates.
- `GET /portfolio` shows a non-empty `summary` when a valid paper portfolio exists.
- The frontend no longer shows `n/a` except for genuinely unavailable optional fields.
