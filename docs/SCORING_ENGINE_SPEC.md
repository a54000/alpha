# Scoring Engine Specification

## Design Principles

1. All weights are explicit — no defaults, no inference
2. Scores are additive within each category
3. Category scores are weighted-summed to a final 0–100 score
4. Every stock in NSE500 receives a score every trading day
5. Rankings are purely ordinal — top N by score
6. Score bands are for human interpretation only, not entry gates

---

## Score Band Reference (All Models)

| Score | Interpretation |
|-------|----------------|
| 90–100 | Exceptional Opportunity |
| 80–89 | Strong Opportunity |
| 70–79 | Worth Watching |
| 60–69 | Weak Signal |
| < 60 | Not Eligible |

---

## Model A: Swing Score

**Horizon:** 5–30 days
**Composition:** 100% Technical

```
Total = 100 points

  Trend            30 pts
  Momentum         30 pts
  Volume           20 pts
  Breakout         10 pts
  Relative Strength 10 pts
```

---

### Trend (30 points)

**ADX Strength + Direction (20 pts)**

| Condition | Points |
|-----------|--------|
| adx_14 >= 35 AND adx_14 > adx_prev | 20 |
| adx_14 >= 25 AND adx_14 > adx_prev | 14 |
| adx_14 >= 25 AND adx_14 <= adx_prev | 8 |
| adx_14 >= 20 | 4 |
| adx_14 < 20 | 0 |

**EMA Short-Term Alignment (10 pts)**

| Condition | Points |
|-----------|--------|
| close > ema_5 AND ema_5 > ema_13 | 10 |
| close > ema_13 | 6 |
| close > ema_20 | 3 |
| close <= ema_20 | 0 |

---

### Momentum (30 points)

**RSI (15 pts)**

| Condition | Points |
|-----------|--------|
| 55 <= rsi_14 <= 68 | 15 |
| 50 <= rsi_14 < 55 | 9 |
| 68 < rsi_14 <= 75 | 7 |
| 45 <= rsi_14 < 50 | 4 |
| rsi_14 > 75 (overbought) | 2 |
| rsi_14 < 45 | 0 |

**MACD Histogram (10 pts)**

| Condition | Points |
|-----------|--------|
| macd_hist > 0 AND macd_hist > macd_hist_prev | 10 |
| macd_hist > 0 AND macd_hist <= macd_hist_prev | 5 |
| macd_hist < 0 AND macd_hist > macd_hist_prev | 3 |
| macd_hist < 0 AND macd_hist <= macd_hist_prev | 0 |

**Stochastic (5 pts)**

| Condition | Points |
|-----------|--------|
| stoch_k > stoch_d AND stoch_k between 50–80 | 5 |
| stoch_k > stoch_d AND stoch_k < 50 | 3 |
| stoch_k > stoch_d AND stoch_k > 80 | 1 |
| stoch_k <= stoch_d | 0 |

---

### Volume (20 points)

**Volume Ratio (20 pts)**

| Condition | Points |
|-----------|--------|
| volume_ratio >= 3.0 | 20 |
| volume_ratio >= 2.0 | 15 |
| volume_ratio >= 1.5 | 10 |
| volume_ratio >= 1.2 | 5 |
| volume_ratio < 1.2 | 0 |

---

### Breakout (10 points)

**52-Week High Proximity (6 pts)**

| Condition | Points |
|-----------|--------|
| pct_from_52w_high >= -2% | 6 |
| pct_from_52w_high >= -5% | 4 |
| pct_from_52w_high >= -10% | 2 |
| pct_from_52w_high < -10% | 0 |

**Bollinger Squeeze (4 pts)**

| Condition | Points |
|-----------|--------|
| bb_width < bb_width_20avg * 0.70 | 4 |
| bb_width < bb_width_20avg * 0.85 | 2 |
| bb_width >= bb_width_20avg | 0 |

---

### Relative Strength (10 points)

**RS Rank Percentile (10 pts)**

| Condition | Points |
|-----------|--------|
| rs_rank_pct >= 90 | 10 |
| rs_rank_pct >= 75 | 7 |
| rs_rank_pct >= 60 | 4 |
| rs_rank_pct >= 50 | 2 |
| rs_rank_pct < 50 | 0 |

---

## Model B: Positional Score

**Horizon:** 1–6 months
**Composition:** 40% Trend + 30% Relative Strength + 20% Sector + 10% Volume

