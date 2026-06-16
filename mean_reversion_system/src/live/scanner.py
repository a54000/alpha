"""Live scanner for Disha paper trading."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Iterable

import pandas as pd
from sqlalchemy import text

from mean_reversion_system.src.data.db_connector import get_engine
from mean_reversion_system.src.strategy.signals import add_all_indicators, calculate_stop_loss, generate_long_signals
from mean_reversion_system.src.strategy.sizing import apply_position_limits, calculate_position_size
from mean_reversion_system.src.strategy.vcp_signals import add_vcp_features, calculate_vcp_stop_loss, generate_vcp_long_signals, score_vcp_setup

CAPITAL = 1_000_000.0
V4B_ALLOC = 0.15
VCP_ALLOC = 0.80
RISK_PER_TRADE = 0.01
MAX_POSITION_PCT = 0.15


@dataclass(frozen=True)
class ScanResult:
    symbol: str
    signal_type: str
    entry_price: float
    sl_price: float
    target_price: float
    position_size: int
    regime_score: float
    bb_width: float
    rsi: float
    adx: float
    rationale: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _daily_bars(symbols: Iterable[str] | None, as_of_date: date | None) -> pd.DataFrame:
    symbol_filter = ""
    params: dict[str, object] = {}
    if symbols:
        symbol_list = list(symbols)
        symbol_filter = "AND symbol = ANY(:symbols)"
        params["symbols"] = symbol_list
    if as_of_date is not None:
        date_clause = "AND (datetime AT TIME ZONE 'Asia/Kolkata')::date <= :as_of_date"
        params["as_of_date"] = as_of_date
    else:
        date_clause = ""
    query = f"""
        WITH latest AS (
            SELECT max((datetime AT TIME ZONE 'Asia/Kolkata')::date) AS max_date
            FROM public.ohlcv_15min
            WHERE symbol NOT IN ('NIFTY50', 'BANKNIFTY') AND volume > 0
            {date_clause}
        ),
        bars AS (
            SELECT
                symbol,
                (datetime AT TIME ZONE 'Asia/Kolkata')::date AS session_date,
                datetime,
                open::double precision AS open,
                high::double precision AS high,
                low::double precision AS low,
                close::double precision AS close,
                volume::bigint AS volume
            FROM public.ohlcv_15min, latest
            WHERE symbol NOT IN ('NIFTY50', 'BANKNIFTY')
              {symbol_filter}
              AND volume > 0
              AND (datetime AT TIME ZONE 'Asia/Kolkata')::date >= latest.max_date - INTERVAL '420 days'
              AND (datetime AT TIME ZONE 'Asia/Kolkata')::date <= latest.max_date
        ),
        ranked AS (
            SELECT *,
                   row_number() OVER (PARTITION BY symbol, session_date ORDER BY datetime ASC) AS rn_open,
                   row_number() OVER (PARTITION BY symbol, session_date ORDER BY datetime DESC) AS rn_close
            FROM bars
        )
        SELECT symbol, session_date AS date,
               max(open) FILTER (WHERE rn_open = 1) AS open,
               max(high) AS high,
               min(low) AS low,
               max(close) FILTER (WHERE rn_close = 1) AS close,
               sum(volume) AS volume
        FROM ranked
        GROUP BY symbol, session_date
        ORDER BY symbol, session_date
    """
    frame = pd.read_sql(text(query), get_engine(), params=params)
    if not frame.empty:
        frame["date"] = pd.to_datetime(frame["date"]).dt.date
    return frame


def _vcp_market_gate() -> tuple[bool, str]:
    labels_path = Path(__file__).resolve().parents[2] / "results" / "sprint_2_1" / "daily_regime_labels.csv"
    if not labels_path.exists():
        return False, "market labels unavailable"
    labels = pd.read_csv(labels_path)
    if len(labels) < 61:
        return False, "insufficient market labels"
    latest = labels.iloc[-1]
    nifty = pd.to_numeric(labels["nifty_close"], errors="coerce")
    ret60 = float(nifty.iloc[-1] / nifty.shift(60).iloc[-1] - 1)
    constructive = bool(
        latest["regime_label"] == "UPTREND"
        or (
            latest["regime_label"] == "RANGING"
            and float(latest["nifty_close"]) > float(latest["sma200"])
            and float(latest["di_plus"]) >= float(latest["di_minus"])
        )
    )
    return bool(constructive and ret60 > 0), f"{latest['regime_label']}, NIFTY60D={ret60:.2%}"


def _scan_symbol(symbol: str, bars: pd.DataFrame, market_gate: bool, market_text: str) -> list[ScanResult]:
    results: list[ScanResult] = []
    if len(bars) < 260:
        return results
    latest_close = float(bars.iloc[-1]["close"])
    mr = add_all_indicators(bars)
    if bool(generate_long_signals(mr).iloc[-1]):
        history = mr.dropna(subset=["atr"])
        try:
            stop = calculate_stop_loss(history, "long", latest_close)
        except ValueError:
            stop = latest_close * 0.95
        target = float(mr.iloc[-1].get("bb_mid", latest_close * 1.03))
        qty = apply_position_limits(calculate_position_size(CAPITAL * V4B_ALLOC, latest_close, stop, RISK_PER_TRADE), CAPITAL * V4B_ALLOC, latest_close, MAX_POSITION_PCT)
        results.append(
            ScanResult(
                symbol=symbol,
                signal_type="V4B_BUY",
                entry_price=latest_close,
                sl_price=stop,
                target_price=target,
                position_size=qty,
                regime_score=1.0,
                bb_width=float(mr.iloc[-1].get("bb_width", 0.0)),
                rsi=float(mr.iloc[-1].get("rsi", 0.0)),
                adx=float(mr.iloc[-1].get("adx", 0.0)),
                rationale=f"Mean reversion setup: close below lower band, RSI oversold. Market: {market_text}",
            )
        )
    vcp = add_vcp_features(bars)
    if market_gate and bool(generate_vcp_long_signals(vcp).iloc[-1]):
        score = score_vcp_setup(vcp)
        try:
            stop = calculate_vcp_stop_loss(vcp.iloc[:-1], latest_close)
        except ValueError:
            stop = latest_close * 0.92
        qty = apply_position_limits(calculate_position_size(CAPITAL * VCP_ALLOC, latest_close, stop, RISK_PER_TRADE), CAPITAL * VCP_ALLOC, latest_close, MAX_POSITION_PCT)
        results.append(
            ScanResult(
                symbol=symbol,
                signal_type="VCP_BUY",
                entry_price=latest_close,
                sl_price=stop,
                target_price=latest_close + 3 * (latest_close - stop),
                position_size=qty,
                regime_score=score.final_vcp_score / 100,
                bb_width=float(vcp.iloc[-1].get("bb_width", 0.0)),
                rsi=0.0,
                adx=0.0,
                rationale=f"VCP breakout: score {score.final_vcp_score}, pivot {score.pivot_price:.2f}. Market: {market_text}",
            )
        )
    return results


def scan_universe(universe: Iterable[str] | None = None, as_of_date: date | None = None) -> list[ScanResult]:
    """Scan symbols and return actionable paper-trading setups."""

    daily = _daily_bars(universe, as_of_date)
    market_gate, market_text = _vcp_market_gate()
    results: list[ScanResult] = []
    for symbol, group in daily.groupby("symbol", sort=False):
        bars = group.sort_values("date").reset_index(drop=True)
        results.extend(_scan_symbol(str(symbol), bars, market_gate, market_text))
    return results


def schedule_daily_scan(callback, timezone: str = "Asia/Kolkata") -> BackgroundScheduler:
    """Schedule a 16:00 IST scan callback and return the scheduler."""

    try:
        from apscheduler.schedulers.background import BackgroundScheduler
    except ImportError as exc:
        raise RuntimeError("APScheduler is required for scheduled live scans") from exc
    scheduler = BackgroundScheduler(timezone=timezone)
    scheduler.add_job(callback, "cron", hour=16, minute=0, id="disha_daily_scan", replace_existing=True)
    scheduler.start()
    return scheduler
