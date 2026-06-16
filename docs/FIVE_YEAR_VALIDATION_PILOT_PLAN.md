# Five-Year Validation Pilot Plan

Objective: design a pilot 5-year validation of Swing V2.1 using only high-confidence exact-match securities.

Scope:

- Design only.
- Do not aggregate data.
- Do not create tables.
- Do not modify databases.
- Do not run backtests.
- Do not rebuild features.
- Do not load security master data.

Inputs:

- `angel_data.ohlcv_15min`
- `reports/phase1b_security_master_proposals.csv`
- `reports/phase1b_alias_proposals.csv`
- `reports/phase1b_reconciliation_dry_run.json`
- `reports/phase1b_manual_review_queue.csv`
- Swing V2.1 implementation and scoring logic

Pilot universe:

- Use only the 285 exact-match securities from Phase 1B reconciliation.
- Exclude potential mappings.
- Exclude ambiguous mappings.
- Exclude rename-review cases.
- Exclude manual-review cases.
- Exclude Angel-only securities.

## Executive Design

The pilot should answer one narrow question:

```text
Does frozen Swing V2.1 still show an edge when run on approximately 5 years of Angel-derived daily bars for the 285 safest exact-match securities?
```

This is not a final production backtest. It is a data-expansion pilot with a deliberately conservative universe. The pilot trades off coverage for identity certainty.

## Universe Definition

Source:

- `reports/phase1b_alias_proposals.csv`

Selection rule:

```text
security_proposal_id where:
  source aliases include research and angel
  confidence = high
  review_status = approved
  alias_reason = exact
```

Expected result:

- 285 securities
- 570 alias rows
- one research alias and one Angel alias per security

Explicit exclusions:

- `known_rename`
- `potential`
- `ambiguous`
- `unmatched`
- `angel_only`
- any security with missing Angel 15-minute history
- any security with material unresolved OHLC defects

## 1. Daily-Bar Aggregation Design

### Source Bars

Source table:

```text
angel_data.ohlcv_15min
```

Expected source columns:

- `datetime`
- `symbol`
- `open`
- `high`
- `low`
- `close`
- `volume`

### Session Boundary

Use regular NSE cash-market session:

```text
09:15 to 15:30 Asia/Kolkata
```

For 15-minute bars, expected interval starts normally run:

```text
09:15, 09:30, ..., 15:15
```

Design rule:

- Include bars where local time is `>= 09:15` and `<= 15:15`.
- Treat `15:15` bar as the closing interval.
- Exclude pre-open, post-close, and malformed off-session bars.

### OHLC Derivation

For each `symbol, trading_date`:

- Daily open: `open` of the earliest valid intraday bar.
- Daily high: maximum `high` across valid intraday bars.
- Daily low: minimum `low` across valid intraday bars.
- Daily close: `close` of the latest valid intraday bar.
- Daily volume: sum of `volume` across valid intraday bars.

Minimum expected full-day bars:

```text
25 bars per full trading day
```

Half-days or special sessions:

- Do not force-fill.
- Flag as special/short session if source-wide bar count is below normal.
- Include only if the date appears in the source-wide trading calendar and most symbols have the same shortened pattern.

### Trading Calendar Handling

Use an observed Angel source-wide trading calendar for the pilot:

```text
distinct datetime::date from ohlcv_15min
```

Rationale:

- It avoids assuming an external holiday calendar before the data is validated.
- It makes gaps measurable against the same source.

Future production design can replace this with an official NSE calendar.

### Missing-Bar Handling

For each `symbol, trading_date`:

- If no bars exist: mark missing daily bar.
- If first bar starts after `09:15`: flag missing opening interval.
- If last bar ends before `15:15`: flag missing closing interval.
- If bar count is below full-day expected while source-wide day is normal: flag partial day.
- Do not forward-fill OHLCV.
- Do not synthesize missing opens or closes.

Pilot inclusion rule:

- A symbol can remain in the pilot if gaps are sparse and documented.
- A symbol should be excluded if missing bars affect enough days to distort 20-day returns, ADX, EMA200, or entry/exit prices.

## 2. Data-Quality Validation

### OHLC Checks

Run at 15-minute source level and derived daily level:

- `high >= low`
- `high >= open`
- `high >= close`
- `low <= open`
- `low <= close`
- open, high, low, close are non-null
- prices are positive

Failure policy:

- Source-level bad bars should block that symbol/date from aggregation.
- Daily-level OHLC failure blocks that symbol/date.
- Repeated failures should exclude the symbol from the pilot.

### Gap Checks

For every exact-match symbol:

- Earliest source date.
- Latest source date.
- Trading-day count.
- Missing trading days against source-wide calendar.
- Missing first interval count.
- Missing last interval count.
- Partial-day count.

Pilot target:

- At least 5 years of available source history for seasoned securities.
- IPOs within exact-match set may have shorter valid history but should not be included before listing.

### Duplicate Checks

Source duplicate key:

```text
symbol, datetime
```

Daily duplicate key:

```text
symbol, date
```

Validation:

- No duplicate 15-minute bars for included symbol/datetime.
- No duplicate derived daily bars.
- If duplicate bars exist, require deterministic rule before production use.

