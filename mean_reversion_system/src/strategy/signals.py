"""Indicator calculations for the mean reversion strategy."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


def _project_root() -> Path:
    """Return the mean reversion subproject root.

    Args:
        None.

    Returns:
        Absolute path to the subproject root.

    Raises:
        RuntimeError: Never raised.
    """

    return Path(__file__).resolve().parents[2]


def _strategy_config() -> dict[str, dict[str, float | int]]:
    """Load strategy parameters with a lightweight YAML fallback.

    Args:
        None.

    Returns:
        Nested strategy configuration dictionary.

    Raises:
        RuntimeError: Never raised; defaults are used when config parsing fails.
    """

    defaults: dict[str, dict[str, float | int]] = {
        "bollinger_bands": {"period": 20, "std_dev": 2.0, "bandwidth_threshold": 0.10},
        "rsi": {"period": 14, "oversold": 30, "overbought": 70},
        "atr": {"period": 14, "sl_atr_multiplier": 2.25},
        "adx": {"period": 14},
        "volume": {"ratio_period": 20, "min_ratio": 0.8},
        "exits": {"max_hold_days": 10},
    }
    path = _project_root() / "config" / "strategy_params.yaml"
    if not path.exists():
        return defaults
    try:
        import yaml  # type: ignore

        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        strategy = payload.get("strategy") or {}
        return {key: {**defaults[key], **(strategy.get(key) or {})} for key in defaults}
    except Exception:
        return defaults


def _require_ohlcv(df: pd.DataFrame, columns: list[str]) -> None:
    """Validate that a DataFrame has required columns.

    Args:
        df: Input price DataFrame.
        columns: Required column names.

    Returns:
        None.

    Raises:
        ValueError: If any required column is missing.
    """

    missing = [column for column in columns if column not in df.columns]
    if missing:
        raise ValueError(f"missing required columns: {missing}")


def calc_bollinger_bands(df: pd.DataFrame, period: int, std_dev: float) -> pd.DataFrame:
    """Calculate shifted Bollinger Band columns.

    Args:
        df: OHLCV DataFrame with close column.
        period: Rolling SMA and standard deviation period.
        std_dev: Band width multiplier.

    Returns:
        DataFrame with bb_upper, bb_mid, bb_lower, bb_width, and bb_pct_b.

    Raises:
        ValueError: If close is missing.
    """

    _require_ohlcv(df, ["close"])
    item = df.copy()
    close = pd.to_numeric(item["close"], errors="coerce")
    mid = close.rolling(window=period, min_periods=period).mean()
    sigma = close.rolling(window=period, min_periods=period).std(ddof=0)
    upper = mid + float(std_dev) * sigma
    lower = mid - float(std_dev) * sigma
    width = (upper - lower) / mid.replace(0, np.nan)
    pct_b = (close - lower) / (upper - lower).replace(0, np.nan)
    item["bb_upper"] = upper.shift(1)
    item["bb_mid"] = mid.shift(1)
    item["bb_lower"] = lower.shift(1)
    item["bb_width"] = width.shift(1)
    item["bb_pct_b"] = pct_b.shift(1)
    return item


def calc_rsi(df: pd.DataFrame, period: int) -> pd.DataFrame:
    """Calculate shifted Wilder RSI.

    Args:
        df: OHLCV DataFrame with close column.
        period: RSI lookback period.

    Returns:
        DataFrame with rsi column.

    Raises:
        ValueError: If close is missing.
    """

    _require_ohlcv(df, ["close"])
    item = df.copy()
    close = pd.to_numeric(item["close"], errors="coerce")
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    rsi = rsi.where(avg_loss != 0, 100).where(avg_gain != 0, 0)
    item["rsi"] = rsi.clip(0, 100).shift(1)
    return item


def calc_atr(df: pd.DataFrame, period: int) -> pd.DataFrame:
    """Calculate shifted Average True Range.

    Args:
        df: OHLCV DataFrame with high, low, and close columns.
        period: ATR lookback period.

    Returns:
        DataFrame with atr and atr_pct columns.

    Raises:
        ValueError: If high, low, or close is missing.
    """

    _require_ohlcv(df, ["high", "low", "close"])
    item = df.copy()
    high = pd.to_numeric(item["high"], errors="coerce")
    low = pd.to_numeric(item["low"], errors="coerce")
    close = pd.to_numeric(item["close"], errors="coerce")
    previous_close = close.shift(1)
    true_range = pd.concat([(high - low), (high - previous_close).abs(), (low - previous_close).abs()], axis=1).max(axis=1)
    atr = true_range.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    item["atr"] = atr.shift(1)
    item["atr_pct"] = (atr / close.replace(0, np.nan)).shift(1)
    return item


def calc_adx(df: pd.DataFrame, period: int) -> pd.DataFrame:
    """Calculate shifted ADX and directional indicators.

    Args:
        df: OHLCV DataFrame with high, low, and close columns.
        period: ADX lookback period.

    Returns:
        DataFrame with adx, di_plus, and di_minus columns.

    Raises:
        ValueError: If high, low, or close is missing.
    """

    _require_ohlcv(df, ["high", "low", "close"])
    item = df.copy()
    high = pd.to_numeric(item["high"], errors="coerce")
    low = pd.to_numeric(item["low"], errors="coerce")
    close = pd.to_numeric(item["close"], errors="coerce")
    up_move = high.diff()
    down_move = -low.diff()
    plus_dm = pd.Series(np.where((up_move > down_move) & (up_move > 0), up_move, 0.0), index=item.index)
    minus_dm = pd.Series(np.where((down_move > up_move) & (down_move > 0), down_move, 0.0), index=item.index)
    previous_close = close.shift(1)
    true_range = pd.concat([(high - low), (high - previous_close).abs(), (low - previous_close).abs()], axis=1).max(axis=1)
    atr = true_range.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    plus_di = 100 * plus_dm.ewm(alpha=1 / period, adjust=False, min_periods=period).mean() / atr.replace(0, np.nan)
    minus_di = 100 * minus_dm.ewm(alpha=1 / period, adjust=False, min_periods=period).mean() / atr.replace(0, np.nan)
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    adx = dx.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    item["adx"] = adx.shift(1)
    item["di_plus"] = plus_di.shift(1)
    item["di_minus"] = minus_di.shift(1)
    return item


def calc_volume_ratio(df: pd.DataFrame, period: int) -> pd.DataFrame:
    """Calculate shifted volume ratio versus rolling average volume.

    Args:
        df: OHLCV DataFrame with volume column.
        period: Volume average lookback period.

    Returns:
        DataFrame with vol_ratio column.

    Raises:
        ValueError: If volume is missing.
    """

    _require_ohlcv(df, ["volume"])
    item = df.copy()
    volume = pd.to_numeric(item["volume"], errors="coerce")
    average_volume = volume.rolling(window=period, min_periods=period).mean()
    item["vol_ratio"] = (volume / average_volume.replace(0, np.nan)).shift(1)
    return item


def add_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Add all Sprint 1 indicator columns using configured parameters.

    Args:
        df: OHLCV DataFrame.

    Returns:
        DataFrame enriched with Bollinger, RSI, ATR, ADX, and volume columns.

    Raises:
        ValueError: If required OHLCV columns are missing.
    """

    config = _strategy_config()
    item = calc_bollinger_bands(
        df,
        period=int(config["bollinger_bands"]["period"]),
        std_dev=float(config["bollinger_bands"]["std_dev"]),
    )
    item = calc_rsi(item, period=int(config["rsi"]["period"]))
    item = calc_atr(item, period=int(config["atr"]["period"]))
    item = calc_adx(item, period=int(config["adx"]["period"]))
    item = calc_volume_ratio(item, period=int(config["volume"]["ratio_period"]))
    return item


