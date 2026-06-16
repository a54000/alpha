from datetime import date

from sqlalchemy import create_engine, event, inspect
from sqlalchemy.exc import IntegrityError

from db.base import Base
from db.models import (  # noqa: F401
    BacktestRuns,
    DataQualityLog,
    DailyScores,
    FeaturesDaily,
    ModelVersion,
    PaperDailySnapshot,
    PaperPortfolio,
    PaperPosition,
    PaperTrade,
    PortfolioPositions,
    PricesDaily,
    RecommendationHistory,
    RecommendationDecisionJournal,
    SectorDaily,
    SecurityCorporateActionLineage,
    SecurityMaster,
    SecuritySymbolAlias,
    SymbolMaster,
    TradeLog,
    UniverseSnapshot,
)


def build_sqlite_engine():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    
    @event.listens_for(engine, "connect")
    def enable_sqlite_foreign_keys(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    return engine


def test_all_expected_tables_exist():
    engine = build_sqlite_engine()
    Base.metadata.create_all(engine)
    table_names = set(inspect(engine).get_table_names())

    expected = {
        "symbol_master",
        "prices_daily",
        "features_daily",
        "daily_scores",
        "recommendation_history",
        "recommendation_decision_journal",
        "sector_daily",
        "portfolio_positions",
        "trade_log",
        "backtest_runs",
        "model_version",
        "universe_snapshot",
        "pipeline_runs",
        "data_quality_log",
        "security_master",
        "security_symbol_alias",
        "security_corporate_action_lineage",
        "paper_portfolios",
        "paper_positions",
        "paper_trades",
        "paper_daily_snapshots",
    }

    assert expected.issubset(table_names)


def test_unique_constraints_work():
    engine = build_sqlite_engine()
    Base.metadata.create_all(engine)

    with engine.begin() as connection:
        connection.execute(SymbolMaster.__table__.insert(), [{"symbol": "ABC"}])
        connection.execute(PricesDaily.__table__.insert(), [{"symbol": "ABC", "date": date(2024, 1, 1)}])

        try:
            connection.execute(PricesDaily.__table__.insert(), [{"symbol": "ABC", "date": date(2024, 1, 1)}])
        except IntegrityError:
            pass
        else:
            raise AssertionError("duplicate prices_daily row should fail")


def test_foreign_keys_work():
    engine = build_sqlite_engine()
    Base.metadata.create_all(engine)

    with engine.begin() as connection:
        connection.execute(SymbolMaster.__table__.insert(), [{"symbol": "ABC"}])
        connection.execute(ModelVersion.__table__.insert(), [{"version_tag": "v1.0", "model": "swing", "weights_json": {}}])
        model_version_id = connection.execute(ModelVersion.__table__.select()).first()[0]
        connection.execute(DailyScores.__table__.insert(), [{"symbol": "ABC", "date": date(2024, 1, 1), "model_version_id": model_version_id}])

        try:
            connection.execute(DailyScores.__table__.insert(), [{"symbol": "ZZZ", "date": date(2024, 1, 2), "model_version_id": model_version_id}])
        except IntegrityError:
            pass
        else:
            raise AssertionError("missing symbol foreign key should fail")


def test_security_alias_and_lineage_constraints_work():
    engine = build_sqlite_engine()
    Base.metadata.create_all(engine)

    with engine.begin() as connection:
        result = connection.execute(
            SecurityMaster.__table__.insert().returning(SecurityMaster.security_id),
            [{"canonical_symbol": "ABC"}],
        )
        security_id = result.scalar_one()

        connection.execute(
            SecuritySymbolAlias.__table__.insert(),
            [
                {
                    "security_id": security_id,
                    "source": "research",
                    "symbol": "ABC",
                    "normalized_symbol": "ABC",
                    "alias_reason": "exact",
                }
            ],
        )
        connection.execute(
            SecurityCorporateActionLineage.__table__.insert(),
            [{"event_type": "rename", "from_security_id": security_id}],
        )

        try:
            connection.execute(
                SecuritySymbolAlias.__table__.insert(),
                [
                    {
                        "security_id": 9999,
                        "source": "research",
                        "symbol": "ZZZ",
                        "normalized_symbol": "ZZZ",
                        "alias_reason": "exact",
                    }
                ],
            )
        except IntegrityError:
            pass
        else:
            raise AssertionError("missing security_master foreign key should fail")

        try:
            connection.execute(SecurityCorporateActionLineage.__table__.insert(), [{"event_type": "rename"}])
        except IntegrityError:
            pass
        else:
            raise AssertionError("lineage row without from/to security should fail")
