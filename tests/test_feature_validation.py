"""Tests for feature validation module.

Tests validate:
- Indicator computation logic
- Validation result classification
- Tolerance thresholds
- Mismatch detection
"""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.research.feature_validation import FeatureValidator, FeatureValidationResult, ValidationStatus
from db.base import Base
from db.models import FeaturesDaily, PricesDaily, SymbolMaster


def build_session_factory():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)

    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, future=True)


def seed_price_and_feature_data(session, symbol, start_date, day_count):
    """Seed price and feature data for testing."""
    if session.get(SymbolMaster, symbol) is None:
        session.add(SymbolMaster(symbol=symbol))
        session.flush()

    close = 100.0
    for offset in range(day_count):
        current_date = start_date + timedelta(days=offset)
        high = close * 1.01
        low = close * 0.99
        
        # Price data
        session.add(
            PricesDaily(
                symbol=symbol,
                date=current_date,
                open=close,
                high=high,
                low=low,
                close=close,
                volume=1000,
            )
        )
        
        # Feature data (simplified - just storing close value as all features)
        session.add(
            FeaturesDaily(
                symbol=symbol,
                date=current_date,
                rsi_14=50.0,
                macd_line=1.0,
                macd_signal=0.8,
                macd_hist=0.2,
                adx_14=25.0,
                atr_14=2.0,
                bb_width=0.1,
                ema_5=close,
                ema_13=close,
                ema_20=close,
                ema_50=close,
                ema_150=close,
                ema_200=close,
            )
        )
        
        close *= 1.01


def test_feature_validation_result_construction():
    """Test FeatureValidationResult dataclass can be constructed."""
    result = FeatureValidationResult(
        indicator_name="rsi_14",
        sample_count=100,
        mean_absolute_error=0.01,
        max_absolute_error=0.05,
        match_percentage=95.0,
        status=ValidationStatus.PASS,
        tolerance=0.01,
        mismatches=[],
    )
    
    assert result.indicator_name == "rsi_14"
    assert result.sample_count == 100
    assert result.mean_absolute_error == 0.01
    assert result.max_absolute_error == 0.05
    assert result.match_percentage == 95.0
    assert result.status == ValidationStatus.PASS
    assert result.tolerance == 0.01
    assert result.mismatches == []


def test_compute_rsi():
    """Test RSI computation."""
    validator = FeatureValidator()
    
    # Create simple price series
    close = pd.Series([100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114, 115, 116, 117, 118, 119])
    rsi = validator.compute_rsi(close, period=14)
    
    # RSI should be computed (not None/NaN for later values)
    assert len(rsi) == len(close)
    # Later values should have valid RSI
    assert not pd.isna(rsi.iloc[-1])


def test_compute_macd():
    """Test MACD computation."""
    validator = FeatureValidator()
    
    close = pd.Series([100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114, 115, 116, 117, 118, 119, 120, 121, 122, 123, 124, 125, 126, 127, 128])
    macd_line, macd_signal, macd_hist = validator.compute_macd(close)
    
    assert len(macd_line) == len(close)
    assert len(macd_signal) == len(close)
    assert len(macd_hist) == len(close)
    # MACD hist should equal macd_line - macd_signal
    assert np.allclose(macd_hist, macd_line - macd_signal, equal_nan=True)


def test_compute_ema():
    """Test EMA computation."""
    validator = FeatureValidator()
    
    close = pd.Series([100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110])
    ema_5 = validator.compute_ema(close, 5)
    
    assert len(ema_5) == len(close)
    # EMA should be close to close for trending series
    assert not pd.isna(ema_5.iloc[-1])


def test_compute_atr():
    """Test ATR computation."""
    validator = FeatureValidator()
    
    high = pd.Series([101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114, 115])
    low = pd.Series([99, 100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114])
    close = pd.Series([100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114, 115])
    
    atr = validator.compute_atr(high, low, close, period=14)
    
    assert len(atr) == len(close)
    # ATR should be positive
    assert atr.iloc[-1] > 0


def test_compute_bb_width():
    """Test Bollinger Band width computation."""
    validator = FeatureValidator()
    
    close = pd.Series([100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114, 115, 116, 117, 118, 119, 120, 121])
    bb_width = validator.compute_bb_width(close, period=20, std_dev=2)
    
    assert len(bb_width) == len(close)
    # BB width should be positive
    assert bb_width.iloc[-1] > 0


