# Signal Weights Specification

## Design Principle

Every weight is explicit and versioned. When backtests show a model
underperforming, you change weights here and rerun — not in code.

---

## Model A: Swing (5–30 days)

**Total: 100 points**

```yaml
swing_model:
  version: "1.0"

  momentum:
    weight: 35
    signals:
      rsi:
        weight: 15
        rules:
          - condition: "50 <= rsi_14 <= 70"
            score: 15
          - condition: "45 <= rsi_14 < 50"
            score: 8
          - condition: "rsi_14 > 70"
            score: 5       # overbought, penalise
          - condition: "rsi_14 < 45"
            score: 0

      macd:
        weight: 10
        rules:
          - condition: "macd_hist > 0 AND macd_hist > macd_hist_prev"
            score: 10      # rising histogram — strongest signal
          - condition: "macd_hist > 0 AND macd_hist <= macd_hist_prev"
            score: 5       # positive but slowing
          - condition: "macd_hist < 0 AND macd_hist > macd_hist_prev"
            score: 3       # negative but improving
          - condition: "macd_hist < 0 AND macd_hist <= macd_hist_prev"
            score: 0

      adx:
        weight: 10
        rules:
          - condition: "adx_14 >= 35 AND adx_14 > adx_prev"
            score: 10
          - condition: "adx_14 >= 25 AND adx_14 > adx_prev"
            score: 7
          - condition: "adx_14 >= 20"
            score: 3
          - condition: "adx_14 < 20"
            score: 0       # no trend

  volume:
    weight: 20
    signals:
      volume_ratio:
        weight: 20
        rules:
          - condition: "volume_ratio >= 3.0"
            score: 20
          - condition: "volume_ratio >= 2.0"
            score: 15
          - condition: "volume_ratio >= 1.5"
            score: 10
          - condition: "volume_ratio >= 1.2"
            score: 5
          - condition: "volume_ratio < 1.2"
            score: 0

  breakout:
    weight: 25
    signals:
      proximity_52w_high:
        weight: 15
        rules:
          - condition: "pct_from_52w_high >= -2"
            score: 15      # within 2% of 52W high
          - condition: "pct_from_52w_high >= -5"
            score: 10
          - condition: "pct_from_52w_high >= -10"
            score: 5
          - condition: "pct_from_52w_high < -10"
            score: 0

      bollinger_squeeze:
        weight: 10
        rules:
          - condition: "bb_width < bb_width_20avg * 0.70"
            score: 10      # strong squeeze — coiled spring
          - condition: "bb_width < bb_width_20avg * 0.85"
            score: 6
          - condition: "bb_width >= bb_width_20avg"
            score: 0

  relative_strength:
    weight: 20
    signals:
      rs_rank_percentile:
        weight: 20
        rules:
          - condition: "rs_rank_pct >= 90"
            score: 20
          - condition: "rs_rank_pct >= 75"
            score: 15
          - condition: "rs_rank_pct >= 60"
            score: 10
          - condition: "rs_rank_pct >= 50"
            score: 5
          - condition: "rs_rank_pct < 50"
            score: 0
```

---

## Model B: Positional (1–6 months)

**Total: 100 points**
**Mix: 50% technical + 30% fundamental + 20% sector**

```yaml
positional_model:
  version: "1.0"

  technical:
    weight: 50
    signals:

      ema_alignment:
        weight: 20
        rules:
          - condition: "close > ema_50 > ema_150 > ema_200"
            score: 20      # perfect Weinstein Stage 2
          - condition: "close > ema_50 AND close > ema_200"
            score: 12
          - condition: "close > ema_200"
            score: 6
          - condition: "close < ema_200"
            score: 0

      adx_trend:
        weight: 15
        rules:
          - condition: "adx_14 >= 30 AND adx_14 > adx_prev"
            score: 15
          - condition: "adx_14 >= 20"
            score: 8
          - condition: "adx_14 < 20"
            score: 0

      relative_strength_60d:
        weight: 15
        rules:
          - condition: "rs_rank_pct >= 80"
            score: 15
          - condition: "rs_rank_pct >= 65"
            score: 10
          - condition: "rs_rank_pct >= 50"
            score: 5
          - condition: "rs_rank_pct < 50"
            score: 0

  fundamental:
    weight: 30
    signals:

      earnings_growth:
        weight: 15
        rules:
          - condition: "pat_yoy_pct >= 25"
            score: 15
          - condition: "pat_yoy_pct >= 15"
            score: 10
          - condition: "pat_yoy_pct >= 5"
            score: 5
          - condition: "pat_yoy_pct < 5"
            score: 0

      roe:
        weight: 8
        rules:
          - condition: "roe >= 20"
            score: 8
          - condition: "roe >= 15"
            score: 5
          - condition: "roe >= 10"
            score: 2
          - condition: "roe < 10"
            score: 0

      debt_equity:
        weight: 7
        rules:
          - condition: "debt_equity <= 0.3"
            score: 7
          - condition: "debt_equity <= 0.7"
            score: 4
          - condition: "debt_equity <= 1.5"
            score: 1
          - condition: "debt_equity > 1.5"
            score: 0

  sector:
    weight: 20
    signals:
      sector_rotation_score:
        weight: 20
        rules:
          - condition: "sector_3m_rank <= 3"
            score: 20      # top 3 performing sectors
          - condition: "sector_3m_rank <= 6"
            score: 12
          - condition: "sector_3m_rank <= 10"
            score: 6
          - condition: "sector_3m_rank > 10"
            score: 0
```

