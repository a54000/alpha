# Scoring Validation Reference

Canonical scoring rules for automated test fixtures and manual verification.

**Source documents**

| Document | Role |
|----------|------|
| `docs/SCORING_ENGINE_SPEC.md` | Authoritative weights and scoring tables |
| `docs/FEATURE_REGISTRY.yaml` | Feature names consumed by each model |
| `docs/SECTOR_ROTATION_SPEC.md` | Sector rank → positional sector points |
| `docs/RECOMMENDATION_ENGINE_SPEC.md` | Not present — rules derived from `SCORING_ENGINE_SPEC.md` |

**Global rules**

- Final score = sum of component points (0–100 per model).
- NULL feature → that signal scores **0** (not an error).
- Ineligible stocks (`is_eligible = FALSE`) receive **NULL** score and are excluded from rankings.
- `rs_rank_pct` and sector ranks are cross-sectional — computed after all NSE500 features exist for the date.
- Positional sector points use `sector_3m_rank` (= `rank_3m` in `sector_daily`), per `FEATURE_REGISTRY.yaml` and `SECTOR_ROTATION_SPEC.md`.

**Score bands (interpretation only)**

| Score | Band |
|-------|------|
| 90–100 | Exceptional Opportunity |
| 80–89 | Strong Opportunity |
| 70–79 | Worth Watching |
| 60–69 | Weak Signal |
| < 60 | Not Eligible for Top-20 outputs |

---

## 1. Swing Scoring Model

**Horizon:** 5–30 days  
**Composition:** 100% technical  
**Output column:** `swing_score`

### Component weights

| Component | Max pts | Sub-signals |
|-----------|---------|-------------|
| Trend | 30 | ADX strength (20) + EMA alignment (10) |
| Momentum | 30 | RSI (15) + MACD histogram (10) + Stochastic (5) |
| Volume | 20 | Volume ratio (20) |
| Breakout | 10 | 52-week high proximity (6) + Bollinger squeeze (4) |
| Relative Strength | 10 | RS rank percentile (10) |
| **Total** | **100** | |

### Scoring rules

#### Trend (30)

**ADX strength + direction (20 pts)**

| Condition | Pts |
|-----------|-----|
| `adx_14 >= 35` AND `adx_14 > adx_prev` | 20 |
| `adx_14 >= 25` AND `adx_14 > adx_prev` | 14 |
| `adx_14 >= 25` AND `adx_14 <= adx_prev` | 8 |
| `adx_14 >= 20` | 4 |
| `adx_14 < 20` | 0 |

**EMA short-term alignment (10 pts)**

| Condition | Pts |
|-----------|-----|
| `close > ema_5` AND `ema_5 > ema_13` | 10 |
| `close > ema_13` | 6 |
| `close > ema_20` | 3 |
| `close <= ema_20` | 0 |

#### Momentum (30)

**RSI (15 pts)**

| Condition | Pts |
|-----------|-----|
| `55 <= rsi_14 <= 68` | 15 |
| `50 <= rsi_14 < 55` | 9 |
| `68 < rsi_14 <= 75` | 7 |
| `45 <= rsi_14 < 50` | 4 |
| `rsi_14 > 75` | 2 |
| `rsi_14 < 45` | 0 |

**MACD histogram (10 pts)**

| Condition | Pts |
|-----------|-----|
| `macd_hist > 0` AND `macd_hist > macd_hist_prev` | 10 |
| `macd_hist > 0` AND `macd_hist <= macd_hist_prev` | 5 |
| `macd_hist < 0` AND `macd_hist > macd_hist_prev` | 3 |
| `macd_hist < 0` AND `macd_hist <= macd_hist_prev` | 0 |

**Stochastic (5 pts)**

