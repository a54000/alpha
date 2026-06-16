SELECT create_hypertable('prices_daily', 'date', if_not_exists => TRUE);
SELECT create_hypertable('features_daily', 'date', if_not_exists => TRUE);
SELECT create_hypertable('daily_scores', 'date', if_not_exists => TRUE);
SELECT create_hypertable('recommendation_history', 'date', if_not_exists => TRUE);
SELECT create_hypertable('sector_daily', 'date', if_not_exists => TRUE);
