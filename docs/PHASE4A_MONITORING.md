# Phase 4A Monitoring

Generated on: 2026-06-12

## Objective

Create a live paper trading monitoring layer for frozen Swing V2.1 after the Phase 3F daily pipeline.

## Entry Point

```powershell
python scripts/generate_daily_paper_report.py --report-date 2026-06-12 --portfolio-id 1
```

Output:

```text
reports/daily_paper_report_2026-06-12.md
```

## Inputs

The report reads existing state only:

- `reports/phase3f_daily_cycle.json`
- `reports/phase3f_angel_daily_sync.json`
- `reports/phase3f_feature_validation.json`
- `reports/phase3f_recommendation_validation.json`
- `angel_data.ohlcv_15min`
- `angel_data.fetch_progress`
- `angel_data.pilot_phase2a.daily_bars_clean`
- `angel_data.pilot_phase2a.features_daily`
- `angel_data.pilot_phase2a.recommendations_daily`
- `paper_portfolios`
- `paper_positions`
- `paper_trades`
- `paper_daily_snapshots`

It can still generate a partial report when some inputs are unavailable. Missing inputs become report gaps and alerts rather than strategy changes.

## Report Sections

1. Alerts
2. Pipeline status
3. Portfolio status
4. Risk metrics
5. Sector concentration
6. Strategy health
7. Top ranked stocks
8. Open positions
9. Benchmark comparison
10. Constraints

## Pipeline Status

The report checks:

- daily cycle status from Phase 3F report JSON
- latest Angel candle timestamp
- latest daily bar date
- latest cleaned daily bar date
- latest feature date
- latest recommendation date
- last successful sync from `fetch_progress`
- invalid OHLC rows on the report date
- zero-volume clean daily bars on the report date

## Portfolio Status

The report reads the latest paper snapshot on or before the report date:

- NAV
- cash
- invested amount
- open positions
- realized PnL
- unrealized PnL

Open positions are listed with:

- symbol
- sector
- entry date
- market value
- unrealized PnL
- planned exit date

## Risk Metrics

The monitoring layer calculates:

- current drawdown from paper NAV history
- exposure as invested market value divided by NAV
- sector concentration from open position market values
- daily turnover from paper trades exiting on the report date
- turnover divided by NAV

## Strategy Health

The report reads the frozen Swing V2.1 recommendation table and summarizes:

- recommendation count
- average score
- minimum score
- maximum score
- top ranked stocks

No scoring functions are called by the monitor. It only reads the generated recommendation output.

## Benchmark Comparison

Benchmark comparison uses the benchmark fields already stored in `paper_daily_snapshots`:

- benchmark close
- benchmark daily return

The monitoring layer does not fetch external benchmark data.

## Alerts

Configured alert types:

| Alert | Default trigger |
|---|---:|
| Missing data | latest Angel candle unavailable or more than one calendar day stale |
| Invalid OHLC | invalid clean daily bars on report date |
| Zero volume anomaly | zero-volume clean daily bars on report date |
| Zero recommendations | recommendation count equals zero |
| Abnormal recommendation count | count below 3 or above 20 |
| Excessive concentration | max sector concentration >= 40% |
| Drawdown threshold | current drawdown <= -10% |

Thresholds can be overridden:

```powershell
python scripts/generate_daily_paper_report.py `
  --report-date 2026-06-12 `
  --portfolio-id 1 `
  --drawdown-alert -0.12 `
  --concentration-alert 0.50 `
  --recommendation-low-alert 3 `
  --recommendation-high-alert 20
```

## Operations Flow

Recommended daily sequence:

1. Run Phase 3F daily cycle.
2. Confirm Phase 3F completed successfully.
3. Generate the Phase 4A daily paper report.
4. Review alerts.
5. If alerts are present, resolve data or operations issues before treating the paper recommendation state as healthy.

## Constraints

Phase 4A is read-only monitoring:

- no strategy changes
- no scoring changes
- no recommendation generation changes
- no new factors
- no parameter optimization
- no broker API connections
- no orders

## Verification

Focused tests:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_phase4a_monitoring.py
```

Compile check:

```powershell
.\.venv\Scripts\python.exe -m py_compile scripts/generate_daily_paper_report.py
```
