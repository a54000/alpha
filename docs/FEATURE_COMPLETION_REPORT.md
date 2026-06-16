# Feature Engine Completion Report

**Date:** 2026-06-10  
**Reference:** `docs/FEATURE_REGISTRY.yaml`, `docs/SCORING_VALIDATION.md`, `docs/RECOMMENDATION_ANOMALY_REPORT.md`  
**Modified:** `app/indicators/compute_features.py`

---

## Summary

Nine scoring-critical fields were missing from `FeatureComputer` output. All are now calculated, persisted, and covered by tests. No schema migrations were required — columns already existed in `features_daily`.

---

## Missing Fields Found

| Field | Swing | Positional | Was calculated | Was persisted | Root cause |
|-------|:-----:|:----------:|:--------------:|:-------------:|------------|
| `ema_5` | ✓ | | ✗ | ✗ | Not implemented in `_compute_symbol_features` |
| `ema_13` | ✓ | | ✗ | ✗ | Not implemented |
| `ema_150` | | ✓ | ✗ | ✗ | Not implemented |
| `adx_prev` | ✓ | ✓ | ✗ | ✗ | Not implemented (`adx_14` only) |
| `macd_hist_prev` | ✓ | | ✗ | ✗ | Not implemented (`macd_hist` only) |
| `stoch_k` | ✓ | | ✗ | ✗ | Not implemented |
| `stoch_d` | ✓ | | ✗ | ✗ | Not implemented |
| `bb_width_20avg` | ✓ | | ✗ | ✗ | Not implemented (`bb_width` only) |
| `rs_rank_pct` | ✓ | ✓ | ✗ | ✗ | No cross-sectional pass-2 |

---

## Fixes Applied

### Per-symbol calculations (`_compute_symbol_features`)

| Field | Implementation |
|-------|----------------|
| `ema_5`, `ema_13`, `ema_150` | `close.ewm(span=N).mean()` |
| `adx_prev` | `adx_14.shift(1)` |
| `macd_hist_prev` | `macd_hist.shift(1)` |
| `stoch_k`, `stoch_d` | `compute_stochastic()` — slow stochastic k=14, smooth_k=3, d=3 per `INDICATOR_SPEC.md` |
| `bb_width_20avg` | `bb_width.rolling(20).mean()` |
| `bb_upper`, `bb_mid`, `bb_lower`, `bb_pct` | Added alongside Bollinger band stack |
| `low_52w`, `pct_from_52w_low` | Added per registry |
| `volume_20avg` | `volume.rolling(20).mean()` |
| `sector` | Populated from `symbol_master.sector` |

### Cross-sectional pass-2 (`_apply_rs_rank_pct`)

After all symbols are processed for `[start_date, end_date]`:

1. For each trading date, load all `rs_vs_nifty_20d` values
2. Compute `PERCENTILE_RANK × 100` via `compute_rs_rank_pct()`
3. Update `features_daily.rs_rank_pct` per symbol/date

### Infrastructure improvements

| Change | Purpose |
|--------|---------|
| `WARMUP_DAYS = 300` lookback on price load | Correct EMA/ADX values on incremental runs |
| Persist only `date >= start_date` | Avoid rewriting warmup rows |
| SQLite `on_conflict_do_update` | Consistent upsert behavior in tests |
| `_sanitize_payload` column filter | Only persist valid `FeaturesDaily` columns |
| Exported `compute_stochastic()`, `compute_rs_rank_pct()` | Unit-testable pure functions |

---

## Scoring Input Coverage Matrix

Fields consumed by `ScoreComputer._feature_row_to_dict()`:

| Field | Swing | Positional | Source | Status |
|-------|:-----:|:----------:|--------|--------|
| `is_eligible` | ✓ | ✓ | `features_daily` | Populated |
| `close` | ✓ | ✓ | `prices_daily` join at scoring | Unchanged |
| `adx_14` | ✓ | ✓ | `features_daily` | Was populated |
| `adx_prev` | ✓ | ✓ | `features_daily` | **Fixed** |
| `ema_5` | ✓ | | `features_daily` | **Fixed** |
| `ema_13` | ✓ | | `features_daily` | **Fixed** |
| `ema_20` | ✓ | | `features_daily` | Was populated |
| `ema_50` | | ✓ | `features_daily` | Was populated |
| `ema_150` | | ✓ | `features_daily` | **Fixed** |
| `ema_200` | | ✓ | `features_daily` | Was populated |
| `rsi_14` | ✓ | | `features_daily` | Was populated |
| `macd_hist` | ✓ | | `features_daily` | Was populated |
| `macd_hist_prev` | ✓ | | `features_daily` | **Fixed** |
| `stoch_k` | ✓ | | `features_daily` | **Fixed** |
| `stoch_d` | ✓ | | `features_daily` | **Fixed** |
| `volume_ratio` | ✓ | ✓ | `features_daily` | Was populated |
| `pct_from_52w_high` | ✓ | | `features_daily` | Was populated |
| `bb_width` | ✓ | | `features_daily` | Was populated |
| `bb_width_20avg` | ✓ | | `features_daily` | **Fixed** |
| `rs_rank_pct` | ✓ | ✓ | `features_daily` | **Fixed** |
| `rs_vs_nifty_60d` | | ✓ | `features_daily` | Was populated |
| `sector_3m_rank` | | ✓ | `sector_daily.rank_3m` | Unchanged (sector engine) |

**Not modified:** scoring, recommendation thresholds, backtesting.

---

## Tests Added

| Test file | Test | Validates |
|-----------|------|-----------|
| `tests/test_feature_completion.py` | `test_compute_stochastic_returns_k_and_d` | Stochastic oscillator |
| `tests/test_feature_completion.py` | `test_compute_rs_rank_pct_orders_symbols` | Percentile rank ordering |
| `tests/test_feature_completion.py` | `test_feature_completion_populates_required_scoring_fields` | EMA, derivatives, stoch, BB avg |
| `tests/test_feature_completion.py` | `test_rs_rank_pct_generated_cross_sectionally` | Pass-2 rank across 3 symbols |
| `tests/test_feature_completion.py` | `test_feature_completion_empty_state_returns_zero_rows` | Empty-state handling |
| `tests/test_compute_features.py` | `test_compute_features_populates_features_daily` | Extended assertions for new fields |

**Result:** 9 feature tests pass; full suite passes.

---

## Schema Migrations

**None required.** All fields already exist in `db/models.py` and Alembic migrations `001`–`006`.

---

## Production Backfill Required

Existing `features_daily` rows were computed without the new fields. Incremental mode skips dates already present. To backfill:

```bash
# Option A: truncate and regenerate
psql ... -c "TRUNCATE features_daily;"

# Option B: explicit full-range regenerate
PYTHONPATH=. python -c "
from datetime import date
from db.session import build_session_factory
from app.indicators.compute_features import FeatureComputer
from sqlalchemy import text

sf = build_session_factory()
with sf() as s:
    start = s.execute(text('SELECT MIN(date) FROM prices_daily')).scalar()
    end = s.execute(text('SELECT MAX(date) FROM prices_daily')).scalar()
FeatureComputer(sf).generate(start_date=start, end_date=end)
"

# Then re-run downstream:
# sector_daily → daily_scores → recommendation_history
```

---

## Known Limitations (Out of Scope)

| Item | Notes |
|------|-------|
| `rs_vs_nifty_20d` / `rs_vs_nifty_60d` | Still `close.pct_change(N)`, not `stock_return / nifty_return`. Cross-sectional rank remains valid; absolute RS vs Nifty ratio not yet implemented. |
| `rs_vs_sector_20d` | Not in missing-field list; still uncomputed |
| `rsi_9` | Registered but not consumed by swing/positional scoring |

---

## Document History

| Date | Change |
|------|--------|
| 2026-06-10 | Feature engine completion — 9 missing fields implemented |
