# Phase 5.13 Daily Pipeline Automation

## Objective

Automate the daily market-data ingestion and paper trading workflow using the existing frozen Swing V2.1 pipeline.

This phase does not change strategy, scoring, recommendation logic, paper trading lifecycle, broker integration, or database schema.

## Automation Components

Wrapper:

```text
scripts/run_full_daily_pipeline.ps1
```

Installer:

```text
scripts/install_daily_pipeline_task.ps1
```

Uninstaller:

```text
scripts/uninstall_daily_pipeline_task.ps1
```

## Daily Entry Point

The daily scheduled task runs without weekly rebalance:

```powershell
scripts\run_full_daily_pipeline.ps1 -PortfolioId 1 -PortfolioSize 10 -MaxCandidateRank 5
```

The wrapper calls:

```powershell
.\.venv\Scripts\python.exe scripts\run_full_daily_pipeline.py --business-date <today> --portfolio-id 1 --portfolio-size 10 --max-candidate-rank 5
```

## Logs

Each run writes a timestamped log:

```text
logs/daily_pipeline/daily_pipeline_<business_date>_<timestamp>.log
```

The pipeline summary remains:

```text
reports/phase4b_full_daily_pipeline_<business_date>.json
```

## Recommended Schedule

Recommended first production schedule:

```text
Daily at 18:30 IST
```

Reason:

- Market is closed.
- Intraday data should be available.
- The paper portfolio update can process the completed session.

## Install Scheduled Task

Start with a dry-run scheduled task first:

```powershell
.\scripts\install_daily_pipeline_task.ps1 -StartTime "18:30" -PortfolioId 1 -DryRun -SyncDryRun -Replace
```

After one successful dry-run schedule, install live daily automation:

```powershell
.\scripts\install_daily_pipeline_task.ps1 -StartTime "18:30" -PortfolioId 1 -Replace
```

Install a separate weekly rebalance task only on the selected weekly rebalance day:

```powershell
.\scripts\install_daily_pipeline_task.ps1 -TaskName "NSE Research Weekly Paper Rebalance" -StartTime "18:30" -PortfolioId 1 -DaysOfWeek Monday -RebalancePaper -Replace
```

Change `-DaysOfWeek Monday` to the selected weekly entry/rebalance day if a different day is approved.

The default task name is:

```text
NSE Research Daily Paper Pipeline
```

## Manual Wrapper Test

Dry-run:

```powershell
.\scripts\run_full_daily_pipeline.ps1 -BusinessDate 2026-06-12 -PortfolioId 1 -DryRun -SyncDryRun
```

Daily live run:

```powershell
.\scripts\run_full_daily_pipeline.ps1 -BusinessDate 2026-06-12 -PortfolioId 1
```

Weekly rebalance run:

```powershell
.\scripts\run_full_daily_pipeline.ps1 -BusinessDate 2026-06-12 -PortfolioId 1 -RebalancePaper
```

Resume:

```powershell
.\scripts\run_full_daily_pipeline.ps1 -BusinessDate 2026-06-12 -PortfolioId 1 -Resume
```

Start from a specific step:

```powershell
.\scripts\run_full_daily_pipeline.ps1 -BusinessDate 2026-06-12 -PortfolioId 1 -FromStep feature_generation
```

## Verify Scheduled Task

```powershell
Get-ScheduledTask -TaskName "NSE Research Daily Paper Pipeline"
```

Check latest run state:

```powershell
Get-ScheduledTaskInfo -TaskName "NSE Research Daily Paper Pipeline"
```

Run manually from Task Scheduler:

```powershell
Start-ScheduledTask -TaskName "NSE Research Daily Paper Pipeline"
```

## Uninstall Scheduled Task

```powershell
.\scripts\uninstall_daily_pipeline_task.ps1
```

## Failure Recovery

### Angel Login Failure

Check:

- `ANGEL_API_KEY`
- `ANGEL_CLIENT_ID`
- `ANGEL_PASSWORD`
- `ANGEL_TOTP_SECRET`

Then rerun:

```powershell
.\scripts\run_full_daily_pipeline.ps1 -BusinessDate <YYYY-MM-DD> -PortfolioId 1 -Resume
```

### Missing Token Failure

Refresh:

```powershell
.\.venv\Scripts\python.exe scripts\build_angel_token_map.py --instrument-master data\angel_instrument_master.json
```

Then rerun:

```powershell
.\scripts\run_full_daily_pipeline.ps1 -BusinessDate <YYYY-MM-DD> -PortfolioId 1 -Resume
```

### Partial Pipeline Failure

Inspect:

```text
logs/daily_pipeline/
reports/phase4b_full_daily_pipeline_<business_date>.json
```

Resume:

```powershell
.\scripts\run_full_daily_pipeline.ps1 -BusinessDate <YYYY-MM-DD> -PortfolioId 1 -Resume
```

### Re-run From Step

```powershell
.\scripts\run_full_daily_pipeline.ps1 -BusinessDate <YYYY-MM-DD> -PortfolioId 1 -FromStep recommendation_generation
```

## Operational Readiness Checklist

- Token map generated.
- Sync dry-run reports `missing_tokens: 0`.
- Full pipeline dry-run succeeds.
- Live manual sync succeeds.
- Live manual full pipeline succeeds.
- Scheduled dry-run succeeds.
- Scheduled live run succeeds.
