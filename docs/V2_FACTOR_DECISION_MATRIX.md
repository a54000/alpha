# V2 Factor Decision Matrix

**Date:** 2026-06-11  
**Status:** Research synthesis only  
**Scope:** Swing and Positional V1 factors only  
**Purpose:** Provide the factor-level decision basis for `docs/SCORING_V2_PROPOSAL.md`

---

## Source Documents

This matrix synthesizes:

- `docs/V1_BASELINE.md`
- `docs/SCORING_VALIDATION.md`
- `docs/BACKTEST_RESULTS.md`
- `docs/FACTOR_RESEARCH_SUMMARY.md`
- `docs/FACTOR_STABILITY_REPORT.md`
- `docs/SECTOR_FACTOR_RESEARCH.md`
- `docs/SECTOR_RESEARCH_AUDIT.md`
- `docs/RS_FINAL_VERDICT.md`

No code or scoring model changes are made by this document.

---

## Decision Vocabulary

| Recommendation | Meaning |
|---|---|
| KEEP | Retain current role or broad usage in V2 |
| INCREASE | Retain and allocate more scoring weight |
| REDUCE | Retain, but lower scoring weight or use only as secondary confirmation |
| REMOVE | Remove from V2 scoring as currently used |
| INVESTIGATE | Do not include as a primary V2 factor until more research is complete |

---

## Context From V1

V1 is frozen and underperforms the benchmark.

Key V1 backtest findings:

| Model | Primary Horizon | Avg Return | Win Rate | Profit Factor | Alpha |
|---|---:|---:|---:|---:|---:|
| Swing | 20d | -0.42% | 44.7% | 0.91 | -0.13% |
| Positional | 3m | -2.07% | 44.6% | 0.74 | -0.27% |

The score bucket analysis also showed poor differentiation. Higher V1 scores did not reliably produce better forward returns.

---

## Swing Model Factor Matrix

V1 Swing composition:

| Component | Current Weight |
|---|---:|
| Trend | 30 |
| Momentum | 30 |
| Volume | 20 |
| Breakout | 10 |
| Relative Strength | 10 |
| **Total** | **100** |

### Swing Factor Decisions

| Factor | Current Weight | Predictive Evidence | Stability | Recommendation |
| ------ | -------------- | ------------------- | --------- | -------------- |
| ADX strength / direction (`adx_14`, `adx_prev`) | 20 | Tier A in factor research. Trend-strength factor with positive evidence. | Expected high per stability framework; exact multi-horizon values still need final populated stability table. | INCREASE |
| EMA short-term alignment (`ema_5`, `ema_13`, `ema_20`, close) | 10 | Not directly isolated in the current factor research, but trend structure is a core V1 trend component and pairs logically with ADX. | Not separately measured. | KEEP |
| RSI (`rsi_14`) | 15 | Tier D / inverse relationship. Current bullish treatment is not supported. | Expected low or inverse; not suitable as current bullish score. | REMOVE |
| MACD histogram (`macd_hist`, `macd_hist_prev`) | 10 | Tier D / inverse relationship. Current bullish treatment is not supported. | Expected low or inverse; not suitable as current bullish score. | REMOVE |
| Stochastic (`stoch_k`, `stoch_d`) | 5 | Tier D / inverse relationship. Current bullish treatment is not supported. | Expected low or inverse; not suitable as current bullish score. | REMOVE |
| Volume ratio (`volume_ratio`) | 20 | Tier B / monitor. Moderate positive evidence, but weaker than ADX and BB Width. | Expected medium; may decay at longer horizons. | REDUCE |
| 52-week high proximity (`pct_from_52w_high`) | 6 | Tier C / remove or rework. Weak predictive evidence. | Expected low. | REMOVE |
| Bollinger width / squeeze (`bb_width`, `bb_width_20avg`) | 4 | Tier A. Strongest technical factor found so far and materially underweighted in V1. | Expected high; needs full populated stability table but research summary supports priority. | INCREASE |
| RS rank percentile (`rs_rank_pct`) | 10 | RS final verdict is REMOVE. Corrected RS showed near-zero IC and failed success criteria. | Low after remediation; not predictive across tested horizons. | REMOVE |

### Swing Rationale

ADX and BB Width are the only Swing factors with strong positive evidence. BB Width is especially underweighted in V1 at only 4 points, despite being one of the strongest factors in research. Volume has some value but should not retain a 20-point role unless V2 backtesting proves it. The 30-point oscillator block should not carry into bullish V2 scoring because RSI, MACD histogram, and Stochastic were classified as inverse/weak rather than positively predictive.

The current RS feature should be removed despite remediation, because `RS_FINAL_VERDICT.md` concludes that corrected `rs_rank_pct` still lacks predictive power.

---

## Positional Model Factor Matrix

V1 Positional composition:

| Component | Current Weight |
|---|---:|
| Trend | 40 |
| Relative Strength | 30 |
| Sector Strength | 20 |
| Volume | 10 |
| **Total** | **100** |

### Positional Factor Decisions

