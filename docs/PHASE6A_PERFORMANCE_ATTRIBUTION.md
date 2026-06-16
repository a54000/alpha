# Phase 6A Performance Attribution

Generated on: 2026-06-12

## Objective

Add read-only attribution reporting for frozen Swing V2.1 paper trading and validation results.

## Script

```powershell
.\.venv\Scripts\python.exe scripts/generate_performance_attribution.py
```

Outputs:

- `reports/phase6a_performance_attribution.json`
- `reports/phase6a_performance_attribution.md`

## Position Contribution

For each symbol, the report includes:

- symbol
- sector
- holding period
- realized contribution
- unrealized contribution
- total contribution

Realized contribution comes from `paper_trades.realized_pnl`. Unrealized contribution comes from open `paper_positions.unrealized_pnl`.

## Sector Attribution

For each sector, the report includes:

- sector exposure
- sector return contribution
- concentration percentage

Exposure is based on open paper position market value. Return contribution is the sum of realized and unrealized symbol contribution by sector.

## Strategy Attribution

The report compares:

- Top 5 Weekly
- Top 10 Weekly

Metrics:

- return contribution
- drawdown contribution
- turnover contribution
- closed trades
- final equity

These are read from `reports/phase2e_portfolio_metrics.json`.

## API

```text
GET /portfolio/attribution
```

Optional query parameter:

```text
portfolio_id
```

The API first reads `reports/phase6a_performance_attribution.json`. If the report has not been generated yet, it attempts a read-only on-demand calculation from paper portfolio tables.

## Constraints

Phase 6A does not:

- change scoring
- change ranking
- add factors
- modify portfolio rules
- optimize parameters
- connect broker APIs
- place orders

## Verification

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_phase6a_attribution.py tests/test_phase5_api.py
.\.venv\Scripts\python.exe -m py_compile scripts/generate_performance_attribution.py app/api/main.py app/api/dashboard_service.py
```
