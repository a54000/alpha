# Phase 2A.1 Cleaning Results

Objective: create a deterministic cleaning layer for pilot daily bars.

Scope implemented:

- Created cleaned daily bars.
- Created cleaning audit lineage.
- Created rejected-row report.
- Created repair report.

Scope not implemented:

- No feature generation.
- No scoring.
- No recommendations.
- No backtests.
- No production table changes.
- No changes to original pilot daily bars.

## Inputs

- `angel_data.pilot_phase2a.daily_bars`
- `reports/phase2a_daily_bar_issues.csv`
- `docs/PHASE2A_DATA_QUALITY_FORENSICS.md`

## Delivered Files

- `scripts/run_phase2a1_daily_bar_cleaning.py`
- `reports/phase2a1_cleaning_audit.json`
- `reports/phase2a1_rejected_daily_bars.csv`
- `reports/phase2a1_repaired_daily_bars.csv`
- `docs/PHASE2A1_CLEANING_RESULTS.md`

## Pilot Schema Objects

Created in `angel_data.pilot_phase2a`:

- `daily_bars_clean`
- `daily_bar_cleaning_audit`

Original table preserved:

- `daily_bars`

No rows in `daily_bars` were modified.

## Cleaning Rules

Rules are deterministic and applied in priority order.

| Condition | Rule | Action | Rationale |
| --- | --- | --- | --- |
| Null OHLC | `filter_null_ohlc` | filter | Cannot derive reliable indicators or returns. |
| Non-positive OHLC | `filter_non_positive_price` | filter | Invalid market price. |
| Missing `09:15` bar | `filter_missing_opening_bar` | filter | Daily open may be unreliable; next-open entry needs clean open. |
| Missing `15:15` bar | `filter_missing_closing_bar` | filter | Daily close may be unreliable; indicators and exits need clean close. |
| Partial session | `filter_partial_session` | filter | High, low, and volume may be incomplete. |
| OHLC bounds invalid but prices positive and full session present | `repair_ohlc_bounds` | repair | Preserve open/close, set high to max OHLC and low to min OHLC. |
| No issue | `retain_clean_bar` | retain | Row is clean. |

## Lineage Preservation

Every retained, repaired, or filtered row is written to:

```text
pilot_phase2a.daily_bar_cleaning_audit
```

For repaired rows, `daily_bars_clean` stores:

- cleaned OHLC
- original open
- original high
- original low
- original close
- cleaning action
- cleaning rule
- cleaning notes

For filtered rows, the audit table stores:

- symbol
- date
- action
- rule
- original OHLC
- session flags
- bar count

## Results

| Metric | Count |
| --- | ---: |
| Source daily rows | 345,618 |
| Clean daily rows | 344,597 |
| Retained rows | 344,551 |
| Repaired rows | 46 |
| Rejected rows | 1,021 |
| Impacted symbols | 281 |
| Impacted dates | 167 |

## Counts By Rule

| Action | Rule | Rows | Symbols | Dates |
| --- | --- | ---: | ---: | ---: |
| filter | `filter_missing_closing_bar` | 573 | 281 | 9 |
| filter | `filter_missing_opening_bar` | 287 | 279 | 9 |
| filter | `filter_partial_session` | 161 | 19 | 130 |
| repair | `repair_ohlc_bounds` | 46 | 25 | 25 |
| retain | `retain_clean_bar` | 344,551 | 285 | 1,232 |

## Symbols Impacted Most

| Symbol | Repaired rows | Rejected rows | Total impacted |
| --- | ---: | ---: | ---: |
| `CHOLAHLDNG` | 0 | 40 | 40 |
| `GILLETTE` | 0 | 35 | 35 |
| `3MINDIA` | 1 | 31 | 32 |
| `SUNDARMFIN` | 0 | 29 | 29 |
| `GAIL` | 17 | 3 | 20 |
| `HONAUT` | 0 | 15 | 15 |
| `JBCHEPHARM` | 6 | 3 | 9 |
| `GODFRYPHLP` | 0 | 7 | 7 |
| `BBTC` | 1 | 5 | 6 |
| `DCMSHRIRAM` | 1 | 5 | 6 |

