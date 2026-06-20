# Sector Points Guard Promotion

Status: promoted to active research/paper guard.

## Decision

The current Sector Rotation ADX Rolling 10 setup excludes candidates with:

```text
sector_points < 1
```

This means sectors ranked worse than the top 8 are not investable, even if the individual stock ADX is strong.

## Rationale

The system is a sector-rotation strategy. Allowing stocks from sectors with `sector_points = 0` creates a contradiction:

```text
Strong individual stock momentum, but weak sector backdrop.
```

The guard keeps the portfolio aligned with the strategy thesis.

## Validation

Source:

```text
results/sector_points_filter_comparison/SECTOR_POINTS_FILTER_COMPARISON.md
```

| Metric | Baseline | Sector points >= 1 |
| --- | ---: | ---: |
| CAGR | 26.09% | 25.99% |
| Max drawdown | -13.91% | -13.52% |
| Sharpe | 1.24 | 1.24 |
| Profit factor | 1.76 | 1.85 |
| Win rate | 58.41% | 59.13% |
| Closed trades | 416 | 389 |
| Average cash | 21.20% | 26.37% |

The guard slightly reduces CAGR, improves drawdown, profit factor, and win rate, and increases idle cash.

## Implementation

- Recommendation generation defaults to `--min-sector-points 1`.
- The Recommendations API suppresses existing rows with `sector_points <= 0`.
- The paper-trading pilot data source suppresses existing rows with `sector_points <= 0`.
- Historical baseline reports remain unchanged; filtered comparison reports are stored separately.

## Guardrail

This is a quality guard, not an optimization. Do not tune the threshold without a separate research comparison.
