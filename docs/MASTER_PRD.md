# NSE Research Platform — Master PRD

## Goal

Build a personal stock research platform for NSE500 stocks.

The system does **NOT** predict stock prices.

The system ranks stocks daily for:

1. Swing Trading (5–30 days)
2. Positional Trading (1–6 months)
3. Long-Term Investing (1–3 years)

---

## Success Metrics

| Metric | Target |
|--------|--------|
| Daily ranking generated | Before 8AM IST |
| Universe | NSE500 |
| Backtesting | Full historical simulation |
| Scoring | 0–100 per model |
| Explanations | AI-generated, signal-grounded |

### Swing Model Targets
| Metric | Target |
|--------|--------|
| Win Rate | >55% |
| Avg Reward/Risk | >2 |
| Max Drawdown | <15% |
| Annual Return | >20% |

### Long-Term Model Targets
| Metric | Target |
|--------|--------|
| CAGR | Nifty + 5% |
| Max Drawdown | Lower than Nifty |

---

## Architecture

```
Data Layer        → Prices, Fundamentals, News, Filings
Feature Layer     → Technical Indicators, Fundamental Ratios
Scoring Layer     → Model A (Swing), Model B (Positional), Model C (LT)
Intelligence Layer → Event Engine, Sector Rotation, Institutional Tracker
Research Layer    → LLM Explanations, Signal Memory (Vector DB)
Output Layer      → Dashboard, Daily Digest, Alerts
```

---

## Three Models

### Model A — Swing (5–30 days)
- Weight: 100% technical
- Key signals: RSI, ADX, MACD, Volume Spike, 52W High Proximity, BB Squeeze
- Output: Swing Score 0–100

### Model B — Positional (1–6 months)
- Weight: 50% technical + 30% fundamental + 20% news
- Key signals: Earnings acceleration, sector rotation, institutional buying, price trend
- Output: Position Score 0–100

### Model C — Long-Term (1–3 years)
- Weight: 70% fundamental + 20% events + 10% technical
- Key signals: Revenue CAGR, PAT CAGR, ROCE, Cash Flow, Sector Tailwinds, Valuation
- Output: LT Score 0–100

---

## Data Sources

| Data Type | Source | Frequency |
|-----------|--------|-----------|
| OHLCV Prices | yfinance / KiteConnect | Daily |
| Fundamentals | Screener.in / Tickertape | Quarterly |
| News | ET, Moneycontrol, Mint RSS | Daily |
| NSE Filings | NSE Announcements | Real-time |
| Institutional | NSE Bulk Deals, BSE FII data | Daily |

---

## Database Schema

### Tables
- `prices` — Daily OHLCV for NSE500
- `fundamentals` — Quarterly financial data
- `news` — Headlines with LLM-enriched sentiment
- `daily_scores` — Output scores from all three models
- `signal_explanations` — LLM-generated narratives

---

## Scoring Output Format

```json
{
  "symbol": "BEL",
  "date": "2026-06-10",
  "swing_score": 91,
  "position_score": 78,
  "lt_score": 65,
  "signals_fired": [
    "Volume 4.2x average",
    "ADX 36 — strong trend",
    "Near 52-week high"
  ],
  "explanation": "WHY THIS RANKS HIGH:\n• ...\nRISKS:\n• ...\nCONFIDENCE: 84%",
  "stop_loss": 514.78,
  "target_1": 686.90,
  "target_2": 1332.42,
  "rr_ratio": 2.1
}
```

---

## Event Intelligence Output Format

```json
{
  "stock": "BEL",
  "impact": "positive",
  "theme": "defence",
  "horizon": "2 years",
  "confidence": 91
}
```

---

## Daily Digest Format

```
🔔 DAILY MARKET INTELLIGENCE — [DATE]

📈 TOP SWING OPPORTUNITIES
1. BEL     (91) — Volume 4.2x, near 52W high, ADX 36
2. POLYCAB (88) — BB squeeze breaking out, RSI 64

📊 TOP LONG-TERM
1. DIXON   (93) — Rev CAGR 28%, ROCE 24%, MF buying
2. HAL     (90) — Defence tailwind, strong order book

🗞️ SECTOR SIGNALS
• Defence ↑↑  (+18% 3M)
• Railways ↑  (+12% 3M)
• IT ↓        (-5% 3M)
```

---

## 30-Day Build Plan

### Week 1 — Foundation
- PostgreSQL + TimescaleDB setup
- NSE500 symbol list
- Historical price fetch (2 years)
- 20 technical indicators

### Week 2 — Swing Engine
- Swing scoring model (Model A)
- Relative strength vs Nifty + sector
- Breakout detection
- Top 10 visible in dashboard

### Week 3 — Fundamentals + Sector
- Screener.in scraper
- Sector rotation engine
- Positional + LT scoring models

### Week 4 — Intelligence + Output
- RSS news pipeline
- Claude API event analysis
- LLM explanation generator
- Daily WhatsApp/email digest

---

## Design System

See: `/docs/DESIGN_SYSTEM.md`

## File Structure

See: `/docs/FILE_STRUCTURE.md`