| Condition | Pts |
|-----------|-----|
| `stoch_k > stoch_d` AND `50 <= stoch_k <= 80` | 5 |
| `stoch_k > stoch_d` AND `stoch_k < 50` | 3 |
| `stoch_k > stoch_d` AND `stoch_k > 80` | 1 |
| `stoch_k <= stoch_d` | 0 |

#### Volume (20)

| `volume_ratio` | Pts |
|----------------|-----|
| `>= 3.0` | 20 |
| `>= 2.0` | 15 |
| `>= 1.5` | 10 |
| `>= 1.2` | 5 |
| `< 1.2` | 0 |

#### Breakout (10)

**52-week high proximity (6 pts)** — `pct_from_52w_high` in percent

| Condition | Pts |
|-----------|-----|
| `>= -2` | 6 |
| `>= -5` | 4 |
| `>= -10` | 2 |
| `< -10` | 0 |

**Bollinger squeeze (4 pts)**

| Condition | Pts |
|-----------|-----|
| `bb_width < bb_width_20avg * 0.70` | 4 |
| `bb_width < bb_width_20avg * 0.85` | 2 |
| `bb_width >= bb_width_20avg` | 0 |

#### Relative Strength (10)

| `rs_rank_pct` | Pts |
|---------------|-----|
| `>= 90` | 10 |
| `>= 75` | 7 |
| `>= 60` | 4 |
| `>= 50` | 2 |
| `< 50` | 0 |

### Swing worked examples

| # | Key inputs | Component breakdown | **Final** |
|---|------------|---------------------|-----------|
| 1 | ADX 36↑, EMA stack, RSI 60, MACD rising+, Stoch 65>k, vol 3.2×, 52w −1%, BB squeeze 0.65×, RS 92 | 20+10+15+10+5+20+6+4+10 | **100** |
| 2 | ADX 28↑, close>ema_13, RSI 52, MACD flat+, Stoch 45>k, vol 2.1×, 52w −4%, BB 0.80×, RS 78 | 14+6+9+5+3+15+4+2+7 | **65** |
| 3 | All signals below minimum thresholds | 0+0+0+0+0+0+0+0+0 | **0** |
| 4 | ADX 38↑, EMA stack; RSI 40, MACD falling−, no vol/breakout/RS | 20+10+0+0+0+0+0+0+0 | **30** |
| 5 | ADX 22, close>ema_20, RSI 62, MACD rising+, Stoch 70, vol 1.6×, 52w −8%, RS 63 | 4+3+15+10+5+10+2+0+4 | **53** |
| 6 | ADX 26 flat, close>ema_13, RSI 78, MACD slowing+, Stoch 85>k, vol 1.3×, 52w −4%, BB 0.82×, RS 51 | 8+6+2+5+1+5+4+2+2 | **35** |
| 7 | ADX 27↑, EMA stack, RSI 72, MACD improving−, vol 3.5×, 52w −1.5%, BB squeeze, RS 91 | 14+10+7+3+0+20+6+4+10 | **74** |
| 8 | ADX 26 flat, close>ema_20, RSI 47, MACD improving−, Stoch 40>k, vol 1.5×, 52w −9%, RS 76 | 8+3+4+3+3+10+2+0+7 | **40** |
| 9 | ADX 37↑, EMA stack, RSI 61, MACD rising+, Stoch 72, vol 2.0×, 52w −4%, BB 0.82×, RS 77 | 20+10+15+10+5+15+4+2+7 | **88** |
| 10 | ADX 40↑, EMA stack, RSI 58, MACD rising+, Stoch 60, vol 3.0×, 52w −1%, no squeeze, RS 95 | 20+10+15+10+5+20+6+0+10 | **96** |

**Example 1 detail (score = 100)**

```
Trend:      ADX 20 + EMA 10           = 30
Momentum:   RSI 15 + MACD 10 + Stoch 5 = 30
Volume:     20
Breakout:   52w 6 + BB 4              = 10
RS:         10
                              Total = 100
```

---

## 2. Positional Scoring Model

