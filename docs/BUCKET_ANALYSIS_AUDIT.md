# Bucket Analysis Audit

**Date:** 2026-06-11

**Scope:** Audit of score bucket analysis and related factor/sector bucket analysis paths.

**Code reviewed:**

- `scripts/run_validation_backtest.py`
- `app/backtesting/run_backtest.py`
- `app/research/factor_analysis.py`
- `app/research/sector_factor_analysis.py`
- `tests/test_factor_analysis.py`

**Outputs reviewed:**

- `reports/backtest_validation_results.json`
- `docs/BACKTEST_RESULTS.md`
- `docs/V1_BASELINE.md`
- `docs/SECTOR_FACTOR_RESEARCH.md`
- `docs/SECTOR_RESEARCH_AUDIT.md`

---

## Executive Summary

The score bucket analysis pipeline has a confirmed defect.

Recommendations are assigned into score buckets, but bucket performance is not calculated from those bucket members. Instead, each bucket calls the full `BacktestRunner.run()` method for the bucket's minimum and maximum date range. That reruns the full model over that date range, so multiple buckets can report identical or near-identical results.

This means the existing score bucket conclusions in `reports/backtest_validation_results.json`, `docs/BACKTEST_RESULTS.md`, and documents that rely on them should not be treated as valid evidence of score monotonicity.

The separate factor/sector quintile bucket pipeline is mechanically valid for numeric factor sorting and aggregation, but interpretation must be factor-specific. `bucket_1` always means the lowest numeric factor values, not necessarily the weakest trading signal.

---

## Pipeline Map

### Score Bucket Pipeline

Source: `scripts/run_validation_backtest.py`

Flow:

1. Load all `RecommendationHistory` rows for a model.
2. Assign recommendations to fixed score bands using `bucket_scores()`.
3. For each score bucket, call `analyze_bucket()`.
4. `analyze_bucket()` derives only `start_date` and `end_date` from the bucket.
5. `analyze_bucket()` calls `BacktestRunner.run(model, start_date, end_date, persist=False)`.
6. Metrics are calculated from the full backtest result for that model/date range.

### Factor/Sector Bucket Pipeline

Sources:

- `app/research/factor_analysis.py`
- `app/research/sector_factor_analysis.py`

Flow:

1. Pair factor values with forward returns.
2. Sort pairs by factor value ascending.
3. Split sorted values into five equal-count buckets where possible.
4. Aggregate average return, median return, and win rate per bucket.
5. Label `bucket_1` as lowest numeric values and `bucket_5` as highest numeric values.

---

## Findings

### 1. Critical Defect: Score Bucket Performance Ignores Bucket Members

**Status:** Confirmed defect.

`bucket_scores()` correctly returns lists of recommendations per score range. However, `analyze_bucket()` does not compute returns for those recommendations. It only uses bucket records to get:

- minimum bucket date
- maximum bucket date

Then it calls:

```python
report = backtest_runner.run(model, start_date, end_date, persist=False)
```

`BacktestRunner.run()` loads all recommendations for the model and date range:

```python
query = select(RecommendationHistory).where(RecommendationHistory.model == model)
```

It does not receive a score bucket filter, recommendation IDs, symbols, ranks, or explicit recommendation records.

**Impact:**

The bucket output is not a per-bucket backtest. It is a full model backtest over the bucket's date span.

This explains why existing bucket outputs are identical or near-identical:

- Swing `70-74`, `75-79`, and `80-84` all report `trade_count = 1916`, `avg_return = -0.0042167`, `win_rate = 0.446764`.
- Positional `75-79`, `80-84`, and `85-100` all report `trade_count = 5548`, `avg_return = -0.0205509`, `win_rate = 0.445566`.

Those are not independent bucket results.

**Root Cause:**

The score bucket list is discarded after date range extraction. The backtest runner API only supports model/date filtering, not explicit recommendation-set filtering.

**Proposed Fix:**

Add a path that evaluates exactly the recommendations in the bucket. Reasonable options:

1. Add a `BacktestRunner.run_recommendations(recommendations, model, persist=False)` method.
2. Add optional filters to `BacktestRunner.run()` for recommendation IDs or `(model, date, symbol, rank)` identity.
3. Compute forward returns directly inside score bucket analysis using the same return helper used by `BacktestRunner`.

The preferred design is option 1 because it reuses the existing backtest return logic while making the input set explicit.

---

### 2. Bucket Assignment Has Decimal Score Gaps

**Status:** Confirmed defect risk.

Score buckets are defined with closed integer ranges:

