# Swing V2.1 Implementation

Date: 2026-06-11

## Objective

Implement a separate research scoring model:

```text
swing_v2_1
```

This model does not modify V1, Swing V2, Positional V2, or their recommendation/backtest behavior.

## Model Definition

Swing V2.1 uses:

- Sector Rank
- ADX

Entry filters:

- EMA200 extension <= 25%
- Prior 20d return <= 15%

The score is stored only when the entry filters pass. If a stock fails either entry filter, `swing_v2_1_score` is `NULL` and the stock is not eligible for `swing_v2_1` recommendations.

## Code Changes

### Database Model

File:

- `db/models.py`

Change:

- Added `DailyScores.swing_v2_1_score`.

### Migration

File:

- `alembic/versions/009_add_swing_v2_1_score.py`

Change:

- Adds nullable `daily_scores.swing_v2_1_score NUMERIC(5, 1)`.

Note:

- The local venv does not expose the normal Alembic CLI/module entrypoint.
- The research runner also includes a guarded column check and `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` path so the local research run can proceed safely.

### Scoring

File:

- `app/scoring/compute_scores.py`

Changes:

- Added `compute_swing_v2_1_score()`.
- Reused existing V2 scoring primitives:
  - `score_swing_v2_adx`
  - `score_swing_v2_sector`
- Added prior 20-trading-day return lookup during score generation.
- Added `swing_v2_1_score` to daily score upserts.

Score formula:

```text
(ADX score + Sector Rank score) / 35 * 100
```

Filter behavior:

```text
score = NULL unless:
close / ema_200 - 1 <= 0.25
and
prior_20d_return <= 0.15
```

### Recommendation Generation

File:

- `app/recommendations/generate_recommendations.py`

Changes:

- Added `SWING_V2_1_RECOMMENDATION_CONFIG`.
- Added `RecommendationGenerator.generate_swing_v2_1()`.
- Added `swing_v2_1_score` to candidate loading.
- Recommendations are stored under model name `swing_v2_1`.

Recommendation rules:

- Minimum score: 70
- Top 20 per signal date
- Independent from `swing`, `swing_v2`, `positional`, and `positional_v2`

### Backtesting

File:

- `app/backtesting/run_backtest.py`

Change:

- Added `swing_v2_1` to `BACKTEST_CONFIGS`.

Backtest settings:

- Horizons: 5d, 10d, 20d
- Primary horizon: 20d
- Entry: next-trading-day open
- Exit: fixed-horizon close
- Benchmark: same current benchmark methodology

### Runner

File:

- `scripts/run_swing_v2_1_backtest.py`

Responsibilities:

1. Ensure `swing_v2_1_score` column exists.
2. Backfill V2.1 scores.
3. Clear only existing `swing_v2_1` recommendations.
4. Generate `swing_v2_1` recommendations.
5. Run the `swing_v2_1` backtest.
6. Export `reports/swing_v2_1_results.json`.
7. Include comparison against V1 Swing and Swing V2.

## Generated Output

Report:

- `reports/swing_v2_1_results.json`

Documentation:

- `docs/SWING_V2_1_IMPLEMENTATION.md`
- `docs/SWING_V2_1_RESULTS.md`

## Preservation Of Existing Models

No changes were made to:

- V1 Swing scoring formula
- Swing V2 scoring formula
- Positional V2 scoring formula
- Existing recommendation model names
- Existing backtest methodology

The new model is stored and tested separately as:

```text
swing_v2_1
```

## Caveats

- This is a research model only.
- Survivorship-bias risk remains high.
- Transaction costs are still not modeled.
- True market-cap universe filtering is not implemented.
- Entry filters were selected from prior in-sample research.
- No forward out-of-sample validation has been performed.
