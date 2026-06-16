# Phase 6C Trade Analysis Module

Generated on: 2026-06-13

## Objective

Add an on-demand historical trade reconstruction feature to the Swing Research Cockpit.

This module is analysis-only. It does not change scoring, ranking, recommendation generation, strategy rules, paper trading lifecycle, portfolio logic, broker integrations, or live trading behavior.

## Architecture

### Backend

New service:

- `app/api/trade_analysis_service.py`

New API routes:

- `POST /research/trade-analysis/run`
- `GET /research/trade-analysis/{report_id}`
- `GET /research/trade-analysis/{report_id}/artifact/{artifact_name}`

The service reads:

- `angel_data.pilot_phase2a.recommendations_daily`
- `angel_data.pilot_phase2a.features_daily`
- `angel_data.pilot_phase2a.daily_bars_clean`

The service writes filesystem artifacts only:

- `reports/trade_analysis/<report_id>/trades.csv`
- `reports/trade_analysis/<report_id>/equity_curve.csv`
- `reports/trade_analysis/<report_id>/summary.md`
- `reports/trade_analysis/<report_id>/summary.json`
- `reports/trade_analysis/<report_id>/weekly_equity.csv`
- `reports/trade_analysis/<report_id>/weekly_equity.svg`
- `reports/trade_analysis/<report_id>/metadata.json`

No new database tables or migrations were created.

### Frontend

New page:

- `frontend/app/research/trade-analysis/page.tsx`

Navigation:

- Sidebar link: `Trade Analysis`
- Research page link: `Open Trade Analysis`

The page is a client component because report generation is a POST workflow with loading, error, and result states.

## API Usage

### Run Report

```http
POST /research/trade-analysis/run
Content-Type: application/json
```

```json
{
  "start_date": "2026-06-01",
  "end_date": "2026-06-11",
  "strategy": "TOP5_WEEKLY",
  "initial_capital": 1000000,
  "charge_model": "ZERODHA_DEFAULT"
}
```

Supported strategies:

| API Value | Meaning |
| --- | --- |
| `TOP5_WEEKLY` | Top 5 Weekly |
| `TOP10_WEEKLY` | Top 10 Weekly |
| `TOP10_SECTOR_CAP` | Top 10 Weekly + max 2 open positions per sector |

Supported charge models:

| API Value | Meaning |
| --- | --- |
| `ZERODHA_DEFAULT` | Approximate Zerodha-style equity delivery charges |

Response:

```json
{
  "report_id": "20260613T021213Z_top5_weekly_6e51f76603",
  "status": "completed",
  "summary": {
    "ending_value": 980956.38,
    "total_return": -0.01904,
    "cagr": -0.41630,
    "max_drawdown": -0.03172,
    "total_trades": 5,
    "win_rate": 0.4,
    "total_charges": 2192.44
  },
  "artifacts": {
    "trades_csv": "reports/trade_analysis/<report_id>/trades.csv",
    "summary_md": "reports/trade_analysis/<report_id>/summary.md"
  }
}
```

### Retrieve Metadata

```http
GET /research/trade-analysis/{report_id}
```

Returns:

- status
- parameters
- summary metrics
- generated artifact paths
- input source metadata
- read-only constraint confirmation

### Download Artifacts

```http
GET /research/trade-analysis/{report_id}/artifact/trades.csv
GET /research/trade-analysis/{report_id}/artifact/summary.md
```

Additional supported artifacts:

- `summary.json`
- `metadata.json`
- `equity_curve.csv`
- `weekly_equity.csv`
- `weekly_equity.svg`

## UI Usage

Open:

```text
/research/trade-analysis
```

Controls:

| Control | Purpose |
| --- | --- |
| Start date | First recommendation date included |
| End date | Final simulation date |
| Strategy | Portfolio reconstruction variant |
| Capital | Starting capital |
| Charges | Charge model |
| Generate Trade Analysis | Runs report generation |

Result panel shows:

- total return
- CAGR
- max drawdown
- win rate
- total trades
- total charges
- ending value
- CSV download link
- Markdown summary download link

Total return is calculated from completed trade economics:

