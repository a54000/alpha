# Phase 5.3 UX Acceptance Audit

Date: 2026-06-12

Scope: read-only UX acceptance audit for the Swing Research Cockpit after Phase 5.2 frontend integration and the dashboard data freshness banner. This audit reviews user workflows only. It does not modify frontend code, backend code, APIs, scoring, recommendations, strategy rules, or data.

## Executive Summary

The cockpit does not currently pass UX acceptance because all audited frontend routes return `500 Internal Server Error` at runtime:

- `/`
- `/recommendations`
- `/recommendations/TEST/explanation`
- `/portfolio`
- `/operations`
- `/research`

The backend APIs required by the cockpit are reachable:

- `GET /dashboard`: 200
- `GET /recommendations/latest?model=swing_v2_1&limit=3`: 200, empty recommendation set
- `GET /portfolio`: 200, empty portfolio
- `GET /pipeline/status`: 200, no pipeline steps, one monitoring report
- `GET /research/metrics`: 200
- `GET /recommendations/TEST/explanation?recommendation_type=swing_v2_1`: 404 for missing journal row

Source-level UX coverage is partially present: pages define loading, empty, and error panels, and sidebar routes exist. The immediate acceptance blocker is frontend rendering failure. Once route rendering is fixed, the next UX gaps are mostly around empty recommendations, missing decision-journal rows, stale/unknown operational state, and making pipeline failure/stale data actionable.

## Current Data State

Observed live API state during audit:

| Area | Current API state |
| --- | --- |
| Dashboard | Empty `portfolio`, `risk`, and `benchmark`; `system_health.status = "unknown"` |
| Data freshness | `latest_candle_at = null`, `latest_feature_date = null`, `latest_recommendation_date = null` |
| Recommendations | `date = null`, `recommendations = []`, source `recommendation_history` |
| Portfolio | Empty `summary`, `positions`, `trades`, `risk`, and `benchmark` |
| Pipeline | `status = "unknown"`, `steps = []`, `failed_steps = 0` |
| Monitoring reports | One report listed: `daily_paper_report_2026-06-12.md` |
| Research | Phase 2E, walk-forward, and Phase 3E data available |

## Acceptance Status

| Flow | Acceptance status | Primary blocker |
| --- | --- | --- |
| Dashboard operator flow | Fail | Frontend route returns 500 |
| Recommendation discovery flow | Fail | Frontend route returns 500; recommendations are empty |
| Recommendation explanation flow | Fail | Frontend route returns 500; missing symbols return API 404 |
| Portfolio review flow | Fail | Frontend route returns 500; portfolio data is empty |
| Operations monitoring flow | Fail | Frontend route returns 500; pipeline status is unknown |
| Research metrics flow | Fail | Frontend route returns 500 despite available API data |

## 1. Dashboard Operator Flow

File path: `frontend/app/page.tsx`

API dependencies:

- `GET /dashboard`
- `GET /pipeline/status`

Expected behavior:

- Operator lands on `/`.
- Data Status Card clearly shows latest market data date, latest recommendation date, latest pipeline run, and freshness status.
- Main dashboard shows NAV, realized PnL, drawdown, benchmark return, system health, and exposure.
- If data is stale or unavailable, the dashboard should still render with a visible red/yellow status and actionable context.
- If the API fails, a readable error state should appear.

Current behavior:

- Frontend route `/` returns `500`.
- Backend `/dashboard` and `/pipeline/status` return 200.
- Current data would classify as stale because market data and recommendation dates are unavailable.
- The source contains an empty-state panel and Data Status Card, but runtime failure prevents the operator from seeing them.

Broken links:

- No dashboard-local links.
- Sidebar route to `/` is structurally correct.
- User-facing navigation still fails because the destination route returns 500.

Missing states:

- No actionable remediation for `system_health.status = "unknown"`.
- No explicit distinction between "never initialized" and "stale after prior success".
- No visible last successful sync date when pipeline steps are empty.

Confusing UX:

- With empty portfolio metrics and unknown system health, the dashboard would show several `n/a` metrics. This is technically accurate but not enough to guide an operator.
- Data Status Card reports "Stale data" for missing data, but does not indicate whether the issue is missing Angel data, missing recommendations, or missing pipeline history.

