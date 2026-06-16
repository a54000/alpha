# Angel Symbol Mapping Audit

Objective: build a complete mapping between the current NSE Research Platform universe and the Angel SmartAPI universe.

Scope:

- Research only.
- Do not modify production tables.
- Do not rebuild data.
- Do not aggregate daily bars.
- Only create the mapping and audit.

## Sources

1. Current NSE Research Platform symbols from the latest `universe_snapshot` for `NSE500`.
2. Angel SmartAPI symbols from `angel_data.ohlcv_15min`.

Output:

- `reports/angel_symbol_mapping.csv`

Generated with:

```powershell
.\.venv\Scripts\python.exe scripts\run_angel_symbol_mapping_audit.py
```

## Method

Mapping statuses:

- `exact`: same symbol exists in both sources.
- `known_rename`: manually seeded candidate for a known rename or corporate-action symbol change.
- `normalized_match`: one-to-one match after removing punctuation.
- `potential`: one prefix-similar candidate was found; manual review required.
- `ambiguous`: multiple candidates were found; manual review required.
- `unmatched`: research symbol has no Angel candidate.
- `angel_only`: Angel symbol is not mapped to the current research universe.

Normalization removes non-alphanumeric characters and uppercases the symbol. It is used only for audit matching, not as a production rewrite rule.

## Results

Generated on: 2026-06-12.

Summary:

- Research universe symbols: 501
- Angel symbols: 499
- Mapped research symbols: 313
- Coverage: 62.48%
- Exact matches: 285
- Known rename mappings: 16
- Potential one-to-one mappings: 12
- Ambiguous mappings: 7
- Unmatched research symbols: 181
- Angel-only symbols: 193

## Known Rename Candidates

These are included as audit candidates and should be manually verified before production use:

| Research symbol | Angel symbol |
| --- | --- |
| `ADANITRANS` | `ADANIENSOL` |
| `AMARAJABAT` | `ARE&M` |
| `CADILAHC` | `ZYDUSLIFE` |
| `IBULHSGFIN` | `SAMMAANCAP` |
| `INFRATEL` | `INDUSTOWER` |
| `KALPATPOWR` | `KPIL` |
| `MAHINDCIE` | `CIEINDIA` |
| `MCDOWELL-N` | `UNITDSPR` |
| `MINDAIND` | `UNOMINDA` |
| `MOTHERSUMI` | `MSUMI` |
| `NIITTECH` | `COFORGE` |
| `PHILIPCARB` | `PCBL` |
| `RNAM` | `NAM-INDIA` |
| `SRTRANSFIN` | `SHRIRAMFIN` |
| `TATAGLOBAL` | `TATACONSUM` |
| `WABCOINDIA` | `ZFCVINDIA` |

## Ambiguous Mappings

These must not be auto-mapped:

| Research symbol | Angel candidates |
| --- | --- |
| `AEGISCHEM` | `AEGISLOG`, `AEGISVOPAK` |
| `BAJAJCON` | `BAJAJ-AUTO`, `BAJAJFINSV`, `BAJAJHFL`, `BAJAJHLDNG` |
| `BAJAJELEC` | `BAJAJ-AUTO`, `BAJAJFINSV`, `BAJAJHFL`, `BAJAJHLDNG` |
| `GODREJAGRO` | `GODREJCP`, `GODREJIND`, `GODREJPROP` |
| `HDFC` | `HDFCAMC`, `HDFCBANK`, `HDFCLIFE` |
| `L&TFH` | `LT`, `LTF` |
| `TATACOFFEE` | `TATACAP`, `TATACHEM`, `TATACOMM`, `TATACONSUM` |

## Potential Mappings

These are weak candidates and require manual verification. Some are likely false positives:

| Research symbol | Angel candidate |
| --- | --- |
| `ASHOKA` | `ASHOKLEY` |
| `ASTRAZEN` | `ASTRAL` |
| `IDFC` | `IDFCFIRSTB` |
| `JSLHISAR` | `JSL` |
| `LTI` | `LT` |
| `PTC` | `PTCIL` |
| `PVR` | `PVRINOX` |
| `RAIN` | `RAINBOW` |
| `SHRIRAMCIT` | `SHRIRAMFIN` |
| `STAR` | `STARHEALTH` |
| `WELSPUNIND` | `WELSPUNLIV` |
| `ZYDUSWELL` | `ZYDUSLIFE` |

## Unmatched Symbols

There are 181 research symbols with no current Angel candidate under this audit. Examples:

- `ADVENZYMES`
- `AKZOINDIA`
- `ALBK`
- `ALLCARGO`
- `ANDHRABANK`
- `APLLTD`
- `AVANTIFEED`
- `BALMLAWRIE`
- `BASF`
- `BIRLACORPN`
- `BLISSGVS`
- `BOMDYEING`
- `CARERATING`
- `CENTURYPLY`
- `CERA`
- `COFFEEDAY`
- `CORPBANK`
- `COX&KINGS`
- `DBCORP`
- `DBL`

Full list is in `reports/angel_symbol_mapping.csv`.

## Angel-Only Symbols

There are 193 Angel symbols not mapped to the current research universe. Examples:

- `360ONE`
- `AADHARHFC`
- `AARTIIND`
- `ABBOTINDIA`
- `ABDL`
- `ABSLAMC`
- `ACE`
- `ACMESOLAR`
- `ADANIENT`
- `AEGISLOG`
- `AFCONS`
- `AFFLE`
- `AMBER`
- `ANANDRATHI`
- `ANGELONE`
- `ATHERENERG`
- `BAJAJHFL`

Full list is in `reports/angel_symbol_mapping.csv`.

## Recommended Canonical Format

Use the current NSE/Angel trading symbol as the canonical symbol for historical extension, preserving punctuation where NSE uses it, such as `BAJAJ-AUTO`, `MCDOWELL-N`, `ARE&M`, and `L&TFH`.

Recommended fields for a future non-production staging map:

- `canonical_symbol`: current NSE/Angel trading symbol.
- `research_symbol`: symbol currently used by the research platform.
- `angel_symbol`: symbol present in `ohlcv_15min`.
- `valid_from`: first date the mapping is valid.
- `valid_to`: last date the mapping is valid, nullable.
- `mapping_reason`: exact, rename, merger, demerger, delisting, manual exclusion.
- `review_status`: pending, approved, rejected.

Do not rewrite `symbol_master` until the mapping is manually reviewed. Legacy names should be treated as aliases, not silently replaced.

## Research Conclusion

The symbol mapping is not yet complete enough for production ETL.

The Angel source appears to contain a modern NSE universe, while the current research universe includes many legacy, renamed, merged, and delisted symbols. Exact matches cover most currently aligned names, but the 62.48% mapped coverage shows that symbol history and alias handling must be resolved before daily bars are derived or Swing V2.1 is re-run on extended history.

Next research step: manually review `known_rename`, reject false `potential` mappings, resolve `ambiguous` mappings, and decide whether unmatched legacy symbols should be mapped, excluded, or handled through historical index membership reconstruction.
