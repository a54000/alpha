# Research Freeze Summary

Date: 2026-06-11

## Objective

Freeze all completed Swing research before any further model development.

This document summarizes completed research only. It does not implement a model, modify scoring, create V2.1, or change recommendation logic.

## Current Leading Candidate

The current leading Swing research candidate is:

```text
Sector Rank
+
ADX
+
EMA200 Extension <= 25%
+
Prior 20d Return <= 15%
```

Short name:

**Sector Rank + ADX with entry-quality filters**

This is the leading research candidate, not a production-approved model.

## Executive Summary

V1 underperformed the benchmark and did not produce reliable score-ranking behavior. RS research remediated the implementation but found no predictive value, so RS should be removed from Swing scoring. Sector research found that `rank_3m` is useful when interpreted correctly: lower rank means stronger sector, and negative IC is favorable.

Swing V2 improved versus V1, but the strongest result came from simplifying the model. EMA and Volume were not supported as positive Swing scoring factors. BB Width helped in some combinations, but the minimum-factor model that preserved and improved performance was **Sector Rank + ADX**.

The next major improvement came from entry-quality controls, especially limiting extension above EMA200 and avoiding stocks with excessive prior 20-day gains. The best tested entry-quality combination was:

```text
EMA200 extension <= 25%
AND
Prior 20d return <= 15%
```

The candidate is promising across time splits and universe restrictions, but it remains exposed to serious caveats, especially survivorship bias.

## Research Timeline Summary

| Area | Final Research Finding | Status |
| --- | --- | --- |
| V1 baseline | Swing and Positional V1 underperformed benchmark | Validated |
| RS research | Corrected RS features still had no predictive power | Validated |
| Sector factor research | Sector `rank_3m` is useful; lower rank is stronger | Validated with direction caveat |
| Swing V2 | Improved versus V1 but still weak on absolute return | Validated |
| Contribution analysis | Sector Rank strongest V2 contributor; EMA/Volume weak | Validated |
| Factor pruning | Removing EMA and Volume improved Swing V2 | Validated |
| Core model validation | Sector Rank + ADX was best minimum-factor model | Validated |
| Extension risk | Excessive extension above EMA200 harmed performance | Validated |
| Entry quality | EMA200 cap + prior 20d cap improved the model | Validated, needs out-of-sample |
| Time split | Return/PF improved in all thirds; alpha not all periods | Tentative-positive |
| Universe sensitivity | Top100 liquidity proxy performed best | Tentative |
| Survivorship bias | Current research has HIGH survivorship-bias risk | Validated risk |

## V1 Findings

V1 is the frozen baseline.

Key findings:

- Swing V1 20-day return: `-0.5329%`
- Swing V1 win rate: `43.43%`
- Swing V1 profit factor: `0.8850`
- Swing V1 alpha: `-0.1948%`
- V1 score buckets did not show reliable monotonic performance.
- V1 contained weak factors that later research did not support.

V1 was useful as infrastructure and as a baseline, but not as a production-quality alpha model.

## RS Research Findings

RS implementation was remediated:

- Correct benchmark infrastructure was added.
- RS was changed from absolute return behavior to true relative-strength logic.
- `rs_rank_pct` ranking was corrected for the NSE500 universe path.

However, corrected RS failed predictive tests:

- Spearman IC remained near zero.
- Top RS buckets did not consistently outperform.
- Success criteria failed across horizons.

Final RS verdict:

**REMOVE from Swing scoring.**

RS infrastructure may remain useful for future diagnostics, but current RS factors should not drive Swing model selection.

## Sector Factor Findings

Sector factor research showed that sector leadership matters, especially `rank_3m`.

Important directionality:

- `rank_3m` is ordinal.
- Lower rank is stronger.
- `bucket_1` contains strongest sectors for `rank_3m`.
- Negative Spearman IC for `rank_3m` is favorable.

`rank_3m` showed favorable negative IC across tested horizons:

