"""Daily recommendation generation from scored universe.

Reads:
  - `daily_scores`
  - `features_daily`

Writes:
  - `recommendation_history`

Does not:
  - Run backtests
  - Generate long-term recommendations
  - Modify dashboard or external APIs
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, timedelta
from pathlib import Path
import json
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from db.models import DailyScores, FeaturesDaily, RecommendationHistory


@dataclass(frozen=True)
class RecommendationConfig:
    recommendation_type: str
    score_field: str
    minimum_score: float
    top_n: int = 20


SWING_RECOMMENDATION_CONFIG = RecommendationConfig(
    recommendation_type="swing",
    score_field="swing_score",
    minimum_score=70.0,
)

POSITIONAL_RECOMMENDATION_CONFIG = RecommendationConfig(
    recommendation_type="positional",
    score_field="position_score",
    minimum_score=65.0,
)

SWING_V2_RECOMMENDATION_CONFIG = RecommendationConfig(
    recommendation_type="swing_v2",
    score_field="swing_v2_score",
    minimum_score=70.0,
)

SWING_V2_1_RECOMMENDATION_CONFIG = RecommendationConfig(
    recommendation_type="swing_v2_1",
    score_field="swing_v2_1_score",
    minimum_score=70.0,
)

POSITIONAL_V2_RECOMMENDATION_CONFIG = RecommendationConfig(
    recommendation_type="positional_v2",
    score_field="position_v2_score",
    minimum_score=65.0,
)


@dataclass(frozen=True)
class RecommendationGenerationReport:
    dates_processed: int
    swing_recommendations: int
    positional_recommendations: int
    rows_written: int
    failures: list[str]


def write_recommendation_report(report: RecommendationGenerationReport, output_path: str | Path) -> Path:
    path = Path(output_path)
    path.write_text(json.dumps(asdict(report), indent=2, sort_keys=True), encoding="utf-8")
    return path


def rank_recommendations(
    candidates: list[tuple[str, float, int | None]],
    *,
    minimum_score: float,
    top_n: int,
) -> list[tuple[str, float, int | None]]:
    """Return up to top_n symbols ordered by score desc, symbol asc for ties."""
    qualified = [(symbol, score, version_id) for symbol, score, version_id in candidates if score >= minimum_score]
    qualified.sort(key=lambda item: (-item[1], item[0]))
    return qualified[:top_n]


class RecommendationGenerator:
    def __init__(self, session_factory):
        self.session_factory = session_factory

    def generate(
        self,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> RecommendationGenerationReport:
        return self._generate_for_configs(
            (SWING_RECOMMENDATION_CONFIG, POSITIONAL_RECOMMENDATION_CONFIG),
            start_date,
            end_date,
        )

    def generate_v2(
        self,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> RecommendationGenerationReport:
        return self._generate_for_configs(
            (SWING_V2_RECOMMENDATION_CONFIG, POSITIONAL_V2_RECOMMENDATION_CONFIG),
            start_date,
            end_date,
        )

    def generate_swing_v2_1(
        self,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> RecommendationGenerationReport:
        return self._generate_for_configs(
            (SWING_V2_1_RECOMMENDATION_CONFIG,),
            start_date,
            end_date,
        )

    def _generate_for_configs(
        self,
        configs: tuple[RecommendationConfig, ...],
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> RecommendationGenerationReport:
        failures: list[str] = []
        rows_written = 0
        dates_processed = 0
        swing_recommendations = 0
        positional_recommendations = 0

        with self.session_factory() as session:
            if end_date is None:
                end_date = session.execute(select(DailyScores.date).order_by(DailyScores.date.desc())).scalars().first()
            if start_date is None:
                existing_latest = session.execute(
                    select(RecommendationHistory.date).order_by(RecommendationHistory.date.desc())
                ).scalars().first()
                if existing_latest is not None:
                    start_date = existing_latest + timedelta(days=1)
                else:
                    start_date = session.execute(select(DailyScores.date).order_by(DailyScores.date.asc())).scalars().first()

            if start_date is None or end_date is None:
                return RecommendationGenerationReport(0, 0, 0, 0, failures)

            for current_date in self._date_range(start_date, end_date):
                try:
                    candidates = self._load_candidates(session, current_date)
                    if not candidates:
                        continue

                    date_written = 0
                    for config in configs:
                        if self._has_existing_recommendations(session, current_date, config.recommendation_type):
                            continue
                        scored: list[tuple[str, float, int | None]] = []
                        for candidate in candidates:
                            symbol = candidate["symbol"]
                            score = candidate[config.score_field]
                            model_version_id = candidate["model_version_id"]
                            if score is None:
                                continue
                            scored.append((symbol, score, model_version_id))
                        ranked = rank_recommendations(
                            scored,
                            minimum_score=config.minimum_score,
                            top_n=config.top_n,
                        )
                        written = self._persist_recommendations(
                            session,
                            current_date,
                            config.recommendation_type,
                            ranked,
                        )
                        date_written += written
                        if config.recommendation_type in ("swing", "swing_v2", "swing_v2_1"):
                            swing_recommendations += len(ranked)
                        else:
                            positional_recommendations += len(ranked)
                    if date_written:
                        dates_processed += 1
                        rows_written += date_written
                except Exception as exc:  # pragma: no cover - surfaced in report
                    failures.append(f"{current_date}: {exc}")
            session.commit()

        return RecommendationGenerationReport(
            dates_processed=dates_processed,
            swing_recommendations=swing_recommendations,
            positional_recommendations=positional_recommendations,
            rows_written=rows_written,
            failures=failures,
        )

    def _load_candidates(
        self, session, current_date: date
    ) -> list[dict[str, float | int | str | bool | None]]:
        rows = session.execute(
            select(
                DailyScores.symbol,
                DailyScores.swing_score,
                DailyScores.position_score,
                DailyScores.swing_v2_score,
                DailyScores.swing_v2_1_score,
                DailyScores.position_v2_score,
                DailyScores.model_version_id,
                FeaturesDaily.is_eligible,
            )
            .join(
                FeaturesDaily,
                (DailyScores.symbol == FeaturesDaily.symbol) & (DailyScores.date == FeaturesDaily.date),
            )
            .where(DailyScores.date == current_date)
        ).all()
        return [
            {
                "symbol": row.symbol,
                "swing_score": float(row.swing_score) if row.swing_score is not None else None,
                "position_score": float(row.position_score) if row.position_score is not None else None,
                "swing_v2_score": float(row.swing_v2_score) if row.swing_v2_score is not None else None,
                "swing_v2_1_score": float(row.swing_v2_1_score) if row.swing_v2_1_score is not None else None,
                "position_v2_score": float(row.position_v2_score) if row.position_v2_score is not None else None,
                "model_version_id": row.model_version_id,
                "is_eligible": row.is_eligible,
            }
            for row in rows
            if row.is_eligible is not False
        ]

    def _has_existing_recommendations(self, session, current_date: date, recommendation_type: str) -> bool:
        existing = session.execute(
            select(RecommendationHistory.id)
            .where(
                RecommendationHistory.date == current_date,
                RecommendationHistory.model == recommendation_type,
            )
            .limit(1)
        ).scalar_one_or_none()
        return existing is not None

    def _persist_recommendations(
        self,
        session,
        current_date: date,
        recommendation_type: str,
        ranked: list[tuple[str, float, int | None]],
    ) -> int:
        written = 0
        dialect_name = session.bind.dialect.name if session.bind else "sqlite"
        for rank, (symbol, score, model_version_id) in enumerate(ranked, start=1):
            payload = {
                "date": current_date,
                "model": recommendation_type,
                "rank": rank,
                "symbol": symbol,
                "score": score,
                "model_version_id": model_version_id,
            }
            existing = session.execute(
                select(RecommendationHistory).where(
                    RecommendationHistory.date == current_date,
                    RecommendationHistory.model == recommendation_type,
                    RecommendationHistory.symbol == symbol,
                )
            ).scalar_one_or_none()
            if existing is not None:
                continue

            insert_stmt = RecommendationHistory.__table__.insert().values(**payload)
            if dialect_name == "postgresql":
                insert_stmt = pg_insert(RecommendationHistory.__table__).values(**payload).on_conflict_do_nothing(
                    index_elements=["date", "model", "symbol"]
                )
            elif dialect_name == "sqlite":
                insert_stmt = sqlite_insert(RecommendationHistory.__table__).values(**payload).prefix_with("OR IGNORE")
            result = session.execute(insert_stmt)
            written += int(getattr(result, "rowcount", 1) or 0)
        return written

    def _date_range(self, start_date: date, end_date: date) -> Iterable[date]:
        current = start_date
        while current <= end_date:
            yield current
            current += timedelta(days=1)
