from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker

from app.recommendations.generate_recommendations import (
    POSITIONAL_RECOMMENDATION_CONFIG,
    SWING_RECOMMENDATION_CONFIG,
    RecommendationGenerator,
    rank_recommendations,
)
from db.base import Base
from db.models import DailyScores, FeaturesDaily, ModelVersion, RecommendationHistory, SymbolMaster


def build_session_factory():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)

    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, future=True)


def seed_score_row(
    session,
    *,
    symbol: str,
    score_date: date,
    swing_score: float | None,
    position_score: float | None = None,
    is_eligible: bool = True,
    model_version_id: int | None = None,
):
    if session.get(SymbolMaster, symbol) is None:
        session.add(SymbolMaster(symbol=symbol))
        session.flush()
    session.add(
        FeaturesDaily(
            symbol=symbol,
            date=score_date,
            is_eligible=is_eligible,
        )
    )
    session.add(
        DailyScores(
            symbol=symbol,
            date=score_date,
            swing_score=swing_score,
            position_score=position_score,
            model_version_id=model_version_id,
        )
    )


def test_rank_recommendations_orders_by_score_desc():
    ranked = rank_recommendations(
        [("C", 80.0, 1), ("A", 90.0, 1), ("B", 85.0, 1)],
        minimum_score=65.0,
        top_n=20,
    )
    assert [item[0] for item in ranked] == ["A", "B", "C"]
    assert [item[1] for item in ranked] == [90.0, 85.0, 80.0]


def test_rank_recommendations_breaks_ties_by_symbol():
    ranked = rank_recommendations(
        [("B", 85.0, 1), ("A", 85.0, 1), ("C", 85.0, 1)],
        minimum_score=65.0,
        top_n=20,
    )
    assert [item[0] for item in ranked] == ["A", "B", "C"]
    assert all(item[1] == 85.0 for item in ranked)


def test_rank_recommendations_applies_minimum_score_filter():
    ranked = rank_recommendations(
        [("HIGH", 75.0, 1), ("LOW", 69.0, 1)],
        minimum_score=70.0,
        top_n=20,
    )
    assert ranked == [("HIGH", 75.0, 1)]


def test_rank_recommendations_caps_at_top_n():
    candidates = [(f"S{i:02d}", float(100 - i), 1) for i in range(30)]
    ranked = rank_recommendations(candidates, minimum_score=0.0, top_n=20)
    assert len(ranked) == 20
    assert ranked[0][1] == 100.0
    assert ranked[-1][1] == 81.0


def test_swing_minimum_score_and_ranking():
    factory = build_session_factory()
    score_date = date(2024, 6, 10)

    with factory() as session:
        session.add(ModelVersion(version_tag="v1.0", model="swing", weights_json={}, is_active=True))
        session.commit()
        model_version_id = session.execute(select(ModelVersion.version_id)).scalar_one()

        for symbol, score in [
            ("AAA", 95.0),
            ("BBB", 88.0),
            ("CCC", 72.0),
            ("DDD", 69.0),
            ("EEE", None),
        ]:
            seed_score_row(
                session,
                symbol=symbol,
                score_date=score_date,
                swing_score=score,
                position_score=50.0,
                model_version_id=model_version_id,
            )
        session.commit()

    generator = RecommendationGenerator(factory)
    report = generator.generate(start_date=score_date, end_date=score_date)

    assert report.swing_recommendations == 3
    with factory() as session:
        rows = session.execute(
            select(RecommendationHistory)
            .where(RecommendationHistory.date == score_date, RecommendationHistory.model == "swing")
            .order_by(RecommendationHistory.rank)
        ).scalars().all()
        assert len(rows) == 3
        assert [row.symbol for row in rows] == ["AAA", "BBB", "CCC"]
        assert [float(row.score) for row in rows] == [95.0, 88.0, 72.0]
        assert all(row.model_version_id == model_version_id for row in rows)


