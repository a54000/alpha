# Phase 5.12 Angel Instrument Master Synchronization

## Objective

Create a safe offline process to generate and validate Angel SmartAPI symbol-token mappings for daily market-data ingestion.

This phase does not call Angel trading APIs, does not connect broker order APIs, does not modify strategy logic, does not modify recommendations, and does not change database schema.

## Delivered Components

Script:

```text
scripts/build_angel_token_map.py
```

Primary output:

```text
config/angel_symbol_token_map.csv
```

Validation report:

```text
reports/phase5_12_token_map_validation.json
```

## Input

The script expects an Angel instrument master export in JSON or CSV format.

Typical Angel master fields accepted:

| Accepted field names | Output field |
| --- | --- |
| `symbol`, `name`, `tradingsymbol`, `trading_symbol` | `symbol` |
| `token`, `angel_token`, `symboltoken`, `symbol_token`, `instrument_token` | `angel_token` |
| `exch_seg`, `exchange`, `exch`, `segment` | `exchange` |
| `instrumenttype`, `instrument_type`, `instrument`, `series` | `instrument_type` |
| `expiry`, `expiry_date` | `expiry` |

Symbols ending in `-EQ` are normalized to the canonical symbol without the suffix.

## Output Format

`config/angel_symbol_token_map.csv` contains:

```csv
symbol,angel_token,exchange,instrument_type,expiry
```

Example:

```csv
symbol,angel_token,exchange,instrument_type,expiry
RELIANCE,2885,NSE,EQ,
TCS,11536,NSE,EQ,
```

## Refresh Procedure

1. Download or export the latest Angel instrument master file.

2. Save it under a local path, for example:

```text
data/angel_instrument_master.json
```

3. Run dry validation first:

```powershell
.\.venv\Scripts\python.exe scripts\build_angel_token_map.py --instrument-master data\angel_instrument_master.json --dry-run
```

4. Review:

```text
reports/phase5_12_token_map_validation.json
```

5. If validation is acceptable, generate the token map:

```powershell
.\.venv\Scripts\python.exe scripts\build_angel_token_map.py --instrument-master data\angel_instrument_master.json
```

6. Run ingestion dry-run validation:

```powershell
.\.venv\Scripts\python.exe scripts\sync_angel_daily_data.py --dry-run --symbol-limit 20 --log-level INFO
```

## Pilot Coverage Comparison

By default, the script attempts to compare the generated mapping with:

```text
pilot_phase2a.exact_match_universe
```

The comparison reports:

- Covered pilot symbols.
- Missing pilot symbols.
- Extra Angel symbols not currently in the pilot universe.

To skip database coverage comparison:

```powershell
.\.venv\Scripts\python.exe scripts\build_angel_token_map.py --instrument-master data\angel_instrument_master.json --skip-db-coverage
```

To use an explicit database URL:

```powershell
.\.venv\Scripts\python.exe scripts\build_angel_token_map.py --instrument-master data\angel_instrument_master.json --database-url "<database-url>"
```

## Validation Checks

The script reports:

| Check | Meaning |
| --- | --- |
| `total_mappings` | Number of rows parsed from the master export |
| `duplicate_symbols` | Same normalized symbol appears more than once |
| `duplicate_tokens` | Same Angel token appears more than once |
| `invalid_exchange_symbols` | Mapping is not on an allowed exchange |
| `covered_symbols` | Pilot symbols found in the token map |
| `missing_symbols` | Pilot symbols missing from the token map |
| `extra_symbols` | Token-map symbols not present in the pilot universe |

The script exits with failure if duplicate symbols, duplicate tokens, or invalid exchanges are detected.

By default the builder emits NSE equity rows only. To inspect other exchanges for diagnostics:

```powershell
.\.venv\Scripts\python.exe scripts\build_angel_token_map.py --instrument-master data\angel_instrument_master.json --include-other-exchanges --dry-run
```

Use this diagnostic mode for review only; the daily equity ingestion token map should remain NSE-focused.

## Troubleshooting

### Missing Pilot Symbols

Cause:

- Instrument master is stale.
- Symbol has been renamed.
- Symbol uses an Angel vendor naming convention.
- The pilot universe contains a symbol no longer listed.

Action:

1. Confirm the symbol in the latest Angel master.
2. Check whether the symbol has an `-EQ` suffix or vendor-specific naming.
3. Check Phase 1B reconciliation outputs for known alias or rename cases.
4. Do not manually invent tokens.

### Duplicate Symbols

Cause:

- Multiple instruments share the same visible symbol.
- Derivative or non-equity rows were included.
- The export includes multiple exchange segments.

Action:

1. Prefer `NSE` equity rows.
2. Exclude derivative rows unless explicitly needed for a later phase.
3. Review `instrument_type` and `expiry`.

### Duplicate Tokens

Cause:

- Export issue or repeated rows.

Action:

1. Remove duplicate export rows.
2. Re-download the instrument master if duplicates remain.

### Invalid Exchange Symbols

Cause:

- Non-NSE rows were included.
- Derivative segments such as `NFO` were included.

Action:

1. Filter to NSE equity instruments.
2. Use `--include-non-equity` only for diagnostics, not daily equity ingestion.

## Daily Pipeline Dependency

The daily sync script reads the generated file by default:

```text
config/angel_symbol_token_map.csv
```

Override path:

```powershell
$env:ANGEL_SYMBOL_TOKEN_MAP_CSV="path\to\angel_symbol_token_map.csv"
```

or:

```powershell
.\.venv\Scripts\python.exe scripts\sync_angel_daily_data.py --token-map-csv path\to\angel_symbol_token_map.csv --dry-run
```

## Verification

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_phase5_12_token_map_builder.py
```

Recommended follow-up:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_phase3f_daily_pipeline.py tests\test_phase5_12_token_map_builder.py
```
