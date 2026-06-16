# Swing Extension Risk Analysis

**Date:** 2026-06-11

**Objective:** Determine whether Swing model losses are caused by entering already-extended trends.

**Model:** Sector Rank + ADX

**Scope:** Research only. Production scoring was not modified.

## Inputs

- `reports/swing_top20_trade_ledger.csv`
- Supporting artifact: `reports/swing_extension_risk_analysis.json`

The analysis uses the full Top 20 Sector Rank + ADX ledger.

## Baseline

| Current Sector Rank + ADX | 9016 | 0.22% | 49.51% | 1.059 | 0.38% |

## Distance Above EMA50

| Bucket | Trades | Avg Return | Win Rate | Profit Factor | Alpha |
|---|---:|---:|---:|---:|---:|
| <0 | 3315 | 1.16% | 53.48% | 1.368 | 0.56% |
| 0-5% | 361 | 1.00% | 52.24% | 1.355 | 0.67% |
| 5-10% | 1738 | -0.56% | 47.72% | 0.853 | 0.14% |
| 10-15% | 1790 | -0.15% | 48.97% | 0.961 | 0.53% |
| 15-20% | 930 | -0.79% | 43.13% | 0.831 | 0.10% |
| 20%+ | 882 | -0.47% | 43.51% | 0.915 | 0.03% |

### EMA50 Interpretation

Performance is strongest when price is at or below EMA50, or only modestly above it. Once the stock is more than 5-10% above EMA50, performance weakens. The 15-20% and 20%+ buckets are negative.

## Distance Above EMA200

| Bucket | Trades | Avg Return | Win Rate | Profit Factor | Alpha |
|---|---:|---:|---:|---:|---:|
| <0 | 3356 | 1.05% | 53.18% | 1.330 | 0.52% |
| 0-10% | 1247 | -0.37% | 45.05% | 0.898 | -0.41% |
| 10-20% | 1781 | 0.71% | 53.04% | 1.208 | 1.05% |
| 20-30% | 1352 | 0.65% | 50.63% | 1.186 | 1.51% |
| 30-40% | 764 | -2.48% | 37.30% | 0.568 | -1.15% |
| 40%+ | 516 | -3.32% | 36.45% | 0.534 | -1.86% |

### EMA200 Interpretation

This is the clearest extension risk signal.

Performance deteriorates sharply when price is far above EMA200:

- 30-40% above EMA200: avg return `-2.48%`, profit factor `0.568`
- 40%+ above EMA200: avg return `-3.32%`, profit factor `0.534`

The 10-30% above EMA200 range is still positive, but extreme extension above 30% is harmful.

## Prior 20-Day Return

| Bucket | Trades | Avg Return | Win Rate | Profit Factor | Alpha |
|---|---:|---:|---:|---:|---:|
| <0 | 3334 | 1.16% | 53.48% | 1.371 | 0.57% |
| 0-5% | 360 | -0.28% | 44.51% | 0.927 | 0.72% |
| 5-10% | 1129 | -0.31% | 49.12% | 0.916 | 0.34% |
| 10-15% | 1347 | -0.40% | 48.36% | 0.895 | 0.26% |
| 15-20% | 1073 | -0.88% | 46.63% | 0.787 | -0.13% |
| 20%+ | 1753 | -0.02% | 45.56% | 0.996 | 0.42% |
| Unknown | 20 | -4.33% | 35.00% | 0.327 | -3.52% |

### Prior 20-Day Interpretation

The `15-20%` prior 20d bucket is clearly weak. The `20%+` bucket is roughly flat, not catastrophic, but it does not justify chasing large short-term moves. The best results come from stocks with negative prior 20d returns, suggesting pullbacks or resets inside strong sector/trend contexts may be healthier than chasing vertical moves.

## Prior 60-Day Return

| Bucket | Trades | Avg Return | Win Rate | Profit Factor | Alpha |
|---|---:|---:|---:|---:|---:|
| <0 | 3116 | 0.96% | 52.39% | 1.286 | 0.61% |
| 0-10% | 733 | -0.11% | 48.91% | 0.970 | 0.20% |
| 10-20% | 1319 | -0.01% | 48.31% | 0.997 | 0.62% |
| 20-30% | 1179 | -0.90% | 45.49% | 0.778 | 0.24% |
| 30-40% | 731 | -1.56% | 41.98% | 0.672 | -0.46% |
| 40%+ | 1118 | -1.57% | 40.73% | 0.721 | -0.62% |
| Unknown | 820 | 3.22% | 63.17% | 2.443 | 1.38% |

### Prior 60-Day Interpretation

Prior 60d extension is a strong risk signal.

The worst buckets are:

- 30-40% prior 60d return: avg return `-1.56%`, profit factor `0.672`
- 40%+ prior 60d return: avg return `-1.57%`, profit factor `0.721`

This supports the hypothesis that many losers come from entering trends after large prior moves.

## Research-Only Filter Tests

| Filter | Trades | Avg Return | Win Rate | Profit Factor | Alpha |
|---|---:|---:|---:|---:|---:|
| Current | 9016 | 0.22% | 49.51% | 1.059 | 0.38% |
| A: Prior 20d <= 15% | 6170 | 0.48% | 51.08% | 1.141 | 0.47% |
| B: Prior 60d <= 25% | 5854 | 0.40% | 50.26% | 1.114 | 0.52% |
| C: Distance above EMA50 <= 10% | 5414 | 0.60% | 51.56% | 1.180 | 0.43% |
| D: Distance above EMA200 <= 20% | 6384 | 0.68% | 51.55% | 1.204 | 0.48% |
| E: A + B + C | 4485 | 0.58% | 51.16% | 1.174 | 0.48% |

## Filter Interpretation

All tested extension filters improved the current model.

Best single filter by average return:

```text
D: Distance above EMA200 <= 20%
```

It improved:

- avg return from `0.22%` to `0.68%`
- profit factor from `1.059` to `1.204`
- alpha from `0.38%` to `0.48%`

Best single filter by profit factor is also Filter D.

Filter E, the combination of A+B+C, also improves results materially, but it does not beat the simpler EMA200 extension cap.

## Answers To Research Goal

### Does performance deteriorate once stocks become excessively extended?

Yes.

The clearest deterioration happens when stocks are:

- more than 30% above EMA200, or
- up more than 30-40% over the prior 60 trading days.

### Are losses caused by entering already-extended trends?

Often, yes.

The evidence from EMA200 distance and prior 60d return strongly supports extension risk as a major cause of losses.

### Which filter is most promising?

The most promising simple research filter is:

```text
Distance above EMA200 <= 20%
```

It is simple, intuitive, and produced the strongest single-filter improvement.

## Recommendation

Do not modify production scoring from this research document.

For the next research step, test a Sector Rank + ADX candidate with an extension-risk guardrail, especially:

```text
Close <= EMA200 * 1.20
```

Also consider testing:

- Prior 60d return <= 25%
- Distance above EMA50 <= 10%
- Combined extension filters with portfolio-size concentration

No production scoring was modified.
