# SectorEdge 10 Validated Baseline Audit

Date: 2026-06-20

## Purpose

This document consolidates the backtest audit that followed the discovery of a trade-analysis reporting bug. It defines the current accepted SectorEdge 10 baseline, separates validated mechanics from provisional data constraints, and prevents the headline performance number from being quoted without its caveats.

## Accepted Baseline Configuration

Current candidate baseline:

- Strategy name: SectorEdge 10
- Universe: currently available expanded ready universe, 386 symbols
- Entry timing: next trading day 10:30 candle open
- Entry quality filter: skip if 10:30 entry price is more than 2.5% above prior trading day VWAP
- Sector rank input: 1M/3M blend, 40% 1M and 60% 3M
- Minimum sector points: 1
- Portfolio construction: rolling 10 slots
- Holding period: planned 20 trading days
- Exit: planned holding-period exit only
- Broker/API execution: none; paper/research only

## Decision Table

| Component | Decision | Confidence | Reason |
| --- | --- | --- | --- |
| Force-close reporting bug | Fixed, old reports retired | High | Open positions are now exported separately and no longer force-closed into completed trades. |
| 10:30 + prior-day VWAP filter | Keep | High | Works in FY2024-25 and FY2025-26, survives robustness tests, and matches intraday mechanism on IDBI/BALKRISIND. |
| `min_sector_points=1` | Keep as candidate baseline | Medium | Improves return in both tested FYs, but behaves as reranking/eligibility, not clean risk reduction. |
| Expanded 386-symbol universe | Use current available data | Provisional | This is the best available NSE500 coverage, not a fully point-in-time complete universe. |
| Recommendation fallback / end-date cap | No effect on normal reports | High | Current loader matches strict model/date loader for audited windows. |
| Missing-bar mark-to-market valuation | Fixed | High | Open positions now carry forward latest available close for valuation when one symbol has a missing daily bar on a valid portfolio date. |
| Old 26-27% CAGR | Retired | High | It came from a contaminated report path. |

## Audit Findings

### Force-Close Reporting Bug

The original FY2026-27 drawdown was a reporting artifact caused by open positions being represented as completed trades. The export path now separates:

- `trades.csv`: closed trades only
- `open_positions.csv`: mark-to-market open positions

Old reports should not be used as evidence.

### Missing-Bar Mark-To-Market Bug

During the final full-history rerun, a second reporting issue was found around the FY2023-24/FY2024-25 boundary.

RPOWER was an open position on 2024-03-28, but `pilot_phase2a.daily_bars_clean` had no RPOWER row for that date. The previous equity-curve valuation logic ignored any open position without a current-date bar, effectively valuing that position at zero for the day. This created a false one-day equity hole and overstated full-history drawdown.

The fix is valuation-only:

- entries still require a real entry-date price,
- exits still require a real close on or after the planned exit date,
- open-position mark-to-market now carries forward the latest available close when a symbol is missing a daily bar on an otherwise valid portfolio valuation date.

Boundary check after the fix:

| Date | Equity | Cash | Open Positions |
| --- | ---: | ---: | ---: |
| 2024-03-27 | 1,703,056.20 | 3,707.16 | 10 |
| 2024-03-28 | 1,718,629.60 | 3,707.16 | 10 |
| 2024-04-01 | 1,770,557.64 | 3,707.16 | 10 |

### VWAP Filter

The strongest validated improvement is the combination of:

- wait until 10:30,
- then reject entries more than 2.5% above prior-day VWAP.

This was tested against both FY2024-25 and FY2025-26.

| Period | 10:30 No VWAP | 10:30 + VWAP |
| --- | ---: | ---: |
| FY2024-25 return | 18.27% | 24.03% |
| FY2025-26 return | -5.26% | 5.44% |

Robustness checks showed:

- FY2025-26 advantage remained positive after removing the best VWAP-case winner.
- Removed trades had low precision cost relative to avoided loss.
- IDBI and BALKRISIND were below or near threshold at 09:15, but clearly above threshold by 10:30.

Conclusion: this is a real entry-quality mechanism, not just a curve-fit artifact.

