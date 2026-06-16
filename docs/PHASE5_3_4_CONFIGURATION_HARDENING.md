# Phase 5.3.4 Configuration Hardening

Date: 2026-06-12

Scope: API runtime configuration and error handling only. No scoring, recommendation generation, strategy rules, portfolio logic, or database data were changed.

## Objective

Prevent the Swing Research Cockpit from silently returning empty successful responses when required databases or paper portfolio configuration are missing or broken.

## Implemented Changes

### Separate Required Database Configuration

The cockpit API now requires separate runtime configuration for:

```text
DATABASE_URL
ANGEL_DATABASE_URL
PAPER_PORTFOLIO_ID
```

Expected meaning:

| Variable | Purpose |
| --- | --- |
| `DATABASE_URL` | Research platform database, for paper portfolios, pipeline runs, decision journal, production recommendation fallback |
| `ANGEL_DATABASE_URL` | Angel market data database, for `ohlcv_15min` and `pilot_phase2a` feature/score/recommendation tables |
| `PAPER_PORTFOLIO_ID` | Default paper portfolio id for cockpit portfolio views |

The API now rejects missing configuration and rejects identical `DATABASE_URL` / `ANGEL_DATABASE_URL` values.

### Startup Validation

`app/api/main.py` validates cockpit configuration at FastAPI startup.

Failure examples:

- `DATABASE_URL` missing
- `ANGEL_DATABASE_URL` missing
- `PAPER_PORTFOLIO_ID` missing
- `PAPER_PORTFOLIO_ID` not an integer
- `DATABASE_URL` and `ANGEL_DATABASE_URL` point to the same database URL

This avoids the previous failure mode where the app started and all DB-backed data appeared as empty.

### Typed API Errors

Added typed errors in `app/api/dashboard_service.py`:

- `CockpitConfigurationError`
- `CockpitDatabaseError`

FastAPI handlers now return HTTP 503 with a meaningful JSON error:

```json
{
  "detail": "Database query failed: ...",
  "error_type": "database_error"
}
```

or:

```json
{
  "detail": "Missing required cockpit configuration: DATABASE_URL, ANGEL_DATABASE_URL, PAPER_PORTFOLIO_ID.",
  "error_type": "configuration_error"
}
```

Database query failures are logged with stack traces and are no longer converted into empty success responses.

### Health Endpoint

Added:

```text
GET /health
```

Response shape:

```json
{
  "status": "ok",
  "research_db": {
    "connected": true,
    "database": "nse_research_platform"
  },
  "angel_db": {
    "connected": true,
    "database": "angel_data"
  },
  "paper_portfolio": {
    "configured": true,
    "portfolio_id": 1,
    "exists": true,
    "status": "active"
  }
}
```

If any dependency is unavailable, `status` becomes `degraded` and the failing component includes an error message.

## Files Changed

- `app/api/dashboard_service.py`
- `app/api/main.py`
- `tests/test_phase5_api.py`
- `tests/test_phase5_3_4_configuration_hardening.py`
- `docs/PHASE5_3_4_CONFIGURATION_HARDENING.md`

## Runtime Configuration Contract

Use a shell or process manager that sets all three variables before starting FastAPI:

```powershell
$env:DATABASE_URL = "postgresql+psycopg2://<user>:<password>@localhost:5432/nse_research_platform"
$env:ANGEL_DATABASE_URL = "postgresql+psycopg2://<user>:<password>@localhost:5432/angel_data"
$env:PAPER_PORTFOLIO_ID = "1"

.\.venv\Scripts\python.exe -m uvicorn app.api.main:app --host 127.0.0.1 --port 8000
```

Important: the API service reads environment variables directly. A local `.env` file must be loaded by the process launcher or exported into the shell before `uvicorn` starts.

## Verification

Focused tests:

```text
.\.venv\Scripts\python.exe -m pytest tests/test_phase5_api.py tests/test_phase5_3_4_configuration_hardening.py
```

Result:

```text
12 passed
```

Frontend production build:

```text
npm run build
```

Result:

```text
Compiled successfully
Generating static pages (8/8)
```

## Test Coverage Added

### Missing Env Test

Verifies `CockpitReadService` fails clearly when required configuration is absent.

### DB Failure Test

Verifies DB query failure raises `CockpitDatabaseError` instead of returning an empty successful payload.

### Successful Connection Test

Verifies `/health` service logic reports:

- research DB connected
- Angel DB connected
- paper portfolio configured
- paper portfolio exists

## Operational Impact

Before this phase:

- Missing DB env or DB query errors produced empty dashboards and no recommendations.
- Users saw `n/a` values with no clear explanation.

After this phase:

- Missing required configuration fails startup.
- Runtime DB query failures return HTTP 503.
- `/health` identifies whether research DB, Angel DB, and paper portfolio dependencies are available.

## Follow-Up Recommendation

Update the local API launch script or operator instructions to export:

- `DATABASE_URL`
- `ANGEL_DATABASE_URL`
- `PAPER_PORTFOLIO_ID`

Then restart FastAPI and verify:

```powershell
Invoke-WebRequest http://localhost:8000/health -UseBasicParsing
Invoke-WebRequest http://localhost:8000/recommendations/latest?model=swing_v2_1 -UseBasicParsing
```

No strategy or recommendation rebuild is required for this configuration hardening step.
