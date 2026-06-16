# Scoring V2 Proposal

**Date:** 2026-06-11  
**Status:** Proposal only - not implemented  
**Primary Source:** `docs/V2_FACTOR_DECISION_MATRIX.md`  
**Scope:** EOD Swing V2 and Positional V2 research validation models

---

## Executive Summary

V1 is frozen and remains the benchmark baseline. It underperforms the Nifty500 benchmark, and its score buckets do not meaningfully differentiate stronger recommendations from weaker ones.

V2 should remove weak or harmful V1 factors and concentrate weight into the factors supported by research:

- Increase `bb_width`
- Increase `adx_14`
- Increase sector `rank_3m`
- Keep EMA alignment as trend structure
- Keep or reduce `volume_ratio` as secondary confirmation
- Remove current RS features
- Remove RSI, MACD histogram, Stochastic, and 52-week-high proximity from bullish scoring

This document proposes V2 scoring weights only. It does not implement code, modify scoring models, or change recommendations.

---

## Evidence Basis

From `docs/V2_FACTOR_DECISION_MATRIX.md`:

| Recommendation | Factors |
|---|---|
| INCREASE | `bb_width`, `adx_14`, `rank_3m` |
| KEEP | EMA alignment, `volume_ratio` in Positional |
| REDUCE | `volume_ratio` in Swing |
| REMOVE | `rs_rank_pct`, `rs_vs_nifty_60d`, RSI, MACD histogram, Stochastic, `pct_from_52w_high` |
| INVESTIGATE | Trader-style RS variants, raw sector-return mean reversion, BB Width in Positional, EMA isolated predictive value |

V1 baseline performance:

| Model | Primary Horizon | Avg Return | Win Rate | Profit Factor | Alpha |
|---|---:|---:|---:|---:|---:|
| Swing | 20d | -0.42% | 44.7% | 0.91 | -0.13% |
| Positional | 3m | -2.07% | 44.6% | 0.74 | -0.27% |

The goal of V2 is not to optimize indicators blindly. The goal is to create a cleaner research model from measured evidence, then backtest it against frozen V1.

---

## Swing V2 Proposal

### Design Intent

Swing V2 targets 5d to 20d EOD trades. It should emphasize volatility expansion/breakout behavior, trend strength, and modest volume confirmation. It should remove the V1 oscillator block because the evidence does not support RSI, MACD, or Stochastic as bullish scoring factors.

### Component Weights

| Component | V1 Weight | V2 Proposed Weight | Change | Justification |
|---|---:|---:|---:|---|
| Trend | 30 | 35 | +5 | ADX is Tier A and should receive more weight; EMA alignment remains useful trend structure. |
| Volatility / Breakout | 10 | 40 | +30 | BB Width is Tier A and was severely underweighted in V1. |
| Volume | 20 | 15 | -5 | Volume ratio has moderate evidence but should be secondary. |
| Momentum Oscillators | 30 | 0 | -30 | RSI, MACD histogram, and Stochastic are Tier D / inverse or weak. |
| Relative Strength | 10 | 0 | -10 | Corrected RS research final verdict is REMOVE. |
| Sector Context | 0 | 10 | +10 | Sector `rank_3m` is supported and can help prefer stronger-sector stocks. |
| **Total** | **100** | **100** | | |

### Factor Weights

