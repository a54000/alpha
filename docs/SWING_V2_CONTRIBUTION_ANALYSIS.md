# Swing V2 Contribution Analysis

**Date:** 2026-06-11

**Objective:** Determine which Swing V2 changes drove the performance improvement versus the clean V1 baseline.

**Scope:** Research only. No V3 model is created.

---

## Inputs

Primary result files:

- `reports/v1_clean_backtest_results.json`
- `reports/v2_backtest_results.json`
- `reports/swing_v2_ablation_results.json`

Models compared:

- V1 clean: `swing`
- Swing V2: `swing_v2`

Primary horizon:

- `return_20d`

Execution assumption:

- next-trading-day open entry
- fixed-horizon close exit
- benchmark aligned to each trade's entry/exit window

---

## Method

I tested Swing V2 by removing one factor group at a time:

- ADX
- BB Width
- Sector Rank
- Volume
- EMA

For each ablation:

1. Recomputed daily Swing V2 candidate scores with one factor group removed.
2. Rescaled the remaining score to 100.
3. Applied the same recommendation threshold: `score >= 70`.
4. Selected top 20 recommendations per day.
5. Inserted temporary recommendation rows using short temporary model names.
6. Ran the same remediated backtest engine.
7. Deleted the temporary recommendation rows after measurement.

Temporary model names used:

| Temporary Model | Meaning |
|---|---|
| `sv2_no_adx` | Swing V2 without ADX |
| `sv2_no_bb` | Swing V2 without BB Width |
| `sv2_no_sec` | Swing V2 without Sector Rank |
| `sv2_no_vol` | Swing V2 without Volume |
| `sv2_no_ema` | Swing V2 without EMA |

The ablation scores were rescaled because otherwise removing a factor would mechanically lower the score ceiling and mostly test the threshold, not the factor contribution.

---

## V1 Clean vs Swing V2

| Model | Trades | Valid | Avg Return | Win Rate | Profit Factor | Alpha |
|---|---:|---:|---:|---:|---:|---:|
| V1 Clean Swing | 2,045 | 1,911 | -0.5329% | 43.43% | 0.8850 | -0.1948% |
| Swing V2 | 7,189 | 6,870 | -0.0987% | 46.83% | 0.9767 | 0.1762% |
| Improvement | +5,144 | +4,959 | +0.4341 pp | +3.39 pp | +0.0918 | +0.3711 pp |

Swing V2 improves on the clean V1 baseline across all four requested metrics, but the model is still slightly negative on absolute average return at the 20d horizon.

---

## Ablation Results

| Test | Trades | Valid | Avg Return | Win Rate | Profit Factor | Alpha |
|---|---:|---:|---:|---:|---:|---:|
| Full Swing V2 | 7,189 | 6,870 | -0.0987% | 46.83% | 0.9767 | 0.1762% |
| Remove ADX | 7,664 | 7,374 | -0.0895% | 47.06% | 0.9793 | 0.0176% |
| Remove BB Width | 3,612 | 3,394 | -0.1102% | 48.08% | 0.9732 | 0.0522% |
| Remove Sector Rank | 8,959 | 8,567 | -0.2078% | 46.42% | 0.9516 | 0.0043% |
| Remove Volume | 9,481 | 9,081 | 0.0646% | 48.81% | 1.0158 | 0.1276% |
| Remove EMA | 8,064 | 7,767 | 0.0425% | 47.92% | 1.0104 | 0.2140% |

---

## Impact vs Full Swing V2

Negative values mean the ablation became worse than full Swing V2. Positive values mean the ablation became better than full Swing V2.

| Removed Group | Avg Return Impact | Win Rate Impact | Profit Factor Impact | Alpha Impact |
|---|---:|---:|---:|---:|
| ADX | +0.0093 pp | +0.23 pp | +0.0025 | -0.1586 pp |
| BB Width | -0.0114 pp | +1.26 pp | -0.0035 | -0.1241 pp |
| Sector Rank | -0.1091 pp | -0.40 pp | -0.0252 | -0.1719 pp |
| Volume | +0.1634 pp | +1.98 pp | +0.0391 | -0.0486 pp |
| EMA | +0.1412 pp | +1.09 pp | +0.0337 | +0.0378 pp |

---

## Factor Group Interpretation

### Sector Rank Contribution

