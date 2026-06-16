# Swing Factor Pruning Research

**Date:** 2026-06-11

**Objective:** Determine whether Volume and EMA should be removed from Swing V2.

**Scope:** Research only. Production scoring was not modified.

---

## Inputs

Primary sources:

- `reports/v2_backtest_results.json`
- `reports/swing_factor_pruning_results.json`
- `docs/SWING_V2_CONTRIBUTION_ANALYSIS.md`

Primary horizon:

- `return_20d`

Execution assumption:

- next-trading-day open entry
- fixed-horizon close exit
- benchmark aligned to each trade's entry/exit window

---

## Method

I tested four Swing V2 variants:

1. Current Swing V2
2. Swing V2 minus EMA
3. Swing V2 minus Volume
4. Swing V2 minus EMA and Volume

For pruning tests:

1. Recomputed daily candidate scores with the target factor group removed.
2. Rescaled the remaining score to 100.
3. Applied the same recommendation threshold: `score >= 70`.
4. Selected top 20 recommendations per day.
5. Inserted temporary recommendation rows.
6. Ran the same remediated backtest engine.
7. Deleted temporary recommendation rows after measurement.

Temporary model names:

| Temporary Model | Meaning |
|---|---|
| `sv2_pr_no_ema` | Swing V2 minus EMA |
| `sv2_pr_no_vol` | Swing V2 minus Volume |
| `sv2_pr_no_ev` | Swing V2 minus EMA and Volume |

---

## Results

| Model | Recommendation Count | Valid Count | Avg Return | Win Rate | Profit Factor | Alpha |
|---|---:|---:|---:|---:|---:|---:|
| Current Swing V2 | 7,189 | 6,870 | -0.0987% | 46.83% | 0.9767 | 0.1762% |
| Swing V2 minus EMA | 8,064 | 7,767 | 0.0425% | 47.92% | 1.0104 | 0.2140% |
| Swing V2 minus Volume | 9,481 | 9,081 | 0.0646% | 48.81% | 1.0158 | 0.1276% |
| Swing V2 minus EMA and Volume | 9,478 | 9,078 | 0.1484% | 49.00% | 1.0377 | 0.2056% |

---

## Impact vs Current Swing V2

| Variant | Avg Return Impact | Win Rate Impact | Profit Factor Impact | Alpha Impact | Recommendation Count Impact |
|---|---:|---:|---:|---:|---:|
| Minus EMA | +0.1412 pp | +1.09 pp | +0.0337 | +0.0378 pp | +875 |
| Minus Volume | +0.1634 pp | +1.98 pp | +0.0391 | -0.0486 pp | +2,292 |
| Minus EMA and Volume | +0.2471 pp | +2.17 pp | +0.0610 | +0.0294 pp | +2,289 |

---

## EMA Assessment

Removing EMA improves every measured metric:

- Avg return turns positive.
- Win rate improves from `46.83%` to `47.92%`.
- Profit factor improves from `0.9767` to `1.0104`.
- Alpha improves from `0.1762%` to `0.2140%`.
- Recommendation count increases.

This suggests the current short-term EMA alignment rule is filtering out useful Swing V2 candidates or overweighting mature setups.

**Research verdict:** EMA should be removed from Swing V2 in its current form.

---

## Volume Assessment

Removing Volume improves most measured metrics:

- Avg return turns positive.
- Win rate improves the most among single-factor removals.
- Profit factor improves to `1.0158`.
- Recommendation count increases materially.

Alpha declines versus current Swing V2, but remains positive. The absolute-return improvement is larger than the alpha reduction.

This suggests the current Volume factor may be selecting crowded or already repriced moves. It may work better as a post-score liquidity/eligibility filter than as a positive scoring component.

**Research verdict:** Volume should be removed as a Swing V2 scoring factor or reduced to a non-scoring filter.

---

## Combined EMA + Volume Removal

Removing both EMA and Volume is the strongest tested variant.

It produced:

- highest avg return
- highest win rate
- highest profit factor
- positive alpha
- larger recommendation universe than current Swing V2

Compared with current Swing V2:

- Avg return improves by `0.2471 pp`.
- Win rate improves by `2.17 pp`.
- Profit factor improves by `0.0610`.
- Alpha improves by `0.0294 pp`.
- Recommendation count increases by `2,289`.

This confirms that EMA and Volume are not only weak individually; together they appear to suppress better Swing V2 candidates.

**Research verdict:** Remove both EMA and Volume from Swing V2 if the next implementation step is approved.

---

## Interpretation

The earlier contribution analysis suggested:

- Sector Rank is the clearest positive contributor.
- BB Width is modestly positive.
- ADX is mixed but supports alpha.
- EMA and Volume appear to drag absolute performance.

This pruning test confirms the EMA and Volume concern with a direct combined test.

The likely current Swing V2 driver set is:

- Sector Rank
- BB Width
- ADX

The current drag set is:

- EMA
- Volume

---

## Recommendation

Do not modify production scoring as part of this research.

For the next approved Swing iteration, test a pruned Swing design that removes:

- EMA scoring
- Volume scoring

Keep:

- ADX
- BB Width
- Sector Rank

Volume may remain as a liquidity/eligibility requirement, but the current results do not support using it as a positive scoring factor.

EMA may be revisited later with a different definition, but the current short-term EMA alignment component should not remain in Swing V2 unchanged.

---

## Caveats

1. Scores were rescaled after factor removal to keep the `>= 70` threshold meaningful.
2. Recommendation counts changed materially, especially after removing Volume.
3. This is not a V3 proposal or implementation.
4. Transaction costs and dynamic exits are still not modeled.
5. Results are specific to current EOD data and current Swing V2 scoring rules.

---

## Final Verdict

Both EMA and Volume should be removed from Swing V2 scoring based on this research pass.

The strongest tested variant is **Swing V2 minus EMA and Volume**.

No production scoring changes were made.
