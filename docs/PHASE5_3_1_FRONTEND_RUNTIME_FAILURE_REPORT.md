# Phase 5.3.1 Frontend Runtime Failure Report

Date: 2026-06-12

Scope: root-cause investigation only. No frontend code, backend code, APIs, scoring, recommendations, strategy logic, or data were modified.

## Executive Summary

Root cause: the frontend runtime failure is caused by the production Next.js server artifact/startup path, not by the page route code or backend APIs.

The app is configured with `output: "standalone"` in `frontend/next.config.mjs`, but `frontend/package.json` still defines:

```json
"start": "next start"
```

Running `next start` with standalone output is explicitly unsupported by Next.js. The captured server logs show:

```text
"next start" does not work with "output: standalone" configuration. Use "node .next/standalone/server.js" instead.
```

In addition, both `next start` and `node .next/standalone/server.js` currently fail to resolve generated server chunks:

```text
Error: Cannot find module './673.js'
Require stack:
- ...\.next\server\webpack-runtime.js
- ...\.next\server\pages\_document.js
```

and:

```text
Error: Cannot find module './682.js'
```

The missing chunk files do exist, but under:

- `frontend/.next/server/chunks/673.js`
- `frontend/.next/server/chunks/682.js`
- `frontend/.next/standalone/.next/server/chunks/673.js`
- `frontend/.next/standalone/.next/server/chunks/682.js`

The generated runtime is trying to load them as sibling files via `require("./673.js")` and `require("./682.js")`. That mismatch produces HTTP 500 for every production-served route.

A clean Next dev server on port `3014` rendered all audited routes successfully with HTTP 200, which rules out the route source, server component/client component mismatch, dynamic route handling, and backend API fetches as the primary cause.

## Affected Routes

Production/standalone probe results:

| Route | Result |
| --- | --- |
| `/` | 500 |
| `/recommendations` | 500 |
| `/recommendations/TEST/explanation` | 500 |
| `/portfolio` | 500 |
| `/operations` | 500 |
| `/research` | 500 |

Clean dev server probe results:

| Route | Result |
| --- | --- |
| `/` | 200 |
| `/recommendations` | 200 |
| `/recommendations/TEST/explanation` | 200 |
| `/portfolio` | 200 |
| `/operations` | 200 |
| `/research` | 200 |

## Investigation Checklist

### 1. Next.js Server Logs

Status: checked.

Captured logs:

- `reports/phase5_3_1_next_direct_stderr.log`
- `reports/phase5_3_1_standalone_stderr.log`
- `reports/phase5_3_1_dev_stdout.log`

Findings:

- `next start` logs the standalone-output warning.
- `next start` returns 500 for all audited routes.
- `node .next/standalone/server.js` also returns 500 for all audited routes.
- Both production paths fail with `MODULE_NOT_FOUND` for generated chunks `./673.js` and `./682.js`.
- Clean `next dev` route compilation succeeds and all audited routes return 200.

### 2. Browser Console Errors

Status: indirectly checked.

The failing production routes are server-side failures. HTTP responses are generic `500 Internal Server Error`, and the useful stack appears in the Next.js server stderr logs rather than browser-visible page output.

Clean dev rendering succeeded for all routes, so no browser-side route/render error was reproduced in the clean dev server path.

### 3. API Fetch Failures

Status: checked.

Backend API probes:

| API | Result |
| --- | --- |
| `GET /dashboard` | 200 |
| `GET /recommendations/latest?model=swing_v2_1&limit=1` | 200 |
| `GET /recommendations/TEST/explanation?recommendation_type=swing_v2_1` | 404 |
| `GET /portfolio` | 200 |
| `GET /pipeline/status` | 200 |
| `GET /research/metrics` | 200 |

Findings:

- Primary page APIs are reachable.
- The recommendation explanation API returns 404 for a test symbol without a journal row; the clean dev frontend handles this and still returns page HTTP 200 with an error state.
- API fetch failure is not the global 500 root cause.

### 4. Environment Variables

Status: checked.

Relevant file:

- `frontend/lib/api.ts`

Current behavior:

```ts
const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
```

Findings:

- No frontend `.env` override was found.
- Default API base URL points to `http://localhost:8000`.
- Direct backend API probes on `localhost:8000` succeed.
- API base URL configuration is not the global 500 root cause.

### 5. API Base URL Configuration

Status: checked.

