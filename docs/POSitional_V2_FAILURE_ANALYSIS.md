# Positional V2 Failure Analysis

**Date:** 2026-06-11

**Objective:** Investigate why Positional V2 underperformed V1 Clean and recommend a Positional V2.1 design.

**Scope:** Research only. No code changes and no V3 implementation.

---

## Inputs

Primary files:

- `reports/v1_clean_backtest_results.json`
- `reports/v2_backtest_results.json`
- `reports/positional_v2_failure_ablation_results.json`

Models:

- V1 Clean: `positional`
- Positional V2: `positional_v2`

Primary horizon:

- `return_3m`

Execution assumption:

- next-trading-day open entry
- fixed-horizon close exit
- benchmark aligned to each trade's entry/exit window

---

## Method

I ran leave-one-component-out ablations for Positional V2:

- remove Sector Rank
- remove BB Width
- remove Trend
- remove Volume

For each ablation:

1. Recomputed daily candidate scores.
2. Removed one component group.
3. Rescaled the remaining score to 100.
4. Applied the same `score >= 65` threshold.
5. Selected top 20 recommendations per day.
6. Ran the remediated recommendation backtest.
7. Deleted temporary recommendation rows after measurement.

I also ran one research-only restoration probe:

- compress V2 to 70 points
- restore the V1 RS block as 30 points

This was not an implementation. It was only a diagnostic to test whether restoring V1 RS would likely help.

Temporary model rows were removed after the ablation run.

---

## V1 Clean vs Positional V2

| Model | Trades | Valid | Avg Return | Win Rate | Profit Factor | Alpha |
|---|---:|---:|---:|---:|---:|---:|
| V1 Clean Positional | 6,264 | 5,540 | -2.2126% | 44.08% | 0.7305 | -0.3630% |
| Positional V2 | 8,261 | 7,119 | -2.3992% | 43.91% | 0.7037 | -0.9958% |
| V2 Change | +1,997 | +1,579 | -0.1866 pp | -0.17 pp | -0.0267 | -0.6328 pp |

Positional V2 underperformed V1 Clean on all requested primary metrics:

- lower average return
- lower win rate
- lower profit factor
- worse alpha

The biggest deterioration is alpha, not just raw return.

---

## Ablation Results

| Test | Trades | Valid | Avg Return | Win Rate | Profit Factor | Alpha |
|---|---:|---:|---:|---:|---:|---:|
| Full Positional V2 | 8,261 | 7,119 | -2.3992% | 43.91% | 0.7037 | -0.9958% |
| Remove Sector Rank | 8,809 | 7,724 | -2.7914% | 41.99% | 0.6733 | -1.6253% |
| Remove BB Width | 8,021 | 6,931 | -2.1477% | 44.48% | 0.7250 | -0.6283% |
| Remove Trend | 9,170 | 7,961 | -1.2718% | 43.26% | 0.8377 | -0.6296% |
| Remove Volume | 8,970 | 7,733 | -2.1152% | 44.02% | 0.7360 | -1.0078% |
| Restore V1 RS Probe | 6,084 | 5,336 | -2.5506% | 43.14% | 0.6976 | -0.7515% |

---

## Impact vs Full Positional V2

Positive values mean removing the component improved the metric versus full Positional V2. Negative values mean removing it made the model worse.

| Test | Avg Return Impact | Win Rate Impact | Profit Factor Impact | Alpha Impact |
|---|---:|---:|---:|---:|
| Remove Sector Rank | -0.3922 pp | -1.93 pp | -0.0305 | -0.6295 pp |
| Remove BB Width | +0.2515 pp | +0.57 pp | +0.0212 | +0.3675 pp |
| Remove Trend | +1.1273 pp | -0.65 pp | +0.1340 | +0.3662 pp |
| Remove Volume | +0.2839 pp | +0.11 pp | +0.0322 | -0.0120 pp |
| Restore V1 RS Probe | -0.1515 pp | -0.77 pp | -0.0062 | +0.2442 pp |

---

## Component Findings

### Sector Rank Impact

Sector Rank is not the source of the V2 failure.

Removing Sector Rank made every metric worse:

- avg return fell from `-2.3992%` to `-2.7914%`
- win rate fell from `43.91%` to `41.99%`
- profit factor fell from `0.7037` to `0.6733`
- alpha fell from `-0.9958%` to `-1.6253%`

This confirms that sector leadership still helps the positional model directionally.

**Decision:** Keep Sector Rank in Positional V2.1.

### BB Width Impact

BB Width appears to be a degradation source for Positional V2.

Removing BB Width improved:

- avg return
- win rate
- profit factor
- alpha

The no-BB ablation also slightly exceeded V1 Clean average return, though it still lagged V1 Clean on alpha and profit factor.

Interpretation:

BB Width works better as a swing/volatility factor than as a 3-month positional factor in the current scoring form. It may be selecting volatility expansion after the move is already mature.

**Decision:** Remove BB Width from Positional V2.1 or move it to investigation-only.

### Trend Component Impact

The Trend component is the largest degradation source in this ablation.

Removing the V2 Trend block improved:

- avg return from `-2.3992%` to `-1.2718%`
- profit factor from `0.7037` to `0.8377`
- alpha from `-0.9958%` to `-0.6296%`

Win rate declined slightly, but the large improvement in average return and profit factor suggests the current trend rules are filtering into worse payoff distributions.

This does not prove trend should be removed from a positional model. It does suggest that the current V2 trend implementation is too blunt:

