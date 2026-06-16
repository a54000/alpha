# Angel Symbol Master Forensics

Objective: determine whether low mapping coverage is caused by missing Angel data, incorrect symbol normalization, incomplete Angel symbol master, corporate-action lineage, or research universe issues.

Inputs:

- `reports/angel_symbol_mapping.csv`
- Angel symbols from `angel_data.ohlcv_15min`
- Research symbols from the current NSE Research Platform universe
- NSE official equity symbol list: `https://archives.nseindia.com/content/equities/EQUITY_L.csv`

Scope:

- Research only.
- Do not modify mappings.
- Do not modify databases.
- Do not aggregate data.

## Executive Conclusion

The low raw mapping coverage is mostly not caused by missing Angel data.

Current evidence points to three bigger causes:

1. Research universe issues: the research universe contains stale/legacy NSE500 symbols and misses many current NSE-listed names that are present in Angel.
2. Corporate-action lineage: several missing research symbols are old names, merged entities, delisted entities, or demerged lineages.
3. Incomplete alias mapping: simple string matching misses economic continuity when a company changes symbol or corporate structure.

Angel symbol master coverage appears stronger than raw mapping suggests:

- Angel-only symbols: 193
- Angel-only symbols found in official NSE equity list: 193
- Unmatched research symbols: 181
- Unmatched research symbols found in official NSE equity list: 130
- Raw mapped research coverage: 313 of 501, or 62.48%

The critical point: all Angel-only symbols are official NSE-listed symbols, and the top Angel-only names include economically important companies such as `MCX`, `ATGL`, `ADANIENT`, `KAYNES`, `ETERNAL`, `JIOFIN`, `LICI`, `POLYCAB`, `RVNL`, `PAYTM`, and `MAZDOCK`. These are not bad Angel symbols; they are missing from the research universe or not mapped because the research universe is stale.

## Cause Assessment

| Cause | Finding | Verdict |
| --- | --- | --- |
| Missing Angel data | Some research symbols are not in Angel, but Angel has 499 symbols and all 193 Angel-only symbols validate as current NSE-listed. | Partial cause only. |
| Incorrect symbol normalization | Only a small number of cases look like punctuation/vendor formatting differences, such as `GET&D` versus `GVT&D` and `GEPIL` versus `GPIL`. | Minor cause. |
| Incomplete Angel symbol master | Angel-only names validate against the official NSE equity list. | Not the main cause. |
| Corporate-action lineage | Many gaps are old symbols, renamed entities, mergers, demergers, or delistings. | Major cause. |
| Research universe issues | The research universe misses many current, liquid Angel/NSE symbols and contains many old names. | Major cause. |

## Angel-Only Correspondence To Unmatched Research Symbols

The audit identifies a small set of direct or likely correspondences between Angel-only symbols and unmatched research symbols. These require manual validation before any mapping update:

| Unmatched research symbol | Angel-only candidate | Confidence | Reason |
| --- | --- | --- | --- |
| `GET&D` | `GVT&D` | High | Vendor/current-symbol convention likely differs. |
| `GEPIL` | `GPIL` | High | Likely shortened/current-symbol convention. |
| `GMRINFRA` | `GMRAIRPORT` | Medium | GMR corporate/symbol lineage likely, but verify event dates. |
| `MAGMA` | `POONAWALLA` | Medium | Acquisition/rename lineage likely, but verify continuity. |
| `IBVENTURES` | `IIFL` | Low | Needs corporate-lineage confirmation; do not auto-map. |
| `MAXINDIA` | `MAXHEALTH` | Low | Max group restructuring; ambiguous. |
| `PEL` | `PIRAMALFIN` | Low | Piramal demerger/restructure; ambiguous. |

Estimated direct Angel-only-to-unmatched correspondence from this forensic pass: 7 symbols, of which only 2 are high-confidence formatting/name-convention cases.

## Estimated True Economic Coverage

Raw symbol-string coverage is 62.48%, but this understates economic coverage because:

