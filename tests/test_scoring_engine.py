from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker

from app.scoring.compute_scores import ScoreComputer, compute_position_score, compute_swing_score
from db.base import Base
from db.models import DailyScores, FeaturesDaily, ModelVersion, PricesDaily, SectorDaily, SymbolMaster


def build_session_factory():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)

    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, future=True)


SWING_VALIDATION_EXAMPLES = [
    pytest.param(
        {
            "is_eligible": True,
            "adx_14": 36,
            "adx_prev": 35,
            "close": 110,
            "ema_5": 100,
            "ema_13": 90,
            "ema_20": 80,
            "rsi_14": 60,
            "macd_hist": 1.0,
            "macd_hist_prev": 0.5,
            "stoch_k": 65,
            "stoch_d": 60,
            "volume_ratio": 3.2,
            "pct_from_52w_high": -1,
            "bb_width": 0.65,
            "bb_width_20avg": 1.0,
            "rs_rank_pct": 92,
        },
        100.0,
        id="swing-1",
    ),
    pytest.param(
        {
            "is_eligible": True,
            "adx_14": 28,
            "adx_prev": 27,
            "close": 105,
            "ema_5": 106,
            "ema_13": 100,
            "ema_20": 95,
            "rsi_14": 52,
            "macd_hist": 1.0,
            "macd_hist_prev": 1.1,
            "stoch_k": 45,
            "stoch_d": 40,
            "volume_ratio": 2.1,
            "pct_from_52w_high": -4,
            "bb_width": 0.80,
            "bb_width_20avg": 1.0,
            "rs_rank_pct": 78,
        },
        65.0,
        id="swing-2",
    ),
    pytest.param(
        {
            "is_eligible": True,
            "adx_14": 10,
            "adx_prev": 12,
            "close": 50,
            "ema_5": 60,
            "ema_13": 70,
            "ema_20": 80,
            "rsi_14": 30,
            "macd_hist": -1.0,
            "macd_hist_prev": -0.5,
            "stoch_k": 20,
            "stoch_d": 30,
            "volume_ratio": 1.0,
            "pct_from_52w_high": -20,
            "bb_width": 1.2,
            "bb_width_20avg": 1.0,
            "rs_rank_pct": 20,
        },
        0.0,
        id="swing-3",
    ),
    pytest.param(
        {
            "is_eligible": True,
            "adx_14": 38,
            "adx_prev": 37,
            "close": 110,
            "ema_5": 100,
            "ema_13": 90,
            "ema_20": 80,
            "rsi_14": 40,
            "macd_hist": -1.0,
            "macd_hist_prev": -0.5,
            "volume_ratio": 1.0,
            "pct_from_52w_high": -20,
            "rs_rank_pct": 20,
        },
        30.0,
        id="swing-4",
    ),
    pytest.param(
        {
            "is_eligible": True,
            "adx_14": 22,
            "adx_prev": 21,
            "close": 105,
            "ema_13": 110,
            "ema_20": 100,
            "rsi_14": 62,
            "macd_hist": 1.0,
            "macd_hist_prev": 0.5,
            "stoch_k": 70,
            "stoch_d": 65,
            "volume_ratio": 1.6,
            "pct_from_52w_high": -8,
            "rs_rank_pct": 63,
        },
        53.0,
        id="swing-5",
    ),
    pytest.param(
        {
            "is_eligible": True,
            "adx_14": 26,
            "adx_prev": 27,
            "close": 105,
            "ema_13": 100,
            "ema_20": 95,
            "rsi_14": 78,
            "macd_hist": 1.0,
            "macd_hist_prev": 1.1,
            "stoch_k": 85,
            "stoch_d": 80,
            "volume_ratio": 1.3,
            "pct_from_52w_high": -4,
            "bb_width": 0.82,
            "bb_width_20avg": 1.0,
            "rs_rank_pct": 51,
        },
        35.0,
        id="swing-6",
    ),
    pytest.param(
        {
            "is_eligible": True,
            "adx_14": 27,
            "adx_prev": 26,
            "close": 110,
            "ema_5": 100,
            "ema_13": 90,
            "ema_20": 80,
            "rsi_14": 72,
            "macd_hist": -1.0,
            "macd_hist_prev": -1.5,
            "stoch_k": 40,
            "stoch_d": 45,
            "volume_ratio": 3.5,
            "pct_from_52w_high": -1.5,
            "bb_width": 0.65,
            "bb_width_20avg": 1.0,
            "rs_rank_pct": 91,
        },
        74.0,
        id="swing-7",
    ),
    pytest.param(
        {
            "is_eligible": True,
            "adx_14": 26,
            "adx_prev": 27,
            "close": 101,
            "ema_13": 105,
            "ema_20": 100,
            "rsi_14": 47,
            "macd_hist": -1.0,
            "macd_hist_prev": -1.5,
            "stoch_k": 40,
            "stoch_d": 35,
            "volume_ratio": 1.5,
            "pct_from_52w_high": -9,
            "rs_rank_pct": 76,
        },
        40.0,
        id="swing-8",
    ),
    pytest.param(
        {
            "is_eligible": True,
            "adx_14": 37,
            "adx_prev": 36,
            "close": 110,
            "ema_5": 100,
            "ema_13": 90,
            "ema_20": 80,
            "rsi_14": 61,
            "macd_hist": 1.0,
            "macd_hist_prev": 0.5,
            "stoch_k": 72,
            "stoch_d": 70,
            "volume_ratio": 2.0,
            "pct_from_52w_high": -4,
            "bb_width": 0.82,
            "bb_width_20avg": 1.0,
            "rs_rank_pct": 77,
        },
        88.0,
        id="swing-9",
    ),
    pytest.param(
        {
            "is_eligible": True,
            "adx_14": 40,
            "adx_prev": 39,
            "close": 110,
            "ema_5": 100,
            "ema_13": 90,
            "ema_20": 80,
            "rsi_14": 58,
            "macd_hist": 1.0,
            "macd_hist_prev": 0.5,
            "stoch_k": 60,
            "stoch_d": 55,
            "volume_ratio": 3.0,
            "pct_from_52w_high": -1,
            "bb_width": 1.0,
            "bb_width_20avg": 1.0,
            "rs_rank_pct": 95,
        },
        96.0,
        id="swing-10",
    ),
]


