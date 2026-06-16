# Swing Time Split Validation

Date: 2026-06-11

## Objective

Validate whether the best Swing entry-quality model is stable across different market periods.

Core model:

**Sector Rank + ADX**

Entry filters:

- EMA200 extension <= 25%
- Prior 20d return <= 15%

This is research only. No production scoring, recommendation generation, or backtest logic was modified.

## Artifacts

- Source ledger: `reports/swing_top20_trade_ledger.csv`
- Output data: `reports/swing_time_split_validation.json`

## Method

The existing Sector Rank + ADX Top20 trade ledger was used as the base population.

The filtered model was simulated by applying the two entry-quality filters to the existing ledger:

- `close / ema_200 - 1 <= 25%`
- `prior_20d_return <= 15%`

The backtest history was split by chronological signal dates into three equal date-count periods:

| Period | Dates |
| --- | --- |
| Period A | 2024-07-08 to 2025-02-20 |
| Period B | 2025-02-21 to 2025-10-15 |
| Period C | 2025-10-16 to 2026-06-09 |

Rolling six-month windows were also computed by signal date. The final rolling windows are partial because the available ledger ends on 2026-06-09.

## Important Note

In this research artifact, `Current Top20 baseline` and `Sector Rank + ADX` refer to the same generated Sector Rank + ADX Top20 trade ledger.

This means the main comparison is:

**Sector Rank + ADX without entry filters vs Sector Rank + ADX with entry filters**

## Overall Results

| Model | Trade Count | Avg Return | Win Rate | Profit Factor | Alpha |
| --- | ---: | ---: | ---: | ---: | ---: |
| Current Top20 baseline | 9,016 | 0.22% | 49.51% | 1.059 | 0.38% |
| Sector Rank + ADX | 9,016 | 0.22% | 49.51% | 1.059 | 0.38% |
| Sector Rank + ADX + Entry Filters | 5,663 | 0.71% | 52.02% | 1.219 | 0.54% |

The entry filters reduced trade count by about 37%, but improved every major overall metric.

## Period A

2024-07-08 to 2025-02-20

| Model | Trade Count | Avg Return | Win Rate | Profit Factor | Alpha |
| --- | ---: | ---: | ---: | ---: | ---: |
| Current Top20 baseline | 3,117 | -1.82% | 40.65% | 0.633 | -0.19% |
| Sector Rank + ADX | 3,117 | -1.82% | 40.65% | 0.633 | -0.19% |
| Sector Rank + ADX + Entry Filters | 2,267 | -1.35% | 42.35% | 0.693 | -0.03% |

Period A remained negative, but the entry filters reduced the loss.

| Metric | Improvement |
| --- | ---: |
| Avg Return | +0.47 percentage points |
| Win Rate | +1.70 percentage points |
| Profit Factor | +0.061 |
| Alpha | +0.16 percentage points |

## Period B

2025-02-21 to 2025-10-15

| Model | Trade Count | Avg Return | Win Rate | Profit Factor | Alpha |
| --- | ---: | ---: | ---: | ---: | ---: |
| Current Top20 baseline | 2,889 | 1.26% | 54.45% | 1.436 | -0.41% |
| Sector Rank + ADX | 2,889 | 1.26% | 54.45% | 1.436 | -0.41% |
| Sector Rank + ADX + Entry Filters | 1,668 | 2.07% | 58.15% | 1.848 | 0.10% |

Period B was the cleanest validation period. Entry filters improved return, win rate, profit factor, and alpha.

| Metric | Improvement |
| --- | ---: |
| Avg Return | +0.81 percentage points |
| Win Rate | +3.71 percentage points |
| Profit Factor | +0.412 |
| Alpha | +0.51 percentage points |

## Period C

2025-10-16 to 2026-06-09

| Model | Trade Count | Avg Return | Win Rate | Profit Factor | Alpha |
| --- | ---: | ---: | ---: | ---: | ---: |
| Current Top20 baseline | 3,010 | 1.51% | 54.62% | 1.457 | 2.03% |
| Sector Rank + ADX | 3,010 | 1.51% | 54.62% | 1.457 | 2.03% |
| Sector Rank + ADX + Entry Filters | 1,728 | 2.21% | 59.36% | 1.893 | 1.85% |

