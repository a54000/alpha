# Phase 5.3.2 Production Serving Fix

Date: 2026-06-12

Scope: frontend production serving only. No API logic, backend code, scoring, recommendations, strategy logic, or database objects were changed.

## Objective

Fix the Swing Research Cockpit production runtime failure where all frontend routes returned HTTP 500.

## Decision

The frontend was changed from standalone output to standard Next.js production serving.

Reason:

- `next.config.mjs` used `output: "standalone"`.
- `package.json` used `next start`, which is incompatible with standalone output.
- Phase 5.3.1 also showed that the generated standalone artifact failed when launched with `node .next/standalone/server.js`, due to generated server chunk resolution errors.
- A standard Next production build/start path is sufficient for this local research cockpit and keeps production serving consistent with the existing `npm run start` script.

## Files Changed

- `frontend/next.config.mjs`

Previous:

```js
const nextConfig = {
  output: "standalone"
};
```

Current:

```js
const nextConfig = {};
```

`frontend/package.json` was not changed. It already uses:

```json
"start": "next start"
```

## Build Procedure

A stale `.next` directory from the prior standalone build caused one rebuild to fail during page-data collection. The generated build directory was removed and rebuilt cleanly.

Commands:

```powershell
cd D:\nse-research-app\frontend
Remove-Item .next -Recurse -Force
npm run build
```

Result:

- Build completed successfully.
- All expected App Router routes were present in the production build.

## Production Start Procedure

Command:

```powershell
cd D:\nse-research-app\frontend
npm run start -- -p 3015
```

This now uses the standard Next.js production server consistently.

## Verification

Temporary production server: `http://localhost:3015`

| Route | Result |
| --- | --- |
| `/` | 200 |
| `/recommendations` | 200 |
| `/recommendations/TEST/explanation` | 200 |
| `/portfolio` | 200 |
| `/operations` | 200 |
| `/research` | 200 |

Build verification:

```text
npm run build
Compiled successfully
Generating static pages (8/8)
Finalizing page optimization
```

Runtime verification:

```text
npm run start -- -p 3015
Ready in 1275ms
```

No server stderr errors were emitted during route verification.

## Notes

The dynamic explanation route returned HTTP 200 at the frontend route level. The test symbol may still show an application error state if the backend explanation API returns 404 for a missing decision journal row, but the page itself now renders correctly.

## Current Production Serving Contract

Use:

```powershell
npm run build
npm run start
```

Do not use:

```powershell
node .next/standalone/server.js
```

unless standalone output is intentionally restored and separately verified.

## Acceptance Result

Accepted for Phase 5.3.2.

All required frontend routes now return HTTP 200 under production serving.