Sector Rank is the clearest positive contributor.

Removing Sector Rank caused the largest deterioration:

- Avg return worsened by `0.1091 pp`.
- Win rate fell by `0.40 pp`.
- Profit factor fell by `0.0252`.
- Alpha fell by `0.1719 pp`.

This is consistent with the sector research audit: lower `rank_3m` represents stronger sectors, and Swing V2 correctly transforms that into higher score contribution.

**Verdict:** Sector Rank is responsible for a meaningful part of the Swing V2 improvement.

### BB Width Contribution

BB Width has a modest positive contribution.

Removing BB Width:

- Slightly worsened avg return.
- Slightly worsened profit factor.
- Meaningfully reduced alpha.
- Increased win rate, but with far fewer trades.

The lower trade count matters: removing BB Width and rescaling produced only `3,612` trades versus `7,189` for full Swing V2. The factor appears to broaden opportunity selection while preserving alpha better than the no-BB variant.

**Verdict:** BB Width contributes positively, especially to alpha and opportunity coverage, but it is not the dominant driver in this ablation.

### ADX Contribution

ADX has a mixed contribution.

Removing ADX slightly improved:

- avg return
- win rate
- profit factor

But it materially reduced alpha:

- Full Swing V2 alpha: `0.1762%`
- No ADX alpha: `0.0176%`

This suggests ADX may be helping relative-to-benchmark selection more than raw absolute return. It may also be affecting which market windows and stocks are selected.

**Verdict:** ADX is not the main absolute-return driver in this run, but it appears to support benchmark-relative performance.

### Volume Contribution

Volume is not supported by this ablation as a positive Swing V2 driver.

Removing Volume improved:

- avg return
- win rate
- profit factor

Alpha fell slightly, but full Swing V2 retained only a small alpha advantage versus the no-volume version.

This implies the current 15-point volume scoring may be selecting high-volume moves that are already crowded or extended.

**Verdict:** Volume appears to be a drag on absolute Swing V2 results in the current implementation.

### EMA Contribution

EMA is also not supported as a positive Swing V2 driver in this ablation.

Removing EMA improved:

- avg return
- win rate
- profit factor
- alpha

This does not prove EMA is useless as a trend context factor, but the current 10-point short-term EMA alignment rule does not appear to be responsible for Swing V2 improvement.

**Verdict:** EMA appears to be a drag in this Swing V2 implementation.

---

## Drivers Of Improvement

The Swing V2 improvement versus V1 Clean appears to come mostly from:

1. **Removing weak V1 factors**
   - RSI
   - MACD histogram
   - Stochastic
   - 52-week-high proximity
   - `rs_rank_pct`

2. **Adding Sector Rank**
   - The strongest positive ablation evidence among included V2 factors.

3. **Adding / increasing BB Width**
   - Helps alpha and maintains broader trade coverage.

ADX appears helpful for alpha but not clearly for absolute returns. Volume and EMA do not appear to be improvement drivers in this V2 configuration.

---

## Ranking Of Factor Contributions

Based on leave-one-group-out impact:

| Rank | Factor Group | Contribution Assessment |
|---:|---|---|
| 1 | Sector Rank | Strongest positive contributor |
| 2 | BB Width | Modest positive contributor, especially alpha |
| 3 | ADX | Mixed; helps alpha more than raw return |
| 4 | Volume | Likely negative for absolute performance |
| 5 | EMA | Likely negative in current Swing V2 form |

---

## Important Caveats

1. Ablations change the selected recommendation set, so factor effects are not isolated in a laboratory sense.
2. Scores were rescaled to 100 after factor removal to keep the `>= 70` threshold meaningful.
3. Trade counts vary materially across ablations, especially the no-BB test.
4. The score bucket analysis defect is not part of this test and remains a separate issue.
5. This does not create or recommend V3.
6. These results are specific to the current V2 scoring rules and EOD data.

---

## Conclusion

Swing V2 improved over V1 Clean primarily because it removed weak V1 factors and added better-supported factors.

Among the added or retained V2 factor groups, **Sector Rank is the clearest positive contributor**. **BB Width provides a smaller but still positive contribution**, especially to alpha. **ADX is mixed**, helping alpha but not clearly improving absolute return. **Volume and EMA appear to detract from the current Swing V2 result** and should be investigated before being carried forward unchanged.

No V3 model was created.
