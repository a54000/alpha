# Swing V2.1 Results

Date: 2026-06-11

## Objective

Report full backtest results for the separate research model:

```text
swing_v2_1
```

Output artifact:

- `reports/swing_v2_1_results.json`

## Model

Factors:

- Sector Rank
- ADX

Entry filters:

- EMA200 extension <= 25%
- Prior 20d return <= 15%

Execution:

- Signal after EOD close
- Entry at next-trading-day open
- Exit at fixed-horizon close
- Primary horizon: 20 trading days
- Benchmark aligned to each trade's entry/exit dates

## Backfill Summary

| Item | Value |
| --- | ---: |
| Score start date | 2024-06-10 |
| Score end date | 2026-06-09 |
| Score rows processed | 214,990 |
| Dates processed | 497 |
| Non-null Swing V2.1 scores | 143,294 |
| Recommendation dates | 471 |
| Swing V2.1 recommendations written | 7,248 |

## Primary 20-Day Comparison

| Model | Trade Count | Valid Count | Avg Return | Win Rate | Profit Factor | Alpha |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| V1 Swing | 2,045 | 1,911 | -0.5329% | 43.43% | 0.8850 | -0.1948% |
| Swing V2 | 7,189 | 6,870 | -0.0987% | 46.83% | 0.9767 | 0.1762% |
| Swing V2.1 | 7,241 | 7,056 | 0.4244% | 50.77% | 1.1283 | 0.4107% |

## Swing V2.1 Horizon Results

| Horizon | Trade Count | Valid Count | Avg Return | Win Rate | Profit Factor | Alpha |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 5d | 7,241 | 7,203 | 0.0630% | 47.81% | 1.0331 | 0.1922% |
| 10d | 7,241 | 7,168 | 0.2047% | 48.06% | 1.0836 | 0.2372% |
| 20d | 7,241 | 7,056 | 0.4244% | 50.77% | 1.1283 | 0.4107% |

## Improvement Versus V1

| Metric | V1 Swing | Swing V2.1 | Change |
| --- | ---: | ---: | ---: |
| Avg Return | -0.5329% | 0.4244% | +0.9573 pp |
| Win Rate | 43.43% | 50.77% | +7.33 pp |
| Profit Factor | 0.8850 | 1.1283 | +0.2433 |
| Alpha | -0.1948% | 0.4107% | +0.6055 pp |

## Improvement Versus Swing V2

| Metric | Swing V2 | Swing V2.1 | Change |
| --- | ---: | ---: | ---: |
| Avg Return | -0.0987% | 0.4244% | +0.5231 pp |
| Win Rate | 46.83% | 50.77% | +3.94 pp |
| Profit Factor | 0.9767 | 1.1283 | +0.1516 |
| Alpha | 0.1762% | 0.4107% | +0.2344 pp |

## Interpretation

Swing V2.1 outperformed both V1 Swing and Swing V2 on the primary 20-day horizon.

The model improved:

- average return
- win rate
- profit factor
- alpha

The result is directionally consistent with the prior research freeze:

- Sector Rank + ADX was the strongest core model.
- EMA200 extension filtering reduced overextension risk.
- Prior 20d return filtering reduced short-term chase risk.

## Caveats

This result is not production approval.

Known caveats:

- High survivorship-bias risk remains.
- Universe membership is not point-in-time clean.
- Transaction costs are not included.
- Slippage, brokerage, STT, and stamp duty are not included.
- Exit is fixed horizon only.
- No stop-loss, target, trailing stop, or rank-decay exit is modeled.
- Filters were selected from prior in-sample research.
- No forward out-of-sample validation has been run.

## Verdict

Swing V2.1 is now the strongest implemented Swing research model.

Status:

```text
Research model implemented and backtested.
Not production-approved.
```