```text
gross_pnl = exit_value - entry_value
net_pnl = gross_pnl - charges
total_return = sum(net_pnl) / starting_capital
ending_value = starting_capital + sum(net_pnl)
```

States implemented:

- loading
- API error
- empty pre-run state
- completed result state

## Reconstruction Assumptions

The module mirrors the Phase 2E / Phase 3C frozen lifecycle:

| Area | Assumption |
| --- | --- |
| Signal source | `pilot_phase2a.recommendations_daily` |
| Model | `swing_v2_1` |
| Rebalance cadence | first available recommendation date per ISO week |
| Entry | next available trading-day open after signal date |
| Exit | close after planned 20 symbol trading days |
| Weighting | equal target allocation by portfolio size |
| Leverage | none |
| Open positions at report end | force-closed at final available close for completed ledger reporting |
| Sector cap strategy | max 2 open positions per sector, candidate ranks up to 50 |

The module reconstructs trades for analysis. It does not create or update paper trading positions.

## Trade CSV

Generated file:

```text
reports/trade_analysis/<report_id>/trades.csv
```

Columns:

- `trade_id`
- `symbol`
- `sector`
- `strategy`
- `entry_date`
- `entry_price`
- `exit_date`
- `exit_price`
- `holding_days`
- `quantity`
- `entry_value`
- `exit_value`
- `gross_pnl`
- `gross_return_pct`
- `charges`
- `net_pnl`
- `net_return_pct`
- `brokerage`
- `STT`
- `exchange_charges`
- `GST`
- `SEBI_charges`
- `stamp_duty`

## Summary Report

Generated file:

```text
reports/trade_analysis/<report_id>/summary.md
```

Includes:

- parameters
- starting capital
- ending value
- total return
- CAGR
- max drawdown
- weekly equity chart
- weekly equity table
- gross PnL
- total charges
- net PnL
- total trades
- winners
- losers
- win rate
- average winner
- average loser
- total charges
- top 5 winners
- top 5 losers

## Charge Model

`ZERODHA_DEFAULT` is an approximate analysis-only equity delivery model:

| Charge | Formula |
| --- | --- |
| Brokerage | `0` |
| STT | `0.10% * (buy value + sell value)` |
| Exchange charges | `0.00297% * turnover` |
| SEBI charges | `0.0001% * turnover` |
| Stamp duty | `0.015% * buy value` |
| GST | `18% * (brokerage + exchange charges + SEBI charges)` |

The model is for research comparison only. It is not a broker contract-note simulator and must not be used for live order accounting.

## Validation

Focused tests:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_phase6c_trade_analysis.py tests\test_phase5_api.py tests\test_phase5_2_frontend_integration.py
```

Result:

```text
17 passed
```

Frontend build:

```powershell
npm run build
```

Result:

```text
Compiled successfully
```

Smoke report generated against local Angel pilot data:

| Field | Value |
| --- | --- |
| Report ID | `20260613T021213Z_top5_weekly_6e51f76603` |
| Date range | 2026-06-01 to 2026-06-11 |
| Strategy | TOP5_WEEKLY |
| Trades | 5 |
| Total return | -1.90% |
| Win rate | 40.00% |
| Total charges | 2,192.44 |

Every generated `summary.md` embeds:

```markdown
![Weekly Equity Curve](weekly_equity.svg)
```

The underlying weekly points are also written to:

```text
reports/trade_analysis/<report_id>/weekly_equity.csv
```

## Limitations

1. The analysis runs synchronously. Very large date ranges may take longer than a normal UI interaction.
2. Report metadata is filesystem-backed, so moving or deleting `reports/trade_analysis` removes report lookup history.
3. Custom charge models are visible in the UI as a future option but are not enabled in the API.
4. The charge model is approximate and should be treated as a research friction estimate.
5. The service reads pilot Angel tables, not production `recommendation_history`.
6. Forced final exits are used to provide a completed ledger when the requested end date arrives before planned exit.

## Acceptance Confirmation

- Scoring unchanged.
- Ranking unchanged.
- Recommendation generation unchanged.
- Strategy rules unchanged.
- Paper trading lifecycle unchanged.
- Portfolio logic unchanged.
- No live trading added.
- No broker APIs connected.
- No orders placed.
