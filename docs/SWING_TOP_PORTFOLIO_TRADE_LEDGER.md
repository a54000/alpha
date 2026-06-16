# Swing Top Portfolio Trade Ledger

**Date:** 2026-06-11

**Objective:** Generate the exact trades that would have been taken by the best-performing Swing research model.

**Model:** Sector Rank + ADX

**Scope:** Research only. Production scoring was not modified.

## Exported Ledgers

- `reports/swing_top10_trade_ledger.csv`
- `reports/swing_top20_trade_ledger.csv`

Each ledger includes:

- Signal Date
- Entry Date
- Exit Date
- Symbol
- Sector
- Model Score
- Sector Rank
- ADX Value
- Entry Price
- Exit Price
- Holding Period Return
- Benchmark Return
- Alpha

## Execution Rules

- Signal is generated after close on signal date.
- Entry is next-trading-day open.
- Exit is close after 20 trading days from entry.
- Benchmark return uses the same entry and exit dates.
- Alpha equals trade return minus benchmark return.


## Top 10 Portfolio Summary

| Metric | Value |
|---|---:|
| Trade count | 4726 |
| Valid trade count | 4516 |
| Alpha-valid trade count | 4406 |
| Average return | 0.21% |
| Win rate | 50.47% |
| Average alpha | 0.29% |

Best month by average return: `2025-03` with 5.83% average return.

Worst month by average return: `2026-02` with -9.66% average return.

### Top 10 Portfolio Top 20 Winners

| Signal Date | Entry Date | Symbol | Sector | Score | Sector Rank | ADX | Return | Benchmark | Alpha |
|---|---|---|---|---:|---:|---:|---:|---:|---:|
| 2024-07-22 | 2024-07-23 | EDELWEISS | FINANCIAL SERVICES | 100.00 | 1 | 53.19 | 64.31% | 1.50% | 62.81% |
| 2026-04-30 | 2026-05-01 | HFCL | TELECOM | 100.00 | 1 | 48.50 | 55.08% | N/A | N/A |
| 2026-05-05 | 2026-05-06 | HFCL | TELECOM | 100.00 | 1 | 55.57 | 54.70% | -2.29% | 57.00% |
| 2024-07-19 | 2024-07-22 | EDELWEISS | FINANCIAL SERVICES | 100.00 | 1 | 52.50 | 53.73% | 2.28% | 51.45% |
| 2026-05-04 | 2026-05-05 | HFCL | TELECOM | 94.29 | 2 | 53.18 | 50.75% | -1.21% | 51.95% |
| 2026-05-01 | 2026-05-04 | HFCL | TELECOM | 100.00 | 1 | 50.72 | 48.98% | -1.52% | 50.50% |
| 2025-12-30 | 2025-12-31 | HINDCOPPER | METALS | 94.29 | 2 | 42.22 | 43.41% | -2.43% | 45.83% |
| 2025-03-17 | 2025-03-18 | KSCL | CONSUMER GOODS | 77.14 | 8 | 36.74 | 38.57% | 7.77% | 30.80% |
| 2024-08-06 | 2024-08-07 | CAPLIPOINT | PHARMA | 100.00 | 1 | 36.17 | 37.19% | 4.34% | 32.85% |
| 2026-05-06 | 2026-05-07 | HFCL | TELECOM | 100.00 | 1 | 57.97 | 36.91% | -3.11% | 40.02% |
| 2025-02-04 | 2025-02-05 | GLAXO | PHARMA | 77.14 | 8 | 48.95 | 36.63% | -6.20% | 42.82% |
| 2025-12-29 | 2025-12-30 | NATIONALUM | METALS | 88.57 | 3 | 43.13 | 36.29% | -2.51% | 38.80% |
| 2025-02-03 | 2025-02-04 | GLAXO | PHARMA | 77.14 | 8 | 48.90 | 35.93% | -6.01% | 41.93% |
| 2025-02-01 | 2025-02-03 | GLAXO | PHARMA | 77.14 | 7 | 48.40 | 35.36% | -7.03% | 42.38% |
| 2025-12-30 | 2025-12-31 | NATIONALUM | METALS | 94.29 | 2 | 44.99 | 34.84% | -2.43% | 37.27% |
| 2025-03-10 | 2025-03-11 | KSCL | CONSUMER GOODS | 77.14 | 7 | 36.77 | 34.76% | 3.13% | 31.62% |
| 2026-03-27 | 2026-03-30 | GUJALKALI | CHEMICALS | 77.14 | 7 | 40.42 | 34.62% | 9.25% | 25.37% |
| 2026-04-06 | 2026-04-07 | GUJALKALI | CHEMICALS | 77.14 | 7 | 41.99 | 34.18% | 9.71% | 24.46% |
| 2025-07-02 | 2025-07-03 | SHARDACROP | FERTILISERS & PESTICIDES | 94.29 | 2 | 45.14 | 34.00% | -2.87% | 36.87% |
| 2025-03-17 | 2025-03-18 | GMDCLTD | METALS | 77.14 | 3 | 32.73 | 33.00% | 7.77% | 25.22% |

