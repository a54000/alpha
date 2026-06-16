"""Read-only stock analysis service for the cockpit."""

from __future__ import annotations

import os
from datetime import date
from urllib.parse import urlsplit, urlunsplit

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


FINAL_MODEL = "sector_rotation_adx_1m3m"


class StockAnalysisError(RuntimeError):
    """Raised when stock analysis data cannot be loaded."""


def derive_angel_url(research_database_url: str | None, database_name: str = "angel_data") -> str | None:
    if not research_database_url:
        return None
    parts = urlsplit(research_database_url)
    return urlunsplit((parts.scheme, parts.netloc, f"/{database_name}", parts.query, parts.fragment))


def make_engine(database_url: str) -> Engine:
    kwargs: dict[str, object] = {"future": True, "pool_pre_ping": True}
    if not database_url.startswith("sqlite"):
        kwargs.update({"pool_size": 1, "max_overflow": 0})
    return create_engine(database_url, **kwargs)


class StockAnalysisService:
    def __init__(
        self,
        angel_database_url: str | None = None,
        pilot_schema: str = "pilot_phase2a",
        angel_engine: Engine | None = None,
    ) -> None:
        research_url = os.environ.get("DATABASE_URL")
        self.angel_database_url = angel_database_url or os.environ.get("ANGEL_DATABASE_URL") or derive_angel_url(research_url)
        self.pilot_schema = pilot_schema
        self.angel_engine = angel_engine or (make_engine(self.angel_database_url) if self.angel_database_url else None)

    def _require_engine(self) -> Engine:
        if self.angel_engine is None:
            raise StockAnalysisError("ANGEL_DATABASE_URL is required for stock analysis.")
        return self.angel_engine

    def search_symbols(self, query: str, limit: int = 20) -> dict[str, object]:
        engine = self._require_engine()
        term = query.strip().upper()
        if len(term) < 3:
            return {"query": term, "symbols": []}
        sql = text(
            f"""
            SELECT
                universe.symbol,
                MAX(universe.sector) AS sector,
                MAX(universe.latest_date) AS latest_date
            FROM (
                SELECT symbol, MAX(sector) AS sector, MAX(date) AS latest_date
                FROM {self.pilot_schema}.features_daily
                WHERE symbol ILIKE :pattern
                GROUP BY symbol
                UNION ALL
                SELECT symbol, MAX(sector) AS sector, MAX(date) AS latest_date
                FROM {self.pilot_schema}.recommendations_daily
                WHERE symbol ILIKE :pattern
                GROUP BY symbol
                UNION ALL
                SELECT symbol, NULL::text AS sector, MAX(date) AS latest_date
                FROM {self.pilot_schema}.daily_bars_clean
                WHERE symbol ILIKE :pattern
                GROUP BY symbol
            ) universe
            GROUP BY universe.symbol
            ORDER BY
                CASE WHEN universe.symbol ILIKE :prefix THEN 0 ELSE 1 END,
                universe.symbol ASC
            LIMIT :limit
            """
        )
        with engine.connect() as connection:
            rows = connection.execute(sql, {"pattern": f"%{term}%", "prefix": f"{term}%", "limit": limit}).mappings().all()
        return {
            "query": term,
            "symbols": [
                {
                    "symbol": row["symbol"],
                    "sector": row["sector"],
                    "latest_date": row["latest_date"].isoformat() if hasattr(row["latest_date"], "isoformat") else row["latest_date"],
                }
                for row in rows
            ],
        }

    def dashboard(self, symbol: str) -> dict[str, object]:
        engine = self._require_engine()
        normalized = symbol.strip().upper()
        if not normalized:
            raise StockAnalysisError("symbol is required.")
        with engine.connect() as connection:
            latest_bar = connection.execute(
                text(
                    f"""
                    SELECT symbol, date, open, high, low, close, volume
                    FROM {self.pilot_schema}.daily_bars_clean
                    WHERE symbol = :symbol
                    ORDER BY date DESC
                    LIMIT 1
                    """
                ),
                {"symbol": normalized},
            ).mappings().first()
            if latest_bar is None:
                raise StockAnalysisError(f"No stock data found for {normalized}.")

            latest_feature = connection.execute(
                text(
                    f"""
                    SELECT *
                    FROM {self.pilot_schema}.features_daily
                    WHERE symbol = :symbol
                    ORDER BY date DESC
                    LIMIT 1
                    """
                ),
                {"symbol": normalized},
            ).mappings().first()

            latest_recommendation = connection.execute(
                text(
                    f"""
                    SELECT date, model, rank, score, sector
                    FROM {self.pilot_schema}.recommendations_daily
                    WHERE symbol = :symbol
                      AND model = :model
                    ORDER BY date DESC
                    LIMIT 1
                    """
                ),
                {"symbol": normalized, "model": FINAL_MODEL},
            ).mappings().first()

            recent_bars = connection.execute(
                text(
                    f"""
                    SELECT date, open, high, low, close, volume
                    FROM {self.pilot_schema}.daily_bars_clean
                    WHERE symbol = :symbol
                    ORDER BY date DESC
                    LIMIT 60
                    """
                ),
                {"symbol": normalized},
            ).mappings().all()

        bars = [
            {
                "date": row["date"].isoformat() if hasattr(row["date"], "isoformat") else row["date"],
                "open": float(row["open"]) if row["open"] is not None else None,
                "high": float(row["high"]) if row["high"] is not None else None,
                "low": float(row["low"]) if row["low"] is not None else None,
                "close": float(row["close"]) if row["close"] is not None else None,
                "volume": int(row["volume"]) if row["volume"] is not None else None,
            }
            for row in reversed(recent_bars)
        ]
        feature = dict(latest_feature or {})
        recommendation = dict(latest_recommendation or {})
        return {
            "symbol": normalized,
            "latest_bar": self._serialize_mapping(latest_bar),
            "latest_features": self._serialize_mapping(feature),
            "latest_recommendation": self._serialize_mapping(recommendation),
            "recent_bars": bars,
            "summary": self._summary(latest_bar, feature, recommendation),
        }

    def _summary(self, latest_bar: dict[str, object], feature: dict[str, object], recommendation: dict[str, object]) -> dict[str, object]:
        close = latest_bar.get("close")
        ema_200 = feature.get("ema_200")
        return {
            "sector": feature.get("sector") or recommendation.get("sector"),
            "latest_date": latest_bar.get("date"),
            "close": close,
            "ema_200": ema_200,
            "ema200_extension": feature.get("ema200_extension"),
            "adx_14": feature.get("adx_14"),
            "prior_20d_return": feature.get("prior_20d_return"),
            "sector_rank_3m": feature.get("sector_rank_3m"),
            "last_recommended_date": recommendation.get("date"),
            "last_rank": recommendation.get("rank"),
            "last_score": recommendation.get("score"),
            "above_ema200": bool(close is not None and ema_200 is not None and float(close) > float(ema_200)),
        }

    def _serialize_mapping(self, row: object) -> dict[str, object]:
        if not row:
            return {}
        payload: dict[str, object] = {}
        for key, value in dict(row).items():
            if isinstance(value, date):
                payload[key] = value.isoformat()
            elif hasattr(value, "__float__"):
                try:
                    payload[key] = float(value)
                except (TypeError, ValueError):
                    payload[key] = value
            else:
                payload[key] = value
        return payload
