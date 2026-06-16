ALTER TABLE features_daily
    ADD COLUMN IF NOT EXISTS distance_from_52w_high NUMERIC(6,2);

ALTER TABLE features_daily
    ADD COLUMN IF NOT EXISTS is_52w_breakout BOOLEAN;
