# Swing Entry Quality Research

Date: 2026-06-11

## Objective

Determine whether entry-quality controls contribute more than factor-selection changes for the strongest Swing research model discovered so far:

**Sector Rank + ADX**

This is research only. No production scoring, recommendation generation, or backtest logic was modified.

## Inputs

- `reports/swing_top20_trade_ledger.csv`
- `reports/swing_entry_quality_research.json`
- `docs/SWING_V2.1_FINAL_VALIDATION.md`
- `docs/SWING_EXTENSION_RISK_ANALYSIS.md`
- `docs/EMA200_EXTENSION_ROBUSTNESS.md`

## Method

The existing Sector Rank + ADX Top 20 trade ledger was used as the base population.

Each trade was enriched at the signal date with:

- Close versus EMA50
- Close versus EMA200
- Distance above EMA50
- Distance above EMA200
- Prior 20-day return
- Prior 60-day return
- Distance versus 52-week high

Filters were then simulated directly on the existing research ledger. This means the test measures entry-quality gating on top of the same Sector Rank + ADX model, not a new scoring model.

## Baseline

| Model | Trade Count | Avg Return | Win Rate | Profit Factor | Alpha |
| --- | ---: | ---: | ---: | ---: | ---: |
| Current Sector Rank + ADX | 9,016 | 0.22% | 49.51% | 1.059 | 0.38% |

## Required Filter Tests

| Test | Filter | Trade Count | Avg Return | Win Rate | Profit Factor | Alpha |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Current | None | 9,016 | 0.22% | 49.51% | 1.059 | 0.38% |
| A | EMA200 extension <= 25% | 7,133 | 0.69% | 51.50% | 1.208 | 0.61% |
| B | Prior 20d return <= 15% | 6,170 | 0.48% | 51.08% | 1.141 | 0.47% |
| C | Prior 60d return <= 25% | 5,854 | 0.40% | 50.26% | 1.114 | 0.52% |
| D | EMA200 extension <= 25% AND Prior 20d return <= 15% | 5,663 | 0.71% | 52.02% | 1.219 | 0.54% |
| E | EMA200 extension <= 25% AND Prior 60d return <= 25% | 5,600 | 0.53% | 50.65% | 1.155 | 0.58% |
| F | EMA200 extension <= 25% AND Prior 20d return <= 15% AND Prior 60d return <= 25% | 4,718 | 0.57% | 51.05% | 1.173 | 0.49% |

## Supporting Entry-Quality Controls

| Filter | Trade Count | Avg Return | Win Rate | Profit Factor | Alpha |
| --- | ---: | ---: | ---: | ---: | ---: |
| Distance above EMA50 <= 10% | 5,414 | 0.60% | 51.56% | 1.180 | 0.43% |
| Not more than 5% above 52-week high | 4,695 | 0.68% | 51.58% | 1.200 | 0.83% |
| Not within 2% of 52-week high | 3,616 | 0.66% | 51.03% | 1.189 | 0.58% |

## Findings

Entry-quality controls materially improve the Sector Rank + ADX model.

The current Sector Rank + ADX model produced:

- Avg Return: 0.22%
- Win Rate: 49.51%
- Profit Factor: 1.059
- Alpha: 0.38%

The strongest all-around required filter was **Test D: EMA200 extension <= 25% AND Prior 20d return <= 15%**.

Test D produced:

- Avg Return: 0.71%
- Win Rate: 52.02%
- Profit Factor: 1.219
- Alpha: 0.54%

This is a meaningful improvement over the unfiltered Sector Rank + ADX model:

| Metric | Current | Test D | Change |
| --- | ---: | ---: | ---: |
| Avg Return | 0.22% | 0.71% | +0.49 percentage points |
| Win Rate | 49.51% | 52.02% | +2.51 percentage points |
| Profit Factor | 1.059 | 1.219 | +0.160 |
| Alpha | 0.38% | 0.54% | +0.16 percentage points |

## Factor Changes Versus Entry Controls

