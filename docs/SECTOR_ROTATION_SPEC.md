# Sector Rotation Specification

## Purpose

Compute daily sector performance rankings used by the Positional
and Long-Term scoring models. The positional model allocates 20 points
to sector strength. This document defines exactly how that ranking
is derived.

---

## Sector Universe

19 canonical sectors defined in `sector_master` table. Every NSE500
stock belongs to exactly one sector.

```
1.  Defence
2.  Railways & Infra
3.  Capital Goods
4.  PSU Banks
5.  Private Banks
6.  NBFCs
7.  IT — Large Cap
8.  IT — Midcap
9.  Pharma
10. Auto — OEM
11. Auto Ancillary
12. FMCG
13. Retail & Consumer
14. Chemicals
15. Metals & Mining
16. Power & Energy
17. Real Estate
18. EMS / Electronics
19. Telecom & Hospitality
```

---

## Sector Return Calculation

```python
def compute_sector_return(sector_name, period_days, date):
    """
    Equal-weighted average return of all NSE500 stocks
    in the sector over the last N trading days.
    """
    stocks = get_sector_stocks(sector_name)   # from sector_master

    returns = []
    for symbol in stocks:
        price_today = get_close(symbol, date)
        price_then  = get_close(symbol, date - period_days)
        if price_today and price_then:
            returns.append((price_today - price_then) / price_then)

    return mean(returns) if returns else None
```

**Periods computed daily:**

| Column | Period | Use |
|--------|--------|-----|
| `sector_return_1m` | 21 trading days | Short-term momentum check |
| `sector_return_3m` | 63 trading days | Primary ranking signal |
| `sector_return_6m` | 126 trading days | Trend persistence check |

---

## Composite Sector Score

A weighted composite score drives the final rank.

```python
sector_composite = (
    sector_return_1m * 0.20 +
    sector_return_3m * 0.50 +   # primary signal
    sector_return_6m * 0.30
)
```

Rationale for 3M dominance: long enough to reflect genuine rotation,
short enough to respond to changing leadership within 1–2 quarters.

---

## Sector Rank Table

Stored daily in `sector_daily_ranks`:

```sql
CREATE TABLE sector_daily_ranks (
    date                DATE        NOT NULL,
    sector              VARCHAR(50) NOT NULL,
    sector_return_1m    NUMERIC(8,4),
    sector_return_3m    NUMERIC(8,4),
    sector_return_6m    NUMERIC(8,4),
    composite_score     NUMERIC(8,4),
    rank_3m             INTEGER,        -- rank by 3M return alone
    rank_composite      INTEGER,        -- rank by composite score (used in models)
    stock_count         INTEGER,        -- number of NSE500 stocks in sector
    PRIMARY KEY (date, sector)
);
```

**`rank_composite` is what the scoring engine reads.**
Rank 1 = strongest sector. Rank 19 = weakest.

---

## How Positional Model Consumes This

```python
# In positional_model.py
sector = get_stock_sector(symbol)           # from sector_master
rank   = get_sector_rank(sector, date)      # from sector_daily_ranks

# Scoring table (20 pts):
if   rank == 1:          sector_score = 20
elif rank == 2:          sector_score = 17
elif rank == 3:          sector_score = 14
elif rank in [4, 5]:     sector_score = 10
elif rank in [6, 7, 8]:  sector_score = 5
else:                    sector_score = 0
```

---

## Rotation Signal for Dashboard

Beyond scoring, sector rotation data drives the dashboard sidebar
and the morning email digest.

```
📊 SECTOR ROTATION — 3M PERFORMANCE

  1. Defence            +18.4%  ↑↑
  2. PSU Banks          +12.1%  ↑
  3. Capital Goods       +9.8%  ↑
  4. Auto                +4.3%  →
  ──────────────────────────────
  16. FMCG               +1.1%  →
  17. Pharma             -2.4%  ↓
  18. IT Large Cap       -5.1%  ↓
  19. Metals & Mining    -8.2%  ↓↓
```

Direction indicator rules:
```
↑↑  composite_score > +10%
↑   composite_score > +3%
→   composite_score between -3% and +3%
↓   composite_score < -3%
↓↓  composite_score < -10%
```

---

## Computation Order in Daily Pipeline

```
Step 1: prices updated for all NSE500 stocks
Step 2: compute sector_return_1m/3m/6m for all 19 sectors
Step 3: compute composite_score and rank_composite
Step 4: write to sector_daily_ranks
Step 5: features_daily computation begins
        (sector rank available to join at scoring time)
```

Sector rotation must complete **before** features_daily scoring runs.

---

## Market Regime Signal (V1.1 Placeholder)

Not required for V1 but reserved for V1.1.

```yaml
market_regime:
  source: Nifty 500 index prices
  signal:
    bull:     nifty500 > ema_200 AND breadth > 60%
    sideways: nifty500 near ema_200 OR breadth 40-60%
    bear:     nifty500 < ema_200 AND breadth < 40%

  use_in_v1.1:
    - Reduce positional score weights in bear regime
    - Increase cash allocation recommendation
    - Flag all swing signals with regime context
```

Store daily in `market_regime_daily` table (schema TBD in V1.1).
