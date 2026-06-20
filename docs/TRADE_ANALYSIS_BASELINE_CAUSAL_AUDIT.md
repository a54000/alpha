# Trade Analysis Baseline Causal Audit

Date: 2026-06-19

## Objective

Determine whether the change from the stale trade-analysis baseline to the fixed report is explained only by the open-position / force-close accounting bug.

Conclusion: it is not.

## Reports Compared

Old stale report:

`reports/trade_analysis/20260618T173851Z_sector_rotation_adx_rolling10_sector_rotation_adx_1m3m_fb471857d9`

Fixed report:

`reports/trade_analysis/20260619T134542Z_sector_rotation_adx_rolling10_sector_rotation_adx_1m3m_6d33521edd`

## Headline Difference

| Metric | Old Report | Fixed Report |
| --- | ---: | ---: |
| CAGR | 27.49% | 22.65% |
| Total return | 162.70% | 125.18% |
| Max drawdown | -20.36% | -22.99% |
| FY2024-25 return | 34.23% | 21.58% |
| FY2024-25 closed trades | 97 | 111 |

The FY2024-25 overlap is too low for this to be a pure close-timing bug:

- Common `symbol + entry_date` trades: 59
- Old-only trades: 38
- Fixed-only trades: 52

## Code Changes Observed

The working copy contains changes beyond open-position export handling.

### Pure Accounting / Artifact Fixes

These are legitimate fixes for the previously misleading report:

- Open positions are exported separately to `open_positions.csv`.
- Remaining positions are no longer force-closed at report end.
- Ending value and CAGR are derived from equity curve mark-to-market, not closed-trade net PnL alone.
- Cache key includes `artifact_version = 2`.
- Cache validation now requires `open_positions.csv`, preventing stale report reuse.
- FY table now includes closed-trade counts and win rate.

### Non-Pure Changes That Can Affect Trade Membership

These can change which trades appear, or when they appear:

- `SECTOR_ROTATION_ADX_ROLLING10` uses `entry_price_field="entry_1030_open"`.
- The same strategy uses `previous_day_vwap_max_extension=0.025`.
- Trade analysis loads 10:30 entry prices from `ohlcv_15min`.
- Trade analysis now attaches previous-day VWAPs from `pilot_phase2a.daily_vwap` or derives them from `ohlcv_15min`.
- Recommendation loading now has model fallback behavior.
- Recommendation loading caps request end date to the latest available date for the selected model.
- `scripts/generate_sector_1m3m_pilot_recommendations.py` now filters via `reports/nifty500_expansion_universe_symbols.csv`.
- The recommendation generator now defaults to `--min-sector-points 1`.

Therefore, the fixed report should be treated as a regenerated baseline, not as an isolated force-close correction.

## FY2024-25 Boundary Check

March 2025 boundary positions do not explain the FY2024-25 swing.

| Boundary Check | Old | Fixed |
| --- | ---: | ---: |
| Cross-FY positions | 7 | 6 |
| Cross-FY net PnL | Rs -14,367 | Rs -33,771 |

Difference: about Rs -19,404.

FY-end equity difference: about Rs -283,069.

So the March boundary explains only a small fraction of the FY2024-25 change.

## Targeted Qualification Probe

The probe checked selected old-only and fixed-only trades against current recommendations, features, 10:30 entry price, and previous-day VWAP.

Artifacts:

- `reports/fy2024_25_reconciliation/current_qualification_probe.csv`
- `reports/fy2024_25_reconciliation/recent_recommendation_probe.csv`

### Old-only winners

Several old-only trades still appear to qualify under current recommendation/VWAP logic:

| Symbol | Entry Date | Current Signal Found | Rank | Score | VWAP Extension | Passes VWAP 2.5% |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| CAPLIPOINT | 2024-08-13 | yes | 3 | 82.86 | 1.57% | yes |
| SKFINDIA | 2024-05-07 | yes | 4 | 82.86 | -0.33% | yes |
| PTC | 2024-03-19 | yes | 3 | 88.57 | 0.93% | yes |
| CCL | 2024-08-13 | yes | 4 | 82.86 | 0.01% | yes |

KSCL had recent qualifying recommendations, but the nearest one before the old entry had mixed VWAP outcomes depending on signal date.

This means those old-only trades did not disappear simply because they fail current rules.

### Fixed-only trades

Several fixed-only trades also appear to qualify under current logic:

| Symbol | Entry Date | Current Signal Found | Rank | Score | VWAP Extension | Passes VWAP 2.5% |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| TEAMLEASE | 2024-05-22 | yes | 2 | 77.14 | 0.05% | yes |
| GODREJCP | 2024-10-15 | yes | 3 | 71.43 | 0.53% | yes |
| KARURVYSYA | 2024-12-10 | yes | 5 | 77.14 | -0.50% | yes |

GODREJIND and BAJAJELEC were not found in the current recommendation table within the prior 10 calendar days, which needs deeper trace if those trades remain important to the discrepancy.

## Likely Causal Story

The evidence points to a mixed cause:

1. The old report had a real accounting/export bug around open positions.
2. The fixed report also picked up broader implementation changes.
3. The trade set difference is mostly portfolio-path dependent rather than a simple per-trade qualification difference.

Portfolio-path dependency means:

- available cash changed,
- open slots changed,
- position sizing changed,
- held-symbol constraints changed,
- rank ordering competed differently for limited slots,
- later recommendations were accepted or skipped because earlier positions differed.

That can cascade through the entire FY.

## What We Can Trust Now

Do not trust the old headline:

- Old 27.49% CAGR is retired.
- Old FY2024-25 34.23% is retired.

The fixed 22.65% CAGR is the current regenerated baseline, but not yet an isolated accounting-fix baseline.

## Recommended Next Diagnostic

Create an A/B replay harness with three explicit modes:

1. `legacy_committed_engine`
   - Use committed `HEAD` reconstruction logic.
   - Use the same recommendation rows and price tables.

2. `accounting_fix_only`
   - Same entry, sizing, recommendation, VWAP, and slot logic as old engine.
   - Only change report-end open-position treatment.

3. `current_engine`
   - Use current 10:30/VWAP/open-position behavior.

Then compare:

- trade overlap,
- first divergence date,
- first different symbol entered,
- cash before divergence,
- position count before divergence,
- skipped recommendations and reason.

This is the cleanest way to separate:

- true accounting fix impact,
- entry/VWAP rule impact,
- recommendation data/regeneration impact,
- portfolio-path cascade impact.

## Status

This audit is read-only. No strategy logic, recommendations, tables, or historical data were modified.