- 5d: `-0.0347`
- 10d: `-0.0523`
- 20d: `-0.0683`
- 60d: `-0.0310`

Raw sector return factors were less straightforward and often suggested mean reversion rather than simple trailing-return momentum.

Validated conclusion:

**Sector Rank is one of the strongest supported Swing research inputs.**

## Swing V2 Findings

Swing V2 improved versus V1 but was not the final answer.

| Model | Trades | Avg Return | Win Rate | Profit Factor | Alpha |
| --- | ---: | ---: | ---: | ---: | ---: |
| V1 Swing | 2,045 | -0.5329% | 43.43% | 0.8850 | -0.1948% |
| Swing V2 | 7,189 | -0.0987% | 46.83% | 0.9767 | 0.1762% |

Swing V2 improved:

- average return
- win rate
- profit factor
- alpha
- trade coverage

But Swing V2 still had negative absolute average return and sub-1 profit factor. It was a bridge toward better factor selection, not the final model.

## Contribution Analysis

Leave-one-factor-group-out tests found:

| Factor Group | Research Finding |
| --- | --- |
| Sector Rank | Strongest positive contributor |
| BB Width | Modest positive contributor in V2, especially alpha |
| ADX | Mixed alone, but important for alpha and later core model |
| Volume | Drag on absolute performance |
| EMA | Drag in current Swing V2 form |

Interpretation:

Swing V2 improved mostly because it removed weak V1 factors and added Sector Rank. Volume and EMA did not deserve to remain as positive Swing scoring components.

## Factor Pruning Analysis

Direct pruning confirmed that EMA and Volume hurt the current Swing V2 implementation.

| Model | Avg Return | Win Rate | Profit Factor | Alpha |
| --- | ---: | ---: | ---: | ---: |
| Current Swing V2 | -0.0987% | 46.83% | 0.9767 | 0.1762% |
| Minus EMA | 0.0425% | 47.92% | 1.0104 | 0.2140% |
| Minus Volume | 0.0646% | 48.81% | 1.0158 | 0.1276% |
| Minus EMA and Volume | 0.1484% | 49.00% | 1.0377 | 0.2056% |

Validated conclusion:

**Remove EMA and Volume from Swing scoring in the next approved design.**

## Core Model Validation

The core validation tested multiple simplified variants.

| Variant | Avg Return | Win Rate | Profit Factor | Alpha |
| --- | ---: | ---: | ---: | ---: |
| Current Swing V2 | -0.0987% | 46.83% | 0.9767 | 0.1762% |
| Sector Rank + BB Width + ADX | 0.1484% | 49.00% | 1.0377 | 0.2056% |
| Sector Rank + BB Width | 0.0487% | 47.90% | 1.0124 | 0.0958% |
| Sector Rank + ADX | 0.2216% | 49.51% | 1.0590 | 0.3936% |
| BB Width + ADX | 0.2186% | 48.63% | 1.0554 | 0.2715% |

Validated conclusion:

**Sector Rank + ADX is the best minimum-factor Swing model discovered so far.**

BB Width remains interesting, but it is not required in the leading model. It may be revisited later as a capped filter or non-linear condition.

## Extension Risk Research

The Sector Rank + ADX model still produced large losers. Extension research found that losses were often linked to entering already-extended stocks.

Important findings:

- Stocks more than 30% above EMA200 performed poorly.
- Prior 60-day gains above 30-40% were risky.
- EMA200 extension was the clearest simple risk signal.

EMA200 cap sweep:

| EMA200 Cap | Avg Return | Win Rate | Profit Factor | Alpha |
| --- | ---: | ---: | ---: | ---: |
| No cap | 0.22% | 49.51% | 1.059 | 0.38% |
| <= 20% | 0.68% | 51.55% | 1.204 | 0.48% |
| <= 25% | 0.69% | 51.50% | 1.208 | 0.61% |
| <= 30% | 0.68% | 51.40% | 1.201 | 0.66% |

