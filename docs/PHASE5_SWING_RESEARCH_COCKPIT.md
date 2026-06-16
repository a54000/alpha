# Phase 5 Swing Research Cockpit

Generated on: 2026-06-12

## Objective

Create a read-only web dashboard for frozen Swing V2.1 research, paper trading, operations, and validation status.

## Backend

FastAPI app:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.api.main:app --reload --host 127.0.0.1 --port 8000
```

Endpoints:

- `GET /dashboard`
- `GET /recommendations/latest`
- `GET /recommendations/{symbol}/explanation`
- `GET /portfolio`
- `GET /trades`
- `GET /pipeline/status`
- `GET /research/metrics`

The API is read-only. It has no POST, PUT, PATCH, DELETE, broker, or order endpoints.

## Frontend

Next.js app:

```powershell
cd frontend
npm install
npm run dev
```

Default URL:

```text
http://localhost:3000
```

Configure API base URL:

```text
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

## Pages

1. Dashboard
   - NAV
   - PnL
   - drawdown
   - benchmark
   - system health

2. Recommendations
   - ranked Swing V2.1 list
   - score
   - sector
   - signal details

3. Portfolio
   - holdings
   - trades
   - performance

4. Operations
   - pipeline execution status
   - failures
   - data freshness
   - monitoring reports

5. Research
   - backtest metrics
   - walk-forward and replay summaries
   - validation artifacts

## Data Sources

The cockpit reads:

- security master tables
- daily bars and pilot daily bars
- features
- scores
- recommendations
- paper portfolios
- paper positions
- paper trades
- paper daily snapshots
- pipeline runs
- monitoring reports
- research JSON artifacts under `reports/`

## Read-Only Boundary

Phase 5 does not:

- place orders
- connect broker APIs
- modify recommendations
- change scoring
- change strategy
- add optimization
- write production tables

## Verification

Backend tests:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_phase5_api.py
```

Backend compile:

```powershell
.\.venv\Scripts\python.exe -m py_compile app/api/main.py app/api/dashboard_service.py
```

Frontend checks:

```powershell
cd frontend
npm install
npm run build
```