Prior Swing research showed that simplifying Swing V2 into the Sector Rank + ADX model improved performance versus broader factor mixes. However, after the core model was discovered, the incremental improvement from entry-quality filters was larger than the incremental improvement from later factor-selection refinements.

The clearest example:

- Sector Rank + ADX baseline Avg Return: 0.22%
- Sector Rank + ADX with Test D Avg Return: 0.71%
- Improvement from entry-quality gating: +0.49 percentage points

This suggests that, at the current stage of Swing research, **entry quality is contributing more incremental value than additional factor reshuffling**.

## Interpretation By Filter

### EMA200 Extension Cap

The EMA200 extension cap is the most important single required filter.

Test A improved every major metric:

- Avg Return increased from 0.22% to 0.69%
- Win Rate increased from 49.51% to 51.50%
- Profit Factor increased from 1.059 to 1.208
- Alpha increased from 0.38% to 0.61%

This confirms the earlier extension-risk finding: a strong sector and high ADX are not enough if the stock is already too extended above its long-term trend.

### Prior 20-Day Return Cap

The prior 20-day return cap also improved all major metrics.

It appears to reduce short-term exhaustion risk. The improvement is smaller than the EMA200 cap but still meaningful.

### Prior 60-Day Return Cap

The prior 60-day return cap improves alpha and profit factor but is weaker than the EMA200 and prior 20-day filters.

It may be useful as a secondary control, but the three-filter combination was not superior to the simpler two-filter combination.

### Distance Above EMA50

The EMA50 distance filter improves results, but it is less powerful than the EMA200 extension cap.

This suggests that excessive long-term extension is a more important failure mode than medium-term extension alone.

### Distance Above 52-Week High

The 52-week-high controls are promising.

The filter excluding trades more than 5% above the 52-week high produced:

- Avg Return: 0.68%
- Win Rate: 51.58%
- Profit Factor: 1.200
- Alpha: 0.83%

This had the strongest alpha of all tested filters, but it also reduced trade count materially. It should be treated as a promising research direction, not as a final rule yet.

## Best Filter By Metric

| Metric | Best Filter | Value |
| --- | --- | ---: |
| Avg Return | Test D: EMA200 <= 25% AND Prior 20d <= 15% | 0.71% |
| Win Rate | Test D: EMA200 <= 25% AND Prior 20d <= 15% | 52.02% |
| Profit Factor | Test D: EMA200 <= 25% AND Prior 20d <= 15% | 1.219 |
| Alpha | Not more than 5% above 52-week high | 0.83% |
| Trade Count Retention | Test A: EMA200 <= 25% | 7,133 trades |

## Risks

The entry-quality results are strong, but the following risks remain:

- The filters were tested on the same research sample used to discover the model.
- The 25% EMA200 threshold may still be sample-specific, although prior robustness research suggests the broad range is stable.
- 52-week-high controls need separate robustness testing before being promoted.
- Lower trade counts may increase sensitivity to period-specific market regimes.
- These tests use EOD data and next-trading-day open execution, not intraday confirmation.
- The filters may behave differently during sharp market recoveries, where extended leaders can keep running.

## Conclusion

Yes. Entry-quality controls appear to improve performance more than incremental factor-selection changes at this stage of Swing research.

The Sector Rank + ADX model remains the correct core model, but its losses are meaningfully reduced when obvious overextension is filtered out.

The strongest research candidate from this analysis is:

**Sector Rank + ADX + EMA200 extension <= 25% + Prior 20d return <= 15%**

This filter combination produced the best overall balance of return, win rate, profit factor, and trade count among the required tests.

## Recommendation

Do not create a new production model yet.

Recommended next research step:

1. Validate the EMA200 <= 25% and Prior 20d <= 15% combination across time-split periods.
2. Separately test 52-week-high controls for robustness.
3. Compare the best entry-quality filtered model against V1 Swing, Swing V2, and unfiltered Sector Rank + ADX.

If those results remain stable, the official Swing V2.1 candidate should likely be:

**Sector Rank + ADX with entry-quality guardrails**
