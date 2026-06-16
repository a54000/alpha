# Phase 5.23 Rolling Portfolio UI Backtest

## Objective

Add an interactive Research Cockpit workflow for stepping through the preferred rolling 10-slot portfolio construction week by week.

## Route

Frontend:

- `/research/rolling-portfolio`

Backend:

- `POST /research/rolling-portfolio/simulate`

## Request

```json
{
  "start_date": "2026-05-04",
  "weeks": 1,
  "initial_capital": 1000000
}
```

## Behavior

The simulator reads:

- `pilot_phase2a.recommendations_daily`
- `pilot_phase2a.features_daily`
- `pilot_phase2a.daily_bars_clean`

It applies the preferred construction:

| Rule | Value |
| --- | --- |
| Maximum open positions | `10` |
| Weekly candidate intake | Top `5` recommendations |
| Holding period | `20` trading days |
| Exit rule | Planned exit only |
| Allocation | Equity / `10` |

The UI lets the user:

1. Select a start date.
2. Run the first weekly cohort.
3. Click `Next Week` to include the next recommendation week.
4. Review recommendations logged each week.
5. Review entries, skips, open positions, cash, market value, and equity.
6. Review closed trades after the 20-trading-day holding period completes.

## Important Boundary

This is analysis-only.

The simulator does not:

- Write to `paper_portfolios`.
- Write to `paper_positions`.
- Write to `paper_trades`.
- Modify recommendations.
- Modify scoring.
- Modify strategy factors.
- Place orders.

It reconstructs portfolio state in memory from frozen pilot data.

## Closed Trade Display

Positions are closed when the simulation date reaches the planned exit date:

```text
current_date >= planned_exit_date
```

Closed trades are returned with:

- `status=closed`
- `exit_reason=planned_exit`

The UI displays them in the `Closed Trades` section with a distinct closed badge and tinted row style.

## Frontend Runtime

Use the production-mode restart script for normal operation:

```powershell
.\scripts\restart_research_cockpit_frontend.ps1
```

This stops any existing frontend process, clears stale `.next` artifacts, rebuilds, and starts `next start` on `127.0.0.1:3000`.

Use dev mode only while actively editing frontend code:

```powershell
.\scripts\restart_research_cockpit_frontend.ps1 -Dev
```

Avoid running `npm run build` while `next dev` is still running; that can corrupt the dev server cache and cause `Cannot find module './*.js'` or missing `_next/static` chunk errors.

## Notes

If the selected start date is not an available recommendation date, the backend uses the first weekly recommendation date on or after the selected date and returns it as `effective_start_date`.

The purpose is operator understanding and portfolio construction review, not live paper state mutation.