```
Total = 100 points

  Trend              40 pts
  Relative Strength  30 pts
  Sector Strength    20 pts
  Volume             10 pts
```

---

### Trend (40 points)

**EMA Stage 2 Alignment (25 pts)**

| Condition | Points |
|-----------|--------|
| close > ema_50 AND ema_50 > ema_150 AND ema_150 > ema_200 | 25 |
| close > ema_50 AND close > ema_200 | 16 |
| close > ema_200 only | 8 |
| close < ema_200 | 0 |

*Stage 2 (Weinstein) = the most reliable multi-month uptrend condition.*

**ADX Medium-Term (15 pts)**

| Condition | Points |
|-----------|--------|
| adx_14 >= 30 AND adx_14 > adx_prev | 15 |
| adx_14 >= 25 | 9 |
| adx_14 >= 20 | 4 |
| adx_14 < 20 | 0 |

---

### Relative Strength (30 points)

**RS Rank Percentile — 20-day (18 pts)**

| Condition | Points |
|-----------|--------|
| rs_rank_pct >= 85 | 18 |
| rs_rank_pct >= 70 | 12 |
| rs_rank_pct >= 55 | 6 |
| rs_rank_pct < 55 | 0 |

**RS vs Nifty — 60-day (12 pts)**

| Condition | Points |
|-----------|--------|
| rs_vs_nifty_60d >= 1.20 | 12 |
| rs_vs_nifty_60d >= 1.10 | 8 |
| rs_vs_nifty_60d >= 1.00 | 4 |
| rs_vs_nifty_60d < 1.00 | 0 |

---

### Sector Strength (20 points)

**Sector 3-Month Performance Rank (20 pts)**

The sector rotation engine ranks all sectors by 3-month return daily.
Rank 1 = strongest sector.

| Condition | Points |
|-----------|--------|
| sector_3m_rank == 1 | 20 |
| sector_3m_rank == 2 | 17 |
| sector_3m_rank == 3 | 14 |
| sector_3m_rank 4–5 | 10 |
| sector_3m_rank 6–8 | 5 |
| sector_3m_rank >= 9 | 0 |

*Sector taxonomy: see `sector_master` table (19 sectors).*

---

### Volume (10 points)

**Volume Ratio (10 pts)**

| Condition | Points |
|-----------|--------|
| volume_ratio >= 2.0 | 10 |
| volume_ratio >= 1.5 | 7 |
| volume_ratio >= 1.2 | 4 |
| volume_ratio < 1.2 | 0 |

---

## Model C: Long-Term Score

**Horizon:** 1–3 years
**Composition:** 40% Growth + 30% Quality + 15% Valuation + 15% Trend

```
Total = 100 points

  Growth Quality     40 pts   (Revenue CAGR + PAT CAGR)
  Business Quality   30 pts   (ROE + ROCE + Debt)
  Valuation          15 pts   (PE vs sector median)
  Price Trend        15 pts   (EMA200 + RS 60d)
```

*All fundamental inputs use announced_date + 5-day lag to prevent
look-ahead bias. If quarterly data is unavailable, this model
returns null for that stock (not zero).*

---

### Growth Quality (40 points)

**Revenue CAGR 3-Year (20 pts)**

| Condition | Points |
|-----------|--------|
| revenue_cagr_3y >= 25% | 20 |
| revenue_cagr_3y >= 18% | 14 |
| revenue_cagr_3y >= 12% | 8 |
| revenue_cagr_3y >= 6% | 3 |
| revenue_cagr_3y < 6% | 0 |

**PAT CAGR 3-Year (20 pts)**

| Condition | Points |
|-----------|--------|
| pat_cagr_3y >= 25% | 20 |
| pat_cagr_3y >= 18% | 14 |
| pat_cagr_3y >= 10% | 8 |
| pat_cagr_3y >= 5% | 3 |
| pat_cagr_3y < 5% | 0 |

---

### Business Quality (30 points)

**ROE — Return on Equity (12 pts)**

| Condition | Points |
|-----------|--------|
| roe >= 25% | 12 |
| roe >= 18% | 8 |
| roe >= 12% | 4 |
| roe < 12% | 0 |

**ROCE — Return on Capital Employed (12 pts)**

| Condition | Points |
|-----------|--------|
| roce >= 25% | 12 |
| roce >= 18% | 8 |
| roce >= 12% | 4 |
| roce < 12% | 0 |

**Debt / Equity (6 pts)**