def _signal_close(df: pd.DataFrame) -> pd.Series:
    """Return the close series used for signal evaluation.

    Args:
        df: DataFrame containing close or adj_close.

    Returns:
        Signal close Series.

    Raises:
        ValueError: If neither close nor adj_close is available.
    """

    if "close" in df.columns:
        return pd.to_numeric(df["close"], errors="coerce")
    if "adj_close" in df.columns:
        return pd.to_numeric(df["adj_close"], errors="coerce")
    raise ValueError("missing close or adj_close column")


def _earnings_allowed(df: pd.DataFrame) -> pd.Series:
    """Return a boolean Series indicating rows outside earnings blackout.

    Args:
        df: DataFrame with optional earnings_blackout column.

    Returns:
        True when entries are allowed by earnings filter.

    Raises:
        RuntimeError: Never raised.
    """

    if "earnings_blackout" not in df.columns:
        return pd.Series(True, index=df.index)
    return ~df["earnings_blackout"].fillna(False).astype(bool)


def generate_long_signals(df: pd.DataFrame) -> pd.Series:
    """Generate long mean-reversion entry signals.

    Args:
        df: DataFrame with close/adj_close, bb_lower, rsi, regime, vol_ratio, and optional earnings_blackout.

    Returns:
        Boolean Series with no NaN values.

    Raises:
        ValueError: If required signal columns are missing.
    """

    _require_ohlcv(df, ["bb_lower", "rsi", "vol_ratio", "bb_width"])
    config = _strategy_config()
    close = _signal_close(df)
    rsi = pd.to_numeric(df["rsi"], errors="coerce")
    bb_width = pd.to_numeric(df["bb_width"], errors="coerce")
    signals = (
        (close < pd.to_numeric(df["bb_lower"], errors="coerce"))
        & (rsi < float(config["rsi"]["oversold"]))
        & (pd.to_numeric(df["vol_ratio"], errors="coerce") > float(config["volume"]["min_ratio"]))
        & (bb_width.between(0.05, 0.15, inclusive="both"))
        & _earnings_allowed(df)
    )
    return signals.fillna(False).astype(bool)