### Top 10 Portfolio Top 20 Losers

| Signal Date | Entry Date | Symbol | Sector | Score | Sector Rank | ADX | Return | Benchmark | Alpha |
|---|---|---|---|---:|---:|---:|---:|---:|---:|
| 2025-01-09 | 2025-01-10 | VAKRANGEE | IT | 82.86 | 4 | 36.01 | -49.55% | -1.71% | -47.84% |
| 2025-01-08 | 2025-01-09 | VAKRANGEE | IT | 82.86 | 4 | 35.70 | -47.32% | -2.01% | -45.31% |
| 2025-01-06 | 2025-01-07 | ITI | TELECOM | 94.29 | 2 | 41.42 | -46.59% | -3.93% | -42.66% |
| 2026-02-25 | 2026-02-26 | IDBI | FINANCIAL SERVICES | 77.14 | 3 | 34.62 | -45.86% | -12.51% | -33.36% |
| 2026-02-24 | 2026-02-25 | IDBI | FINANCIAL SERVICES | 82.86 | 2 | 34.50 | -43.85% | -10.13% | -33.72% |
| 2026-02-20 | 2026-02-23 | IDBI | FINANCIAL SERVICES | 82.86 | 2 | 33.61 | -41.09% | -10.33% | -30.76% |
| 2026-02-23 | 2026-02-24 | IDBI | FINANCIAL SERVICES | 82.86 | 2 | 34.26 | -40.73% | -8.28% | -32.45% |
| 2026-02-19 | 2026-02-20 | IDBI | FINANCIAL SERVICES | 77.14 | 3 | 32.96 | -39.56% | -11.13% | -28.43% |
| 2026-02-27 | 2026-03-02 | IDBI | FINANCIAL SERVICES | 88.57 | 3 | 35.64 | -38.23% | -7.13% | -31.10% |
| 2025-01-03 | 2025-01-06 | VAKRANGEE | IT | 88.57 | 3 | 36.03 | -37.41% | N/A | N/A |
| 2025-10-06 | 2025-10-07 | KIOCL | METALS | 88.57 | 3 | 42.63 | -35.50% | 1.39% | -36.88% |
| 2025-01-07 | 2025-01-08 | ITI | TELECOM | 94.29 | 2 | 44.02 | -35.40% | -2.91% | -32.50% |
| 2025-01-08 | 2025-01-09 | ITI | TELECOM | 94.29 | 2 | 44.97 | -33.72% | -2.01% | -31.71% |
| 2025-01-03 | 2025-01-06 | ITI | TELECOM | 94.29 | 2 | 38.89 | -31.70% | N/A | N/A |
| 2025-01-02 | 2025-01-03 | VAKRANGEE | IT | 82.86 | 2 | 34.80 | -31.56% | -5.55% | -26.01% |
| 2025-01-09 | 2025-01-10 | ITI | TELECOM | 88.57 | 3 | 45.14 | -30.37% | -1.71% | -28.66% |
| 2025-02-05 | 2025-02-06 | VAKRANGEE | IT | 77.14 | 7 | 35.02 | -28.87% | -6.48% | -22.39% |
| 2026-02-13 | 2026-02-16 | JKTYRE | AUTOMOBILE | 82.86 | 2 | 30.34 | -28.83% | -6.79% | -22.04% |
| 2026-02-10 | 2026-02-11 | RAIN | CHEMICALS | 77.14 | 6 | 35.80 | -28.50% | -8.02% | -20.48% |
| 2024-09-26 | 2024-09-27 | INTELLECT | IT | 82.86 | 5 | 39.13 | -28.12% | -7.66% | -20.46% |

