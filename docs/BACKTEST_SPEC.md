# Backtest Specification

## Purpose

Define the exact rules used to simulate historical performance of all three
ranking models. Every performance number produced by this platform must be
reproducible using only these rules. No exceptions.

---

## Capital & Portfolio Parameters

```yaml
capital: 1_000_000        # INR 10 lakhs starting capital
portfolio_size: 10        # max concurrent positions per model
position_sizing: equal    # each position = capital / portfolio_size
                          # = INR 1 lakh per position
```

---

## Entry Rules

```yaml
entry:
  trigger: top_N_ranked       # enter top 10 ranked stocks on rebalance day
  condition:
    - volume_ratio >= 1.0     # minimum volume confirmation
  execution: next_day_open    # signal fires EOD, entry at next morning open
  max_positions: 10

  note: >
    Score threshold (>= 60) is NOT used as a hard entry filter in V1.
    Rankings are purely ordinal — top 10 stocks enter regardless of
    absolute score. Score bands are for interpretation only, not gates.
    Rankings are purely ordinal. The top 10 stocks always enter on
    rebalance day regardless of absolute score value.
    Score bands (< 60 warning etc.) are display-only and never affect
    entry decisions. Threshold research is deferred to M2.
```

**Rationale:** Using next-day open avoids look-ahead bias. You will never
actually buy at the close price where the signal fired.

---

## Exit Rules

```yaml
exit:
  rules:
    - type: stop_loss
      trigger: price <= stop_loss_price
      execution: next_day_open   # on gap-down, use open not SL price

    - type: rank_decay
      trigger: stock_rank > 20    # no longer in top 20 on rebalance day
      execution: next_rebalance_open  # not immediate — checked on rebalance schedule

    - type: max_holding
      swing:      20             # trading days (~1 month)
      positional: 90             # trading days (~4.5 months)
      lt:         252            # trading days (~1 year)
      execution: next_day_open

    - type: target_hit
      t1_action: hold            # don't exit at T1, trail stop loss
      t2_action: exit_half       # exit 50% at T2
      t3_action: exit_remaining

exit_strategies_to_compare:
  strategy_a:
    name: "Target-Based Exit"
    description: >
      Exit at T1 (2R), T2 (3.5R), T3 (5R) as defined above.
    use_case: Works well in mean-reverting or range-bound markets.

  strategy_b:
    name: "Score-Decay Exit"
    description: >
      No profit targets. Exit only when:
        (a) stop loss is hit, OR
        (b) score drops below rank cutoff (no longer in top 10), OR
        (c) max holding period reached.
    use_case: Works better in strong trending markets. Lets winners run.

  backtest_both: true
  report_metric: "Profit Factor and CAGR over 2-year period"
  note: >
    Many momentum systems outperform with Strategy B. Do not assume
    targets improve performance — backtest evidence decides.
```

---

## Stop Loss Calculation

```python
# ATR-based stop loss (preferred — adapts to volatility)
atr_14 = ATR(high, low, close, period=14)
stop_loss = entry_price - (1.5 * atr_14)

# Minimum floor: never more than 8% below entry
floor_sl = entry_price * 0.92
stop_loss = max(stop_loss, floor_sl)
```

---

## Target Calculation

```python
risk = entry_price - stop_loss

target_1 = entry_price + (2.0 * risk)   # R:R 1:2
target_2 = entry_price + (3.5 * risk)   # R:R 1:3.5
target_3 = entry_price + (5.0 * risk)   # R:R 1:5
```

---

## Rebalance Frequency

```yaml
rebalance:
  swing:      weekly          # every Monday open
  positional: bi_weekly       # every other Monday open
  lt:         monthly         # first trading day of month

  rules:
    - exit positions that no longer rank in top 20 (checked on rebalance schedule)
    - replace with next highest ranked eligible stocks
    - never rebalance mid-week unless stop loss triggered
```

---

## Transaction Costs

