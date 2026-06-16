"""Signal calculations for the VCP trend-following sleeve."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

VCP_LOOKBACK_DAYS = 80
VCP_MIN_CONTRACTIONS = 3
FIRST_CONTRACTION_RANGE = (0.05, 0.20)
SECOND_CONTRACTION_RANGE = (0.03, 0.10)
FINAL_CONTRACTION_MAX = 0.05
MAX_DISTANCE_FROM_52W_HIGH = 0.15
BREAKOUT_VOLUME_RATIO = 1.5
BREAKOUT_CLOSE_LOCATION = 0.70
FINAL_VOLUME_DRYUP_RATIO = 0.70


@dataclass(frozen=True)
class VCPScore:
    trend_score: int
    high_position_score: int
    contraction_score: int
    volatility_score: int
    volume_dryup_score: int
    breakout_score: int
    final_vcp_score: int
    contraction_depths: list[float]
    pivot_price: float
    distance_to_pivot_percent: float
    atr_percent: float
    breakout_volume_ratio: float
    is_vcp_breakout: bool


def _score(value: bool) -> int:
    return 100 if bool(value) else 0


def add_vcp_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add shifted daily VCP features to an OHLCV frame."""

    required = {"open", "high", "low", "close", "volume"}
    missing = required.difference(df.columns)
    if missing:
        raise ValueError(f"missing required columns: {sorted(missing)}")
    item = df.copy()
    close = pd.to_numeric(item["close"], errors="coerce")
    high = pd.to_numeric(item["high"], errors="coerce")
    low = pd.to_numeric(item["low"], errors="coerce")
    volume = pd.to_numeric(item["volume"], errors="coerce")
    previous_close = close.shift(1)
    true_range = pd.concat([(high - low), (high - previous_close).abs(), (low - previous_close).abs()], axis=1).max(axis=1)
    sma20 = close.rolling(20, min_periods=20).mean()
    std20 = close.rolling(20, min_periods=20).std(ddof=0)
    bb_width = ((sma20 + 2 * std20) - (sma20 - 2 * std20)) / sma20.replace(0, np.nan)
    atr20 = true_range.rolling(20, min_periods=20).mean()
    item["sma20"] = sma20.shift(1)
    item["ema10"] = close.ewm(span=10, adjust=False, min_periods=10).mean().shift(1)
    item["ema20"] = close.ewm(span=20, adjust=False, min_periods=20).mean().shift(1)
    sma150_raw = close.rolling(150, min_periods=150).mean()
    item["sma150"] = sma150_raw.shift(1)
    item["sma150_20d_ago"] = sma150_raw.shift(21)
    item["sma150_slope_positive"] = item["sma150"] > item["sma150_20d_ago"]
    item["sma200"] = close.rolling(200, min_periods=200).mean().shift(1)
    item["week52_high"] = high.rolling(252, min_periods=126).max().shift(1)
    item["distance_from_52w_high"] = ((item["week52_high"] - close) / item["week52_high"].replace(0, np.nan)).shift(1)
    item["high20"] = high.rolling(20, min_periods=20).max().shift(1)
    item["low20"] = low.rolling(20, min_periods=20).min().shift(1)
    item["low50"] = low.rolling(50, min_periods=20).min().shift(1)
    item["pivot_tightness_10d"] = ((high.rolling(10, min_periods=10).max() - low.rolling(10, min_periods=10).min()) / close.replace(0, np.nan)).shift(1)
    item["bb_width"] = bb_width.shift(1)
    item["bb_width_60d_median"] = bb_width.rolling(60, min_periods=40).median().shift(1)
    item["atr20"] = atr20.shift(1)
    item["atr_pct_20d"] = (atr20 / close.replace(0, np.nan) * 100.0).shift(1)
    item["atr_pct_20d_20d_ago"] = (atr20 / close.replace(0, np.nan) * 100.0).shift(21)
    item["avg_volume_20d"] = volume.rolling(20, min_periods=20).mean().shift(1)
    item["avg_volume_60d"] = volume.rolling(60, min_periods=40).mean().shift(1)
    item["avg_volume_last5"] = volume.rolling(5, min_periods=5).mean().shift(1)
    item["avg_volume_previous20"] = volume.shift(6).rolling(20, min_periods=20).mean()
    item["avg_daily_turnover_20d"] = (close * volume).rolling(20, min_periods=20).mean().shift(1)
    return item