---

## Model C: Long-Term (1–3 years)

**Total: 100 points**
**Mix: 25% revenue growth + 20% ROE + 15% valuation + 15% price trend + 15% sector strength + 10% relative strength**

The LT model relies primarily on fundamentals and business quality,
not short-term technical signals.

```yaml
lt_model:
  version: "1.1"

  revenue_growth:
    weight: 25
    signals:
      revenue_cagr_3y:
        weight: 25
        rules:
          - condition: "revenue_cagr_3y >= 25"
            score: 25
          - condition: "revenue_cagr_3y >= 18"
            score: 18
          - condition: "revenue_cagr_3y >= 12"
            score: 10
          - condition: "revenue_cagr_3y >= 6"
            score: 4
          - condition: "revenue_cagr_3y < 6"
            score: 0

  roe:
    weight: 20
    signals:
      roe_latest:
        weight: 20
        rules:
          - condition: "roe >= 25"
            score: 20
          - condition: "roe >= 18"
            score: 14
          - condition: "roe >= 12"
            score: 7
          - condition: "roe < 12"
            score: 0

  valuation:
    weight: 15
    signals:
      pe_vs_sector:
        weight: 15
        rules:
          - condition: "pe_ratio < sector_median_pe * 0.75"
            score: 15      # meaningfully cheaper than sector
          - condition: "pe_ratio < sector_median_pe * 0.90"
            score: 10
          - condition: "pe_ratio <= sector_median_pe * 1.10"
            score: 6       # fairly valued
          - condition: "pe_ratio > sector_median_pe * 1.10"
            score: 2       # premium — quality costs, not zero

  price_trend:
    weight: 15
    signals:
      ema_200:
        weight: 10
        rules:
          - condition: "close > ema_200 AND pct_from_52w_high >= -20"
            score: 10
          - condition: "close > ema_200"
            score: 6
          - condition: "close < ema_200"
            score: 0
      debt_equity:
        weight: 5
        rules:
          - condition: "debt_equity <= 0.2"
            score: 5
          - condition: "debt_equity <= 0.5"
            score: 3
          - condition: "debt_equity > 0.5"
            score: 0

  sector_strength:
    weight: 15
    signals:
      sector_rotation_6m:
        weight: 15
        rules:
          - condition: "sector_6m_rank <= 3"
            score: 15
          - condition: "sector_6m_rank <= 7"
            score: 9
          - condition: "sector_6m_rank > 7"
            score: 3

  relative_strength:
    weight: 10
    signals:
      rs_rank_pct:
        weight: 10
        rules:
          - condition: "rs_rank_pct >= 75"
            score: 10
          - condition: "rs_rank_pct >= 55"
            score: 6
          - condition: "rs_rank_pct < 55"
            score: 0
```

```

---

## Score Interpretation

| Score | Interpretation | Eligible for Ranking? |
|-------|----------------|-----------------------|
| 90–100 | Exceptional Opportunity | ✅ Yes |
| 80–89 | Strong Opportunity | ✅ Yes |
| 70–79 | Worth Watching | ✅ Yes |
| 60–69 | Weak Opportunity | ✅ Yes |
| < 60 | Not Eligible | ❌ No |

**Stocks scoring below 60 are excluded from all Top 20 outputs.**

---

## Version History

| Version | Date | Change |
|---------|------|--------|
| 1.0 | 2026-06-10 | Initial weights — pre-backtest. Models A and B. LT model was technical-only. |
| 1.1 | 2026-06-10 | LT model (Model C) replaced with fundamentals-led spec: Revenue Growth 25%, ROE 20%, Valuation 15%, Price Trend 15%, Sector Strength 15%, Relative Strength 10%. Score bands updated to align with V1_SCOPE calibration. |

**Rule:** After every 3-month backtest review, update version and log
what changed and why. Never change weights without a documented reason.