Pilot default:

- Exclude duplicate-affected symbol/date from aggregation.
- Exclude symbol if duplicates are frequent.

### Corporate-Action Detection Requirements

Even exact-match symbols can have splits, bonuses, demergers, or large dividends.

Detect:

- Daily close-to-close absolute move >= 40%.
- Daily open versus prior close absolute gap >= 40%.
- Large discontinuity near known corporate-action dates.

Policy:

- Flag candidates.
- Do not automatically adjust.
- Do not trust backtest results until major discontinuities are reviewed.

For pilot reporting:

- Report results both including and excluding corporate-action-flagged trades if practical in later implementation.

## 3. Research Database Integration Approach

### Recommended Approach

Use staging or temporary tables first.

Do not load into production `prices_daily` during the pilot.

Preferred design:

```text
staging_angel_daily_bars_exact_285
staging_angel_data_quality_exact_285
staging_angel_feature_rebuild_exact_285
staging_angel_scores_exact_285
staging_angel_recommendations_exact_285
```

Alternative:

- Use a separate pilot database cloned from `nse_research_platform`.

Best option for safety:

```text
Create a separate pilot database.
Restore current research DB schema.
Load only pilot daily bars and derived research artifacts.
```

This avoids contaminating current production/research tables.

### Staging Workflow

1. Select 285 exact-match Angel symbols.
2. Validate source 15-minute bars.
3. Aggregate to daily bars in staging.
4. Validate derived daily bars.
5. Compare overlapping dates with current `prices_daily`.
6. Only then rebuild pilot features in isolated tables or pilot DB.
7. Generate pilot scores and recommendations in isolated tables or pilot DB.
8. Run pilot backtests.
9. Export reports.

### Validation Workflow

Before feature rebuild:

- Source coverage report.
- Daily aggregation report.
- Overlap comparison versus current daily prices.
- Corporate-action candidate report.

Before scoring:

- Feature completeness report.
- EMA200 warmup coverage report.
- ADX availability report.
- Sector rank availability report.

Before backtest:

- Recommendation count by date.
- Eligible universe size by date.
- Entry/exit price availability.
- Benchmark availability.

## 4. Feature Rebuild Scope

Swing V2.1 needs:

- close
- open
- ADX 14
- EMA200
- prior 20-day return
- sector rank
- sector metadata

Existing feature pipeline can regenerate:

- ADX 14
- EMA periods including EMA200
- price-derived returns
- liquidity and eligibility fields
- existing technical indicators, even if not used by V2.1

Sector rebuild can regenerate:

- sector return windows
- sector rank
- sector strength fields

Features that may be constrained:

- Relative strength versus Nifty if benchmark history is incomplete.
- Any feature depending on `symbol_master.nse500` static membership.
- Sector ranks if sector membership for Angel-only/current symbols is missing.
- 52-week features during early warmup.
- EMA200 until at least 200 daily bars exist.

Pilot rule:

- Keep Swing V2.1 frozen.
- Rebuild all required existing features, but use only the fields required by V2.1 for eligibility and scoring.
- Do not create new factors.
- Do not alter V2.1 thresholds.

Warmup:

- Require at least 252 trading days before evaluating signals.
- For five-year source data, first tradable signal date should be after warmup.

## 5. Swing V2.1 Rebuild Process

Frozen V2.1 definition:

- Core signals:
  - Sector Rank
  - ADX
- Entry filters:
  - distance above EMA200 <= 25%
  - prior 20-day return <= 15%

Score formula:

```text
(ADX score + Sector Rank score) / 35 * 100
```

Score is null unless entry filters pass.

### Score Generation

Pilot design:

1. Load staged features.
2. Run existing `ScoreComputer` logic in isolated pilot context.
3. Generate only for 285 exact-match securities.
4. Write scores to pilot/staging score table or pilot DB.
5. Validate score counts by date.

### Recommendation Generation

Pilot design:

1. Use existing `generate_swing_v2_1()` logic.
2. Minimum score: 70.
3. Top 20 per signal date.
4. Store recommendations in pilot/staging recommendation table or pilot DB.
5. Validate no non-pilot symbols appear.

### Backtest Generation

Use existing Swing V2.1 backtest rules:

- Entry: next-trading-day open.
- Exit: fixed-horizon close.
- Horizons: 5d, 10d, 20d.
- Primary horizon: 20d.

Portfolio validation:

- Top 5 weekly.
- Top 10 weekly.
- Top 10 weekly plus max 2 per sector.

Transaction cost sensitivity:

- Include 0.25% round-trip cost scenario in pilot reporting if using portfolio backtester.

## 6. Validation Methodology

### Compare Against Current 2-Year Results

Current champion trade-level 20-day results:

- Avg Return: 0.4244%
- Win Rate: 50.77%
- Profit Factor: 1.1283
- Alpha: 0.4107%

Compare:

- Current 2-year V2.1 on full current research universe.
- Pilot 2-year overlap using only exact-match 285.
- Pilot 5-year exact-match 285.

This separates:

- universe restriction effect
- data source effect
- time-period extension effect

