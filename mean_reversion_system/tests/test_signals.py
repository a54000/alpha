from __future__ import annotations

from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from mean_reversion_system.src.data.fetcher import fetch_earnings_dates, is_earnings_blackout
from mean_reversion_system.src.regime.detector import detect_regime, get_regime_history, is_valid_entry_regime
from mean_reversion_system.src.strategy.signals import (
    add_all_indicators,
    calc_adx,
    calc_atr,
    calc_bollinger_bands,
    calc_rsi,
    calc_volume_ratio,
    calculate_stop_loss,
    generate_exit_signals,
    generate_long_signals,
    generate_short_signals,
)


def make_ohlcv(close: np.ndarray, volume: int = 500_000) -> pd.DataFrame:
    index = pd.date_range("2023-01-02", periods=len(close), freq="B")
    close_series = pd.Series(close, index=index)
    return pd.DataFrame(
        {
            "open": close_series.shift(1).fillna(close_series.iloc[0]).to_numpy(),
            "high": close_series.to_numpy() + 0.5,
            "low": close_series.to_numpy() - 0.5,
            "close": close_series.to_numpy(),
            "volume": np.full(len(close_series), volume),
        },
        index=index,
    )


def test_bollinger_band_width_narrows_in_synthetic_rangebound_series():
    wide = 100 + np.sin(np.linspace(0, 12 * np.pi, 80)) * 8
    narrow = 100 + np.sin(np.linspace(0, 12 * np.pi, 80)) * 1
    close = np.concatenate([wide, narrow])
    result = calc_bollinger_bands(make_ohlcv(close), period=20, std_dev=2.0)

    assert result["bb_width"].iloc[-1] < result["bb_width"].iloc[70]


def test_rsi_is_bounded_between_zero_and_one_hundred():
    close = 100 + np.sin(np.linspace(0, 20 * np.pi, 180)) * 5
    result = calc_rsi(make_ohlcv(close), period=14)
    valid = result["rsi"].dropna()

    assert not valid.empty
    assert ((valid >= 0) & (valid <= 100)).all()


def test_indicator_at_index_t_does_not_use_price_from_t():
    close = np.full(80, 100.0)
    base = calc_bollinger_bands(make_ohlcv(close), period=20, std_dev=2.0)
    shocked = close.copy()
    shocked[40] = 160.0
    shocked_result = calc_bollinger_bands(make_ohlcv(shocked), period=20, std_dev=2.0)

    assert shocked_result["bb_mid"].iloc[40] == base["bb_mid"].iloc[40]
    assert shocked_result["bb_mid"].iloc[41] != base["bb_mid"].iloc[41]


def test_add_all_indicators_creates_expected_columns():
    close = 100 + np.sin(np.linspace(0, 14 * np.pi, 160)) * 2
    result = add_all_indicators(make_ohlcv(close))

    expected = {"bb_upper", "bb_mid", "bb_lower", "bb_width", "bb_pct_b", "rsi", "atr", "atr_pct", "adx", "di_plus", "di_minus", "vol_ratio"}
    assert expected.issubset(result.columns)
    assert result[list(expected)].iloc[80:].notna().all().all()


def test_atr_adx_and_volume_ratio_are_vectorised_outputs():
    close = np.linspace(100, 140, 120)
    df = make_ohlcv(close)
    result = calc_volume_ratio(calc_adx(calc_atr(df, period=14), period=14), period=20)

    assert result["atr"].dropna().gt(0).all()
    assert result["adx"].dropna().between(0, 100).all()
    assert result["vol_ratio"].dropna().eq(1.0).all()


def test_regime_detection_labels_synthetic_ranging_and_trending_periods():
    rng = np.random.default_rng(42)
    ranging = 100 + rng.normal(0, 0.12, 140)
    trending = np.linspace(101, 170, 140)
    df = make_ohlcv(np.concatenate([ranging, trending]))
    regimes = detect_regime(df)

    assert regimes.iloc[100:130].eq("ranging").mean() > 0.6
    assert regimes.iloc[-40:].isin(["trending_up"]).mean() > 0.6


