# Survivorship Bias Assessment

Date: 2026-06-11

## Objective

Assess whether current Swing research results may be materially affected by survivorship bias.

Scope reviewed:

- `symbol_master`
- `universe_snapshot`
- Recommendation generation
- Feature ranking universe
- Sector calculations
- Backtesting universe

This is research only. No code, scoring model, recommendation logic, or backtest logic was modified.

## Executive Verdict

Current Swing research has **HIGH survivorship-bias risk**.

The schema contains fields and tables that could support point-in-time universe handling, but the populated data and most production/research paths do not consistently enforce historical NSE500 membership.

The most important finding:

**The system currently behaves like it is using the present-day NSE500/symbol universe, not a true date-valid historical NSE500 universe.**

## Live Database Evidence

Current PostgreSQL snapshot:

| Table / Field | Count |
| --- | ---: |
| `symbol_master` rows | 502 |
| `symbol_master.nse500 = true` | 501 |
| `symbol_master.nse500_from_date IS NOT NULL` | 0 |
| `symbol_master.nse500_to_date IS NOT NULL` | 0 |
| `universe_snapshot` rows | 501 |
| Distinct `universe_snapshot.date` values | 1 |
| `prices_daily` rows | 214,990 |
| `features_daily` rows | 214,990 |
| `daily_scores` rows | 214,990 |
| `recommendation_history` rows | 23,800 |

Interpretation:

- `universe_snapshot` exists, but only one snapshot date is populated.
- `symbol_master` has no date-valid NSE500 membership ranges populated.
- Historical scoring and recommendations were generated over a universe that is effectively current/static.

## Schema Review

### SymbolMaster

`SymbolMaster` includes:

- `nse500`
- `nse500_from_date`
- `nse500_to_date`

This is enough to support date-valid membership in principle.

However, the live data has:

- 501 current NSE500 symbols
- 0 symbols with `nse500_from_date`
- 0 symbols with `nse500_to_date`

Therefore, historical entry and exit from the NSE500 is not represented in the current dataset.

### UniverseSnapshot

`UniverseSnapshot` exists with:

- `date`
- `symbol`
- `index_name`

This is the correct structure for point-in-time constituent snapshots.

However, the live database contains only one snapshot date. That means it cannot currently answer: "Was this stock in the NSE500 on this historical signal date?"

## Pipeline Review

## 1. Is The System Using Current NSE500 Membership Or Date-Valid Membership?

Mostly **current/static membership**.

Evidence:

- `app/ingestion/symbol_loader.py` writes current constituent records to `symbol_master` with `nse500=True`.
- It also writes `universe_snapshot`, but only for the provided `snapshot_date`.
- The live DB has one `universe_snapshot` date and no membership start/end dates.
- `app/sectors/compute_sector_strength.py` loads symbols using `SymbolMaster.nse500.is_(True)` without date-valid membership checks.
- `app/scoring/compute_scores.py` scores every row in `features_daily` for a date and does not join `universe_snapshot`.
- `app/recommendations/generate_recommendations.py` loads candidates from `daily_scores` joined to `features_daily`, filtered only by `is_eligible is not False`.

Partial exception:

- `app/indicators/compute_features.py` applies date-valid `symbol_master` checks inside `_apply_rs_rank_pct`.

But because `nse500_from_date` and `nse500_to_date` are not populated in the live DB, this does not currently provide a complete historical-membership solution.

Verdict: **Current/static membership dominates.**

## 2. Are Delisted Or Excluded Stocks Represented Historically?

No meaningful evidence that they are represented.

The live database has:

- 502 symbols total
- 501 marked as NSE500
- No populated `nse500_to_date`
- One `universe_snapshot` date

That means stocks that were historically in the NSE500 but later removed, delisted, merged, or otherwise excluded are likely absent unless they remain in the current symbol set.

This is the core survivorship-bias problem.

Verdict: **No, historical exclusions are not sufficiently represented.**

