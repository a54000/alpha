"""Broad market regime classifier for strategy sleeve routing."""

from __future__ import annotations

from typing import Literal

import pandas as pd

from mean_reversion_system.src.strategy.signals import add_all_indicators

MarketRegime = Literal["ranging", "uptrend", "downtrend"]


def detect_market_regime(nifty_df: pd.DataFrame) -> pd.Series:
    """Classify market regime from daily index-like OHLCV data.

    Args:
        nifty_df: Daily OHLCV DataFrame for Nifty/Nifty500 or a documented proxy.

    Returns:
        Series containing ranging, uptrend, or downtrend labels.

    Raises:
        ValueError: If required OHLC columns are missing.
    """

    required = {"open", "high", "low", "close"}
    missing = sorted(required - set(nifty_df.columns))
    if missing:
        raise ValueError(f"missing market regime columns: {missing}")

    item = add_all_indicators(nifty_df.copy())
    close = pd.to_numeric(item["close"], errors="coerce")
    sma50 = close.rolling(50, min_periods=50).mean().shift(1)
    sma200 = close.rolling(200, min_periods=200).mean().shift(1)
    sma200_prev20 = sma200.shift(20)
    drawdown = close / close.cummax() - 1
    adx = pd.to_numeric(item["adx"], errors="coerce")

    regime = pd.Series("ranging", index=item.index, dtype="object")
    uptrend = (close > sma200) & (sma200 > sma200_prev20) & (close > sma50) & (drawdown > -0.10)
    downtrend = (close < sma200) & ((sma200 < sma200_prev20) | (drawdown < -0.15))
    regime.loc[uptrend] = "uptrend"
    regime.loc[downtrend] = "downtrend"
    regime.loc[item[["close", "adx"]].isna().any(axis=1) | sma200.isna()] = "ranging"
    return regime.astype("object")
