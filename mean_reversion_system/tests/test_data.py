from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

import pandas as pd

from mean_reversion_system.src.data import fetcher
from mean_reversion_system.src.data.db_connector import _database_url
from mean_reversion_system.src.data.quality_report import run_full_quality_audit
from mean_reversion_system.src.data.bhavcopy import cross_validate_prices
from mean_reversion_system.src.data.preprocessor import build_signal_ready_df, validate_data_quality, add_adjusted_prices, clean_ohlcv, clean_15min, resample_to_daily, resample_to_weekly
from mean_reversion_system.src.data.universe_history import load_universe_snapshot, document_survivorship_limitation


def test_fetch_universe_returns_initial_midcap_seed():
    symbols = fetcher.fetch_universe(Path("config") / "universe.yaml")

    assert len(symbols) == 80
    assert "LTIM.NS" in symbols
    assert all(symbol.endswith(".NS") for symbol in symbols)


def test_fetch_ohlcv_returns_correct_columns_date_range_and_uses_cache(tmp_path, monkeypatch):
    calls = {"count": 0}
    index = pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-04"])
    raw = pd.DataFrame(
        {
            "Open": [100.0, 101.0, 102.0],
            "High": [102.0, 103.0, 104.0],
            "Low": [99.0, 100.0, 101.0],
            "Close": [101.0, 102.0, 103.0],
            "Adj Close": [100.5, 101.5, 102.5],
            "Volume": [200000, 210000, 220000],
        },
        index=index,
    )

    class FakeYFinance:
        @staticmethod
        def download(*args, **kwargs):
            calls["count"] += 1
            return raw

    monkeypatch.setitem(__import__("sys").modules, "yfinance", FakeYFinance)

    first = fetcher.fetch_ohlcv("LTIM.NS", date(2024, 1, 2), date(2024, 1, 5), cache_dir=tmp_path)
    second = fetcher.fetch_ohlcv("LTIM.NS", date(2024, 1, 2), date(2024, 1, 5), cache_dir=tmp_path)

    assert calls["count"] == 1
    assert list(first.columns) == ["open", "high", "low", "close", "volume"]
    assert first.index.min() == pd.Timestamp("2024-01-02")
    assert first.index.max() == pd.Timestamp("2024-01-04")
    assert first["close"].iloc[0] == 100.5
    assert second.equals(first)
    assert list(tmp_path.glob("*.parquet"))


def test_clean_ohlcv_handles_missing_values_and_bad_ranges():
    df = pd.DataFrame(
        {
            "open": [100.0, None, 105.0, 106.0],
            "high": [101.0, 103.0, 104.0, 107.0],
            "low": [99.0, 101.0, 106.0, 105.0],
            "close": [100.5, 102.0, 105.5, None],
            "volume": [1000, None, -5, 0],
        },
        index=pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04"]),
    )

    cleaned = clean_ohlcv(df)

    assert cleaned[["open", "high", "low", "close"]].isna().sum().sum() == 0
    assert (cleaned["volume"] >= 0).all()
    assert (cleaned["high"] >= cleaned[["open", "close"]].max(axis=1)).all()
    assert (cleaned["low"] <= cleaned[["open", "close"]].min(axis=1)).all()


def test_add_adjusted_prices_uses_adjustment_factor():
    df = pd.DataFrame(
        {"open": [100.0], "high": [110.0], "low": [90.0], "close": [100.0], "adj_close": [50.0]},
        index=pd.to_datetime(["2024-01-01"]),
    )

    adjusted = add_adjusted_prices(df)

    assert adjusted["adj_open"].iloc[0] == 50.0
    assert adjusted["adj_high"].iloc[0] == 55.0
    assert adjusted["adj_low"].iloc[0] == 45.0


