# 30-Day Paper Trading Observation Start

## Start Status

- Observation status: READY TO START ON NEXT SCHEDULED RUN
- Scheduled task: NSE Research Daily Paper Pipeline
- Schedule: Monday-Friday at 18:30 IST
- Next scheduled run: 2026-06-15 18:30
- Portfolio ID: 1
- Broker orders enabled: no
- Strategy/scoring changed: no

## Controlled Run Completed

Business date: 2026-06-12

| Step | Status | Started | Completed |
| --- | --- | --- | --- |
| angel_data_sync | success | 2026-06-14 08:34:08.478961 | 2026-06-14 08:40:08.494471 |
| market_data_validation | success | 2026-06-14 08:40:08.518782 | 2026-06-14 08:41:50.867974 |
| daily_bar_refresh | success | 2026-06-14 08:41:50.871463 | 2026-06-14 08:42:13.561504 |
| feature_generation | success | 2026-06-14 08:42:13.565537 | 2026-06-14 08:52:09.703610 |
| swing_v2_1_scoring | success | 2026-06-14 08:52:09.706779 | 2026-06-14 08:57:37.962786 |
| recommendation_generation | success | 2026-06-14 08:57:37.970303 | 2026-06-14 08:58:45.663277 |
| decision_journal_capture | success | 2026-06-14 08:58:45.669160 | 2026-06-14 08:58:47.001504 |
| paper_portfolio_update | success | 2026-06-14 08:58:47.005578 | 2026-06-14 08:58:49.310243 |
| monitoring_report_generation | success | 2026-06-14 08:58:49.312873 | 2026-06-14 08:58:56.795211 |

## Data Freshness

- max_15m: 2026-06-13 15:15:00+05:30
- max_daily: 2026-06-12
- max_features: 2026-06-12
- max_scores: 2026-06-12
- max_recs: 2026-06-12

## Latest Recommendations

| Rank | Symbol | Score | Sector |
| ---: | --- | ---: | --- |
| 1 | ELGIEQUIP | 82.86 | INDUSTRIAL MANUFACTURING |

## Portfolio State

- Portfolio: Swing V2.1 Rolling 10 Slot Paper
- Status: active
- Cash: 1000000.00
- NAV: 1000000.00
- Decision journal snapshots for 2026-06-12: 1

Recent snapshots:

| Date | NAV | Cash | Open Positions |
| --- | ---: | ---: | ---: |
| 2026-06-13 | 1000000.00 | 1000000.00 | 0 |
| 2026-06-12 | 1000000.00 | 1000000.00 | 0 |
| 2026-06-11 | 1000000.00 | 1000000.00 | 0 |

## Known Caveat

The 2026-06-12 recommendation was processed, but no paper entry was created because the paper engine requires the next trading-day open after the signal date. The latest cleaned daily bar currently ends at 2026-06-12, so the next valid entry can occur after the next trading session is ingested.

## Artifacts

- reports/phase4b_full_daily_pipeline_2026-06-12.json
- reports/daily_paper_report_2026-06-12.md
- reports/phase3f_angel_daily_sync.json