### Top 10 Portfolio Top Sectors By Contribution

| Sector | Trades | Avg Return | Avg Alpha | Total Alpha |
|---|---:|---:|---:|---:|
| FINANCIAL SERVICES | 1279 | 1.57% | 1.02% | 1269.25% |
| METALS | 354 | 1.68% | 1.78% | 604.52% |
| HEALTHCARE SERVICES | 295 | 1.99% | 1.44% | 419.46% |
| CHEMICALS | 83 | 5.06% | 3.99% | 331.50% |
| AUTOMOBILE | 381 | 0.63% | 0.66% | 246.73% |
| PHARMA | 450 | -0.70% | 0.20% | 88.60% |
| TELECOM | 75 | -0.32% | 0.63% | 45.31% |
| FERTILISERS & PESTICIDES | 180 | -1.18% | 0.14% | 24.57% |
| PAPER | 4 | -7.77% | -5.60% | -22.41% |
| INDUSTRIAL MANUFACTURING | 314 | -0.20% | -0.10% | -30.56% |

### Top 10 Portfolio Bottom Sectors By Contribution

| Sector | Trades | Avg Return | Avg Alpha | Total Alpha |
|---|---:|---:|---:|---:|
| IT | 231 | -4.49% | -2.64% | -578.84% |
| CONSUMER GOODS | 445 | -1.49% | -0.97% | -430.67% |
| TEXTILES | 50 | -8.86% | -4.74% | -232.36% |
| CONSTRUCTION | 88 | -2.87% | -2.04% | -177.68% |
| SERVICES | 36 | -3.24% | -3.39% | -122.00% |
| ENERGY | 129 | 2.41% | -0.92% | -112.77% |
| CEMENT & CEMENT PRODUCTS | 122 | -0.36% | -0.34% | -40.99% |
| INDUSTRIAL MANUFACTURING | 314 | -0.20% | -0.10% | -30.56% |
| PAPER | 4 | -7.77% | -5.60% | -22.41% |
| FERTILISERS & PESTICIDES | 180 | -1.18% | 0.14% | 24.57% |


## Top 20 Portfolio Summary

| Metric | Value |
|---|---:|
| Trade count | 9016 |
| Valid trade count | 8613 |
| Alpha-valid trade count | 8402 |
| Average return | 0.22% |
| Win rate | 49.51% |
| Average alpha | 0.38% |

Best month by average return: `2026-04` with 7.22% average return.

Worst month by average return: `2026-02` with -8.22% average return.

### Top 20 Portfolio Top 20 Winners