def test_data_quality_validator_catches_known_bad_patterns():
    df = pd.DataFrame(
        {
            "open": [100.0, -1.0, 102.0],
            "high": [101.0, 103.0, 101.0],
            "low": [99.0, 104.0, 100.0],
            "close": [100.5, 102.0, None],
            "volume": [1000, 0, 2000],
        },
        index=pd.to_datetime(["2024-01-01", "2024-01-01", "2024-01-03"]),
    )

    report = validate_data_quality(df)

    assert report["rows"] == 3
    assert report["null_rows"] == 1
    assert report["zero_volume_rows"] == 1
    assert report["invalid_price_rows"] >= 1
    assert report["duplicate_dates"] == 1
    assert report["is_valid"] is False


def test_survivorship_universe_excludes_removed_symbol():
    old_symbols = load_universe_snapshot(date(2019, 1, 1))
    new_symbols = load_universe_snapshot(date(2024, 1, 1))

    assert "YESBANK.NS" in old_symbols
    assert "YESBANK.NS" not in new_symbols


def test_universe_snapshot_raises_on_prehistory_date():
    try:
        load_universe_snapshot(date(2015, 1, 1))
    except ValueError as exc:
        assert "before earliest snapshot" in str(exc)
    else:
        raise AssertionError("expected ValueError for prehistory date")


def test_dual_price_adjusted_can_differ_from_raw_for_split_stock(tmp_path, monkeypatch):
    index = pd.to_datetime(["2018-09-03", "2018-09-04", "2018-09-05"])

    def fake_download(symbol, start_date, end_date, auto_adjust):
        close = [700.0, 705.0, 710.0] if auto_adjust else [1400.0, 1410.0, 1420.0]
        return pd.DataFrame(
            {"Open": close, "High": close, "Low": close, "Close": close, "Volume": [1_000_000] * 3},
            index=index,
        )

    monkeypatch.setattr(fetcher, "_download_yfinance", fake_download)
    adjusted, raw = fetcher.fetch_dual_price_series("INFY.NS", date(2018, 9, 1), date(2018, 9, 6), cache_dir=tmp_path)

    assert not adjusted["close"].equals(raw["close"])


def test_build_signal_ready_df_column_names(monkeypatch):
    index = pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03"])
    adjusted = pd.DataFrame({"close": [100.0, 101.0, 102.0]}, index=index)
    raw = pd.DataFrame({"open": [100.5, 101.5, 102.5], "close": [100.8, 101.8, 102.8], "volume": [10, 20, 30]}, index=index)

    monkeypatch.setattr("mean_reversion_system.src.data.preprocessor.fetch_dual_price_series", lambda *args, **kwargs: (adjusted, raw))
    monkeypatch.setattr("mean_reversion_system.src.data.preprocessor.get_split_dates", lambda symbol: [])

    result = build_signal_ready_df("ABC.NS", date(2024, 1, 1), date(2024, 1, 4))

    assert list(result.columns) == ["adj_close", "raw_open", "raw_close", "volume"]


def test_warm_up_buffer_fetch_start():
    result = fetcher.get_fetch_start(date(2021, 9, 1))

    assert result == date(2021, 6, 14)


def test_data_quality_zero_volume_flagged():
    df = pd.DataFrame(
        {"open": [100.0], "high": [101.0], "low": [99.0], "close": [100.0], "volume": [0]},
        index=pd.to_datetime(["2024-01-01"]),
    )

    report = validate_data_quality(df, symbol="ABC.NS")

    assert report.zero_volume_days == 1


def test_data_quality_ohlc_integrity():
    df = pd.DataFrame(
        {"open": [100.0], "high": [95.0], "low": [99.0], "close": [100.0], "volume": [1000]},
        index=pd.to_datetime(["2024-01-01"]),
    )

    report = validate_data_quality(df, symbol="ABC.NS")

    assert report.ohlc_errors == 1
    assert report.is_usable is True