Validated conclusion:

**EMA200 extension control is robust across a 20-30% range.**

The current best balance point is `<= 25%`.

## Entry Quality Research

Entry-quality controls improved the Sector Rank + ADX model more than further factor reshuffling.

| Model / Filter | Trades | Avg Return | Win Rate | Profit Factor | Alpha |
| --- | ---: | ---: | ---: | ---: | ---: |
| Sector Rank + ADX | 9,016 | 0.22% | 49.51% | 1.059 | 0.38% |
| EMA200 <= 25% | 7,133 | 0.69% | 51.50% | 1.208 | 0.61% |
| Prior 20d <= 15% | 6,170 | 0.48% | 51.08% | 1.141 | 0.47% |
| EMA200 <= 25% and Prior 20d <= 15% | 5,663 | 0.71% | 52.02% | 1.219 | 0.54% |

Validated conclusion:

**The strongest all-around entry-quality candidate is EMA200 extension <= 25% plus prior 20d return <= 15%.**

## Time-Split Validation

The leading entry-filtered candidate improved across major time periods on trade-level metrics.

| Period | Baseline Avg Return | Filtered Avg Return | Baseline PF | Filtered PF | Alpha Change |
| --- | ---: | ---: | ---: | ---: | ---: |
| Period A | -1.82% | -1.35% | 0.633 | 0.693 | +0.16 pp |
| Period B | 1.26% | 2.07% | 1.436 | 1.848 | +0.51 pp |
| Period C | 1.51% | 2.21% | 1.457 | 1.893 | -0.17 pp |

Rolling six-month validation:

- Avg return improved in `22 / 22` windows.
- Profit factor improved in `21 / 22` windows.
- Alpha improved in `16 / 22` windows.

Tentative conclusion:

The entry-quality candidate is broadly stable on average return and profit factor, but alpha is not uniformly improved. The final period alpha decline remains an open caveat.

## Universe Sensitivity Findings

Universe sensitivity tested the leading candidate across liquidity/size-restricted universes.

Important limitation:

True market cap is not available in the implemented database. The test used average traded value as a liquidity/size proxy.

| Universe | Trades | Avg Return | Win Rate | Profit Factor | Alpha | Unique Symbols |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| NSE500 proxy | 6,868 | 0.29% | 50.09% | 1.087 | 0.36% | 372 |
| Top300 liquidity proxy | 6,384 | 0.52% | 51.47% | 1.164 | 0.53% | 289 |
| Top200 liquidity proxy | 5,275 | 0.63% | 52.75% | 1.204 | 0.34% | 196 |
| Top100 liquidity proxy | 3,594 | 1.33% | 55.52% | 1.500 | 0.53% | 100 |

Tentative conclusion:

Performance improves as the tradable universe is restricted toward larger/more liquid names. Top100 is strongest, but diversification and sector concentration worsen.

Top100 caveat:

- Top 5 sector share rises to `70.76%`.
- Financial Services alone reaches `28.35%`.
- It uses a liquidity proxy, not true market cap.

## Survivorship Bias Assessment

Survivorship-bias risk is **HIGH**.

Live database evidence:

- `symbol_master`: 502 symbols
- `nse500 = true`: 501 symbols
- `nse500_from_date IS NOT NULL`: 0
- `nse500_to_date IS NOT NULL`: 0
- `universe_snapshot`: 501 rows
- distinct `universe_snapshot.date`: 1

Implications:

- Historical NSE500 membership is not point-in-time clean.
- Delisted or removed constituents are likely missing.
- Recommendation research inherits current/static universe bias.
- Sector rank likely inherits survivorship bias.
- Backtest alpha inherits upstream portfolio-universe bias.

Validated risk:

**Current Swing research is provisional until point-in-time universe correction is implemented.**

## Validated Findings