def test_validate_indicator_perfect_match():
    """Test validation with perfect match."""
    validator = FeatureValidator()
    
    computed = {("SYMBOL1", date(2024, 1, 1)): 50.0, ("SYMBOL1", date(2024, 1, 2)): 51.0}
    stored = {("SYMBOL1", date(2024, 1, 1)): 50.0, ("SYMBOL1", date(2024, 1, 2)): 51.0}
    
    result = validator.validate_indicator("test_indicator", computed, stored, tolerance=0.01)
    
    assert result.sample_count == 2
    assert result.mean_absolute_error == 0.0
    assert result.match_percentage == 100.0
    assert result.status == ValidationStatus.PASS


def test_validate_indicator_with_mismatches():
    """Test validation with mismatches."""
    validator = FeatureValidator()
    
    computed = {("SYMBOL1", date(2024, 1, 1)): 50.0, ("SYMBOL1", date(2024, 1, 2)): 51.0}
    stored = {("SYMBOL1", date(2024, 1, 1)): 55.0, ("SYMBOL1", date(2024, 1, 2)): 51.0}  # 10% error on first
    
    result = validator.validate_indicator("test_indicator", computed, stored, tolerance=0.01)
    
    assert result.sample_count == 2
    assert result.match_percentage == 50.0  # Only 1 out of 2 matches
    assert result.status == ValidationStatus.FAIL  # Below 80%
    assert len(result.mismatches) == 1


def test_validate_indicator_none_stored():
    """Test validation with None stored values."""
    validator = FeatureValidator()
    
    computed = {("SYMBOL1", date(2024, 1, 1)): 50.0}
    stored = {("SYMBOL1", date(2024, 1, 1)): None}
    
    result = validator.validate_indicator("test_indicator", computed, stored, tolerance=0.01)
    
    assert result.sample_count == 1
    assert result.match_percentage == 0.0
    assert len(result.mismatches) == 1


def test_validate_indicator_classification_pass():
    """Test PASS classification (>=95% match)."""
    validator = FeatureValidator()
    
    computed = {("SYMBOL1", date(2024, 1, i)): 50.0 + i * 0.001 for i in range(1, 21)}
    stored = {("SYMBOL1", date(2024, 1, i)): 50.0 + i * 0.001 for i in range(1, 21)}  # Perfect match
    
    result = validator.validate_indicator("test", computed, stored, tolerance=0.01)
    
    assert result.status == ValidationStatus.PASS


def test_validate_indicator_classification_warn():
    """Test WARN classification (80-94% match)."""
    validator = FeatureValidator()
    
    computed = {("SYMBOL1", date(2024, 1, i)): 50.0 for i in range(1, 11)}
    stored = {}
    # 8 matches, 2 mismatches = 80% match
    for i in range(1, 11):
        if i < 9:
            stored[("SYMBOL1", date(2024, 1, i))] = 50.0
        else:
            stored[("SYMBOL1", date(2024, 1, i))] = 55.0  # 10% error
    
    result = validator.validate_indicator("test", computed, stored, tolerance=0.01)
    
    assert result.status == ValidationStatus.WARN


def test_validate_indicator_classification_fail():
    """Test FAIL classification (<80% match)."""
    validator = FeatureValidator()
    
    computed = {("SYMBOL1", date(2024, 1, i)): 50.0 for i in range(1, 11)}
    stored = {}
    # 5 matches, 5 mismatches = 50% match
    for i in range(1, 11):
        if i < 6:
            stored[("SYMBOL1", date(2024, 1, i))] = 50.0
        else:
            stored[("SYMBOL1", date(2024, 1, i))] = 55.0  # 10% error
    
    result = validator.validate_indicator("test", computed, stored, tolerance=0.01)
    
    assert result.status == ValidationStatus.FAIL


def test_feature_validator_instantiation():
    """Test FeatureValidator can be instantiated."""
    validator = FeatureValidator()
    assert validator is not None
    assert validator.TOLERANCE_PASS == 0.01
    assert validator.TOLERANCE_WARN == 0.05


def test_validation_status_enum():
    """Test ValidationStatus enum values."""
    assert ValidationStatus.PASS.value == "PASS"
    assert ValidationStatus.WARN.value == "WARN"
    assert ValidationStatus.FAIL.value == "FAIL"
