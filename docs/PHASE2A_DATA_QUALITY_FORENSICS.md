# Phase 2A Data Quality Forensics

Objective: analyze `reports/phase2a_daily_bar_issues.csv`.

Scope:

- Research only.
- Do not modify pilot tables.
- Do not regenerate bars.
- Do not rebuild features.

## Executive Summary

The Phase 2A pilot produced 345,618 daily bars for 285 exact-match securities. The issues file contains 1,067 issue rows.

Most issues are not randomly distributed. They cluster heavily by date:

- `2024-03-02`: 281 missing closing bars
- `2024-05-18`: 280 missing closing bars
- `2025-10-21`: 279 missing opening bars

These three dates account for 840 of 1,067 issue rows, or 78.7% of all reported issues.

Conclusion:

- Date-wide opening/closing-bar issues require filtering.
- Invalid OHLC rows require repair or exclusion.
- Repeated symbol-specific partial-day issues require symbol-level review before feature rebuild.

## Issue Counts

| Issue type | Rows | Affected symbols | Affected dates | Classification |
| --- | ---: | ---: | ---: | --- |
| missing_closing_bar | 573 | 281 | 9 | Requires filtering |
| missing_opening_bar | 287 | 279 | 9 | Requires filtering |
| partial_day | 161 | 19 | 130 | Requires filtering |
| invalid_ohlc | 46 | 25 | 25 | Requires repair |
| Total | 1,067 | - | - | - |

## Symbols With Highest Issue Counts

| Symbol | Issue rows | Main issue profile | Classification |
| --- | ---: | --- | --- |
| `CHOLAHLDNG` | 40 | 37 partial days | Requires filtering |
| `GILLETTE` | 35 | 31 partial days | Requires filtering |
| `3MINDIA` | 32 | 28 partial days, 1 invalid OHLC | Requires filtering plus repair row |
| `SUNDARMFIN` | 29 | 26 partial days | Requires filtering |
| `GAIL` | 20 | 17 invalid OHLC rows | Requires repair |
| `HONAUT` | 15 | 12 partial days | Requires filtering |
| `JBCHEPHARM` | 9 | 6 invalid OHLC rows | Requires repair |
| `GODFRYPHLP` | 7 | 4 partial days | Requires filtering |
| `BBTC` | 6 | mixed partial/invalid/edge bars | Requires filtering plus repair row |
| `DCMSHRIRAM` | 6 | mixed partial/invalid/edge bars | Requires filtering plus repair row |

## Dates With Highest Issue Counts

| Date | Issue rows | Main issue profile | Classification |
| --- | ---: | --- | --- |
| 2024-03-02 | 281 | missing closing bar | Requires filtering |
| 2024-05-18 | 280 | missing closing bar | Requires filtering |
| 2025-10-21 | 279 | missing opening bar | Requires filtering |
| 2023-03-03 | 22 | invalid OHLC | Requires repair |
| 2023-01-20 | 4 | partial day | Requires filtering |
| 2021-09-20 | 4 | mixed missing close and invalid OHLC | Requires filtering plus repair |
| 2022-07-15 | 4 | partial day | Requires filtering |
| 2026-06-12 | 4 | missing closing bar | Requires filtering |

The top three dates explain most of the issue volume and should be handled as calendar/session exceptions.

## Year Clustering

| Year | Issue rows | Main drivers |
| --- | ---: | --- |
| 2021 | 30 | partial days and GAIL invalid OHLC rows |
| 2022 | 88 | partial days plus scattered invalid OHLC rows |
| 2023 | 85 | partial days plus 2023-03-03 invalid OHLC cluster |
| 2024 | 568 | two date-wide missing-close sessions |
| 2025 | 288 | one date-wide missing-open session |
| 2026 | 8 | small edge-bar/partial-day residue |

Interpretation:

- 2024 and 2025 problems are mostly date-wide session boundary issues.
- 2021-2023 problems are more symbol-specific and require closer review.

## Open, Close, And Session Impact

### Open Impact

Missing opening bar rows:

```text
287
```

Main cluster:

- `2025-10-21`: 279 rows

Impact:

- Next-day open entry logic depends on valid open prices.
- A missing `09:15` bar can distort daily open.
- These dates should be excluded from entry-price usage unless repaired.

Classification:

```text
Requires filtering
```

### Close Impact

Missing closing bar rows:

```text
573
```

Main clusters:

- `2024-03-02`: 281 rows
- `2024-05-18`: 280 rows

Impact:

- Fixed-horizon exits use close prices.
- Technical indicators use close prices.
- Missing final interval can distort daily close, returns, EMA, ADX, and prior 20-day return.

