# Indicator Specification

## Rules

1. All indicators are computed by `features/indicators.py`
2. All outputs are written to `features_daily` table
3. No model may compute an indicator inline — always read from `features_daily`
4. Minimum history required before an indicator is valid is noted per indicator
5. Use `pandas-ta` as the primary library (pure Python, no C compilation)

---

## Group 1: Momentum (4 indicators)

### RSI — Relative Strength Index

```
Formula:    RSI(close, period=N)
Variants:   rsi_14 (primary), rsi_9 (secondary)
Min history: N + 1 periods

Interpretation:
  > 70   : Overbought — penalise in swing model
  50–70  : Momentum zone — sweet spot for swing entries
  45–50  : Neutral
  < 45   : Weak — zero score

Library:    pandas_ta.rsi(close, length=14)
Column:     rsi_14, rsi_9
```

---

### MACD — Moving Average Convergence Divergence

```
Formula:    MACD(close, fast=12, slow=26, signal=9)
Outputs:    macd_line, macd_signal, macd_hist
            macd_hist_prev  ← previous day histogram (join on date-1)
Min history: 26 + 9 = 35 periods

Key signal: histogram direction (rising vs falling)
  macd_hist > 0 AND rising  : strongest bullish signal
  macd_hist > 0 AND falling : weakening
  macd_hist < 0 AND rising  : potential reversal forming
  macd_hist < 0 AND falling : bearish, no score

Library:    pandas_ta.macd(close, fast=12, slow=26, signal=9)
Columns:    macd_line, macd_signal, macd_hist, macd_hist_prev
```

---

### Stochastic Oscillator

```
Formula:    STOCH(high, low, close, k=14, d=3, smooth_k=3)
Outputs:    stoch_k, stoch_d
Min history: 14 + 3 = 17 periods

Key signal: K > D crossover (PCO state)
  k > d AND k > 80  : overbought, use with caution
  k > d AND 50-80   : bullish momentum confirmed
  k > d AND k < 50  : early signal, lower confidence
  k < d             : bearish, no score

Library:    pandas_ta.stoch(high, low, close, k=14, d=3, smooth_k=3)
Columns:    stoch_k, stoch_d
```

---

### ADX — Average Directional Index

```
Formula:    ADX(high, low, close, period=14)
Outputs:    adx_14, adx_prev
Min history: 14 * 2 = 28 periods (ADX needs extra warmup)

Interpretation:
  >= 35 AND rising  : very strong trend
  >= 25 AND rising  : strong trend — confirmed signal
  >= 20             : trend present but weak
  < 20              : no trend — avoid momentum strategies

Note: ADX measures trend STRENGTH, not direction.
      Always combine with EMA direction to confirm bullish/bearish.

Library:    pandas_ta.adx(high, low, close, length=14)['ADX_14']
Columns:    adx_14, adx_prev
```

---

## Group 2: Trend (6 indicators)

### EMA Stack — Exponential Moving Averages

```
Variants:   ema_5, ema_13, ema_20, ema_50, ema_150, ema_200
Min history: 200 periods for full stack

Key patterns:
  Swing:      close > ema_5 > ema_13  (short-term bullish)
  Positional: close > ema_50 > ema_150 > ema_200  (Stage 2 uptrend)
  Long-Term:  close > ema_200  (above long-term trend line)

Weinstein Stage 2 condition (positional model):
  close > ema_50 > ema_150 > ema_200 = perfect alignment

Library:    pandas_ta.ema(close, length=N)
Columns:    ema_5, ema_13, ema_20, ema_50, ema_150, ema_200
```

---

## Group 3: Volatility (4 indicators)

### Bollinger Bands

```
Formula:    BBANDS(close, period=20, std_dev=2)
Outputs:    bb_upper, bb_mid, bb_lower, bb_width, bb_width_20avg, bb_pct
Min history: 20 periods

Derived:
  bb_width      = (bb_upper - bb_lower) / bb_mid
  bb_width_20avg = rolling 20-day mean of bb_width
  bb_pct        = (close - bb_lower) / (bb_upper - bb_lower)
                  0 = at lower band, 1 = at upper band

Key signal — BB Squeeze:
  bb_width < bb_width_20avg * 0.70  : strong squeeze (coiled spring)
  bb_width < bb_width_20avg * 0.85  : moderate squeeze
  bb_width >= bb_width_20avg        : expanded, no squeeze

Library:    pandas_ta.bbands(close, length=20, std=2)
Columns:    bb_upper, bb_mid, bb_lower, bb_width, bb_width_20avg, bb_pct
```

---

### ATR — Average True Range

```
Formula:    ATR(high, low, close, period=14)
Output:     atr_14
Min history: 14 periods

Use:        Stop loss calculation ONLY — not a scoring signal
            stop_loss = entry_price - (1.5 * atr_14)
            floor:     entry_price * 0.92 (max 8% stop)

Library:    pandas_ta.atr(high, low, close, length=14)
Column:     atr_14
```

