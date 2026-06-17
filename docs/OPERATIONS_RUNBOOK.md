# NSE Research Platform Operations Runbook

Status: operational guide for local/research deployment.

This runbook explains how to operate the NSE Research Platform / Swing Research Cockpit day to day.

The application is a research and paper-trading system only. It does not place broker orders and does not connect to broker order APIs.

## 1. System Purpose

The app supports:

- Angel SmartAPI 15-minute market-data ingestion
- Daily-bar aggregation and cleaning
- Feature generation
- Sector Rotation ADX Rolling 10 recommendation generation
- Paper portfolio update
- Operations monitoring
- Research dashboards and trade analysis

Current preferred strategy:

```text
Sector Rotation ADX Rolling 10
Internal mode: sector_rotation_adx_r10_vwap25
Recommendation model: sector_rotation_adx_1m3m
Portfolio slots: 10
Weekly candidate count: 5
Entry: T+1 10:30 candle open
VWAP rule: skip if entry > signal-day VWAP + 2.5%
Exit: planned 20 trading-day hold
```

## 2. Important Paths

| Purpose | Path |
| --- | --- |
| Project root | `D:\nse-research-app` |
| Backend API | `app/api/main.py` |
| Frontend app | `frontend/` |
| Daily orchestrator | `scripts/run_full_daily_pipeline.py` |
| PowerShell daily wrapper | `scripts/run_full_daily_pipeline.ps1` |
| Scheduled task installer | `scripts/install_daily_pipeline_task.ps1` |
| Scheduled task uninstaller | `scripts/uninstall_daily_pipeline_task.ps1` |
| Angel sync script | `scripts/sync_angel_daily_data.py` |
| Paper update module | `app.paper_trading.daily_update` |
| Logs | `logs/daily_pipeline/` |
| Pipeline summaries | `reports/phase4b_full_daily_pipeline_<date>.json` |
| Latest paper update | `reports/latest_paper_update.json` |
| Docs | `docs/` |

## 3. Required Services

Before operation, confirm:

1. PostgreSQL is running.
2. Research database is reachable through `DATABASE_URL`.
3. Angel database is reachable through `ANGEL_DATABASE_URL`.
4. Python virtual environment exists at `.venv`.
5. Frontend dependencies are installed under `frontend/node_modules`.
6. `.env` exists and contains required values.

Required `.env` keys:

```text
DATABASE_URL
ANGEL_DATABASE_URL
ANGEL_API_KEY
ANGEL_CLIENT_ID
ANGEL_PASSWORD
ANGEL_TOTP_SECRET
PAPER_PORTFOLIO_ID
PAPER_TRADING_DATA_SOURCE
PAPER_TRADING_PILOT_SCHEMA
PAPER_STRATEGY_MODE
```

Recommended strategy values:

```text
PAPER_TRADING_DATA_SOURCE=pilot_phase2a
PAPER_TRADING_PILOT_SCHEMA=pilot_phase2a
PAPER_STRATEGY_MODE=sector_rotation_adx_r10_vwap25
PAPER_PORTFOLIO_ID=1
```

## 4. Start The Application

### 4.1 Start Backend

From project root:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.api.main:app --reload --host 127.0.0.1 --port 8000
```

Health check:

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8000/health
```

Expected:

- API status is reachable.
- Research DB is connected.
- Angel DB is connected.
- Paper portfolio status is healthy or explicitly degraded with a clear reason.

### 4.2 Start Frontend

```powershell
cd D:\nse-research-app\frontend
npm run dev
```

Open:

```text
http://127.0.0.1:3000
```

Main pages:

- Dashboard
- Recommendations
- Stock Analysis
- Portfolio
- Rolling Portfolio
- Trade Analysis

## 5. Stop The Application

If running in terminals, stop backend/frontend with `Ctrl+C`.

If background processes are running, identify ports:

```powershell
netstat -ano | findstr :8000
netstat -ano | findstr :3000
```

Then stop the matching process id:

```powershell
Stop-Process -Id <PID> -Force
```

Use care: only stop the process you confirmed belongs to this app.

## 6. Daily Operating Procedure

Recommended run time:

```text
18:30 IST, after market close
```

Normal daily run. This keeps data, recommendations, dashboards, and mark-to-market fresh. It does not open new paper positions:

```powershell
.\scripts\run_full_daily_pipeline.ps1 `
  -BusinessDate <YYYY-MM-DD> `
  -PortfolioId 1 `
  -PortfolioSize 10 `
  -MaxCandidateRank 5
```

