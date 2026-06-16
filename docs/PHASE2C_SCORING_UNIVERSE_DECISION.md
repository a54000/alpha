# Phase 2C Scoring Universe Decision

Generated on: 2026-06-12

## Objective

Choose the official scoring start date for the first Swing V2.1 long-history validation.

Inputs:

- `docs/PHASE2B_WARMUP_VALIDATION.md`
- `docs/PHASE2B_PRODUCTION_PARITY_AUDIT.md`
- `angel_data.pilot_phase2a.features_daily`

This decision analysis was read-only. No scores were generated, no backtests were run, and no tables were modified.

## Eligibility Definitions

### Production-Parity Eligibility

Production Swing V2.1 returns a non-null score when:

```sql
close IS NOT NULL
AND ema_200 IS NOT NULL
AND ema_200 <> 0
AND prior_20d_return IS NOT NULL
AND ((close - ema_200) / ema_200) <= 0.25
AND prior_20d_return <= 0.15
```

Production does not explicitly require 200 rows of EMA history. ADX and sector rank can be null and score zero.

### Strict Research Eligibility

The stricter Phase 2B warmup rule adds mature-lookback requirements:

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

## Source Coverage

`pilot_phase2a.features_daily` contains:

- Dates: 2021-06-14 to 2026-06-11
- Trading dates: 1,232
- Symbols: 285
- Rows present per date: 275 to 282

## Candidate Start Dates

| Candidate | Date | Production-eligible symbols on date | Strict-eligible symbols on date | Meaning |
| --- | --- | ---: | ---: | --- |
| Production parity start | 2021-07-12 | 253 | 0 | First date production Swing V2.1 can score pilot rows |
| 275+ production start | 2022-05-25 | 275 | 271 | First date with at least 275 production-eligible symbols |
| Strict warmup start | 2023-08-03 | 226 | 226 | Conservative EMA200 warmup date from Phase 2B validation |
| Latest checkpoint | 2026-06-11 | 264 | 264 | Current end of pilot feature table |

## Threshold Dates

| Threshold | Production-parity date | Strict-research date |
| --- | --- | --- |
| First any eligible symbol | 2021-07-12 | 2022-04-01 |
| First 250 eligible symbols | 2021-07-12 | 2022-05-04 |
| First 275 eligible symbols | 2022-05-25 | 2025-01-13 |
| First 280 eligible symbols | 2025-02-14 | 2025-02-14 |

The 280-symbol threshold is too late for a first long-history validation because it would discard most of the historical expansion.

## Coverage By Year

| Year | Trading days | Avg production eligible | Min production eligible | Max production eligible | Avg strict eligible | Min strict eligible | Max strict eligible |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2021 | 138 | 206.98 | 0 | 265 | 0.00 | 0 | 0 |
| 2022 | 247 | 246.35 | 173 | 275 | 180.83 | 0 | 271 |
| 2023 | 245 | 231.42 | 166 | 273 | 230.25 | 166 | 270 |
| 2024 | 246 | 205.70 | 134 | 269 | 205.70 | 134 | 269 |
| 2025 | 248 | 260.73 | 192 | 280 | 260.73 | 192 | 280 |
| 2026 | 108 | 252.84 | 158 | 279 | 252.84 | 158 | 279 |

Coverage is not monotonic because Swing V2.1 excludes overextended names using `ema200_extension > 0.25` and `prior_20d_return > 0.15`.

## Coverage By Period

| Period | Trading days | Avg production eligible | Min production eligible | Max production eligible | Avg strict eligible | Min strict eligible | Max strict eligible |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Before production start | 20 | 0.00 | 0 | 0 | 0.00 | 0 | 0 |
| 2021-07-12 to 2022-05-24 | 214 | 246.48 | 173 | 274 | 39.44 | 0 | 269 |
| 2022-05-25 to 2023-08-02 | 296 | 245.36 | 182 | 275 | 242.90 | 179 | 271 |
| 2023-08-03 forward | 702 | 232.63 | 134 | 280 | 232.63 | 134 | 280 |

After 2023-08-03, production-parity and strict-research eligibility converge for the current pilot table because all remaining scoreable rows have already passed the 200-row gate.

## Monthly Coverage Evolution

The monthly averages show four regimes:

1. **June 2021:** no production-eligible rows because the 20-day prior return is unavailable.
2. **July 2021 to March 2022:** production can score many names, but strict warmup is still unavailable because EMA200 history has not matured.
3. **April 2022 to July 2023:** strict coverage catches up, usually within a few symbols of production coverage.
4. **August 2023 onward:** production and strict counts match, with variation driven by overextension filters rather than warmup.

Representative monthly averages:

| Month | Avg production eligible | Avg strict eligible | Interpretation |
| --- | ---: | ---: | --- |
| 2021-07 | 164.33 | 0.00 | Production scoring begins mid-month |
| 2021-12 | 255.00 | 0.00 | Production coverage high, strict EMA200 unavailable |
| 2022-04 | 228.32 | 223.37 | Strict scoring begins |
| 2022-05 | 268.24 | 263.57 | First 275+ production date occurs |
| 2023-08 | 216.09 | 216.09 | Strict and production eligibility converge |
| 2025-02 | 274.05 | 274.05 | Strong broad-universe coverage |
| 2026-06 | 258.11 | 258.11 | Current endpoint remains broadly covered |

## Tradeoff Analysis

### Production Parity Start: 2021-07-12

Benefits:

- Exact match to current production Swing V2.1 eligibility.
- Maximizes long-history period.
- Starts with 253 scoreable symbols.

Costs:

- Uses early EMA200 values before 200-row maturity.
- Strict research eligibility is zero on this date.
- May be challenged as less conservative in a research validation.

### 275+ Symbol Start: 2022-05-25

Benefits:

- First date with at least 275 production-eligible symbols.
- Strict eligibility is already close at 271 symbols.
- Preserves most of the long-history window: about four years through 2026-06.
- Balances production parity with adequate universe breadth.

Costs:

- Still before every symbol reaches the strict EMA200 maturity date.
- Some strict-warmup names remain excluded until later.

### Strict Warmup Start: 2023-08-03

Benefits:

- Fully aligned with the conservative 200-row EMA warmup rule.
- Production and strict eligibility match from this date forward.
- Easiest to defend from a pure indicator-maturity perspective.

Costs:

- Loses more than two years of available production-parity scoring history.
- Starts with only 226 scoreable symbols because overextension filters remove many names that day.
- Weakens the purpose of a long-history validation.

## Decision

Official Phase 2C scoring start date: **2022-05-25**.

This is the best first long-history validation start because:

1. It is the first date with at least 275 production-eligible pilot symbols.
2. It retains a long validation window from 2022-05-25 through 2026-06-11.
3. It is close to strict warmup eligibility on day one: 271 strict-eligible symbols versus 275 production-eligible symbols.
4. It avoids the weakest part of early production parity, where EMA200 values exist but no strict EMA200 maturity is available.
5. It avoids waiting until 2023-08-03, which would discard too much useful history and starts with only 226 scoreable symbols due to market overextension filters.

## Phase 2C Operating Rule

For the first official Swing V2.1 long-history validation:

- Start date: `2022-05-25`
- End date: latest available pilot feature date, currently `2026-06-11`
- Scoring eligibility: production-parity Swing V2.1 rules
- Reporting: include a strict-warmup sensitivity flag or companion summary beginning `2023-08-03`

The primary result should be production-parity. The strict warmup result should be reported as a sensitivity check, not the official baseline.

## Validation SQL

```sql
WITH d AS (
    SELECT
        date,
        COUNT(*) AS rows_present,
        COUNT(*) FILTER (
            WHERE close IS NOT NULL
              AND ema_200 IS NOT NULL
              AND ema_200 <> 0
              AND prior_20d_return IS NOT NULL
              AND ((close - ema_200) / ema_200) <= 0.25
              AND prior_20d_return <= 0.15
        ) AS prod_eligible,
        COUNT(*) FILTER (
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
        ) AS strict_eligible
    FROM pilot_phase2a.features_daily
    GROUP BY date
)
SELECT date, rows_present, prod_eligible, strict_eligible
FROM d
WHERE date IN ('2021-07-12', '2022-05-25', '2023-08-03', '2026-06-11')
ORDER BY date;
```

## Acceptance Confirmation

- Coverage quantified by date, year, period, and representative months.
- One official Phase 2C scoring start date selected: `2022-05-25`.
- No scores generated.
- No backtests run.
- No tables modified.
