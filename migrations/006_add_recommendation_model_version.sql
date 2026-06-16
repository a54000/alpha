ALTER TABLE recommendation_history ADD COLUMN IF NOT EXISTS model_version_id INTEGER REFERENCES model_version(version_id);