**Horizon:** 1–6 months  
**Composition:** 40% trend + 30% relative strength + 20% sector + 10% volume  
**Output column:** `position_score`

### Component weights

| Component | Max pts | Sub-signals |
|-----------|---------|-------------|
| Trend | 40 | EMA Stage 2 alignment (25) + ADX medium-term (15) |
| Relative Strength | 30 | RS rank 20-day (18) + RS vs Nifty 60-day (12) |
| Sector Strength | 20 | Sector 3-month rank (20) |
| Volume | 10 | Volume ratio (10) |
| **Total** | **100** | |

### Scoring rules

#### Trend (40)

**EMA Stage 2 alignment (25 pts)**

| Condition | Pts |
|-----------|-----|
| `close > ema_50` AND `ema_50 > ema_150` AND `ema_150 > ema_200` | 25 |
| `close > ema_50` AND `close > ema_200` | 16 |
| `close > ema_200` only | 8 |
| `close < ema_200` | 0 |

**ADX medium-term (15 pts)**

| Condition | Pts |
|-----------|-----|
| `adx_14 >= 30` AND `adx_14 > adx_prev` | 15 |
| `adx_14 >= 25` | 9 |
| `adx_14 >= 20` | 4 |
| `adx_14 < 20` | 0 |

#### Relative Strength (30)

**RS rank percentile — 20-day (18 pts)**

| `rs_rank_pct` | Pts |
|---------------|-----|
| `>= 85` | 18 |
| `>= 70` | 12 |
| `>= 55` | 6 |
| `< 55` | 0 |

**RS vs Nifty — 60-day (12 pts)**

| `rs_vs_nifty_60d` | Pts |
|-------------------|-----|
| `>= 1.20` | 12 |
| `>= 1.10` | 8 |
| `>= 1.00` | 4 |
| `< 1.00` | 0 |

#### Sector Strength (20)

Uses `sector_3m_rank` from `sector_daily.rank_3m` (`SECTOR_ROTATION_SPEC.md`).

| `sector_3m_rank` | Pts |
|------------------|-----|
| 1 | 20 |
| 2 | 17 |
| 3 | 14 |
| 4–5 | 10 |
| 6–8 | 5 |
| `>= 9` | 0 |

#### Volume (10)

| `volume_ratio` | Pts |
|----------------|-----|
| `>= 2.0` | 10 |
| `>= 1.5` | 7 |
| `>= 1.2` | 4 |
| `< 1.2` | 0 |

### Positional worked examples

| # | Key inputs | Component breakdown | **Final** |
|---|------------|---------------------|-----------|
| 1 | Stage 2 EMA, ADX 32↑, RS rank 88, RS Nifty 1.25, sector rank 1, vol 2.5× | 25+15+18+12+20+10 | **100** |
| 2 | close>ema_50 & ema_200, ADX 26, RS rank 72, RS Nifty 1.12, sector rank 3, vol 1.6× | 16+9+12+8+14+7 | **66** |
| 3 | Below ema_200, ADX 15, RS rank 40, RS Nifty 0.90, sector rank 15, vol 1.0× | 0+0+0+0+0+0 | **0** |
| 4 | Stage 2, ADX 31↑, RS rank 90, RS Nifty 1.22, sector rank 11, vol 1.3× | 25+15+18+12+0+4 | **74** |
| 5 | close>ema_200, ADX 18, RS rank 58, RS Nifty 1.02, sector rank 1, vol 1.0× | 8+0+6+4+20+0 | **38** |
| 6 | close>ema_50 & ema_200, ADX 33↑, RS rank 74, RS Nifty 1.05, sector rank 5, vol 2.2× | 16+15+12+4+10+10 | **67** |
| 7 | Stage 2, ADX 27, RS rank 57, RS Nifty 0.95, sector rank 7, vol 1.7× | 25+9+6+0+5+7 | **52** |
| 8 | close>ema_200, ADX 17, RS rank 86, RS Nifty 1.21, sector rank 2, vol 2.1× | 8+0+18+12+17+10 | **65** |
| 9 | Stage 2, ADX 30↑, RS rank 87, RS Nifty 1.15, sector rank 4, vol 1.25× | 25+15+18+8+10+4 | **80** |
| 10 | close>ema_50 & ema_200, ADX 21, RS rank 48, RS Nifty 1.11, sector rank 8, vol 1.55× | 16+4+0+8+5+7 | **40** |