### Sector Points Guard

`min_sector_points=1` removes zero-sector-point candidates. It is useful, but less clean than VWAP.

| Period | Min 0 Return | Min 1 Return |
| --- | ---: | ---: |
| FY2024-25 | 20.98% | 24.03% |
| FY2025-26 | 4.99% | 6.71% |

Trade drilldown showed:

- FY2024-25 removed trades were still profitable.
- FY2025-26 removed trades were negative, but replacement trades were also negative.
- The rule changes path/ranking and sector eligibility rather than simply filtering bad trades.

Decision: keep in the candidate baseline because it improves both audited years, but label confidence as medium.

### VWAP + Sector Guard Interaction

Final interaction test fixed 10:30 entry and compared all four combinations.

| Period | Min0 No VWAP | Min0 VWAP | Min1 No VWAP | Min1 VWAP |
| --- | ---: | ---: | ---: | ---: |
| FY2023-24 return | 38.18% | 38.39% | 44.33% | 44.63% |
| FY2024-25 return | 15.81% | 20.98% | 18.27% | 24.03% |
| FY2025-26 return | -2.21% | 4.99% | -4.10% | 6.71% |

Conclusion:

- VWAP is robust under both sector-guard settings.
- The accepted `min1 + VWAP` combination is best return in all three audited FYs.
- The sector guard is more useful when paired with VWAP than when evaluated alone.

### Universe Coverage

The current expanded ready universe has 386 usable symbols. This is not the full intended NSE500 history.

The 285-symbol universe should not be treated as a preferred strategy design. It was an earlier data-availability subset. The correct framing is:

- current results are based on best available coverage,
- full NSE500 point-in-time history is not yet complete,
- absolute CAGR and drawdown remain provisional until coverage improves.

Revisit trigger:

- rerun full baseline when usable coverage reaches at least 450 symbols, or
- rerun when missing historical backfill for current NSE500 constituents is materially complete, or
- rerun after each additional 50 usable symbols are added.

### Recommendation Loading

The recommendation loader was audited against a strict model/date query.

For FY2024-25, FY2025-26, and the full current report window:

- fallback was not used,
- current rows matched strict rows,
- no hidden model substitution occurred.

End-date capping only applies when the user asks for a future date beyond available recommendations.

## Performance Number Policy

Do not quote any CAGR without the configuration and caveat.

Correct wording:

> SectorEdge 10 candidate baseline, using current 386-symbol available universe, 10:30 entry, prior-day VWAP extension filter, and min-sector-points guard, remains provisional pending fuller NSE500 history.

Avoid:

> Strategy CAGR is 26%.

Avoid:

> Strategy CAGR is 22.65%.

Those figures came from contaminated or mixed report states. The 22.65% report (`20260619T134542Z_sector_rotation_adx_rolling10_sector_rotation_adx_1m3m_6d33521edd`) is especially not comparable to the accepted baseline: although it was requested with `recommendation_model=sector_rotation_adx_1m3m`, its metadata shows `recommendation_source_model=swing_v2_1`, 9,567 recommendation rows, and 400 symbols. The accepted completed-FY rerun uses `recommendation_source_model=sector_rotation_adx_1m3m`, 7,207 recommendation rows, and 386 symbols.

## Final Rerun Sanity Check

After the completed-FY rerun, a concern was raised that CAGR moved from the retired 22.65% report to 26.63%.

That move is not attributable to the missing-bar mark-to-market fix alone.

An isolated in-memory A/B using the same request, same recommendations, same prices, and only changing valuation behavior showed:

| Case | CAGR | Max Drawdown | Ending Value | Closed Trades |
| --- | ---: | ---: | ---: | ---: |
| Old valuation: missing bar valued as zero | 26.57% | -19.64% | 2,430,781.43 | 399 |
| Carry-forward valuation | 26.63% | -14.69% | 2,435,539.48 | 399 |
| Difference | +0.07 pp | +4.95 pp | +4,758.06 | 0 |

Interpretation:

- The mark-to-market fix materially corrects drawdown because 906 portfolio valuation dates had at least one open-position price gap.
- It has only a small effect on full-period CAGR in the accepted SectorEdge setup.
- The large difference from 22.65% to 26.63% is explained by comparing different report states: the retired 22.65% report used fallback/mixed recommendation data and should not be treated as the previous value of the accepted baseline.

## Final Accepted Reruns

The full-history reports were regenerated under the accepted baseline configuration:

- expanded ready universe,
- `min_sector_points=1`,
- 10:30 entry,
- prior-day VWAP 2.5% filter,
- rolling 10 slots,
- 20 trading-day planned hold.

### Completed-FY Baseline

Report ID:

`20260620T062200Z_sector_rotation_adx_rolling10_sector_rotation_adx_1m3m_28bd1295ee`

Range: 2022-05-25 to 2026-03-31

| Metric | Value |
| --- | ---: |
| Ending value | 2,435,539.48 |
| Total return | 143.55% |
| CAGR | 26.63% |
| Max drawdown | -14.69% |
| Closed trades | 399 |
| Open positions at cutoff | 5 |
| Open unrealized PnL | -13,924.67 |
| Win rate | 55.89% |

Financial-year returns:

| FY | Return | Closed Trades | Win Rate |
| --- | ---: | ---: | ---: |
| FY2022-23 | 6.77% | 79 | 50.63% |
| FY2023-24 | 61.75% | 111 | 63.96% |
| FY2024-25 | 34.18% | 101 | 58.42% |
| FY2025-26 | 3.57% | 108 | 49.07% |

### Latest Available Baseline

Report ID:

`20260620T062121Z_sector_rotation_adx_rolling10_sector_rotation_adx_1m3m_74ee93fec5`

Range: 2022-05-25 to 2026-06-19

| Metric | Value |
| --- | ---: |
| Ending value | 2,804,628.13 |
| Total return | 180.46% |
| CAGR | 29.54% |
| Max drawdown | -14.69% |
| Closed trades | 415 |
| Open positions | 8 |
| Open unrealized PnL | 108,904.43 |
| Win rate | 56.39% |

Financial-year returns:

| FY | Return | Closed Trades | Win Rate |
| --- | ---: | ---: | ---: |
| FY2022-23 | 6.77% | 79 | 50.63% |
| FY2023-24 | 61.75% | 111 | 63.96% |
| FY2024-25 | 34.18% | 101 | 58.42% |
| FY2025-26 | 3.57% | 108 | 49.07% |
| FY2026-27 partial | 14.15% | 16 | 68.75% |

The app should display the completed-FY baseline as the cleaner long-history anchor and may show the latest-available result separately as a live/current-period view. Both must carry the universe caveat.

## Remaining Caveats

- Current universe is not full point-in-time NSE500 history.
- Liquidity is acceptable at Rs 10L portfolio size, but capacity should be retested before scaling.
- No live-trading execution slippage has been validated.
- No broker orders are placed by this system.
- Short-side and standalone Market Lens/RRG long-short setup are separate research tracks and are not part of SectorEdge 10 baseline.

## Artifacts

- `reports/vwap_false_negative_audit/VWAP_FALSE_NEGATIVE_AUDIT.md`
- `reports/vwap_edge_robustness/VWAP_EDGE_ROBUSTNESS.md`
- `reports/min_sector_points_bisection/MIN_SECTOR_POINTS_BISECTION.md`
- `reports/min_sector_points_drilldown/MIN_SECTOR_POINTS_DRILLDOWN.md`
- `reports/vwap_sector_guard_interaction/VWAP_SECTOR_GUARD_INTERACTION.md`
- `reports/recommendation_loading_audit/RECOMMENDATION_LOADING_AUDIT.md`
- `reports/universe_expansion_bisection/UNIVERSE_EXPANSION_BISECTION.md`
- `reports/trade_analysis/20260620T062200Z_sector_rotation_adx_rolling10_sector_rotation_adx_1m3m_28bd1295ee/summary.md`
- `reports/trade_analysis/20260620T062121Z_sector_rotation_adx_rolling10_sector_rotation_adx_1m3m_74ee93fec5/summary.md`
