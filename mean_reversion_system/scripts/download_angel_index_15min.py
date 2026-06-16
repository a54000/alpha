"""Download Angel SmartAPI 15-minute index candles into angel_data."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time as time_module
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
import pyotp
import requests
from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from mean_reversion_system.src.data.db_connector import get_engine

SCRIP_MASTER_URL = "https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json"
INDEX_FALLBACKS = {
    "NIFTY50": {"symbol": "NIFTY50", "name": "NIFTY 50", "token": "99926000", "exchange": "NSE"},
    "BANKNIFTY": {"symbol": "BANKNIFTY", "name": "NIFTY BANK", "token": "99926009", "exchange": "NSE"},
}


def _load_env() -> None:
    try:
        from dotenv import load_dotenv  # type: ignore

        load_dotenv(REPO / ".env")
        load_dotenv(ROOT / ".env")
    except Exception:
        return


def _parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def _smart_connect():
    _load_env()
    from SmartApi import SmartConnect

    required = ["ANGEL_API_KEY", "ANGEL_CLIENT_ID", "ANGEL_PASSWORD", "ANGEL_TOTP_SECRET"]
    missing = [key for key in required if not os.environ.get(key)]
    if missing:
        raise EnvironmentError(f"missing Angel SmartAPI environment variables: {', '.join(missing)}")
    smart = SmartConnect(api_key=os.environ["ANGEL_API_KEY"])
    totp = pyotp.TOTP(os.environ["ANGEL_TOTP_SECRET"].strip().strip('"')).now()
    session = smart.generateSession(os.environ["ANGEL_CLIENT_ID"].strip().strip('"'), os.environ["ANGEL_PASSWORD"].strip().strip('"'), totp)
    if not session or not session.get("status"):
        raise RuntimeError(f"Angel SmartAPI login failed: {session}")
    return smart


def _resolve_index_tokens() -> dict[str, dict[str, str]]:
    try:
        response = requests.get(SCRIP_MASTER_URL, timeout=30)
        response.raise_for_status()
        payload = response.json()
    except Exception:
        return INDEX_FALLBACKS.copy()

    resolved = INDEX_FALLBACKS.copy()
    wanted = {"NIFTY 50": "NIFTY50", "NIFTY BANK": "BANKNIFTY", "BANKNIFTY": "BANKNIFTY"}
    for item in payload:
        exch = str(item.get("exch_seg") or item.get("exch_seg ") or "").upper()
        if exch != "NSE":
            continue
        name = str(item.get("name") or "").upper()
        symbol = str(item.get("symbol") or "").upper()
        token = str(item.get("token") or "")
        instrument_type = str(item.get("instrumenttype") or "").upper()
        for needle, key in wanted.items():
            if token and instrument_type == "AMXIDX" and (name == needle or symbol == needle):
                resolved[key] = {"symbol": key, "name": needle, "token": token, "exchange": "NSE"}
    return resolved


def _chunks(start: date, end: date, days: int) -> list[tuple[datetime, datetime]]:
    ranges = []
    current = start
    while current <= end:
        chunk_end = min(current + timedelta(days=days - 1), end)
        ranges.append((datetime.combine(current, time(9, 0)), datetime.combine(chunk_end, time(15, 30))))
        current = chunk_end + timedelta(days=1)
    return ranges


def _fetch_chunk(smart: Any, token: str, exchange: str, start_dt: datetime, end_dt: datetime) -> pd.DataFrame:
    params = {
        "exchange": exchange,
        "symboltoken": token,
        "interval": "FIFTEEN_MINUTE",
        "fromdate": start_dt.strftime("%Y-%m-%d %H:%M"),
        "todate": end_dt.strftime("%Y-%m-%d %H:%M"),
    }
    response = smart.getCandleData(params)
    if not response or not response.get("status"):
        message = response.get("message") if isinstance(response, dict) else response
        raise RuntimeError(f"getCandleData failed for token {token} {params['fromdate']} to {params['todate']}: {message}")
    data = response.get("data") or []
    if not data:
        return pd.DataFrame(columns=["datetime", "open", "high", "low", "close", "volume"])
    frame = pd.DataFrame(data, columns=["datetime", "open", "high", "low", "close", "volume"])
    frame["datetime"] = pd.to_datetime(frame["datetime"], errors="coerce")
    for column in ["open", "high", "low", "close", "volume"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame = frame.dropna(subset=["datetime", "open", "high", "low", "close"]).copy()
    return frame


def _upsert_ohlcv(symbol: str, frame: pd.DataFrame) -> int:
    if frame.empty:
        return 0
    rows = []
    for row in frame.itertuples(index=False):
        rows.append(
            {
                "symbol": symbol,
                "datetime": row.datetime.to_pydatetime() if hasattr(row.datetime, "to_pydatetime") else row.datetime,
                "open": float(row.open),
                "high": float(row.high),
                "low": float(row.low),
                "close": float(row.close),
                "volume": int(row.volume) if pd.notna(row.volume) else 0,
            }
        )
    query = text(
        """
        INSERT INTO ohlcv_15min (symbol, datetime, open, high, low, close, volume)
        VALUES (:symbol, :datetime, :open, :high, :low, :close, :volume)
        ON CONFLICT (symbol, datetime) DO UPDATE SET
            open = EXCLUDED.open,
            high = EXCLUDED.high,
            low = EXCLUDED.low,
            close = EXCLUDED.close,
            volume = EXCLUDED.volume
        """
    )
    engine = get_engine()
    with engine.begin() as connection:
        connection.execute(query, rows)
    return len(rows)


def download_indices(start: date, end: date, chunk_days: int = 30, sleep_seconds: float = 0.4) -> dict[str, dict[str, Any]]:
    smart = _smart_connect()
    tokens = _resolve_index_tokens()
    summary: dict[str, dict[str, Any]] = {}
    for key in ["NIFTY50", "BANKNIFTY"]:
        meta = tokens[key]
        frames = []
        errors = []
        for start_dt, end_dt in _chunks(start, end, chunk_days):
            try:
                frame = _fetch_chunk(smart, meta["token"], meta["exchange"], start_dt, end_dt)
                if not frame.empty:
                    frames.append(frame)
            except Exception as exc:
                errors.append({"from": start_dt.isoformat(), "to": end_dt.isoformat(), "error": str(exc)})
            time_module.sleep(sleep_seconds)
        combined = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=["datetime", "open", "high", "low", "close", "volume"])
        if not combined.empty:
            combined = combined.drop_duplicates(subset=["datetime"]).sort_values("datetime")
        inserted = _upsert_ohlcv(key, combined)
        summary[key] = {
            "token": meta["token"],
            "exchange": meta["exchange"],
            "rows_upserted": inserted,
            "first_datetime": str(combined["datetime"].min()) if not combined.empty else None,
            "last_datetime": str(combined["datetime"].max()) if not combined.empty else None,
            "errors": errors,
        }
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", default="2021-06-14")
    parser.add_argument("--end", default=date.today().isoformat())
    parser.add_argument("--chunk-days", type=int, default=30)
    parser.add_argument("--sleep", type=float, default=0.4)
    args = parser.parse_args()
    summary = download_indices(_parse_date(args.start), _parse_date(args.end), chunk_days=args.chunk_days, sleep_seconds=args.sleep)
    output_dir = ROOT / "results" / "index_download"
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "angel_index_15min_download_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
