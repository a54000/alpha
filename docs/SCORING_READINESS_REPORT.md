# Scoring Readiness Report

**Reviewed:** `docs/SCORING_VALIDATION.md`  
**Compared against:** `db/models.py`, `features_daily` schema (`migrations/001_initial_schema.sql` + amendments), `sector_daily` schema  
**Date:** 2026-06-10

**Scope note:** `docs/RECOMMENDATION_ENGINE_SPEC.md` is not present. This report validates data availability only — not scoring code, pipeline completeness, or feature correctness.

**Legend**

| Column | Meaning |
|--------|---------|
| **Available** | Column exists in the cited source table (or exact alias documented) |
| **Derivable** | Can be computed at scoring time from data in implemented schema tables, even if not stored as a dedicated column |

---

## Summary

| Model | Fields required | Schema-ready | Blocked |
|-------|-----------------|--------------|---------|
| Swing | 18 | 17 | 0 (1 join field) |
| Positional | 11 | 10 | 1 (sector join dependency) |
| Long-term | 11 | 4 | 7 |
| Global / eligibility | 3 | 2 | 1 |

---

## Global & Eligibility Fields

| Field | Source table | Available | Derivable | Used by |
|-------|--------------|-----------|-----------|---------|
| `is_eligible` | `features_daily` | YES | YES | All models (pre-filter) |
| `close` | `prices_daily` | YES | YES | Swing, Positional, LT (EMA / price comparisons) |
| `history_days` | — | NO | YES | Eligibility (`prices_daily` row count per symbol) |
| `sector` | `symbol_master` / `features_daily` | YES | YES | Positional (`sector_daily` join) |
| `announced_date` | `fundamentals` | NO | NO | LT (5-day lag rule) |

`close` is not stored in `features_daily`; scoring must join `prices_daily` on `(symbol, date)` or pass `close` into the scoring layer at runtime.

---

## Swing Model Fields

| Field | Source table | Available | Derivable | Notes |
|-------|--------------|-----------|-----------|-------|
| `adx_14` | `features_daily` | YES | YES | |
| `adx_prev` | `features_daily` | YES | YES | Column exists; shift of `adx_14` |
| `ema_5` | `features_daily` | YES | YES | Column exists; computable from `prices_daily.close` |
| `ema_13` | `features_daily` | YES | YES | Column exists; computable from `prices_daily.close` |
| `ema_20` | `features_daily` | YES | YES | |
| `close` | `prices_daily` | YES | YES | Required for EMA alignment rules |
| `rsi_14` | `features_daily` | YES | YES | |
| `macd_hist` | `features_daily` | YES | YES | |
| `macd_hist_prev` | `features_daily` | YES | YES | Column exists; shift of `macd_hist` |
| `stoch_k` | `features_daily` | YES | YES | Column exists; computable from OHLC |
| `stoch_d` | `features_daily` | YES | YES | Column exists; computable from OHLC |
| `volume_ratio` | `features_daily` | YES | YES | |
| `pct_from_52w_high` | `features_daily` | YES | YES | |
| `bb_width` | `features_daily` | YES | YES | |
| `bb_width_20avg` | `features_daily` | YES | YES | Column exists; 20-day mean of `bb_width` |
| `rs_rank_pct` | `features_daily` | YES | YES | Cross-sectional; requires full NSE500 pass-2 rank |

**Swing schema status:** All required fields are present in schema or derivable from `prices_daily` / `features_daily`.

---

## Positional Model Fields

| Field | Source table | Available | Derivable | Notes |
|-------|--------------|-----------|-----------|-------|
| `close` | `prices_daily` | YES | YES | EMA Stage 2 alignment |
| `ema_50` | `features_daily` | YES | YES | |
| `ema_150` | `features_daily` | YES | YES | Column exists; computable from `prices_daily.close` |
| `ema_200` | `features_daily` | YES | YES | |
| `adx_14` | `features_daily` | YES | YES | |
| `adx_prev` | `features_daily` | YES | YES | |
| `rs_rank_pct` | `features_daily` | YES | YES | Cross-sectional pass-2 |
| `rs_vs_nifty_60d` | `features_daily` | YES | YES | Column exists |
| `volume_ratio` | `features_daily` | YES | YES | |
| `sector_3m_rank` | `sector_daily.rank_3m` | YES | YES | Join `symbol_master.sector` + `date` |

**Positional schema status:** All required fields are present. `sector_3m_rank` is stored as `rank_3m` in `sector_daily` (name alias only).

---

## Long-Term Model Fields

| Field | Source table | Available | Derivable | Notes |
|-------|--------------|-----------|-----------|-------|
| `revenue_cagr_3y` | `fundamentals` | NO | NO | Table not in `db/models.py` or migrations |
| `pat_cagr_3y` | `fundamentals` | NO | NO | Requires 3Y PAT history + CAGR computation |
| `roe` | `fundamentals` | NO | NO | Documented in `DB_SCHEMA.md` only |
| `roce` | `fundamentals` | NO | NO | Documented in `DB_SCHEMA.md` only |
| `debt_equity` | `fundamentals` | NO | NO | Documented in `DB_SCHEMA.md` only |
| `pe_ratio` | `fundamentals` | NO | NO | Documented in `DB_SCHEMA.md` only |
| `sector_median_pe` | — | NO | NO | Requires `fundamentals.pe_ratio` + `symbol_master.sector` aggregation |
| `pe_relative` | — | NO | NO | `pe_ratio / sector_median_pe`; both parents missing |
| `close` | `prices_daily` | YES | YES | |
| `ema_200` | `features_daily` | YES | YES | |
| `pct_from_52w_high` | `features_daily` | YES | YES | |
| `rs_vs_nifty_60d` | `features_daily` | YES | YES | |

