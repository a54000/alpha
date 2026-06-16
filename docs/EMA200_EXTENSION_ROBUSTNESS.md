# EMA200 Extension Robustness

**Date:** 2026-06-11

**Objective:** Determine whether the 20% EMA200 extension cap is robust or a sample-specific threshold.

**Model:** Sector Rank + ADX

**Scope:** Research only. Production scoring was not modified.

## Input

- `reports/swing_top20_trade_ledger.csv`
- Supporting artifact: `reports/ema200_extension_robustness.json`

## Baseline

| Model | Trades | Avg Return | Win Rate | Profit Factor | Alpha |
|---|---:|---:|---:|---:|---:|
| Current Sector Rank + ADX | 9016 | 0.22% | 49.51% | 1.059 | 0.38% |

## Threshold Sweep

| EMA200 Extension Cap | Trade Count | Avg Return | Win Rate | Profit Factor | Alpha |
|---|---:|---:|---:|---:|---:|
| <= 5% | 3788 | 0.95% | 52.23% | 1.298 | 0.42% |
| <= 10% | 4603 | 0.67% | 51.00% | 1.202 | 0.27% |
| <= 15% | 5529 | 0.64% | 51.39% | 1.192 | 0.30% |
| <= 20% | 6384 | 0.68% | 51.55% | 1.204 | 0.48% |
| <= 25% | 7133 | 0.69% | 51.50% | 1.208 | 0.61% |
| <= 30% | 7736 | 0.68% | 51.40% | 1.201 | 0.66% |
| <= 35% | 8212 | 0.55% | 50.74% | 1.158 | 0.58% |
| <= 40% | 8500 | 0.41% | 50.21% | 1.115 | 0.50% |

## Performance Chart: Average Return

| Threshold | Avg Return |
|---|---|
| <= 5% | ######### 0.95% |
| <= 10% | ###### 0.67% |
| <= 15% | ###### 0.64% |
| <= 20% | ###### 0.68% |
| <= 25% | ###### 0.69% |
| <= 30% | ###### 0.68% |
| <= 35% | ##### 0.55% |
| <= 40% | #### 0.41% |

## Performance Chart: Profit Factor

| Threshold | Profit Factor |
|---|---|
| <= 5% | ############## 1.298 |
| <= 10% | ########## 1.202 |
| <= 15% | ######### 1.192 |
| <= 20% | ########## 1.204 |
| <= 25% | ########## 1.208 |
| <= 30% | ########## 1.201 |
| <= 35% | ####### 1.158 |
| <= 40% | ##### 1.115 |

## Interpretation

The result is robust, but not as a single precise 20% threshold.

Performance is strong across a range:

- `<= 5%`: highest average return and strongest profit factor, but fewer trades.
- `<= 10%` to `<= 20%`: stable positive returns and profit factors above 1.19.
- `<= 25%` to `<= 30%`: best balance of trade count, alpha, and stable profitability.
- `<= 35%` and `<= 40%`: performance begins to decay, though still better than the uncapped baseline.

This suggests the real effect is an extension zone, not a hard cliff at exactly 20%.

## Stability Assessment

| Question | Answer |
|---|---|
| Does performance improve smoothly? | Mostly. Performance is best under tight caps, stays strong through 30%, then decays after 30%. |
| Does a specific threshold exist? | No exact threshold. The stable range appears to be roughly 10-30%. |
| Is the result stable? | Yes. Every tested cap from 5% to 40% improves average return and profit factor versus the uncapped baseline. |
| Is 20% sample-specific? | 20% is not uniquely optimal. It is part of a robust range. |

## Optimal Threshold Range

The best practical range is:

```text
EMA200 extension cap: 20% to 30%
```

Reason:

- `<= 20%` improves average return to `0.68%` and profit factor to `1.204`.
- `<= 25%` has slightly higher average return, alpha, and profit factor with more trades.
- `<= 30%` has the highest alpha and still strong profit factor.
- Above 30%, average return and profit factor start deteriorating.

If prioritizing highest quality over trade count, `<= 5%` is strongest. If prioritizing robustness and usable opportunity count, `20-30%` is better.

## Recommendation

Do not modify production scoring from this document.

For the next research candidate, test EMA200 extension caps as a range rather than hard-code 20% immediately:

1. Conservative: `Close <= EMA200 * 1.20`
2. Balanced: `Close <= EMA200 * 1.25`
3. Broader: `Close <= EMA200 * 1.30`

Based on this sweep, `25%` may be the best balance point, while `20-30%` is the robust range.

No production scoring was modified.
