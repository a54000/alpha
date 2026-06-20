# Improving Sector 20-Day Hold Backtest

Research-only study. No strategy, scoring, recommendation, or database state was changed.

## Setup

- Test window: `2025-06-17` to `2026-06-17`
- Sector filter: sectors in the RRG `Improving` quadrant on weekly signal date.
- Stock universe: all mapped stocks in those Improving sectors.
- Entry: next trading session 10:30 candle open.
- Exit: planned `20` trading-day hold, exit at daily close.

## Summary

| Metric | Value |
| --- | ---: |
| Trades | 2647 |
| Win rate | 51.42% |
| Average return | 1.01% |
| Median return | 0.25% |
| Average winner | 6.76% |
| Average loser | -5.08% |
| Profit factor | 1.41 |
| Trade-level Sharpe | 0.45 |

## Current Improving-Sector Stocks

| Sector | Stocks |
| --- | --- |
| CONSUMER GOODS | ABFRL, ASIANPAINT, BALRAMCHIN, BATAINDIA, BBTC, BERGEPAINT, BLUESTARCO, BRITANNIA, CCL, COLPAL, CROMPTON, DABUR, DCMSHRIRAM, DIXON, DMART, EMAMILTD, GILLETTE, GODFRYPHLP, GODREJCP, GODREJIND, HAVELLS, HINDUNILVR, ITC, JUBLFOOD, MARICO, RADICO, TITAN, TRENT, UBL, VBL, VOLTAS, WHIRLPOOL |
| SERVICES | 3MINDIA, ADANIPORTS, BLUEDART, CONCOR, EIHOTEL, GESHIP, INDHOTEL, INDIGO, LEMONTREE, MMTC, REDINGTON, SCI |

## Artifacts

- `results/improving_sector_20d_backtest/trades.csv`
- `results/improving_sector_20d_backtest/weekly_sector_states.csv`
- `results/improving_sector_20d_backtest/latest_improving_sector_stocks.csv`
- `results/improving_sector_20d_backtest/summary.json`