**Example 1 detail (score = 100)**

```
Trend:      EMA Stage 2 25 + ADX 15     = 40
RS:         rank 18 + Nifty 60d 12     = 30
Sector:     rank 1                      = 20
Volume:     10
                              Total = 100
```

---

## 3. Long-Term Scoring Model

**Horizon:** 1–3 years  
**Composition:** 40% growth + 30% quality + 15% valuation + 15% price trend  
**Output column:** `lt_score`

Fundamental inputs require `announced_date <= signal_date − 5 trading days`. If required quarterly data is unavailable, the model returns **NULL** (not zero).

### Component weights

| Component | Max pts | Sub-signals |
|-----------|---------|-------------|
| Growth Quality | 40 | Revenue CAGR 3Y (20) + PAT CAGR 3Y (20) |
| Business Quality | 30 | ROE (12) + ROCE (12) + Debt/Equity (6) |
| Valuation | 15 | PE vs sector median (15) |
| Price Trend | 15 | EMA 200 position (9) + RS vs Nifty 60d (6) |
| **Total** | **100** | |

### Scoring rules

#### Growth Quality (40)

**Revenue CAGR 3-year (20 pts)**

| `revenue_cagr_3y` | Pts |
|-------------------|-----|
| `>= 25%` | 20 |
| `>= 18%` | 14 |
| `>= 12%` | 8 |
| `>= 6%` | 3 |
| `< 6%` | 0 |

**PAT CAGR 3-year (20 pts)**

| `pat_cagr_3y` | Pts |
|---------------|-----|
| `>= 25%` | 20 |
| `>= 18%` | 14 |
| `>= 10%` | 8 |
| `>= 5%` | 3 |
| `< 5%` | 0 |

#### Business Quality (30)

**ROE (12 pts)**

| `roe` | Pts |
|-------|-----|
| `>= 25%` | 12 |
| `>= 18%` | 8 |
| `>= 12%` | 4 |
| `< 12%` | 0 |

**ROCE (12 pts)**

| `roce` | Pts |
|--------|-----|
| `>= 25%` | 12 |
| `>= 18%` | 8 |
| `>= 12%` | 4 |
| `< 12%` | 0 |

**Debt / Equity (6 pts)**

| `debt_equity` | Pts |
|---------------|-----|
| `<= 0.2` | 6 |
| `<= 0.5` | 4 |
| `<= 1.0` | 2 |
| `> 1.0` | 0 |

#### Valuation (15)

`pe_relative = pe_ratio / sector_median_pe`

| `pe_relative` | Pts |
|---------------|-----|
| `<= 0.70` (30% discount) | 15 |
| `<= 0.85` (15% discount) | 11 |
| `<= 1.00` (at par) | 7 |
| `<= 1.20` (20% premium) | 3 |
| `> 1.20` | 0 |

#### Price Trend (15)

**EMA 200 position (9 pts)**

| Condition | Pts |
|-----------|-----|
| `close > ema_200` AND `pct_from_52w_high >= -20%` | 9 |
| `close > ema_200` | 5 |
| `close < ema_200` | 0 |

**RS vs Nifty — 60-day (6 pts)**

| `rs_vs_nifty_60d` | Pts |
|-------------------|-----|
| `>= 1.10` | 6 |
| `>= 1.00` | 3 |
| `< 1.00` | 0 |

### Long-term worked examples