- Angel has many current NSE-listed symbols absent from the research universe.
- Several research symbols are stale aliases of current Angel symbols.
- Some missing research symbols are no longer economically relevant for current-universe research because they are delisted, merged, or suspended.

Conservative estimate:

- Direct mapped coverage: 313 of 501, or 62.48%
- Add high-confidence Angel-only correspondences: 315 of 501, or 62.87%
- Add all seven direct/likely correspondences: 320 of 501, or 63.87%

Economic coverage for a modern NSE universe is likely materially higher than 63.87%, because many Angel-only symbols are current and liquid NSE companies that should be in a refreshed universe. The current blocker is not just alias mapping; it is that the research universe itself must be reconciled against a current NSE500 membership source before extended historical testing.

## Top 100 Unmatched Research Symbols By Local Market-Relevance Proxy

Market relevance proxy: latest research `features_daily.avg_traded_value`, with latest price-volume fallback. Values are shown in INR crore-equivalent units from local data calculations.

| Rank | Research symbol | Sector | In official NSE list | Relevance proxy |
| ---: | --- | --- | --- | ---: |
| 1 | `THOMASCOOK` | SERVICES | yes | 542.1 |
| 2 | `MHRIL` | SERVICES | yes | 216.2 |
| 3 | `SOUTHBANK` | FINANCIAL SERVICES | yes | 149.0 |
| 4 | `CERA` | CONSTRUCTION | yes | 128.0 |
| 5 | `SUVEN` | PHARMA | yes | 112.4 |
| 6 | `KTKBANK` | FINANCIAL SERVICES | yes | 105.3 |
| 7 | `SHILPAMED` | PHARMA | yes | 80.1 |
| 8 | `THYROCARE` | HEALTHCARE SERVICES | yes | 77.2 |
| 9 | `AVANTIFEED` | CONSUMER GOODS | yes | 69.6 |
| 10 | `SPARC` | PHARMA | yes | 69.2 |
| 11 | `WABAG` | SERVICES | yes | 65.4 |
| 12 | `EDELWEISS` | FINANCIAL SERVICES | yes | 43.5 |
| 13 | `RAYMOND` | TEXTILES | yes | 42.1 |
| 14 | `RELAXO` | CONSUMER GOODS | yes | 40.9 |
| 15 | `SFL` | CONSUMER GOODS | yes | 36.9 |
| 16 | `TIMETECHNO` | INDUSTRIAL MANUFACTURING | yes | 35.7 |
| 17 | `ITDC` | SERVICES | yes | 34.3 |
| 18 | `NETWORK18` | MEDIA & ENTERTAINMENT | yes | 31.5 |
| 19 | `PCJEWELLER` | CONSUMER GOODS | yes | 26.8 |
| 20 | `BLISSGVS` | PHARMA | yes | 26.1 |
| 21 | `KIOCL` | METALS | yes | 24.5 |
| 22 | `SHARDACROP` | FERTILISERS & PESTICIDES | yes | 22.9 |
| 23 | `QUESS` | SERVICES | yes | 22.4 |
| 24 | `PARAGMILK` | CONSUMER GOODS | yes | 19.0 |
| 25 | `GREAVESCOT` | INDUSTRIAL MANUFACTURING | yes | 18.8 |
| 26 | `IBREALEST` | CONSTRUCTION | no | 18.2 |
| 27 | `APLLTD` | PHARMA | yes | 17.0 |
| 28 | `DCBBANK` | FINANCIAL SERVICES | yes | 16.7 |
| 29 | `PRAJIND` | INDUSTRIAL MANUFACTURING | yes | 16.5 |
| 30 | `KNRCON` | CONSTRUCTION | yes | 16.5 |
| 31 | `DELTACORP` | SERVICES | yes | 16.2 |
| 32 | `RCF` | FERTILISERS & PESTICIDES | yes | 15.3 |
| 33 | `GPPL` | SERVICES | yes | 15.0 |
| 34 | `GUJGASLTD` | ENERGY | yes | 14.9 |
| 35 | `PGHH` | CONSUMER GOODS | yes | 14.1 |
| 36 | `NESCO` | SERVICES | yes | 14.1 |
| 37 | `JAMNAAUTO` | AUTOMOBILE | yes | 13.0 |
| 38 | `VMART` | CONSUMER GOODS | yes | 12.6 |
| 39 | `MOIL` | METALS | yes | 12.2 |
| 40 | `BOMDYEING` | TEXTILES | yes | 11.8 |
| 41 | `FDC` | PHARMA | yes | 11.1 |
| 42 | `JUSTDIAL` | IT | yes | 10.6 |
| 43 | `COFFEEDAY` | CONSUMER GOODS | yes | 10.3 |
| 44 | `GNFC` | CHEMICALS | yes | 9.9 |
| 45 | `RENUKA` | CONSUMER GOODS | yes | 9.5 |
| 46 | `KRBL` | CONSUMER GOODS | yes | 9.5 |
| 47 | `VSTIND` | CONSUMER GOODS | yes | 9.0 |
| 48 | `GHCL` | CHEMICALS | yes | 8.6 |
| 49 | `LUXIND` | TEXTILES | yes | 7.9 |
| 50 | `SUNTECK` | CONSTRUCTION | yes | 7.9 |
| 51 | `SYMPHONY` | CONSUMER GOODS | yes | 7.8 |
| 52 | `IFBIND` | CONSUMER GOODS | yes | 7.6 |
| 53 | `NFL` | FERTILISERS & PESTICIDES | yes | 7.5 |
| 54 | `INDOSTAR` | FINANCIAL SERVICES | yes | 7.4 |
| 55 | `FINPIPE` | INDUSTRIAL MANUFACTURING | yes | 7.3 |
| 56 | `VINATIORGA` | CHEMICALS | yes | 7.0 |
| 57 | `PNCINFRA` | CONSTRUCTION | yes | 6.9 |
| 58 | `RALLIS` | FERTILISERS & PESTICIDES | yes | 6.7 |
| 59 | `JYOTHYLAB` | CONSUMER GOODS | yes | 6.5 |
| 60 | `BASF` | CHEMICALS | yes | 6.5 |
| 61 | `TTKPRESTIG` | CONSUMER GOODS | yes | 6.1 |
| 62 | `DCAL` | PHARMA | yes | 6.0 |
| 63 | `REPCOHOME` | FINANCIAL SERVICES | yes | 6.0 |
| 64 | `GSFC` | FERTILISERS & PESTICIDES | yes | 5.9 |
| 65 | `SUDARSCHEM` | CHEMICALS | yes | 5.6 |
| 66 | `ORIENTELEC` | CONSUMER GOODS | yes | 5.5 |
| 67 | `DBL` | CONSTRUCTION | yes | 5.5 |
| 68 | `CENTURYPLY` | CONSUMER GOODS | yes | 5.4 |
| 69 | `GALAXYSURF` | CHEMICALS | yes | 5.4 |
| 70 | `VIPIND` | CONSUMER GOODS | yes | 5.4 |
| 71 | `SIS` | SERVICES | yes | 5.2 |
| 72 | `KSCL` | CONSUMER GOODS | yes | 5.2 |
| 73 | `GULFOILLUB` | ENERGY | yes | 4.9 |
| 74 | `STARCEMENT` | CEMENT & CEMENT PRODUCTS | yes | 4.9 |
| 75 | `JAICORPLTD` | INDUSTRIAL MANUFACTURING | yes | 4.7 |
| 76 | `JISLJALEQS` | INDUSTRIAL MANUFACTURING | yes | 4.6 |
| 77 | `GRINDWELL` | INDUSTRIAL MANUFACTURING | yes | 4.4 |
| 78 | `SANOFI` | PHARMA | yes | 4.4 |
| 79 | `HERITGFOOD` | CONSUMER GOODS | yes | 4.4 |
| 80 | `KANSAINER` | CONSUMER GOODS | yes | 4.4 |
| 81 | `ALLCARGO` | SERVICES | yes | 4.3 |
| 82 | `SKFINDIA` | INDUSTRIAL MANUFACTURING | yes | 4.3 |
| 83 | `VENKEYS` | CONSUMER GOODS | yes | 4.2 |
| 84 | `PGHL` | PHARMA | yes | 4.1 |
| 85 | `SUPRAJIT` | AUTOMOBILE | yes | 4.0 |
| 86 | `MAHLOG` | SERVICES | yes | 4.0 |
| 87 | `AKZOINDIA` | CONSUMER GOODS | no | 3.8 |
| 88 | `JKPAPER` | PAPER | yes | 3.8 |
| 89 | `UFLEX` | INDUSTRIAL MANUFACTURING | yes | 3.8 |
| 90 | `BIRLACORPN` | CEMENT & CEMENT PRODUCTS | yes | 3.6 |
| 91 | `SHK` | CONSUMER GOODS | yes | 3.6 |
| 92 | `KOLTEPATIL` | CONSTRUCTION | yes | 3.4 |
| 93 | `GUJALKALI` | CHEMICALS | yes | 3.3 |
| 94 | `CARERATING` | FINANCIAL SERVICES | yes | 3.3 |
| 95 | `VRLLOG` | SERVICES | yes | 3.2 |
| 96 | `FINEORG` | CHEMICALS | yes | 3.1 |
| 97 | `BALMLAWRIE` | SERVICES | yes | 3.0 |
| 98 | `ADVENZYMES` | CONSUMER GOODS | yes | 3.0 |
| 99 | `SUNDRMFAST` | AUTOMOBILE | yes | 2.9 |
| 100 | `MAHSEAMLES` | METALS | yes | 2.9 |