```yaml
slippage:   0.20%    # per side (buy + sell = 0.40% round trip)
brokerage:  20       # INR per order (flat, Zerodha-style)
stt:        0.10%    # Securities Transaction Tax (sell side only)
stamp_duty: 0.015%   # buy side only
total_cost_approx: 0.50%  # conservative round-trip assumption
```

---

## Benchmark

```yaml
benchmark: NIFTY_500     # compare against the universe we rank
secondary: NIFTY_50      # commonly quoted reference
```

---

## Performance Metrics to Report

```yaml
returns:
  - total_return_pct
  - cagr_pct
  - benchmark_alpha_pct

risk:
  - max_drawdown_pct
  - max_drawdown_duration_days
  - volatility_annualised

trade_statistics:
  - total_trades
  - win_rate_pct
  - avg_win_pct
  - avg_loss_pct
  - reward_risk_ratio
  - avg_holding_days
  - profit_factor          # gross_profit / gross_loss

risk_adjusted:
  - sharpe_ratio           # risk_free_rate: 6.5% (India 10Y)
  - sortino_ratio
  - calmar_ratio           # cagr / max_drawdown
```

---

## Backtest Period

```yaml
full_history:   2022-01-01 to present   # ~3 years
walk_forward:
  train:  18 months
  test:   6 months
  step:   3 months
  # Prevents overfitting model weights to a single period
```

---

## Feature Registry & Recommendation History

### Recommendation History Table

Every ranking run must persist the following to `recommendation_history`:

| Column | Description |
|--------|-------------|
| date | Signal date |
| symbol | NSE symbol |
| swing_score | Score from Model A |
| position_score | Score from Model B |
| lt_score | Score from Model C |
| rank | Rank within that model on that date |
| rsi | RSI value at signal time |
| adx | ADX value at signal time |
| volume_ratio | Volume / 20-day average |
| sector_strength | Sector rotation score |
| reason_codes | Pipe-delimited list of signals that fired |

**Purpose:**
- Track score evolution over time
- Analyze signal persistence
- Study rank improvements and deterioration
- Support future model research

Example query this enables:
```sql
-- Stocks that improved in rank for 10+ consecutive days
SELECT symbol, COUNT(*) as streak
FROM recommendation_history
WHERE model = 'swing'
GROUP BY symbol
HAVING COUNT(DISTINCT date) >= 10
ORDER BY streak DESC;
```

### Feature Registry

All computed features must be registered in `/docs/FEATURE_REGISTRY.yaml`
before any model may consume them.

**No model may consume an unregistered feature.**

Example:

```yaml
rsi_14:
  source: prices
  formula: "RSI(close, period=14)"
  refresh: daily

adx_14:
  source: prices
  formula: "ADX(high, low, close, period=14)"
  refresh: daily

volume_ratio:
  source: prices
  formula: "volume / ROLLING_MEAN(volume, 20)"
  refresh: daily

relative_strength:
  source: prices
  formula: "stock_return_20d / nifty500_return_20d"
  refresh: daily

sector_strength:
  source: sector_prices
  formula: "sector_return_3m rank among all sectors"
  refresh: daily

ema_200:
  source: prices
  formula: "EMA(close, period=200)"
  refresh: daily
```

---

## What Backtests Cannot Tell You

1. **Survivorship bias** — NSE500 composition changes. Stocks that went bust
   are no longer in the index. Performance will look better than reality.
   *Mitigation:* maintain a snapshot of NSE500 composition by date.

2. **Impact cost** — A ₹1L position in a small-cap may move the price.
   Slippage of 0.2% may underestimate real friction.

3. **Look-ahead bias** — Quarterly results are published with a delay.
   Never use a result that wasn't publicly available on the signal date.
   *Rule:* use fundamentals data only after a 5-day lag from announcement.

4. **Regime dependence** — A momentum strategy that worked in 2023-2024
   bull market may underperform in sideways or bear markets.
   *Mitigation:* always show performance split by market regime.
