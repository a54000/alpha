# Phase 2B Warmup Validation

Generated on: 2026-06-12

## Objective

Validate warmup behavior for lookback-sensitive Swing V2.1 pilot features generated in `angel_data.pilot_phase2a.features_daily`.

This is a read-only validation. No features were regenerated, no tables were modified, no scores were generated, and no backtests were run.

## Source

```sql
SELECT COUNT(*), COUNT(DISTINCT symbol), MIN(date), MAX(date)
FROM pilot_phase2a.features_daily;
```

Observed:

- Rows: 344,597
- Symbols: 285
- Date range: 2021-06-14 to 2026-06-11

## Feature Warmup Rules

| Feature | Required history rule | Reason |
| --- | ---: | --- |
| `ema_50` | `history_days >= 50` | 50-row EWM maturity gate |
| `ema_200` | `history_days >= 200` | 200-row EWM maturity gate and Swing V2.1 overextension gate |
| `adx_14` | `history_days >= 28` | 14-period ADX with prior trend stabilization |
| `adx_prev` | `history_days >= 29` | ADX plus one prior row |
| `prior_20d_return` | `history_days > 20` | Requires current close and close from 20 trading rows earlier |
| `sector_rank_3m` | `history_days >= 64` for symbol-level scoring maturity | 63-trading-row sector lookback plus current row |

For Swing V2.1 scoring, the controlling warmup gate is `ema_200`, because it requires the longest lookback among direct scoring dependencies.

## First Valid Dates

The table below separates first non-null value availability from first mature availability.

| Feature | Earliest non-null date | Latest first non-null date across symbols | Earliest mature date | Latest first mature date across symbols |
| --- | --- | --- | --- | --- |
| `ema_50` | 2021-06-14 | 2022-10-13 | 2021-08-24 | 2022-12-26 |
| `ema_200` | 2021-06-14 | 2022-10-13 | 2022-04-01 | 2023-08-03 |
| `adx_14` | 2021-06-15 | 2022-10-14 | 2021-07-22 | 2022-11-24 |
| `adx_prev` | 2021-06-16 | 2022-10-17 | 2021-07-23 | 2022-11-25 |
| `prior_20d_return` | 2021-07-12 | 2022-11-15 | 2021-07-12 | 2022-11-15 |
| `sector_rank_3m` | 2021-06-14 | 2022-10-13 | 2021-09-14 | 2023-01-13 |

## Premature Availability Checks

Some production-style indicators produce numerical values before a conservative lookback gate is complete. These rows must be treated as warmup rows for pilot scoring.

| Check | Rows |
| --- | ---: |
| `ema_50 IS NOT NULL AND history_days < 50` | 13,960 |
| `ema_200 IS NOT NULL AND history_days < 200` | 56,527 |
| `adx_14 IS NOT NULL AND history_days < 28` | 7,321 |
| `adx_prev IS NOT NULL AND history_days < 29` | 7,321 |
| `prior_20d_return IS NOT NULL AND history_days <= 20` | 0 |
| `sector_rank_3m IS NOT NULL AND history_days < 64` | 17,936 |

Conclusion: `prior_20d_return` respects its lookback naturally. EMA, ADX, and sector ranks are numerically available before the recommended scoring maturity gates.

## Warmup Rows Requiring Exclusion

For Swing V2.1 pilot scoring, exclude rows where any direct scoring dependency is unavailable or immature:

```sql
WHERE history_days < 200
   OR NOT has_ema200_warmup
   OR NOT has_prior20_warmup
   OR NOT has_adx_warmup
   OR prior_20d_return IS NULL
   OR adx_14 IS NULL
   OR adx_prev IS NULL
```

Observed exclusion set:

- Rows requiring exclusion: 56,527
- Symbols affected: 285
- Warmup exclusion date range: 2021-06-14 to 2023-08-02

The exclusion count is governed by the EMA200 warmup gate.

## Pilot Scoring Start Date

Recommended pilot scoring start date: **2023-08-03**.

Rationale:

- It is the first date with at least 280 eligible symbols after all direct Swing V2.1 warmup gates.
- It is the latest first mature EMA200 date across symbols that eventually reach 200 rows.
- A full 285-symbol simultaneous eligible date does not occur because two pilot symbols never reach the 200-row gate.

Eligibility checkpoints:

| Date | Rows present | Eligible rows |
| --- | ---: | ---: |
| 2022-04-01 | 278 | 262 |
| 2023-08-03 | 280 | 280 |
| 2026-06-11 | 281 | 281 |

