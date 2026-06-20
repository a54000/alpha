# Sector RRG Data Coverage Audit

Read-only audit of the data needed to compute real RS-Ratio / RS-Momentum sector rotation tails.

## Summary

- As of: `2026-06-17`
- Sectors audited: `17`
- Ready: `17`
- Warning: `0`
- Not ready: `0`
- Minimum required overlap sessions: `35`

## Sector Results

| Sector | Status | Reason | Valid Sessions | Nifty Overlap | Price Coverage | Fix |
| --- | --- | --- | ---: | ---: | ---: | --- |
| AUTOMOBILE | ready | ok | 95 | 92 | 100.0% | No data fix required for RRG readiness. |
| CEMENT & CEMENT PRODUCTS | ready | ok | 95 | 92 | 100.0% | No data fix required for RRG readiness. |
| CHEMICALS | ready | ok | 95 | 92 | 89.4% | No data fix required for RRG readiness. |
| CONSTRUCTION | ready | ok | 95 | 92 | 100.0% | No data fix required for RRG readiness. |
| CONSUMER GOODS | ready | ok | 95 | 92 | 98.7% | No data fix required for RRG readiness. |
| ENERGY | ready | ok | 95 | 92 | 100.0% | No data fix required for RRG readiness. |
| FERTILISERS & PESTICIDES | ready | ok | 95 | 92 | 100.0% | No data fix required for RRG readiness. |
| FINANCIAL SERVICES | ready | ok | 95 | 92 | 98.4% | No data fix required for RRG readiness. |
| HEALTHCARE SERVICES | ready | ok | 95 | 92 | 100.0% | No data fix required for RRG readiness. |
| INDUSTRIAL MANUFACTURING | ready | ok | 95 | 92 | 100.0% | No data fix required for RRG readiness. |
| IT | ready | ok | 95 | 92 | 100.0% | No data fix required for RRG readiness. |
| MEDIA & ENTERTAINMENT | ready | ok | 95 | 92 | 100.0% | No data fix required for RRG readiness. |
| METALS | ready | ok | 95 | 92 | 99.9% | No data fix required for RRG readiness. |
| PHARMA | ready | ok | 95 | 92 | 98.1% | No data fix required for RRG readiness. |
| SERVICES | ready | ok | 95 | 92 | 99.8% | No data fix required for RRG readiness. |
| TELECOM | ready | ok | 95 | 92 | 100.0% | No data fix required for RRG readiness. |
| TEXTILES | ready | ok | 95 | 92 | 100.0% | No data fix required for RRG readiness. |

## Interpretation

- `ready` means enough sector and Nifty 50 history exists for a reliable RRG tail.
- `warning` means the sector can compute, but some constituent daily bars are missing.
- `not_ready` means the page should not make a rotation call for that sector yet.