Classification:

```text
Requires filtering
```

### Entire Session / Partial-Day Impact

Partial-day rows:

```text
161
```

Main symbol clusters:

- `CHOLAHLDNG`
- `GILLETTE`
- `3MINDIA`
- `SUNDARMFIN`
- `HONAUT`

Impact:

- Partial days may still provide usable OHLC if open/close are present, but volume and intraday high/low may be incomplete.
- Repeated partial days in the same symbol can distort volume, ATR, ADX, and high/low-derived features.

Classification:

```text
Requires filtering
```

## Invalid OHLC Forensics

Invalid OHLC rows:

```text
46
```

Affected symbols:

```text
25
```

Top affected symbols:

| Symbol | Invalid OHLC rows |
| --- | ---: |
| `GAIL` | 17 |
| `JBCHEPHARM` | 6 |
| multiple others | 1 each |

Top invalid OHLC date:

| Date | Invalid OHLC rows |
| --- | ---: |
| 2023-03-03 | 22 |

Examples:

- `3MINDIA` on 2023-03-03 has low above open.
- `BHARATFORG` on 2023-03-03 has high below open.
- `GAIL` has repeated invalid OHLC rows across 2021-2023.

Impact:

- Invalid OHLC rows cannot safely feed indicators.
- They can corrupt high/low, ATR, ADX, breakout, and daily return calculations.

Classification:

```text
Requires repair
```

Recommended handling before Phase 2B:

- Exclude invalid OHLC symbol/date rows from feature generation, or
- Repair from source 15-minute bars if the bad daily value is caused by aggregation edge cases, or
- Exclude affected symbol if defects are frequent and not repairable.

## Feature Generation Impact

### EMA200

Impact:

- Missing close values or distorted closes affect EMA200 for many subsequent days.
- Date-wide missing closing bars should be removed before feature rebuild.

Classification:

```text
Requires filtering
```

### Prior 20-Day Return

Impact:

- Missing or distorted closes affect rolling 20-day returns.
- A single bad close can affect both the signal day and subsequent 20-day lookbacks.

Classification:

```text
Requires filtering
```

### ADX

Impact:

- ADX depends on high, low, and close.
- Invalid OHLC rows directly corrupt ADX.
- Partial sessions may understate true high/low range.

Classification:

```text
Requires repair for invalid OHLC; filtering for partial sessions
```

### Sector Rank

Impact:

- Sector rank depends on daily returns across symbols.
- Date-wide missing close/open events can distort sector-level returns if included.
- Since the issue clusters are mostly date-wide, sector ranks should exclude affected dates.

Classification:

```text
Requires filtering
```

### Volume And Liquidity

Impact:

- Null and zero-volume daily rows are not present.
- Partial sessions can still understate volume.

Classification:

```text
Mostly safe, but partial-day volume requires filtering if used
```

## Classification Summary

### Safe To Ignore

None of the major issue classes should be blindly ignored before feature rebuild.

Possibly safe after explicit policy:

- Isolated partial days where open and close are present and the date is a known special trading session.
- Tiny number of edge-bar issues on non-signal dates, if excluded from entry/exit price usage.

### Requires Filtering

Filter before Phase 2B:

- `2024-03-02`
- `2024-05-18`
- `2025-10-21`
- all symbol/date rows with missing opening bar
- all symbol/date rows with missing closing bar
- all partial days unless validated as source-wide special sessions

### Requires Repair

Repair or exclude before Phase 2B:

- 46 invalid OHLC rows
- `GAIL` repeated invalid OHLC rows
- `JBCHEPHARM` repeated invalid OHLC rows
- 2023-03-03 invalid OHLC cluster

## Recommended Pre-Phase 2B Gate

Before feature rebuild:

1. Create an exclusion list of bad symbol/date daily bars.
2. Exclude all invalid OHLC rows.
3. Exclude date-wide bad sessions:
   - `2024-03-02`
   - `2024-05-18`
   - `2025-10-21`
4. Review whether partial days are true special sessions or bad source coverage.
5. Produce a clean daily-bar view for feature generation.
6. Recompute coverage after filtering.

Do not mutate `pilot_phase2a.daily_bars` during this step. Use a view, staging query, or separate clean table in a later approved phase.

## Final Verdict

The Phase 2A daily bars are good enough to proceed to a cleaning/filter design phase, but not directly to feature generation.

Most issue volume is date-clustered and therefore manageable with filtering. The invalid OHLC rows are smaller in count but more serious and require repair or exclusion. Feature generation should wait until a clean-bar policy is defined and validated.