| Factor | V1 Weight | V2 Proposed Weight | Recommendation | Justification |
|---|---:|---:|---|---|
| ADX strength / direction (`adx_14`, `adx_prev`) | 20 | 25 | INCREASE | Tier A trend-strength factor with positive evidence. |
| EMA short-term alignment (`ema_5`, `ema_13`, `ema_20`, close) | 10 | 10 | KEEP | Trend structure is not isolated in research but remains useful with ADX. |
| BB Width absolute / regime (`bb_width`) | 0 direct | 25 | INCREASE | Strongest technical evidence; V1 underweights BB Width. |
| BB Width relative expansion (`bb_width` vs `bb_width_20avg`) | 4 | 15 | INCREASE | Retains V1 breakout concept but gives BB Width meaningful influence. |
| Volume ratio (`volume_ratio`) | 20 | 15 | REDUCE | Moderate evidence, useful confirmation, but not a primary driver. |
| Sector rank (`rank_3m`) | 0 | 10 | INVESTIGATE / ADD | Supported by sector research; lower rank is stronger and must be transformed if scored. |
| RSI (`rsi_14`) | 15 | 0 | REMOVE | Tier D / inverse relationship; not supported as bullish scoring. |
| MACD histogram (`macd_hist`) | 10 | 0 | REMOVE | Tier D / inverse relationship; not supported as bullish scoring. |
| Stochastic (`stoch_k`, `stoch_d`) | 5 | 0 | REMOVE | Tier D / inverse relationship; not supported as bullish scoring. |
| 52-week high proximity (`pct_from_52w_high`) | 6 | 0 | REMOVE | Tier C weak evidence. |
| RS rank percentile (`rs_rank_pct`) | 10 | 0 | REMOVE | RS final verdict is REMOVE after remediation and research. |
| **Total** | **100** | **100** | | |

### Swing V2 Expected Benefits

- More weight goes to researched positive factors instead of popular but weak indicators.
- Removing 30 points of oscillator scoring should reduce false bullish signals.
- Removing RS avoids a factor with near-zero predictive value.
- Increasing BB Width should improve breakout/volatility signal quality.
- Adding light sector context may improve stock selection when technical setups are otherwise similar.

### Swing V2 Risks

- BB Width scoring direction must be designed carefully; V1 used squeeze logic, but research supports BB Width as a broader factor.
- Sector rank is not a V1 Swing factor, so its Swing use must be validated separately.
- Removing oscillators may reduce familiar confirmation signals, even if evidence says they hurt.
- A factor-level improvement may not translate into portfolio-level improvement without V2 backtesting.

---

## Positional V2 Proposal

### Design Intent

Positional V2 targets 20d to 60d and 1m to 3m EOD trades. It should emphasize trend structure, ADX trend strength, sector leadership via `rank_3m`, and a smaller set of confirmation factors. The V1 RS block should be removed because corrected RS research failed its predictive criteria.

### Component Weights

| Component | V1 Weight | V2 Proposed Weight | Change | Justification |
|---|---:|---:|---:|---|
| Trend | 40 | 40 | 0 | EMA trend structure remains central; ADX should carry more of this component. |
| Sector Strength | 20 | 30 | +10 | `rank_3m` has favorable sector leadership evidence. |
| Volatility / Breakout | 0 | 15 | +15 | BB Width is strong across technical research; add as cross-model factor for validation. |
| Volume | 10 | 10 | 0 | Keep as secondary confirmation. |
| Relative Strength | 30 | 0 | -30 | Corrected RS features do not show predictive value. |
| Eligibility / Quality Guard | 0 | 5 | +5 | Preserve room for eligibility/liquidity/risk guardrails in scoring design. |
| **Total** | **100** | **100** | | |

### Factor Weights

| Factor | V1 Weight | V2 Proposed Weight | Recommendation | Justification |
|---|---:|---:|---|---|
| EMA Stage 2 alignment (`ema_50`, `ema_150`, `ema_200`, close) | 25 | 22 | KEEP | Core positional trend structure; not isolated but still necessary context. |
| ADX medium-term (`adx_14`, `adx_prev`) | 15 | 18 | INCREASE | Tier A trend-strength evidence; should have more influence within trend. |
| Sector 3-month rank (`rank_3m`) | 20 | 30 | INCREASE | Sector research supports stronger-ranked sectors; lower rank is stronger. |
| BB Width (`bb_width`, `bb_width_20avg`) | 0 | 15 | INVESTIGATE / ADD | Strong technical factor; proposed for validation in Positional V2 despite not being V1 Positional. |
| Volume ratio (`volume_ratio`) | 10 | 10 | KEEP | Moderate confirmation factor; keep at current Positional weight. |
| Eligibility / liquidity guard (`is_eligible`, liquidity constraints) | 0 | 5 | KEEP | Not a predictive factor, but helps avoid low-quality candidates. |
| RS rank percentile (`rs_rank_pct`) | 18 | 0 | REMOVE | RS final verdict is REMOVE. |
| RS vs Nifty 60d (`rs_vs_nifty_60d`) | 12 | 0 | REMOVE | Corrected RS family failed empirical validation. |
| Raw sector returns (`sector_return_1m/3m/6m`) | 0 | 0 | INVESTIGATE | Do not use as bullish momentum; current evidence suggests mean reversion. |
| **Total** | **100** | **100** | | |

