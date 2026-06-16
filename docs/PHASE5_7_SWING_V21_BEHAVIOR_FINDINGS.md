# Phase 5.7 Swing V2.1 Behavior Findings

Generated on: 2026-06-12

## Objective

Document the observed live recommendation behavior where Swing V2.1 can recommend a stock with negative EMA200 extension and negative 20-day return.

This is a behavior finding only. No scoring, thresholds, recommendation logic, backtests, or production data were changed.

## Example Case: NATCOPHARM

Live recommendation review showed:

| Field | Value |
| --- | ---: |
| Symbol | NATCOPHARM |
| Recommendation type | swing_v2_1 |
| Sector | PHARMA |
| Business date | 2026-06-11 |
| EMA 200 | 975.2176 |
| EMA200 extension | -13.61% |
| Prior 20d return | -27.99% |
| ADX 14 | 41.4591 |
| Sector rank 3m | 7 |
| Final score | 77.1429 |
| Recommendation rank | 2 |

The recommendation is therefore a stock trading below its EMA200 and down sharply over the prior 20 trading days.

## Current Swing V2.1 Scoring Behavior

Frozen Swing V2.1 uses production-parity scoring from `app.scoring.compute_scores.compute_swing_v2_1_score`.

The key eligibility gate is:

```python
ema200_extension = (close - ema_200) / ema_200
if ema200_extension > 0.25 or prior_20d_return > 0.15:
    return None
```

This means Swing V2.1 blocks:

- EMA200 extension above +25%.
- Prior 20-day return above +15%.

Swing V2.1 does not block:

- Price below EMA200.
- Negative EMA200 extension.
- Negative prior 20-day return.
- Short-term drawdowns when ADX and sector rank are strong enough.

After the ceiling filters pass, the final Swing V2.1 score is driven by:

- ADX behavior.
- Sector rank.

NATCOPHARM passed because its negative EMA200 extension and negative prior 20-day return are below the upper exclusion thresholds, and its ADX/sector components produced a score above the recommendation threshold.

## Why This Is Not an Implementation Bug

The observed NATCOPHARM recommendation matches the frozen strategy rules exactly.

It is not caused by:

- A frontend display issue.
- A malformed explanation API response.
- A recommendation decision journal error.
- A sign inversion in EMA200 extension.
- A sign inversion in prior 20-day return.
- A missing threshold in the implementation relative to the frozen rule.

The implementation is applying the documented production-parity rule: avoid excessive upside extension, but do not require positive trend or positive recent momentum.

This is best classified as a strategy behavior finding, not a defect.

## Historical Validation Context

Phase 2F portfolio diagnostics found that the five-year Swing V2.1 pilot was structurally encouraging but not risk-free.

Relevant findings:

- The portfolios are strongly pro-cyclical.
- Most wealth creation occurred during bull portfolio regimes.
- Bear regimes detracted from returns.
- Top 5 Weekly benefited most from high-volatility rebound periods.
- Top 10 Weekly was more balanced across volatility regimes.

This context matters because the current filters can admit reversal-like candidates. A stock that is below EMA200 or down over 20 days can still score well if ADX and sector rank are favorable. That may be undesirable in a pure trend-following interpretation, but it may also be part of why Top 5 captured rebound behavior in the historical pilot.

Phase 2G walk-forward validation found:

- Top 5 Weekly remained positive in all three walk-forward periods.
- Top 10 Weekly also remained formally positive, but its edge nearly vanished in Period 3.
- Period 3 was materially weaker and was already flagged for later diagnostics.

The NATCOPHARM case should therefore be treated as a live example of a known strategic ambiguity: Swing V2.1 is not a strict above-EMA trend model. It is closer to a sector/ADX strength model with upside-extension risk controls.

## Interpretation

Current Swing V2.1 says:

> Avoid stocks that are already too extended upward, but allow stocks that may be early in a rebound or still below long-term trend.

That behavior can be useful in rebound regimes, but it can also produce recommendations that look uncomfortable during manual review because they are not aligned with a simple momentum/trend checklist.

## Potential Future V2.2 Experiments

These are research candidates only. They should not be applied to frozen Swing V2.1 without a separate design, implementation, and validation phase.

### Require Price Above EMA200

Rule:

```text
close >= ema_200
```

Expected effect:

- Removes below-EMA candidates.
- Makes the strategy more trend-following.
- May reduce rebound capture.

### Require EMA200 Extension >= 0

Rule:

```text
ema200_extension >= 0
```

Expected effect:

- Equivalent to requiring price at or above EMA200.
- Keeps the existing +25% upper cap.
- Narrows universe during weak markets.

### Require Prior 20d Return >= 0

Rule:

```text
prior_20d_return >= 0
```

Expected effect:

- Removes recently falling stocks.
- Makes the strategy more momentum-confirmed.
- May enter rebounds later.

### Separate Momentum And Reversal Modes

Possible split:

| Mode | Candidate Behavior | Example Filters |
| --- | --- | --- |
| Momentum mode | Trend continuation | `close >= ema_200`, `prior_20d_return >= 0` |
| Reversal mode | High-ADX rebound candidates | negative extension allowed, stricter risk controls |

Expected effect:

- Makes strategy intent explicit.
- Avoids mixing trend and rebound logic in one score.
- Requires separate validation and reporting to prevent hidden overfitting.

## Recommendation

Do not change frozen Swing V2.1.

Record NATCOPHARM as an expected behavior example and use it as a seed case for a future V2.2 research backlog. Any proposed lower-bound filter should be tested as a separate experiment against:

- Five-year pilot results.
- Walk-forward stability.
- Bear-regime performance.
- Rebound-regime capture.
- Turnover and transaction-cost sensitivity.

## Acceptance Confirmation

- Scoring unchanged.
- Thresholds unchanged.
- Recommendation logic unchanged.
- No backtests rerun.
- No production tables modified.
