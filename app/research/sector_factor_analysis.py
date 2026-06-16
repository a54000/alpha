"""Sector factor research for testing sector leadership predictive power."""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Any

from sqlalchemy import select

from app.research.factor_analysis import FactorAnalyzer
from db.models import FeaturesDaily, SectorDaily
from db.session import build_session_factory


@dataclass(frozen=True)
class SectorFactorResult:
    """Research metrics for one sector factor and forward horizon."""

    factor_name: str
    horizon: str
    sample_size: int
    pearson_correlation: float | None
    spearman_ic: float | None
    average_return: float | None
    median_return: float | None
    top_bucket_return: float | None
    bottom_bucket_return: float | None
    bucket_spread: float | None
    monotonicity_score: float | None
    buckets: dict[str, dict[str, Any]]


class SectorFactorAnalyzer:
    """Analyze sector_daily factors against future stock returns."""

    FACTOR_COLUMNS = {
        "rank_3m": SectorDaily.rank_3m,
        "sector_return_1m": SectorDaily.sector_return_1m,
        "sector_return_3m": SectorDaily.sector_return_3m,
        "sector_return_6m": SectorDaily.sector_return_6m,
    }

    def __init__(self, session_factory=None):
        self.session_factory = session_factory or build_session_factory()
        self.factor_analyzer = FactorAnalyzer(self.session_factory)
        self._forward_return_cache: dict[tuple[str, date, str], float | None] = {}

    def run(
        self,
        factor_names: list[str],
        horizons: list[int],
        start_date: date,
        end_date: date,
    ) -> dict[str, dict[str, SectorFactorResult]]:
        """Run sector factor research for the requested factors and horizons."""

        unsupported = [name for name in factor_names if name not in self.FACTOR_COLUMNS]
        if unsupported:
            raise ValueError(
                f"Unsupported sector factor(s): {', '.join(unsupported)}. "
                f"Supported: {', '.join(self.FACTOR_COLUMNS)}"
            )

        results: dict[str, dict[str, SectorFactorResult]] = {}
        for factor_name in factor_names:
            results[factor_name] = {}
            rows = self._load_factor_rows(factor_name, start_date, end_date)
            for horizon in horizons:
                horizon_label = f"{horizon}d"
                factor_values: dict[str, float] = {}
                forward_returns: dict[str, float | None] = {}

                for symbol, signal_date, factor_value in rows:
                    if factor_value is None:
                        continue
                    key = f"{symbol}_{signal_date.isoformat()}"
                    factor_values[key] = float(factor_value)
                    forward_returns[key] = self._compute_forward_return(symbol, signal_date, horizon_label)

                summary = self.factor_analyzer.factor_summary(
                    factor_name,
                    factor_values,
                    forward_returns,
                )
                buckets = self._bucket_details(factor_values, forward_returns)
                bucket_spread = self._bucket_spread(summary.top_bucket_return, summary.bottom_bucket_return)

                results[factor_name][horizon_label] = SectorFactorResult(
                    factor_name=factor_name,
                    horizon=horizon_label,
                    sample_size=summary.sample_size,
                    pearson_correlation=summary.pearson_correlation,
                    spearman_ic=summary.spearman_ic,
                    average_return=summary.average_return,
                    median_return=summary.median_return,
                    top_bucket_return=summary.top_bucket_return,
                    bottom_bucket_return=summary.bottom_bucket_return,
                    bucket_spread=bucket_spread,
                    monotonicity_score=self._monotonicity_score(buckets),
                    buckets=buckets,
                )

        return results

    def write_outputs(
        self,
        results: dict[str, dict[str, SectorFactorResult]],
        report_path: Path,
        json_path: Path,
        start_date: date,
        end_date: date,
    ) -> None:
        """Write Markdown and JSON artifacts for Phase 6.5C."""

        json_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.parent.mkdir(parents=True, exist_ok=True)

        json_payload = {
            "phase": "6.5C",
            "research": "Sector Factor Research",
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "results": {
                factor: {horizon: asdict(result) for horizon, result in horizons.items()}
                for factor, horizons in results.items()
            },
        }
        json_path.write_text(json.dumps(json_payload, indent=2, sort_keys=True), encoding="utf-8")
        report_path.write_text(self._render_markdown(results, start_date, end_date, json_path), encoding="utf-8")

    def _load_factor_rows(self, factor_name: str, start_date: date, end_date: date) -> list[tuple[str, date, Any]]:
        factor_column = self.FACTOR_COLUMNS[factor_name]
        with self.session_factory() as session:
            return session.execute(
                select(
                    FeaturesDaily.symbol,
                    FeaturesDaily.date,
                    factor_column,
                )
                .join(
                    SectorDaily,
                    (SectorDaily.date == FeaturesDaily.date)
                    & (SectorDaily.sector == FeaturesDaily.sector),
                )
                .where(
                    FeaturesDaily.date >= start_date,
                    FeaturesDaily.date <= end_date,
                    FeaturesDaily.sector.is_not(None),
                )
                .order_by(FeaturesDaily.date.asc(), FeaturesDaily.symbol.asc())
            ).all()

    def _compute_forward_return(self, symbol: str, signal_date: date, horizon: str) -> float | None:
        cache_key = (symbol, signal_date, horizon)
        if cache_key not in self._forward_return_cache:
            self._forward_return_cache[cache_key] = self.factor_analyzer.compute_forward_returns(
                symbol,
                signal_date,
                horizon,
            )
        return self._forward_return_cache[cache_key]

    def _bucket_details(
        self,
        factor_values: dict[str, float],
        forward_returns: dict[str, float | None],
    ) -> dict[str, dict[str, Any]]:
        common_keys = sorted(set(factor_values) & set(forward_returns))
        clean_factor_values = []
        clean_forward_returns = []
        for key in common_keys:
            factor_value = factor_values[key]
            forward_return = forward_returns[key]
            if factor_value is None or forward_return is None:
                continue
            clean_factor_values.append(factor_value)
            clean_forward_returns.append(forward_return)

        return self.factor_analyzer.bucket_analysis(clean_factor_values, clean_forward_returns, num_buckets=5)

    @staticmethod
    def _bucket_spread(top_bucket_return: float | None, bottom_bucket_return: float | None) -> float | None:
        if top_bucket_return is None or bottom_bucket_return is None:
            return None
        return top_bucket_return - bottom_bucket_return

    @staticmethod
    def _monotonicity_score(buckets: dict[str, dict[str, Any]]) -> float | None:
        bucket_returns = [
            buckets[key]["average_return"]
            for key in sorted(buckets)
            if buckets[key].get("average_return") is not None
        ]
        if len(bucket_returns) < 2:
            return None

        comparisons = len(bucket_returns) - 1
        non_decreasing = sum(
            1
            for left, right in zip(bucket_returns, bucket_returns[1:])
            if right >= left
        )
        return non_decreasing / comparisons

    def _render_markdown(
        self,
        results: dict[str, dict[str, SectorFactorResult]],
        start_date: date,
        end_date: date,
        json_path: Path,
    ) -> str:
        lines = [
            "# Sector Factor Research",
            "",
            "**Phase:** 6.5C",
            f"**Date Range:** {start_date.isoformat()} to {end_date.isoformat()}",
            f"**JSON Results:** `{json_path.as_posix()}`",
            "",
            "## Scope",
            "",
            "This research tests whether sector leadership factors predict future stock returns.",
            "It does not modify scoring models, recommendations, or V2 implementation.",
            "",
            "## Method",
            "",
            "- Join `features_daily` to `sector_daily` on `(date, sector)`.",
            "- Assign each stock the sector factor value available on the signal date.",
            "- Compute stock forward returns at 5d, 10d, 20d, and 60d horizons.",
            "- Report Pearson correlation, Spearman IC, quintile buckets, monotonicity, and bucket spread.",
            "",
            "## Summary",
            "",
            "| Factor | Horizon | Sample | Pearson | Spearman IC | Bottom Bucket | Top Bucket | Spread | Monotonicity |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]

        for factor_name, horizons in results.items():
            for horizon, result in horizons.items():
                lines.append(
                    "| "
                    + " | ".join(
                        [
                            factor_name,
                            horizon,
                            str(result.sample_size),
                            self._fmt(result.pearson_correlation),
                            self._fmt(result.spearman_ic),
                            self._fmt(result.bottom_bucket_return),
                            self._fmt(result.top_bucket_return),
                            self._fmt(result.bucket_spread),
                            self._fmt(result.monotonicity_score),
                        ]
                    )
                    + " |"
                )

        lines.extend(["", "## Quintile Buckets", ""])
        for factor_name, horizons in results.items():
            lines.extend([f"### {factor_name}", ""])
            for horizon, result in horizons.items():
                lines.extend(
                    [
                        f"#### {horizon}",
                        "",
                        "| Bucket | Count | Average Return | Median Return | Win Rate |",
                        "|---|---:|---:|---:|---:|",
                    ]
                )
                for bucket_name, stats in result.buckets.items():
                    lines.append(
                        "| "
                        + " | ".join(
                            [
                                bucket_name,
                                str(stats["count"]),
                                self._fmt(stats["average_return"]),
                                self._fmt(stats["median_return"]),
                                self._fmt(stats["win_rate"]),
                            ]
                        )
                        + " |"
                    )
                lines.append("")

        lines.extend(
            [
                "## Interpretation Notes",
                "",
                "- Positive spread means the highest factor quintile outperformed the lowest factor quintile.",
                "- For `rank_3m`, lower ranks are stronger sectors, so a negative spread can still indicate leadership strength.",
                "- Monotonicity is the share of adjacent bucket steps where average return increases from lower to higher factor values.",
                "- These results are research inputs only. V2 scoring should wait for the separate proposal step.",
                "",
            ]
        )
        return "\n".join(lines)

    @staticmethod
    def _fmt(value: float | None) -> str:
        if value is None or (isinstance(value, float) and math.isnan(value)):
            return "N/A"
        return f"{value:.4f}"
