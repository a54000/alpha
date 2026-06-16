# Codex Working Rules

## Purpose

This document governs how Codex (or any AI coding assistant) must behave
when working on the NSE Research Platform. These rules exist because AI
assistants have a well-documented failure mode: they fill in gaps with
plausible-looking decisions that silently contradict the specification.

Every rule below exists to prevent a specific class of drift.

---

## Non-Negotiable Rules

### Rule 1 — Never invent scoring weights

All model weights are defined in `/docs/SIGNAL_WEIGHTS.md`.

If a weight is missing for a signal you are implementing, **stop and ask**.
Do not substitute a "reasonable" default. A 10% vs 20% weight difference
can make a model look 30% better in backtest — this is not a trivial choice.

```
❌ WRONG:  adx_score = adx_value * 0.15   # seems reasonable
✅ RIGHT:  adx_score = adx_value * WEIGHTS['swing']['momentum']['adx']
```

---

### Rule 2 — All weights must come from PRD documents

The chain of authority is:

```
MASTER_PRD.md → SIGNAL_WEIGHTS.md → code
```

If you cannot trace a number back to a document, it does not belong in the
code. This applies to: scoring weights, thresholds, holding periods,
rebalance frequencies, slippage assumptions, capital allocation.

---

### Rule 3 — Write tests before implementation

For every scoring function, write the test first.

```python
# Write this FIRST:
def test_swing_score_perfect_setup():
    """A stock with RSI 62, ADX 38, volume 3x, near 52W high
    should score >= 80."""
    score = compute_swing_score(mock_perfect_stock())
    assert score >= 80

# Then implement compute_swing_score()
```

Tests must cover:
- Perfect signal (all conditions met)
- Zero signal (all conditions failed)
- Edge cases (RSI exactly 50, ADX exactly 25, etc.)
- Score banding (score < 60 must never appear in Top 20)

---

### Rule 4 — Produce a design note before coding major modules

Before writing code for any of these, produce a short design note (inline
comment block or separate `.md` in `/docs/design-notes/`) that states:

- What this module does
- What it reads (inputs, table names, columns)
- What it writes (outputs, table names, columns)
- What it does NOT do

```python
"""
MODULE: swing_model.py

DOES:
  Reads features_daily for a given date.
  Applies SIGNAL_WEIGHTS swing rules.
  Writes swing_score + component scores to daily_scores.

READS:
  features_daily (symbol, date, rsi_14, adx_14, macd_hist,
                  volume_ratio, pct_from_52w_high, bb_width,
                  bb_width_20avg, rs_rank_pct)

WRITES:
  daily_scores (symbol, date, swing_score,
                swing_momentum, swing_volume,
                swing_breakout, swing_rs)

DOES NOT:
  Fetch prices. Compute indicators. Generate explanations.
  Make any external API calls.
"""
```

---

### Rule 5 — No ML models in V1

V1 uses deterministic, rules-based scoring only.

The following are banned in V1:
- `sklearn`, `xgboost`, `lightgbm`, `tensorflow`, `torch`
- Any `fit()`, `predict()`, `transform()` pipeline
- Any feature importance calculation
- Any cross-validation or hyperparameter tuning

If you believe ML would improve a specific component, document it in
`/docs/FUTURE_IDEAS.md` for consideration in a later milestone.

---

### Rule 6 — No news processing in V1

The following are banned in V1:
- RSS feed ingestion
- Any LLM API calls for news analysis
- Sentiment scoring from headlines
- `news` table writes from automated jobs

The `news` table may exist in the schema but must not be populated
by any V1 pipeline job.

---

### Rule 7 — No LLM-generated stock recommendations

LLMs may not generate, rank, or score stocks in V1.

Permitted LLM usage in V1: zero.

If a function takes a stock symbol as input and returns text that
influences a ranking decision, it is banned in V1 regardless of how
it is framed.

---

### Rule 8 — All backtests must use next-day-open execution

```python
# Signal fires on date D using close price
# Entry must use open price of date D+1

❌ WRONG:  entry_price = prices.loc[signal_date, 'close']
✅ RIGHT:  entry_price = prices.loc[signal_date + 1_trading_day, 'open']
```

Any backtest result that uses same-day close execution is invalid and
must be discarded. This is the single most common source of look-ahead
bias in retail backtesting.

---

### Rule 9 — Every feature must be registered before use

Before any feature can be consumed by a model, it must exist in
`/docs/FEATURE_REGISTRY.yaml`.

```yaml
# Before adding rsi_14 to swing_model.py, this must exist:
rsi_14:
  source: prices
  formula: "RSI(close, period=14)"
  refresh: daily
  table: features_daily
  column: rsi_14
```

If you add a new indicator to `features_daily`, update
`FEATURE_REGISTRY.yaml` in the same commit.

---

### Rule 10 — Schema changes require migration scripts

No `ALTER TABLE` may be run manually against any environment.

Every schema change must be expressed as a numbered migration script:

```
/migrations/
  001_initial_schema.sql
  002_add_rs_rank_pct.sql
  003_add_universe_snapshot.sql
```

Migration scripts are append-only. Never edit a migration that has
already been applied.

---

## Structural Rules

### On file organisation

Follow `/docs/FILE_STRUCTURE.md` exactly. Do not create new top-level
directories without updating that document first.

### On configuration

All thresholds, weights, and parameters live in config files or
`SIGNAL_WEIGHTS.md`. No magic numbers in code.

```python
❌ WRONG:  if score < 60:
✅ RIGHT:  if score < config.MIN_ELIGIBLE_SCORE:  # = 60, from SIGNAL_WEIGHTS
```

### On database access

- All DB access goes through a single connection module (`db/connection.py`)
- No raw SQL strings outside of `/db/` directory
- All queries must be parameterised — no f-string SQL

### On error handling

Pipeline jobs must not silently fail. Every job must:
1. Write a `pipeline_runs` record with status and duration
2. Write a `data_quality_log` record if record counts diverge > 5%
3. Send an alert (log to file in V1, email in M2) on any failure

---

## Decision Log

When Codex makes an architectural decision not covered by these rules,
it must log it:

```
/docs/DECISION_LOG.md

## 2026-06-10
Decision: Used pandas-ta instead of TA-Lib for indicator computation
Reason: TA-Lib requires C compilation which fails on target deployment
        environment. pandas-ta is pure Python with equivalent coverage.
Alternatives considered: talib, custom implementation
Reversible: Yes — all indicator calls are wrapped in features/indicators.py
```

This log is how you audit what changed and why, six months later.

---

## Checklist Before Any PR / Commit

- [ ] No invented weights or thresholds
- [ ] All new features registered in FEATURE_REGISTRY.yaml
- [ ] Tests written and passing
- [ ] No ML imports
- [ ] No LLM calls
- [ ] Backtest uses next-day-open
- [ ] Schema changes have migration scripts
- [ ] Design note written for any new module > 100 lines
- [ ] Decision log updated if an undocumented choice was made
