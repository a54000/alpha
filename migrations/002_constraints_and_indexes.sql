CREATE UNIQUE INDEX uq_model_version_single_active
    ON model_version (model, is_active)
    WHERE is_active = TRUE;

CREATE INDEX ix_prices_daily_symbol ON prices_daily (symbol);
CREATE INDEX ix_prices_daily_date ON prices_daily (date);
CREATE INDEX ix_prices_daily_symbol_date ON prices_daily (symbol, date);

CREATE INDEX ix_features_daily_symbol ON features_daily (symbol);
CREATE INDEX ix_features_daily_date ON features_daily (date);
CREATE INDEX ix_features_daily_symbol_date ON features_daily (symbol, date);
CREATE INDEX ix_features_daily_date_rs_rank_pct ON features_daily (date, rs_rank_pct);

CREATE INDEX ix_daily_scores_symbol ON daily_scores (symbol);
CREATE INDEX ix_daily_scores_date ON daily_scores (date);
CREATE INDEX ix_daily_scores_symbol_date ON daily_scores (symbol, date);

CREATE INDEX ix_recommendation_history_symbol ON recommendation_history (symbol);
CREATE INDEX ix_recommendation_history_date ON recommendation_history (date);
CREATE INDEX ix_recommendation_history_symbol_date ON recommendation_history (symbol, date);

CREATE INDEX ix_sector_daily_sector ON sector_daily (sector);
CREATE INDEX ix_sector_daily_date ON sector_daily (date);
CREATE INDEX ix_sector_daily_sector_date ON sector_daily (sector, date);

CREATE INDEX ix_universe_snapshot_symbol ON universe_snapshot (symbol);
CREATE INDEX ix_universe_snapshot_date ON universe_snapshot (date);
CREATE INDEX ix_universe_snapshot_symbol_date ON universe_snapshot (symbol, date);

CREATE INDEX ix_trade_log_symbol_entry_date ON trade_log (symbol, entry_date);
CREATE INDEX ix_trade_log_strategy_entry_date ON trade_log (strategy, entry_date);
CREATE INDEX ix_trade_log_run_type_exit_date ON trade_log (run_type, exit_date);

CREATE INDEX ix_pipeline_runs_run_date_job_name ON pipeline_runs (run_date, job_name);
CREATE INDEX ix_pipeline_runs_failed ON pipeline_runs (status) WHERE status = 'failed';

CREATE INDEX ix_data_quality_log_date_job_name ON data_quality_log (date, job_name);
CREATE INDEX ix_data_quality_log_non_ok ON data_quality_log (status) WHERE status != 'ok';