Example:

```powershell
.\scripts\run_full_daily_pipeline.ps1 `
  -BusinessDate 2026-06-17 `
  -PortfolioId 1 `
  -PortfolioSize 10 `
  -MaxCandidateRank 5
```

Weekly rebalance run. Use this only on the chosen weekly entry cycle:

```powershell
.\scripts\run_full_daily_pipeline.ps1 `
  -BusinessDate <YYYY-MM-DD> `
  -PortfolioId 1 `
  -PortfolioSize 10 `
  -MaxCandidateRank 5 `
  -RebalancePaper
```

Dry run:

```powershell
.\scripts\run_full_daily_pipeline.ps1 `
  -BusinessDate <YYYY-MM-DD> `
  -PortfolioId 1 `
  -DryRun `
  -SyncDryRun
```

Resume after partial failure:

```powershell
.\scripts\run_full_daily_pipeline.ps1 `
  -BusinessDate <YYYY-MM-DD> `
  -PortfolioId 1 `
  -Resume
```

Start from a specific step:

```powershell
.\scripts\run_full_daily_pipeline.ps1 `
  -BusinessDate <YYYY-MM-DD> `
  -PortfolioId 1 `
  -FromStep feature_generation
```

## 7. Daily Pipeline Steps

The full orchestrator runs:

| Order | Step | Purpose |
| ---: | --- | --- |
| 1 | `angel_data_sync` | Fetch missing 15-minute Angel candles |
| 2 | `market_data_validation` | Validate latest source data |
| 3 | `daily_bar_refresh` | Rebuild/refresh cleaned pilot daily bars |
| 4 | `feature_generation` | Refresh required strategy features |
| 5 | `swing_v2_1_scoring` | Compute scores |
| 6 | `recommendation_generation` | Generate daily/weekly recommendations |
| 7 | `decision_journal_capture` | Save recommendation explanation snapshot |
| 8 | `paper_portfolio_update` | Update paper holdings, trades, NAV |
| 9 | `monitoring_report_generation` | Generate daily paper report |

Failure behavior:

- If any step fails, downstream steps stop.
- The failure is recorded in `pipeline_runs`.
- A JSON summary is still written under `reports/`.

## 8. Post-Run Checks

After a run, check:

### 8.1 Pipeline Summary

```powershell
Get-Content reports\phase4b_full_daily_pipeline_<YYYY-MM-DD>.json
```

Look for:

```text
status = success
failed_steps = 0
```

### 8.2 Latest Paper Update

```powershell
Get-Content reports\latest_paper_update.json
```

Look for:

- data source
- recommendation date used
- price date used
- symbols entered
- symbols skipped and reason
- NAV/cash update

### 8.3 API Health

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8000/health
```

### 8.4 Dashboard Pages

Open:

```text
http://127.0.0.1:3000
http://127.0.0.1:3000/recommendations
http://127.0.0.1:3000/portfolio
http://127.0.0.1:3000/research/rolling-portfolio
http://127.0.0.1:3000/research/trade-analysis
```

Confirm:

- Dashboard data freshness is current.
- Recommendations show the latest recommendation date.
- Portfolio shows cash, NAV, open positions, and paper status.
- Operations page shows latest pipeline status.

## 9. Scheduled Task Automation

Default task name:

```text
NSE Research Daily Paper Pipeline
```

### 9.1 Install Dry-Run Task First

```powershell
.\scripts\install_daily_pipeline_task.ps1 `
  -StartTime "18:30" `
  -PortfolioId 1 `
  -DryRun `
  -SyncDryRun `
  -Replace
```

### 9.2 Install Live Daily Task

```powershell
.\scripts\install_daily_pipeline_task.ps1 `
  -StartTime "18:30" `
  -PortfolioId 1 `
  -Replace
```

This daily task does not include `-RebalancePaper`.

### 9.3 Install Weekly Rebalance Task

Use a separate task name and include `-RebalancePaper` only for the weekly rebalance job:

```powershell
.\scripts\install_daily_pipeline_task.ps1 `
  -TaskName "NSE Research Weekly Paper Rebalance" `
  -StartTime "18:30" `
  -PortfolioId 1 `
  -DaysOfWeek Monday `
  -RebalancePaper `
  -Replace
```

Change `-DaysOfWeek Monday` if the approved weekly entry/rebalance day is different.

### 9.4 Verify Task

```powershell
Get-ScheduledTask -TaskName "NSE Research Daily Paper Pipeline"
Get-ScheduledTaskInfo -TaskName "NSE Research Daily Paper Pipeline"
```

