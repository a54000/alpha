# Angel Data Audit

Objective: audit the Angel SmartAPI historical database and determine whether it is suitable for extending the NSE Research Platform history.

Scope:

- Research only.
- Do not modify Angel data.
- Do not aggregate Angel data.
- Do not rebuild `prices_daily`, `features_daily`, `sector_daily`, `daily_scores`, or recommendations.
- Use the audit to decide whether daily bars can later be derived reliably from 15-minute bars.

## Source

- Database: `angel_data`
- Table: `ohlcv_15min`
- Expected columns: `datetime`, `symbol`, `open`, `high`, `low`, `close`, `volume`

## Audit Command

Run:

```powershell
.\.venv\Scripts\python.exe scripts\run_angel_data_audit.py
```

If the Angel database uses a separate URL:

```powershell
$env:ANGEL_DATABASE_URL="postgresql+psycopg2://postgres:YOUR_PASSWORD@localhost:5432/angel_data"
.\.venv\Scripts\python.exe scripts\run_angel_data_audit.py --table ohlcv_15min
```

Output:

- `reports/angel_data_audit.json`

## Validations

The audit validates:

1. Distinct symbol count.
2. Earliest date per symbol.
3. Latest date per symbol.
4. Missing symbols versus the current NSE500 research universe.
5. Data gaps by symbol using the Angel source-wide trading calendar.
6. Duplicate records by `symbol, datetime`.
7. OHLC consistency:
   - `high >= low`
   - `high >= open`
   - `high >= close`
   - `low <= open`
   - `low <= close`
8. Volume completeness:
   - null volume rows
   - zero volume rows
9. Trading-day coverage:
   - total trading days
   - first and last trading days
   - lowest symbol-count days

## Suitability Rules

The dataset is considered directly suitable only when:

- `ohlcv_15min` exists and is readable.
- Current NSE500 symbols are materially covered.
- Duplicate extra rows are zero or explainable.
- OHLC invalid rows are zero.
- Data gaps are limited and explainable.
- Volume nulls are zero and zero-volume rows are explainable.

The dataset is considered conditionally suitable when:

- Most symbols are present, but some symbols require mapping, exclusion, or manual review.
- Gaps exist but are confined to suspended, renamed, delisted, or illiquid symbols.
- Daily bars can be derived for a clean subset after exclusions.

The dataset is not suitable when:

- A large share of NSE500 symbols is missing.
- Widespread gaps exist across active symbols.
- Duplicate or OHLC defects are common enough to distort derived daily bars.
- Source date coverage is materially shorter than the intended research window.

## Current Result

Latest generated report:

- `reports/angel_data_audit.json`

Status: completed on 2026-06-12.

Summary:

- Total rows: 13,537,581
- Distinct Angel symbols: 499
- Source date range: 2021-06-14 to 2026-06-12
- Trading days observed: 1,240
- Current research symbols compared: 501
- Missing symbols versus current research universe: 216
- Duplicate `symbol, datetime` groups: 0
- OHLC invalid rows: 680 across 92 symbols
- Null volume rows: 0
- Zero-volume rows: 82 across 44 symbols
- Suitability: conditional

Interpretation:

- The Angel database is large enough to support a 5-year research extension for many symbols.
- Daily bars should not be derived blindly yet because OHLC defects exist and must be reviewed or excluded.
- The 216 missing-symbol count is partly a symbol-master problem: the current research universe includes legacy, renamed, merged, and delisted symbols such as `ADANITRANS`, `CADILAHC`, `CORPBANK`, and `MOTHERSUMI`, while the Angel source contains modern symbols such as `ADANIENSOL`, `ZYDUSLIFE`, and `MSUMI`.
- The next research step is symbol mapping and exclusion review, not aggregation or backtesting.

Current conclusion:

- Complete enough for research use: not yet.
- Daily bars can be reliably derived: not yet for the full universe.
- Daily bars may be derivable for a clean subset after symbol mapping, gap review, and OHLC defect handling.

## Decision Points

Use the report to answer:

- Is the dataset complete enough for research use?
- Can daily bars be reliably derived from 15-minute data?
- Which symbols, if any, should be excluded before historical backtesting?

No ETL, aggregation, feature recomputation, scoring, or backtesting should happen until this audit is completed and reviewed.