POSITIONAL_VALIDATION_EXAMPLES = [
    pytest.param(
        {
            "is_eligible": True,
            "close": 120,
            "ema_50": 110,
            "ema_150": 100,
            "ema_200": 90,
            "adx_14": 32,
            "adx_prev": 31,
            "rs_rank_pct": 88,
            "rs_vs_nifty_60d": 1.25,
            "volume_ratio": 2.5,
        },
        1,
        100.0,
        id="positional-1",
    ),
    pytest.param(
        {
            "is_eligible": True,
            "close": 110,
            "ema_50": 100,
            "ema_150": 105,
            "ema_200": 90,
            "adx_14": 26,
            "adx_prev": 25,
            "rs_rank_pct": 72,
            "rs_vs_nifty_60d": 1.12,
            "volume_ratio": 1.6,
        },
        3,
        66.0,
        id="positional-2",
    ),
    pytest.param(
        {
            "is_eligible": True,
            "close": 80,
            "ema_50": 90,
            "ema_150": 95,
            "ema_200": 100,
            "adx_14": 15,
            "adx_prev": 14,
            "rs_rank_pct": 40,
            "rs_vs_nifty_60d": 0.90,
            "volume_ratio": 1.0,
        },
        15,
        0.0,
        id="positional-3",
    ),
    pytest.param(
        {
            "is_eligible": True,
            "close": 120,
            "ema_50": 110,
            "ema_150": 100,
            "ema_200": 90,
            "adx_14": 31,
            "adx_prev": 30,
            "rs_rank_pct": 90,
            "rs_vs_nifty_60d": 1.22,
            "volume_ratio": 1.3,
        },
        11,
        74.0,
        id="positional-4",
    ),
    pytest.param(
        {
            "is_eligible": True,
            "close": 105,
            "ema_50": 110,
            "ema_150": 108,
            "ema_200": 100,
            "adx_14": 18,
            "adx_prev": 17,
            "rs_rank_pct": 58,
            "rs_vs_nifty_60d": 1.02,
            "volume_ratio": 1.0,
        },
        1,
        38.0,
        id="positional-5",
    ),
    pytest.param(
        {
            "is_eligible": True,
            "close": 110,
            "ema_50": 100,
            "ema_150": 105,
            "ema_200": 90,
            "adx_14": 33,
            "adx_prev": 32,
            "rs_rank_pct": 74,
            "rs_vs_nifty_60d": 1.05,
            "volume_ratio": 2.2,
        },
        5,
        67.0,
        id="positional-6",
    ),
    pytest.param(
        {
            "is_eligible": True,
            "close": 120,
            "ema_50": 110,
            "ema_150": 100,
            "ema_200": 90,
            "adx_14": 27,
            "adx_prev": 26,
            "rs_rank_pct": 57,
            "rs_vs_nifty_60d": 0.95,
            "volume_ratio": 1.7,
        },
        7,
        52.0,
        id="positional-7",
    ),
    pytest.param(
        {
            "is_eligible": True,
            "close": 105,
            "ema_50": 110,
            "ema_150": 108,
            "ema_200": 100,
            "adx_14": 17,
            "adx_prev": 16,
            "rs_rank_pct": 86,
            "rs_vs_nifty_60d": 1.21,
            "volume_ratio": 2.1,
        },
        2,
        65.0,
        id="positional-8",
    ),
    pytest.param(
        {
            "is_eligible": True,
            "close": 120,
            "ema_50": 110,
            "ema_150": 100,
            "ema_200": 90,
            "adx_14": 30,
            "adx_prev": 29,
            "rs_rank_pct": 87,
            "rs_vs_nifty_60d": 1.15,
            "volume_ratio": 1.25,
        },
        4,
        80.0,
        id="positional-9",
    ),
    pytest.param(
        {
            "is_eligible": True,
            "close": 110,
            "ema_50": 100,
            "ema_150": 105,
            "ema_200": 90,
            "adx_14": 21,
            "adx_prev": 20,
            "rs_rank_pct": 48,
            "rs_vs_nifty_60d": 1.11,
            "volume_ratio": 1.55,
        },
        8,
        40.0,
        id="positional-10",
    ),
]


