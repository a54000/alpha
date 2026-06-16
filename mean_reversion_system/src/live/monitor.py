"""Monitoring and Telegram alerts for Disha paper trading."""

from __future__ import annotations

import os
from typing import Mapping

import requests

from mean_reversion_system.src.live.scanner import ScanResult


def _telegram_credentials() -> tuple[str | None, str | None]:
    return os.getenv("TELEGRAM_BOT_TOKEN"), os.getenv("TELEGRAM_CHAT_ID")


def _send_telegram(text: str) -> bool:
    token, chat_id = _telegram_credentials()
    if not token or not chat_id:
        return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    response = requests.post(url, json={"chat_id": chat_id, "text": text}, timeout=15)
    response.raise_for_status()
    return True


def format_signal_alert(scan_result: ScanResult) -> str:
    side = "BUY" if scan_result.signal_type.endswith("BUY") else scan_result.signal_type
    return (
        f"SIGNAL: {side} {scan_result.symbol} | "
        f"Entry: Rs {scan_result.entry_price:,.2f} | "
        f"SL: Rs {scan_result.sl_price:,.2f} | "
        f"Target: Rs {scan_result.target_price:,.2f} | "
        f"Size: {scan_result.position_size} shares | "
        f"Regime score: {scan_result.regime_score:.2f} | "
        f"{scan_result.rationale}"
    )


def send_signal_alert(scan_result: ScanResult) -> bool:
    """Send a formatted signal alert through Telegram."""

    return _send_telegram(format_signal_alert(scan_result))


def send_daily_summary(portfolio: Mapping[str, object]) -> bool:
    """Send an end-of-day paper portfolio summary."""

    text = (
        "DAILY SUMMARY | "
        f"Equity: Rs {float(portfolio.get('equity_estimate', 0.0)):,.2f} | "
        f"Realised P&L: Rs {float(portfolio.get('realised_pnl', 0.0)):,.2f} | "
        f"Open positions: {portfolio.get('open_positions', 0)} | "
        f"Heat: {float(portfolio.get('heat', 0.0)):.2%}"
    )
    return _send_telegram(text)