## Top 100 Angel-Only Symbols

Market relevance proxy: average daily traded value over the most recent 30 calendar days of Angel 15-minute data. Values are shown in INR crore-equivalent units from local data calculations.

| Rank | Angel symbol | In official NSE list | Relevance proxy | Recent days |
| ---: | --- | --- | ---: | ---: |
| 1 | `MCX` | yes | 1184.4 | 20 |
| 2 | `NETWEB` | yes | 1016.2 | 20 |
| 3 | `ATGL` | yes | 940.0 | 20 |
| 4 | `ADANIENT` | yes | 860.9 | 20 |
| 5 | `OLAELEC` | yes | 750.4 | 20 |
| 6 | `POWERINDIA` | yes | 745.3 | 20 |
| 7 | `ETERNAL` | yes | 711.9 | 20 |
| 8 | `KAYNES` | yes | 685.0 | 20 |
| 9 | `TEJASNET` | yes | 597.2 | 20 |
| 10 | `GROWW` | yes | 585.2 | 20 |
| 11 | `DATAPATTNS` | yes | 545.4 | 20 |
| 12 | `TMPV` | yes | 512.6 | 20 |
| 13 | `JPPOWER` | yes | 512.5 | 20 |
| 14 | `GVT&D` | yes | 482.0 | 20 |
| 15 | `PINELABS` | yes | 472.3 | 20 |
| 16 | `ATHERENERG` | yes | 435.4 | 20 |
| 17 | `HYUNDAI` | yes | 428.7 | 20 |
| 18 | `SAREGAMA` | yes | 423.7 | 20 |
| 19 | `AMBER` | yes | 404.4 | 20 |
| 20 | `MOTHERSON` | yes | 396.9 | 20 |
| 21 | `LENSKART` | yes | 387.0 | 20 |
| 22 | `MEESHO` | yes | 379.6 | 20 |
| 23 | `TMCV` | yes | 371.8 | 20 |
| 24 | `MAXHEALTH` | yes | 369.2 | 20 |
| 25 | `POLICYBZR` | yes | 350.8 | 20 |
| 26 | `WAAREEENER` | yes | 323.1 | 20 |
| 27 | `ENRIN` | yes | 320.2 | 20 |
| 28 | `NESTLEIND` | yes | 307.8 | 20 |
| 29 | `KALYANKJIL` | yes | 306.4 | 20 |
| 30 | `RVNL` | yes | 292.7 | 20 |
| 31 | `JIOFIN` | yes | 276.7 | 20 |
| 32 | `SWIGGY` | yes | 275.6 | 20 |
| 33 | `ANGELONE` | yes | 270.1 | 20 |
| 34 | `AEGISLOG` | yes | 264.8 | 20 |
| 35 | `GRSE` | yes | 259.4 | 20 |
| 36 | `POLYCAB` | yes | 256.8 | 20 |
| 37 | `PREMIERENE` | yes | 249.5 | 20 |
| 38 | `LICI` | yes | 247.3 | 20 |
| 39 | `CARTRADE` | yes | 246.2 | 20 |
| 40 | `GMRAIRPORT` | yes | 239.5 | 20 |
| 41 | `PAYTM` | yes | 234.4 | 20 |
| 42 | `GLAND` | yes | 227.2 | 20 |
| 43 | `FORCEMOT` | yes | 223.0 | 20 |
| 44 | `HONASA` | yes | 217.3 | 20 |
| 45 | `LTM` | yes | 211.8 | 20 |
| 46 | `MANKIND` | yes | 206.6 | 20 |
| 47 | `TATACOMM` | yes | 202.2 | 20 |
| 48 | `JAINREC` | yes | 199.5 | 20 |
| 49 | `LODHA` | yes | 191.9 | 20 |
| 50 | `MAZDOCK` | yes | 189.4 | 20 |
| 51 | `NYKAA` | yes | 189.3 | 20 |
| 52 | `APARINDS` | yes | 189.1 | 20 |
| 53 | `ANANTRAJ` | yes | 177.8 | 20 |
| 54 | `NEWGEN` | yes | 175.3 | 20 |
| 55 | `PATANJALI` | yes | 164.0 | 20 |
| 56 | `PWL` | yes | 155.8 | 20 |
| 57 | `ANANDRATHI` | yes | 151.9 | 20 |
| 58 | `ZENTEC` | yes | 151.6 | 21 |
| 59 | `JSWCEMENT` | yes | 149.1 | 20 |
| 60 | `EMMVEE` | yes | 147.3 | 20 |
| 61 | `SYRMA` | yes | 145.5 | 20 |
| 62 | `PGEL` | yes | 144.9 | 20 |
| 63 | `RRKABEL` | yes | 144.6 | 20 |
| 64 | `CPPLUS` | yes | 144.2 | 20 |
| 65 | `GPIL` | yes | 144.1 | 20 |
| 66 | `VMM` | yes | 144.0 | 20 |
| 67 | `ACUTAAS` | yes | 143.3 | 20 |
| 68 | `IIFL` | yes | 138.7 | 20 |
| 69 | `LTF` | yes | 134.7 | 20 |
| 70 | `HBLENGINE` | yes | 133.0 | 20 |
| 71 | `TATATECH` | yes | 132.4 | 20 |
| 72 | `KPITTECH` | yes | 129.0 | 20 |
| 73 | `JYOTICNC` | yes | 128.0 | 20 |
| 74 | `BELRISE` | yes | 119.8 | 20 |
| 75 | `DELHIVERY` | yes | 117.0 | 20 |
| 76 | `ICICIAMC` | yes | 115.3 | 20 |
| 77 | `OLECTRA` | yes | 109.0 | 20 |
| 78 | `JBMA` | yes | 107.2 | 20 |
| 79 | `SAILIFE` | yes | 103.5 | 20 |
| 80 | `IREDA` | yes | 102.6 | 20 |
| 81 | `TITAGARH` | yes | 99.4 | 20 |
| 82 | `CEMPRO` | yes | 98.9 | 20 |
| 83 | `ACMESOLAR` | yes | 98.2 | 20 |
| 84 | `KFINTECH` | yes | 95.9 | 20 |
| 85 | `360ONE` | yes | 92.5 | 20 |
| 86 | `IRFC` | yes | 91.6 | 20 |
| 87 | `SONACOMS` | yes | 88.6 | 20 |
| 88 | `LLOYDSME` | yes | 85.3 | 20 |
| 89 | `CAMS` | yes | 84.9 | 20 |
| 90 | `AFCONS` | yes | 82.0 | 20 |
| 91 | `LGEINDIA` | yes | 81.5 | 20 |
| 92 | `NSLNISP` | yes | 80.2 | 20 |
| 93 | `BLS` | yes | 79.8 | 20 |
| 94 | `NEULANDLAB` | yes | 78.4 | 20 |
| 95 | `FIRSTCRY` | yes | 77.5 | 20 |
| 96 | `CONCORDBIO` | yes | 74.7 | 20 |
| 97 | `NUVAMA` | yes | 73.6 | 20 |
| 98 | `TECHNOE` | yes | 73.4 | 20 |
| 99 | `SHYAMMETL` | yes | 70.9 | 20 |
| 100 | `SBICARD` | yes | 70.5 | 20 |