**Long-term schema status:** Price-trend inputs are ready. All fundamental inputs are blocked — `fundamentals` table is not implemented.

---

## `sector_daily` Readiness (Positional)

| Field (scoring name) | `sector_daily` column | Available | Derivable |
|----------------------|----------------------|-----------|-----------|
| `sector_3m_rank` | `rank_3m` | YES | YES |
| `sector_return_3m` | `sector_return_3m` / `return_3m` | YES | YES | Not consumed directly by positional scoring rules |
| `rank_composite` | `rank_composite` | YES | YES | Not consumed by positional scoring rules |

Positional scoring reads `rank_3m` only (aliased as `sector_3m_rank` in validation doc).

---

## `features_daily` Column Coverage

All swing and positional technical fields from `SCORING_VALIDATION.md` have matching columns in `FeaturesDaily` (`db/models.py` lines 47–91), except `close` which lives in `prices_daily`.

Columns in schema **not** referenced by `SCORING_VALIDATION.md` (no scoring dependency):  
`rsi_9`, `macd_line`, `macd_signal`, `atr_14`, `bb_upper`, `bb_mid`, `bb_lower`, `bb_pct`, `volume_20avg`, `high_52w`, `low_52w`, `distance_from_52w_high`, `pct_from_52w_low`, `is_52w_breakout`, `rs_vs_nifty_20d`, `rs_vs_sector_20d`, `avg_traded_value`.

---

## Missing Dependencies

### Blocking (schema)

| # | Dependency | Impact | Resolution |
|---|------------|--------|------------|
| 1 | **`fundamentals` table** | LT model cannot run; 7 fields unavailable | Add table to `db/models.py` + migration per `DB_SCHEMA.md` |
| 2 | **`revenue_cagr_3y`** | LT growth component (20 pts) | Compute from `fundamentals.revenue_cr` history |
| 3 | **`pat_cagr_3y`** | LT growth component (20 pts) | Compute from `fundamentals.pat_cr` history |
| 4 | **`roe`** | LT quality component (12 pts) | Ingest into `fundamentals` |
| 5 | **`roce`** | LT quality component (12 pts) | Ingest into `fundamentals` |
| 6 | **`debt_equity`** | LT quality component (6 pts) | Ingest into `fundamentals` |
| 7 | **`pe_ratio`** | LT valuation component (15 pts) | Ingest into `fundamentals` |
| 8 | **`sector_median_pe`** | LT valuation (`pe_relative`) | Cross-sectional aggregate from `fundamentals` + `symbol_master` |
| 9 | **`announced_date`** | LT 5-day lag rule | Column on `fundamentals` (documented, not implemented) |

### Non-blocking (runtime / pipeline)

These fields exist in schema but require joins or batch computation before scoring:

| Dependency | Impact | Resolution |
|------------|--------|------------|
| `close` join from `prices_daily` | Swing / Positional / LT price comparisons | Join at scoring read time |
| `rs_rank_pct` cross-sectional rank | Swing (10 pts) + Positional (18 pts) | Pass-2 rank across all NSE500 on date |
| `sector_daily` population | Positional sector component (20 pts) | Run sector strength engine before scoring |
| `symbol_master.sector` → `sector_daily` join | Positional sector lookup | Join on `(sector, date)` |
| `is_eligible` population | Pre-filter all models | Feature pipeline eligibility logic |
| Several `features_daily` columns not yet written by `compute_features.py` | Empty columns at runtime (`ema_5`, `ema_13`, `ema_150`, `adx_prev`, `macd_hist_prev`, `stoch_k`, `stoch_d`, `bb_width_20avg`, `rs_rank_pct`, `sector`) | Extend feature pipeline or compute at scoring time from `prices_daily` |

---

## Model Readiness

| Model | Verdict | Reason |
|-------|---------|--------|
| Swing | Schema ready | All inputs in `features_daily` / `prices_daily` |
| Positional | Schema ready | All inputs in `features_daily` / `prices_daily` / `sector_daily` |
| Long-term | **Not ready** | `fundamentals` table and 7 derived fields missing |

---

## Recommendation

**MISSING_DEPENDENCIES**

Swing and Positional models have full schema coverage for all inputs defined in `SCORING_VALIDATION.md`. The Long-Term model is blocked: the `fundamentals` table exists only in `docs/DB_SCHEMA.md` and is absent from `db/models.py` and all migrations. Until `fundamentals` is implemented and CAGR / sector-median-PE features are derivable, only Swing and Positional scoring can proceed.

**Minimum path to `READY_FOR_SCORING` (all three models):**

1. Implement `fundamentals` table (`db/models.py` + migration) with `announced_date`, `revenue_cr`, `pat_cr`, `roe`, `roce`, `debt_equity`, `pe_ratio`
2. Add derivation layer for `revenue_cagr_3y`, `pat_cagr_3y`, `sector_median_pe`, `pe_relative`
3. Ensure `sector_daily.rank_3m` is populated before positional scoring runs
4. Ensure `rs_rank_pct` pass-2 computation runs before swing/positional scoring
5. Join `prices_daily.close` at scoring read time (or denormalize into scoring input)

---

## Document history

| Date | Change |
|------|--------|
| 2026-06-10 | Initial readiness audit vs `SCORING_VALIDATION.md` |
