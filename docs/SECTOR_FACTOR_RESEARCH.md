# Sector Factor Research

**Phase:** 6.5C
**Date Range:** 2024-07-08 to 2026-06-09
**JSON Results:** `reports/sector_factor_results.json`

## Scope

This research tests whether sector leadership factors predict future stock returns.
It does not modify scoring models, recommendations, or V2 implementation.

## Method

- Join `features_daily` to `sector_daily` on `(date, sector)`.
- Assign each stock the sector factor value available on the signal date.
- Compute stock forward returns at 5d, 10d, 20d, and 60d horizons.
- Report Pearson correlation, Spearman IC, quintile buckets, monotonicity, and bucket spread.

## Summary

| Factor | Horizon | Sample | Pearson | Spearman IC | Bottom Bucket | Top Bucket | Spread | Monotonicity |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| rank_3m | 5d | 203241 | -0.0253 | -0.0347 | 0.0020 | -0.0022 | -0.0042 | 0.2500 |
| rank_3m | 10d | 201076 | -0.0415 | -0.0523 | 0.0053 | -0.0044 | -0.0096 | 0.0000 |
| rank_3m | 20d | 196746 | -0.0589 | -0.0683 | 0.0112 | -0.0093 | -0.0206 | 0.2500 |
| rank_3m | 60d | 179426 | -0.0293 | -0.0310 | -0.0083 | -0.0220 | -0.0137 | 0.2500 |
| sector_return_1m | 5d | 203241 | -0.0295 | -0.0262 | 0.0039 | -0.0006 | -0.0046 | 0.7500 |
| sector_return_1m | 10d | 201076 | -0.0313 | -0.0211 | 0.0080 | 0.0026 | -0.0054 | 0.5000 |
| sector_return_1m | 20d | 196746 | -0.0396 | -0.0368 | 0.0154 | 0.0057 | -0.0097 | 0.5000 |
| sector_return_1m | 60d | 179426 | -0.0359 | -0.0217 | 0.0162 | -0.0008 | -0.0170 | 0.5000 |
| sector_return_3m | 5d | 185055 | -0.0518 | -0.0513 | 0.0067 | -0.0008 | -0.0076 | 0.2500 |
| sector_return_3m | 10d | 182890 | -0.0584 | -0.0544 | 0.0117 | -0.0012 | -0.0130 | 0.2500 |
| sector_return_3m | 20d | 178560 | -0.0725 | -0.0712 | 0.0169 | -0.0069 | -0.0238 | 0.5000 |
| sector_return_3m | 60d | 161240 | -0.1156 | -0.0958 | 0.0416 | -0.0187 | -0.0603 | 0.5000 |
| sector_return_6m | 5d | 157776 | -0.0553 | -0.0394 | 0.0063 | -0.0031 | -0.0095 | 0.5000 |
| sector_return_6m | 10d | 155611 | -0.0740 | -0.0623 | 0.0130 | -0.0050 | -0.0181 | 0.2500 |
| sector_return_6m | 20d | 151281 | -0.1279 | -0.1276 | 0.0301 | -0.0127 | -0.0427 | 0.0000 |
| sector_return_6m | 60d | 133977 | -0.2023 | -0.2118 | 0.0779 | -0.0221 | -0.1000 | 0.2500 |

## Quintile Buckets

### rank_3m

#### 5d

| Bucket | Count | Average Return | Median Return | Win Rate |
|---|---:|---:|---:|---:|
| bucket_1 | 40649 | 0.0020 | 0.0000 | 0.4985 |
| bucket_2 | 40648 | 0.0006 | -0.0019 | 0.4773 |
| bucket_3 | 40648 | -0.0010 | -0.0031 | 0.4602 |
| bucket_4 | 40648 | -0.0010 | -0.0029 | 0.4568 |
| bucket_5 | 40648 | -0.0022 | -0.0050 | 0.4421 |

#### 10d

| Bucket | Count | Average Return | Median Return | Win Rate |
|---|---:|---:|---:|---:|
| bucket_1 | 40216 | 0.0053 | 0.0009 | 0.5060 |
| bucket_2 | 40215 | -0.0003 | -0.0050 | 0.4611 |
| bucket_3 | 40215 | -0.0005 | -0.0046 | 0.4621 |
| bucket_4 | 40215 | -0.0028 | -0.0061 | 0.4467 |
| bucket_5 | 40215 | -0.0044 | -0.0092 | 0.4285 |