def test_positional_minimum_score_and_top_20_cap():
    factory = build_session_factory()
    score_date = date(2024, 6, 11)

    with factory() as session:
        session.add(ModelVersion(version_tag="v1.0", model="positional", weights_json={}, is_active=True))
        session.commit()
        model_version_id = session.execute(select(ModelVersion.version_id)).scalar_one()

        seed_score_row(
            session,
            symbol="LOW",
            score_date=score_date,
            swing_score=90.0,
            position_score=60.0,
            model_version_id=model_version_id,
        )
        for index in range(25):
            symbol = f"P{index:02d}"
            seed_score_row(
                session,
                symbol=symbol,
                score_date=score_date,
                swing_score=50.0,
                position_score=float(90 - index),
                model_version_id=model_version_id,
            )
        session.commit()

    report = RecommendationGenerator(factory).generate(start_date=score_date, end_date=score_date)

    assert report.positional_recommendations == 20
    with factory() as session:
        rows = session.execute(
            select(RecommendationHistory)
            .where(RecommendationHistory.date == score_date, RecommendationHistory.model == "positional")
            .order_by(RecommendationHistory.rank)
        ).scalars().all()
        assert len(rows) == 20
        assert float(rows[0].score) == 90.0
        assert float(rows[-1].score) == 71.0
        assert all(float(row.score) >= POSITIONAL_RECOMMENDATION_CONFIG.minimum_score for row in rows)


def test_excludes_ineligible_and_null_scores():
    factory = build_session_factory()
    score_date = date(2024, 6, 12)

    with factory() as session:
        session.add(ModelVersion(version_tag="v1.0", model="swing", weights_json={}, is_active=True))
        session.commit()
        model_version_id = session.execute(select(ModelVersion.version_id)).scalar_one()

        seed_score_row(
            session,
            symbol="GOOD",
            score_date=score_date,
            swing_score=80.0,
            model_version_id=model_version_id,
            is_eligible=True,
        )
        seed_score_row(
            session,
            symbol="BAD",
            score_date=score_date,
            swing_score=95.0,
            model_version_id=model_version_id,
            is_eligible=False,
        )
        seed_score_row(
            session,
            symbol="NULLS",
            score_date=score_date,
            swing_score=None,
            model_version_id=model_version_id,
            is_eligible=True,
        )
        session.commit()

    RecommendationGenerator(factory).generate(start_date=score_date, end_date=score_date)

    with factory() as session:
        rows = session.execute(
            select(RecommendationHistory).where(RecommendationHistory.date == score_date)
        ).scalars().all()
        assert len(rows) == 1
        assert rows[0].symbol == "GOOD"


def test_generate_is_idempotent():
    factory = build_session_factory()
    score_date = date(2024, 6, 13)

    with factory() as session:
        session.add(ModelVersion(version_tag="v1.0", model="swing", weights_json={}, is_active=True))
        session.commit()
        model_version_id = session.execute(select(ModelVersion.version_id)).scalar_one()
        seed_score_row(
            session,
            symbol="AAA",
            score_date=score_date,
            swing_score=80.0,
            position_score=70.0,
            model_version_id=model_version_id,
        )
        session.commit()

    generator = RecommendationGenerator(factory)
    first = generator.generate(start_date=score_date, end_date=score_date)
    second = generator.generate(start_date=score_date, end_date=score_date)

    assert first.rows_written == 2
    assert second.rows_written == 0

    with factory() as session:
        count = session.execute(
            select(RecommendationHistory).where(RecommendationHistory.date == score_date)
        ).scalars().all()
        assert len(count) == 2


@pytest.mark.parametrize(
    ("config", "field", "minimum"),
    [
        (SWING_RECOMMENDATION_CONFIG, "swing", 70.0),
        (POSITIONAL_RECOMMENDATION_CONFIG, "positional", 65.0),
    ],
)
def test_recommendation_configs(config, field, minimum):
    assert config.recommendation_type == field
    assert config.minimum_score == minimum
    assert config.top_n == 20