def _contractions(df: pd.DataFrame, lookback: int = VCP_LOOKBACK_DAYS) -> tuple[list[float], float]:
    window = df.tail(lookback).copy()
    if len(window) < 30:
        return [], np.nan
    high = pd.to_numeric(window["high"], errors="coerce").to_numpy(dtype=float)
    low = pd.to_numeric(window["low"], errors="coerce").to_numpy(dtype=float)
    close = pd.to_numeric(window["close"], errors="coerce").to_numpy(dtype=float)
    pivots: list[tuple[str, int, float]] = []
    for idx in range(2, len(window) - 2):
        if high[idx] >= max(high[idx - 2 : idx + 3]):
            pivots.append(("peak", idx, high[idx]))
        elif low[idx] <= min(low[idx - 2 : idx + 3]):
            pivots.append(("trough", idx, low[idx]))
    depths: list[float] = []
    pivot_price = np.nan
    for pos, pivot in enumerate(pivots):
        if pivot[0] != "peak":
            continue
        following = [item for item in pivots[pos + 1 :] if item[0] == "trough" and item[1] > pivot[1]]
        if not following:
            continue
        trough = following[0]
        if trough[2] < pivot[2]:
            depths.append(float((pivot[2] - trough[2]) / pivot[2]))
            pivot_price = float(pivot[2])
    if len(depths) < VCP_MIN_CONTRACTIONS:
        recent_high = float(np.nanmax(high[-20:])) if len(high) else np.nan
        recent_low = float(np.nanmin(low[-20:])) if len(low) else np.nan
        if recent_high and not np.isnan(recent_high):
            depths.append(float((recent_high - recent_low) / recent_high))
            pivot_price = recent_high
    return depths[-3:], pivot_price if not np.isnan(pivot_price) else float(np.nanmax(close[-20:]))


def score_vcp_setup(df: pd.DataFrame) -> VCPScore:
    """Return explainable VCP setup and breakout scores for the latest row."""

    required = {"close", "high", "low", "volume", "sma150", "sma200", "sma150_20d_ago", "week52_high", "atr_pct_20d", "atr_pct_20d_20d_ago", "avg_volume_20d"}
    missing = required.difference(df.columns)
    if missing:
        raise ValueError(f"missing required columns: {sorted(missing)}")
    latest = df.iloc[-1]
    close = float(latest["close"])
    high = float(latest["high"])
    low = float(latest["low"])
    volume = float(latest["volume"])
    sma150 = float(latest["sma150"])
    sma200 = float(latest["sma200"])
    sma150_20d_ago = float(latest["sma150_20d_ago"])
    week52_high = float(latest["week52_high"])
    atr_percent = float(latest["atr_pct_20d"])
    atr_percent_20d_ago = float(latest["atr_pct_20d_20d_ago"])
    avg_volume_20d = float(latest["avg_volume_20d"])
    depths, pivot = _contractions(df.iloc[:-1])
    trend_ok = close > sma150 and close > sma200 and sma150 > sma200 and sma150 > sma150_20d_ago
    distance_52w = (week52_high - close) / week52_high if week52_high > 0 else np.inf
    high_position_ok = distance_52w <= MAX_DISTANCE_FROM_52W_HIGH
    contraction_ok = False
    if len(depths) >= 3:
        c1, c2, c3 = depths[-3:]
        contraction_ok = (
            c1 > c2 > c3
            and FIRST_CONTRACTION_RANGE[0] <= c1 <= FIRST_CONTRACTION_RANGE[1]
            and SECOND_CONTRACTION_RANGE[0] <= c2 <= SECOND_CONTRACTION_RANGE[1]
            and c3 <= FINAL_CONTRACTION_MAX
        )
    volatility_ok = atr_percent < atr_percent_20d_ago
    last5 = float(latest.get("avg_volume_last5", np.nan))
    previous20 = float(latest.get("avg_volume_previous20", np.nan))
    volume_dryup_ok = last5 < FINAL_VOLUME_DRYUP_RATIO * previous20 if previous20 > 0 else False
    close_location = (close - low) / max(high - low, 1e-9)
    volume_ratio = volume / avg_volume_20d if avg_volume_20d > 0 else 0.0
    breakout_ok = close > pivot and volume_ratio >= BREAKOUT_VOLUME_RATIO and close_location >= BREAKOUT_CLOSE_LOCATION
    distance_to_pivot = (pivot - close) / pivot if pivot > 0 else np.nan
    scores = {
        "trend_score": _score(trend_ok),
        "high_position_score": _score(high_position_ok),
        "contraction_score": _score(contraction_ok),
        "volatility_score": _score(volatility_ok),
        "volume_dryup_score": _score(volume_dryup_ok),
        "breakout_score": _score(breakout_ok),
    }
    final_score = int(round(sum(scores.values()) / len(scores)))
    return VCPScore(
        **scores,
        final_vcp_score=final_score,
        contraction_depths=[float(depth) for depth in depths],
        pivot_price=float(pivot),
        distance_to_pivot_percent=float(distance_to_pivot),
        atr_percent=atr_percent,
        breakout_volume_ratio=float(volume_ratio),
        is_vcp_breakout=all(value == 100 for value in scores.values()),
    )