| Condition | Points |
|-----------|--------|
| debt_equity <= 0.2 | 6 |
| debt_equity <= 0.5 | 4 |
| debt_equity <= 1.0 | 2 |
| debt_equity > 1.0 | 0 |

---

### Valuation (15 points)

**PE Relative to Sector Median (15 pts)**

```
pe_relative = stock_pe / sector_median_pe

Interpretation:
  Stock trading at discount to sector = higher score
  Stock trading at premium = lower score
```

| Condition | Points |
|-----------|--------|
| pe_relative <= 0.70 (30% discount) | 15 |
| pe_relative <= 0.85 (15% discount) | 11 |
| pe_relative <= 1.00 (at par) | 7 |
| pe_relative <= 1.20 (20% premium) | 3 |
| pe_relative > 1.20 | 0 |

*Sector median PE is computed fresh each quarter from all NSE500
stocks in the same sector with positive earnings.*

---

### Price Trend (15 points)

**EMA 200 Position (9 pts)**

| Condition | Points |
|-----------|--------|
| close > ema_200 AND pct_from_52w_high >= -20% | 9 |
| close > ema_200 | 5 |
| close < ema_200 | 0 |

**RS vs Nifty — 60-day (6 pts)**

| Condition | Points |
|-----------|--------|
| rs_vs_nifty_60d >= 1.10 | 6 |
| rs_vs_nifty_60d >= 1.00 | 3 |
| rs_vs_nifty_60d < 1.00 | 0 |

---

## Score Output Format

```python
# daily_scores table — one row per symbol per day
{
    "symbol": "BEL",
    "date": "2026-06-10",

    # Final scores
    "swing_score":    91.0,
    "position_score": 74.0,
    "lt_score":       65.0,

    # Swing component breakdown
    "swing_trend":     24,   # out of 30
    "swing_momentum":  22,   # out of 30
    "swing_volume":    15,   # out of 20
    "swing_breakout":   8,   # out of 10
    "swing_rs":        10,   # out of 10  → but capped at 30 for this example
    # note: sum of components may differ from final due to cap

    # Risk levels (ATR-based)
    "stop_loss":   514.78,
    "target_1":    686.90,
    "target_2":   1092.00,
    "target_3":   1498.00,
    "rr_ratio":      2.1
}
```

---

## Implementation Notes

### Null handling

- If any required feature is NULL, that signal scores 0 (not error)
- If > 50% of signals are NULL for a stock, exclude from rankings
  and log to `data_quality_log`

### Cross-sectional dependency

`rs_rank_pct` requires all 500 stocks computed before any can be ranked.
Scoring pipeline must run in two passes:

```
Pass 1: Compute all point-in-time features for all 500 stocks
Pass 2: Compute cross-sectional ranks (rs_rank_pct, sector ranks)
Pass 3: Compute final scores using Pass 1 + Pass 2 outputs
```

### Version tagging

Every score written to `daily_scores` must reference the active
`model_version` row for that model. This enables comparing
"what would v1.1 have scored on 2026-01-15" against actual v1.0 history.

```sql
ALTER TABLE daily_scores ADD COLUMN model_version_id INTEGER
    REFERENCES model_version(version_id);
```

---

## Pre-Scoring Eligibility Filter

Applied before any model scores a stock. Stocks failing this filter
receive score = NULL and are excluded from all rankings.

```yaml
eligibility_filters:
  min_avg_traded_value_20d: 10_00_00_000   # INR 10 Crore per day
  min_avg_volume_20d:       100_000         # shares per day
  min_price:                10              # INR — exclude sub-10 stocks
  min_history_days:         60             # minimum trading history
  listed:                   true           # must be currently in NSE500
```

**Rationale:**
- ₹10 Cr daily traded value ensures a ₹1L position can enter/exit
  without meaningful price impact
- Prevents illiquid microcaps from spiking to #1 on a single
  abnormal volume day
- Sub-₹10 stocks are excluded — volatility is noise, not signal

**Implementation:**
```python
# Run BEFORE compute_swing_score(), compute_positional_score(), compute_lt_score()
def is_eligible(symbol, date, features) -> bool:
    avg_tv = features['avg_price_20d'] * features['volume_20avg']
    return (
        avg_tv >= 1e8 and          # 10 Cr
        features['volume_20avg'] >= 100_000 and
        features['close'] >= 10 and
        features['history_days'] >= 60
    )
```

Eligibility is computed and stored in `features_daily.is_eligible` (BOOLEAN).