- EMA Stage 2 alignment may be late.
- Higher ADX emphasis may select exhausted trends.
- Combining Stage 2 alignment with high ADX may over-select crowded continuation trades.

**Decision:** Do not carry current V2 Trend unchanged. Reduce and rework it for V2.1.

### Volume Component Impact

Volume is a mild degradation source.

Removing Volume improved:

- avg return
- win rate slightly
- profit factor

Alpha was almost unchanged and slightly worse. That means Volume may provide a little benchmark-relative filtering, but not enough to justify the current contribution if the objective is 3-month payoff quality.

**Decision:** Keep Volume only as a small confirmation or tie-breaker, not a core positional factor.

### V1 RS Restoration Probe

Restoring the V1 RS block did not solve the failure.

The restore-RS probe produced:

- worse avg return than full V2
- worse win rate than full V2
- worse profit factor than full V2
- better alpha than full V2, but still worse than V1 Clean alpha

This is consistent with `RS_FINAL_VERDICT.md`: the existing RS factors should not be restored as scoring drivers.

**Decision:** Do not restore `rs_rank_pct` or `rs_vs_nifty_60d` in their V1 form.

---

## What Caused The Degradation?

Primary causes:

1. **V2 Trend implementation**
   - Largest negative contribution.
   - Removing it materially improved average return and profit factor.

2. **BB Width added to Positional**
   - Helped Swing V2, but hurt Positional V2.
   - Should not be assumed cross-model.

3. **Volume as a scored component**
   - Mild drag on absolute returns and profit factor.

Not the cause:

1. **Sector Rank**
   - Removing it made Positional V2 much worse.

2. **RS removal**
   - Restoring V1 RS did not improve the model enough and worsened most absolute metrics.

---

## Which V1 Factors Should Be Restored?

| V1 Factor | Restore? | Rationale |
|---|---|---|
| `rs_rank_pct` | No | Prior RS research failed; restore probe worsened avg return, win rate, and profit factor. |
| `rs_vs_nifty_60d` | No | Same RS family problem; restore probe did not justify reintroduction. |
| V1 EMA Stage 2 structure | Partially | Trend should remain conceptually, but V2 implementation needs lower weight or stricter payoff validation. |
| V1 ADX lower emphasis | Partially | V2 increased ADX; ablation suggests high trend emphasis is harmful. Restore lower ADX influence or use as tie-breaker. |
| V1 Sector Rank | Yes | Sector Rank remains supported; V2 increased it and ablation confirms it helps. |
| V1 Volume at 10 points | Reduce / optional | V2 kept volume at 10, but ablation suggests even this may be too much. |

---

## Which V2 Factors Should Remain?

| V2 Factor | Keep? | Rationale |
|---|---|---|
| Sector Rank | Yes | Strongest supported Positional V2 component. Removing it worsened all metrics. |
| BB Width | No | Hurt all primary metrics in Positional V2 ablation. |
| Trend | Yes, but reworked | Current implementation hurts payoff; trend concept should remain but with lower weight and less ADX exhaustion risk. |
| Volume | Small only | Mild drag; keep only as confirmation/tie-breaker if needed. |
| Eligibility guard | Yes | Not a predictive factor, but keeps low-quality names out. |
| Current RS features | No | Restore probe and prior RS verdict do not support restoration. |

---

## Recommended Positional V2.1 Design

This is a research recommendation only. Do not implement yet.

### Design Goal

V2.1 should keep what worked in V2 and remove what caused the degradation:

- keep Sector Rank
- remove BB Width from Positional
- reduce/rework Trend
- reduce Volume
- do not restore V1 RS

### Proposed Component Weights

| Component | Positional V2 | Proposed V2.1 | Change |
|---|---:|---:|---:|
| Sector Rank | 30 | 40 | +10 |
| Trend | 40 | 30 | -10 |
| Volume | 10 | 5 | -5 |
| BB Width | 15 | 0 | -15 |
| Eligibility / Quality Guard | 5 | 5 | 0 |
| Research Reserve / Unallocated Validation Block | 0 | 20 | +20 |
| **Total** | **100** | **100** | |

The 20-point reserve should not be assigned to an untested factor blindly. It should be used only after testing alternatives such as:

- lower-volatility trend continuation
- drawdown-from-high filters
- sector rank persistence
- sector-relative strength variants
- valuation/fundamental overlays if available

### If A Fully Allocated V2.1 Is Required

Use this as a conservative test candidate:

| Factor | Proposed Weight |
|---|---:|
| Sector rank (`rank_3m`) | 40 |
| EMA trend structure | 18 |
| ADX trend strength | 12 |
| Volume ratio | 5 |
| Eligibility / liquidity guard | 5 |
| Sector rank persistence / stability filter | 20 |
| **Total** | **100** |

Important: the final 20-point sector persistence block should be implemented only if it can be derived without look-ahead and validated separately. If not, leave it out of production scoring and run it as research.

---

## Final Recommendation

Do not proceed with current Positional V2 as a replacement model.

Recommended actions:

1. Keep Sector Rank.
2. Remove BB Width from Positional scoring.
3. Rework Trend; do not keep the current 40-point V2 trend block unchanged.
4. Reduce Volume to a small confirmation role.
5. Do not restore V1 RS factors.
6. Design Positional V2.1 around sector leadership plus a lower-risk trend confirmation, then backtest it separately.

No implementation was performed in this analysis.