def test_nifty50_data_fetches_and_caches(tmp_path, monkeypatch):
    calls = {"count": 0}
    index = pd.to_datetime(["2024-01-01", "2024-01-02"])

    def fake_download(symbol, start_date, end_date, auto_adjust):
        calls["count"] += 1
        return pd.DataFrame(
            {"Open": [100.0, 101.0], "High": [102.0, 103.0], "Low": [99.0, 100.0], "Close": [101.0, 102.0], "Volume": [1000, 1100]},
            index=index,
        )

    monkeypatch.setattr(fetcher, "_download_yfinance", fake_download)

    first = fetcher.fetch_index_data("^NSEI", date(2024, 1, 1), date(2024, 1, 3), cache_dir=tmp_path)
    second = fetcher.fetch_index_data("^NSEI", date(2024, 1, 1), date(2024, 1, 3), cache_dir=tmp_path)

    assert calls["count"] == 1
    assert {"open", "high", "low", "close", "volume"}.issubset(first.columns)
    assert second.equals(first)


def test_bhavcopy_cross_validation_detects_match(monkeypatch):
    index = pd.to_datetime(["2024-01-01"])
    raw = pd.DataFrame({"open": [100.0], "high": [101.0], "low": [99.0], "close": [100.0], "volume": [1000]}, index=index)
    bhav = pd.DataFrame({"symbol": ["ABC"], "open": [100.0], "high": [101.0], "low": [99.0], "close": [100.1], "volume": [1000]})

    monkeypatch.setattr("mean_reversion_system.src.data.bhavcopy.fetch_ohlcv", lambda *args, **kwargs: raw)
    monkeypatch.setattr("mean_reversion_system.src.data.bhavcopy.download_bhavcopy", lambda trade_date: bhav)

    result = cross_validate_prices("ABC.NS", date(2024, 1, 1), date(2024, 1, 1), tolerance_pct=0.005)

    assert result.match_rate == 1.0
    assert result.max_divergence_pct < 0.005


def test_db_connector_builds_url_from_env(monkeypatch):
    config = {
        "name": "angel_data",
        "host_env": "DB_HOST",
        "port_env": "DB_PORT",
        "user_env": "DB_USER",
        "password_env": "DB_PASSWORD",
        "url_env": "MISSING_URL",
    }
    monkeypatch.setenv("DB_HOST", "localhost")
    monkeypatch.setenv("DB_PORT", "5432")
    monkeypatch.setenv("DB_USER", "postgres")
    monkeypatch.setenv("DB_PASSWORD", "secret")

    assert _database_url(config) == "postgresql+psycopg2://postgres:secret@localhost:5432/angel_data"


def test_fetch_15min_uses_parameterized_query_and_cache(tmp_path, monkeypatch):
    calls = {"count": 0}
    raw = pd.DataFrame(
        {
            "datetime": pd.to_datetime(["2024-01-01 09:15", "2024-01-01 09:30"]),
            "open": [100.0, 101.0],
            "high": [101.0, 102.0],
            "low": [99.0, 100.0],
            "close": [100.5, 101.5],
            "volume": [1000, 1100],
        }
    )

    def fake_read_sql_query(query, engine, params=None):
        calls["count"] += 1
        assert ":symbol" in str(query)
        assert params["symbol"] == "ABC"
        return raw

    monkeypatch.setattr(pd, "read_sql_query", fake_read_sql_query)
    first = fetcher.fetch_15min("ABC", datetime(2024, 1, 1, 9, 15), datetime(2024, 1, 1, 15, 30), cache_dir=tmp_path, engine=object())
    second = fetcher.fetch_15min("ABC", datetime(2024, 1, 1, 9, 15), datetime(2024, 1, 1, 15, 30), cache_dir=tmp_path, engine=object())

    assert calls["count"] == 1
    assert str(first.index.tz) == "Asia/Kolkata"
    assert second.equals(first)


def test_fetch_active_universe_filters_known_bad_and_completeness(tmp_path, monkeypatch):
    rows = pd.DataFrame(
        {
            "symbol": ["ABC", "WIPRO", "THIN"],
            "bars": [25000, 25000, 21000],
            "first_bar": [date(2021, 6, 14), date(2021, 6, 14), date(2021, 6, 14)],
            "last_bar": [date(2024, 6, 14), date(2024, 6, 14), date(2026, 6, 1)],
        }
    )

    monkeypatch.setattr(pd, "read_sql_query", lambda *args, **kwargs: rows)
    result = fetcher.fetch_active_universe(min_bars=20000, min_completeness=0.70, cache_dir=tmp_path, engine=object())

    assert result == ["ABC"]


