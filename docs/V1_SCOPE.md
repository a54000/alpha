# V1 Scope

## One Rule

V1 is finished when this works reliably every morning:

```
By 8:00 AM IST, every trading day:

1. Refresh price data
2. Compute features and scores for all NSE500 stocks
3. Generate Top 20 rankings (Swing, Positional, Long-Term)
4. Send email digest

Backtests run weekly (every Sunday) or after any model/weight change.
They do NOT run in the morning pipeline.
```

**No news AI. No agents. No vector DB. No ML. No LLM narratives.**

If it does exactly this, V1 is a success.

---

## What V1 Includes

| Component | In V1? |
|-----------|--------|
| NSE500 price fetch (daily) | ✅ |
| 20 technical indicators | ✅ |
| Swing scoring model | ✅ |
| Positional scoring model | ✅ |
| Long-term scoring model (fundamentals-led) | ✅ |
| Sector rotation (price-based) | ✅ |
| features_daily table | ✅ |
| recommendation_history table | ✅ |
| Backtesting engine | ✅ |
| Daily email digest | ✅ |
| Streamlit dashboard | ✅ |
| Fundamentals data | ✅ (basic: PE, ROE from screener) |
| Portfolio positions table | ✅ (manual entry) |

## What V1 Explicitly Excludes

| Component | Milestone |
|-----------|-----------|
| News ingestion | M2 |
| LLM event analysis | M2 |
| LLM narrative explanations | M2 |
| Vector DB / signal memory | M3 |
| Real-time / intraday data | M3 |
| WhatsApp alerts | M2 |
| Institutional flow tracking | M2 |
| Agentic workflows | M4 |
| ML prediction models | Never |

---

## V1 Milestone Timeline

### Week 1 — Data Foundation
- [ ] PostgreSQL setup with all tables
- [ ] NSE500 symbol list loaded
- [ ] 2 years of historical OHLCV fetched
- [ ] Daily price update job working
- [ ] features_daily table populated

### Week 2 — Scoring Engine
- [ ] All 20 indicators computing correctly
- [ ] Swing model scoring NSE500
- [ ] Positional model scoring NSE500
- [ ] LT model scoring NSE500
- [ ] recommendation_history writing daily

### Week 3 — Backtest + Fundamentals
- [ ] Backtesting engine running against 1 year history
- [ ] Win rate, Sharpe, drawdown computing correctly
- [ ] Basic fundamentals (PE, ROE) from screener
- [ ] Sector rotation engine

### Week 4 — Output
- [ ] Streamlit dashboard showing top 20 per model
- [ ] Daily email digest formatted and sending
- [ ] 7AM IST cron job stable
- [ ] End-to-end test: one full trading week

---

## V1 Done Criteria

Before declaring V1 complete, answer yes to all:

- [ ] Has it run without failure for 5 consecutive trading days?
- [ ] Does backtested swing win rate exceed 50%?
- [ ] Does the email arrive before 8AM IST?
- [ ] Can you explain why each top-ranked stock appears there?
- [ ] Is recommendation_history tracking correctly?

---

## Additional V1 Requirements

### Data Quality & Observability

The platform must track all ingestion and scoring jobs.

**Required table: `data_quality_log`**

| Column | Type |
|--------|------|
| date | DATE |
| job_name | VARCHAR |
| records_expected | INTEGER |
| records_loaded | INTEGER |
| status | VARCHAR |
| error_message | TEXT |

**Required table: `pipeline_runs`**

| Column | Type |
|--------|------|
| run_id | SERIAL |
| job_name | VARCHAR |
| start_time | TIMESTAMP |
| end_time | TIMESTAMP |
| status | VARCHAR |
| duration_seconds | NUMERIC |

### Universe Snapshot

To avoid survivorship bias during backtesting, a daily snapshot of NSE500
membership must be maintained.

**Required table: `universe_snapshot`**

| Column | Type |
|--------|------|
| date | DATE |
| symbol | VARCHAR |
| index_name | VARCHAR |

### Portfolio Tracking

Portfolio tracking is included in V1 via manual position entry.

**Required table: `portfolio_positions`**

| Column | Type |
|--------|------|
| symbol | VARCHAR |
| quantity | INTEGER |
| avg_cost | NUMERIC |
| entry_date | DATE |
| strategy | VARCHAR |

### Score Calibration

All three models use the same score band interpretation:

| Score | Interpretation |
|-------|----------------|
| 90–100 | Exceptional Opportunity |
| 80–89 | Strong Opportunity |
| 70–79 | Worth Watching |
| 60–69 | Weak Opportunity |
| < 60 | Not Eligible |

**Rankings are purely ordinal — Top 20 stocks by score appear regardless of absolute score value.**
Stocks with score < 60 are displayed with a ⚠ warning indicator but are NOT excluded.
This prevents empty rankings on low-signal days and avoids hardcoding an untested threshold.

---

## Long-Term Model Definition (V1)

**Purpose:** Identify stocks suitable for 1–3 year holding periods.

The LT model relies primarily on fundamentals and business quality,
not short-term technical signals.

**Inputs:**

| Factor | Weight |
|--------|--------|
| Revenue Growth | 25% |
| ROE | 20% |
| Valuation (PE relative to sector) | 15% |
| Price Trend | 15% |
| Sector Strength | 15% |
| Relative Strength | 10% |

**Output:**

```json
{
  "symbol": "DIXON",
  "lt_score": 91
}
```