### Trade-Level Metrics

Report by horizon:

- trade count
- valid trade count
- average return
- median return
- win rate
- max gain
- max loss
- standard deviation
- profit factor
- alpha versus benchmark

### Portfolio Metrics

Report for each portfolio structure:

- CAGR
- total return
- Sharpe
- Sortino
- max drawdown
- profit factor
- turnover
- average holdings
- sector concentration
- benchmark return
- alpha

### Stability Checks

Split the 5-year pilot:

- year-by-year
- first half versus second half
- bull/bear regime if existing regime labels are available
- high/low volatility if existing regime analysis can be reused

Do not add market filters.

## 7. Runtime Estimates

Approximate source size:

- Angel source has about 13.5M 15-minute rows for 499 symbols.
- Exact-match pilot uses 285 symbols.
- Expected pilot source rows: roughly 7.5M to 8.0M rows, depending on coverage.

Estimated runtime on local PostgreSQL:

| Step | Estimate |
| --- | ---: |
| Select exact-match symbol list | < 1 minute |
| Source 15-minute validation | 5-15 minutes |
| Daily aggregation | 5-20 minutes |
| Derived daily validation | 2-5 minutes |
| Overlap comparison versus current prices | 2-5 minutes |
| Feature generation | 15-45 minutes |
| Sector rank generation | 5-15 minutes |
| Score generation | 5-15 minutes |
| Recommendation generation | 2-10 minutes |
| Trade-level backtest | 5-15 minutes |
| Portfolio backtests | 5-20 minutes |

Expected total:

- Fast path: 1-2 hours
- Conservative path with reports and checks: 2-4 hours

Actual runtime depends on indexing, PostgreSQL memory settings, and whether a separate pilot database is used.

## 8. Risks

### Universe Bias

Using only 285 exact-match securities improves identity certainty but introduces a universe restriction.

Risk:

- Results may not represent the full NSE500.
- Excludes renamed, newly listed, and Angel-only current securities.

Mitigation:

- Compare exact-match pilot against current 2-year full-universe results.
- Label results as exact-match pilot only.

### Survivorship Effects

The 285 exact-match set may overrepresent securities that survived unchanged across the period.

Risk:

- Pilot may overstate robustness.

Mitigation:

- Treat pilot as data plumbing validation, not final survivorship-correct backtest.
- Later include reviewed lineage and historical membership snapshots.

### Missing IPO Coverage

Angel-only new IPOs are excluded.

Risk:

- Pilot misses important current NSE500 constituents and recent winners/losers.

Mitigation:

- Track Angel-only excluded count separately.
- Add reviewed IPO handling in later phases.

### Symbol-Lineage Limitations

Renames and corporate-action successors are excluded.

Risk:

- Five-year history is incomplete for entities that changed symbols.

Mitigation:

- Keep Phase 1B review queue active.
- Expand pilot only after alias validity dates are approved.

### Corporate Actions

Unadjusted or inconsistently adjusted data can distort factors and returns.

Mitigation:

- Large-discontinuity detection.
- Review high-impact symbols.
- Report sensitivity excluding flagged trades.

### Sector Rank Integrity

Sector rank depends on accurate sector assignments and sufficient sector coverage.

Risk:

- 285-symbol subset may distort sector ranks.

Mitigation:

- Compute sector ranks within pilot and report sector counts.
- Compare to current two-year sector rank behavior.
- Do not interpret sector results as final full-universe behavior.

## Pilot Acceptance Criteria

Proceed to implementation only if:

- Exact-match list is reproducible from proposal files.
- Source 15-minute coverage exists for most of the 285 symbols back to 2021.
- Derived daily bars pass OHLC and duplicate checks.
- Missing-bar rates are acceptable and reported.
- Corporate-action discontinuities are flagged.
- Feature rebuild can produce ADX, EMA200, prior 20-day return, and sector rank.
- Pilot results are clearly labeled as exact-match restricted.

## Non-Goals

This pilot does not:

- Solve full NSE500 survivorship bias.
- Load security master data.
- Approve rename mappings.
- Use potential or ambiguous mappings.
- Include Angel-only securities.
- Create production tables.
- Modify `prices_daily`.
- Modify `features_daily`.
- Change Swing V2.1 logic.
- Introduce market filters.
- Create V2.2 or V3.

## Recommended Implementation Sequence Later

When implementation is approved:

1. Generate exact-match symbol list from `phase1b_alias_proposals.csv`.
2. Run read-only Angel source validation for those symbols.
3. Build daily aggregation into isolated staging or pilot DB.
4. Validate daily bars.
5. Compare overlapping current daily prices.
6. Rebuild required features in isolation.
7. Recompute sector ranks in isolation.
8. Generate Swing V2.1 scores in isolation.
9. Generate recommendations in isolation.
10. Run trade-level and portfolio backtests in isolation.
11. Compare against current 2-year baseline.
12. Produce pilot validation report.

Final note:

The pilot should be treated as a controlled validation of data expansion mechanics and model durability on the safest identity subset. It should not be treated as the final answer on whether Swing V2.1 survives full historical NSE500 reconstruction.