| Signal Date | Entry Date | Symbol | Sector | Score | Sector Rank | ADX | Return | Benchmark | Alpha |
|---|---|---|---|---:|---:|---:|---:|---:|---:|
| 2024-07-22 | 2024-07-23 | EDELWEISS | FINANCIAL SERVICES | 100.00 | 1 | 53.19 | 64.31% | 1.50% | 62.81% |
| 2026-04-29 | 2026-04-30 | HFCL | TELECOM | 88.57 | 3 | 46.12 | 62.85% | N/A | N/A |
| 2026-04-28 | 2026-04-29 | HFCL | TELECOM | 82.86 | 4 | 44.21 | 61.50% | 0.40% | 61.10% |
| 2025-01-21 | 2025-01-22 | GODFRYPHLP | CONSUMER GOODS | 71.43 | 14 | 36.94 | 61.39% | -4.06% | 65.45% |
| 2026-04-24 | 2026-04-27 | HFCL | TELECOM | 77.14 | 7 | 39.31 | 60.04% | 1.25% | 58.79% |
| 2025-03-17 | 2025-03-18 | BSE | FINANCIAL SERVICES | 71.43 | 5 | 32.38 | 58.62% | 7.77% | 50.85% |
| 2025-01-20 | 2025-01-21 | GODFRYPHLP | CONSUMER GOODS | 71.43 | 14 | 35.67 | 56.81% | -5.50% | 62.31% |
| 2026-04-30 | 2026-05-01 | HFCL | TELECOM | 100.00 | 1 | 48.50 | 55.08% | N/A | N/A |
| 2025-01-22 | 2025-01-23 | GODFRYPHLP | CONSUMER GOODS | 71.43 | 13 | 38.20 | 54.88% | -3.02% | 57.91% |
| 2026-05-05 | 2026-05-06 | HFCL | TELECOM | 100.00 | 1 | 55.57 | 54.70% | -2.29% | 57.00% |
| 2024-07-19 | 2024-07-22 | EDELWEISS | FINANCIAL SERVICES | 100.00 | 1 | 52.50 | 53.73% | 2.28% | 51.45% |
| 2024-08-16 | 2024-08-19 | EDELWEISS | FINANCIAL SERVICES | 100.00 | 1 | 36.43 | 51.92% | 3.43% | 48.49% |
| 2024-12-06 | 2024-12-09 | ITI | TELECOM | 71.43 | 16 | 35.15 | 51.22% | -4.07% | 55.29% |
| 2026-04-27 | 2026-04-28 | HFCL | TELECOM | 82.86 | 5 | 41.82 | 50.93% | 0.39% | 50.54% |
| 2026-04-23 | 2026-04-24 | HFCL | TELECOM | 77.14 | 8 | 37.15 | 50.93% | -0.60% | 51.53% |
| 2026-05-04 | 2026-05-05 | HFCL | TELECOM | 94.29 | 2 | 53.18 | 50.75% | -1.21% | 51.95% |
| 2025-03-18 | 2025-03-19 | BSE | FINANCIAL SERVICES | 71.43 | 4 | 33.58 | 49.89% | 6.62% | 43.27% |
| 2025-03-13 | 2025-03-17 | BSE | FINANCIAL SERVICES | 71.43 | 5 | 31.08 | 49.41% | 7.51% | 41.90% |
| 2026-05-01 | 2026-05-04 | HFCL | TELECOM | 100.00 | 1 | 50.72 | 48.98% | -1.52% | 50.50% |
| 2024-08-19 | 2024-08-20 | EDELWEISS | FINANCIAL SERVICES | 100.00 | 1 | 38.27 | 43.80% | 3.21% | 40.59% |

### Top 20 Portfolio Top 20 Losers

| Signal Date | Entry Date | Symbol | Sector | Score | Sector Rank | ADX | Return | Benchmark | Alpha |
|---|---|---|---|---:|---:|---:|---:|---:|---:|
| 2025-01-09 | 2025-01-10 | VAKRANGEE | IT | 82.86 | 4 | 36.01 | -49.55% | -1.71% | -47.84% |
| 2025-01-08 | 2025-01-09 | VAKRANGEE | IT | 82.86 | 4 | 35.70 | -47.32% | -2.01% | -45.31% |
| 2025-01-06 | 2025-01-07 | ITI | TELECOM | 94.29 | 2 | 41.42 | -46.59% | -3.93% | -42.66% |
| 2026-02-25 | 2026-02-26 | IDBI | FINANCIAL SERVICES | 77.14 | 3 | 34.62 | -45.86% | -12.51% | -33.36% |
| 2026-02-24 | 2026-02-25 | IDBI | FINANCIAL SERVICES | 82.86 | 2 | 34.50 | -43.85% | -10.13% | -33.72% |
| 2026-02-20 | 2026-02-23 | IDBI | FINANCIAL SERVICES | 82.86 | 2 | 33.61 | -41.09% | -10.33% | -30.76% |
| 2026-02-23 | 2026-02-24 | IDBI | FINANCIAL SERVICES | 82.86 | 2 | 34.26 | -40.73% | -8.28% | -32.45% |
| 2026-02-26 | 2026-02-27 | IDBI | FINANCIAL SERVICES | 82.86 | 2 | 34.90 | -40.57% | -10.63% | -29.95% |
| 2026-02-19 | 2026-02-20 | IDBI | FINANCIAL SERVICES | 77.14 | 3 | 32.96 | -39.56% | -11.13% | -28.43% |
| 2026-02-17 | 2026-02-18 | IDBI | FINANCIAL SERVICES | 71.43 | 4 | 31.09 | -38.78% | -9.95% | -28.83% |
| 2026-02-27 | 2026-03-02 | IDBI | FINANCIAL SERVICES | 88.57 | 3 | 35.64 | -38.23% | -7.13% | -31.10% |
| 2025-01-03 | 2025-01-06 | VAKRANGEE | IT | 88.57 | 3 | 36.03 | -37.41% | N/A | N/A |
| 2025-01-23 | 2025-01-24 | KIRLOSENG | INDUSTRIAL MANUFACTURING | 71.43 | 16 | 37.27 | -35.80% | -3.26% | -32.54% |
| 2026-02-18 | 2026-02-19 | IDBI | FINANCIAL SERVICES | 77.14 | 3 | 32.50 | -35.62% | -9.98% | -25.64% |
| 2025-10-06 | 2025-10-07 | KIOCL | METALS | 88.57 | 3 | 42.63 | -35.50% | 1.39% | -36.88% |
| 2025-01-07 | 2025-01-08 | ITI | TELECOM | 94.29 | 2 | 44.02 | -35.40% | -2.91% | -32.50% |
| 2025-01-08 | 2025-01-09 | ITI | TELECOM | 94.29 | 2 | 44.97 | -33.72% | -2.01% | -31.71% |
| 2025-02-03 | 2025-02-04 | VAKRANGEE | IT | 77.14 | 3 | 30.88 | -33.43% | -6.01% | -27.42% |
| 2025-01-03 | 2025-01-06 | KEC | CONSTRUCTION | 71.43 | 10 | 44.97 | -33.01% | N/A | N/A |
| 2025-01-21 | 2025-01-22 | KIRLOSENG | INDUSTRIAL MANUFACTURING | 71.43 | 16 | 35.04 | -32.31% | -4.06% | -28.24% |

