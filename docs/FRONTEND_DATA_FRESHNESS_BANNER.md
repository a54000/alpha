# Frontend Data Freshness Banner

Generated on: 2026-06-12

## Objective

Expose operational freshness clearly on the Swing Research Cockpit dashboard.

## Location

Dashboard page:

```text
frontend/app/page.tsx
```

Component:

```text
frontend/components/DataStatusCard.tsx
```

## API Dependencies

Uses existing APIs only:

- `GET /dashboard`
- `GET /pipeline/status`

No backend business logic was changed.

## Displayed Fields

The Data Status card shows:

- latest market data date
- latest recommendation date
- latest pipeline run
- freshness status

## Status Rules

GREEN: `All current`

- market data exists
- recommendations exist
- pipeline is not failed
- market data and recommendations are aligned
- both are current relative to the latest pipeline business date when available

YELLOW: `Pipeline delayed`

- pipeline status is failed or unavailable, or
- market data and recommendations are not aligned to the same date

RED: `Stale data`

- market data date is missing, or
- recommendation date is missing, or
- market data or recommendations lag the latest pipeline business date

## UI Behavior

The card uses:

- green left border and pill for current data
- yellow left border and pill for delayed pipeline state
- red left border and pill for stale or missing data

The dashboard still renders existing NAV, PnL, drawdown, benchmark, system health, and exposure sections.

## Constraints

This change does not:

- modify scoring
- modify recommendations
- change backend logic
- add strategy rules
- connect broker APIs
- place orders

## Verification

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_phase5_2_frontend_integration.py
cd frontend
npm run build
```
