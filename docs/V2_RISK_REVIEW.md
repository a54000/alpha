# V2 Risk Review

**Date:** 2026-06-11  
**Reviewed Document:** `docs/SCORING_V2_PROPOSAL.md`  
**Purpose:** Identify assumptions, gaps, and risks that could invalidate the V2 proposal  
**Status:** Research review only. No code changes.

---

## Executive Summary

The V2 proposal is directionally better than V1 because it removes weak factors and concentrates weight into factors with stronger evidence. However, the proposal is not yet proven.

The biggest risk is that V2 is still based on factor-level forward-return research, not a full recommendation-level portfolio backtest. A factor can look useful in isolation and still fail after scoring interactions, ranking, recommendation thresholds, execution assumptions, transaction costs, and market-regime effects.

V2 should therefore be treated as a research hypothesis, not as a validated model.

---

## Weak Assumptions

### 1. Factor-level evidence will translate into portfolio-level alpha

The proposal assumes that stronger standalone factors will produce better recommendations once combined into a 100-point score. This may fail because factor interactions can dilute, duplicate, or reverse standalone effects.

**Could invalidate V2 if:** V2 score buckets remain flat or V2 recommendations still underperform V1/benchmark.

### 2. Proposed weights are not empirically optimized

Swing V2 assigns 40 points to BB Width and 35 points to Trend. Positional V2 assigns 30 points to Sector Rank and 15 points to BB Width. These are judgment-based weights derived from evidence tiers, not optimized or cross-validated weights.

**Could invalidate V2 if:** The chosen weights over-concentrate in one signal and produce worse diversification or unstable recommendations.

### 3. BB Width interpretation is not fully settled

The proposal increases BB Width dramatically, but V1 used BB Width as a squeeze condition while research treats `bb_width` as a factor. These are not necessarily the same signal.

**Could invalidate V2 if:** The implementation rewards the wrong BB Width regime, such as chasing already-expanded volatility after the move has matured.

### 4. EMA alignment is kept without isolated evidence

EMA alignment remains in both Swing and Positional V2 because it is intuitive trend structure, but the current research matrix says EMA was not separately isolated.

**Could invalidate V2 if:** EMA rules add lag, reduce responsiveness, or block otherwise strong candidates without improving returns.

### 5. Sector rank is added to Swing despite not being a V1 Swing factor

Sector `rank_3m` is proposed as 10 points in Swing V2. Sector rank evidence exists, but using it for short-horizon swing scoring is still an extension.

**Could invalidate V2 if:** Sector rank works better at positional horizons than 5d/10d swing horizons, or if it reduces Swing trade responsiveness.

### 6. Positional BB Width is an extrapolation

BB Width is not a V1 Positional factor. Adding it to Positional V2 is reasonable but not yet proven as part of positional scoring.

**Could invalidate V2 if:** BB Width improves short-term selection but does not improve 1m/3m holding-period results.

### 7. Removing oscillators may remove useful interaction effects

RSI, MACD, and Stochastic are weak/inverse as bullish standalone factors, but the research may not fully capture conditional interactions, such as oscillator behavior only inside strong trends.

**Could invalidate V2 if:** A stripped-down model loses timing information that was useful only in combination with trend/volume filters.

### 8. Removing RS may discard untested trader-style RS

Current `rs_rank_pct` and corrected benchmark-relative RS failed research. But trader-style RS120, RS250, RS slope, RS breakout, and sector-relative RS are not tested.

**Could invalidate V2 if:** V2 removes all relative strength exposure while an untested RS variant is actually useful.

---

## Research Gaps

### 1. No V2 recommendation backtest yet

The proposal is not validated as a model. It has not generated V2 scores, V2 recommendations, or V2 backtest results.

**Required before confidence:** Full V2 backtest against frozen V1 and benchmark.

### 2. No factor interaction analysis

The research identifies standalone factor behavior, but not interactions such as:

- BB Width plus ADX
- ADX plus EMA alignment
- Sector rank plus BB Width
- Volume ratio only during breakouts

**Risk:** Weights may double-count related effects or miss useful conditional logic.

### 3. No time-split validation

The same broad historical period has been used to discover factors and propose V2. There is no documented train/test split, walk-forward split, or out-of-sample validation.

**Risk:** The V2 design may be fitted to the 2024-07-08 to 2026-06-09 sample.

### 4. No regime-specific analysis

The period may not cover enough bull, bear, sideways, high-volatility, and low-volatility regimes.

**Risk:** V2 may only work in the market regime represented by the current sample.

### 5. No transaction-cost research

V1 backtests exclude slippage, brokerage, STT, stamp duty, and spread impact. V2 may increase turnover if BB Width and sector rank create more frequent recommendation changes.

**Risk:** Even if gross returns improve, net returns may remain negative.

### 6. No dynamic exit validation