| Factor | Current Weight | Predictive Evidence | Stability | Recommendation |
| ------ | -------------- | ------------------- | --------- | -------------- |
| EMA Stage 2 alignment (`ema_50`, `ema_150`, `ema_200`, close) | 25 | Not directly isolated in current factor research, but it is the core positional trend structure filter. | Not separately measured. | KEEP |
| ADX medium-term (`adx_14`, `adx_prev`) | 15 | Tier A in factor research. Positive trend-strength evidence. | Expected high per stability framework. | INCREASE |
| RS rank percentile (`rs_rank_pct`) | 18 | RS final verdict is REMOVE. Corrected RS showed near-zero IC and no useful bucket spread. | Low after remediation. | REMOVE |
| RS vs Nifty 60d (`rs_vs_nifty_60d`) | 12 | Corrected RS family did not meet predictive success criteria; trader-style RS variants not yet tested. | Not supported by current corrected RS research. | REMOVE |
| Sector 3-month rank (`rank_3m`) | 20 | Phase 6.5C supports sector rank. Stronger-ranked sectors outperformed weaker-ranked sectors across 5d, 10d, 20d, and 60d. | Medium to high. Direction is consistent, but interpretation must be inverted because lower rank is stronger. | INCREASE |
| Volume ratio (`volume_ratio`) | 10 | Tier B / monitor. Moderate secondary confirmation. | Expected medium; less central than trend, BB Width, and sector rank. | KEEP |

### Positional Rationale

The biggest Positional V1 problem is the 30-point RS block. RS remediation fixed the implementation, but research still found no predictive value, so both RS components should be removed from Positional V2 as scoring drivers.

Sector rank is the strongest Positional-specific factor currently available. `SECTOR_RESEARCH_AUDIT.md` confirms that `rank_3m` must be interpreted inversely: `bucket_1` is strongest sectors because lower rank is better. Negative IC for `rank_3m` is favorable and supports sector leadership.

Raw sector returns should not replace sector rank. `sector_return_1m`, `sector_return_3m`, and `sector_return_6m` showed negative ICs consistent with mean reversion rather than simple bullish sector momentum.

---

## Cross-Model Factors

| Factor | Used In | Current Total Weight | Recommendation | Rationale |
|---|---|---:|---|---|
| `adx_14` / ADX trend strength | Swing, Positional | 35 | INCREASE | Tier A evidence and useful for both swing and positional horizons. |
| EMA alignment | Swing, Positional | 35 | KEEP | Not isolated in factor research, but remains useful as trend structure confirmation. |
| `volume_ratio` | Swing, Positional | 30 | REDUCE / KEEP | Moderate evidence; reduce Swing overweight, keep Positional as confirmation. |
| `rs_rank_pct` | Swing, Positional | 28 | REMOVE | Corrected RS final verdict is REMOVE. |
| `rs_vs_nifty_60d` | Positional | 12 | REMOVE | RS family failed empirical validation; keep infrastructure for future research only. |
| `rank_3m` | Positional | 20 | INCREASE | Sector rank has favorable forward-return separation when interpreted correctly. |
| `bb_width` | Swing | 4 | INCREASE | Strong evidence and underweighted in V1. Consider adding to Positional V2 proposal, but note it is not a V1 Positional factor. |
| RSI / MACD / Stochastic | Swing | 30 | REMOVE | Tier D inverse/weak evidence; not valid as bullish V2 signals. |
| `pct_from_52w_high` | Swing | 6 | REMOVE | Tier C weak evidence. |

---

## Candidate V2 Weight Direction

This section is a decision guide, not an implementation spec.

### Swing V2 Direction

| Component | V1 Weight | Decision Direction |
|---|---:|---|
| Trend | 30 | Keep or modestly increase, led by ADX |
| Momentum oscillators | 30 | Remove from bullish V2 |
| Volume | 20 | Reduce to secondary confirmation |
| Breakout / BB Width | 10 total, only 4 for BB | Increase materially via BB Width |
| Relative Strength | 10 | Remove current RS |
| Sector Context | 0 | Investigate/add via `rank_3m` only if proposal chooses cross-model sector context |

### Positional V2 Direction

| Component | V1 Weight | Decision Direction |
|---|---:|---|
| Trend | 40 | Keep or increase, especially ADX |
| Relative Strength | 30 | Remove current RS block |
| Sector Strength | 20 | Increase `rank_3m`; do not use raw sector returns as bullish momentum |
| Volume | 10 | Keep as secondary confirmation |
| BB Width | 0 | Investigate/add as cross-model factor based on strong technical evidence |

---

## Risks And Caveats

1. **Factor research is not a complete V2 backtest.** The matrix identifies candidates, but V2 must still be implemented separately and backtested against frozen V1.
2. **EMA alignment was not isolated.** EMA structure is kept as trend context, but exact weight should be validated.
3. **BB Width direction needs scoring care.** Research supports BB Width, but V1 uses it as a squeeze condition. V2 must avoid assuming every BB interpretation is equally predictive.
4. **Sector rank direction is easy to misread.** For `rank_3m`, lower is stronger. A higher-is-better scoring transform should be used if implemented.
5. **Raw sector returns are not sector leadership scores.** Current research suggests mean reversion for raw sector return factors.
6. **RS is not solved forever.** Current `rs_rank_pct` should be removed, but trader-style RS120/RS250/static/adaptive RS remains untested.
7. **Backtest limitations remain.** V1 backtests lack transaction costs, next-day-open execution, dynamic exits, and survivorship-bias correction.

---

## Final Decision Summary

| Recommendation | Factors |
|---|---|
| INCREASE | `bb_width`, `adx_14`, `rank_3m` |
| KEEP | EMA alignment, `volume_ratio` in Positional |
| REDUCE | `volume_ratio` in Swing |
| REMOVE | `rs_rank_pct`, `rs_vs_nifty_60d`, RSI, MACD histogram, Stochastic, `pct_from_52w_high` |
| INVESTIGATE | Trader-style RS variants, raw sector-return mean reversion, BB Width in Positional, EMA isolated predictive value |

This matrix should be used as the primary source for the next `SCORING_V2_PROPOSAL.md` update.