def generate_short_signals(df: pd.DataFrame) -> pd.Series:
    """Return disabled short signals for the delivery-only mean-reversion system.

    Args:
        df: DataFrame with close/adj_close, bb_upper, rsi, regime, vol_ratio, and optional earnings_blackout.

    Returns:
        Boolean Series with no NaN values.

    Raises:
        ValueError: If required signal columns are missing.
    """

    _ = df
    return pd.Series(False, index=df.index, dtype=bool)


def generate_exit_signals(df: pd.DataFrame, direction: str) -> pd.Series:
    """Generate middle-band exit signals.

    Args:
        df: DataFrame with close/adj_close and bb_mid.
        direction: Trade direction, either long or short.

    Returns:
        Boolean Series with no NaN values.

    Raises:
        ValueError: If direction is unsupported or bb_mid is missing.
    """

    if direction not in {"long", "short"}:
        raise ValueError("direction must be 'long' or 'short'")
    _require_ohlcv(df, ["bb_mid"])
    close = _signal_close(df)
    mid = pd.to_numeric(df["bb_mid"], errors="coerce")
    previous_close = close.shift(1)
    previous_mid = mid.shift(1)
    if direction == "long":
        exits = (previous_close < previous_mid) & (close >= mid)
    else:
        exits = (previous_close > previous_mid) & (close <= mid)
    if "bars_held" in df.columns:
        max_hold_days = int(_strategy_config()["exits"]["max_hold_days"])
        exits = exits | (pd.to_numeric(df["bars_held"], errors="coerce") >= max_hold_days)
    return exits.fillna(False).astype(bool)


def calculate_stop_loss(df: pd.DataFrame, direction: str, entry_price: float) -> float:
    """Calculate ATR-based stop loss using the latest available ATR.

    Args:
        df: DataFrame with atr column.
        direction: Trade direction, either long or short.
        entry_price: Entry fill price.

    Returns:
        Stop-loss price.

    Raises:
        ValueError: If direction is unsupported, atr is missing, or values are invalid.
    """

    if direction not in {"long", "short"}:
        raise ValueError("direction must be 'long' or 'short'")
    _require_ohlcv(df, ["atr"])
    atr_series = pd.to_numeric(df["atr"], errors="coerce").rolling(10, min_periods=1).mean().dropna()
    if atr_series.empty or entry_price <= 0:
        raise ValueError("entry_price and atr must be positive")
    multiplier = float(_strategy_config()["atr"]["sl_atr_multiplier"])
    atr_smooth = float(atr_series.iloc[-1])
    if direction == "long":
        structure = pd.to_numeric(df["low"], errors="coerce").tail(10).min() - 0.5 * atr_smooth if "low" in df.columns else entry_price - multiplier * atr_smooth
        return float(min(entry_price - multiplier * atr_smooth, structure))
    structure = pd.to_numeric(df["high"], errors="coerce").tail(10).max() + 0.5 * atr_smooth if "high" in df.columns else entry_price + multiplier * atr_smooth
    return float(max(entry_price + multiplier * atr_smooth, structure))