Period C improved on absolute return, win rate, and profit factor, but alpha was slightly lower.

| Metric | Improvement |
| --- | ---: |
| Avg Return | +0.70 percentage points |
| Win Rate | +4.74 percentage points |
| Profit Factor | +0.436 |
| Alpha | -0.17 percentage points |

This is the main caveat in the validation. The filter did not make the model worse on trade performance, but in the final third it gave up some benchmark-relative alpha.

## Rolling Six-Month Validation

Rolling six-month windows were computed by signal date.

| Rolling Test | Result |
| --- | ---: |
| Windows evaluated | 22 |
| Avg return improved | 22 / 22 |
| Profit factor improved | 21 / 22 |
| Alpha improved | 16 / 22 |

Worst rolling-window deltas:

| Metric | Window | Delta |
| --- | --- | ---: |
| Avg Return | 2025-01-01 to 2025-06-30 | +0.00 percentage points |
| Profit Factor | 2025-01-01 to 2025-06-30 | -0.001 |
| Alpha | 2026-03-01 to 2026-08-31 | -0.75 percentage points |

Best rolling-window deltas:

| Metric | Window | Delta |
| --- | --- | ---: |
| Avg Return | 2026-04-01 to 2026-09-30 | +4.53 percentage points |
| Profit Factor | 2026-04-01 to 2026-09-30 | +62.037 |
| Alpha | 2025-06-01 to 2025-11-30 | +0.60 percentage points |

The very large profit-factor improvement in the 2026-04 window should be treated carefully because it is a partial trailing window with fewer filtered trades.

## Stability Assessment

### Does Improvement Exist In All Periods?

Yes for:

- Avg Return
- Win Rate
- Profit Factor

Not fully for:

- Alpha

Alpha improved in Period A and Period B, but declined slightly in Period C.

### Is Improvement Concentrated In One Regime?

No. The improvement is not concentrated in only one period.

The filtered model improved average return in all three periods:

- Period A: +0.47 percentage points
- Period B: +0.81 percentage points
- Period C: +0.70 percentage points

The strongest absolute model performance occurred in Period C, but the filter also helped during the weak Period A regime.

### Does Any Period Become Materially Worse?

No period became materially worse on trade-level performance.

The only deterioration was benchmark-relative alpha in Period C:

- Unfiltered alpha: 2.03%
- Filtered alpha: 1.85%
- Change: -0.17 percentage points

Because return, win rate, and profit factor all improved in Period C, this is not a direct model-quality failure. It suggests the filtered basket may have lagged the benchmark basket during a favorable benchmark regime.

## Production Readiness Interpretation

The entry-quality filters are robust enough for serious production consideration, but not yet enough for immediate promotion.

Evidence supporting robustness:

- Average return improved in all three time periods.
- Profit factor improved in all three time periods.
- Rolling six-month average return improved in 22 of 22 evaluated windows.
- Rolling six-month profit factor improved in 21 of 22 evaluated windows.
- The weak early period remained weak, but losses were reduced.

Evidence requiring caution:

- Alpha improved in only 2 of 3 major periods.
- Rolling six-month alpha improved in 16 of 22 windows, not all windows.
- The final period had lower alpha despite better raw trade performance.
- The filtered model cuts trade count materially, which may increase portfolio concentration.
- The filters were selected from the same broad research cycle, so out-of-sample validation is still required.

## Conclusion

The entry-quality improvement appears broadly stable across market periods.

The best current Swing research candidate remains:

**Sector Rank + ADX + EMA200 extension <= 25% + Prior 20d return <= 15%**

This candidate improved average return, win rate, and profit factor across all three time splits. It also improved average return in every evaluated rolling six-month window.

However, the alpha evidence is less perfect. The final third showed slightly weaker alpha, and rolling-window alpha improved in 16 of 22 windows.

## Recommendation

Do not create V2.1 yet.

Before production promotion, run one more validation layer:

1. Compare this entry-filtered model against V1 Swing, Swing V2, and unfiltered Sector Rank + ADX on the same top-portfolio construction.
2. Test whether alpha weakness in Period C is caused by benchmark composition, sector concentration, or missing high-beta winners.
3. Validate the filters on an out-of-sample forward period when new EOD data becomes available.

If those checks pass, the model is strong enough to become the official Swing V2.1 candidate.
