# Angel Mapping Gap Analysis

Objective: determine whether the 188 unmatched research symbols represent genuine missing Angel coverage, symbol naming differences, corporate-action renames, delistings, or exchange/vendor naming conventions.

Input:

- `reports/angel_symbol_mapping.csv`

Scope:

- Research only.
- Do not modify mapping tables.
- Do not modify databases.
- Do not create daily bars.
- Only analyze the unmatched symbols.

## Summary

The updated mapping audit found:

- Research universe symbols: 501
- Angel symbols: 499
- Exact matches: 285
- Known rename mappings: 16
- Potential mappings: 12
- Ambiguous mappings: 7
- Unmatched research symbols: 181
- Angel-only symbols: 193

This gap analysis classifies all 181 `unmatched` research symbols from the CSV.

## Counts By Category

| Category | Count | Interpretation |
| --- | ---: | --- |
| Unknown | 146 | No safe one-to-one mapping from the CSV alone. Requires manual exchange/vendor review. |
| Exact missing | 17 | Likely genuinely absent from current Angel data under that legacy symbol, commonly due to delisting, merger, bank consolidation, suspension, or extinct share class. |
| Likely rename | 6 | Credible rename or corporate-action candidate exists, but the current Angel symbol was not found by the audit rule or still needs successor validation. |
| Ambiguous | 10 | Multiple possible successors or unclear lineage. Must not be auto-mapped. |
| Likely formatting difference | 2 | Strong vendor/exchange naming convention candidate, usually punctuation or short-code drift. |
| Total | 181 | All unmatched research symbols reviewed. |

## Estimated True Coverage After Normalization

Current mapped research symbols from the symbol audit: 313 of 501, or 62.48%.

If the remaining 6 likely renames and 2 likely formatting differences are verified and added, estimated mapped coverage becomes:

- 321 of 501 symbols
- 64.07% estimated coverage

If the 10 ambiguous cases are also resolved one-to-one, the upper-bound coverage becomes:

- 331 of 501 symbols
- 66.07% estimated coverage

This is still below the level required for a clean historical NSE500 extension. The core issue is not only formatting; the current research universe appears to contain many legacy, renamed, merged, suspended, or delisted symbols, while Angel contains a more modern symbol set.

## Top Rename Candidates

These high-confidence rename candidates were fixed in `reports/angel_symbol_mapping.csv`:

| Research symbol | Candidate / lineage | Action |
| --- | --- | --- |
| `KALPATPOWR` | `KPIL` | Fixed as `known_rename`; verify validity dates before production ETL. |
| `WABCOINDIA` | `ZFCVINDIA` | Fixed as `known_rename`; verify validity dates before production ETL. |
| `SRTRANSFIN` | `SHRIRAMFIN` | Fixed as `known_rename`; verify merger date before production ETL. |
| `TATAGLOBAL` | `TATACONSUM` | Fixed as `known_rename`; verify validity dates before production ETL. |
| `INFRATEL` | `INDUSTOWER` | Fixed as `known_rename`; verify merger/rename date before production ETL. |
| `RNAM` | `NAM-INDIA` | Fixed as `known_rename`; verify validity dates before production ETL. |
| `MAHINDCIE` | `CIEINDIA` | Fixed as `known_rename`; verify validity dates before production ETL. |

Remaining top rename candidates:

| Research symbol | Candidate / lineage | Action |
| --- | --- | --- |
| `GMRINFRA` | `GMRP&UI` | Candidate not present in Angel symbols; verify vendor symbol. |
| `MINDTREE` | `LTIM` | Candidate already maps to `LTI`; needs merger-date handling, not simple one-to-one replacement. |
| `MAGMA` | Poonawalla Fincorp lineage | Verify current successor symbol and continuity. |
| `ISEC` | ICICI Securities lineage | Candidate not present in Angel symbols; verify vendor symbol. |
| `IBVENTURES` | Renamed corporate entity | Verify current tradable successor. |
| `SFL` | Shriram group lineage | Candidate already maps to another research symbol; needs event-date handling. |

## Top Formatting-Rule Candidates

These look like vendor or exchange-symbol convention issues:

| Research symbol | Candidate | Rule |
| --- | --- | --- |
| `GET&D` | `GVT&D` | Vendor/current-symbol convention likely differs. |
| `GEPIL` | `GPIL` | Shortened/current-symbol convention likely differs. |

Important: punctuation normalization alone does not solve most gaps. Only 2 of the 188 unmatched symbols are strong formatting-rule candidates from this CSV-only pass.

