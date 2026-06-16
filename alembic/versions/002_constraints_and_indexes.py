"""Add indexes and additional constraints."""

from __future__ import annotations

from alembic import op


revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ix_prices_daily_symbol", "prices_daily", ["symbol"])
    op.create_index("ix_prices_daily_date", "prices_daily", ["date"])
    op.create_index("ix_prices_daily_symbol_date", "prices_daily", ["symbol", "date"])

    op.create_index("ix_features_daily_symbol", "features_daily", ["symbol"])
    op.create_index("ix_features_daily_date", "features_daily", ["date"])
    op.create_index("ix_features_daily_symbol_date", "features_daily", ["symbol", "date"])
    op.create_index("ix_features_daily_date_rs_rank_pct", "features_daily", ["date", "rs_rank_pct"])

    op.create_index("ix_daily_scores_symbol", "daily_scores", ["symbol"])
    op.create_index("ix_daily_scores_date", "daily_scores", ["date"])
    op.create_index("ix_daily_scores_symbol_date", "daily_scores", ["symbol", "date"])

    op.create_index("ix_recommendation_history_symbol", "recommendation_history", ["symbol"])
    op.create_index("ix_recommendation_history_date", "recommendation_history", ["date"])
    op.create_index("ix_recommendation_history_symbol_date", "recommendation_history", ["symbol", "date"])

    op.create_index("ix_sector_daily_sector", "sector_daily", ["sector"])
    op.create_index("ix_sector_daily_date", "sector_daily", ["date"])
    op.create_index("ix_sector_daily_sector_date", "sector_daily", ["sector", "date"])

    op.create_index("ix_universe_snapshot_symbol", "universe_snapshot", ["symbol"])
    op.create_index("ix_universe_snapshot_date", "universe_snapshot", ["date"])
    op.create_index("ix_universe_snapshot_symbol_date", "universe_snapshot", ["symbol", "date"])

    op.create_index("ix_trade_log_symbol_entry_date", "trade_log", ["symbol", "entry_date"])
    op.create_index("ix_trade_log_strategy_entry_date", "trade_log", ["strategy", "entry_date"])
    op.create_index("ix_trade_log_run_type_exit_date", "trade_log", ["run_type", "exit_date"])

    op.create_index("ix_pipeline_runs_run_date_job_name", "pipeline_runs", ["run_date", "job_name"])
    op.create_index("ix_pipeline_runs_failed", "pipeline_runs", ["status"], postgresql_where="status = 'failed'")

    op.create_index("ix_data_quality_log_date_job_name", "data_quality_log", ["date", "job_name"])
    op.create_index("ix_data_quality_log_non_ok", "data_quality_log", ["status"], postgresql_where="status != 'ok'")

    op.create_index("uq_model_version_single_active", "model_version", ["model", "is_active"], unique=True, postgresql_where="is_active = TRUE")


def downgrade() -> None:
    for index_name, table_name in [
        ("uq_model_version_single_active", "model_version"),
        ("ix_data_quality_log_non_ok", "data_quality_log"),
        ("ix_data_quality_log_date_job_name", "data_quality_log"),
        ("ix_pipeline_runs_failed", "pipeline_runs"),
        ("ix_pipeline_runs_run_date_job_name", "pipeline_runs"),
        ("ix_trade_log_run_type_exit_date", "trade_log"),
        ("ix_trade_log_strategy_entry_date", "trade_log"),
        ("ix_trade_log_symbol_entry_date", "trade_log"),
        ("ix_universe_snapshot_symbol_date", "universe_snapshot"),
        ("ix_universe_snapshot_date", "universe_snapshot"),
        ("ix_universe_snapshot_symbol", "universe_snapshot"),
        ("ix_sector_daily_sector_date", "sector_daily"),
        ("ix_sector_daily_date", "sector_daily"),
        ("ix_sector_daily_sector", "sector_daily"),
        ("ix_recommendation_history_symbol_date", "recommendation_history"),
        ("ix_recommendation_history_date", "recommendation_history"),
        ("ix_recommendation_history_symbol", "recommendation_history"),
        ("ix_daily_scores_symbol_date", "daily_scores"),
        ("ix_daily_scores_date", "daily_scores"),
        ("ix_daily_scores_symbol", "daily_scores"),
        ("ix_features_daily_date_rs_rank_pct", "features_daily"),
        ("ix_features_daily_symbol_date", "features_daily"),
        ("ix_features_daily_date", "features_daily"),
        ("ix_features_daily_symbol", "features_daily"),
        ("ix_prices_daily_symbol_date", "prices_daily"),
        ("ix_prices_daily_date", "prices_daily"),
        ("ix_prices_daily_symbol", "prices_daily"),
    ]:
        op.drop_index(index_name, table_name=table_name)

