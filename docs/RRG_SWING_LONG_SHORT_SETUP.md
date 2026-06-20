# Standalone RRG Swing Long/Short Setup

This is a separate research setup from SectorEdge 10.

It can emit LONG and SHORT candidates, but it does not change SectorEdge 10 scoring, recommendations, paper trading, or live execution.

The setup is intended for top-down swing research where the market/sector context can support both long and short trades. It is not a replacement for the current SectorEdge 10 production/paper workflow.

## Key Decisions

- Uses 4-week relative strength for swing recency.
- Uses 12-week momentum while skipping the most recent week.
- Requires volume confirmation with volume ratio above 1.10.
- Uses ATR-based stop references.
- Scores proximity to the 21 EMA so extended entries are penalized.
- Lets RRG tail direction override a simple quadrant read.

## Signal Interpretation

- LONG requires a supportive sector state, rightward RRG tail, composite score above threshold, and volume confirmation.
- SHORT requires a weakening/lagging sector state, leftward RRG tail, composite score above threshold, and volume confirmation.
- A sector quadrant alone is not enough. Tail direction can downgrade a Leading sector or block fresh shorts in a Lagging sector that is turning right.
- Entry and stop values are references only: entry uses the latest close, and stop uses 1.5x ATR from that reference price.

## Command

```powershell
.\.venv\Scripts\python.exe scripts\generate_rrg_swing_long_short_setup.py --as-of 2026-06-18
```

## Latest Run

- Requested as-of: `2026-06-18`
- As of: `2026-06-12`
- Benchmark: `NIFTY50`
- LONG candidates: `0`
- SHORT candidates: `8`
- Total scored: `383`

The effective as-of date may be earlier than the requested date when benchmark index history is older than stock history. Current benchmark fallback is `NIFTY50` because NIFTY500 index history is not yet available in the local Angel index table.

Outputs:

- `D:\nse-research-app\reports\rrg_swing_long_short_setup.csv`
- `D:\nse-research-app\reports\rrg_swing_long_short_setup.json`

## Safety

Research only. No broker APIs. No production table updates. No SectorEdge 10 changes.