The current evidence uses fixed forward returns. V2 proposal does not validate stop-losses, targets, trailing exits, rank decay, or time exits.

**Risk:** Fixed-horizon factor results may not map to actual trading behavior.

### 7. No risk-adjusted performance targets

The proposal targets win rate, average return, and profit factor, but does not require Sharpe, Sortino, drawdown, Calmar, tail loss, or volatility-adjusted alpha.

**Risk:** V2 may improve average return while worsening drawdowns or tail risk.

### 8. No sector concentration analysis

Increasing `rank_3m` may cluster recommendations into a few sectors.

**Risk:** Portfolio concentration may increase drawdown and reduce diversification.

### 9. No liquidity/slippage sensitivity by stock

The proposal includes eligibility/liquidity guardrails, but does not yet validate execution quality by liquidity bucket.

**Risk:** Lower-liquidity names could dominate factor wins but be hard to trade at expected prices.

---

## Potential Overfitting

### 1. Weight choices may fit observed factor rankings

The proposed weights heavily reward factors that looked strongest in the current research. This is sensible but can overfit if the factor ranking is sample-specific.

### 2. Reusing the same period for discovery and validation

If V2 is backtested on the same period used to select the factors, performance may overstate future robustness.

### 3. Multiple factor trials increase false discovery risk

Many factors were inspected across multiple horizons. Some positive results may occur by chance.

### 4. Sector results may be sample-specific

Sector rank worked in the tested window, but sector rotation behavior can change materially across market regimes.

### 5. BB Width may be regime-sensitive

BB Width can behave differently during broad bull markets, volatility shocks, and quiet mean-reversion regimes.

### 6. Removing weak factors based only on this sample may over-prune

RSI, MACD, and Stochastic may be weak as unconditional bullish factors but useful under specific regimes or as risk filters.

---

## Data Quality Concerns

### 1. Price data coverage is limited

The current backtest period is roughly 2024-07-08 to 2026-06-09 with about 497 trading days. This is short for robust model design, especially for positional signals.

### 2. Symbol coverage is below NSE500 count

Backtest docs report 434 symbols with price data, not a full 500-stock universe.

**Risk:** Results may not represent the actual NSE500 universe.

### 3. Historical NSE500 membership may be inaccurate

If the universe is based on current or static membership rather than date-accurate membership, results can be biased.

### 4. Corporate action adjustment quality is not reviewed here

Bad split/dividend adjustment can distort returns, indicators, 52-week levels, and forward-return research.

### 5. Indicator warm-up and missing data may affect samples

Features like EMA 150/200, BB Width averages, and 52-week fields require sufficient history. Early-period rows may have missing or less reliable values.

### 6. Sector classification may be static

If sector assignments are current/static, historical sector research may be distorted for companies whose classification changed.

### 7. Sector return computation may be affected by small sector counts

Some sectors have very few stocks. For example, small sectors can produce unstable sector returns and rankings.

### 8. Imported database/data migration risk

The database was migrated from another machine. If dump/restore, `.env`, or PostgreSQL version differences affected data completeness, research output could be impacted.

---

## Survivorship Bias Concerns

### 1. NSE500 composition changes over time

V1 docs explicitly note survivorship bias. If failed, delisted, excluded, or newly added companies are not handled historically, factor performance may be overstated.

### 2. Current constituents may dominate historical tests

If the universe uses current NSE500 stocks across the whole history, it excludes names that dropped out and includes names before they were actually index members.

### 3. Sector rank research may inherit survivorship bias

Sector returns are equal-weighted from available stocks. If weak stocks disappeared from the dataset, sector strength may be overstated.

### 4. Recommendation backtests may omit historical losers

Survivorship bias can make any V2 improvement look better than live-tradable reality.

**Required mitigation:** Use `universe_snapshot` and date-valid NSE500 membership for feature ranking, sector computation, scoring, and backtesting.

---

## Benchmark Comparison Concerns

### 1. Benchmark horizon comparison is limited

V1 benchmark alpha is documented for Swing 20d and Positional 3m, but not every horizon.

### 2. Benchmark execution assumptions differ from model assumptions

If model returns use signal-date close and benchmark comparison uses comparable close-to-close returns, the comparison is internally consistent but still not realistic for live execution.

### 3. Nifty500 TRI may not match actual trade universe implementation

Benchmark is `^CRSLDX`, while trade universe has 434 symbols and may not match exact historical Nifty500 composition.

### 4. No risk-adjusted benchmark comparison

Alpha alone is insufficient. V2 should compare volatility, drawdown, Sharpe/Sortino, hit rate, and tail risk against benchmark.

### 5. Cash drag and position sizing are unclear

Top-N recommendations do not automatically translate to a realistic portfolio. Benchmark comparison can be misleading without capital allocation, holding overlap, turnover, and cash assumptions.

### 6. Transaction costs affect strategy more than benchmark

