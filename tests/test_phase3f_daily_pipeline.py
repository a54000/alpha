from __future__ import annotations

import importlib.util
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text


REPO_ROOT = Path(__file__).resolve().parents[1]


def load_script(name: str):
    spec = importlib.util.spec_from_file_location(name, REPO_ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_missing_window_starts_after_latest_candle_not_full_history():
    sync = load_script("sync_angel_daily_data")
    latest = datetime(2026, 6, 11, 15, 15)
    now = datetime(2026, 6, 12, 16, 0, tzinfo=timezone.utc)

    start, end = sync.missing_window(latest, now, bootstrap_lookback_days=5, override_from=None)

    assert start == datetime(2026, 6, 11, 15, 30, tzinfo=timezone.utc)
    assert end == now


def test_missing_window_bootstraps_recent_only_when_symbol_has_no_history():
    sync = load_script("sync_angel_daily_data")
    now = datetime(2026, 6, 12, 16, 0, tzinfo=timezone.utc)

    start, _end = sync.missing_window(None, now, bootstrap_lookback_days=5, override_from=None)

    assert start == datetime(2026, 6, 7, 16, 0, tzinfo=timezone.utc)


def test_iter_chunks_splits_incremental_request_ranges():
    sync = load_script("sync_angel_daily_data")
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    end = datetime(2026, 1, 5, tzinfo=timezone.utc)

    chunks = sync.iter_chunks(start, end, chunk_days=2)

    assert chunks == [
        (datetime(2026, 1, 1, tzinfo=timezone.utc), datetime(2026, 1, 3, tzinfo=timezone.utc)),
        (datetime(2026, 1, 3, 0, 15, tzinfo=timezone.utc), datetime(2026, 1, 5, tzinfo=timezone.utc)),
    ]


def test_normalize_candles_deduplicates_symbol_datetime_rows():
    sync = load_script("sync_angel_daily_data")
    candles = [
        ["2026-06-12T09:15:00+05:30", 10, 12, 9, 11, 1000],
        ["2026-06-12T09:15:00+05:30", 10, 12, 9, 11, 1000],
        ["2026-06-12T09:30:00+05:30", 11, 13, 10, 12, 1100],
    ]

    rows = sync.normalize_candles("AAA", candles)

    assert len(rows) == 2
    assert rows[0]["symbol"] == "AAA"
    assert rows[0]["datetime"].isoformat() == "2026-06-12T09:15:00+05:30"


def test_daily_cycle_builds_ordered_steps_and_paper_update_is_opt_in():
    runner = load_script("run_daily_paper_cycle")
    args = runner.parse_args(
        [
            "--cycle-date",
            "2026-06-12",
            "--skip-sync",
            "--dry-run",
        ]
    )

    steps = runner.build_steps(args)

    assert [step.name for step in steps] == [
        "validate_latest_angel_data",
        "update_clean_daily_bars",
        "refresh_features",
        "compute_scores",
        "generate_recommendations",
    ]


def test_daily_cycle_adds_paper_update_when_portfolio_id_is_set():
    runner = load_script("run_daily_paper_cycle")
    args = runner.parse_args(
        [
            "--cycle-date",
            "2026-06-12",
            "--skip-sync",
            "--portfolio-id",
            "7",
            "--dry-run",
        ]
    )

    steps = runner.build_steps(args)

    assert steps[-1].name == "update_paper_portfolio"
    assert "--portfolio-id" in steps[-1].command
    assert "7" in steps[-1].command


def test_daily_cycle_dry_run_does_not_execute_subprocess(monkeypatch):
    runner = load_script("run_daily_paper_cycle")
    called = False

    def fake_run(*_args, **_kwargs):
        nonlocal called
        called = True
        raise AssertionError("subprocess.run should not be called in dry-run mode")

    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    step = runner.CycleStep("example", ["python", "does_not_run.py"])

    result = runner.run_step(step, dry_run=True)

    assert result.status == "dry_run"
    assert result.returncode == 0
    assert called is False


def test_sync_parse_args_supports_dry_run_contract():
    sync = load_script("sync_angel_daily_data")

    args = sync.parse_args(["--dry-run", "--symbol-limit", "5"])

    assert args.dry_run is True
    assert args.symbol_limit == 5


def test_sync_parse_args_supports_catch_up_window():
    sync = load_script("sync_angel_daily_data")

    args = sync.parse_args(["--from-date", "2026-06-12", "--to-date", "2026-06-13T16:00:00+05:30"])

    assert args.from_date == "2026-06-12"
    assert args.to_date == "2026-06-13T16:00:00+05:30"


def test_sync_parse_args_supports_symbol_allowlist():
    sync = load_script("sync_angel_daily_data")

    args = sync.parse_args(["--symbols", "WIPRO,TATASTEEL"])

    assert sync.parse_symbol_allowlist(args.symbols) == {"WIPRO", "TATASTEEL"}


def local_tmp_dir(name: str) -> Path:
    path = REPO_ROOT / ".pytest_tmp_phase5_11" / name
    path.mkdir(parents=True, exist_ok=True)
    return path


def test_token_map_csv_loads_symbol_token_exchange():
    sync = load_script("sync_angel_daily_data")
    token_map = local_tmp_dir("valid") / "angel_symbol_token_map.csv"
    token_map.write_text("symbol,angel_token,exchange\nABC,12345,NSE\n", encoding="utf-8")

    loaded = sync.load_token_map_from_csv(str(token_map))

    assert loaded == {"ABC": ("12345", "NSE")}


def test_token_map_csv_rejects_duplicates():
    sync = load_script("sync_angel_daily_data")
    token_map = local_tmp_dir("duplicates") / "angel_symbol_token_map.csv"
    token_map.write_text(
        "symbol,angel_token,exchange\nABC,12345,NSE\nABC,54321,NSE\nXYZ,12345,NSE\n",
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="duplicate symbols"):
        sync.load_token_map_from_csv(str(token_map))


def test_missing_token_detection_reports_unmapped_symbols():
    sync = load_script("sync_angel_daily_data")
    symbols = [
        sync.TrackedSymbol(symbol="ABC", token="12345"),
        sync.TrackedSymbol(symbol="XYZ", token=None),
    ]

    assert sync.symbols_missing_tokens(symbols) == ["XYZ"]


def test_update_progress_uses_legacy_schema_when_present(monkeypatch):
    sync = load_script("sync_angel_daily_data")
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    called = []

    def fake_legacy(_connection, result):
        called.append(("legacy", result.symbol))

    def fake_v2(_connection, _result):
        raise AssertionError("v2 progress updater should not be used")

    monkeypatch.setattr(sync, "update_progress_legacy", fake_legacy)
    monkeypatch.setattr(sync, "update_progress_v2", fake_v2)

    with engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE fetch_progress (
                    symbol text PRIMARY KEY,
                    token text,
                    status text,
                    last_fetched_at text,
                    candles_count integer,
                    error_msg text
                )
                """
            )
        )
        sync.update_progress(connection, sync.SymbolSyncResult("ABC", "12345", None, "2026-06-12", "2026-06-12"))

    assert called == [("legacy", "ABC")]