The first date with any eligible rows is 2022-04-01. That date is usable only for exploratory incremental scoring because it has 262 eligible symbols. For the main pilot, 2023-08-03 is safer and cleaner.

## Symbols That Never Reach Scoring Warmup

Two symbols never reach 200 rows and should be excluded from Swing V2.1 pilot scoring unless the pilot explicitly allows partial-history symbols:

| Symbol | Rows | First date | Last date | Max history days | Eligible rows |
| --- | ---: | --- | --- | ---: | ---: |
| WIPRO | 44 | 2021-12-13 | 2022-02-11 | 44 | 0 |
| TATASTEEL | 166 | 2021-06-14 | 2022-02-10 | 166 | 0 |

## Production Behavior Deviations

No formula deviation was found for the reviewed feature definitions, but the pilot validation highlights production-style warmup behavior that must be handled explicitly:

1. `ema_50` and `ema_200` are non-null from the first row because Pandas EWM starts immediately. This matches production feature behavior, but early EMA values are not mature.
2. `adx_14` and `adx_prev` become non-null before the conservative ADX warmup gate. This matches the Wilder-style EWM approach used in production, but early rows should be excluded from scoring.
3. `sector_rank_3m` is available from the first sector date because rank generation can rank null or immature sector returns. This mirrors the production sector rank pattern where early ranks can exist, but pilot scoring should require symbol-level maturity.
4. `prior_20d_return` behaves as expected and does not appear before 20 prior trading rows exist.

## Validation SQL

```sql
SELECT
    'ema_50_before_50_rows' AS check_name,
    COUNT(*)
FROM pilot_phase2a.features_daily
WHERE ema_50 IS NOT NULL AND history_days < 50
UNION ALL
SELECT 'ema_200_before_200_rows', COUNT(*)
FROM pilot_phase2a.features_daily
WHERE ema_200 IS NOT NULL AND history_days < 200
UNION ALL
SELECT 'adx_14_before_28_rows', COUNT(*)
FROM pilot_phase2a.features_daily
WHERE adx_14 IS NOT NULL AND history_days < 28
UNION ALL
SELECT 'adx_prev_before_29_rows', COUNT(*)
FROM pilot_phase2a.features_daily
WHERE adx_prev IS NOT NULL AND history_days < 29
UNION ALL
SELECT 'prior20_before_21_rows', COUNT(*)
FROM pilot_phase2a.features_daily
WHERE prior_20d_return IS NOT NULL AND history_days <= 20
UNION ALL
SELECT 'sector_rank_3m_before_64_rows', COUNT(*)
FROM pilot_phase2a.features_daily
WHERE sector_rank_3m IS NOT NULL AND history_days < 64;
```

```sql
SELECT
    COUNT(*) AS rows_requiring_exclusion,
    COUNT(DISTINCT symbol) AS symbols,
    MIN(date) AS first_date,
    MAX(date) AS last_date
FROM pilot_phase2a.features_daily
WHERE history_days < 200
   OR NOT has_ema200_warmup
   OR NOT has_prior20_warmup
   OR NOT has_adx_warmup
   OR prior_20d_return IS NULL
   OR adx_14 IS NULL
   OR adx_prev IS NULL;
```

```sql
WITH eligible AS (
    SELECT
        date,
        COUNT(*) AS n
    FROM pilot_phase2a.features_daily
    WHERE history_days >= 200
      AND prior_20d_return IS NOT NULL
      AND adx_14 IS NOT NULL
      AND adx_prev IS NOT NULL
      AND sector_rank_3m IS NOT NULL
    GROUP BY date
)
SELECT
    MIN(date) FILTER (WHERE n >= 1) AS first_any,
    MIN(date) FILTER (WHERE n >= 250) AS first_250,
    MIN(date) FILTER (WHERE n >= 280) AS first_280,
    MAX(n) AS max_eligible
FROM eligible;
```

Observed:

- First any eligible row date: 2022-04-01
- First 250-symbol eligible date: 2022-04-01
- First 280-symbol eligible date: 2023-08-03
- Maximum eligible symbols on one date: 282

## Recommendation

Use `2023-08-03` as the main Phase 2 pilot scoring start date.

For any later scoring script, enforce row-level eligibility:

```sql
history_days >= 200
AND prior_20d_return IS NOT NULL
AND adx_14 IS NOT NULL
AND adx_prev IS NOT NULL
AND sector_rank_3m IS NOT NULL
```

Also exclude `WIPRO` and `TATASTEEL` from the primary Swing V2.1 pilot because they never reach the EMA200 warmup gate in the cleaned pilot feature table.