#### 20d

| Bucket | Count | Average Return | Median Return | Win Rate |
|---|---:|---:|---:|---:|
| bucket_1 | 39350 | 0.0112 | 0.0030 | 0.5152 |
| bucket_2 | 39349 | -0.0025 | -0.0081 | 0.4572 |
| bucket_3 | 39349 | -0.0016 | -0.0073 | 0.4580 |
| bucket_4 | 39349 | -0.0052 | -0.0106 | 0.4380 |
| bucket_5 | 39349 | -0.0093 | -0.0153 | 0.4180 |

#### 60d

| Bucket | Count | Average Return | Median Return | Win Rate |
|---|---:|---:|---:|---:|
| bucket_1 | 35886 | -0.0083 | -0.0285 | 0.4150 |
| bucket_2 | 35885 | -0.0094 | -0.0244 | 0.4287 |
| bucket_3 | 35885 | -0.0039 | -0.0149 | 0.4543 |
| bucket_4 | 35885 | -0.0208 | -0.0333 | 0.3989 |
| bucket_5 | 35885 | -0.0220 | -0.0396 | 0.3877 |

### sector_return_1m

#### 5d

| Bucket | Count | Average Return | Median Return | Win Rate |
|---|---:|---:|---:|---:|
| bucket_1 | 40649 | 0.0039 | 0.0007 | 0.5056 |
| bucket_2 | 40648 | -0.0020 | -0.0034 | 0.4553 |
| bucket_3 | 40648 | -0.0018 | -0.0034 | 0.4546 |
| bucket_4 | 40648 | -0.0013 | -0.0036 | 0.4546 |
| bucket_5 | 40648 | -0.0006 | -0.0030 | 0.4647 |

#### 10d

| Bucket | Count | Average Return | Median Return | Win Rate |
|---|---:|---:|---:|---:|
| bucket_1 | 40216 | 0.0080 | 0.0019 | 0.5111 |
| bucket_2 | 40215 | -0.0033 | -0.0066 | 0.4451 |
| bucket_3 | 40215 | -0.0065 | -0.0101 | 0.4213 |
| bucket_4 | 40215 | -0.0034 | -0.0068 | 0.4434 |
| bucket_5 | 40215 | 0.0026 | -0.0017 | 0.4836 |

#### 20d

| Bucket | Count | Average Return | Median Return | Win Rate |
|---|---:|---:|---:|---:|
| bucket_1 | 39350 | 0.0154 | 0.0089 | 0.5375 |
| bucket_2 | 39349 | -0.0059 | -0.0113 | 0.4370 |
| bucket_3 | 39349 | -0.0131 | -0.0180 | 0.3988 |
| bucket_4 | 39349 | -0.0095 | -0.0147 | 0.4222 |
| bucket_5 | 39349 | 0.0057 | -0.0009 | 0.4907 |

#### 60d

| Bucket | Count | Average Return | Median Return | Win Rate |
|---|---:|---:|---:|---:|
| bucket_1 | 35886 | 0.0162 | -0.0008 | 0.4915 |
| bucket_2 | 35885 | -0.0211 | -0.0378 | 0.3887 |
| bucket_3 | 35885 | -0.0337 | -0.0476 | 0.3620 |
| bucket_4 | 35885 | -0.0250 | -0.0373 | 0.3884 |
| bucket_5 | 35885 | -0.0008 | -0.0145 | 0.4541 |

### sector_return_3m

#### 5d

| Bucket | Count | Average Return | Median Return | Win Rate |
|---|---:|---:|---:|---:|
| bucket_1 | 37011 | 0.0067 | 0.0023 | 0.5178 |
| bucket_2 | 37011 | -0.0013 | -0.0021 | 0.4689 |
| bucket_3 | 37011 | -0.0039 | -0.0050 | 0.4388 |
| bucket_4 | 37011 | -0.0047 | -0.0063 | 0.4273 |
| bucket_5 | 37011 | -0.0008 | -0.0034 | 0.4574 |

#### 10d

