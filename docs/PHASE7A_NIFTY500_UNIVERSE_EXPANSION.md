# Phase 7A Nifty 500 Universe Expansion Audit

Read-only audit. No data was downloaded, no tables were modified, and no strategy logic was changed.

## Summary

- Nifty 500 symbols in source file: `501`
- Currently usable in pilot features: `386`
- Not ready: `115`
- Token coverage: `82.83%`
- Pilot feature coverage: `77.05%`

## Gap Reasons

| Reason | Count | Meaning |
| --- | ---: | --- |
| missing_angel_token | 86 | No Angel token was found in config/angel_symbol_token_map.csv. |
| needs_angel_backfill | 29 | Token exists, but no 15-minute candles exist in angel_data.ohlcv_15min. |
| usable | 386 | Token, candles, daily bars, and features exist. |

## Safe Expansion Path

1. Resolve `missing_angel_token` symbols first.
2. Backfill `needs_angel_backfill` symbols using Angel historical sync.
3. Run daily aggregation for symbols with candles but no daily bars.
4. Run feature generation and sector mapping.
5. Re-run this audit until usable coverage is acceptable.

## Generated Reports

- `reports/nifty500_universe_gap.csv`
- `reports/nifty500_token_coverage.csv`
- `reports/nifty500_backfill_status.csv`
- `reports/nifty500_universe_expansion_audit.json`
