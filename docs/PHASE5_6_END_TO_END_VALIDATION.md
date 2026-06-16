# Phase 5.6 End-to-End Paper Trading Cycle Validation

## Objective

Run one controlled paper trading cycle for frozen Swing V2.1 and validate the data, decision, portfolio, and dashboard layers without changing strategy, scoring, recommendation rules, broker integration, or order behavior.

## Execution Summary

| Item | Result |
| --- | --- |
| Execution date | 2026-06-12 |
| Business date validated | 2026-06-11 |
| Portfolio ID | 1 |
| Portfolio | Swing V2.1 Rolling 10 Slot Paper |
| Mode | Existing daily pipeline and existing phase scripts |
| Broker APIs connected | No |
| Orders placed | No |
| Strategy changed | No |
| Scoring changed | No |
| Recommendation rules changed | No |

The controlled cycle completed after recovery from an initial orchestrator timeout during feature generation. The timeout left the feature table empty, so the existing feature-generation script was rerun once to restore `pilot_phase2a.features_daily`, then the existing orchestrator was resumed from scoring through monitoring.

## Commands Executed

Initial orchestrator attempt:

```powershell
.\.venv\Scripts\python.exe scripts\run_full_daily_pipeline.py --business-date 2026-06-11 --portfolio-id 1 --portfolio-size 10 --max-candidate-rank 5 --sync-dry-run --rebalance-paper --output-json reports\phase5_6_full_daily_pipeline_2026-06-11.json
```

The command exceeded the command timeout while running feature generation. Duplicate timed-out subprocesses were stopped to avoid competing writes.

Feature generation recovery:

```powershell
.\.venv\Scripts\python.exe scripts\run_phase2b_pilot_feature_generation.py --pilot-schema pilot_phase2a --output-json reports\phase5_6_feature_validation.json --coverage-csv reports\phase5_6_feature_coverage_by_symbol.csv --nulls-csv reports\phase5_6_feature_null_rates.csv
```

Resume from scoring:

```powershell
.\.venv\Scripts\python.exe scripts\run_full_daily_pipeline.py --business-date 2026-06-11 --portfolio-id 1 --portfolio-size 10 --max-candidate-rank 5 --sync-dry-run --rebalance-paper --from-step swing_v2_1_scoring --output-json reports\phase5_6_full_daily_pipeline_2026-06-11_resume.json
```

## Pipeline Step Results

| Step | Status | Started | Completed | Notes |
| --- | --- | --- | --- | --- |
| Angel data sync | Success | 2026-06-12 22:18:16 | 2026-06-12 22:18:17 | Existing `--sync-dry-run` path used because Angel symbol-token map is not configured. |
| Market data validation | Success | 2026-06-12 22:18:17 | 2026-06-12 22:19:59 | Generated Phase 4B market-data validation reports. |
| Daily bar refresh | Success | 2026-06-12 22:19:59 | 2026-06-12 22:20:18 | Generated Phase 4B cleaning outputs. |
| Feature generation | Success after recovery | 2026-06-12 | 2026-06-12 | Existing feature script restored 344,597 feature rows. Not recorded in `pipeline_runs` because it was run directly after timeout recovery. |
| Swing V2.1 scoring | Success | 2026-06-12 22:32:15 | 2026-06-12 22:36:04 | Existing orchestrator resumed from this step. |
| Recommendation generation | Success | 2026-06-12 22:36:04 | 2026-06-12 22:36:49 | Existing production-parity recommendation generation used. |
| Decision journal capture | Success | 2026-06-12 22:36:49 | 2026-06-12 22:36:50 | 8 snapshots written. |
| Paper portfolio update | Success | 2026-06-12 22:36:50 | 2026-06-12 22:36:52 | One NAV snapshot created. No trades created. |
| Monitoring report generation | Success | 2026-06-12 22:36:52 | 2026-06-12 22:36:59 | `reports/daily_paper_report_2026-06-11.md` generated. |

## Data Layer Validation

| Check | Result |
| --- | --- |
| Latest Angel 15-minute candle | 2026-06-12 11:45:00+05:30 |
| Latest cleaned daily bars | 2026-06-11 |
| Cleaned daily bars on latest date | 281 |
| Latest features date | 2026-06-11 |
| Feature rows on latest date | 281 |
| Total feature rows | 344,597 |
| Latest scores date | 2026-06-11 |
| Score rows on latest date | 281 |
| Latest recommendations date | 2026-06-11 |
| Recommendation rows on latest date | 8 |