## Dates Impacted Most

| Date | Repaired rows | Rejected rows | Total impacted |
| --- | ---: | ---: | ---: |
| 2024-03-02 | 0 | 281 | 281 |
| 2024-05-18 | 0 | 280 | 280 |
| 2025-10-21 | 0 | 279 | 279 |
| 2023-03-03 | 22 | 0 | 22 |
| 2021-09-20 | 1 | 3 | 4 |
| 2022-07-15 | 0 | 4 | 4 |
| 2023-01-20 | 0 | 4 | 4 |
| 2026-06-12 | 0 | 4 | 4 |

## Verification SQL

Row counts:

```sql
SELECT
  (SELECT COUNT(*) FROM pilot_phase2a.daily_bars) AS source_rows,
  (SELECT COUNT(*) FROM pilot_phase2a.daily_bars_clean) AS clean_rows,
  COUNT(*) FILTER (WHERE action = 'retain') AS retained_rows,
  COUNT(*) FILTER (WHERE action = 'repair') AS repaired_rows,
  COUNT(*) FILTER (WHERE action = 'filter') AS rejected_rows
FROM pilot_phase2a.daily_bar_cleaning_audit;
```

Expected:

```text
source_rows = 345618
clean_rows = 344597
retained_rows = 344551
repaired_rows = 46
rejected_rows = 1021
```

Confirm original table is unchanged:

```sql
SELECT COUNT(*) FROM pilot_phase2a.daily_bars;
```

Expected:

```text
345618
```

Confirm no invalid OHLC remains in clean bars:

```sql
SELECT COUNT(*)
FROM pilot_phase2a.daily_bars_clean
WHERE open IS NULL OR high IS NULL OR low IS NULL OR close IS NULL
   OR open <= 0 OR high <= 0 OR low <= 0 OR close <= 0
   OR high < low OR high < open OR high < close OR low > open OR low > close;
```

Expected:

```text
0
```

Confirm no incomplete sessions remain in clean bars:

```sql
SELECT COUNT(*)
FROM pilot_phase2a.daily_bars_clean
WHERE cleaning_action <> 'repair'
  AND cleaning_action <> 'retain';
```

Expected:

```text
0
```

Audit rejected rows:

```sql
SELECT rule_name, COUNT(*)
FROM pilot_phase2a.daily_bar_cleaning_audit
WHERE action = 'filter'
GROUP BY rule_name
ORDER BY COUNT(*) DESC;
```

Audit repaired rows:

```sql
SELECT symbol, date, original_open, original_high, original_low, original_close,
       cleaned_open, cleaned_high, cleaned_low, cleaned_close
FROM pilot_phase2a.daily_bar_cleaning_audit
WHERE action = 'repair'
ORDER BY symbol, date;
```

## Rollback

Preferred rollback:

```sql
DROP TABLE IF EXISTS pilot_phase2a.daily_bars_clean;
DROP TABLE IF EXISTS pilot_phase2a.daily_bar_cleaning_audit;
```

Report files may also be deleted if needed:

- `reports/phase2a1_cleaning_audit.json`
- `reports/phase2a1_rejected_daily_bars.csv`
- `reports/phase2a1_repaired_daily_bars.csv`

No production rollback is required.

## Next Gate Before Feature Generation

Before Phase 2B feature generation:

1. Confirm `daily_bars_clean` has zero invalid OHLC rows.
2. Confirm rejected rows are acceptable.
3. Decide whether the 46 repaired OHLC rows are acceptable or should be excluded instead.
4. Review high-impact symbols:
   - `GAIL`
   - `JBCHEPHARM`
   - `CHOLAHLDNG`
   - `GILLETTE`
   - `3MINDIA`
5. Recalculate symbol coverage after cleaning.

## Final Status

Phase 2A.1 cleaning framework is complete.

Cleaned daily bars exist in:

```text
angel_data.pilot_phase2a.daily_bars_clean
```

The clean table is ready for a separate Phase 2B feature-generation design or implementation step, subject to accepting the repair/filter policy above.