## Forensic Interpretation

The top 100 unmatched research symbols are mostly still official NSE-listed names. That means the mapping problem is not limited to dead symbols. However, many of these symbols are absent from Angel while newer or successor symbols are present.

The top 100 Angel-only symbols are all official NSE-listed and many are highly liquid or economically important. This strongly indicates the research universe is stale relative to the Angel universe.

## Supplemental Angel-Only Analysis

An external HTML analysis file, `C:\Users\Surinder\Downloads\angel_only_symbols_analysis.html`, groups Angel-only symbols into four practical buckets:

| Category | Count |
| --- | ---: |
| Delisted / merged | 52 |
| New IPOs post-2021 | 67 |
| Renamed / rebranded | 18 |
| Needs manual review | 9 |
| Total in that analysis | 146 |

Examples and rationale from that file:

- Delisted or merged: `DHFL`, `JETAIRWAYS`, `RCOM`, `ALBK`, `CORPBANK`, `ANDHRABANK`, `SYNDIBANK`, `ORIENTBANK`, `MINDTREE`, `GRUH`.
- New IPOs post-2021: `SWIGGY`, `OLAELEC`, `HYUNDAI`, `PAYTM`, `NYKAA`, `POLICYBZR`, `DELHIVERY`, `IREDA`, `DOMS`, `SAGILITY`.
- Renamed or rebranded: `LTM`, `TMPV`, `ETERNAL`, `LTF`, `ABREL`, `JSWDULUX`, `GVT&D`.
- Needs manual review: `HDFC`, `BAJAJCON`, `BAJAJELEC`, `TATACOFFEE`, `L&TFH`, `GODREJAGRO`.

