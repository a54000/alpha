# Phase 5.2.1 Frontend Navigation Audit

Date: 2026-06-12

Scope: read-only audit of the Swing Research Cockpit frontend routes, links, dynamic route parameters, and API dependencies. No frontend code, backend code, APIs, scoring, recommendations, or strategy logic were modified.

## Executive Summary

The source-level navigation map is structurally correct:

- The sidebar uses `next/link` for all primary pages.
- All primary target routes exist under `frontend/app`.
- The recommendation explanation route exists as a dynamic Next.js App Router route.
- API dependencies exist for all audited pages.

However, runtime probes against the currently running frontend returned `500 Internal Server Error` for every audited frontend route:

- `/`
- `/recommendations`
- `/recommendations/TEST/explanation`
- `/portfolio`
- `/operations`
- `/research`

The matching backend API probes mostly succeeded:

- `GET /dashboard`: 200
- `GET /recommendations/latest?model=swing_v2_1&limit=1`: 200, empty recommendations
- `GET /recommendations/TEST/explanation?recommendation_type=swing_v2_1`: 404
- `GET /portfolio`: 200
- `GET /pipeline/status`: 200
- `GET /research/metrics`: 200

This points to a frontend runtime/rendering issue rather than missing route files or wrong sidebar hrefs. The recommendation explanation page also has a real empty-data/API-404 edge case when the selected symbol has no decision journal row.

`npm run build` succeeds, so the failure is not currently caught by TypeScript or the production build step.

## Route Inventory

| Page | File path | Route | Route exists |
| --- | --- | --- | --- |
| Dashboard | `frontend/app/page.tsx` | `/` | Yes |
| Recommendations | `frontend/app/recommendations/page.tsx` | `/recommendations` | Yes |
| Recommendation explanation | `frontend/app/recommendations/[symbol]/explanation/page.tsx` | `/recommendations/{symbol}/explanation` | Yes |
| Portfolio | `frontend/app/portfolio/page.tsx` | `/portfolio` | Yes |
| Operations | `frontend/app/operations/page.tsx` | `/operations` | Yes |
| Research | `frontend/app/research/page.tsx` | `/research` | Yes |

## Shared Navigation

File path: `frontend/app/layout.tsx`

Link/button component used: `next/link` `Link`

Defined targets:

| Label | Target route | Expected route | Route exists | Next.js routing correct |
| --- | --- | --- | --- | --- |
| Dashboard | `/` | `/` | Yes | Yes |
| Recommendations | `/recommendations` | `/recommendations` | Yes | Yes |
| Portfolio | `/portfolio` | `/portfolio` | Yes | Yes |
| Operations | `/operations` | `/operations` | Yes | Yes |
| Research | `/research` | `/research` | Yes | Yes |

Finding: no wrong sidebar hrefs found.

Root cause classification: not a routing issue at source level.

## Page-by-Page Audit

### 1. Dashboard

File path: `frontend/app/page.tsx`

Link/button component used: no page-local navigation links. Page is reached from sidebar `Link href="/"`.

Target route: `/`

Expected route: `/`

Whether route exists: yes, App Router root page exists.

Whether Next.js routing is correct: yes at source level.

Dynamic route parameters: not applicable.

API dependency:

- `GET /dashboard`
- `GET /pipeline/status`

API availability:

- `/dashboard`: 200
- `/pipeline/status`: 200

Browser-side error if applicable:

- `http://localhost:3000/`: 500
- clean temporary production probe also returned 500

Notes:

- The dashboard API returns a valid payload with empty `portfolio`, `risk`, and `benchmark` objects and `system_health.status = "unknown"`.
- The page has empty-state handling for no dashboard metrics.
- Since the API succeeds and the route exists, the current failure is likely frontend runtime/rendering, not a missing API or wrong route.

Root cause classification: frontend rendering issue.

### 2. Recommendations

File path: `frontend/app/recommendations/page.tsx`

Link/button component used:

- Sidebar `Link href="/recommendations"`
- Table row symbol link: `Link href={`/recommendations/${encodeURIComponent(row.symbol)}/explanation`}`

Target route:

- Page route: `/recommendations`
- Detail route: `/recommendations/{encodedSymbol}/explanation`

Expected route:

- `/recommendations`
- `/recommendations/{symbol}/explanation`

Whether route exists: yes.

Whether Next.js routing is correct: yes at source level.

Dynamic route parameters:

- `row.symbol` is passed through `encodeURIComponent`.
- This is correct for special characters in symbols.

API dependency:

- `GET /recommendations/latest?model=swing_v2_1&limit=50`

API availability:

- `GET /recommendations/latest?model=swing_v2_1&limit=1`: 200
- Current payload has `date = null` and `recommendations = []`.

Browser-side error if applicable:

- `http://localhost:3000/recommendations`: 500 during route probe after the global frontend runtime issue appeared.
- Earlier rendered HTML showed the intended empty state: "No Swing V2.1 recommendations were returned by the API."

Notes:

- With the current API data, there are no recommendation rows, so no symbol links are rendered. This can make explanation navigation appear unavailable even though the route and link template are present.

Root cause classification: empty state handling plus frontend rendering issue.

### 3. Recommendation Explanation

File path: `frontend/app/recommendations/[symbol]/explanation/page.tsx`

Link/button component used:

- Inbound links are generated by `frontend/app/recommendations/page.tsx` with `next/link`.
- No page-local navigation links.

Target route:

- `/recommendations/{symbol}/explanation`

Expected route:

- `/recommendations/{symbol}/explanation`

Whether route exists: yes.

Whether Next.js routing is correct: yes at source level.

Dynamic route parameters:

- Inbound link encodes symbol with `encodeURIComponent(row.symbol)`.
- The explanation page decodes `params.symbol` with `decodeURIComponent(params.symbol).toUpperCase()`.
- The API call re-encodes the decoded uppercase symbol.
- This is mostly correct for ordinary NSE symbols.

Potential dynamic parameter caveat:

- Converting the route parameter to uppercase may be safe for normal NSE symbols but could be lossy if a future vendor symbol format is case-sensitive.

API dependency:

- `GET /recommendations/{symbol}/explanation?recommendation_type=swing_v2_1`

API availability:

- `GET /recommendations/TEST/explanation?recommendation_type=swing_v2_1`: 404

Browser-side error if applicable:

- `http://localhost:3000/recommendations/TEST/explanation`: 500

Notes:

- The backend correctly returns 404 when no decision journal row exists for the symbol.
- The frontend uses `safeApiGet`, so source-level intent is to render `ErrorState` for the 404.
- The observed frontend 500 suggests the global frontend runtime/rendering issue is preventing the intended error state from being shown.

Root cause classification: API issue for symbols without journal rows, then frontend rendering issue because the route renders as 500 instead of a clean error state.

### 4. Portfolio

File path: `frontend/app/portfolio/page.tsx`

Link/button component used: no page-local navigation links. Page is reached from sidebar `Link href="/portfolio"`.

Target route: `/portfolio`

Expected route: `/portfolio`

Whether route exists: yes.

Whether Next.js routing is correct: yes at source level.

Dynamic route parameters: not applicable.

API dependency:

- `GET /portfolio`

API availability:

- `/portfolio`: 200

Browser-side error if applicable:

- `http://localhost:3000/portfolio`: 500 during route probe after the global frontend runtime issue appeared.
- Earlier rendered HTML showed the intended empty state for no paper portfolio snapshot.

Notes:

- The API returns empty summary, positions, trades, risk, and benchmark objects/arrays.
- The page has empty-state handling for no portfolio snapshot and no holdings/trades.

Root cause classification: frontend rendering issue.

### 5. Operations

File path: `frontend/app/operations/page.tsx`

Link/button component used: no page-local navigation links. Page is reached from sidebar `Link href="/operations"`.

Target route: `/operations`

Expected route: `/operations`

Whether route exists: yes.