```python
if 70 <= score <= 74:
elif 75 <= score <= 79:
elif 80 <= score <= 84:
```

This excludes decimal scores between ranges:

- `74.1` to `74.9`
- `79.1` to `79.9`
- `84.1` to `84.9`
- `89.1` to `89.9`

The positional model has the same issue around `69/70`, `74/75`, `79/80`, and `84/85`.

**Impact:**

If recommendation scores are decimals, some records are silently dropped from all buckets.

**Root Cause:**

The code uses display-style labels as exact numeric bounds, rather than half-open intervals.

**Proposed Fix:**

Use half-open ranges:

- Swing:
  - `70 <= score < 75`
  - `75 <= score < 80`
  - `80 <= score < 85`
  - `85 <= score < 90`
  - `90 <= score <= 100`

- Positional:
  - `65 <= score < 70`
  - `70 <= score < 75`
  - `75 <= score < 80`
  - `80 <= score < 85`
  - `85 <= score <= 100`

Also report an `unbucketed_count` so missing or out-of-range scores are visible.

---

### 3. Score Buckets Are Fixed Bands, Not Quintiles

**Status:** Design clarification needed.

The score bucket pipeline uses fixed score bands, not equal-count quintiles.

Examples:

- Swing: `70-74`, `75-79`, `80-84`, `85-89`, `90-100`
- Positional: `65-69`, `70-74`, `75-79`, `80-84`, `85-100`

This is valid if the objective is threshold validation. It is not valid to describe these as quintiles.

**Impact:**

If score distributions are concentrated, fixed bands may produce uneven sample sizes. That is not wrong, but the report must interpret them as threshold bands, not quintile buckets.

**Proposed Fix:**

Keep fixed bands for score threshold validation, but label them as "score bands." If the research objective is rank-order predictive power, add a separate equal-count score quintile analysis.

---

### 4. Score Bucket `trade_count` Is Misleading

**Status:** Confirmed defect.

When returns exist, `analyze_bucket()` reports:

```python
"trade_count": len(returns)
```

Because `returns` come from the full model/date-range backtest, this is not the number of recommendations in the score bucket.

When no returns exist, it reports:

```python
"trade_count": len(bucket)
```

So the same field has two meanings depending on the branch.

**Impact:**

The reported count can look like valid bucket sample size while actually being full-backtest valid return count.

**Proposed Fix:**

Report separate fields:

- `assigned_count`: number of recommendations assigned to the bucket
- `priced_count`: number with entry price available
- `valid_return_count`: number with valid forward return

---

### 5. No Evidence Of Direct Output Object Reuse, But Functional Reuse Exists

**Status:** Confirmed.

The code does not appear to reuse the same Python dictionary object for multiple buckets. The repeated results are caused by rerunning equivalent full-model backtests, not by accidental shared mutable output.

**Impact:**

This is a logic defect, not a formatting-only copy/paste defect.

**Proposed Fix:**

Fix the bucket input to the performance calculation. After that, regenerate all affected report files.

---

### 6. Existing Score Bucket Reports Contain Invalid Evidence

**Status:** Confirmed.

The following outputs include score bucket tables affected by the defect:

- `reports/backtest_validation_results.json`
- `docs/BACKTEST_RESULTS.md`
- `docs/V1_BASELINE.md`

Related V2 documents correctly flagged the bucket analysis as suspicious, but any recommendation based specifically on score bucket monotonicity should be considered provisional.

**Impact:**

Current conclusions that "higher scores do not differentiate performance" may still be true, but the existing score bucket analysis does not prove it.

**Proposed Fix:**

After code remediation, rerun validation backtests and update the affected research docs. Until then, use overall backtest performance, factor research, and sector research as stronger evidence than score bucket monotonicity.

---

## Factor/Sector Quintile Review

### 7. Factor Bucket Assignment Logic Is Mechanically Correct

**Status:** Valid with caveats.

`FactorAnalyzer.bucket_analysis()`:

1. Requires equal-length factor and return arrays.
2. Pairs each factor value with its corresponding return.
3. Sorts pairs ascending by factor value.
4. Splits the sorted data into `num_buckets`.
5. Aggregates count, average return, median return, and win rate.

Tests cover:

- bucket count
- equal distribution
- remainder distribution
- average calculation
- median calculation
- win-rate calculation
- empty input
- mismatched lengths
- sorting behavior

**Caveats:**

- Tied factor values can be split across adjacent buckets.
- Remainder observations are assigned to earlier buckets.
- This is equal-count bucketing, not percentile cutpoint bucketing by unique values.

