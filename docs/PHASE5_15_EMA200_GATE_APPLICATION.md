# Phase 5.15 EMA200 Gate Application

## Objective

Apply the `price > EMA200` finding to the active Swing recommendation path for the primary Top 5 weekly paper strategy.

## Rule Applied

Recommendation candidates must now satisfy:

```text
ema200_extension > 0
```

This is equivalent to:

```text
daily close > daily EMA200
```

The gate is applied during Phase 2D recommendation generation, after Swing V2.1 scores are computed and before ranking.

## What Changed

Updated:

```text
scripts/run_phase2d_pilot_recommendations.py
```

The recommendation generator now excludes candidates whose signal-date price is below or equal to EMA200.

## What Did Not Change

- Scoring weights did not change.
- ADX scoring did not change.
- Sector rank scoring did not change.
- EMA200 upside-extension cap did not change.
- Prior 20-day return cap did not change.
- Paper trading lifecycle did not change.
- Broker integration was not added.

## Operational Impact

The dashboard and paper trading engine read from:

```text
pilot_phase2a.recommendations_daily
```

After Phase 2D is rerun, active recommendations will reflect the EMA200-positive gate.

Because Top 5 and Top 10 currently share the same recommendation table, the Top 10 shadow list will also be drawn from the EMA200-filtered recommendation pool. A separate Top 10 unfiltered shadow model would require a distinct model name or recommendation table partition.

## Validation

Added tests:

```text
tests/test_phase5_15_ema200_recommendation_gate.py
```

The tests verify:

- A high-scoring below-EMA200 candidate is excluded.
- A lower-scoring above-EMA200 candidate can rank first.
- `ema200_extension = 0` is rejected.