Nifty500 benchmark return is passive. V2 recommendations may involve turnover, taxes, spreads, and slippage. Gross alpha must be large enough to survive these costs.

---

## Backtest Methodology Risks

### 1. Entry price uses signal-date close

V1 docs note that backtest uses close price instead of next-day open. This can introduce look-ahead bias.

### 2. Fixed-horizon returns are not trading-system returns

The current method checks forward returns after fixed periods. It does not model how trades would actually be exited.

### 3. Score bucket analysis may have a defect

Backtest docs mention identical or near-identical bucket outputs, suggesting the bucket analysis may be reusing the same results.

### 4. No overlapping-position handling

The recommendation stream can contain repeated names across dates. A realistic portfolio must define whether to add, hold, rebalance, or ignore duplicates.

### 5. No capital constraints

Top-20 lists do not define capital allocation, max positions, max sector exposure, or position sizing.

### 6. No turnover or holding-period analysis

V2 may improve signal quality while creating excessive turnover.

### 7. Invalid future trades near period end

The longer the horizon, the more invalid trades appear near the end of sample. This can skew horizon comparisons.

---

## Factor-Specific Risks

### BB Width

- Direction and threshold selection are not finalized.
- Absolute BB Width and relative BB Width expansion may capture different effects.
- Volatility expansion can occur after a move is already extended.
- High BB Width may also indicate instability and downside volatility.

### ADX

- ADX measures trend strength, not trend direction.
- ADX can remain high late in trends.
- ADX combined with EMA alignment may lag turning points.

### EMA Alignment

- Kept primarily by trading logic, not isolated evidence.
- May reduce early entry quality.
- May over-select already mature trends.

### Volume Ratio

- Moderate evidence only.
- Volume spikes can occur on distribution, news, or exhaustion.
- EOD volume ratio lacks intraday context.

### Sector Rank

- `rank_3m` must be inverted for scoring because rank 1 is strongest.
- Sector rank can cause concentration.
- Raw sector returns showed mean reversion, so sector scoring must not accidentally reward high raw returns incorrectly.
- Small sectors can create noisy ranks.

### Removed Oscillators

- RSI/MACD/Stochastic may still be useful conditionally or as risk filters.
- Removing them entirely may reduce timing information.
- Inverse relationships may suggest mean-reversion opportunities that are not captured by the V2 trend/breakout design.

### Removed RS

- Current RS should be removed, but trader-style RS variants remain untested.
- Removing RS may make the model less cross-sectionally aware outside sector rank.

---

## What Could Invalidate V2

V2 should be considered invalid or needing redesign if any of the following occur:

1. V2 recommendations do not outperform V1 on primary horizons.
2. V2 does not improve benchmark alpha after transaction costs.
3. V2 score buckets remain flat or inverted.
4. V2 performance depends on one sector or one short time period.
5. V2 produces excessive turnover.
6. V2 increases drawdown or tail losses materially.
7. V2 fails out-of-sample or walk-forward validation.
8. V2 performance disappears under next-day-open execution.
9. V2 performance disappears after survivorship-bias correction.
10. V2 performance is driven by data errors, missing symbols, or sector classification artifacts.
11. BB Width scoring direction proves wrong in implementation.
12. Sector rank transformation is implemented incorrectly.
13. V2 has lower trade count or narrower universe coverage that makes results statistically weak.

---

## Required Pre-Implementation Checks

Before coding V2 scoring, verify:

1. V2 proposal weights are still aligned with `V2_FACTOR_DECISION_MATRIX.md`.
2. Sector rank direction is documented in implementation notes.
3. BB Width scoring direction is specified clearly.
4. EMA alignment is acknowledged as retained-but-not-isolated.
5. V2 will be stored as a separate model version, not overwrite V1.
6. Backtest comparison will use the same dates and universe as V1.

---

## Required Post-Implementation Validation

After V2 implementation, require:

1. V2 vs V1 side-by-side backtest.
2. V2 vs benchmark at each relevant horizon.
3. Score bucket analysis with verified non-reused buckets.
4. Transaction-cost-adjusted results.
5. Next-day-open execution results.
6. Sector concentration report.
7. Turnover report.
8. Drawdown and risk-adjusted metrics.
9. Walk-forward or date-split validation.
10. Survivorship-bias sensitivity check using `universe_snapshot`.

---

## Final Risk Verdict

The V2 proposal is a reasonable research hypothesis, but it is not yet a validated trading model.

The proposal can be invalidated by:

- overfitting to the current factor research window,
- incorrect BB Width or sector-rank interpretation,
- survivorship bias,
- unrealistic backtest execution,
- missing transaction costs,
- weak score bucket behavior,
- or failure to outperform frozen V1 and benchmark after realistic assumptions.

Proceed only if V2 is built as a separate validation model and subjected to the checks above.