def test_regime_history_and_single_date_check():
    rng = np.random.default_rng(42)
    ranging = 100 + rng.normal(0, 0.12, 140)
    trending = np.linspace(101, 170, 140)
    df = make_ohlcv(np.concatenate([ranging, trending]))
    history = get_regime_history(df)
    ranging_date = history.index[120]

    assert {"regime", "previous_regime", "is_transition", "transition_date"}.issubset(history.columns)
    assert history["is_transition"].sum() >= 1
    assert is_valid_entry_regime(df, ranging_date) is True


def test_earnings_blackout_uses_csv_lookup(tmp_path: Path):
    earnings_file = tmp_path / "earnings_dates.csv"
    earnings_file.write_text("symbol,date\nLTIM.NS,2024-01-20\nRELIANCE.NS,2024-02-10\n", encoding="utf-8")

    assert fetch_earnings_dates("LTIM.NS", earnings_file=earnings_file) == [date(2024, 1, 20)]
    assert is_earnings_blackout("LTIM.NS", date(2024, 1, 15), earnings_file=earnings_file) is True
    assert is_earnings_blackout("LTIM.NS", date(2024, 1, 24), earnings_file=earnings_file) is False


def test_generate_long_and_short_signals_known_conditions():
    index = pd.date_range("2024-01-01", periods=6, freq="B")
    df = pd.DataFrame(
        {
            "open": [96.0, 100.0, 113.0, 95.0, 93.0, 95.0],
            "close": [95.0, 100.0, 112.0, 94.0, 94.0, 94.0],
            "bb_lower": [96.0] * 6,
            "bb_upper": [110.0] * 6,
            "rsi": [26.0, 74.0, 73.0, 26.0, 27.0, 26.0],
            "regime": ["ranging"] * 6,
            "vol_ratio": [1.0] * 6,
            "volume": [100, 100, 200, 100, 200, 200],
            "avg_volume_20d": [100] * 6,
            "bb_width": [0.06] * 6,
            "earnings_blackout": [False, False, False, False, False, True],
        },
        index=index,
    )

    long_signals = generate_long_signals(df)
    short_signals = generate_short_signals(df)

    assert long_signals.tolist() == [True, False, False, True, True, False]
    assert short_signals.tolist() == [False, False, False, False, False, False]
    assert long_signals.iloc[:4].isna().sum() == 0


def test_generate_signals_warmup_rows_have_no_nan():
    index = pd.date_range("2024-01-01", periods=50, freq="B")
    df = pd.DataFrame(
        {
            "close": [100.0] * 50,
            "open": [99.0] * 50,
            "bb_lower": [pd.NA] * 20 + [99.0] * 30,
            "bb_upper": [pd.NA] * 20 + [101.0] * 30,
            "bb_width": [pd.NA] * 20 + [0.06] * 30,
            "rsi": [pd.NA] * 20 + [50.0] * 30,
            "regime": ["volatile"] * 20 + ["ranging"] * 30,
            "vol_ratio": [pd.NA] * 20 + [1.0] * 30,
            "volume": [100] * 50,
            "avg_volume_20d": [100] * 50,
        },
        index=index,
    )

    assert generate_long_signals(df).iloc[:50].isna().sum() == 0
    assert generate_short_signals(df).iloc[:50].isna().sum() == 0


def test_generate_exit_signals_middle_band_cross_and_time_exit():
    index = pd.date_range("2024-01-01", periods=4, freq="B")
    df = pd.DataFrame({"close": [95.0, 98.0, 101.0, 102.0], "bb_mid": [100.0, 100.0, 100.0, 100.0], "bars_held": [1, 2, 3, 10]}, index=index)

    long_exits = generate_exit_signals(df, "long")

    assert long_exits.tolist() == [False, False, True, True]


def test_calculate_stop_loss_uses_atr_multiplier():
    df = pd.DataFrame({"atr": [4.0]}, index=pd.date_range("2024-01-01", periods=1))

    assert calculate_stop_loss(df, "long", 100.0) == 91.0
    assert calculate_stop_loss(df, "short", 100.0) == 109.0