- V1 Swing underperforms and should not be promoted.
- Corrected RS features do not provide useful Swing predictive power.
- Sector `rank_3m` has predictive value when interpreted inversely.
- Swing V2 improves versus V1 but remains too weak.
- Sector Rank is the clearest positive Swing V2 factor.
- EMA and Volume are not supported as positive Swing V2 scoring factors.
- Sector Rank + ADX is the best minimum-factor Swing model found so far.
- Excessive extension above EMA200 is a real risk.
- EMA200 extension cap has robust support across the 20-30% range.
- Prior 20d return cap improves entry quality.
- The leading entry-filtered candidate improves average return and profit factor across all three time splits.
- Survivorship-bias risk is high and must be addressed before production confidence.

## Tentative Findings

- Top100 liquidity/size universe may be superior to the broader NSE500 universe.
- Top300 may be a more diversified fallback if Top100 concentration is unacceptable.
- 52-week-high controls may add alpha, but require separate robustness testing.
- BB Width may be useful as a bounded filter or moderate-range signal, even though it is not part of the leading model.
- The entry-quality model may be production-worthy after point-in-time universe correction and forward out-of-sample validation.

## Invalidated Findings

- V1 composite Swing scoring is not a reliable alpha model.
- RS should not remain as a positive Swing scoring factor.
- Current EMA short-term alignment should not remain as a positive Swing V2 scoring factor.
- Current Volume ratio scoring should not remain as a positive Swing V2 scoring factor.
- BB Width is not required for the best current Swing model.
- Raw sector trailing returns should not be treated as simple bullish momentum without direction-specific interpretation.
- Same-day-close entry backtests are invalid as tradable execution results; next-day-open entry is required and has been remediated.

## Open Questions

1. How much performance remains after point-in-time NSE500 membership correction?
2. How much performance remains after adding historical removed/delisted constituents?
3. Does Top100 still win when true market cap replaces average traded value?
4. Does Top100 remain stable across time splits, or is it concentrated in one period?
5. Can sector concentration caps preserve Top100 performance while reducing crowding?
6. Why does alpha weaken in the final time split despite better raw return and profit factor?
7. Should 52-week-high controls be added after a separate robustness test?
8. How does the candidate perform after transaction costs, slippage, and realistic execution friction?
9. Does intraday data improve or weaken the EOD-derived edge?
10. Can dynamic exits improve the large-loser profile without reducing winners too much?

## Known Caveats

- Survivorship bias is high.
- Universe is current/static, not true point-in-time NSE500.
- Market-cap data is not implemented; universe sensitivity used average traded value as proxy.
- Transaction costs are not included in the research metrics.
- Slippage, brokerage, STT, and stamp duty are not included.
- Exit logic is fixed horizon only.
- No stop-loss, target, trailing stop, or rank-decay exit is modeled.
- All research is based on EOD data.
- The filters were selected and tested within the same broad historical sample.
- Forward out-of-sample validation has not yet occurred.
- Sector rank is itself exposed to survivorship bias.
- Top100 results have higher sector concentration.
- Alpha improvement is not uniform across all time splits.
- Some rolling windows are partial near the end of available data.

## Frozen Candidate Definition

Until the next approved research phase, freeze the current Swing candidate as:

```text
Core factors:
- Sector Rank
- ADX

Entry filters:
- EMA200 extension <= 25%
- Prior 20d return <= 15%

Execution assumption:
- Signal after EOD close
- Entry at next-trading-day open
- Exit at fixed 20-trading-day close
- Benchmark matched to same entry/exit dates
```

## Freeze Decision

Research is frozen at:

**Sector Rank + ADX + EMA200 extension <= 25% + Prior 20d return <= 15%**

This candidate is the current leader, but the correct status is:

```text
Research leader, not production-approved.
```

No further model development should proceed until the next phase explicitly addresses:

1. point-in-time universe correction,
2. survivorship-bias remediation,
3. true market-cap or approved liquidity-universe definition,
4. transaction-cost assumptions,
5. out-of-sample validation.