@pytest.mark.parametrize(("features", "expected"), SWING_VALIDATION_EXAMPLES)
def test_swing_validation_examples(features, expected):
    assert compute_swing_score(features) == expected


@pytest.mark.parametrize(("features", "sector_rank", "expected"), POSITIONAL_VALIDATION_EXAMPLES)
def test_positional_validation_examples(features, sector_rank, expected):
    assert compute_position_score(features, sector_rank) == expected


def test_ineligible_stock_scores_are_null():
    features = {
        "is_eligible": False,
        "adx_14": 40,
        "adx_prev": 39,
        "close": 110,
        "ema_5": 100,
        "ema_13": 90,
        "ema_20": 80,
        "rsi_14": 60,
        "macd_hist": 1.0,
        "macd_hist_prev": 0.5,
        "stoch_k": 65,
        "stoch_d": 60,
        "volume_ratio": 3.2,
        "pct_from_52w_high": -1,
        "bb_width": 0.65,
        "bb_width_20avg": 1.0,
        "rs_rank_pct": 92,
    }
    assert compute_swing_score(features) is None
    assert compute_position_score(features, sector_3m_rank=1) is None


def test_null_feature_scores_zero_for_swing():
    assert compute_swing_score({"is_eligible": True}) == 0.0


def test_persists_daily_scores():
    factory = build_session_factory()
    score_date = date(2024, 6, 10)

    with factory() as session:
        session.add(SymbolMaster(symbol="TEST", sector="Defence"))
        session.add(
            ModelVersion(
                version_tag="v1.0",
                model="swing",
                weights_json={},
                is_active=True,
            )
        )
        session.commit()
        model_version_id = session.execute(select(ModelVersion.version_id)).scalar_one()

        session.add(
            PricesDaily(
                symbol="TEST",
                date=score_date,
                open=100,
                high=101,
                low=99,
                close=110,
                volume=1000,
            )
        )
        session.add(
            FeaturesDaily(
                symbol="TEST",
                date=score_date,
                sector="Defence",
                is_eligible=True,
                adx_14=36,
                adx_prev=35,
                ema_5=100,
                ema_13=90,
                ema_20=80,
                ema_50=95,
                ema_150=90,
                ema_200=85,
                rsi_14=60,
                macd_hist=1.0,
                macd_hist_prev=0.5,
                stoch_k=65,
                stoch_d=60,
                volume_ratio=3.2,
                pct_from_52w_high=-1,
                bb_width=0.65,
                bb_width_20avg=1.0,
                rs_rank_pct=92,
                rs_vs_nifty_60d=1.25,
            )
        )
        session.add(
            SectorDaily(
                date=score_date,
                sector="Defence",
                rank_3m=1,
            )
        )
        session.commit()

    computer = ScoreComputer(factory)
    report = computer.generate(start_date=score_date, end_date=score_date)

    assert report.rows_written == 1
    assert report.symbols_processed == 1

    with factory() as session:
        row = session.execute(select(DailyScores).where(DailyScores.symbol == "TEST")).scalar_one()
        assert row.date == score_date
        assert float(row.swing_score) == 100.0
        assert float(row.position_score) == 100.0
        assert row.model_version_id == model_version_id
        assert row.lt_score is None