| # | Key inputs | Component breakdown | **Final** |
|---|------------|---------------------|-----------|
| 1 | Rev CAGR 28%, PAT CAGR 30%, ROE 27%, ROCE 26%, D/E 0.15, PE rel 0.65, above EMA200 near high, RS Nifty 1.15 | 20+20+12+12+6+15+9+6 | **100** |
| 2 | Rev 19%, PAT 20%, ROE 19%, ROCE 20%, D/E 0.4, PE rel 0.82, above EMA200, RS Nifty 1.02 | 14+14+8+8+4+11+5+3 | **67** |
| 3 | Rev 4%, PAT 3%, ROE 8%, ROCE 9%, D/E 1.5, PE rel 1.35, below EMA200, RS Nifty 0.88 | 0+0+0+0+0+0+0+0 | **0** |
| 4 | Rev 26%, PAT 27%, ROE 28%, ROCE 30%, D/E 0.1, PE rel 1.40, above EMA200 near high, RS Nifty 1.12 | 20+20+12+12+6+0+9+6 | **85** |
| 5 | Rev 13%, PAT 11%, ROE 13%, ROCE 14%, D/E 0.9, PE rel 0.68, above EMA200 only, RS Nifty 0.95 | 8+8+4+4+2+15+5+0 | **46** |
| 6 | Rev 7%, PAT 6%, ROE 20%, ROCE 19%, D/E 0.45, PE rel 0.95, above EMA200 near high, RS Nifty 1.14 | 3+3+8+8+4+7+9+6 | **48** |
| 7 | Rev 20%, PAT 12%, ROE 26%, ROCE 13%, D/E 0.18, PE rel 0.80, above EMA200 only, RS Nifty 1.01 | 14+8+12+4+6+11+5+3 | **63** |
| 8 | Rev 30%, PAT 19%, ROE 19%, ROCE 27%, D/E 0.15, PE rel 1.18, below EMA200, RS Nifty 1.11 | 20+14+8+12+6+3+0+6 | **69** |
| 9 | Rev 14%, PAT 5%, ROE 12%, ROCE 20%, D/E 0.18, PE rel 0.65, above EMA200 near high, RS Nifty 1.13 | 8+3+4+8+6+15+9+6 | **59** |
| 10 | Rev 22%, PAT 22%, ROE 30%, ROCE 28%, D/E 0.12, PE rel 0.98, above EMA200 only, RS Nifty 1.03 | 14+14+12+12+6+7+5+3 | **73** |

**Example 1 detail (score = 100)**

```
Growth:     Revenue 20 + PAT 20         = 40
Quality:    ROE 12 + ROCE 12 + D/E 6   = 30
Valuation:  PE relative 15              = 15
Price:      EMA 9 + RS Nifty 6         = 15
                              Total = 100
```

**Example 9 detail (score = 59 — below eligibility threshold)**

```
Growth:     8 + 3  = 11
Quality:    4 + 8 + 6 = 18
Valuation:  15
Price:      9 + 6 = 15
                              Total = 59  → Not Eligible (< 60)
```

---

## Validation checklist

Use this when implementing or regression-testing the scoring engine:

- [ ] Swing: nine sub-signals sum to `swing_score` (max 100)
- [ ] Positional: four components sum to `position_score` (max 100)
- [ ] Long-term: eight sub-signals sum to `lt_score` (max 100)
- [ ] Sector points match `sector_3m_rank` lookup table exactly
- [ ] All 30 worked examples above produce the documented final scores
- [ ] NULL features score 0; ineligible stocks score NULL
- [ ] LT model returns NULL when required fundamentals are missing

---

## Document history

| Date | Change |
|------|--------|
| 2026-06-10 | Initial validation reference derived from `SCORING_ENGINE_SPEC.md`, `FEATURE_REGISTRY.yaml`, `SECTOR_ROTATION_SPEC.md` |
