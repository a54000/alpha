# Phase 6 Backtesting Readiness Report

**Date:** 2026-06-10  
**Auditor scope:** Read-only review of database, pipeline, scoring, recommendations, backtest dependencies, and tests.  
**Reference documents:** `docs/BACKTEST_SPEC.md`, `docs/SCORING_VALIDATION.md`, `docs/SCORING_READINESS_REPORT.md`, `docs/LOCAL_DEVELOPMENT.md`

---

## Verdict

# BLOCKED

Phase 6 backtesting **code exists** (`app/backtesting/run_backtest.py`, `tests/test_backtesting.py`) and unit tests pass, but the **runtime PostgreSQL environment is not ready** to execute a meaningful backtest. The database is schema-only at an outdated migration revision with zero populated pipeline data.

---

## Validation Checklist

| # | Item | Result | Notes |
|---|------|--------|-------|
| **DATABASE** | | | |
| 1 | PostgreSQL is the runtime database | **PASS** | `db/connection.py` requires `DATABASE_URL`; `.env.example` and `docs/LOCAL_DEVELOPMENT.md` document PostgreSQL. Tests use in-memory SQLite only. |
| 2 | `DATABASE_URL` is required and documented | **PASS** | `get_database_url()` raises if unset. Documented in `.env.example` and `docs/LOCAL_DEVELOPMENT.md`. |
| 3 | Alembic head revision matches latest migration | **FAIL** | `alembic heads` → `006 (head)`. Live PostgreSQL `alembic current` → `005`. |
| 4 | `recommendation_history` contains `model_version_id` | **FAIL** | Column declared in `db/models.py` and migration `006`, but **not present** in live PostgreSQL (`\d recommendation_history` on `nse_research_platform`). |
| 5 | All required tables exist | **PASS** | 13 application tables present in `db/models.py`, migrations, and PostgreSQL. |
| **DATA PIPELINE** | | | |
| 6 | Dependency chain complete | **FAIL** | Code path exists (`symbol_master` → `prices_daily` → `features_daily` → `sector_daily` → `daily_scores` → `recommendation_history`), but **all tables are empty** in PostgreSQL. |
| 7 | No missing foreign keys | **PASS** | Core FK graph implemented. See non-critical gap on `model_version_id` FK below. |
| 8 | No schema mismatches (models vs migrations) | **PARTIAL** | Models and migrations `001`–`005` align. Migration `006` adds `model_version_id` as bare `Integer` without FK; model declares `ForeignKey("model_version.version_id")`. |
| **BACKTEST DEPENDENCIES** | | | |
| 9 | `recommendation_history` has backtest-required fields | **PASS** | `date`, `model`, `rank`, `symbol`, `score` sufficient for Phase 6 forward-return engine. `model_version_id` present in model; not yet in live DB. Enrichment columns (`entry_price`, `rsi_14`, etc.) exist but are **not populated** by `RecommendationGenerator`. |
| 10 | `prices_daily` has sufficient history for all horizons | **FAIL** | `prices_daily` row count = **0**. Horizons require up to **126 trading days** forward (6m positional). |
| 11 | Recommendation dates joinable to future prices | **PASS** (code) / **FAIL** (data) | `forward_trading_day_return()` in `app/backtesting/run_backtest.py` joins via trading-day offsets; covered by `tests/test_backtesting.py`. No production data to join. |
| 12 | No survivorship-bias issues in current design | **PARTIAL** | `universe_snapshot` table and `symbol_loader.py` exist. Scoring and recommendations **do not filter** by `universe_snapshot` membership on signal date. Risk documented in `BACKTEST_SPEC.md` and `V1_SCOPE.md`. |
| 13 | Missing future-price handling defined | **PASS** | Returns `None` when exit index exceeds available dates; excluded from aggregate metrics. Tested in `test_forward_return_missing_future_prices_returns_none`. |
| **SCORING** | | | |
| 14 | Swing score matches `SCORING_VALIDATION.md` | **PASS** | All 10 worked examples parametrized in `tests/test_scoring_engine.py`. Implementation in `app/scoring/compute_scores.py`. |
| 15 | Position score matches `SCORING_VALIDATION.md` | **PASS** | All 10 worked examples parametrized. Sector rank via `sector_daily.rank_3m`. |
| 16 | Long-term score excluded and documented as blocked | **PASS** | `ScoreComputer` does not compute `lt_score` (remains `NULL`). Documented in module docstring, `SCORING_READINESS_REPORT.md`, and `tests/test_scoring_engine.py`. |
| **RECOMMENDATIONS** | | | |
| 17 | Top-20 logic implemented | **PASS** | `rank_recommendations(..., top_n=20)`; tested in `test_rank_recommendations_caps_at_top_n` and `test_positional_minimum_score_and_top_20_cap`. |
| 18 | Minimum score filters implemented | **PASS** | Swing ≥ 70, Positional ≥ 65 (`SWING_RECOMMENDATION_CONFIG`, `POSITIONAL_RECOMMENDATION_CONFIG`). Tested. |
| 19 | Idempotency verified | **PASS** | `test_generate_is_idempotent` confirms second run writes 0 rows. |
| 20 | Model version tracking present | **PASS** (code) / **FAIL** (DB) | `daily_scores.model_version_id` and `recommendation_history.model_version_id` written by generators. Live DB missing column until migration `006` applied. |

---

## Blockers

### Critical

