"""Tests for dashboard query utilities.

Tests validate:
- latest recommendation retrieval
- sector ranking retrieval
- score retrieval
- empty-state handling
"""

from __future__ import annotations

import pytest
from datetime import date
from unittest.mock import Mock, MagicMock, patch

from app.dashboard.queries import (
    DashboardQueries,
    PipelineStats,
    RecommendationRow,
    SectorRow,
    ScoreRow,
)


class TestDashboardQueries:
    """Test suite for DashboardQueries class."""

    @pytest.fixture
    def mock_engine(self):
        """Create a mock SQLAlchemy engine."""
        engine = Mock()
        engine.connect.return_value.__enter__ = Mock()
        engine.connect.return_value.__exit__ = Mock()
        return engine

    @pytest.fixture
    def queries(self, mock_engine):
        """Create DashboardQueries instance with mocked engine."""
        with patch("app.dashboard.queries.create_engine", return_value=mock_engine):
            return DashboardQueries(database_url="postgresql://test")

    def test_get_pipeline_stats(self, queries, mock_engine):
        """Test pipeline statistics retrieval."""
        # Mock the connection and results
        mock_conn = Mock()
        mock_engine.connect.return_value.__enter__.return_value = mock_conn
        
        # Mock scalar returns
        mock_conn.execute.side_effect = [
            Mock(scalar_one_or_none=Mock(return_value=date(2024, 1, 15))),  # latest_pipeline_date
            Mock(scalar_one=Mock(return_value=500)),  # total_symbols
            Mock(scalar_one=Mock(return_value=1000000)),  # total_prices
            Mock(scalar_one=Mock(return_value=1000000)),  # total_features
            Mock(scalar_one=Mock(return_value=5000)),  # total_sectors
            Mock(scalar_one=Mock(return_value=1000000)),  # total_scores
            Mock(scalar_one=Mock(return_value=10000)),  # total_recommendations
        ]
        
        stats = queries.get_pipeline_stats()
        
        assert isinstance(stats, PipelineStats)
        assert stats.latest_pipeline_date == date(2024, 1, 15)
        assert stats.total_symbols == 500
        assert stats.total_prices == 1_000_000
        assert stats.total_features == 1_000_000
        assert stats.total_sectors == 5_000
        assert stats.total_scores == 1_000_000
        assert stats.total_recommendations == 10_000

    def test_get_pipeline_stats_empty_database(self, queries, mock_engine):
        """Test pipeline stats with empty database."""
        mock_conn = Mock()
        mock_engine.connect.return_value.__enter__.return_value = mock_conn
        
        # Mock scalar returns for empty database
        mock_conn.execute.side_effect = [
            Mock(scalar_one_or_none=Mock(return_value=None)),  # latest_pipeline_date
            Mock(scalar_one=Mock(return_value=0)),  # total_symbols
            Mock(scalar_one=Mock(return_value=0)),  # total_prices
            Mock(scalar_one=Mock(return_value=0)),  # total_features
            Mock(scalar_one=Mock(return_value=0)),  # total_sectors
            Mock(scalar_one=Mock(return_value=0)),  # total_scores
            Mock(scalar_one=Mock(return_value=0)),  # total_recommendations
        ]
        
        stats = queries.get_pipeline_stats()
        
        assert stats.latest_pipeline_date is None
        assert stats.total_symbols == 0
        assert stats.total_prices == 0
        assert stats.total_features == 0
        assert stats.total_sectors == 0
        assert stats.total_scores == 0
        assert stats.total_recommendations == 0

    def test_get_latest_recommendation_date(self, queries, mock_engine):
        """Test latest recommendation date retrieval."""
        mock_conn = Mock()
        mock_engine.connect.return_value.__enter__.return_value = mock_conn
        
        mock_conn.execute.return_value.scalar_one_or_none.return_value = date(2024, 1, 15)
        
        result = queries.get_latest_recommendation_date("swing")
        
        assert result == date(2024, 1, 15)
        mock_conn.execute.assert_called_once()

    def test_get_latest_recommendation_date_none(self, queries, mock_engine):
        """Test latest recommendation date when no data exists."""
        mock_conn = Mock()
        mock_engine.connect.return_value.__enter__.return_value = mock_conn
        
        mock_conn.execute.return_value.scalar_one_or_none.return_value = None
        
        result = queries.get_latest_recommendation_date("swing")
        
        assert result is None

    def test_get_swing_recommendations(self, queries, mock_engine):
        """Test swing recommendations retrieval."""
        # First call for latest date
        mock_conn = Mock()
        mock_engine.connect.return_value.__enter__.return_value = mock_conn
        
        # Mock latest date call
        mock_conn.execute.return_value.scalar_one_or_none.return_value = date(2024, 1, 15)
        
        # Mock recommendations query
        mock_row = Mock()
        mock_row.rank = 1
        mock_row.symbol = "RELIANCE"
        mock_row.score = 85.5
        mock_row.sector = "Energy"
        mock_row.model_version = "v1.0"
        
        mock_conn.execute.return_value.fetchall.return_value = [mock_row]
        
        recommendations = queries.get_swing_recommendations(limit=20)
        
        assert len(recommendations) == 1
        assert isinstance(recommendations[0], RecommendationRow)
        assert recommendations[0].rank == 1
        assert recommendations[0].symbol == "RELIANCE"
        assert recommendations[0].score == 85.5
        assert recommendations[0].sector == "Energy"
        assert recommendations[0].model_version == "v1.0"

    def test_get_swing_recommendations_empty(self, queries, mock_engine):
        """Test swing recommendations when no data exists."""
        mock_conn = Mock()
        mock_engine.connect.return_value.__enter__.return_value = mock_conn
        
        # Mock no latest date
        mock_conn.execute.return_value.scalar_one_or_none.return_value = None
        
        recommendations = queries.get_swing_recommendations(limit=20)
        
        assert recommendations == []

    def test_get_positional_recommendations(self, queries, mock_engine):
        """Test positional recommendations retrieval."""
        mock_conn = Mock()
        mock_engine.connect.return_value.__enter__.return_value = mock_conn
        
        # Mock latest date call
        mock_conn.execute.return_value.scalar_one_or_none.return_value = date(2024, 1, 15)
        
        # Mock recommendations query
        mock_row = Mock()
        mock_row.rank = 1
        mock_row.symbol = "TCS"
        mock_row.score = 78.0
        mock_row.sector = "IT"
        mock_row.model_version = "v1.0"
        
        mock_conn.execute.return_value.fetchall.return_value = [mock_row]
        
        recommendations = queries.get_positional_recommendations(limit=20)
        
        assert len(recommendations) == 1
        assert isinstance(recommendations[0], RecommendationRow)
        assert recommendations[0].rank == 1
        assert recommendations[0].symbol == "TCS"
        assert recommendations[0].score == 78.0
        assert recommendations[0].sector == "IT"
        assert recommendations[0].model_version == "v1.0"

    def test_get_positional_recommendations_empty(self, queries, mock_engine):
        """Test positional recommendations when no data exists."""
        mock_conn = Mock()
        mock_engine.connect.return_value.__enter__.return_value = mock_conn
        
        # Mock no latest date
        mock_conn.execute.return_value.scalar_one_or_none.return_value = None
        
        recommendations = queries.get_positional_recommendations(limit=20)
        
        assert recommendations == []

    def test_get_latest_sector_date(self, queries, mock_engine):
        """Test latest sector date retrieval."""
        mock_conn = Mock()
        mock_engine.connect.return_value.__enter__.return_value = mock_conn
        
        mock_conn.execute.return_value.scalar_one_or_none.return_value = date(2024, 1, 15)
        
        result = queries.get_latest_sector_date()
        
        assert result == date(2024, 1, 15)

    def test_get_sector_strength(self, queries, mock_engine):
        """Test sector strength retrieval."""
        mock_conn = Mock()
        mock_engine.connect.return_value.__enter__.return_value = mock_conn
        
        # Mock latest date call
        mock_conn.execute.return_value.scalar_one_or_none.return_value = date(2024, 1, 15)
        
        # Mock sector query
        mock_row = Mock()
        mock_row.sector = "IT"
        mock_row.sector_score = 0.15
        mock_row.rank_3m = 1
        mock_row.rank_composite = 1
        mock_row.stock_count = 25
        
        mock_conn.execute.return_value.fetchall.return_value = [mock_row]
        
        sectors = queries.get_sector_strength()
        
        assert len(sectors) == 1
        assert isinstance(sectors[0], SectorRow)
        assert sectors[0].sector == "IT"
        assert sectors[0].sector_score == 0.15
        assert sectors[0].rank_3m == 1
        assert sectors[0].composite_rank == 1
        assert sectors[0].stock_count == 25

    def test_get_sector_strength_empty(self, queries, mock_engine):
        """Test sector strength when no data exists."""
        mock_conn = Mock()
        mock_engine.connect.return_value.__enter__.return_value = mock_conn
        
        # Mock no latest date
        mock_conn.execute.return_value.scalar_one_or_none.return_value = None
        
        sectors = queries.get_sector_strength()
        
        assert sectors == []

    def test_get_latest_score_date(self, queries, mock_engine):
        """Test latest score date retrieval."""
        mock_conn = Mock()
        mock_engine.connect.return_value.__enter__.return_value = mock_conn
        
        mock_conn.execute.return_value.scalar_one_or_none.return_value = date(2024, 1, 15)
        
        result = queries.get_latest_score_date()
        
        assert result == date(2024, 1, 15)

    def test_get_scores(self, queries, mock_engine):
        """Test score retrieval."""
        mock_conn = Mock()
        mock_engine.connect.return_value.__enter__.return_value = mock_conn
        
        # Mock latest date call
        mock_conn.execute.return_value.scalar_one_or_none.return_value = date(2024, 1, 15)
        
        # Mock scores query
        mock_row = Mock()
        mock_row.symbol = "RELIANCE"
        mock_row.swing_score = 85.5
        mock_row.position_score = 72.0
        mock_row.sector = "Energy"
        
        mock_conn.execute.return_value.fetchall.return_value = [mock_row]
        
        scores = queries.get_scores(symbol_filter=None, sort_by="swing_score", limit=100)
        
        assert len(scores) == 1
        assert isinstance(scores[0], ScoreRow)
        assert scores[0].symbol == "RELIANCE"
        assert scores[0].swing_score == 85.5
        assert scores[0].position_score == 72.0
        assert scores[0].sector == "Energy"

    def test_get_scores_with_filter(self, queries, mock_engine):
        """Test score retrieval with symbol filter."""
        mock_conn = Mock()
        mock_engine.connect.return_value.__enter__.return_value = mock_conn
        
        # Mock latest date call
        mock_conn.execute.return_value.scalar_one_or_none.return_value = date(2024, 1, 15)
        
        # Mock scores query
        mock_row = Mock()
        mock_row.symbol = "RELIANCE"
        mock_row.swing_score = 85.5
        mock_row.position_score = 72.0
        mock_row.sector = "Energy"
        
        mock_conn.execute.return_value.fetchall.return_value = [mock_row]
        
        scores = queries.get_scores(symbol_filter="REL", sort_by="swing_score", limit=100)
        
        assert len(scores) == 1
        assert scores[0].symbol == "RELIANCE"

    def test_get_scores_empty(self, queries, mock_engine):
        """Test score retrieval when no data exists."""
        mock_conn = Mock()
        mock_engine.connect.return_value.__enter__.return_value = mock_conn
        
        # Mock no latest date
        mock_conn.execute.return_value.scalar_one_or_none.return_value = None
        
        scores = queries.get_scores(symbol_filter=None, sort_by="swing_score", limit=100)
        
        assert scores == []

    def test_get_scores_invalid_sort_column(self, queries, mock_engine):
        """Test score retrieval with invalid sort column defaults to swing_score."""
        mock_conn = Mock()
        mock_engine.connect.return_value.__enter__.return_value = mock_conn
        
        # Mock latest date call
        mock_conn.execute.return_value.scalar_one_or_none.return_value = date(2024, 1, 15)
        
        # Mock scores query
        mock_row = Mock()
        mock_row.symbol = "RELIANCE"
        mock_row.swing_score = 85.5
        mock_row.position_score = 72.0
        mock_row.sector = "Energy"
        
        mock_conn.execute.return_value.fetchall.return_value = [mock_row]
        
        # Use invalid sort column, should default to swing_score
        scores = queries.get_scores(symbol_filter=None, sort_by="invalid_column", limit=100)
        
        assert len(scores) == 1

    def test_recommendation_row_null_handling(self, queries, mock_engine):
        """Test RecommendationRow handles None values correctly."""
        mock_row = Mock()
        mock_row.rank = 1
        mock_row.symbol = "TEST"
        mock_row.score = None
        mock_row.sector = None
        mock_row.model_version = None
        
        rec = RecommendationRow(
            rank=mock_row.rank,
            symbol=mock_row.symbol,
            score=mock_row.score,
            sector=mock_row.sector,
            model_version=mock_row.model_version,
        )
        
        assert rec.score is None
        assert rec.sector is None
        assert rec.model_version is None

    def test_sector_row_null_handling(self):
        """Test SectorRow handles None values correctly."""
        sector = SectorRow(
            sector="IT",
            sector_score=None,
            rank_3m=None,
            composite_rank=None,
            stock_count=None,
        )
        
        assert sector.sector_score is None
        assert sector.rank_3m is None
        assert sector.composite_rank is None
        assert sector.stock_count is None

    def test_score_row_null_handling(self):
        """Test ScoreRow handles None values correctly."""
        score = ScoreRow(
            symbol="TEST",
            swing_score=None,
            position_score=None,
            sector=None,
        )
        
        assert score.swing_score is None
        assert score.position_score is None
        assert score.sector is None
