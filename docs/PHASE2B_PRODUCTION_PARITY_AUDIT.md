# Phase 2B Production Parity Audit

Generated on: 2026-06-12

## Objective

Determine whether the Phase 2B pilot warmup rules exactly match production Swing V2.1 scoring behavior.

Sources:

- `app/scoring/compute_scores.py`
- `angel_data.pilot_phase2a.features_daily`
- `docs/PHASE2B_WARMUP_VALIDATION.md`

This audit was read-only. No scores were generated, no features were rebuilt, no tables were modified, and no backtests were run.

## Production Swing V2.1 Eligibility

Production Swing V2.1 scoring is implemented in `compute_swing_v2_1_score`.

The function returns `None` only when:

1. `is_eligible` is explicitly false.
2. `close` is null.
3. `ema_200` is null.
4. `ema_200` is zero.
5. `prior_20d_return` is null.
6. `(close - ema_200) / ema_200 > 0.25`.
7. `prior_20d_return > 0.15`.

If those checks pass, production computes:

```text
(ADX component + sector component) / 35 * 100
```

## Production Requirements By Feature

| Feature | Production requirement | Blocks Swing V2.1 score? | Notes |
| --- | --- | --- | --- |
| `ema_200` | Must be non-null and non-zero | Yes | No explicit 200-row maturity check |
| `adx_14` | Passed into ADX scoring | No | Null ADX scores 0 points |
| `adx_prev` | Passed into ADX scoring | No | Null previous ADX reduces rising-trend bonus but does not block scoring |
| `prior_20d_return` | Must be non-null and `<= 0.15` | Yes | Loaded in production from `prices_daily`, not stored `features_daily` |
| `sector_rank_3m` | Passed into sector scoring | No | Null sector rank scores 0 points |

## Explicit Warmup Gating In Production

Production does **not** explicitly require:

- 200 rows before using `ema_200`
- 28 rows before using `adx_14`
- 29 rows before using `adx_prev`
- 64 rows before using sector rank
- a general `history_days` gate

Production does require non-null `prior_20d_return`, which naturally imposes a 20-row lookback requirement.

Production feature generation uses Pandas EWM behavior for EMA and ADX, so early EMA/ADX values can exist before conservative maturity windows are complete.

## Pilot Warmup Rules

`PHASE2B_WARMUP_VALIDATION.md` recommended stricter pilot gates:

```sql
history_days >= 200
AND prior_20d_return IS NOT NULL
AND adx_14 IS NOT NULL
AND adx_prev IS NOT NULL
AND sector_rank_3m IS NOT NULL
```

This rule is more conservative than production.

The strict rule was designed for research hygiene, not production parity.

## Production vs Pilot Eligibility Difference

Production-parity eligibility on the pilot feature table:

```sql
close IS NOT NULL
AND ema_200 IS NOT NULL
AND ema_200 <> 0
AND prior_20d_return IS NOT NULL
AND ((close - ema_200) / ema_200) <= 0.25
AND prior_20d_return <= 0.15
```

Strict pilot eligibility:

```sql
history_days >= 200
AND prior_20d_return IS NOT NULL
AND adx_14 IS NOT NULL
AND adx_prev IS NOT NULL
AND sector_rank_3m IS NOT NULL
AND close IS NOT NULL
AND ema_200 IS NOT NULL
AND ema_200 <> 0
AND ((close - ema_200) / ema_200) <= 0.25
AND prior_20d_return <= 0.15
```

Observed counts:

| Rule | Eligible rows | Symbols | First date | Last date |
| --- | ---: | ---: | --- | --- |
| Production actual | 288,681 | 285 | 2021-07-12 | 2026-06-11 |
| Strict pilot | 243,645 | 283 | 2022-04-01 | 2026-06-11 |

Difference:

- Production accepts **45,036** rows before the 200-row history gate.
- Those rows would be excluded by strict pilot warmup rules.
- Production does not require ADX or sector rank to be non-null; however, in the current pilot table, production-eligible rows did not have null ADX or null sector rank.

Observed production-eligible rows with potential warmup deviations:

| Metric | Rows |
| --- | ---: |
| Production-eligible rows with `history_days < 200` | 45,036 |
| Production-eligible rows with null `adx_14` or `adx_prev` | 0 |
| Production-eligible rows with null `sector_rank_3m` | 0 |

## Earliest Valid Scoring Dates

The table below treats "valid" as "production function would return a non-null Swing V2.1 score".