| Bucket | Count | Average Return | Median Return | Win Rate |
|---|---:|---:|---:|---:|
| bucket_1 | 36578 | 0.0117 | 0.0066 | 0.5328 |
| bucket_2 | 36578 | -0.0050 | -0.0075 | 0.4426 |
| bucket_3 | 36578 | -0.0062 | -0.0089 | 0.4309 |
| bucket_4 | 36578 | -0.0074 | -0.0112 | 0.4122 |
| bucket_5 | 36578 | -0.0012 | -0.0053 | 0.4509 |

#### 20d

| Bucket | Count | Average Return | Median Return | Win Rate |
|---|---:|---:|---:|---:|
| bucket_1 | 35712 | 0.0169 | 0.0111 | 0.5423 |
| bucket_2 | 35712 | -0.0077 | -0.0129 | 0.4347 |
| bucket_3 | 35712 | -0.0098 | -0.0136 | 0.4261 |
| bucket_4 | 35712 | -0.0097 | -0.0146 | 0.4179 |
| bucket_5 | 35712 | -0.0069 | -0.0110 | 0.4302 |

#### 60d

| Bucket | Count | Average Return | Median Return | Win Rate |
|---|---:|---:|---:|---:|
| bucket_1 | 32248 | 0.0416 | 0.0278 | 0.5603 |
| bucket_2 | 32248 | -0.0256 | -0.0391 | 0.3942 |
| bucket_3 | 32248 | -0.0278 | -0.0385 | 0.3870 |
| bucket_4 | 32248 | -0.0275 | -0.0394 | 0.3821 |
| bucket_5 | 32248 | -0.0187 | -0.0289 | 0.3953 |

### sector_return_6m

#### 5d

| Bucket | Count | Average Return | Median Return | Win Rate |
|---|---:|---:|---:|---:|
| bucket_1 | 31556 | 0.0063 | 0.0015 | 0.5117 |
| bucket_2 | 31555 | -0.0027 | -0.0055 | 0.4391 |
| bucket_3 | 31555 | -0.0022 | -0.0043 | 0.4459 |
| bucket_4 | 31555 | -0.0017 | -0.0031 | 0.4578 |
| bucket_5 | 31555 | -0.0031 | -0.0038 | 0.4516 |

#### 10d

| Bucket | Count | Average Return | Median Return | Win Rate |
|---|---:|---:|---:|---:|
| bucket_1 | 31123 | 0.0130 | 0.0074 | 0.5388 |
| bucket_2 | 31122 | -0.0041 | -0.0081 | 0.4429 |
| bucket_3 | 31122 | -0.0052 | -0.0082 | 0.4327 |
| bucket_4 | 31122 | -0.0029 | -0.0061 | 0.4481 |
| bucket_5 | 31122 | -0.0050 | -0.0070 | 0.4367 |

#### 20d

| Bucket | Count | Average Return | Median Return | Win Rate |
|---|---:|---:|---:|---:|
| bucket_1 | 30257 | 0.0301 | 0.0241 | 0.5942 |
| bucket_2 | 30256 | -0.0052 | -0.0079 | 0.4568 |
| bucket_3 | 30256 | -0.0085 | -0.0127 | 0.4274 |
| bucket_4 | 30256 | -0.0090 | -0.0131 | 0.4196 |
| bucket_5 | 30256 | -0.0127 | -0.0145 | 0.4133 |

#### 60d

| Bucket | Count | Average Return | Median Return | Win Rate |
|---|---:|---:|---:|---:|
| bucket_1 | 26796 | 0.0779 | 0.0646 | 0.6601 |
| bucket_2 | 26796 | 0.0084 | -0.0072 | 0.4744 |
| bucket_3 | 26795 | -0.0130 | -0.0237 | 0.4197 |
| bucket_4 | 26795 | -0.0347 | -0.0445 | 0.3562 |
| bucket_5 | 26795 | -0.0221 | -0.0317 | 0.4057 |

## Interpretation Notes

- Positive spread means the highest factor quintile outperformed the lowest factor quintile.
- For `rank_3m`, lower ranks are stronger sectors, so a negative spread can still indicate leadership strength.
- Monotonicity is the share of adjacent bucket steps where average return increases from lower to higher factor values.
- These results are research inputs only. V2 scoring should wait for the separate proposal step.
