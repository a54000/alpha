# Rolling 10 1M/3M VWAP25 Frozen Candidate

Status: frozen research/paper candidate, separate from frozen Swing V2.1.

## Candidate ID

- Strategy mode: `sector_rotation_adx_r10_vwap25`
- Recommendation model: `sector_rotation_adx_1m3m`
- Paper data source: intended for `PAPER_TRADING_DATA_SOURCE=pilot_phase2a`
- Legacy Swing V2.1 mode remains: `swing_v2_1_rolling_10_slot`

## Rules

1. Generate candidates using the Sector Rotation ADX score with sector strength based only on 1-month and 3-month sector returns.
2. Sector rank score uses `40% * 1M sector return + 60% * 3M sector return`.
3. Select up to the top 5 weekly recommendations.
4. Maintain a rolling 10-slot portfolio.
5. Enter on the next trading day at the 10:30 15-minute candle open.
6. Skip entry if the 10:30 entry price is more than 2.5% above the signal day's full-day VWAP.
7. Hold each entered position for 20 trading days.
8. Exit only on planned holding-period completion.
9. Do not use stop-loss, RSI filter, daily fill-up, or calendar-month holding.

## Validation Snapshot

Source: `results/entry_1030_prevday_vwap_grid/ENTRY_1030_PREVDAY_VWAP_GRID.md`

- CAGR: 29.07%
- Max drawdown: -12.28%
- Sharpe: 1.35
- Sortino: 1.71
- Profit factor: 1.90
- Win rate: 56.45%
- Closed trades: 411
- Average cash: 22.13%
- Skipped entries: 28

## Rejected Alternatives

- Same-day VWAP filters were less clean for live use than previous-day VWAP.
- Daily fill-up improved cash use but worsened risk-adjusted behavior.
- 15-trading-day and one-calendar-month holding periods did not improve the final candidate.
- RSI skip did not justify inclusion.
- Stop-loss variants reduced CAGR without materially improving drawdown.

## Paper Trading Integration

Generate candidate recommendation rows without overwriting legacy V2.1:

```powershell
.\.venv\Scripts\python.exe scripts\generate_sector_1m3m_pilot_recommendations.py `
  --start-date 2022-05-25 `
  --end-date 2026-06-12
```

Use the new strategy mode explicitly:

```powershell
.\.venv\Scripts\python.exe -m app.paper_trading.daily_update `
  --cycle-date 2026-06-12 `
  --portfolio-id 1 `
  --data-source pilot_phase2a `
  --strategy-mode sector_rotation_adx_r10_vwap25 `
  --rebalance
```

Full daily pipeline with candidate paper mode:

```powershell
.\.venv\Scripts\python.exe scripts\run_full_daily_pipeline.py `
  --business-date 2026-06-12 `
  --portfolio-id 1 `
  --paper-strategy-mode sector_rotation_adx_r10_vwap25 `
  --rebalance-paper
```

For a separate paper portfolio:

```powershell
.\.venv\Scripts\python.exe scripts\initialize_paper_portfolio.py `
  --name "Rolling 10 1M3M VWAP25 Paper" `
  --strategy-mode sector_rotation_adx_r10_vwap25 `
  --initial-capital 1000000
```

The original Swing V2.1 paper mode is unchanged and remains the default.

## Operational Guardrails

- Do not overwrite `swing_v2_1` recommendations.
- Do not replace the existing Swing V2.1 paper portfolio unless explicitly requested.
- Keep this mode paper/research only until it completes live observation.
- No broker API integration or order placement is part of this candidate.