Important reconciliation note:

- The current regenerated CSV audit reports 193 `angel_only` symbols.
- The HTML analysis reports 146 total Angel-only symbols.
- Therefore the HTML appears to use a narrower or earlier filtered subset. Its category logic is useful, but its totals should not replace the current CSV-derived counts unless the filtering rule is recovered.

The HTML supports the main conclusion: the Angel-only population is not junk data. It contains a mix of new listings, current renamed symbols, corporate-action successors, and a smaller manual-review bucket.

Therefore:

- Angel is not missing broad market coverage.
- The research universe is not a reliable current NSE500 proxy.
- Symbol-string coverage understates practical research coverage.
- A refreshed universe and reviewed alias table are prerequisites before historical ETL.

## Recommended Next Research Steps

1. Build a non-production current NSE500 universe snapshot from an official or trusted source.
2. Compare that snapshot against Angel symbols directly.
3. Create an alias-review table with `research_symbol`, `angel_symbol`, `canonical_symbol`, `valid_from`, `valid_to`, and `review_status`.
4. Resolve high-confidence formatting cases first: `GET&D -> GVT&D`, `GEPIL -> GPIL`.
5. Resolve corporate-action lineage only with dates, not simple replacement.
6. Exclude symbols that are delisted, suspended, merged without clean continuity, or absent from Angel after review.

No historical backtest should be rerun until the universe and alias problem is separated from the Angel data-quality problem.
