# NSE Research Platform

A research and paper-trading platform for Indian equity swing strategies, focused on NSE-listed stocks and Angel SmartAPI market data.

The current user-facing strategy candidate is **Sector Rotation ADX Rolling 10**. It is a research and paper-trading system only: the application does not place broker orders, does not connect to live order APIs, and does not change strategy rules automatically.

## What This Project Does

- Ingests 15-minute OHLCV candles from Angel SmartAPI.
- Aggregates and validates pilot daily bars.
- Generates sector rotation, trend, and momentum features.
- Produces weekly stock recommendations for the frozen strategy candidate.
- Runs rolling portfolio and historical trade-analysis backtests.
- Tracks a paper portfolio using the same rules used in validation.
- Provides a read-only FastAPI backend and Next.js dashboard.
- Stores research documentation, migration plans, diagnostics, and validation results.

## Current Strategy Candidate

**Name:** Sector Rotation ADX Rolling 10

**Internal mode:** `sector_rotation_adx_r10_vwap25`

**Recommendation model:** `sector_rotation_adx_1m3m`

Rules:

1. Rank sectors using 1-month and 3-month sector strength.
2. Sector score = `40% * 1M sector return + 60% * 3M sector return`.
3. Generate up to the top 5 weekly recommendations.
4. Maintain a rolling 10-slot portfolio.
5. Enter on the next trading day at the 10:30 15-minute candle open.
6. Skip entry if the 10:30 entry price is more than 2.5% above the signal day's VWAP.
7. Hold each entered position for 20 trading days.
8. Exit only after the planned holding period completes.
9. No stop-loss, RSI filter, daily fill-up, calendar-month holding, or broker execution is part of the frozen candidate.

See:

- [`docs/ROLLING10_1M3M_VWAP25_FROZEN_CANDIDATE.md`](docs/ROLLING10_1M3M_VWAP25_FROZEN_CANDIDATE.md)
- [`docs/SECTOR_ROTATION_ADX_STRATEGY_SPEC.md`](docs/SECTOR_ROTATION_ADX_STRATEGY_SPEC.md)
- [`docs/SECTOR_ROTATION_ADX_SYSTEM.md`](docs/SECTOR_ROTATION_ADX_SYSTEM.md)

## Application Modules

```text
app/
  api/                FastAPI services and read-only dashboard endpoints
  backtesting/        Portfolio and strategy backtest helpers
  indicators/         Feature generation and indicator calculations
  ingestion/          Data loading and validation components
  paper_trading/      Paper portfolio engine and data-source abstraction
  recommendations/    Recommendation generation logic
  scoring/            Scoring logic
  sectors/            Sector strength computation
  utils/              Shared configuration and utilities

alembic/              Alembic database migrations
config/               Runtime mapping files, such as Angel symbol-token map
configs/              Core YAML configuration
db/                   SQLAlchemy models and database connection helpers
docs/                 Architecture, audits, validation, and phase documentation
frontend/             Next.js Research Cockpit UI
migrations/           Legacy SQL migration files
scripts/              Data, research, paper-trading, and operations scripts
sql/                  SQL helpers
tests/                Pytest coverage
```

Generated folders such as `reports/`, `results/`, `logs/`, `backups/`, local database dumps, `.venv`, `.next`, and `node_modules` are intentionally excluded from Git.

## Tech Stack

Backend:

- Python
- FastAPI
- SQLAlchemy
- Alembic
- PostgreSQL
- Pandas
- Angel SmartAPI client

Frontend:

- Next.js 14
- React 18
- TypeScript
- Ant Design icons
- Lucide icons

Databases:

- Research database for application state, paper trading, recommendations, migrations, and dashboards.
- Angel market-data database for 15-minute OHLCV candles.

## Required Environment

Copy `.env.example` to `.env` and fill in local values:

```powershell
Copy-Item .env.example .env
```

Required keys:

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

Example values are provided in [`.env.example`](.env.example). Do not commit real credentials.

## Local Setup

Create and activate a Python virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install Python dependencies:

```powershell
pip install -r requirements.txt
```

Install frontend dependencies:

```powershell
cd frontend
npm install
cd ..
```

## Database Setup

This project expects PostgreSQL databases to already exist and be reachable through:

- `DATABASE_URL`
- `ANGEL_DATABASE_URL`

Run Alembic migrations for the research database:

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
```

Useful migration references:

- [`docs/PHASE5_4_RESEARCH_DB_MIGRATION_AUDIT.md`](docs/PHASE5_4_RESEARCH_DB_MIGRATION_AUDIT.md)
- [`docs/PHASE5_4_1_MIGRATION_EXECUTION_PLAN.md`](docs/PHASE5_4_1_MIGRATION_EXECUTION_PLAN.md)
- [`docs/PHASE5_4_2_SCHEMA_UPGRADE_RESULTS.md`](docs/PHASE5_4_2_SCHEMA_UPGRADE_RESULTS.md)

## Run The Backend

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.api.main:app --reload --host 127.0.0.1 --port 8000
```

Health check:

```text
http://127.0.0.1:8000/health
```

Important API endpoints:

- `GET /health`
- `GET /dashboard`
- `GET /recommendations/latest`
- `GET /recommendations/{symbol}/explanation`
- `GET /portfolio`
- `GET /trades`
- `GET /pipeline/status`
- `GET /research/metrics`
- `GET /stock-analysis/search`
- `GET /stock-analysis/{symbol}`
- `POST /research/trade-analysis/run`
- `GET /research/trade-analysis/{report_id}`

## Run The Frontend

```powershell
cd frontend
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

## Daily Paper-Trading Operations

The daily operational pipeline is implemented as a controlled script:

```powershell
.\.venv\Scripts\python.exe scripts\run_full_daily_pipeline.py `
  --business-date YYYY-MM-DD `
  --portfolio-id 1 `
  --paper-strategy-mode sector_rotation_adx_r10_vwap25 `
  --rebalance-paper
```

Use dry-run mode before a real run:

```powershell
.\.venv\Scripts\python.exe scripts\run_full_daily_pipeline.py `
  --business-date YYYY-MM-DD `
  --portfolio-id 1 `
  --dry-run `
  --sync-dry-run
```

Daily pipeline steps:

1. Sync latest Angel candles.
2. Validate market data freshness.
3. Refresh daily bars.
4. Refresh features.
5. Compute strategy scores.
6. Generate recommendations.
7. Update paper portfolio.
8. Generate monitoring output.

See:

- [`docs/OPERATIONS_RUNBOOK.md`](docs/OPERATIONS_RUNBOOK.md)
- [`docs/PHASE3F_DAILY_OPERATIONS.md`](docs/PHASE3F_DAILY_OPERATIONS.md)
- [`docs/PHASE4B_ORCHESTRATION.md`](docs/PHASE4B_ORCHESTRATION.md)
- [`docs/PHASE5_13_DAILY_AUTOMATION.md`](docs/PHASE5_13_DAILY_AUTOMATION.md)

## Angel Instrument Mapping

Angel symbol-token mapping is stored in:

```text
config/angel_symbol_token_map.csv
```

Build or validate the map:

```powershell
.\.venv\Scripts\python.exe scripts\build_angel_token_map.py `
  --instrument-master data\angel_instrument_master.json `
  --dry-run
```

See:

- [`docs/PHASE5_11_INGESTION_READINESS.md`](docs/PHASE5_11_INGESTION_READINESS.md)
- [`docs/PHASE5_12_TOKEN_MAP_SETUP.md`](docs/PHASE5_12_TOKEN_MAP_SETUP.md)

## Paper Portfolio Initialization

Initialize a paper portfolio:

```powershell
.\.venv\Scripts\python.exe scripts\initialize_paper_portfolio.py `
  --name "Sector Rotation ADX Rolling 10 Paper" `
  --strategy-mode sector_rotation_adx_r10_vwap25 `
  --initial-capital 1000000
```

See:

- [`docs/PHASE5_5_PAPER_PORTFOLIO_INITIALIZATION.md`](docs/PHASE5_5_PAPER_PORTFOLIO_INITIALIZATION.md)
- [`docs/PAPER_TRADING_30_DAY_OBSERVATION_START.md`](docs/PAPER_TRADING_30_DAY_OBSERVATION_START.md)

## Research And Backtesting

The project contains several diagnostic and experiment scripts under `scripts/`, including:

- Rolling 10 portfolio backtests.
- Sector ranking experiments.
- VWAP entry-quality experiments.
- MAE/MFE and stop-loss diagnostics.
- Monte Carlo analysis.
- Trade analysis reports.
- Breadth and regime diagnostics.

Key research documents:

- [`docs/BACKTEST_EXECUTION_AUDIT.md`](docs/BACKTEST_EXECUTION_AUDIT.md)
- [`docs/BACKTEST_REMEDIATION_IMPLEMENTATION.md`](docs/BACKTEST_REMEDIATION_IMPLEMENTATION.md)
- [`docs/SWING_ENTRY_QUALITY_RESEARCH.md`](docs/SWING_ENTRY_QUALITY_RESEARCH.md)
- [`docs/SWING_LOSER_PATTERN_ANALYSIS.md`](docs/SWING_LOSER_PATTERN_ANALYSIS.md)
- [`docs/PHASE5_20_ROLLING_10_COHORT_BACKTEST_POST_FIX.md`](docs/PHASE5_20_ROLLING_10_COHORT_BACKTEST_POST_FIX.md)

## Tests

Run backend tests:

```powershell
.\.venv\Scripts\python.exe -m pytest
```

Build frontend:

```powershell
cd frontend
npm run build
```

## GitHub Export Notes

This repository is configured to exclude local-only and sensitive artifacts:

- `.env`
- database dumps
- local virtual environments
- frontend build output
- `node_modules`
- generated reports and results
- logs and backups
- bulky local data files

Use `.env.example` as the safe configuration template.

## Safety Boundary

This is a research and paper-trading platform. It does not place broker orders and should not be treated as investment advice.

Before using any strategy with real capital:

1. Validate data quality.
2. Confirm no look-ahead bias.
3. Confirm fill-price assumptions.
4. Run paper trading for a sufficient live observation period.
5. Review drawdown, liquidity, slippage, and tax impact.
6. Make independent investment decisions.

## License

No license has been selected yet. Until a license is added, all rights are reserved by the repository owner.
