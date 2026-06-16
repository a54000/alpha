# Universe Sensitivity Research

Date: 2026-06-11

## Objective

Determine how Swing model performance changes as the tradable universe is restricted.

Model under test:

**Sector Rank + ADX**

Entry filters:

- EMA200 extension <= 25%
- Prior 20d return <= 15%

This is research only. No production scoring, recommendation logic, or V2.1 implementation was modified.

## Artifacts

- Results JSON: `reports/universe_sensitivity_results.json`

## Important Data Limitation

The implemented database does not contain a market-cap field.

The requested Top300, Top200, and Top100 market-cap universes were therefore approximated using:

**Average traded value over the research period**

This is a liquidity/size proxy, not true market capitalization. The universe filter was also restricted to stock rows only:

- `symbol_master.nse500 = true`
- Excludes `INDEX` sector

Because true market cap is unavailable, this research should be interpreted as **universe quality / liquidity sensitivity**, not a final market-cap universe decision.

## Method

The research simulation reconstructed the Sector Rank + ADX model directly from:

- `features_daily`
- `sector_daily`
- `prices_daily`
- `index_prices_daily`

Score formula:

`(score_swing_v2_adx + score_swing_v2_sector) / 35 * 100`

Recommendation methodology:

- Daily candidate ranking
- Minimum score: 70
- Top 20 recommendations per signal date
- Entry filters applied before ranking
- Entry: next-trading-day open
- Exit: close after 20 trading days from entry
- Benchmark: `index_prices_daily.NIFTY500` using the same entry and exit dates

## Universe Comparison

| Universe | Universe Size | Trade Count | Avg Return | Win Rate | Profit Factor | Alpha | Unique Symbols |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Current NSE500 tradable proxy universe | 433 | 6,868 | 0.29% | 50.09% | 1.087 | 0.36% | 372 |
| Top300 by avg traded value proxy | 300 | 6,384 | 0.52% | 51.47% | 1.164 | 0.53% | 289 |
| Top200 by avg traded value proxy | 200 | 5,275 | 0.63% | 52.75% | 1.204 | 0.34% | 196 |
| Top100 by avg traded value proxy | 100 | 3,594 | 1.33% | 55.52% | 1.500 | 0.53% | 100 |

## Change Versus NSE500

| Universe | Avg Return Change | Profit Factor Change | Alpha Change |
| --- | ---: | ---: | ---: |
| Current NSE500 tradable proxy universe | 0.00 pp | 0.000 | 0.00 pp |
| Top300 by avg traded value proxy | +0.23 pp | +0.076 | +0.17 pp |
| Top200 by avg traded value proxy | +0.33 pp | +0.117 | -0.01 pp |
| Top100 by avg traded value proxy | +1.03 pp | +0.413 | +0.17 pp |

## Sector Concentration

| Universe | Top Sector | Top Sector Share | Top 5 Sector Share |
| --- | --- | ---: | ---: |
| Current NSE500 tradable proxy universe | Financial Services | 23.66% | 62.39% |
| Top300 by avg traded value proxy | Financial Services | 25.55% | 62.30% |
| Top200 by avg traded value proxy | Financial Services | 26.88% | 65.23% |
| Top100 by avg traded value proxy | Financial Services | 28.35% | 70.76% |

### Top Sectors By Universe

| Universe | Top Sectors |
| --- | --- |
| Current NSE500 | Financial Services 23.66%, Consumer Goods 15.83%, Industrial Manufacturing 8.23%, Pharma 8.07%, IT 6.61% |
| Top300 | Financial Services 25.55%, Consumer Goods 13.27%, Pharma 8.05%, Industrial Manufacturing 8.04%, IT 7.39% |
| Top200 | Financial Services 26.88%, Consumer Goods 12.53%, Industrial Manufacturing 9.82%, IT 8.53%, Energy 7.47% |
| Top100 | Financial Services 28.35%, Consumer Goods 12.66%, IT 10.41%, Industrial Manufacturing 10.38%, Metals 8.96% |

## Findings

### 1. Does Performance Improve As Universe Quality Increases?

Yes, mostly.

As the universe is restricted toward larger/more liquid stocks, the model improves on:

- Avg Return
- Win Rate
- Profit Factor

The improvement is strongest in the Top100 universe.

| Universe | Avg Return | Profit Factor |
| --- | ---: | ---: |
| NSE500 proxy | 0.29% | 1.087 |
| Top300 | 0.52% | 1.164 |
| Top200 | 0.63% | 1.204 |
| Top100 | 1.33% | 1.500 |

The pattern suggests the model performs better when weaker/liquidity-constrained names are removed.

### 2. Is There An Optimal Universe Size?

Based on this test, **Top100 is the best-performing universe**.

Top100 leads on:

- Avg Return
- Win Rate
- Profit Factor
- Alpha, tied closely with Top300

However, Top100 also has the highest concentration risk.

Top300 is the more balanced alternative:

- Better than NSE500 on all major metrics
- Less concentrated than Top100
- Much higher trade count than Top100

### 3. Does Restricting The Universe Reduce Diversification?

Yes.

Unique symbols traded decline from 372 in the NSE500 proxy universe to 100 in Top100.

Top 5 sector concentration rises:

- NSE500 proxy: 62.39%
- Top300: 62.30%
- Top200: 65.23%
- Top100: 70.76%

This means the Top100 result is stronger, but more dependent on fewer symbols and fewer sectors.

### 4. Does Alpha Survive In Top100 And Top200?

Yes, alpha remains positive in both Top100 and Top200.

| Universe | Alpha |
| --- | ---: |
| Top200 | 0.34% |
| Top100 | 0.53% |

But Top200 alpha is slightly below the NSE500 proxy universe:

- NSE500 proxy alpha: 0.36%
- Top200 alpha: 0.34%

Top100 has materially better raw return and profit factor, while alpha improves versus NSE500.

### 5. Does The Model Rely On Smaller-Cap Stocks For Performance?

No evidence of reliance on smaller-cap or less-liquid stocks.

Performance improves when the universe is restricted:

- Avg return rises from 0.29% to 1.33%.
- Profit factor rises from 1.087 to 1.500.
- Win rate rises from 50.09% to 55.52%.

This suggests the model's edge is not primarily coming from smaller, less-liquid names. It appears stronger in the larger/more liquid subset.

## Risk Assessment

### Top100 Strengths

- Best average return
- Best win rate
- Best profit factor
- Positive alpha
- Strong evidence that entry-filtered Sector Rank + ADX works in liquid names

### Top100 Risks

- Lowest trade count
- Highest sector concentration
- Uses all 100 available names at least once, so universe breadth is fully consumed
- More vulnerable to sector crowding, especially Financial Services
- Result is based on traded-value proxy, not actual market cap

### Top300 Strengths

- Positive improvement across return, profit factor, and alpha
- Retains much more diversification than Top100
- Trade count remains close to NSE500 proxy
- Top 5 sector share is nearly unchanged versus NSE500 proxy

### Top200 Mixed Evidence

Top200 improves raw return, win rate, and profit factor, but alpha is slightly below the NSE500 proxy universe. It is not clearly superior to Top300 or Top100.

## Final Recommendation

**Move to Top100 for the next research candidate, but do not productionize without concentration controls.**

Reason:

- Top100 has the strongest risk-adjusted evidence in this test.
- Profit factor improves from 1.087 to 1.500.
- Avg return improves from 0.29% to 1.33%.
- Win rate improves from 50.09% to 55.52%.
- Alpha remains positive and improves versus the NSE500 proxy universe.

However, because Top100 has materially higher sector concentration, the next validation should test:

1. Top100 with max sector exposure caps.
2. Top100 versus Top300 across time splits.
3. True market-cap ranking if market-cap data is added.
4. Point-in-time universe correction before any production decision.

## Decision

| Option | Decision |
| --- | --- |
| Stay at NSE500 | No |
| Move to Top300 | Acceptable conservative fallback |
| Move to Top200 | No clear advantage |
| Move to Top100 | Recommended research direction |

The best evidence currently supports:

**Sector Rank + ADX + entry filters on a Top100 liquid/large universe**

This should be treated as a research candidate only, not V2.1 production logic.