### 9.5 Run Task Manually

```powershell
Start-ScheduledTask -TaskName "NSE Research Daily Paper Pipeline"
```

### 9.6 Remove Task

```powershell
.\scripts\uninstall_daily_pipeline_task.ps1
```

## 10. Angel Data Sync

Manual dry run:

```powershell
.\.venv\Scripts\python.exe scripts\sync_angel_daily_data.py `
  --from-date <YYYY-MM-DD> `
  --dry-run `
  --symbol-limit 20 `
  --log-level INFO
```

Live targeted symbol sync:

```powershell
.\.venv\Scripts\python.exe scripts\sync_angel_daily_data.py `
  --symbols ELGIEQUIP `
  --from-date 2026-06-13T09:15:00+05:30 `
  --to-date 2026-06-16T15:30:00+05:30 `
  --log-level INFO
```

Sync report:

```text
reports/phase3f_angel_daily_sync.json
```

## 11. Token Map Operations

Angel token map:

```text
config/angel_symbol_token_map.csv
```

Build/validate from Angel instrument master:

```powershell
.\.venv\Scripts\python.exe scripts\build_angel_token_map.py `
  --instrument-master data\angel_instrument_master.json `
  --dry-run
```

Expected validation:

- Missing symbols: 0 for pilot universe
- Duplicate symbols: 0
- Duplicate tokens: 0
- Invalid exchange symbols: 0

If missing tokens appear:

1. Refresh `data\angel_instrument_master.json`.
2. Rebuild token map.
3. Rerun Angel sync dry-run.

## 12. VWAP Operations

The final strategy uses signal-day VWAP for the entry-quality skip.

Build persistent pilot VWAP:

```powershell
.\.venv\Scripts\python.exe scripts\build_pilot_daily_vwap.py
```

Check if VWAP table exists and has latest date:

```sql
SELECT MAX(date), COUNT(*)
FROM pilot_phase2a.daily_vwap;
```

If Trade Analysis or Rolling Portfolio is slow, confirm `pilot_phase2a.daily_vwap` is populated so the app does not have to repeatedly recompute VWAP from 15-minute candles.

## 13. Paper Portfolio Operations

Initialize portfolio:

```powershell
.\.venv\Scripts\python.exe scripts\initialize_paper_portfolio.py `
  --name "Sector Rotation ADX Rolling 10 Paper" `
  --strategy-mode sector_rotation_adx_r10_vwap25 `
  --initial-capital 1000000
```

Run one paper update:

```powershell
.\.venv\Scripts\python.exe -m app.paper_trading.daily_update `
  --cycle-date <YYYY-MM-DD> `
  --portfolio-id 1 `
  --portfolio-size 10 `
  --max-candidate-rank 5 `
  --strategy-mode sector_rotation_adx_r10_vwap25 `
  --data-source pilot_phase2a `
  --rebalance `
  --output-json reports\latest_paper_update.json
```

For daily mark-to-market only, omit `--rebalance`.

For weekly new-entry rebalance, include `--rebalance`.

Important statuses:

- `entered`: position created.
- `skipped`: candidate not entered.
- `entry_gt_prevday_vwap_threshold`: skipped because entry was more than 2.5% above signal-day VWAP.
- `missing_1030_entry_price`: skipped because the required 10:30 candle was unavailable.
- `portfolio_full`: no free slot.
- `already_held_or_closed_today`: duplicate/re-entry blocked.

## 14. Common Failure Recovery

### 14.1 Backend Returns 503

Check:

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8000/health
```

Common causes:

- `DATABASE_URL` missing or wrong
- `ANGEL_DATABASE_URL` missing or wrong
- Research DB schema not migrated
- Paper portfolio row missing
- PostgreSQL not running

### 14.2 Frontend Shows N/A

