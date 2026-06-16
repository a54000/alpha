# Schema Validation Report

Date: 2026-06-10

## Environment

- PostgreSQL 18.3 via local Homebrew server
- Connection: Unix socket at `/private/tmp`, port `5433`
- Python validation environment: `.venv`

## Validation Summary

- `alembic upgrade head`: passed
- `alembic downgrade base`: passed
- `alembic upgrade head` after rollback: passed
- Test suite: passed (`10 passed`)
- Docker validation: not run, because `docker` is not installed in this environment

## Tables

Table count excluding `alembic_version`: `13`

Tables:

- `backtest_runs`
- `daily_scores`
- `data_quality_log`
- `features_daily`
- `model_version`
- `pipeline_runs`
- `portfolio_positions`
- `prices_daily`
- `recommendation_history`
- `sector_daily`
- `symbol_master`
- `trade_log`
- `universe_snapshot`

## Indexes

Indexes present:

- `prices_daily`: `ix_prices_daily_symbol`, `ix_prices_daily_date`, `ix_prices_daily_symbol_date`, `uq_prices_daily_symbol_date`
- `features_daily`: `ix_features_daily_symbol`, `ix_features_daily_date`, `ix_features_daily_symbol_date`, `ix_features_daily_date_rs_rank_pct`, `uq_features_daily_symbol_date`
- `daily_scores`: `ix_daily_scores_symbol`, `ix_daily_scores_date`, `ix_daily_scores_symbol_date`, `uq_daily_scores_symbol_date`
- `recommendation_history`: `ix_recommendation_history_symbol`, `ix_recommendation_history_date`, `ix_recommendation_history_symbol_date`, `uq_recommendation_history_date_model_symbol`
- `sector_daily`: `ix_sector_daily_sector`, `ix_sector_daily_date`, `ix_sector_daily_sector_date`, `uq_sector_daily_sector_date`
- `universe_snapshot`: `ix_universe_snapshot_symbol`, `ix_universe_snapshot_date`, `ix_universe_snapshot_symbol_date`
- `trade_log`: `ix_trade_log_symbol_entry_date`, `ix_trade_log_strategy_entry_date`, `ix_trade_log_run_type_exit_date`
- `pipeline_runs`: `ix_pipeline_runs_run_date_job_name`, `ix_pipeline_runs_failed`
- `data_quality_log`: `ix_data_quality_log_date_job_name`, `ix_data_quality_log_non_ok`
- `model_version`: `uq_model_version_single_active`

## Foreign Keys

Foreign keys present:

- `prices_daily.symbol -> symbol_master.symbol`
- `features_daily.symbol -> symbol_master.symbol`
- `daily_scores.symbol -> symbol_master.symbol`
- `daily_scores.model_version_id -> model_version.version_id`
- `recommendation_history.symbol -> symbol_master.symbol`
- `portfolio_positions.symbol -> symbol_master.symbol`
- `trade_log.symbol -> symbol_master.symbol`
- `universe_snapshot.symbol -> symbol_master.symbol`

## Unique Constraints

Unique constraints present:

- `prices_daily`: `UNIQUE(symbol, date)`
- `features_daily`: `UNIQUE(symbol, date)`
- `daily_scores`: `UNIQUE(symbol, date)`
- `recommendation_history`: `UNIQUE(date, model, symbol)`
- `sector_daily`: `UNIQUE(sector, date)`

## Hypertables

- No hypertables were created in this environment.
- Reason: TimescaleDB extension is not installed on the local PostgreSQL instance.

## Test Results

- `10 passed`
- 3 warnings from Alembic about missing `path_separator=os` in `alembic.ini`

## Mismatches Found

### `docs/DB_SCHEMA.md` vs current models/migrations

- The document uses `sector_daily_ranks`, while the implemented schema uses `sector_daily` to match the requested table name.
- `features_daily` now includes `is_eligible` and `avg_traded_value` from the amendment section, which are implemented in models and migrations.
- `DB_SCHEMA.md` still describes `prices`, while the implemented table name is `prices_daily` per the requested schema layer.

### Models vs migrations

- The SQLAlchemy models and Alembic migrations are aligned on table names, keys, constraints, and indexes.
- The Timescale hypertable step is intentionally fail-soft when the extension is unavailable, so hypertables are not created in this environment.

### Environment vs desired target

- Docker validation could not be performed because `docker` is not installed here.
- TimescaleDB-specific validation could not be completed because the extension is not installed in the local PostgreSQL server.