def generate_vcp_long_signals(df: pd.DataFrame) -> pd.Series:
    """Generate daily VCP breakout signals."""

    signals = pd.Series(False, index=df.index, dtype=bool)
    close = pd.to_numeric(df.get("close", pd.Series(index=df.index, dtype=float)), errors="coerce")
    high = pd.to_numeric(df.get("high", pd.Series(index=df.index, dtype=float)), errors="coerce")
    low = pd.to_numeric(df.get("low", pd.Series(index=df.index, dtype=float)), errors="coerce")
    volume = pd.to_numeric(df.get("volume", pd.Series(index=df.index, dtype=float)), errors="coerce")
    prefilter = (
        (close > pd.to_numeric(df.get("sma150", pd.Series(index=df.index, dtype=float)), errors="coerce"))
        & (close > pd.to_numeric(df.get("sma200", pd.Series(index=df.index, dtype=float)), errors="coerce"))
        & (pd.to_numeric(df.get("sma150", pd.Series(index=df.index, dtype=float)), errors="coerce") > pd.to_numeric(df.get("sma200", pd.Series(index=df.index, dtype=float)), errors="coerce"))
        & (pd.to_numeric(df.get("sma150", pd.Series(index=df.index, dtype=float)), errors="coerce") > pd.to_numeric(df.get("sma150_20d_ago", pd.Series(index=df.index, dtype=float)), errors="coerce"))
        & (pd.to_numeric(df.get("distance_from_52w_high", pd.Series(index=df.index, dtype=float)), errors="coerce") <= MAX_DISTANCE_FROM_52W_HIGH)
        & (pd.to_numeric(df.get("atr_pct_20d", pd.Series(index=df.index, dtype=float)), errors="coerce") < pd.to_numeric(df.get("atr_pct_20d_20d_ago", pd.Series(index=df.index, dtype=float)), errors="coerce"))
        & (pd.to_numeric(df.get("avg_volume_last5", pd.Series(index=df.index, dtype=float)), errors="coerce") < FINAL_VOLUME_DRYUP_RATIO * pd.to_numeric(df.get("avg_volume_previous20", pd.Series(index=df.index, dtype=float)), errors="coerce"))
        & (volume >= BREAKOUT_VOLUME_RATIO * pd.to_numeric(df.get("avg_volume_20d", pd.Series(index=df.index, dtype=float)), errors="coerce"))
        & (((close - low) / (high - low).replace(0, np.nan)) >= BREAKOUT_CLOSE_LOCATION)
    ).fillna(False)
    candidate_positions = np.flatnonzero(prefilter.to_numpy())
    for pos in candidate_positions:
        if pos < 260:
            continue
        try:
            signals.iloc[pos] = score_vcp_setup(df.iloc[: pos + 1]).is_vcp_breakout
        except (ValueError, OverflowError):
            signals.iloc[pos] = False
    liquid = pd.to_numeric(df.get("avg_daily_turnover_20d", pd.Series(0, index=df.index)), errors="coerce") > 20_000_000
    return (signals & liquid.fillna(False)).astype(bool)


def calculate_vcp_stop_loss(df: pd.DataFrame, entry_price: float) -> float:
    """Calculate a long VCP initial stop from base structure and ATR."""

    if entry_price <= 0:
        raise ValueError("entry_price must be positive")
    if "atr20" not in df.columns:
        raise ValueError("missing required column: atr20")
    atr = pd.to_numeric(df["atr20"], errors="coerce").dropna()
    if atr.empty:
        raise ValueError("atr20 must contain at least one valid value")
    atr_value = float(atr.iloc[-1])
    structure_low = float(pd.to_numeric(df["low"], errors="coerce").tail(20).min())
    return min(entry_price - 2.5 * atr_value, structure_low - 0.5 * atr_value)