| # | Blocker | Evidence | Resolution |
|---|---------|----------|------------|
| C1 | **Alembic migration `006` not applied** | `alembic heads` = `006`; `alembic current` on `nse_research_platform` = `005` | Run `alembic upgrade head` against PostgreSQL with `DATABASE_URL` set. |
| C2 | **`recommendation_history.model_version_id` absent in live database** | `\d recommendation_history` shows no `model_version_id` column | Apply migration `006`. |
| C3 | **Production database is empty** | All pipeline tables report `count = 0` (`symbol_master`, `prices_daily`, `features_daily`, `sector_daily`, `daily_scores`, `recommendation_history`) | Execute ingestion → features → sectors → scoring → recommendations pipeline on PostgreSQL. |
| C4 | **No historical price data for backtest horizons** | `prices_daily` = 0 rows; positional 6m horizon needs 126+ trading days beyond each signal | Ingest ≥ 2 years OHLCV for NSE500 symbols plus benchmark `^CRSLDX` per `configs/config.yaml`. |
| C5 | **No recommendations to backtest** | `recommendation_history` = 0 rows | Run `RecommendationGenerator` after upstream pipeline populates `daily_scores`. |

### Non-Critical

| # | Blocker | Evidence | Impact |
|---|---------|----------|--------|
| N1 | **Migration `006` omits FK on `model_version_id`** | `alembic/versions/006_add_recommendation_model_version.py` adds `Integer` only; `db/models.py` declares `ForeignKey` | Referential integrity not enforced at DB level for recommendations. |
| N2 | **Survivorship bias not enforced in ranking pipeline** | `universe_snapshot` populated by `symbol_loader.py` but not consumed by scoring or recommendations | Backtest may include symbols not in historical NSE500 membership. |
| N3 | **`BACKTEST_SPEC.md` vs Phase 6 implementation divergence** | Spec: `next_day_open` entry, portfolio simulation, stop-loss exits. Implemented engine: recommendation-date **close** entry, fixed-horizon forward returns | Acceptable for Phase 6 scope; full spec simulation not yet built. |
| N4 | **Recommendation enrichment fields not populated** | `RecommendationGenerator._persist_recommendations` writes `date`, `model`, `rank`, `symbol`, `score`, `model_version_id` only | `entry_price`, `rsi_14`, `adx_14`, etc. remain `NULL`; backtest derives entry from `prices_daily`. |
| N5 | **NIFTY benchmark availability unverified in production** | Benchmark symbol `^CRSLDX` configured; no rows in `prices_daily` | Benchmark comparison will be skipped until benchmark prices are ingested. |
| N6 | **Stale validation reports** | `SCHEMA_VALIDATION_REPORT.md` references revision `005` era and 10 tests; suite now has 66 tests | Documentation drift only. |
| N7 | **TimescaleDB hypertables not created** | Extension unavailable locally; migration `003` is fail-soft | Performance risk at scale, not a functional blocker for Phase 6. |

---

## What Is Ready

| Area | Status |
|------|--------|
| PostgreSQL runtime configuration | Configured (`DATABASE_URL`, `python-dotenv`, docs) |
| Schema (models + migrations `001`–`006`) | Defined; `006` pending apply |
| Swing / Positional scoring | Implemented; 20/20 validation examples pass |
| Long-term scoring | Correctly excluded (`lt_score` = `NULL`) |
| Recommendation engine | Top-20, min-score filters, idempotency, model version in code |
| Sector strength engine | Equal-weight returns; persists `sector_daily` |
| Feature pipeline | `compute_features.py` reads `prices_daily`, writes `features_daily` |
| Phase 6 backtest engine | `app/backtesting/run_backtest.py` — swing 5d/10d/20d, positional 1m/3m/6m, aggregates, benchmark alpha, `backtest_runs` persistence |
| Unit / integration tests | **66 passed** (includes backtesting, scoring, recommendations, migrations) |

---

## Live PostgreSQL Snapshot

```
Database:     nse_research_platform
Alembic:      005 (head available: 006)
symbol_master:          0 rows
prices_daily:           0 rows
features_daily:         0 rows
sector_daily:           0 rows
daily_scores:           0 rows
recommendation_history: 0 rows
backtest_runs:          0 rows
universe_snapshot:      0 rows
```

---

## Recommended Remediation Sequence

Execute in order before running Phase 6 backtests against PostgreSQL:

```bash
# 1. Apply pending migration
cp .env.example .env   # if not done
alembic upgrade head
alembic current        # expect 006

# 2. Populate pipeline (example — wire to your orchestration)
# symbol_loader → price_loader → compute_features → compute_sector_strength
# → ScoreComputer → RecommendationGenerator

# 3. Verify data minimums
# - prices_daily: ≥ 252 trading days per symbol + ^CRSLDX benchmark
# - recommendation_history: > 0 rows for swing and/or positional
# - daily_scores: populated for same date range

# 4. Run backtest
python -c "
from db.session import build_session_factory
from app.backtesting.run_backtest import BacktestRunner, write_backtest_report

runner = BacktestRunner(build_session_factory())
report = runner.run('swing')
write_backtest_report(report, 'reports/swing_backtest.json')
print(report)
"
```

---

## Exact Next Prompt (after blockers cleared)

```
Run the full data pipeline on PostgreSQL (symbol_master → prices_daily →
features_daily → sector_daily → daily_scores → recommendation_history),
then execute BacktestRunner for swing and positional models over the
populated date range. Write reports to reports/ and validate backtest_runs
rows against tests/test_backtesting.py expectations. Confirm benchmark
alpha using ^CRSLDX prices.
```

---

## Document History

| Date | Change |
|------|--------|
| 2026-06-10 | Initial Phase 6 readiness audit |