## 3. Are Recommendations Generated Only From Symbols That Survive To Present Day?

Likely yes.

Recommendation generation uses:

- `daily_scores`
- `features_daily`
- `features_daily.is_eligible`

It does not join:

- `universe_snapshot`
- `symbol_master` with historical `from/to` filters

Since `daily_scores` and `features_daily` were generated from the available `symbol_master` and price universe, recommendations inherit that universe. If the upstream universe is current/static, recommendations are effectively generated from present-surviving symbols.

Verdict: **Yes, current recommendations likely inherit present-day survivor bias.**

## 4. Does Sector Rank Inherit Survivorship Bias?

Yes.

Sector strength calculation uses:

`SymbolMaster.nse500.is_(True)`

It does not use:

- `universe_snapshot.date == current_date`
- `nse500_from_date <= current_date`
- `nse500_to_date >= current_date OR nse500_to_date IS NULL`

This means sector returns and ranks are computed from the currently flagged NSE500 names, not the historically valid sector constituents.

Because Swing V2 and the Sector Rank + ADX research depend heavily on `sector_daily.rank_3m`, survivorship bias in sector calculations can directly affect the strongest current Swing research model.

Verdict: **Yes, sector rank inherits survivorship bias.**

## 5. Does Benchmark Comparison Inherit Survivorship Bias?

Partially.

The benchmark price series itself does not have ordinary stock-level survivorship bias if it is an index price series such as NIFTY500. The index level already reflects index methodology at each date.

However, benchmark comparison can still inherit bias indirectly because:

- The model portfolio may be selected from a survivorship-biased stock universe.
- Alpha is calculated by comparing that biased portfolio to the benchmark.
- If failed historical constituents are missing, portfolio returns may be overstated relative to the benchmark.

Verdict: **Benchmark price data is lower risk, but benchmark-relative alpha inherits upstream portfolio bias.**

## Area Risk Ratings

| Area | Survivorship Bias Risk | Rationale |
| --- | --- | --- |
| Factor research | HIGH | `FactorAnalyzer.run()` queries `features_daily` by date without `universe_snapshot` or historical membership filtering. Missing failed/excluded stocks can inflate factor performance. |
| Recommendation research | HIGH | Recommendations are generated from `daily_scores` and `features_daily.is_eligible`, not point-in-time universe membership. |
| Backtesting | HIGH | Backtest consumes `recommendation_history`; it does not create bias itself, but fully inherits biased recommendations. |
| Sector analysis | HIGH | Sector strength uses current `nse500=True` symbols and does not use date-valid membership. Sector Rank + ADX therefore inherits bias. |

## Detailed Findings

### SymbolMaster

Risk: **HIGH**

The model supports historical membership fields, but the data does not populate them. With all `nse500_from_date` and `nse500_to_date` values missing, the table behaves as a current constituent list.

Impact:

- Historical backtests may exclude stocks that failed, were removed, or stopped trading.
- Current survivors may be treated as if they were valid throughout the full backtest period.
- Features and scores may exist for dates where a stock was not actually in the NSE500.

### UniverseSnapshot

Risk: **HIGH**

The table exists but is not sufficiently populated. One snapshot date is not enough for historical research.

Required behavior should be:

`universe_snapshot WHERE date = signal_date AND index_name = 'NSE500'`

Current behavior is closer to:

`current symbol list with nse500 = true`

### Feature Ranking Universe

Risk: **MEDIUM to HIGH**

The relative strength rank implementation has a partial date-valid filter in `_apply_rs_rank_pct`, but this depends on membership dates being populated.

Because the live membership dates are null, this protection is not currently reliable.

Also, the base feature-generation loop processes all symbols from `SymbolMaster`, not `universe_snapshot` membership by date.

### Recommendation Generation

Risk: **HIGH**

Recommendation generation does not enforce historical index membership. It filters out rows only when `is_eligible is False`.