### Positional V2 Expected Benefits

- Removes the 30-point RS block that lacks predictive support.
- Gives more influence to sector leadership, which showed favorable forward-return separation.
- Keeps the long-horizon trend structure of V1 while improving ADX emphasis.
- Adds BB Width as a researched technical factor that may improve score differentiation.
- Maintains volume as confirmation without over-weighting it.

### Positional V2 Risks

- BB Width in Positional is an extension from Swing/factor research and must be validated.
- Sector `rank_3m` can be misread; rank 1 is strongest, so scoring must invert rank into a higher-is-better score.
- Raw sector returns should not be substituted for sector rank because their evidence suggests mean reversion.
- Removing RS may reduce exposure to trader-style relative strength ideas, but those variants are not yet tested.
- V2 may improve factor logic but still fail after transaction costs or more realistic execution assumptions.

---

## Explicit Exclusions From V2

The following should not be included in V2 scoring as bullish factors:

| Excluded Factor | Reason |
|---|---|
| `rs_rank_pct` | Final RS verdict is REMOVE after remediation and research. |
| `rs_vs_nifty_60d` | Current corrected RS family failed predictive criteria. |
| RSI | Tier D / inverse or weak behavior. |
| MACD histogram | Tier D / inverse or weak behavior. |
| Stochastic | Tier D / inverse or weak behavior. |
| `pct_from_52w_high` | Tier C weak evidence. |
| Raw `sector_return_1m/3m/6m` as bullish momentum | Sector research suggests mean reversion, not momentum. |
| ATR rules | Not researched yet for V2. |
| New price momentum fields | Not researched yet for V2. |
| Trader-style RS120/RS250/zero-cross/breakout/slope | Valid backlog, but not tested yet. |
| 15-minute/intraday signals | Separate future intraday model, not EOD V2. |

---

## Validation Requirements

V2 must be implemented as a separate validation model before any production decision.

Required validation:

1. Backfill Swing V2 and Positional V2 scores over the V1 comparison window.
2. Generate V2 recommendations separately from V1.
3. Backtest V2 recommendations with the same methodology used for V1.
4. Compare V2 against frozen V1 and benchmark.
5. Check score bucket monotonicity.
6. Document whether V2 improves win rate, average return, profit factor, alpha, and score differentiation.

Suggested minimum success thresholds:

| Metric | V1 Baseline | V2 Target |
|---|---:|---:|
| Swing 20d avg return | -0.42% | > 0.00% |
| Swing 20d win rate | 44.7% | > 48.0% |
| Swing 20d profit factor | 0.91 | > 1.00 |
| Positional 3m avg return | -2.07% | > -0.50% |
| Positional 3m win rate | 44.6% | > 48.0% |
| Positional 3m profit factor | 0.74 | > 0.90 |
| Score bucket behavior | Weak/flat | Top score buckets outperform lower buckets |

---

## Final Recommendation

Proceed to V2 implementation only as a research validation build.

The proposed model direction is:

```text
 Increase BB Width
+ Increase ADX
+ Increase sector rank_3m
+ Keep EMA trend structure
+ Keep/reduce volume confirmation
- Remove current RS
- Remove RSI/MACD/Stochastic bullish scoring
- Remove 52-week-high proximity
- Avoid raw sector return chasing
```

This proposal should be treated as the design input for implementation planning, not as evidence that V2 will outperform. V2 must earn that through a separate backtest against frozen V1.
