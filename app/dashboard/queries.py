"""Database queries for the Streamlit validation dashboard.

Reads:
  - PostgreSQL database via DATABASE_URL

Writes:
  - Nothing (read-only queries)

Does not:
  - Modify data
  - Implement caching
  - Handle authentication
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import Engine


@dataclass(frozen=True)
class PipelineStats:
    """Statistics about the pipeline data."""
    latest_pipeline_date: date | None
    total_symbols: int
    total_prices: int
    total_features: int
    total_sectors: int
    total_scores: int
    total_recommendations: int


@dataclass(frozen=True)
class RecommendationRow:
    """A single recommendation row."""
    rank: int
    symbol: str
    score: float | None
    sector: str | None
    model_version: str | None


@dataclass(frozen=True)
class SectorRow:
    """A single sector strength row."""
    sector: str
    sector_score: float | None
    rank_3m: int | None
    composite_rank: int | None
    stock_count: int | None


@dataclass(frozen=True)
class ScoreRow:
    """A single score row for the explorer."""
    symbol: str
    swing_score: float | None
    position_score: float | None
    sector: str | None


class DashboardQueries:
    """Read-only queries for the dashboard."""

    def __init__(self, database_url: str | None = None) -> None:
        """Initialize the query engine."""
        if database_url is None:
            from db.connection import get_database_url
            database_url = get_database_url()
        self.engine: Engine = create_engine(database_url, future=True)

    def get_pipeline_stats(self) -> PipelineStats:
        """Get overview statistics about the pipeline."""
        with self.engine.connect() as conn:
            # Get latest pipeline run date
            latest_pipeline = conn.execute(
                text("SELECT MAX(run_date) FROM pipeline_runs")
            ).scalar_one_or_none()

            # Get total symbols
            total_symbols = conn.execute(
                text("SELECT COUNT(*) FROM symbol_master")
            ).scalar_one()

            # Get total prices
            total_prices = conn.execute(
                text("SELECT COUNT(*) FROM prices_daily")
            ).scalar_one()

            # Get total features
            total_features = conn.execute(
                text("SELECT COUNT(*) FROM features_daily")
            ).scalar_one()

            # Get total sector records
            total_sectors = conn.execute(
                text("SELECT COUNT(*) FROM sector_daily")
            ).scalar_one()

            # Get total scores
            total_scores = conn.execute(
                text("SELECT COUNT(*) FROM daily_scores")
            ).scalar_one()

            # Get total recommendations
            total_recommendations = conn.execute(
                text("SELECT COUNT(*) FROM recommendation_history")
            ).scalar_one()

        return PipelineStats(
            latest_pipeline_date=latest_pipeline,
            total_symbols=total_symbols,
            total_prices=total_prices,
            total_features=total_features,
            total_sectors=total_sectors,
            total_scores=total_scores,
            total_recommendations=total_recommendations,
        )

    def get_latest_recommendation_date(self, model: str) -> date | None:
        """Get the latest date with recommendations for a given model."""
        with self.engine.connect() as conn:
            result = conn.execute(
                text("SELECT MAX(date) FROM recommendation_history WHERE model = :model"),
                {"model": model}
            ).scalar_one_or_none()
        return result

    def get_swing_recommendations(self, limit: int = 20) -> list[RecommendationRow]:
        """Get top N swing recommendations for the latest date."""
        with self.engine.connect() as conn:
            # Get latest date
            latest_date = self.get_latest_recommendation_date("swing")
            if latest_date is None:
                return []

            # Query recommendations with sector info
            query = text("""
                SELECT 
                    rh.rank,
                    rh.symbol,
                    rh.score,
                    sm.sector,
                    mv.version_tag as model_version
                FROM recommendation_history rh
                LEFT JOIN symbol_master sm ON rh.symbol = sm.symbol
                LEFT JOIN model_version mv ON rh.model_version_id = mv.version_id
                WHERE rh.model = 'swing'
                AND rh.date = :latest_date
                ORDER BY rh.rank ASC
                LIMIT :limit
            """)
            
            rows = conn.execute(query, {"latest_date": latest_date, "limit": limit}).fetchall()
            
            return [
                RecommendationRow(
                    rank=row.rank,
                    symbol=row.symbol,
                    score=float(row.score) if row.score is not None else None,
                    sector=row.sector,
                    model_version=row.model_version,
                )
                for row in rows
            ]

    def get_positional_recommendations(self, limit: int = 20) -> list[RecommendationRow]:
        """Get top N positional recommendations for the latest date."""
        with self.engine.connect() as conn:
            # Get latest date
            latest_date = self.get_latest_recommendation_date("positional")
            if latest_date is None:
                return []

            # Query recommendations with sector info
            query = text("""
                SELECT 
                    rh.rank,
                    rh.symbol,
                    rh.score,
                    sm.sector,
                    mv.version_tag as model_version
                FROM recommendation_history rh
                LEFT JOIN symbol_master sm ON rh.symbol = sm.symbol
                LEFT JOIN model_version mv ON rh.model_version_id = mv.version_id
                WHERE rh.model = 'positional'
                AND rh.date = :latest_date
                ORDER BY rh.rank ASC
                LIMIT :limit
            """)
            
            rows = conn.execute(query, {"latest_date": latest_date, "limit": limit}).fetchall()
            
            return [
                RecommendationRow(
                    rank=row.rank,
                    symbol=row.symbol,
                    score=float(row.score) if row.score is not None else None,
                    sector=row.sector,
                    model_version=row.model_version,
                )
                for row in rows
            ]

    def get_latest_sector_date(self) -> date | None:
        """Get the latest date with sector data."""
        with self.engine.connect() as conn:
            result = conn.execute(
                text("SELECT MAX(date) FROM sector_daily")
            ).scalar_one_or_none()
        return result

    def get_sector_strength(self) -> list[SectorRow]:
        """Get sector strength rankings for the latest date."""
        with self.engine.connect() as conn:
            latest_date = self.get_latest_sector_date()
            if latest_date is None:
                return []

            query = text("""
                SELECT 
                    sector,
                    sector_score,
                    rank_3m,
                    rank_composite,
                    stock_count
                FROM sector_daily
                WHERE date = :latest_date
                ORDER BY sector_score DESC NULLS LAST
            """)
            
            rows = conn.execute(query, {"latest_date": latest_date}).fetchall()
            
            return [
                SectorRow(
                    sector=row.sector,
                    sector_score=float(row.sector_score) if row.sector_score is not None else None,
                    rank_3m=row.rank_3m,
                    composite_rank=row.rank_composite,
                    stock_count=row.stock_count,
                )
                for row in rows
            ]

    def get_latest_score_date(self) -> date | None:
        """Get the latest date with score data."""
        with self.engine.connect() as conn:
            result = conn.execute(
                text("SELECT MAX(date) FROM daily_scores")
            ).scalar_one_or_none()
        return result

    def get_scores(
        self,
        symbol_filter: str | None = None,
        sort_by: str = "swing_score",
        limit: int = 100,
    ) -> list[ScoreRow]:
        """Get scores for the latest date, with optional filtering and sorting."""
        with self.engine.connect() as conn:
            latest_date = self.get_latest_score_date()
            if latest_date is None:
                return []

            # Build query
            base_query = """
                SELECT 
                    ds.symbol,
                    ds.swing_score,
                    ds.position_score,
                    sm.sector
                FROM daily_scores ds
                LEFT JOIN symbol_master sm ON ds.symbol = sm.symbol
                WHERE ds.date = :latest_date
            """
            
            params: dict[str, Any] = {"latest_date": latest_date}
            
            if symbol_filter:
                base_query += " AND ds.symbol ILIKE :symbol_filter"
                params["symbol_filter"] = f"%{symbol_filter}%"
            
            # Sorting
            valid_sort_columns = ["swing_score", "position_score", "symbol"]
            if sort_by not in valid_sort_columns:
                sort_by = "swing_score"
            
            base_query += f" ORDER BY {sort_by} DESC NULLS LAST"
            
            base_query += " LIMIT :limit"
            params["limit"] = limit
            
            query = text(base_query)
            rows = conn.execute(query, params).fetchall()
            
            return [
                ScoreRow(
                    symbol=row.symbol,
                    swing_score=float(row.swing_score) if row.swing_score is not None else None,
                    position_score=float(row.position_score) if row.position_score is not None else None,
                    sector=row.sector,
                )
                for row in rows
            ]