### Top 20 Portfolio Top Sectors By Contribution

| Sector | Trades | Avg Return | Avg Alpha | Total Alpha |
|---|---:|---:|---:|---:|
| FINANCIAL SERVICES | 2183 | 1.67% | 1.29% | 2739.82% |
| METALS | 544 | 2.76% | 2.86% | 1484.97% |
| CHEMICALS | 243 | 2.96% | 2.89% | 682.79% |
| HEALTHCARE SERVICES | 390 | 2.28% | 1.73% | 664.78% |
| PHARMA | 733 | 0.33% | 0.87% | 628.27% |
| TELECOM | 128 | 3.04% | 3.63% | 442.30% |
| AUTOMOBILE | 608 | -0.27% | 0.02% | 10.48% |
| MEDIA & ENTERTAINMENT | 6 | -7.19% | -5.16% | -30.95% |
| CEMENT & CEMENT PRODUCTS | 250 | 0.29% | -0.17% | -41.56% |
| TEXTILES | 107 | -3.43% | -0.67% | -69.04% |

### Top 20 Portfolio Bottom Sectors By Contribution

| Sector | Trades | Avg Return | Avg Alpha | Total Alpha |
|---|---:|---:|---:|---:|
| CONSUMER GOODS | 1153 | -1.64% | -0.98% | -1112.92% |
| IT | 424 | -2.50% | -1.78% | -730.45% |
| CONSTRUCTION | 269 | -2.15% | -1.83% | -480.33% |
| SERVICES | 199 | -4.01% | -2.45% | -468.73% |
| INDUSTRIAL MANUFACTURING | 737 | -0.75% | -0.33% | -238.51% |
| FERTILISERS & PESTICIDES | 222 | -1.44% | -0.45% | -97.90% |
| ENERGY | 398 | 0.85% | -0.23% | -87.87% |
| PAPER | 19 | -5.11% | -3.71% | -70.43% |
| TEXTILES | 107 | -3.43% | -0.67% | -69.04% |
| CEMENT & CEMENT PRODUCTS | 250 | 0.29% | -0.17% | -41.56% |

## Notes

- Monthly best/worst months are based on average holding-period return by entry month.
- Sector contribution is ranked by total alpha contribution, not average return alone.
- Top 10 and Top 20 ledgers are overlapping by construction; Top 10 is the highest-ranked subset of Top 20.
- This is still a fixed-horizon research ledger, not a full portfolio simulator with capital constraints, overlapping position sizing, transaction costs, or dynamic exits.

No production scoring was modified.