| Threshold | Production actual | Strict pilot |
| --- | --- | --- |
| First any eligible symbol | 2021-07-12 | 2022-04-01 |
| First 250 eligible symbols | 2021-07-12 | 2022-05-04 |
| First 275 eligible symbols | 2022-05-25 | 2025-01-13 |
| First 280 eligible symbols | 2025-02-14 | 2025-02-14 |

Checkpoint dates:

| Date | Rows present | Production-eligible rows | Strict-pilot eligible rows |
| --- | ---: | ---: | ---: |
| 2021-07-12 | 278 | 253 | 0 |
| 2022-04-01 | 278 | 244 | 230 |
| 2023-08-03 | 280 | 226 | 226 |
| 2026-06-11 | 281 | 264 | 264 |

The 2023-08-03 date from `PHASE2B_WARMUP_VALIDATION.md` remains a good conservative warmup start date, but it is not exact production parity.

## Recommended Scoring Start Date Under True Production Parity

For exact production parity, use **2021-07-12**.

Reason:

- It is the first date where production Swing V2.1 would return non-null scores for pilot rows.
- It has 253 production-eligible symbols.
- It honors the true production checks: non-null `ema_200`, non-null `prior_20d_return`, and the two Swing V2.1 overextension filters.

For a broad-universe production-parity pilot, use **2022-05-25** if a 275-symbol threshold is acceptable, or **2025-02-14** if a 280-symbol threshold is required after overextension filters.

For conservative research hygiene rather than parity, use **2023-08-03** with the explicit 200-row warmup gate.

## Parity Conclusion

The Phase 2B warmup rules do **not** exactly match production behavior.

Main deviations:

1. Pilot warmup validation requires `history_days >= 200`; production does not.
2. Pilot warmup validation treats ADX and sector rank maturity as scoring prerequisites; production does not.
3. Production blocks Swing V2.1 scores using overextension filters, which the warmup-only validation did not include in its broad-universe date recommendation.
4. Production `prior_20d_return` is computed from `prices_daily` at scoring time. The pilot stores an equivalent per-symbol 20-row return in `features_daily`; this is acceptable for the pilot as long as the scoring phase documents that substitution.

## Validation SQL

```sql
WITH prod AS (
    SELECT
        date,
        COUNT(*) AS eligible_rows
    FROM pilot_phase2a.features_daily
    WHERE close IS NOT NULL
      AND ema_200 IS NOT NULL
      AND ema_200 <> 0
      AND prior_20d_return IS NOT NULL
      AND ((close - ema_200) / ema_200) <= 0.25
      AND prior_20d_return <= 0.15
    GROUP BY date
),
strict AS (
    SELECT
        date,
        COUNT(*) AS eligible_rows
    FROM pilot_phase2a.features_daily
    WHERE history_days >= 200
      AND prior_20d_return IS NOT NULL
      AND adx_14 IS NOT NULL
      AND adx_prev IS NOT NULL
      AND sector_rank_3m IS NOT NULL
      AND close IS NOT NULL
      AND ema_200 IS NOT NULL
      AND ema_200 <> 0
      AND ((close - ema_200) / ema_200) <= 0.25
      AND prior_20d_return <= 0.15
    GROUP BY date
)
SELECT
    'production_actual' AS rule,
    MIN(date) FILTER (WHERE eligible_rows >= 1) AS first_any,
    MIN(date) FILTER (WHERE eligible_rows >= 250) AS first_250,
    MIN(date) FILTER (WHERE eligible_rows >= 275) AS first_275,
    MIN(date) FILTER (WHERE eligible_rows >= 280) AS first_280,
    MAX(eligible_rows) AS max_eligible
FROM prod
UNION ALL
SELECT
    'strict_pilot',
    MIN(date) FILTER (WHERE eligible_rows >= 1),
    MIN(date) FILTER (WHERE eligible_rows >= 250),
    MIN(date) FILTER (WHERE eligible_rows >= 275),
    MIN(date) FILTER (WHERE eligible_rows >= 280),
    MAX(eligible_rows)
FROM strict;
```

## Final Recommendation

Use two named modes in the next scoring phase:

1. **Production parity mode**
   - Start date: `2021-07-12`
   - Eligibility: match `compute_swing_v2_1_score` exactly.
   - Purpose: apples-to-apples comparison with current production behavior.

2. **Strict research mode**
   - Start date: `2023-08-03`
   - Eligibility: require `history_days >= 200` plus non-null direct dependencies.
   - Purpose: cleaner five-year research interpretation with mature long-lookback indicators.

For the user's requested production parity audit, the recommended scoring start date is **2021-07-12**.