`is_eligible` is a liquidity/tradability filter, not a historical NSE500 membership filter.

### Sector Calculations

Risk: **HIGH**

Sector ranks are central to current Swing research, especially the Sector Rank + ADX model.

Because sector calculation uses currently flagged NSE500 symbols, the sector return stream may be cleaner than reality:

- Failed constituents may be missing.
- Removed constituents may be missing.
- Sector averages may overweight survivors.
- Sector ranks may be different from true historical ranks.

This is material because sector rank is one of the two core factors in the leading Swing model.

### Backtesting Universe

Risk: **HIGH**

The backtester is not the primary source of survivorship bias. It simply tests recommendations already generated.

But because recommendations inherit upstream universe bias, backtest results are also biased.

The current backtest can answer:

"How did recommendations perform for the available current/static universe?"

It cannot yet answer:

"How would the model have performed using the true NSE500 constituents available at each historical date?"

## Materiality To Current Swing Research

Survivorship bias is likely material for current Swing results because the best model is:

**Sector Rank + ADX + entry-quality filters**

This model depends on:

- Stock-level features from the available symbol universe
- Sector ranks computed from the available symbol universe
- Recommendation ranking from the available scored universe
- Backtests from recommendations generated over that same universe

If historical losers, delisted stocks, or removed NSE500 constituents are missing, the model may look stronger than it would have in a true point-in-time test.

The bias could affect:

- Average return
- Win rate
- Profit factor
- Alpha
- Sector-rank predictive strength
- Entry-filter robustness

## Answers To Required Questions

| Question | Answer |
| --- | --- |
| Is the system using current NSE500 membership or date-valid membership? | Mostly current/static membership. Date-valid support exists in schema but is not populated/enforced consistently. |
| Are delisted/excluded stocks represented historically? | No meaningful evidence. Current data has no membership end dates and only one universe snapshot date. |
| Are recommendations generated only from symbols that survive to present day? | Likely yes, because recommendations inherit the current/static scored universe. |
| Does sector rank inherit survivorship bias? | Yes. Sector calculations use current `nse500=True` symbols, not point-in-time membership. |
| Does benchmark comparison inherit survivorship bias? | Indirectly yes. The benchmark price series is lower risk, but alpha inherits bias from the model portfolio universe. |

## Recommended Remediation

Before treating Swing V2.1 or entry-quality filtered results as production-grade, implement and validate point-in-time universe handling.

Required data remediation:

1. Populate historical `universe_snapshot` for every rebalance/signal date, or at least monthly NSE500 constituent snapshots.
2. Populate `symbol_master.nse500_from_date` and `symbol_master.nse500_to_date` where reliable.
3. Include historical removed/delisted constituents with prices up to their final trading dates.

Required code remediation:

1. Feature generation should restrict ranking universes by signal-date membership.
2. Sector strength should compute sector returns from date-valid constituents only.
3. Scoring should only score symbols valid for the signal date, or mark non-members as ineligible for ranking.
4. Recommendation generation should join point-in-time universe membership.
5. Factor research should filter observations to valid historical universe membership.
6. Backtest reports should include a flag indicating whether the run was point-in-time universe clean.

Required validation:

1. Count NSE500 members by date and verify realistic constituent counts.
2. Compare current/static results against point-in-time universe results.
3. Re-run Sector Rank + ADX research after universe correction.
4. Re-run entry-quality and time-split validation after universe correction.

## Final Assessment

| Research Output | Current Usefulness | Production Confidence |
| --- | --- | --- |
| Factor research | Useful for directional exploration | Not production-clean |
| Sector research | Useful but materially exposed | Not production-clean |
| Recommendation research | Useful for model discovery | Not production-clean |
| Swing backtests | Useful as provisional research | Not production-clean |

Overall survivorship-bias risk: **HIGH**

The current Swing research should be treated as **provisional** until point-in-time NSE500 membership and historical excluded constituents are incorporated.
