from __future__ import annotations

from datetime import date

import pytest

from mean_reversion_system.src.live.executor import PaperPortfolio
from mean_reversion_system.src.live.monitor import format_signal_alert, send_signal_alert
from mean_reversion_system.src.live.scanner import ScanResult, schedule_daily_scan


def make_scan_result() -> ScanResult:
    return ScanResult(
        symbol="LTIM",
        signal_type="V4B_BUY",
        entry_price=4820.0,
        sl_price=4650.0,
        target_price=4950.0,
        position_size=42,
        regime_score=1.0,
        bb_width=0.08,
        rsi=28.0,
        adx=14.0,
        rationale="Ranging setup",
    )


def test_scan_result_schema_and_alert_format():
    result = make_scan_result()
    payload = result.to_dict()

    assert payload["symbol"] == "LTIM"
    assert "entry_price" in payload
    assert "SL: Rs 4,650.00" in format_signal_alert(result)


def test_paper_portfolio_persists_and_closes_position(tmp_path):
    db = tmp_path / "paper.sqlite"
    portfolio = PaperPortfolio(db_path=db, initial_capital=100_000)
    trade_id = portfolio.open_position(make_scan_result(), entry_date=date(2026, 1, 1))

    reopened = PaperPortfolio(db_path=db, initial_capital=100_000)
    summary = reopened.get_portfolio_summary()
    closed = reopened.check_exits({"LTIM": 4960.0}, item_date=date(2026, 1, 2))

    assert trade_id
    assert summary["open_positions"] == 1
    assert len(closed) == 1
    assert reopened.get_portfolio_summary()["open_positions"] == 0


def test_telegram_alert_noops_without_env(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)

    assert send_signal_alert(make_scan_result()) is False


def test_schedule_daily_scan_returns_scheduler():
    try:
        scheduler = schedule_daily_scan(lambda: None)
    except RuntimeError:
        pytest.skip("APScheduler not installed in current environment")
    try:
        jobs = scheduler.get_jobs()
        assert any(job.id == "disha_daily_scan" for job in jobs)
    finally:
        scheduler.shutdown(wait=False)
