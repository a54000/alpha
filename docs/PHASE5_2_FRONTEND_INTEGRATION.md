# Phase 5.2 Frontend Integration Audit

Generated on: 2026-06-12

## Objective

Connect Swing Research Cockpit frontend pages to the FastAPI backend and ensure each page handles loading, API failures, empty data, and navigation correctly.

## Audit Results

| Page | Required API | Status |
|---|---|---|
| Dashboard | `GET /dashboard` | Connected |
| Recommendations | `GET /recommendations/latest` | Connected |
| Recommendation explanation | `GET /recommendations/{symbol}/explanation` | Connected |
| Portfolio | `GET /portfolio` | Connected |
| Operations | `GET /pipeline/status` | Connected |
| Research | `GET /research/metrics` | Connected |

## Fixes Implemented

Frontend API client:

- Added `safeApiGet()` in `frontend/lib/api.ts`.
- API failures now return structured error state instead of throwing unhandled server-render errors.

Shared states:

- Added `ErrorState`.
- Added `EmptyState`.
- Added `LoadingState`.
- Added global `frontend/app/loading.tsx`.

Page behavior:

- Dashboard renders `/dashboard` metrics and shows an empty state if no dashboard metrics are available.
- Recommendations renders `/recommendations/latest` rows and links each symbol to its explanation page.
- Recommendation explanation renders `/recommendations/{symbol}/explanation`.
- Portfolio renders `/portfolio` summary, holdings, and trades with explicit empty states.
- Operations renders `/pipeline/status`, pipeline steps, freshness, and monitoring report rows.
- Research renders `/research/metrics` validation and backtest summaries.

Navigation:

- Recommendation symbol links now route to:

```text
/recommendations/{symbol}/explanation
```

## Loading States

The Next.js App Router uses:

```text
frontend/app/loading.tsx
```

This shows a loading panel while server-rendered page data is being fetched.

## Error States

Each page now uses `safeApiGet()` and renders `ErrorState` when the backend request fails.

This covers:

- FastAPI server unavailable
- non-2xx response
- network failure
- invalid fetch path

## Empty States

Each page now renders explicit empty states when the API responds successfully but returns no usable rows or metrics.

Examples:

- no recommendations
- no explanation snapshot
- no paper portfolio
- no holdings
- no trades
- no pipeline run rows
- no research metrics

## Constraints

Phase 5.2 does not:

- change backend business logic
- change scoring
- change recommendations
- change strategy rules
- add factors
- optimize parameters
- connect broker APIs
- place orders

## Verification

Backend/API integration source tests:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_phase5_2_frontend_integration.py tests/test_phase5_api.py
```

Frontend build:

```powershell
cd frontend
npm run build
```