Feature generation recovery report:

- `reports/phase5_6_feature_validation.json`
- `reports/phase5_6_feature_coverage_by_symbol.csv`
- `reports/phase5_6_feature_null_rates.csv`

## Decision Layer Validation

| Check | Result |
| --- | --- |
| Decision journal entries for 2026-06-11 | 8 |
| Explanation API | HTTP 200 |
| Example explanation route | `/recommendations/ELGIEQUIP/explanation` |

Top journal entries:

| Rank | Symbol | Score |
| --- | --- | --- |
| 1 | ELGIEQUIP | 77.1429 |
| 2 | NATCOPHARM | 77.1429 |
| 3 | CENTRALBK | 71.4286 |
| 4 | CONCOR | 71.4286 |
| 5 | EIDPARRY | 71.4286 |

## Portfolio Layer Validation

| Check | Result |
| --- | --- |
| Paper portfolio update status | Success |
| Paper positions | 0 |
| Open paper positions | 0 |
| Trades recorded | 0 |
| Daily snapshots | 1 |
| Snapshot for 2026-06-11 | 1 |
| Portfolio cash | 1,000,000.00 |
| Portfolio NAV | 1,000,000.00 |
| Benchmark captured | No benchmark value for 2026-06-11 in research `index_prices_daily` |

No rebalance trades were created. The paper engine reads production `recommendation_history` and `prices_daily`; those production research tables do not currently contain 2026-06-11 recommendation/price rows, while the live recommendation UI reads from the Angel pilot tables. The update still produced a valid NAV snapshot with all cash and no open positions.

## Dashboard Layer Validation

Backend API checks:

| Endpoint | Status |
| --- | --- |
| `/health` | 200 |
| `/dashboard` | 200 |
| `/recommendations/latest` | 200 |
| `/recommendations/ELGIEQUIP/explanation` | 200 |
| `/portfolio` | 200 |
| `/pipeline/status` | 200 on retry with longer timeout |
| `/research/metrics` | 200 |

Frontend route checks:

| Route | Status |
| --- | --- |
| `/` | 200 |
| `/recommendations` | 200 |
| `/recommendations/ELGIEQUIP/explanation` | 200 |
| `/portfolio` | 200 |
| `/operations` | 200 |
| `/research` | 200 |

## Reports Generated

| Report | Purpose |
| --- | --- |
| `reports/phase5_6_feature_validation.json` | Feature-generation recovery validation |
| `reports/phase5_6_feature_coverage_by_symbol.csv` | Feature coverage by symbol |
| `reports/phase5_6_feature_null_rates.csv` | Feature null-rate analysis |
| `reports/phase5_6_full_daily_pipeline_2026-06-11_resume.json` | Resumed orchestrator result from scoring through monitoring |
| `reports/phase5_1_decision_journal_capture.json` | Decision journal capture result |
| `reports/daily_paper_report_2026-06-11.md` | Daily paper monitoring report |

## Warnings

1. The first full orchestrator attempt timed out during feature generation and produced duplicate long-running subprocesses. They were stopped, then feature generation was recovered by running the existing feature-generation script once.
2. `pipeline_runs` contains 8 tracked successful steps for 2026-06-11. The recovered feature-generation step succeeded but is not represented as a `pipeline_runs` row because it was run directly after timeout recovery.
3. Angel sync was run through the existing `--sync-dry-run` mode. Live sync requires an Angel symbol-token map, which is not currently configured in `.env`.
4. Paper trading created a NAV snapshot but no positions or trades because the paper service currently reads production `recommendation_history` and `prices_daily`, while the latest pilot recommendations are in `angel_data.pilot_phase2a.recommendations_daily`.
5. Benchmark close and benchmark return are `n/a` for the 2026-06-11 paper snapshot because the research benchmark table does not have that date.

## Result

Phase 5.6 validated that the data, decision journal, API, frontend, and monitoring layers can run end to end against the current Angel pilot data through 2026-06-11. The portfolio update path executed and created a daily snapshot, but no simulated entries occurred because production research recommendation and price tables are not aligned with the pilot recommendation source used by the dashboard.

Recommended next operational fix: align the paper trading update source with the frozen Phase 2D pilot recommendations or load the approved recommendation feed into `recommendation_history` before expecting live paper entries.
