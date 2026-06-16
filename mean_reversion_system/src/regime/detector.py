"""Market regime detection for the mean reversion strategy."""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from mean_reversion_system.src.strategy.signals import add_all_indicators


def detect_regime(df: pd.DataFrame, index_df: pd.DataFrame | None = None) -> pd.Series:
    """Classify each bar into a market regime.

    Args:
        df: OHLCV DataFrame, with indicators already present or computable.
        index_df: Optional Nifty50 OHLCV DataFrame for broad-market gate.

    Returns:
        Series with values ranging, trending_up, trending_down, or volatile.

    Raises:
        ValueError: If close data is missing.
    """

    if "close" not in df.columns:
        raise ValueError("missing required column: close")
    item = df.copy()
    required = {"adx", "di_plus", "di_minus", "atr_pct", "bb_width"}
    if not required.issubset(item.columns):
        item = add_all_indicators(item)

    close = pd.to_numeric(item["close"], errors="coerce")
    sma50 = close.rolling(window=50, min_periods=50).mean().shift(1)
    slope = ((sma50 - sma50.shift(20)) / (sma50.shift(20) * 20).replace(0, np.nan)).abs()
    regime = pd.Series("ranging", index=item.index, dtype="object")
    regime.loc[(item["adx"] > 25) & (item["di_plus"] >= item["di_minus"])] = "trending_up"
    regime.loc[(item["adx"] > 25) & (item["di_minus"] > item["di_plus"])] = "trending_down"
    regime.loc[item["atr_pct"] > 0.04] = "volatile"
    ranging = (item["adx"] < 20) & (item["bb_width"] < 0.10) & (slope < 0.001)
    if index_df is not None:
        index_item = index_df.copy()
        if "adx" not in index_item.columns:
            index_item = add_all_indicators(index_item)
        index_adx = index_item["adx"].reindex(item.index).ffill()
        ranging = ranging & (index_adx < 25)
    regime.loc[~ranging & ~(regime.isin(["trending_up", "trending_down", "volatile"]))] = "volatile"
    regime.loc[ranging] = "ranging"
    regime.loc[item[["adx", "bb_width", "atr_pct"]].isna().any(axis=1)] = "volatile"
    return regime


def is_valid_entry_regime(df: pd.DataFrame, item_date: date | pd.Timestamp) -> bool:
    """Check whether one date is valid for mean reversion entry.

    Args:
        df: OHLCV DataFrame.
        item_date: Date to inspect.

    Returns:
        True when the date is classified as ranging.

    Raises:
        KeyError: If the date is not present in the DataFrame index.
    """

    regimes = detect_regime(df)
    key = pd.Timestamp(item_date)
    if key not in regimes.index:
        raise KeyError(f"date not present in regime history: {item_date}")
    return bool(regimes.loc[key] == "ranging")


def get_regime_history(df: pd.DataFrame) -> pd.DataFrame:
    """Build a regime history table with transition flags.

    Args:
        df: OHLCV DataFrame.

    Returns:
        DataFrame with regime and is_transition columns.

    Raises:
        ValueError: If close data is missing.
    """

    regimes = detect_regime(df)
    history = pd.DataFrame({"regime": regimes})
    history["previous_regime"] = history["regime"].shift(1)
    history["is_transition"] = history["previous_regime"].notna() & (history["regime"] != history["previous_regime"])
    history["transition_date"] = history.index.where(history["is_transition"], pd.NaT)
    return history