Check backend first:

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8000/dashboard
Invoke-RestMethod -Uri http://127.0.0.1:8000/recommendations/latest
Invoke-RestMethod -Uri http://127.0.0.1:8000/portfolio
```

If backend is good, restart frontend.

If backend returns 503, fix DB/config before touching frontend.

### 14.3 Frontend Internal Server Error

Clean build cache:

```powershell
Remove-Item -Recurse -Force frontend\.next
```

Then restart:

```powershell
cd frontend
npm run dev
```

### 14.4 SmartAPI Login Failure

Check `.env`:

```text
ANGEL_API_KEY
ANGEL_CLIENT_ID
ANGEL_PASSWORD
ANGEL_TOTP_SECRET
```

Also confirm dependencies:

```powershell
.\.venv\Scripts\python.exe -c "import SmartApi, pyotp; print('ok')"
```

If missing:

```powershell
.\.venv\Scripts\python.exe -m pip install smartapi-python pyotp
```

### 14.5 Missing 10:30 Candle

Cause:

- Angel data for the symbol/date is incomplete.
- Market day was partial or data sync did not fetch that bar.

Recovery:

```powershell
.\.venv\Scripts\python.exe scripts\sync_angel_daily_data.py `
  --symbols <SYMBOL> `
  --from-date <YYYY-MM-DD>T09:15:00+05:30 `
  --to-date <YYYY-MM-DD>T15:30:00+05:30 `
  --log-level INFO
```

Then rerun from the failed/downstream step:

```powershell
.\scripts\run_full_daily_pipeline.ps1 `
  -BusinessDate <YYYY-MM-DD> `
  -PortfolioId 1 `
  -Resume
```

### 14.6 Pipeline Failed Midway

Inspect latest log:

```powershell
Get-ChildItem logs\daily_pipeline | Sort-Object LastWriteTime -Descending | Select-Object -First 5
```

Inspect summary:

```powershell
Get-Content reports\phase4b_full_daily_pipeline_<YYYY-MM-DD>.json
```

Resume:

```powershell
.\scripts\run_full_daily_pipeline.ps1 `
  -BusinessDate <YYYY-MM-DD> `
  -PortfolioId 1 `
  -Resume
```

## 15. Database Checks

Research DB Alembic revision:

```powershell
.\.venv\Scripts\python.exe -m alembic current
```

Expected current schema includes:

- paper portfolios
- paper positions
- paper trades
- paper daily snapshots
- pipeline runs
- recommendation decision journal

Useful SQL checks:

```sql
SELECT * FROM alembic_version;

SELECT MAX(date)
FROM pilot_phase2a.daily_bars_clean;

SELECT MAX(date)
FROM pilot_phase2a.features_daily;

SELECT MAX(date)
FROM pilot_phase2a.recommendations_daily
WHERE model = 'sector_rotation_adx_1m3m';

SELECT portfolio_id, name, strategy, cash, current_nav, status
FROM paper_portfolios;

SELECT business_date, step_name, status, started_at, completed_at, error_message
FROM pipeline_runs
ORDER BY started_at DESC
LIMIT 20;
```

## 16. Backup And GitHub Export

Check git status:

```powershell
git status --short --branch
```

Commit changes:

```powershell
git add <files>
git commit -m "Describe change"
```

Push:

```powershell
git push
```

Current GitHub remote:

```text
https://github.com/a54000/alpha.git
```

Excluded from Git:

- `.env`
- database dumps
- `.venv`
- `node_modules`
- `.next`
- `reports`
- `results`
- logs
- backups
- bulky local data files

## 17. Release / Change-Control Rules

Do not change production/paper strategy behavior casually.

Before changing strategy rules:

1. Run a read-only diagnostic.
2. Document the result under `docs/`.
3. Run a full portfolio backtest.
4. Compare CAGR, drawdown, Sharpe, profit factor, trade count, win rate, and cash usage.
5. Only then promote as a selectable research/paper mode.

Frozen current paper mode:

```text
sector_rotation_adx_r10_vwap25
```

Do not overwrite legacy Swing V2.1 modes unless explicitly intended.

## 18. Security Notes

- Never commit `.env`.
- Never commit Angel credentials.
- Never commit database dumps to GitHub.
- The app is read-only from the UI perspective and does not place orders.
- Any future broker order integration must be designed as a separate, explicitly approved project.

## 19. Normal Day Checklist

1. Confirm PostgreSQL is running.
2. Confirm backend health endpoint is healthy.
3. Confirm frontend loads.
4. Run pipeline after market close or confirm scheduled task ran.
5. Check `reports/phase4b_full_daily_pipeline_<date>.json`.
6. Check `reports/latest_paper_update.json`.
7. Open dashboard and portfolio pages.
8. Confirm recommendations date and market data date are current.
9. Record any skipped candidates and reasons.

## 20. Emergency Checklist

If something looks wrong:

1. Do not change strategy code.
2. Do not manually patch database tables.
3. Check `/health`.
4. Check latest pipeline log.
5. Check latest pipeline summary JSON.
6. Check Angel sync report.
7. If data is missing, rerun sync for the affected symbol/date.
8. Resume the pipeline.
9. Document the incident and recovery action.
