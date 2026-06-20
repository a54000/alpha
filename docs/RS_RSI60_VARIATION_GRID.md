# RS + 60-Minute RSI Variation Grid

Research-only parameter neighborhood test. No production strategy or database state was changed.

## Best Variant

- RS lookback: 88 sessions
- Improvement lookback: 10 sessions
- RSI cap: 60.0
- Minimum relative-strength spread: 0.0

| Metric | Value |
| --- | ---: |
| CAGR | 26.05% |
| Total return | 150.15% |
| Max drawdown | -19.50% |
| Sharpe | 1.15 |
| Profit factor | 1.56 |
| Trades | 478 |

## Top 15 Variants

| Rank | RS | Improve | RSI Cap | Min RS | CAGR | Max DD | Sharpe | PF | Trades | Score |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 88 | 10 | 60 | 0.0 | 26.05% | -19.50% | 1.15 | 1.56 | 478 | 1.21 |
| 2 | 88 | 3 | 60 | 0.0 | 27.00% | -31.14% | 1.20 | 1.52 | 481 | 1.16 |
| 3 | 88 | 5 | 55 | 0.0 | 23.84% | -17.74% | 1.08 | 1.53 | 478 | 1.14 |
| 4 | 88 | 10 | 55 | 0.0 | 21.58% | -21.57% | 1.09 | 1.52 | 470 | 1.09 |
| 5 | 88 | 10 | 65 | 0.0 | 26.00% | -25.48% | 1.05 | 1.51 | 483 | 1.06 |
| 6 | 88 | 3 | 65 | 0.0 | 25.37% | -36.23% | 1.09 | 1.44 | 483 | 0.98 |
| 7 | 88 | 5 | 60 | 0.0 | 19.43% | -28.50% | 0.96 | 1.39 | 479 | 0.87 |
| 8 | 66 | 3 | 65 | 0.0 | 20.24% | -30.08% | 0.88 | 1.39 | 483 | 0.78 |
| 9 | 66 | 3 | 60 | 0.0 | 19.19% | -26.75% | 0.85 | 1.44 | 480 | 0.78 |
| 10 | 88 | 3 | 55 | 0.0 | 17.31% | -27.12% | 0.81 | 1.37 | 475 | 0.72 |
| 11 | 66 | 5 | 65 | 0.0 | 17.57% | -26.32% | 0.74 | 1.39 | 483 | 0.65 |
| 12 | 66 | 10 | 60 | 0.0 | 14.68% | -27.62% | 0.71 | 1.37 | 474 | 0.58 |
| 13 | 66 | 10 | 65 | 0.0 | 14.18% | -25.12% | 0.67 | 1.32 | 482 | 0.56 |
| 14 | 66 | 10 | 55 | 0.0 | 13.35% | -22.55% | 0.58 | 1.29 | 456 | 0.49 |
| 15 | 88 | 5 | 65 | 0.0 | 12.85% | -35.71% | 0.65 | 1.23 | 481 | 0.42 |

## Verdict

Best variant is promising enough for deeper validation against SectorEdge 10.

## Artifacts

- `results/rs_rsi60_variation_grid/variation_grid.csv`
- `results/rs_rsi60_variation_grid/summary.json`