API/data dependency issues:

- `/dashboard` currently depends on available paper portfolio and system health data, but those are empty/unknown.
- `/pipeline/status` has no step rows, so latest pipeline run cannot be derived from `steps`.

Root cause classification:

- Primary: frontend rendering issue.
- Secondary: empty operational state handling.

## 2. Recommendation Discovery Flow

File path: `frontend/app/recommendations/page.tsx`

API dependency:

- `GET /recommendations/latest?model=swing_v2_1&limit=50`

Expected behavior:

- User opens `/recommendations`.
- Latest Swing V2.1 recommendations appear in ranked order.
- Each symbol links to its explanation page.
- Empty recommendation sets should render a clear empty state and preserve the surrounding navigation.
- API failure should render a readable error state.

Current behavior:

- Frontend route `/recommendations` returns `500`.
- Backend recommendations API returns 200 with `date = null` and `recommendations = []`.
- Source code would render "No Swing V2.1 recommendations were returned by the API."
- No explanation links are rendered because there are no recommendation rows.

Broken links:

- Sidebar route to `/recommendations` is structurally correct but runtime rendering fails.
- Symbol explanation links are structurally correct when rows exist.
- With empty recommendations, no symbol links exist, so users have no path into explanation pages.

Missing states:

- Empty recommendations state does not indicate whether recommendations are missing because scoring has not run, recommendation generation has failed, or the selected model/date has no data.
- No date picker or prior-date fallback is present for discovery when latest recommendations are empty.
- No link from the empty state to Operations for pipeline diagnosis.

Confusing UX:

- "Ranked Swing V2.1 list from n/a" is technically true but vague.
- Users may interpret an empty table as a strategy output of zero recommendations rather than a data/pipeline absence.

API/data dependency issues:

- Current source is `recommendation_history`, while prior pilot/cockpit work may also use pilot recommendation tables. The UI does not explain the source switch.
- Empty recommendation data blocks explanation discovery.

Root cause classification:

- Primary: frontend rendering issue.
- Secondary: empty state handling and API/data availability.

## 3. Recommendation Explanation Flow

File path: `frontend/app/recommendations/[symbol]/explanation/page.tsx`

API dependency:

- `GET /recommendations/{symbol}/explanation?recommendation_type=swing_v2_1`

Expected behavior:

- User clicks a symbol from the recommendations table.
- Explanation page shows rank, score, sector, and feature snapshot.
- If no decision journal exists, the page should explain that the snapshot has not been captured for that symbol/date.
- The page should allow users to recover back to recommendations.

Current behavior:

- Frontend route `/recommendations/TEST/explanation` returns `500`.
- Backend explanation API returns 404 for a symbol without a decision journal row.
- Source code uses `safeApiGet`, so intended behavior is an error panel, but runtime failure prevents it.

Broken links:

- Generated recommendation links use `encodeURIComponent(row.symbol)` and target the correct dynamic route.
- No back link or local navigation is present on the explanation page.
- Explanation links are unavailable if latest recommendations are empty.

Missing states:

- No dedicated "explanation not captured yet" state separate from generic API failure.
- No handling for selecting a historical recommendation date.
- No fallback to feature data if journal data is absent.
- No visible route back to `/recommendations`.

Confusing UX:

- A missing journal row returns an API 404, which is a data availability condition, not necessarily a broken page.
- Uppercasing the decoded symbol is acceptable for ordinary NSE symbols but could be surprising for future case-sensitive vendor identifiers.

API/data dependency issues:

- Decision journal must be populated for explanation pages to work.
- Current empty recommendations prevent normal discovery of symbols with journal data.

Root cause classification:

- Primary: frontend rendering issue.
- Secondary: API/data dependency for missing journal snapshots.

## 4. Portfolio Review Flow

File path: `frontend/app/portfolio/page.tsx`

API dependency:

- `GET /portfolio`

Expected behavior:

- User opens `/portfolio`.
- Page shows NAV, cash, exposure, open positions, holdings, and recent trades.
- Empty portfolio should render a clear empty state.
- Open positions and trade history should be scannable and resilient to missing optional fields.

Current behavior:

- Frontend route `/portfolio` returns `500`.
- Backend `/portfolio` returns 200 with empty summary, positions, trades, risk, and benchmark.
- Source code includes empty-state handling for no paper portfolio snapshot, no holdings, and no trades.

Broken links:

- No portfolio-local links.
- Sidebar route to `/portfolio` is structurally correct but runtime rendering fails.

Missing states:

- Empty portfolio message mentions `PAPER_PORTFOLIO_ID` and initialization, which is operationally useful but not user-friendly for a cockpit operator.
- No distinction between "paper trading not initialized" and "portfolio initialized but currently flat".
- No link to Operations or latest paper report for diagnosis.

Confusing UX:

- Metric cards would show `n/a` for NAV, cash, and exposure beside an empty portfolio message.
- "Open Positions" falls back to zero, which may look healthy even when no portfolio exists.

API/data dependency issues:

- Portfolio page requires a default or configured paper portfolio.
- Current API state indicates no available paper portfolio snapshot.

Root cause classification:

- Primary: frontend rendering issue.
- Secondary: empty portfolio state handling.

## 5. Operations Monitoring Flow

File path: `frontend/app/operations/page.tsx`

API dependency:

- `GET /pipeline/status`

Expected behavior:

- User opens `/operations`.
- Page shows pipeline status, failed steps, latest candle, latest recommendations, step-level execution rows, and monitoring reports.
- Pipeline failure should be clearly visible with failed step, error message, and latest successful stage.
- Empty pipeline history should not look equivalent to a healthy pipeline.

Current behavior:

- Frontend route `/operations` returns `500`.
- Backend `/pipeline/status` returns 200 with `status = "unknown"`, `steps = []`, and one monitoring report.
- Source code would render an empty state for no pipeline rows.

Broken links:

- No operations-local links.
- Sidebar route to `/operations` is structurally correct but runtime rendering fails.

Missing states:

- No explicit "pipeline has never run" state.
- No status severity mapping for `unknown`; source currently gives `tone="ok"` unless status is exactly `failed`.
- No partial-failure recovery guidance in the UI.
- Monitoring report paths are displayed as text only; not linked.

Confusing UX:

- `status = "unknown"` can appear in a neutral/positive metric tone, which may mislead operators.
- `failed_steps = 0` with no pipeline steps could be read as healthy even though there is no run history.

API/data dependency issues:

- Freshness and operations status depend on `pipeline_runs` rows.
- Current API has no step rows, so it cannot support a meaningful latest-run workflow.

Root cause classification:

- Primary: frontend rendering issue.
- Secondary: missing operational state semantics for unknown/no-run state.

## 6. Research Metrics Flow

File path: `frontend/app/research/page.tsx`

API dependency:

- `GET /research/metrics`

Expected behavior:

- User opens `/research`.
- Page shows available validation studies and concise summaries of metrics.
- Large JSON payloads should be summarized into readable research sections.
- Missing report files should render a clear empty state.

Current behavior:

- Frontend route `/research` returns `500`.
- Backend `/research/metrics` returns 200 with available Phase 2E, walk-forward, and Phase 3E data.
- Source code maps summary entries and renders a truncated JSON preview of `paper_replay`.

Broken links:

- No research-local links.
- Sidebar route to `/research` is structurally correct but runtime rendering fails.

Missing states:

- No per-report missing-state breakdown.
- No clear distinction between backtest metrics, walk-forward metrics, and paper replay metrics in the first view.
- No navigation to underlying report documents.

Confusing UX:

- Raw/truncated JSON is useful for debugging but not ideal for acceptance-level research review.
- "Portfolio Metrics Keys" shows key availability rather than actual headline research outcomes.

API/data dependency issues:

- API has data, so the main issue is frontend rendering and presentation quality.

Root cause classification:

- Primary: frontend rendering issue.
- Secondary: frontend presentation issue.

## Test Scenario Review

### Scenario: Normal Data

Expected:

- Dashboard green freshness status.
- Recommendations populated with clickable symbols.
- Explanation pages show journal snapshots.
- Portfolio has NAV, holdings, trades, and risk.
- Operations shows successful latest pipeline run.
- Research shows validation summaries.

Current:

- Cannot validate in browser because all frontend routes return 500.
- Backend currently does not represent normal live data: recommendations, portfolio, pipeline dates, and freshness fields are empty/null.

Acceptance result: fail.

Primary issue: frontend rendering issue, with insufficient normal-data fixture availability for full UX validation.

### Scenario: Stale Data

Expected:

- Dashboard Data Status Card turns red for stale data.
- Operations page identifies stale source and latest successful step.
- User can understand whether market data, features, recommendations, or paper update is stale.

Current:

- Backend data is effectively stale/unavailable: latest market data and recommendation dates are null.
- Data Status Card source logic would classify this as "Stale data".
- Frontend route 500 prevents the state from being visible.

Acceptance result: fail.

Primary issue: frontend rendering issue.

Secondary issue: stale state is not actionable enough when dates are null and pipeline steps are empty.

### Scenario: Empty Portfolio

Expected:

- Portfolio page clearly says no paper portfolio is available or initialized.
- Dashboard avoids presenting `n/a` metrics as if they are normal.
- User understands the next operational check.

Current:

- Backend `/portfolio` returns empty objects/arrays.
- Source code has empty-state handling.
- Frontend route 500 prevents validation.

Acceptance result: fail.

Primary issue: frontend rendering issue.

Secondary issue: empty portfolio copy is more developer/operator-config focused than cockpit-user focused.

### Scenario: Pipeline Failure

Expected:

- Operations page shows failed status prominently.
- Failed step and error message are visible.
- Dashboard data freshness should warn or show stale status.
- Downstream workflow should not look healthy.

Current:

- Live pipeline status is `unknown`, not `failed`.
- Source code marks Operations status bad only when status equals `failed`.
- Dashboard Data Status Card treats failed pipeline status as yellow "Pipeline delayed"; stale/missing market/recommendation dates become red before failed status is considered.
- Frontend route 500 prevents visible validation.

Acceptance result: fail for runtime validation; source behavior is partially present but incomplete.

Primary issue: frontend rendering issue.

Secondary issue: `unknown` and no-run states need explicit severity, and failed/stale precedence should be reviewed for operator clarity.

## Cross-Flow Findings

### Finding 1: Global frontend 500 blocks all UX acceptance

Severity: high

Every workflow fails in the browser because page rendering fails before users can interact with the intended states.

Classification: frontend rendering issue.

### Finding 2: Source navigation is mostly correct, but runtime navigation is unusable

Severity: high

The sidebar and dynamic recommendation hrefs are structurally valid, but every destination route currently returns 500.

Classification: frontend rendering issue.

### Finding 3: Empty data states exist but are not sufficiently diagnostic

Severity: medium

Pages generally render `EmptyState`, but messages do not always distinguish between:

- not initialized
- no latest run
- stale data
- API unavailable
- no recommendations generated
- zero recommendations as a valid strategy result

Classification: empty state handling.

### Finding 4: Operations unknown status can look too benign

Severity: medium

The Operations status card only uses bad tone for `failed`. `unknown` with no pipeline steps is not healthy, but the UX does not clearly mark it as a warning.

Classification: confusing UX.

### Finding 5: Recommendation explanation depends on decision journal availability

Severity: medium

The route exists, but missing journal rows return 404. This is expected from the API but should read as "no explanation snapshot captured" rather than a broken page.

Classification: API/data dependency issue.

### Finding 6: Research page needs acceptance-level summaries

Severity: low

The research page exposes available data, but raw/truncated JSON and key lists are more diagnostic than user-facing.

Classification: frontend presentation issue.

## Recommended Follow-Up Sequence

1. Capture and fix the common frontend runtime 500.
2. Re-run route probes for all six workflows.
3. Validate empty-state rendering with the current live API payloads.
4. Add or test fixtures for normal data, stale data, empty portfolio, and pipeline failure.
5. Improve UX copy and severity mapping for unknown/no-run/stale states.
6. Re-run this acceptance audit after pages render successfully.

## Acceptance Verdict

Phase 5.3 UX acceptance is not approved yet.

Reason: the cockpit workflows are structurally present in source, but all audited frontend routes currently fail at runtime. The backend APIs are reachable, so the next actionable step is frontend runtime error diagnosis before workflow-level UX can be accepted.