---

## Group 4: Volume (2 indicators)

### Volume Ratio

```
Formula:    volume / ROLLING_MEAN(volume, 20)
Output:     volume_ratio, volume_20avg
Min history: 20 periods

Interpretation:
  >= 3.0 : exceptional surge — institutional activity likely
  >= 2.0 : strong confirmation signal
  >= 1.5 : moderate confirmation
  >= 1.2 : slight above average
  < 1.2  : no volume confirmation

Note: Volume ratio is computed as of the SIGNAL day (EOD).
      Not adjusted for pre/post market.

Library:    pandas rolling mean on volume column
Columns:    volume_ratio, volume_20avg
```

---

## Group 5: Relative Strength (3 indicators)

### RS vs Nifty 500

```
Formula:    stock_return_Nd / nifty500_return_Nd
  where:    return_Nd = (close_today - close_N_days_ago) / close_N_days_ago

Variants:   rs_vs_nifty_20d, rs_vs_nifty_60d
Min history: 60 periods

Interpretation:
  > 1.0 : outperforming the index
  < 1.0 : underperforming the index
  > 1.2 : strong outperformance

Nifty500 reference: fetch ^CRSLDX or NIFTY500 index from yfinance

Columns:    rs_vs_nifty_20d, rs_vs_nifty_60d
```

---

### RS Rank Percentile (Cross-Sectional)

```
Formula:    PERCENT_RANK(rs_vs_nifty_20d) across all NSE500 on same date

Output:     rs_rank_pct  (0–100)
  100 = strongest relative strength in NSE500
  50  = median
  0   = weakest

IMPORTANT: This is a cross-sectional computation.
  All 500 stocks must have rs_vs_nifty_20d computed BEFORE
  this rank can be calculated for any single stock.

  Compute sequence:
    1. Compute rs_vs_nifty_20d for all 500 stocks
    2. Rank all 500 stocks by rs_vs_nifty_20d
    3. Write rs_rank_pct for each stock

Library:    pandas DataFrame.rank(pct=True) * 100
Column:     rs_rank_pct
```

---

### RS vs Sector

```
Formula:    stock_return_20d / sector_avg_return_20d
  where:    sector_avg = mean return of all stocks in same sector

Output:     rs_vs_sector_20d
Min history: 20 periods

Interpretation:
  > 1.0 : outperforming sector peers
  < 1.0 : sector laggard

Column:     rs_vs_sector_20d
```

---

## Group 6: Breakout Signals (2 computed values)

### 52-Week High / Low

```
Formula:
  high_52w          = ROLLING_MAX(high, 252)
  low_52w           = ROLLING_MIN(low, 252)
  pct_from_52w_high = (close - high_52w) / high_52w * 100  ← negative
  pct_from_52w_low  = (close - low_52w)  / low_52w  * 100  ← positive

Min history: 252 periods

Key signal — proximity to 52W high:
  >= -2%   : at/near breakout zone
  -2% to -5%  : approaching
  -5% to -10% : building base
  < -10%      : far from highs

Columns:    high_52w, low_52w, pct_from_52w_high, pct_from_52w_low
```

---

## Computation Order (Daily Pipeline)

Indicators must be computed in this sequence — some depend on others:

```
1. EMA (5, 13, 20, 50, 150, 200)     ← price only
2. ATR (14)                           ← price only
3. RSI (9, 14)                        ← price only
4. MACD (12, 26, 9)                   ← price only, then lag macd_hist_prev
5. Stochastic (14, 3)                 ← price only
6. ADX (14)                           ← price only, then lag adx_prev
7. Bollinger Bands (20)               ← price only
8. bb_width, bb_width_20avg, bb_pct  ← derived from BB output
9. volume_20avg, volume_ratio         ← volume only
10. high_52w, low_52w                 ← price only
11. pct_from_52w_high, pct_from_52w_low ← derived
12. rs_vs_nifty_20d, rs_vs_nifty_60d ← requires Nifty500 prices
13. rs_vs_sector_20d                  ← requires sector group prices
14. rs_rank_pct                       ← LAST: requires all 500 rs_vs_nifty_20d
```

---

## Minimum History Requirements

Before the pipeline should attempt scoring:

```
Warm-up period required: 252 trading days (~1 year)

For a stock added to NSE500 today:
  - EMA/RSI/MACD computable after ~35 days
  - ADX computable after ~28 days
  - Bollinger computable after ~20 days
  - rs_rank_pct computable after ~20 days
  - 52W high/low computable after ~252 days

Stocks with < 252 days history: include in ranking but
flag with insufficient_history = TRUE in features_daily.
Score them on available indicators only.
```