These caveats are acceptable for exploratory factor research if documented.

---

### 8. `bucket_1` And `bucket_5` Are Numeric Direction Labels

**Status:** Valid but easy to misinterpret.

For factor research:

- `bucket_1` = lowest numeric factor values
- `bucket_5` = highest numeric factor values

This is not the same as:

- weakest signal
- strongest signal
- worst sectors
- best sectors

For example, `rank_3m` is inverse by design: lower rank means stronger sector. Therefore:

- `rank_3m bucket_1` = strongest sectors
- `rank_3m bucket_5` = weakest sectors
- negative IC for `rank_3m` is favorable
- negative highest-minus-lowest spread for `rank_3m` can support sector leadership

**Impact:**

Generic labels like "Top Bucket" can be misleading for inverse factors.

**Proposed Fix:**

Reports should distinguish:

- `lowest_value_bucket_return`
- `highest_value_bucket_return`
- `strongest_signal_bucket`
- `weakest_signal_bucket`
- `direction_adjusted_spread`

---

### 9. Sector Monotonicity Is Direction-Sensitive

**Status:** Interpretation defect risk.

`SectorFactorAnalyzer._monotonicity_score()` checks whether average returns increase from `bucket_1` to `bucket_5`.

That is correct only for factors where higher numeric value is expected to be better.

For `rank_3m`, higher numeric value is weaker sector rank. Therefore, a strong leadership signal would generally be decreasing from `bucket_1` to `bucket_5`, not increasing.

**Impact:**

The monotonicity score for `rank_3m` can understate or invert the quality of the factor if interpreted as leadership monotonicity.

**Proposed Fix:**

Add factor direction metadata:

| Factor | Higher Numeric Value Means | Preferred Direction |
|---|---|---|
| `rank_3m` | weaker sector rank | lower is better |
| `sector_return_1m` | higher trailing sector return | higher is better if using momentum |
| `sector_return_3m` | higher trailing sector return | higher is better if using momentum |
| `sector_return_6m` | higher trailing sector return | higher is better if using momentum |

Then calculate monotonicity and spread in the intended direction.

---

## Copy/Paste And Reporting Errors

### Confirmed Reporting Problems

1. Score bucket tables in existing reports present invalid per-bucket performance.
2. Score bucket `trade_count` is labeled as if it were bucket size, but it is full-backtest valid return count.
3. Some documents already identify the bucket issue as suspicious; this audit confirms the root cause.

### Not Confirmed As Copy/Paste Errors

The repeated bucket metrics do not appear to come from manually copied table rows or shared dictionary reuse. They come from rerunning full-model backtests with overlapping or identical date windows.

### Reporting Ambiguities

1. "Quintile" should be reserved for equal-count factor buckets, not fixed score bands.
2. "Top Bucket" should be clarified as highest numeric values, not automatically strongest signal.
3. Sector `rank_3m` should always be described as inverse-direction.

---

## Recommended Fix Plan

Do not implement V2 scoring from the existing score bucket outputs until this is fixed.

Recommended remediation:

1. Add a bucket-specific backtest path that accepts explicit recommendation records.
2. Preserve recommendation identity through the bucket analysis pipeline.
3. Use half-open score ranges to avoid decimal gaps.
4. Report `assigned_count`, `priced_count`, and `valid_return_count`.
5. Add `unbucketed_count`.
6. Add unit tests for decimal score boundaries.
7. Add unit tests proving each bucket only evaluates its own recommendation records.
8. Re-run validation backtests.
9. Regenerate `reports/backtest_validation_results.json`.
10. Update `docs/BACKTEST_RESULTS.md`, `docs/V1_BASELINE.md`, and any V2 docs that reference score bucket behavior.

---

## Audit Verdict

| Area | Verdict |
|---|---|
| Score bucket assignment | Defective for decimal boundaries |
| Score bucket performance aggregation | Defective; bucket members ignored |
| Score bucket trade counts | Misleading |
| Score bucket output reuse | No object reuse found; full-backtest rerun causes repeated outputs |
| Factor quintile creation | Mechanically valid |
| Factor bucket return aggregation | Mechanically valid |
| Sector bucket interpretation | Valid only with factor direction caveats |
| Existing score bucket conclusions | Invalid until rerun after fix |

The most important correction is to make score bucket analysis evaluate the exact recommendations assigned to each bucket. Until that is done, score bucket monotonicity should not be used as evidence for or against V1 or V2 scoring quality.
