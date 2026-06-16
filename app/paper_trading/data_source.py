"""Configurable read sources for paper trading.

The adapters only supply recommendations, prices, symbol trading dates, and
sectors. Portfolio lifecycle and accounting remain in PaperTradingService.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date
from types import SimpleNamespace
from urllib.parse import urlsplit, urlunsplit

from sqlalchemy import bindparam, create_engine, select, text
from sqlalchemy.engine import Engine

from db.models import PricesDaily, RecommendationHistory, SymbolMaster


@dataclass(frozen=True)
class PaperTradingSourceConfig:
    name: str = "PRODUCTION"
    pilot_schema: str = "pilot_phase2a"
    angel_database_url: str | None = None


def derive_angel_url(research_database_url: str | None, database_name: str = "angel_data") -> str | None:
    if not research_database_url:
        return None
    parts = urlsplit(research_database_url)
    return urlunsplit((parts.scheme, parts.netloc, f"/{database_name}", parts.query, parts.fragment))


def normalize_source_name(value: str | None) -> str:
    normalized = (value or "production").strip().lower()
    if normalized in {"pilot_phase2a", "pilot", "phase2a"}:
        return "PILOT_PHASE2A"
    if normalized in {"production", "prod"}:
        return "PRODUCTION"
    raise ValueError(f"unsupported paper trading data source: {value}")


def source_config_from_env() -> PaperTradingSourceConfig:
    return PaperTradingSourceConfig(
        name=normalize_source_name(os.environ.get("PAPER_TRADING_DATA_SOURCE")),
        pilot_schema=os.environ.get("PAPER_TRADING_PILOT_SCHEMA", "pilot_phase2a"),
        angel_database_url=os.environ.get("ANGEL_DATABASE_URL") or derive_angel_url(os.environ.get("DATABASE_URL")),
    )


def make_engine(database_url: str) -> Engine:
    kwargs: dict[str, object] = {"future": True, "pool_pre_ping": True}
    if not database_url.startswith("sqlite"):
        kwargs.update({"pool_size": 1, "max_overflow": 0})
    return create_engine(database_url, **kwargs)


class PaperTradingDataSource:
    name = "PRODUCTION"

    def recommendations(self, session, signal_date: date, model: str, max_rank: int):
        raise NotImplementedError

    def price(self, session, symbol: str, price_date: date, field: str) -> float | None:
        raise NotImplementedError

    def intraday_price(self, session, symbol: str, price_date: date, bar_time: str, field: str) -> float | None:
        return None

    def daily_vwap(self, session, symbol: str, price_date: date) -> float | None:
        return None

    def next_trading_day_after(self, session, signal_date: date) -> date | None:
        raise NotImplementedError

    def next_intraday_trading_day_after(self, session, signal_date: date, bar_time: str) -> date | None:
        return self.next_trading_day_after(session, signal_date)

    def next_symbol_intraday_trading_day_after(self, session, symbol: str, signal_date: date, bar_time: str) -> date | None:
        return self.next_intraday_trading_day_after(session, signal_date, bar_time)

    def symbol_trading_dates(self, session, symbol: str, start_date: date) -> list[date]:
        raise NotImplementedError

    def sector(self, session, symbol: str) -> str | None:
        raise NotImplementedError


class ProductionPaperTradingDataSource(PaperTradingDataSource):
    name = "PRODUCTION"

    def recommendations(self, session, signal_date: date, model: str, max_rank: int):
        return list(
            session.execute(
                select(RecommendationHistory)
                .where(
                    RecommendationHistory.date == signal_date,
                    RecommendationHistory.model == model,
                    RecommendationHistory.rank <= max_rank,
                )
                .order_by(RecommendationHistory.rank.asc(), RecommendationHistory.symbol.asc())
            ).scalars()
        )

    def price(self, session, symbol: str, price_date: date, field: str) -> float | None:
        row = session.execute(
            select(PricesDaily.open, PricesDaily.close).where(
                PricesDaily.symbol == symbol,
                PricesDaily.date == price_date,
            )
        ).first()
        if row is None:
            return None
        value = row.open if field == "open" else row.close
        fallback = row.close if field == "open" else row.open
        return float(value if value is not None else fallback) if value is not None or fallback is not None else None

    def next_trading_day_after(self, session, signal_date: date) -> date | None:
        return session.execute(
            select(PricesDaily.date)
            .where(PricesDaily.date > signal_date)
            .order_by(PricesDaily.date.asc())
            .limit(1)
        ).scalar_one_or_none()

    def symbol_trading_dates(self, session, symbol: str, start_date: date) -> list[date]:
        return list(
            session.execute(
                select(PricesDaily.date)
                .where(PricesDaily.symbol == symbol, PricesDaily.date >= start_date)
                .order_by(PricesDaily.date.asc())
            ).scalars()
        )

    def sector(self, session, symbol: str) -> str | None:
        return session.execute(select(SymbolMaster.sector).where(SymbolMaster.symbol == symbol)).scalar_one_or_none()


class PilotPhase2APaperTradingDataSource(PaperTradingDataSource):
    name = "PILOT_PHASE2A"

    def __init__(self, engine: Engine, schema: str = "pilot_phase2a") -> None:
        self.engine = engine
        self.schema = schema

    def recommendations(self, session, signal_date: date, model: str, max_rank: int):
        with self.engine.connect() as connection:
            effective_signal_date = connection.execute(
                text(
                    f"""
                    SELECT MAX(date)
                    FROM {self.schema}.recommendations_daily
                    WHERE date <= :signal_date
                      AND model = :model
                    """
                ),
                {"signal_date": signal_date, "model": model},
            ).scalar_one_or_none()
            if effective_signal_date is None:
                return []
            rows = connection.execute(
                text(
                    f"""
                    SELECT date, model, rank, symbol, score, sector
                    FROM {self.schema}.recommendations_daily
                    WHERE date = :signal_date
                      AND model = :model
                      AND rank <= :max_rank
                    ORDER BY rank ASC, symbol ASC
                    """
                ),
                {"signal_date": effective_signal_date, "model": model, "max_rank": max_rank},
            ).mappings().all()
        return [
            SimpleNamespace(
                date=row["date"],
                model=row["model"],
                rank=int(row["rank"]),
                symbol=str(row["symbol"]),
                score=float(row["score"]) if row["score"] is not None else None,
                sector=row["sector"],
            )
            for row in rows
        ]

    def price(self, session, symbol: str, price_date: date, field: str) -> float | None:
        with self.engine.connect() as connection:
            row = connection.execute(
                text(
                    f"""
                    SELECT open, close
                    FROM {self.schema}.daily_bars_clean
                    WHERE symbol = :symbol AND date = :price_date
                    """
                ),
                {"symbol": symbol, "price_date": price_date},
            ).first()
        if row is None:
            return None
        value = row.open if field == "open" else row.close
        fallback = row.close if field == "open" else row.open
        return float(value if value is not None else fallback) if value is not None or fallback is not None else None

    def intraday_price(self, session, symbol: str, price_date: date, bar_time: str, field: str) -> float | None:
        allowed_fields = {"open", "high", "low", "close"}
        if field not in allowed_fields:
            raise ValueError(f"unsupported intraday price field: {field}")
        with self.engine.connect() as connection:
            value = connection.execute(
                text(
                    f"""
                    SELECT {field}
                    FROM ohlcv_15min
                    WHERE symbol = :symbol
                      AND datetime::date = :price_date
                      AND datetime::time = CAST(:bar_time AS time)
                    LIMIT 1
                    """
                ),
                {"symbol": symbol, "price_date": price_date, "bar_time": bar_time},
            ).scalar_one_or_none()
        return float(value) if value is not None else None

    def daily_vwap(self, session, symbol: str, price_date: date) -> float | None:
        with self.engine.connect() as connection:
            value = connection.execute(
                text(
                    """
                    SELECT SUM(((high + low + close) / 3.0) * volume) / NULLIF(SUM(volume), 0) AS daily_vwap
                    FROM ohlcv_15min
                    WHERE symbol = :symbol
                      AND datetime::date = :price_date
                      AND volume > 0
                    """
                ),
                {"symbol": symbol, "price_date": price_date},
            ).scalar_one_or_none()
        return float(value) if value is not None else None

    def next_trading_day_after(self, session, signal_date: date) -> date | None:
        with self.engine.connect() as connection:
            return connection.execute(
                text(
                    f"""
                    SELECT MIN(date)
                    FROM {self.schema}.daily_bars_clean
                    WHERE date > :signal_date
                    """
                ),
                {"signal_date": signal_date},
            ).scalar_one_or_none()

    def next_intraday_trading_day_after(self, session, signal_date: date, bar_time: str) -> date | None:
        with self.engine.connect() as connection:
            return connection.execute(
                text(
                    """
                    SELECT MIN(datetime::date)
                    FROM ohlcv_15min
                    WHERE datetime::date > :signal_date
                      AND datetime::time = CAST(:bar_time AS time)
                    """
                ),
                {"signal_date": signal_date, "bar_time": bar_time},
            ).scalar_one_or_none()

    def next_symbol_intraday_trading_day_after(self, session, symbol: str, signal_date: date, bar_time: str) -> date | None:
        with self.engine.connect() as connection:
            return connection.execute(
                text(
                    """
                    SELECT MIN(datetime::date)
                    FROM ohlcv_15min
                    WHERE symbol = :symbol
                      AND datetime::date > :signal_date
                      AND datetime::time = CAST(:bar_time AS time)
                    """
                ),
                {"symbol": symbol, "signal_date": signal_date, "bar_time": bar_time},
            ).scalar_one_or_none()

    def symbol_trading_dates(self, session, symbol: str, start_date: date) -> list[date]:
        with self.engine.connect() as connection:
            return list(
                connection.execute(
                    text(
                        f"""
                        SELECT date
                        FROM {self.schema}.daily_bars_clean
                        WHERE symbol = :symbol AND date >= :start_date
                        ORDER BY date ASC
                        """
                    ),
                    {"symbol": symbol, "start_date": start_date},
                ).scalars()
            )

    def sector(self, session, symbol: str) -> str | None:
        with self.engine.connect() as connection:
            return connection.execute(
                text(
                    f"""
                    SELECT sector
                    FROM {self.schema}.recommendations_daily
                    WHERE symbol = :symbol
                    ORDER BY date DESC
                    LIMIT 1
                    """
                ),
                {"symbol": symbol},
            ).scalar_one_or_none()


def build_data_source(config: PaperTradingSourceConfig | None = None) -> PaperTradingDataSource:
    config = config or source_config_from_env()
    if config.name == "PRODUCTION":
        return ProductionPaperTradingDataSource()
    if config.name == "PILOT_PHASE2A":
        if not config.angel_database_url:
            raise ValueError("ANGEL_DATABASE_URL is required for PILOT_PHASE2A paper trading data source.")
        return PilotPhase2APaperTradingDataSource(make_engine(config.angel_database_url), config.pilot_schema)
    raise ValueError(f"unsupported paper trading data source: {config.name}")
