# Fibonacci Extension Exit Diagnostic

Status: research-only diagnostic. No production scoring, recommendation, paper-trading, or portfolio rules were changed.

## Objective

Evaluate whether Fibonacci extensions should be added to the current **Sector Rotation ADX Rolling 10** candidate as an exit/profit-management layer.

The diagnostic tested Fibonacci extensions as exits, not as new entry signals.

## Strategy Baseline Tested

- Variant: `rolling_10_1m3m_entry_1030_skip_prevday_vwap_25bp`
- User-facing strategy: Sector Rotation ADX Rolling 10
- Sector ranking: 40% 1-month sector strength + 60% 3-month sector strength
- Portfolio: Rolling 10 slots
- Entry: T+1 10:30 candle open
- Entry quality filter: skip if entry is more than 2.5% above signal-day VWAP
- Planned exit: 20 trading days

## Fibonacci Method

For each completed historical trade:

1. Identify the signal date.
2. Use the 20 trading rows before signal date.
3. Define:
   - Swing low = minimum low in the lookback window
   - Swing high = maximum high in the lookback window
   - Swing range = swing high - swing low
4. Compute extensions:
   - 1.272
   - 1.618
   - 2.000
5. Check whether each extension was reached during the existing 20-trading-day holding window.
6. Compare current planned-exit return with a hypothetical partial-profit rule:
   - Sell 50% at 1.618 if reached
   - Hold remaining 50% to planned 20-day exit

All comparisons use the existing Zerodha-style charge model.

## Output Artifacts

Generated under:

```text
results/fib_extension_exit_diagnostic/
```

Files:

- `fib_extension_trade_diagnostic.csv`
- `fib_extension_exit_diagnostic.json`
- `FIB_EXTENSION_EXIT_DIAGNOSTIC.md`

The script is:

```text
scripts/run_fib_extension_exit_diagnostic.py
```

Run command:

```powershell
.\.venv\Scripts\python.exe scripts\run_fib_extension_exit_diagnostic.py
```

## Summary Results

| Metric | Result |
| --- | ---: |
| Total trades | 411 |
| Diagnosable trades | 411 |
| Current average net return | 2.61% |
| 50% at 1.618 average net return | 2.32% |
| Aggregate return delta | -117.50 percentage points |
| Losers entered above 1.272 | 3 |
| Losers entered above 1.618 | 0 |

## Extension Hit Rates

| Extension | Hit Count | Hit Rate | Winner Hit Rate | Loser Hit Rate | Entries Already Above Level |
| --- | ---: | ---: | ---: | ---: | ---: |
| 1.272 | 200 | 48.66% | 70.26% | 20.67% | 8 |
| 1.618 | 116 | 28.22% | 44.83% | 6.70% | 0 |
| 2.000 | 67 | 16.30% | 27.16% | 2.23% | 0 |

## Interpretation

Fibonacci extensions are informative, but the first tested rule is not an upgrade.

The 1.618 extension is reached by many winners and only a small share of losers, which means it has some signal value. However, selling 50% at 1.618 reduced average trade return from 2.61% to 2.32%.

That reduction happened because the strategy's best winners often kept running after 1.618. Partial profit-taking helped some trades that later reversed, but it cut too much upside from large winners such as IFCI, FINCABLES, SCHAEFFLER, EMAMILTD, and other high-momentum trades.

The overextended-entry idea also does not look strong from this first pass:

- Only 8 trades entered above 1.272.
- Only 3 losing trades entered above 1.272.
- No trades entered above 1.618.

So a simple "skip if already above 1.272 or 1.618" rule is unlikely to explain many losers.

## Finding

Do not add the 50% profit-at-1.618 rule to the frozen candidate.

The current 20-trading-day hold appears to be doing important winner capture. A mechanical Fib partial exit reduces some giveback, but the lost upside from large winners is currently larger than the protection benefit.

## Better Next Tests

If Fibonacci is explored further, the next tests should be narrower:

1. **Trail only after 1.618**
   - Do not sell immediately at 1.618.
   - Activate a trailing stop only after 1.618 is reached.

2. **Use 2.000 as a profit-management trigger**
   - 1.618 may be too early for this strategy.
   - A 2.000 trigger may protect only very extended winners.

3. **Giveback-based exit after extension**
   - If price reaches 1.618 and then gives back 30-40% of open profit, exit.
   - This preserves winner participation better than fixed partial exits.

4. **Apply Fib logic only to extreme MFE trades**
   - Use Fib levels as an alert/risk-management overlay, not a universal exit.

## Recommendation

Keep the current frozen candidate unchanged.

Fibonacci extensions should remain a research overlay for winner management. The first tested partial-profit rule does not justify promotion into paper trading.
