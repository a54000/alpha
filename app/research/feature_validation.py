"""Feature validation utility.

Validates that features_daily values match independently recomputed
indicator values from prices_daily to ensure calculation correctness.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from enum import Enum
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy import select, func

from db.models import FeaturesDaily, PricesDaily, SymbolMaster
from db.session import build_session_factory


class ValidationStatus(Enum):
    """Classification of validation result."""
    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"


@dataclass(frozen=True)
class FeatureValidationResult:
    """Result of validating a single indicator.
    
    Attributes:
        indicator_name: Name of the indicator being validated
        sample_count: Number of samples validated
        mean_absolute_error: Mean absolute error between computed and stored values
        max_absolute_error: Maximum absolute error observed
        match_percentage: Percentage of samples within tolerance
        status: PASS, WARN, or FAIL classification
        tolerance: Tolerance threshold used for classification
        mismatches: List of (symbol, date, computed, stored) for mismatches
    """
    indicator_name: str
    sample_count: int
    mean_absolute_error: float
    max_absolute_error: float
    match_percentage: float
    status: ValidationStatus
    tolerance: float
    mismatches: list[tuple[str, date, float, float | None]]


class FeatureValidator:
    """Validator for features_daily calculations."""
    
    # Tolerance thresholds for classification
    TOLERANCE_PASS = 0.01  # 1% relative error
    TOLERANCE_WARN = 0.05  # 5% relative error
    
    def __init__(self, session_factory=None):
        """Initialize validator with optional session factory."""
        self.session_factory = session_factory or build_session_factory()
    
    def select_liquid_symbols(self, count: int = 10) -> list[str]:
        """Select liquid NSE symbols based on average traded value.
        
        Args:
            count: Number of symbols to select
            
        Returns:
            List of symbol tickers
        """
        with self.session_factory() as session:
            # Get symbols from SymbolMaster (NSE500 stocks)
            query = select(SymbolMaster.symbol).limit(count)
            symbols = [row[0] for row in session.execute(query).all()]
        
        return symbols
    
    def select_dates(self, count: int = 5, months_back: int = 6) -> list[date]:
        """Select dates from the most recent N months.
        
        Args:
            count: Number of dates to select
            months_back: How many months back to consider
            
        Returns:
            List of dates
        """
        with self.session_factory() as session:
            # Get the most recent date in the database
            max_date = session.execute(select(func.max(PricesDaily.date))).scalar()
            
            if max_date is None:
                return []
            
            end_date = max_date
            start_date = end_date - timedelta(days=months_back * 30)
            
            query = select(PricesDaily.date).where(
                PricesDaily.date >= start_date,
                PricesDaily.date <= end_date,
            ).distinct().order_by(
                PricesDaily.date.desc(),
            ).limit(count)
            
            dates = [row[0] for row in session.execute(query).all()]
        
        return dates
    
    def load_price_data(self, symbols: list[str], dates: list[date]) -> dict[str, pd.DataFrame]:
        """Load OHLCV data for symbols and dates.
        
        Args:
            symbols: List of symbol tickers
            dates: List of dates
            
        Returns:
            Dictionary mapping symbol to DataFrame with OHLCV data
        """
        if not dates:
            return {}
        
        start_date = min(dates) - timedelta(days=300)  # Need history for indicators
        
        with self.session_factory() as session:
            query = select(
                PricesDaily.symbol,
                PricesDaily.date,
                PricesDaily.open,
                PricesDaily.high,
                PricesDaily.low,
                PricesDaily.close,
                PricesDaily.volume,
            ).where(
                PricesDaily.symbol.in_(symbols),
                PricesDaily.date >= start_date,
                PricesDaily.date <= max(dates),
            ).order_by(
                PricesDaily.symbol.asc(),
                PricesDaily.date.asc(),
            )
            
            rows = session.execute(query).all()
        
        # Convert to DataFrame per symbol
        data = {}
        for symbol in symbols:
            symbol_rows = [r for r in rows if r.symbol == symbol]
            if symbol_rows:
                df = pd.DataFrame([
                    {
                        'date': r.date,
                        'open': r.open,
                        'high': r.high,
                        'low': r.low,
                        'close': r.close,
                        'volume': r.volume,
                    }
                    for r in symbol_rows
                ])
                df.set_index('date', inplace=True)
                df.sort_index(inplace=True)
                data[symbol] = df
        
        return data
    
    def load_feature_data(self, symbols: list[str], dates: list[date]) -> dict[str, dict[date, dict[str, float]]]:
        """Load feature data for symbols and dates.
        
        Args:
            symbols: List of symbol tickers
            dates: List of dates
            
        Returns:
            Dictionary mapping symbol to date to feature values
        """
        with self.session_factory() as session:
            query = select(
                FeaturesDaily.symbol,
                FeaturesDaily.date,
                FeaturesDaily.rsi_14,
                FeaturesDaily.macd_line,
                FeaturesDaily.macd_signal,
                FeaturesDaily.macd_hist,
                FeaturesDaily.adx_14,
                FeaturesDaily.atr_14,
                FeaturesDaily.bb_width,
                FeaturesDaily.ema_5,
                FeaturesDaily.ema_13,
                FeaturesDaily.ema_20,
                FeaturesDaily.ema_50,
                FeaturesDaily.ema_150,
                FeaturesDaily.ema_200,
            ).where(
                FeaturesDaily.symbol.in_(symbols),
                FeaturesDaily.date.in_(dates),
            )
            
            rows = session.execute(query).all()
        
        data = {}
        for row in rows:
            if row.symbol not in data:
                data[row.symbol] = {}
            data[row.symbol][row.date] = {
                'rsi_14': row.rsi_14,
                'macd': row.macd_line,
                'macd_signal': row.macd_signal,
                'macd_hist': row.macd_hist,
                'adx_14': row.adx_14,
                'atr_14': row.atr_14,
                'bb_width': row.bb_width,
                'ema_5': row.ema_5,
                'ema_13': row.ema_13,
                'ema_20': row.ema_20,
                'ema_50': row.ema_50,
                'ema_150': row.ema_150,
                'ema_200': row.ema_200,
            }
        
        return data
    
    def compute_rsi(self, close: pd.Series, period: int = 14) -> pd.Series:
        """Compute RSI indicator.
        
        Args:
            close: Close price series
            period: RSI period
            
        Returns:
            RSI values
        """
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def compute_macd(self, close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> tuple[pd.Series, pd.Series, pd.Series]:
        """Compute MACD indicator.
        
        Args:
            close: Close price series
            fast: Fast EMA period
            slow: Slow EMA period
            signal: Signal line period
            
        Returns:
            Tuple of (macd_line, macd_signal, macd_histogram)
        """
        ema_fast = close.ewm(span=fast, adjust=False).mean()
        ema_slow = close.ewm(span=slow, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        macd_signal = macd_line.ewm(span=signal, adjust=False).mean()
        macd_hist = macd_line - macd_signal
        return macd_line, macd_signal, macd_hist
    
    def compute_adx(self, high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
        """Compute ADX indicator.
        
        Args:
            high: High price series
            low: Low price series
            close: Close price series
            period: ADX period
            
        Returns:
            ADX values
        """
        # True Range
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        
        # ATR
        atr = tr.rolling(window=period).mean()
        
        # +DM and -DM
        plus_dm = high.diff()
        minus_dm = -low.diff()
        
        plus_dm = plus_dm.where((plus_dm > 0) & (plus_dm > minus_dm), 0)
        minus_dm = minus_dm.where((minus_dm > 0) & (minus_dm > plus_dm), 0)
        
        # Smoothed +DM and -DM
        plus_dm_smooth = plus_dm.rolling(window=period).mean()
        minus_dm_smooth = minus_dm.rolling(window=period).mean()
        
        # +DI and -DI
        plus_di = 100 * (plus_dm_smooth / atr)
        minus_di = 100 * (minus_dm_smooth / atr)
        
        # DX
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
        
        # ADX
        adx = dx.rolling(window=period).mean()
        
        return adx
    
    def compute_atr(self, high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
        """Compute ATR indicator.
        
        Args:
            high: High price series
            low: Low price series
            close: Close price series
            period: ATR period
            
        Returns:
            ATR values
        """
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean()
        return atr
    
    def compute_bb_width(self, close: pd.Series, period: int = 20, std_dev: int = 2) -> pd.Series:
        """Compute Bollinger Band width.
        
        Args:
            close: Close price series
            period: BB period
            std_dev: Standard deviation multiplier
            
        Returns:
            BB width values
        """
        sma = close.rolling(window=period).mean()
        std = close.rolling(window=period).std()
        upper = sma + (std * std_dev)
        lower = sma - (std * std_dev)
        bb_width = (upper - lower) / sma
        return bb_width
    
    def compute_ema(self, close: pd.Series, period: int) -> pd.Series:
        """Compute EMA indicator.
        
        Args:
            close: Close price series
            period: EMA period
            
        Returns:
            EMA values
        """
        return close.ewm(span=period, adjust=False).mean()
    
    def validate_indicator(
        self,
        indicator_name: str,
        computed_values: dict[tuple[str, date], float],
        stored_values: dict[tuple[str, date], float | None],
        tolerance: float = TOLERANCE_PASS,
    ) -> FeatureValidationResult:
        """Validate a single indicator.
        
        Args:
            indicator_name: Name of the indicator
            computed_values: Dictionary of (symbol, date) -> computed value
            stored_values: Dictionary of (symbol, date) -> stored value
            tolerance: Tolerance threshold for classification
            
        Returns:
            FeatureValidationResult
        """
        keys = set(computed_values.keys()) & set(stored_values.keys())
        
        if not keys:
            return FeatureValidationResult(
                indicator_name=indicator_name,
                sample_count=0,
                mean_absolute_error=0.0,
                max_absolute_error=0.0,
                match_percentage=0.0,
                status=ValidationStatus.WARN,
                tolerance=tolerance,
                mismatches=[],
            )
        
        errors = []
        matches = 0
        mismatches = []
        
        for key in keys:
            computed = computed_values[key]
            stored = stored_values[key]
            
            if stored is None:
                mismatches.append((key[0], key[1], computed, None))
                continue
            
            # Convert Decimal to float if needed
            stored_float = float(stored) if hasattr(stored, '__float__') else stored
            
            # Relative error
            if abs(stored_float) > 1e-10:
                relative_error = abs(computed - stored_float) / abs(stored_float)
            else:
                relative_error = abs(computed - stored_float)
            
            errors.append(relative_error)
            
            if relative_error <= tolerance:
                matches += 1
            else:
                mismatches.append((key[0], key[1], computed, stored_float))
        
        sample_count = len(keys)
        mean_absolute_error = np.mean(errors) if errors else 0.0
        max_absolute_error = np.max(errors) if errors else 0.0
        match_percentage = (matches / sample_count * 100) if sample_count > 0 else 0.0
        
        # Classify status
        if match_percentage >= 95:
            status = ValidationStatus.PASS
        elif match_percentage >= 80:
            status = ValidationStatus.WARN
        else:
            status = ValidationStatus.FAIL
        
        return FeatureValidationResult(
            indicator_name=indicator_name,
            sample_count=sample_count,
            mean_absolute_error=mean_absolute_error,
            max_absolute_error=max_absolute_error,
            match_percentage=match_percentage,
            status=status,
            tolerance=tolerance,
            mismatches=mismatches,
        )
    
    def run_validation(
        self,
        symbol_count: int = 10,
        date_count: int = 5,
        months_back: int = 6,
    ) -> dict[str, FeatureValidationResult]:
        """Run full validation on all indicators.
        
        Args:
            symbol_count: Number of symbols to validate
            date_count: Number of dates per symbol
            months_back: How many months back to consider
            
        Returns:
            Dictionary mapping indicator name to validation result
        """
        # Select symbols and dates
        symbols = self.select_liquid_symbols(symbol_count)
        dates = self.select_dates(date_count, months_back)
        
        # Load data
        price_data = self.load_price_data(symbols, dates)
        feature_data = self.load_feature_data(symbols, dates)
        
        # Compute indicators for each symbol
        computed_indicators = {
            'rsi_14': {},
            'macd': {},
            'macd_signal': {},
            'macd_hist': {},
            'adx_14': {},
            'atr_14': {},
            'bb_width': {},
            'ema_5': {},
            'ema_13': {},
            'ema_20': {},
            'ema_50': {},
            'ema_150': {},
            'ema_200': {},
        }
        
        for symbol, df in price_data.items():
            if len(df) < 200:
                continue  # Need enough history for indicators
            
            # Compute indicators
            rsi = self.compute_rsi(df['close'])
            macd_line, macd_signal, macd_hist = self.compute_macd(df['close'])
            adx = self.compute_adx(df['high'], df['low'], df['close'])
            atr = self.compute_atr(df['high'], df['low'], df['close'])
            bb_width = self.compute_bb_width(df['close'])
            ema_5 = self.compute_ema(df['close'], 5)
            ema_13 = self.compute_ema(df['close'], 13)
            ema_20 = self.compute_ema(df['close'], 20)
            ema_50 = self.compute_ema(df['close'], 50)
            ema_150 = self.compute_ema(df['close'], 150)
            ema_200 = self.compute_ema(df['close'], 200)
            
            # Store computed values for selected dates
            for validation_date in dates:
                if validation_date in df.index:
                    computed_indicators['rsi_14'][(symbol, validation_date)] = rsi.loc[validation_date]
                    computed_indicators['macd'][(symbol, validation_date)] = macd_line.loc[validation_date]
                    computed_indicators['macd_signal'][(symbol, validation_date)] = macd_signal.loc[validation_date]
                    computed_indicators['macd_hist'][(symbol, validation_date)] = macd_hist.loc[validation_date]
                    computed_indicators['adx_14'][(symbol, validation_date)] = adx.loc[validation_date]
                    computed_indicators['atr_14'][(symbol, validation_date)] = atr.loc[validation_date]
                    computed_indicators['bb_width'][(symbol, validation_date)] = bb_width.loc[validation_date]
                    computed_indicators['ema_5'][(symbol, validation_date)] = ema_5.loc[validation_date]
                    computed_indicators['ema_13'][(symbol, validation_date)] = ema_13.loc[validation_date]
                    computed_indicators['ema_20'][(symbol, validation_date)] = ema_20.loc[validation_date]
                    computed_indicators['ema_50'][(symbol, validation_date)] = ema_50.loc[validation_date]
                    computed_indicators['ema_150'][(symbol, validation_date)] = ema_150.loc[validation_date]
                    computed_indicators['ema_200'][(symbol, validation_date)] = ema_200.loc[validation_date]
        
        # Load stored values
        stored_indicators = {
            'rsi_14': {},
            'macd': {},
            'macd_signal': {},
            'macd_hist': {},
            'adx_14': {},
            'atr_14': {},
            'bb_width': {},
            'ema_5': {},
            'ema_13': {},
            'ema_20': {},
            'ema_50': {},
            'ema_150': {},
            'ema_200': {},
        }
        
        for symbol, date_features in feature_data.items():
            for validation_date, features in date_features.items():
                stored_indicators['rsi_14'][(symbol, validation_date)] = features['rsi_14']
                stored_indicators['macd'][(symbol, validation_date)] = features['macd']
                stored_indicators['macd_signal'][(symbol, validation_date)] = features['macd_signal']
                stored_indicators['macd_hist'][(symbol, validation_date)] = features['macd_hist']
                stored_indicators['adx_14'][(symbol, validation_date)] = features['adx_14']
                stored_indicators['atr_14'][(symbol, validation_date)] = features['atr_14']
                stored_indicators['bb_width'][(symbol, validation_date)] = features['bb_width']
                stored_indicators['ema_5'][(symbol, validation_date)] = features['ema_5']
                stored_indicators['ema_13'][(symbol, validation_date)] = features['ema_13']
                stored_indicators['ema_20'][(symbol, validation_date)] = features['ema_20']
                stored_indicators['ema_50'][(symbol, validation_date)] = features['ema_50']
                stored_indicators['ema_150'][(symbol, validation_date)] = features['ema_150']
                stored_indicators['ema_200'][(symbol, validation_date)] = features['ema_200']
        
        # Validate each indicator
        results = {}
        for indicator_name in computed_indicators.keys():
            result = self.validate_indicator(
                indicator_name,
                computed_indicators[indicator_name],
                stored_indicators[indicator_name],
            )
            results[indicator_name] = result
        
        return results
    
    def run_validation_for_symbol(
        self,
        symbol: str,
        date_count: int = 5,
        months_back: int = 6,
    ) -> dict[str, FeatureValidationResult]:
        """Run validation for a specific symbol.
        
        Args:
            symbol: Symbol ticker to validate
            date_count: Number of dates to validate
            months_back: How many months back to consider
            
        Returns:
            Dictionary mapping indicator name to validation result
        """
        # Select dates
        dates = self.select_dates(date_count, months_back)
        
        # Load data
        price_data = self.load_price_data([symbol], dates)
        feature_data = self.load_feature_data([symbol], dates)
        
        # Compute indicators
        computed_indicators = {
            'rsi_14': {},
            'macd': {},
            'macd_signal': {},
            'macd_hist': {},
            'adx_14': {},
            'atr_14': {},
            'bb_width': {},
            'ema_5': {},
            'ema_13': {},
            'ema_20': {},
            'ema_50': {},
            'ema_150': {},
            'ema_200': {},
        }
        
        if symbol not in price_data or len(price_data[symbol]) < 200:
            print(f"Warning: Insufficient price data for {symbol}")
            return {name: FeatureValidationResult(
                indicator_name=name,
                sample_count=0,
                mean_absolute_error=0.0,
                max_absolute_error=0.0,
                match_percentage=0.0,
                status=ValidationStatus.WARN,
                tolerance=self.TOLERANCE_PASS,
                mismatches=[],
            ) for name in computed_indicators.keys()}
        
        df = price_data[symbol]
        
        # Compute indicators
        rsi = self.compute_rsi(df['close'])
        macd_line, macd_signal, macd_hist = self.compute_macd(df['close'])
        adx = self.compute_adx(df['high'], df['low'], df['close'])
        atr = self.compute_atr(df['high'], df['low'], df['close'])
        bb_width = self.compute_bb_width(df['close'])
        ema_5 = self.compute_ema(df['close'], 5)
        ema_13 = self.compute_ema(df['close'], 13)
        ema_20 = self.compute_ema(df['close'], 20)
        ema_50 = self.compute_ema(df['close'], 50)
        ema_150 = self.compute_ema(df['close'], 150)
        ema_200 = self.compute_ema(df['close'], 200)
        
        # Store computed values for selected dates
        for validation_date in dates:
            if validation_date in df.index:
                computed_indicators['rsi_14'][(symbol, validation_date)] = rsi.loc[validation_date]
                computed_indicators['macd'][(symbol, validation_date)] = macd_line.loc[validation_date]
                computed_indicators['macd_signal'][(symbol, validation_date)] = macd_signal.loc[validation_date]
                computed_indicators['macd_hist'][(symbol, validation_date)] = macd_hist.loc[validation_date]
                computed_indicators['adx_14'][(symbol, validation_date)] = adx.loc[validation_date]
                computed_indicators['atr_14'][(symbol, validation_date)] = atr.loc[validation_date]
                computed_indicators['bb_width'][(symbol, validation_date)] = bb_width.loc[validation_date]
                computed_indicators['ema_5'][(symbol, validation_date)] = ema_5.loc[validation_date]
                computed_indicators['ema_13'][(symbol, validation_date)] = ema_13.loc[validation_date]
                computed_indicators['ema_20'][(symbol, validation_date)] = ema_20.loc[validation_date]
                computed_indicators['ema_50'][(symbol, validation_date)] = ema_50.loc[validation_date]
                computed_indicators['ema_150'][(symbol, validation_date)] = ema_150.loc[validation_date]
                computed_indicators['ema_200'][(symbol, validation_date)] = ema_200.loc[validation_date]
        
        # Load stored values
        stored_indicators = {
            'rsi_14': {},
            'macd': {},
            'macd_signal': {},
            'macd_hist': {},
            'adx_14': {},
            'atr_14': {},
            'bb_width': {},
            'ema_5': {},
            'ema_13': {},
            'ema_20': {},
            'ema_50': {},
            'ema_150': {},
            'ema_200': {},
        }
        
        if symbol in feature_data:
            for validation_date, features in feature_data[symbol].items():
                stored_indicators['rsi_14'][(symbol, validation_date)] = features['rsi_14']
                stored_indicators['macd'][(symbol, validation_date)] = features['macd']
                stored_indicators['macd_signal'][(symbol, validation_date)] = features['macd_signal']
                stored_indicators['macd_hist'][(symbol, validation_date)] = features['macd_hist']
                stored_indicators['adx_14'][(symbol, validation_date)] = features['adx_14']
                stored_indicators['atr_14'][(symbol, validation_date)] = features['atr_14']
                stored_indicators['bb_width'][(symbol, validation_date)] = features['bb_width']
                stored_indicators['ema_5'][(symbol, validation_date)] = features['ema_5']
                stored_indicators['ema_13'][(symbol, validation_date)] = features['ema_13']
                stored_indicators['ema_20'][(symbol, validation_date)] = features['ema_20']
                stored_indicators['ema_50'][(symbol, validation_date)] = features['ema_50']
                stored_indicators['ema_150'][(symbol, validation_date)] = features['ema_150']
                stored_indicators['ema_200'][(symbol, validation_date)] = features['ema_200']
        
        # Validate each indicator
        results = {}
        for indicator_name in computed_indicators.keys():
            result = self.validate_indicator(
                indicator_name,
                computed_indicators[indicator_name],
                stored_indicators[indicator_name],
            )
            results[indicator_name] = result
        
        return results