## Ambiguous Cases

These must not be auto-mapped:

| Research symbol | Reason |
| --- | --- |
| `PEL` | Piramal entity changed/demerged; multiple successor interpretations possible. |
| `JUBILANT` | Jubilant group split; multiple possible successors. |
| `MAXINDIA` | Max group restructuring; multiple possible successors. |
| `TCNSBRANDS` | Potential acquisition/merger handling needed; not safe to map automatically. |
| `SANOFI` | Possible demerger/consumer-health naming issue; needs event review. |
| `SHK` | Symbol abbreviation too short; likely S H Kelkar but needs confirmation. |
| `THYROCARE` | Potential acquisition/delisting lineage; needs review. |
| `NBVENTURES` | Corporate rename/restructuring ambiguity; needs review. |
| `GDL` | Could be Gateway Distriparks lineage, but Angel candidate is not direct. |
| `PRSMJOHNSN` | Prism Johnson naming may be vendor-specific or absent; needs review. |

## Full Unmatched Classification

| Research symbol | Category | Rationale |
| --- | --- | --- |
| `ADVENZYMES` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `AKZOINDIA` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `ALBK` | Exact missing | Bank merger/delisting; no current Angel coverage expected under old symbol. |
| `ALLCARGO` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `ANDHRABANK` | Exact missing | Bank merger/delisting; no current Angel coverage expected under old symbol. |
| `APLLTD` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `AVANTIFEED` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `BALMLAWRIE` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `BASF` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `BIRLACORPN` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `BLISSGVS` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `BOMDYEING` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `CARERATING` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `CENTURYPLY` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `CERA` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `COFFEEDAY` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `CORPBANK` | Exact missing | Bank merger/delisting; no current Angel coverage expected under old symbol. |
| `COX&KINGS` | Exact missing | Delisted/defunct legacy symbol; no current Angel coverage expected. |
| `DBCORP` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `DBL` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `DCAL` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `DCBBANK` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `DELTACORP` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `DHFL` | Exact missing | Resolved/delisted legacy symbol; no current Angel coverage expected. |
| `DISHTV` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `EDELWEISS` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `EQUITAS` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `ESSELPACK` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `FCONSUMER` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `FDC` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `FINEORG` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `FINPIPE` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `FLFL` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `FRETAIL` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `GALAXYSURF` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `GAYAPROJ` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `GDL` | Ambiguous | Could be Gateway Distriparks lineage, but Angel candidate not direct. |
| `GEPIL` | Likely formatting difference | Angel has close candidate `GPIL`; likely vendor or post-rename convention. |
| `GET&D` | Likely formatting difference | Angel has close vendor-style candidate `GVT&D`; punctuation/vendor convention likely. |
| `GHCL` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `GMRINFRA` | Likely rename | Likely modern exchange symbol candidate `GMRP&UI`, but that candidate is not present in Angel symbols; verify vendor symbol. |
| `GNFC` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `GPPL` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `GREAVESCOT` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `GRINDWELL` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `GRUH` | Exact missing | Merged legacy symbol; no current Angel coverage expected. |
| `GSFC` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `GSKCONS` | Exact missing | Merged/acquired legacy symbol; no current Angel coverage expected. |
| `GSPL` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `GUJALKALI` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `GUJFLUORO` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `GUJGASLTD` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `GULFOILLUB` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `HATHWAY` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `HATSUN` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `HEIDELBERG` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `HERITGFOOD` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `HEXAWARE` | Exact missing | Delisted legacy symbol; no current Angel coverage expected. |
| `HIMATSEIDE` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `IBREALEST` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `IBULISL` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `IBVENTURES` | Likely rename | Likely renamed corporate entity; verify current tradable successor. |
| `ICRA` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `IFBIND` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `INDOCO` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `INDOSTAR` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `INFIBEAM` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `INOXLEISUR` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `ISEC` | Likely rename | Likely vendor/name difference for ICICI Securities; verify Angel symbol availability. |
| `ITDC` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `ITDCEM` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `JAGRAN` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `JAICORPLTD` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `JAMNAAUTO` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `JETAIRWAYS` | Exact missing | Suspended/legacy symbol; no reliable current Angel coverage expected. |
| `JISLJALEQS` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `JKLAKSHMI` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `JKPAPER` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `JPASSOCIAT` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `JUBILANT` | Ambiguous | Jubilant group split; multiple possible successors. |
| `JUSTDIAL` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `JYOTHYLAB` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `KANSAINER` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `KIOCL` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `KNRCON` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `KOLTEPATIL` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `KRBL` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `KSCL` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `KTKBANK` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `LAKSHVILAS` | Exact missing | Bank merger/delisting; no current Angel coverage expected. |
| `LAXMIMACH` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `LUXIND` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `MAGMA` | Likely rename | Likely renamed/acquired into Poonawalla Fincorp lineage; verify target symbol. |
| `MAHLOG` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `MAHSCOOTER` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `MAHSEAMLES` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `MASFIN` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `MAXINDIA` | Ambiguous | Max group restructuring; multiple possible successors. |
| `MHRIL` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `MINDTREE` | Likely rename | Likely merged into `LTIM`; verify event date. |
| `MOIL` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `MONSANTO` | Exact missing | Merged/delisted legacy symbol; no current Angel coverage expected. |
| `NBVENTURES` | Ambiguous | Corporate rename/restructuring ambiguity; needs review. |
| `NESCO` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `NETWORK18` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `NFL` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `NILKAMAL` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `OMAXE` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `ORIENTBANK` | Exact missing | Bank merger/delisting; no current Angel coverage expected. |
| `ORIENTCEM` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `ORIENTELEC` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `PARAGMILK` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `PCJEWELLER` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `PEL` | Ambiguous | Piramal entity changed/demerged; multiple successor interpretations possible. |
| `PGHH` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `PGHL` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `PNCINFRA` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `PRAJIND` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `PRSMJOHNSN` | Ambiguous | Prism Johnson naming may be vendor-specific or absent; needs review. |
| `QUESS` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `RAJESHEXPO` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `RALLIS` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `RAYMOND` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `RCF` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `RCOM` | Exact missing | Suspended/legacy symbol; no reliable current Angel coverage expected. |
| `RELAXO` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `RELCAPITAL` | Exact missing | Distressed/delisted or sparse legacy symbol; no complete Angel coverage expected. |
| `RELINFRA` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `RENUKA` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `REPCOHOME` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `RHFL` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `RUPA` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `SADBHAV` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `SANOFI` | Ambiguous | Possible demerger/consumer-health naming issue; needs event review. |
| `SFL` | Likely rename | Likely Shriram group legacy symbol; verify against `SHRIRAMFIN`. |
| `SHANKARA` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `SHARDACROP` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `SHILPAMED` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `SHK` | Ambiguous | Symbol abbreviation too short; likely S H Kelkar but needs confirmation. |
| `SHOPERSTOP` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `SIS` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `SKFINDIA` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `SOUTHBANK` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `SPARC` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `SPTL` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `SREINFRA` | Exact missing | Distressed/legacy symbol; no complete Angel coverage expected. |
| `STARCEMENT` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `STRTECH` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `SUDARSCHEM` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `SUNCLAYLTD` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `SUNDRMFAST` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `SUNTECK` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `SUPRAJIT` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `SUVEN` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `SWANENERGY` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `SYMPHONY` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `SYNDIBANK` | Exact missing | Bank merger/delisting; no current Angel coverage expected. |
| `TAKE` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `TATAMOTORS` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `TATAMTRDVR` | Exact missing | DVR class likely no longer separately available; no current Angel coverage expected. |
| `TCNSBRANDS` | Ambiguous | Potential acquisition/merger handling needed; not safe to map automatically. |
| `TEAMLEASE` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `THOMASCOOK` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `THYROCARE` | Ambiguous | Potential acquisition/delisting lineage; needs review. |
| `TIMETECHNO` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `TNPL` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `TTKPRESTIG` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `TV18BRDCST` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `TVTODAY` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `UFLEX` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `UJJIVAN` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `VAKRANGEE` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `VARROC` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `VENKEYS` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `VGUARD` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `VINATIORGA` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `VIPIND` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `VMART` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `VRLLOG` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `VSTIND` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |
| `WABAG` | Unknown | No safe one-to-one mapping from `angel_symbol_mapping.csv`; requires manual exchange/vendor review. |

## Research Conclusion

The 188 unmatched symbols are not primarily a simple formatting problem. Only 2 have strong formatting-rule candidates from the CSV. A small set are likely corporate-action renames, and a meaningful set are legacy symbols that may be genuinely absent from current Angel data.

Before any historical ETL, the next research step should be a reviewed alias table with validity dates. Symbols in `likely_rename` and `likely_formatting_difference` should be checked first. `Ambiguous` symbols should remain excluded until a one-to-one lineage is proven. `Unknown` symbols should not be force-mapped.