def test_clean_15min_drops_bad_bars_marks_partial_and_converts_utc():
    index = pd.date_range("2024-01-03 09:15", periods=5, freq="15min")
    df = pd.DataFrame(
        {
            "open": [100.0, 0.0, 102.0, 103.0, 104.0],
            "high": [101.0, 102.0, 100.0, 104.0, 105.0],
            "low": [99.0, 100.0, 101.0, 102.0, 103.0],
            "close": [100.5, 101.0, 102.0, 103.5, 104.5],
            "volume": [1000, 1000, 1000, 0, 1000],
        },
        index=index,
    )

    cleaned = clean_15min(df, "ABC")

    assert len(cleaned) == 2
    assert str(cleaned.index.tz) == "UTC"
    assert cleaned["is_partial_session"].all()


def test_resample_to_daily_excludes_closing_auction_from_range():
    index = pd.to_datetime(["2024-01-01 09:15", "2024-01-01 15:00", "2024-01-01 15:15", "2024-01-01 15:30"]).tz_localize("Asia/Kolkata").tz_convert("UTC")
    df = pd.DataFrame(
        {
            "open": [100.0, 101.0, 102.0, 103.0],
            "high": [101.0, 110.0, 999.0, 998.0],
            "low": [99.0, 95.0, 1.0, 2.0],
            "close": [100.5, 109.0, 103.0, 104.0],
            "volume": [100, 200, 300, 400],
            "is_partial_session": [False, False, False, False],
        },
        index=index,
    )

    daily = resample_to_daily(df)

    assert daily["open"].iloc[0] == 100.0
    assert daily["high"].iloc[0] == 110.0
    assert daily["low"].iloc[0] == 95.0
    assert daily["close"].iloc[0] == 104.0
    assert daily["volume"].iloc[0] == 1000


def test_resample_to_weekly_uses_friday_alignment():
    daily = pd.DataFrame(
        {
            "open": [100.0, 101.0, 102.0],
            "high": [101.0, 104.0, 103.0],
            "low": [99.0, 100.0, 98.0],
            "close": [100.5, 103.0, 102.0],
            "volume": [1000, 2000, 3000],
        },
        index=pd.to_datetime(["2024-01-01", "2024-01-03", "2024-01-05"]),
    )

    weekly = resample_to_weekly(daily)

    assert weekly.index[0] == pd.Timestamp("2024-01-05")
    assert weekly["open"].iloc[0] == 100.0
    assert weekly["high"].iloc[0] == 104.0
    assert weekly["volume"].iloc[0] == 6000


def test_survivorship_limitation_documented():
    limitation = document_survivorship_limitation()

    assert limitation["bias_type"] == "partial_survivorship"
    assert "RCOM" in limitation["missing_examples"]


def test_quality_report_uses_db_side_checks(monkeypatch):
    responses = [
        pd.DataFrame({"symbol": ["ABC"], "count": [2]}),
        pd.DataFrame({"symbol": ["ABC"], "count": [1]}),
        pd.DataFrame({"symbol": ["THIN"], "count": [100]}),
        pd.DataFrame({"symbol": ["ABC"], "count": [3]}),
        pd.DataFrame({"symbol": ["LATE"], "first_bar": [date(2022, 1, 1)]}),
        pd.DataFrame({"count": [0]}),
        pd.DataFrame({"symbol": ["ABC"], "bars": [25000], "first_bar": [date(2021, 6, 14)], "last_bar": [date(2024, 6, 14)]}),
    ]

    def fake_read_sql_query(*args, **kwargs):
        return responses.pop(0)

    monkeypatch.setattr(pd, "read_sql_query", fake_read_sql_query)
    report = run_full_quality_audit(engine=object())

    assert report.broken_ohlc == {"ABC": 2}
    assert report.zero_volume == {"ABC": 1}
    assert report.partial_sessions == {"ABC": 3}
    assert report.late_start_symbols == ["LATE"]
    assert report.timezone_bad_rows == 0