Whether Next.js routing is correct: yes at source level.

Dynamic route parameters: not applicable.

API dependency:

- `GET /pipeline/status`

API availability:

- `/pipeline/status`: 200

Browser-side error if applicable:

- `http://localhost:3000/operations`: 500

Notes:

- The API returns `summary`, `steps: []`, and one monitoring report.
- The page expects those fields and has empty-state handling for no pipeline steps.
- The route exists and API succeeds, so the current failure is frontend runtime/rendering.

Root cause classification: frontend rendering issue.

### 6. Research

File path: `frontend/app/research/page.tsx`

Link/button component used: no page-local navigation links. Page is reached from sidebar `Link href="/research"`.

Target route: `/research`

Expected route: `/research`

Whether route exists: yes.

Whether Next.js routing is correct: yes at source level.

Dynamic route parameters: not applicable.

API dependency:

- `GET /research/metrics`

API availability:

- `/research/metrics`: 200

Browser-side error if applicable:

- `http://localhost:3000/research`: 500 during route probe after the global frontend runtime issue appeared.
- A separate probe returned 200 earlier, before all frontend routes began returning 500.

Notes:

- The API returns a large research metrics payload.
- The page renders summaries and a truncated JSON preview.
- Since the API succeeds and the route exists, the observed 500 is grouped with the global frontend runtime/rendering issue.

Root cause classification: frontend rendering issue.

## Findings

### Finding 1: All frontend routes currently return 500 at runtime

Severity: high

Evidence:

- `http://localhost:3000/`: 500
- `http://localhost:3000/recommendations`: 500
- `http://localhost:3000/portfolio`: 500
- `http://localhost:3000/operations`: 500
- `http://localhost:3000/research`: 500
- `http://localhost:3000/recommendations/TEST/explanation`: 500
- Clean temporary production probe returned the same 500 behavior.
- Backend APIs are available for all primary pages.
- `npm run build` succeeds.

Classification: frontend rendering issue.

Likely impact: navigation appears broken because every destination page fails to render, even when the link target is correct.

### Finding 2: Recommendation explanation links are absent when latest recommendations are empty

Severity: medium

Evidence:

- `GET /recommendations/latest?model=swing_v2_1&limit=1` returns `recommendations: []`.
- The recommendations page only renders explanation links for returned recommendation rows.

Classification: empty state handling.

Likely impact: users cannot navigate to explanation pages from the recommendations table when the current recommendation set is empty.

### Finding 3: Explanation route has valid routing but API returns 404 for symbols without decision journal records

Severity: medium

Evidence:

- Route file exists: `frontend/app/recommendations/[symbol]/explanation/page.tsx`.
- Link template is correct: `/recommendations/${encodeURIComponent(row.symbol)}/explanation`.
- `GET /recommendations/TEST/explanation?recommendation_type=swing_v2_1` returns 404.

Classification: API issue for missing journal data, plus frontend rendering issue because the user sees 500 instead of a clean error state.

Likely impact: direct explanation URLs for symbols without journal rows fail.

### Finding 4: No wrong sidebar hrefs found

Severity: none

Evidence:

- Sidebar route targets map directly to existing App Router files.

Classification: not a routing issue.

## Verification Performed

Commands/probes performed:

- Inspected frontend route files under `frontend/app`.
- Inspected link usage with `rg`.
- Probed frontend routes on `localhost:3000`.
- Probed backend API dependencies on `localhost:8000`.
- Ran `npm run build` in `frontend`; build completed successfully.
- Started a temporary clean production server on another port and confirmed the frontend 500 behavior was not limited to the original dev server.

## Recommended Next Investigation

This audit intentionally did not modify code. The next phase should capture the server-side Next.js error stack for the common 500 across routes, then fix the frontend render failure first. After that, re-check recommendation explanation behavior with:

- a symbol that exists in `recommendation_decision_journal`
- a symbol that does not exist
- an empty latest recommendations payload

The source navigation itself should not be the first fix target; the immediate blocker is page rendering.