Findings:

- Server components use `safeApiGet`, which calls the configured API base.
- The clean dev server successfully renders API-backed pages.
- Incorrect API base URL is not the root cause.

### 6. Server Component / Client Component Mismatch

Status: checked by reproduction.

Findings:

- The app pages are server components.
- `next dev` compiled and rendered all audited routes successfully.
- No server/client component boundary error was reproduced.
- Server/client mismatch is not the root cause.

### 7. Dynamic Route Handling

Status: checked.

Route:

- `frontend/app/recommendations/[symbol]/explanation/page.tsx`

Findings:

- Clean dev route `/recommendations/TEST/explanation` returned HTTP 200.
- The page correctly receives the dynamic `symbol` param and calls the API.
- The backend returned 404 for `TEST`, but the frontend page still rendered successfully in dev.
- Dynamic route handling is not the global 500 root cause.

### 8. Static Rendering / Build-Time API Calls

Status: checked.

Findings:

- `npm run build` succeeds.
- Pages use `fetch(..., { cache: "no-store" })`, making them runtime-rendered rather than static pages that depend on build-time API availability.
- Build-time API calls are not the root cause.
- The failure occurs after build, when serving generated production/standalone artifacts.

## Affected Files

Primary configuration files:

- `frontend/next.config.mjs`
- `frontend/package.json`

Runtime/helper files involved:

- `frontend/lib/api.ts`

Generated artifacts implicated by logs:

- `frontend/.next/server/webpack-runtime.js`
- `frontend/.next/server/chunks/673.js`
- `frontend/.next/server/chunks/682.js`
- `frontend/.next/standalone/server.js`
- `frontend/.next/standalone/.next/server/webpack-runtime.js`
- `frontend/.next/standalone/.next/server/chunks/673.js`
- `frontend/.next/standalone/.next/server/chunks/682.js`

Audited page files that are affected only because the production server fails globally:

- `frontend/app/page.tsx`
- `frontend/app/recommendations/page.tsx`
- `frontend/app/recommendations/[symbol]/explanation/page.tsx`
- `frontend/app/portfolio/page.tsx`
- `frontend/app/operations/page.tsx`
- `frontend/app/research/page.tsx`

## Root Cause

The frontend source routes are not the root cause. The root cause is the production serving path for the Next.js app:

1. `next.config.mjs` enables `output: "standalone"`.
2. `package.json` still starts production with `next start`, which Next.js warns is unsupported for standalone output.
3. Production serving then fails to resolve generated server chunks, producing `MODULE_NOT_FOUND` for `./673.js` and `./682.js`.
4. Because `_document`/webpack runtime loading is shared, every route returns HTTP 500.

The clean dev server proves the application pages can render when served through a non-broken Next runtime path.

## Recommended Fix

Recommended path:

1. Decide whether the cockpit should use standard Next serving or standalone serving.
2. If standard serving is preferred for local cockpit use:
   - remove `output: "standalone"` from `frontend/next.config.mjs`
   - keep `npm run start` as `next start`
   - rebuild with a clean `.next`
3. If standalone serving is preferred:
   - change the production start command to run `node .next/standalone/server.js`
   - ensure `.next/static` and `public` are available in the deployed standalone layout as required by Next.js
   - investigate why the standalone webpack runtime is resolving chunk files as siblings while the emitted chunks are under `server/chunks`
   - rebuild from a clean `.next` directory before retesting

For this desktop/local research cockpit, the simplest likely fix is to remove standalone output and use the standard Next production server:

```js
// frontend/next.config.mjs
const nextConfig = {};

export default nextConfig;
```

Then:

```powershell
cd D:\nse-research-app\frontend
npm run build
npm run start
```

No backend or strategy changes are required.

## Confidence Level

High.

Evidence:

- Production routes reproduce 500 consistently.
- Server logs show concrete `MODULE_NOT_FOUND` failures in Next generated server runtime.
- Backend APIs are reachable directly.
- Clean `next dev` renders every audited route successfully.
- The failure is common to all routes and occurs before route-specific UX logic matters.

Residual uncertainty:

- The exact reason webpack runtime emits `require("./673.js")` while chunks are located under `server/chunks` was not corrected in this investigation because code changes were out of scope.
- The safest confirmation will be a follow-up fix branch that rebuilds from a clean `.next` with either standard output or a corrected standalone start/deploy layout.
