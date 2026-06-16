# Fibonacci Loser-Cut Diagnostic

Status: research-only diagnostic. No production scoring, recommendations, paper trading, portfolio logic, or database rows were modified.

## Question

Can losing trades in **Sector Rotation ADX Rolling 10** be cut earlier using Fibonacci-derived downside/invalidation levels?

This diagnostic tested Fibonacci as a loser-cut mechanism, not as a new entry rule and not as a profit-taking rule.

## Baseline Tested

- Strategy: Sector Rotation ADX Rolling 10
- Variant: `rolling_10_1m3m_entry_1030_skip_prevday_vwap_25bp`
- Sector ranking: 40% 1-month + 60% 3-month sector strength
- Portfolio: Rolling 10 slots
- Entry: T+1 10:30 15-minute candle open
- VWAP filter: skip if entry is more than 2.5% above signal-day VWAP
- Planned exit: 20 trading days

## Fibonacci Stop/Invaldiation Levels Tested

For every completed trade:

1. Use the 20 trading rows before the signal date.
2. Calculate:
   - Swing low = minimum low in the lookback window
   - Swing high = maximum high in the lookback window
   - Swing range = swing high - swing low
3. Test early exit if price breaks below:
   - `swing_high_break`: prior 20-day swing high
   - `fib_0_786`: 78.6% retracement
   - `fib_0_618`: 61.8% retracement
   - `fib_0_500`: 50.0% retracement
4. A level is only used when it is below the actual entry price.
5. Intraday 15-minute lows are used to detect whether the level was hit.

## Output Artifacts

Generated under:

```text
results/fib_loser_cut_diagnostic/
```

Files:

- `fib_loser_cut_summary.csv`
- `fib_loser_cut_trade_diagnostic.csv`
- `fib_loser_cut_diagnostic.json`
- `FIB_LOSER_CUT_DIAGNOSTIC.md`

Script:

```text
scripts/run_fib_loser_cut_diagnostic.py
```

Run command:

```powershell
.\.venv\Scripts\python.exe scripts\run_fib_loser_cut_diagnostic.py
```

## Portfolio-Level Results

| Variant | CAGR | Total Return | Max DD | Sharpe Proxy | Profit Factor | Win Rate | Avg Return | Stop Hits | Winners Cut | Losers Cut |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Baseline | 28.55% | 174.76% | -8.90% | 3.91 | 1.90 | 56.45% | 2.61% | 0 | 0 | 0 |
| Swing high break | 26.27% | 155.66% | -9.37% | 3.58 | 1.85 | 49.15% | 2.31% | 49 | 30 | 19 |
| Fib 0.786 | 17.75% | 93.03% | -8.65% | 2.53 | 1.58 | 37.47% | 1.48% | 176 | 78 | 98 |
| Fib 0.618 | 17.01% | 88.17% | -14.46% | 2.31 | 1.50 | 36.74% | 1.37% | 201 | 81 | 120 |
| Fib 0.500 | 20.83% | 114.15% | -11.09% | 2.85 | 1.62 | 44.04% | 1.73% | 161 | 51 | 110 |

## Finding

Fibonacci loser cuts do catch some bad trades, but they cut too many eventual winners.

The best-looking early invalidation rule is `swing_high_break`, but even that:

- Cut 49 trades total
- Cut 19 losers
- Also cut 30 winners
- Reduced CAGR by 2.28 percentage points
- Reduced win rate from 56.45% to 49.15%
- Slightly worsened max drawdown from -8.90% to -9.37%
- Reduced profit factor from 1.90 to 1.85

The deeper retracement levels cut more losers, but they damage the system materially:

- `fib_0_786` cut 98 losers but also 78 winners and reduced CAGR by 10.80 percentage points.
- `fib_0_618` cut 120 losers but also 81 winners and worsened max drawdown materially.
- `fib_0_500` cut 110 losers but also 51 winners and reduced CAGR by 7.72 percentage points.

## Interpretation

The current strategy is momentum-based. Many eventual winners temporarily retrace below common Fib levels before continuing higher. A mechanical Fib invalidation rule exits too early and interferes with the strategy's winner-capture behavior.

This is consistent with the earlier Fibonacci profit-taking diagnostic:

- Immediate partial profit at 1.618 reduced average return.
- Downside Fib cuts also reduced portfolio-level performance.

Together, both diagnostics suggest that Fibonacci levels are useful as an observation layer, but not yet useful as hard trading rules.

## Answer

No, based on this diagnostic, losers should not be cut earlier using these simple Fibonacci levels.

The rules catch some losers, but the cost of cutting winners is larger than the benefit.

## What Might Still Be Worth Testing

If we continue with Fibonacci research, the next experiment should not be a simple stop at a fixed Fib retracement. Better candidates:

1. **Conditional Fib loser cut**
   - Only cut below swing high if the trade is also below VWAP or below EMA20/EMA50.

2. **Time-delayed Fib invalidation**
   - Ignore Fib breaks during the first 2-3 trading days.
   - Apply only after the trade has had time to confirm.

3. **Profit-protection only**
   - Activate Fib-based trailing only after the trade first reaches 1.272 or 1.618 extension.

4. **Loser-only pattern classifier**
   - Combine Fib break with low MFE, weak sector breadth, and failed ADX follow-through.

## Recommendation

Do not promote Fibonacci loser cuts into the current paper-trading strategy.

Keep the frozen candidate unchanged:

```text
Sector Rotation ADX Rolling 10
10:30 entry
Previous-day VWAP + 2.5% skip
20 trading-day planned exit
No Fibonacci stop
```

Fibonacci may still be useful for visual trade review and future composite diagnostics, but not as a standalone early-exit rule.
