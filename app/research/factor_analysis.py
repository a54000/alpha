"""Factor analysis for evaluating predictive power of scoring components.

This module provides scaffolding for analyzing individual factors
(e.g., RSI, ADX, volume ratio) to determine their correlation with
forward returns and overall predictive power.

Analytics implementation is deferred to future research phase.
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from scipy import stats
from sqlalchemy import select

from db.models import PricesDaily, FeaturesDaily
from db.session import build_session_factory


@dataclass(frozen=True)
class FactorAnalysisResult:
    """Results of factor analysis for a single scoring component.
    
    Attributes:
        factor_name: Name of the factor being analyzed (e.g., 'rsi_14', 'adx_14')
        sample_size: Number of observations in the analysis
        pearson_correlation: Pearson correlation coefficient between factor and forward returns
        spearman_ic: Spearman Information Coefficient (rank correlation)
        average_return: Average forward return across all observations
        median_return: Median forward return across all observations
        top_bucket_return: Average forward return for top quintile/bucket of factor values
        bottom_bucket_return: Average forward return for bottom quintile/bucket of factor values
    """
    factor_name: str
    sample_size: int
    pearson_correlation: float | None
    spearman_ic: float | None
    average_return: float | None
    median_return: float | None
    top_bucket_return: float | None
    bottom_bucket_return: float | None


class FactorAnalyzer:
    """Analyzer for evaluating factor predictive power.
    
    This class provides the interface for factor analysis methods.
    Actual implementation is deferred to research phase.
    
    Methods may raise NotImplementedError until analytics are implemented.
    """
    
    def __init__(self, session_factory=None):
        """Initialize FactorAnalyzer with optional session factory."""
        self.session_factory = session_factory or build_session_factory()
    
    def compute_forward_returns(
        self,
        symbol: str,
        date: date,
        horizon: str,
    ) -> float | None:
        """Compute forward return for a symbol on a given date.
        
        Args:
            symbol: Stock symbol (e.g., 'RELIANCE.NS')
            date: Signal date
            horizon: Forward horizon ('5d', '10d','20d', or '60d')
            
        Returns:
            Forward return as (future_close / current_close) - 1, or None if unavailable
            
        Raises:
            ValueError: If horizon is not supported
        """
        # Map horizon strings to trading days
        horizon_map = {
            '5d': 5,
            '10d': 10,
            '20d': 20,
            '60d': 60,
            '120d': 120,
        }
        
        if horizon not in horizon_map:
            raise ValueError(f"Unsupported horizon: {horizon}. Supported: {list(horizon_map.keys())}")
        
        periods_forward = horizon_map[horizon]
        
        with self.session_factory() as session:
            # Get current price
            current_price_row = session.execute(
                select(PricesDaily.close)
                .where(
                    PricesDaily.symbol == symbol,
                    PricesDaily.date == date,
                )
            ).scalar_one_or_none()
            
            if current_price_row is None:
                return None
            
            current_close = float(current_price_row)
            
            # Get future price (periods_forward trading days ahead)
            # Query prices for the symbol starting from the date
            future_prices = session.execute(
                select(PricesDaily.date, PricesDaily.close)
                .where(
                    PricesDaily.symbol == symbol,
                    PricesDaily.date > date,
                )
                .order_by(PricesDaily.date.asc())
                .limit(periods_forward + 1)  # Get one extra to ensure we have the Nth day
            ).all()
            
            if len(future_prices) < periods_forward:
                return None
            
            # Get the Nth trading day's close price
            future_close = float(future_prices[periods_forward - 1].close)
            
            if future_close is None or current_close == 0:
                return None
            
            return (future_close / current_close) - 1.0
    
    def bucket_analysis(
        self,
        factor_values: list[float],
        forward_returns: list[float],
        num_buckets: int = 5,
    ) -> dict[str, dict[str, Any]]:
        """Perform bucket analysis on factor values.
        
        Args:
            factor_values: List of factor values
            forward_returns: Corresponding forward returns
            num_buckets: Number of quantile buckets to create (default: 5)
            
        Returns:
            Dictionary mapping bucket names to statistics:
            {
                "bucket_1": {"count": int, "average_return": float, "median_return": float, "win_rate": float},
                "bucket_2": {...},
                ...
            }
            
        Raises:
            ValueError: If factor_values and forward_returns have different lengths
        """
        if len(factor_values) != len(forward_returns):
            raise ValueError("factor_values and forward_returns must have the same length")
        
        if len(factor_values) == 0:
            return {}
        
        # Pair factor values with returns and sort by factor value
        paired = list(zip(factor_values, forward_returns))
        paired.sort(key=lambda x: x[0])
        
        # Split into buckets
        bucket_size = len(paired) // num_buckets
        remainder = len(paired) % num_buckets
        
        results = {}
        start_idx = 0
        
        for i in range(num_buckets):
            # Distribute remainder across first few buckets
            current_bucket_size = bucket_size + (1 if i < remainder else 0)
            end_idx = start_idx + current_bucket_size
            
            bucket_pairs = paired[start_idx:end_idx]
            bucket_returns = [ret for _, ret in bucket_pairs]
            
            if bucket_returns:
                count = len(bucket_returns)
                avg_return = statistics.mean(bucket_returns)
                median_return = statistics.median(bucket_returns)
                wins = sum(1 for ret in bucket_returns if ret > 0)
                win_rate = wins / count if count > 0 else 0.0
                
                results[f"bucket_{i+1}"] = {
                    "count": count,
                    "average_return": avg_return,
                    "median_return": median_return,
                    "win_rate": win_rate,
                }
            
            start_idx = end_idx
        
        return results
    
    def information_coefficient(
        self,
        factor_values: list[float],
        forward_returns: list[float],
    ) -> float:
        """Compute Information Coefficient (IC) for a factor.
        
        Args:
            factor_values: List of factor values
            forward_returns: Corresponding forward returns
            
        Returns:
            Spearman rank correlation coefficient (IC)
            
        Raises:
            ValueError: If input lists have different lengths
        """
        if len(factor_values) != len(forward_returns):
            raise ValueError("factor_values and forward_returns must have the same length")
        
        if len(factor_values) < 2:
            return 0.0
        
        # Remove None values
        paired = [(f, r) for f, r in zip(factor_values, forward_returns) if f is not None and r is not None]
        
        if len(paired) < 2:
            return 0.0
        
        x = [f for f, _ in paired]
        y = [r for _, r in paired]
        
        correlation, _ = stats.spearmanr(x, y)
        return correlation if not math.isnan(correlation) else 0.0
    
    def spearman_rank_correlation(
        self,
        x: list[float],
        y: list[float],
    ) -> float:
        """Compute Spearman rank correlation coefficient.
        
        Args:
            x: First variable values
            y: Second variable values
            
        Returns:
            Spearman correlation coefficient
            
        Raises:
            ValueError: If input lists have different lengths
        """
        if len(x) != len(y):
            raise ValueError("x and y must have the same length")
        
        if len(x) < 2:
            return 0.0
        
        # Remove None values
        paired = [(xi, yi) for xi, yi in zip(x, y) if xi is not None and yi is not None]
        
        if len(paired) < 2:
            return 0.0
        
        x_clean = [xi for xi, _ in paired]
        y_clean = [yi for _, yi in paired]
        
        correlation, _ = stats.spearmanr(x_clean, y_clean)
        return correlation if not math.isnan(correlation) else 0.0
    
    def factor_summary(
        self,
        factor_name: str,
        factor_values: dict[str, float],
        forward_returns: dict[str, float],
    ) -> FactorAnalysisResult:
        """Generate comprehensive factor analysis summary.
        
        Args:
            factor_name: Name of the factor
            factor_values: Mapping of symbol/date to factor values
            forward_returns: Mapping of symbol/date to forward returns
            
        Returns:
            FactorAnalysisResult with all computed metrics
            
        Raises:
            ValueError: If factor_values and forward_returns have different keys
        """
        if set(factor_values.keys()) != set(forward_returns.keys()):
            raise ValueError("factor_values and forward_returns must have the same keys")
        
        if not factor_values:
            return FactorAnalysisResult(
                factor_name=factor_name,
                sample_size=0,
                pearson_correlation=None,
                spearman_ic=None,
                average_return=None,
                median_return=None,
                top_bucket_return=None,
                bottom_bucket_return=None,
            )
        
        # Convert to lists
        factor_list = [factor_values[k] for k in sorted(factor_values.keys())]
        return_list = [forward_returns[k] for k in sorted(forward_returns.keys())]
        
        # Remove None values
        paired = [(f, r) for f, r in zip(factor_list, return_list) if f is not None and r is not None]
        
        if not paired:
            return FactorAnalysisResult(
                factor_name=factor_name,
                sample_size=0,
                pearson_correlation=None,
                spearman_ic=None,
                average_return=None,
                median_return=None,
                top_bucket_return=None,
                bottom_bucket_return=None,
            )
        
        factor_clean = [f for f, _ in paired]
        return_clean = [r for _, r in paired]
        sample_size = len(paired)
        
        # Pearson correlation
        pearson_corr, _ = stats.pearsonr(factor_clean, return_clean)
        pearson_corr = pearson_corr if not math.isnan(pearson_corr) else None
        
        # Spearman IC
        spearman_ic = self.information_coefficient(factor_clean, return_clean)
        
        # Average and median returns
        avg_return = statistics.mean(return_clean)
        median_return = statistics.median(return_clean)
        
        # Bucket analysis for top and bottom bucket returns
        bucket_results = self.bucket_analysis(factor_clean, return_clean, num_buckets=5)
        
        top_bucket_return = None
        bottom_bucket_return = None
        
        if bucket_results:
            # Top bucket (bucket_5) has highest factor values
            if "bucket_5" in bucket_results:
                top_bucket_return = bucket_results["bucket_5"]["average_return"]
            # Bottom bucket (bucket_1) has lowest factor values
            if "bucket_1" in bucket_results:
                bottom_bucket_return = bucket_results["bucket_1"]["average_return"]
        
        return FactorAnalysisResult(
            factor_name=factor_name,
            sample_size=sample_size,
            pearson_correlation=pearson_corr,
            spearman_ic=spearman_ic,
            average_return=avg_return,
            median_return=median_return,
            top_bucket_return=top_bucket_return,
            bottom_bucket_return=bottom_bucket_return,
        )
    
    def run(
        self,
        factor_names: list[str],
        start_date: date,
        end_date: date,
        horizon_days: int = 20,
    ) -> list[FactorAnalysisResult]:
        """Run factor analysis for multiple factors.
        
        Args:
            factor_names: List of factor names to analyze
            start_date: Analysis start date
            end_date: Analysis end date
            horizon_days: Forward return horizon in trading days
            
        Returns:
            List of FactorAnalysisResult for each factor
            
        Raises:
            ValueError: If factor name is not supported
        """
        # Map factor names to database column names
        factor_column_map = {
            'rs_rank_pct': 'rs_rank_pct',
            'volume_ratio': 'volume_ratio',
            'adx_14': 'adx_14',
            'rsi_14': 'rsi_14',
            'macd_hist': 'macd_hist',
            'stoch_k': 'stoch_k',
            'pct_from_52w_high': 'pct_from_52w_high',
            'bb_width': 'bb_width',
            'rank_3m': None,  # This comes from sector_daily, not features_daily
        }
        
        results = []
        
        for factor_name in factor_names:
            if factor_name not in factor_column_map:
                raise ValueError(f"Unsupported factor: {factor_name}. Supported: {list(factor_column_map.keys())}")
            
            column_name = factor_column_map[factor_name]
            
            if column_name is None:
                # Skip factors not in features_daily (like rank_3m from sector_daily)
                continue
            
            with self.session_factory() as session:
                # Query feature values for the date range
                query = select(
                    FeaturesDaily.symbol,
                    FeaturesDaily.date,
                    getattr(FeaturesDaily, column_name)
                ).where(
                    FeaturesDaily.date >= start_date,
                    FeaturesDaily.date <= end_date,
                )
                
                feature_rows = session.execute(query).all()
                
                if not feature_rows:
                    results.append(FactorAnalysisResult(
                        factor_name=factor_name,
                        sample_size=0,
                        pearson_correlation=None,
                        spearman_ic=None,
                        average_return=None,
                        median_return=None,
                        top_bucket_return=None,
                        bottom_bucket_return=None,
                    ))
                    continue
                
                # Build factor values and compute forward returns
                factor_values = {}
                forward_returns = {}
                
                for symbol, signal_date, factor_value in feature_rows:
                    if factor_value is None:
                        continue
                    
                    key = f"{symbol}_{signal_date.isoformat()}"
                    factor_values[key] = float(factor_value)
                    
                    # Compute forward return
                    horizon_str = f"{horizon_days}d"
                    fwd_return = self.compute_forward_returns(symbol, signal_date, horizon_str)
                    forward_returns[key] = fwd_return
                
                # Generate factor summary
                result = self.factor_summary(factor_name, factor_values, forward_returns)
                results.append(result)
        
        return results
