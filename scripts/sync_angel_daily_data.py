#!/usr/bin/env python3
"""Incrementally synchronize Angel SmartAPI 15-minute candles.

Reads:
  - security_symbol_alias/security_master when populated
  - pilot_phase2a.exact_match_universe fallback
  - angel_data.ohlcv_15min latest candle timestamps

Writes:
  - angel_data.ohlcv_15min using conflict-safe upsert
  - angel_data.fetch_progress progress rows when available

Does not:
  - Redownload full history for symbols that already have candles
  - Modify daily bars, features, scores, recommendations, or strategy rules
  - Connect broker order APIs or place orders
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Protocol
from urllib.parse import urlsplit, urlunsplit

from dotenv import load_dotenv
from sqlalchemy import create_engine, inspect, text

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

INTERVAL = "FIFTEEN_MINUTE"
DEFAULT_LOOKBACK_DAYS = 5
DEFAULT_CHUNK_DAYS = 60


class CandleClient(Protocol):
    def getCandleData(self, payload: dict[str, object]) -> dict[str, object]:
        ...


@dataclass(frozen=True)
class TrackedSymbol:
    symbol: str
    token: str | None = None
    exchange: str = "NSE"


@dataclass
class SymbolSyncResult:
    symbol: str
    token: str | None
    latest_before: str | None
    requested_from: str
    requested_to: str
    fetched_rows: int = 0
    inserted_or_updated_rows: int = 0
    status: str = "pending"
    error: str | None = None


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Incrementally sync Angel 15-minute candles.")
    parser.add_argument("--research-database-url", default=os.environ.get("DATABASE_URL"))
    parser.add_argument("--angel-database-url", default=os.environ.get("ANGEL_DATABASE_URL"))
    parser.add_argument("--angel-database-name", default="angel_data")
    parser.add_argument("--source-table", default="ohlcv_15min")
    parser.add_argument("--pilot-schema", default="pilot_phase2a")
    parser.add_argument("--from-date", help="Override missing-candle start timestamp, ISO format.")
    parser.add_argument("--to-date", help="Override sync end timestamp, ISO format. Defaults to now.")
    parser.add_argument("--bootstrap-lookback-days", type=int, default=DEFAULT_LOOKBACK_DAYS)
    parser.add_argument("--chunk-days", type=int, default=DEFAULT_CHUNK_DAYS)
    parser.add_argument("--sleep-seconds", type=float, default=0.5)
    parser.add_argument("--rate-limit-sleep-seconds", type=float, default=60.0)
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--symbol-limit", type=int)
    parser.add_argument("--symbols", help="Comma-separated symbol allowlist for targeted sync.")
    parser.add_argument("--token-map-csv", default=os.environ.get("ANGEL_SYMBOL_TOKEN_MAP_CSV", "config/angel_symbol_token_map.csv"))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--output-json", default="reports/phase3f_angel_daily_sync.json")
    parser.add_argument("--log-level", default="INFO")
    return parser.parse_args(argv)


def derive_angel_url(research_database_url: str | None, database_name: str) -> str | None:
    if not research_database_url:
        return None
    parts = urlsplit(research_database_url)
    return urlunsplit((parts.scheme, parts.netloc, f"/{database_name}", parts.query, parts.fragment))


def parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def login_to_angel(retries: int = 3, sleep_seconds: float = 2.0) -> CandleClient:
    try:
        from SmartApi.smartConnect import SmartConnect
        import pyotp
    except ImportError as exc:
        raise RuntimeError("SmartApi and pyotp packages are required for live sync.") from exc

    required = {
        "ANGEL_API_KEY": os.environ.get("ANGEL_API_KEY"),
        "ANGEL_CLIENT_ID": os.environ.get("ANGEL_CLIENT_ID"),
        "ANGEL_PASSWORD": os.environ.get("ANGEL_PASSWORD"),
        "ANGEL_TOTP_SECRET": os.environ.get("ANGEL_TOTP_SECRET"),
    }
    missing = [key for key, value in required.items() if not value]
    if missing:
        raise RuntimeError(f"Missing Angel credentials: {', '.join(missing)}")

    last_error: Exception | None = None
    for attempt in range(1, max(1, retries) + 1):
        try:
            client = SmartConnect(api_key=required["ANGEL_API_KEY"])
            totp = pyotp.TOTP(required["ANGEL_TOTP_SECRET"]).now()
            response = client.generateSession(required["ANGEL_CLIENT_ID"], required["ANGEL_PASSWORD"], totp)
            if not response.get("status"):
                raise RuntimeError(f"Angel login failed: {response.get('message') or response}")
            if attempt > 1:
                logging.info("Angel login succeeded on retry %s", attempt)
            return client
        except Exception as exc:  # noqa: BLE001 - vendor login can fail with transient network errors
            last_error = exc
            if attempt < max(1, retries):
                pause = sleep_seconds * attempt
                logging.warning("Angel login attempt %s failed: %s; retrying in %.1fs", attempt, exc, pause)
                time.sleep(pause)
    raise RuntimeError(f"Angel login failed after {max(1, retries)} attempts: {last_error}") from last_error


def ensure_fetch_progress_table(connection) -> None:
    connection.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS fetch_progress (
                symbol text PRIMARY KEY,
                last_attempt_at timestamptz,
                last_success_at timestamptz,
                latest_candle_at timestamptz,
                status text NOT NULL,
                rows_fetched integer DEFAULT 0,
                rows_upserted integer DEFAULT 0,
                error_message text
            )
            """
        )
    )


def load_token_map_from_csv(path: str | None) -> dict[str, tuple[str, str]]:
    if not path:
        return {}
    csv_path = Path(path)
    if not csv_path.is_absolute():
        csv_path = REPO_ROOT / csv_path
    if not csv_path.exists():
        return {}

    required = {"symbol", "angel_token", "exchange"}
    token_map: dict[str, tuple[str, str]] = {}
    symbols_seen: set[str] = set()
    tokens_seen: set[str] = set()
    missing: list[int] = []
    duplicate_symbols: set[str] = set()
    duplicate_tokens: set[str] = set()

    with csv_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        headers = set(reader.fieldnames or [])
        missing_headers = required - headers
        if missing_headers:
            raise RuntimeError(f"Token map CSV is missing required columns: {', '.join(sorted(missing_headers))}")
        for line_no, row in enumerate(reader, start=2):
            symbol = (row.get("symbol") or "").strip().upper()
            token = (row.get("angel_token") or "").strip()
            exchange = (row.get("exchange") or "").strip().upper() or "NSE"
            if not symbol or not token:
                missing.append(line_no)
                continue
            if symbol in symbols_seen:
                duplicate_symbols.add(symbol)
            if token in tokens_seen:
                duplicate_tokens.add(token)
            symbols_seen.add(symbol)
            tokens_seen.add(token)
            token_map[symbol] = (token, exchange)

    errors: list[str] = []
    if missing:
        errors.append(f"missing symbol/token at lines: {', '.join(map(str, missing[:20]))}")
    if duplicate_symbols:
        errors.append(f"duplicate symbols: {', '.join(sorted(duplicate_symbols)[:20])}")
    if duplicate_tokens:
        errors.append(f"duplicate Angel tokens: {', '.join(sorted(duplicate_tokens)[:20])}")
    if errors:
        raise RuntimeError(f"Invalid Angel token map CSV {csv_path}: {'; '.join(errors)}")
    return token_map


def load_token_map(token_map_csv: str | None = None) -> dict[str, tuple[str, str]]:
    csv_tokens = load_token_map_from_csv(token_map_csv)
    if csv_tokens:
        return csv_tokens

    raw_json = os.environ.get("ANGEL_SYMBOL_TOKEN_MAP_JSON")
    raw_file = os.environ.get("ANGEL_SYMBOL_TOKEN_MAP_FILE")
    if raw_json:
        payload = json.loads(raw_json)
        return {str(key).upper(): (str(value), "NSE") for key, value in payload.items()}
    if raw_file:
        payload = json.loads(Path(raw_file).read_text(encoding="utf-8"))
        return {str(key).upper(): (str(value), "NSE") for key, value in payload.items()}
    return {}


def parse_symbol_allowlist(value: str | None) -> set[str]:
    if not value:
        return set()
    return {item.strip().upper() for item in value.split(",") if item.strip()}


def read_tracked_symbols(
    connection,
    pilot_schema: str,
    symbol_limit: int | None = None,
    token_map_csv: str | None = None,
    symbol_allowlist: set[str] | None = None,
) -> list[TrackedSymbol]:
    inspector = inspect(connection)
    token_map = load_token_map(token_map_csv)
    symbols: list[str] = []

    if inspector.has_table("security_symbol_alias") and inspector.has_table("security_master"):
        rows = connection.execute(
            text(
                """
                SELECT DISTINCT a.symbol
                FROM security_symbol_alias a
                JOIN security_master s ON s.security_id = a.security_id
                WHERE a.source = 'angel'
                  AND a.review_status IN ('approved', 'auto_approved')
                  AND s.status = 'active'
                ORDER BY a.symbol
                """
            )
        ).scalars().all()
        symbols = [str(row) for row in rows]

    if not symbols and inspector.has_schema(pilot_schema) and inspector.has_table("exact_match_universe", schema=pilot_schema):
        rows = connection.execute(
            text(f"SELECT DISTINCT angel_symbol FROM {pilot_schema}.exact_match_universe ORDER BY angel_symbol")
        ).scalars().all()
        symbols = [str(row) for row in rows]

    if not symbols and inspector.has_table("ohlcv_15min"):
        rows = connection.execute(text("SELECT DISTINCT symbol FROM ohlcv_15min ORDER BY symbol")).scalars().all()
        symbols = [str(row) for row in rows]

    if symbol_allowlist:
        known_symbols = {symbol.upper(): symbol for symbol in symbols}
        symbols = [known_symbols.get(symbol, symbol) for symbol in sorted(symbol_allowlist)]

    if symbol_limit is not None:
        symbols = symbols[:symbol_limit]
    return [
        TrackedSymbol(
            symbol=symbol,
            token=token_map.get(symbol.upper(), (None, "NSE"))[0],
            exchange=token_map.get(symbol.upper(), (None, "NSE"))[1],
        )
        for symbol in symbols
    ]


def symbols_missing_tokens(symbols: list[TrackedSymbol]) -> list[str]:
    return sorted(symbol.symbol for symbol in symbols if not symbol.token)


def latest_candle_at(connection, table: str, symbol: str) -> datetime | None:
    return connection.execute(text(f"SELECT MAX(datetime) FROM {table} WHERE symbol = :symbol"), {"symbol": symbol}).scalar_one_or_none()


def missing_window(latest: datetime | None, now: datetime, bootstrap_lookback_days: int, override_from: datetime | None) -> tuple[datetime, datetime]:
    if latest is not None and latest.tzinfo is None and now.tzinfo is not None:
        latest = latest.replace(tzinfo=now.tzinfo)
    start = override_from or ((latest + timedelta(minutes=15)) if latest else now - timedelta(days=bootstrap_lookback_days))
    return start, now


def iter_chunks(start: datetime, end: datetime, chunk_days: int) -> list[tuple[datetime, datetime]]:
    if start > end:
        return []
    chunks: list[tuple[datetime, datetime]] = []
    cursor = start
    while cursor <= end:
        chunk_end = min(cursor + timedelta(days=chunk_days), end)
        chunks.append((cursor, chunk_end))
        cursor = chunk_end + timedelta(minutes=15)
    return chunks


def format_angel_dt(value: datetime) -> str:
    local = value.astimezone().replace(tzinfo=None) if value.tzinfo else value
    return local.strftime("%Y-%m-%d %H:%M")


def fetch_candles_with_retry(
    client: CandleClient,
    symbol: TrackedSymbol,
    start: datetime,
    end: datetime,
    retries: int,
    sleep_seconds: float,
    rate_limit_sleep_seconds: float,
) -> list[list[object]]:
    if not symbol.token:
        raise RuntimeError(f"Missing Angel token for {symbol.symbol}. Set ANGEL_SYMBOL_TOKEN_MAP_JSON or ANGEL_SYMBOL_TOKEN_MAP_FILE.")
    payload = {
        "exchange": symbol.exchange,
        "symboltoken": symbol.token,
        "interval": INTERVAL,
        "fromdate": format_angel_dt(start),
        "todate": format_angel_dt(end),
    }
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            response = client.getCandleData(payload)
            if response.get("status") and response.get("data"):
                return list(response["data"])
            if response.get("status") and not response.get("data"):
                return []
            raise RuntimeError(str(response.get("message") or response))
        except Exception as exc:  # noqa: BLE001 - retry boundary logs vendor/API failures
            last_error = exc
            if attempt < retries:
                message = str(exc).lower()
                pause = rate_limit_sleep_seconds if "rate" in message or "access denied" in message else sleep_seconds * attempt
                time.sleep(pause)
    raise RuntimeError(f"Angel candle request failed for {symbol.symbol}: {last_error}") from last_error


def normalize_candles(symbol: str, candles: list[list[object]]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    seen: set[tuple[str, datetime]] = set()
    for candle in candles:
        if len(candle) < 6:
            continue
        candle_dt = parse_dt(str(candle[0]))
        if candle_dt is None:
            continue
        key = (symbol, candle_dt)
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            {
                "datetime": candle_dt,
                "symbol": symbol,
                "open": candle[1],
                "high": candle[2],
                "low": candle[3],
                "close": candle[4],
                "volume": candle[5],
            }
        )
    return rows


def upsert_candles(connection, table: str, rows: list[dict[str, object]]) -> int:
    if not rows:
        return 0
    result = connection.execute(
        text(
            f"""
            INSERT INTO {table} (datetime, symbol, open, high, low, close, volume)
            VALUES (:datetime, :symbol, :open, :high, :low, :close, :volume)
            ON CONFLICT (symbol, datetime) DO UPDATE SET
                open = EXCLUDED.open,
                high = EXCLUDED.high,
                low = EXCLUDED.low,
                close = EXCLUDED.close,
                volume = EXCLUDED.volume
            """
        ),
        rows,
    )
    return int(result.rowcount or 0)


def fetch_progress_columns(connection) -> set[str]:
    inspector = inspect(connection)
    if not inspector.has_table("fetch_progress"):
        return set()
    return {column["name"] for column in inspector.get_columns("fetch_progress")}


def update_progress(connection, result: SymbolSyncResult) -> None:
    columns = fetch_progress_columns(connection)
    if {"last_attempt_at", "last_success_at", "latest_candle_at", "error_message"}.issubset(columns):
        update_progress_v2(connection, result)
        return
    if {"last_fetched_at", "candles_count", "error_msg"}.issubset(columns):
        update_progress_legacy(connection, result)
        return
    raise RuntimeError("fetch_progress exists but does not match a supported progress schema.")


def update_progress_v2(connection, result: SymbolSyncResult) -> None:
    connection.execute(
        text(
            """
            INSERT INTO fetch_progress (
                symbol, last_attempt_at, last_success_at, latest_candle_at, status,
                rows_fetched, rows_upserted, error_message
            )
            VALUES (
                :symbol, now(),
                CASE WHEN :status = 'success' THEN now() ELSE NULL END,
                :latest_candle_at, :status, :rows_fetched, :rows_upserted, :error_message
            )
            ON CONFLICT (symbol) DO UPDATE SET
                last_attempt_at = EXCLUDED.last_attempt_at,
                last_success_at = COALESCE(EXCLUDED.last_success_at, fetch_progress.last_success_at),
                latest_candle_at = COALESCE(EXCLUDED.latest_candle_at, fetch_progress.latest_candle_at),
                status = EXCLUDED.status,
                rows_fetched = EXCLUDED.rows_fetched,
                rows_upserted = EXCLUDED.rows_upserted,
                error_message = EXCLUDED.error_message
            """
        ),
        {
            "symbol": result.symbol,
            "status": result.status,
            "rows_fetched": result.fetched_rows,
            "rows_upserted": result.inserted_or_updated_rows,
            "error_message": result.error,
            "latest_candle_at": result.requested_to if result.status == "success" else result.latest_before,
        },
    )


def update_progress_legacy(connection, result: SymbolSyncResult) -> None:
    connection.execute(
        text(
            """
            INSERT INTO fetch_progress (
                symbol, token, status, last_fetched_at, candles_count, error_msg
            )
            VALUES (
                :symbol, :token, :status,
                CASE WHEN :status IN ('success', 'up_to_date') THEN now() ELSE NULL END,
                :candles_count, :error_msg
            )
            ON CONFLICT (symbol) DO UPDATE SET
                token = COALESCE(EXCLUDED.token, fetch_progress.token),
                status = EXCLUDED.status,
                last_fetched_at = COALESCE(EXCLUDED.last_fetched_at, fetch_progress.last_fetched_at),
                candles_count = EXCLUDED.candles_count,
                error_msg = EXCLUDED.error_msg
            """
        ),
        {
            "symbol": result.symbol,
            "token": result.token,
            "status": result.status,
            "candles_count": result.inserted_or_updated_rows,
            "error_msg": result.error,
        },
    )


def sync_symbol(
    connection,
    client: CandleClient | None,
    symbol: TrackedSymbol,
    table: str,
    now: datetime,
    bootstrap_lookback_days: int,
    chunk_days: int,
    retries: int,
    sleep_seconds: float,
    rate_limit_sleep_seconds: float,
    dry_run: bool,
    override_from: datetime | None = None,
) -> SymbolSyncResult:
    latest = latest_candle_at(connection, table, symbol.symbol)
    start, end = missing_window(latest, now, bootstrap_lookback_days, override_from)
    result = SymbolSyncResult(
        symbol=symbol.symbol,
        token=symbol.token,
        latest_before=latest.isoformat() if latest else None,
        requested_from=start.isoformat(),
        requested_to=end.isoformat(),
    )
    if start > end:
        result.status = "up_to_date"
        return result
    if dry_run:
        result.status = "dry_run"
        return result
    if client is None:
        raise RuntimeError("A live Angel client is required unless --dry-run is used.")

    fetched: list[list[object]] = []
    for chunk_start, chunk_end in iter_chunks(start, end, chunk_days):
        fetched.extend(
            fetch_candles_with_retry(
                client,
                symbol,
                chunk_start,
                chunk_end,
                retries,
                sleep_seconds,
                rate_limit_sleep_seconds,
            )
        )
        time.sleep(sleep_seconds)

    rows = normalize_candles(symbol.symbol, fetched)
    result.fetched_rows = len(rows)
    result.inserted_or_updated_rows = upsert_candles(connection, table, rows)
    result.status = "success"
    return result


def main() -> int:
    load_dotenv(REPO_ROOT / ".env")
    args = parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level.upper()), format="%(asctime)s %(levelname)s %(message)s")

    research_url = args.research_database_url or os.environ.get("DATABASE_URL")
    angel_url = args.angel_database_url or derive_angel_url(research_url, args.angel_database_name)
    if not angel_url:
        raise RuntimeError("Angel database URL is required. Set ANGEL_DATABASE_URL or DATABASE_URL.")

    now = parse_dt(args.to_date) or datetime.now(timezone.utc)
    override_from = parse_dt(args.from_date)
    engine = create_engine(angel_url, future=True)
    client = None
    results: list[SymbolSyncResult] = []

    with engine.begin() as connection:
        if not args.dry_run:
            ensure_fetch_progress_table(connection)
        symbols = read_tracked_symbols(
            connection,
            args.pilot_schema,
            args.symbol_limit,
            args.token_map_csv,
            parse_symbol_allowlist(args.symbols),
        )
        missing_tokens = symbols_missing_tokens(symbols)
        if missing_tokens and not args.dry_run:
            preview = ", ".join(missing_tokens[:20])
            suffix = "" if len(missing_tokens) <= 20 else f", ... ({len(missing_tokens)} total)"
            raise RuntimeError(f"Missing Angel tokens for tracked symbols: {preview}{suffix}")
        client = None if args.dry_run else login_to_angel(retries=args.retries, sleep_seconds=args.sleep_seconds)
        logging.info("tracking %s Angel symbols", len(symbols))
        for index, symbol in enumerate(symbols, start=1):
            logging.info("[%s/%s] syncing %s", index, len(symbols), symbol.symbol)
            try:
                result = sync_symbol(
                    connection=connection,
                    client=client,
                    symbol=symbol,
                    table=args.source_table,
                    now=now,
                    bootstrap_lookback_days=args.bootstrap_lookback_days,
                    chunk_days=args.chunk_days,
                    retries=args.retries,
                    sleep_seconds=args.sleep_seconds,
                    rate_limit_sleep_seconds=args.rate_limit_sleep_seconds,
                    dry_run=args.dry_run,
                    override_from=override_from,
                )
            except Exception as exc:  # noqa: BLE001 - per-symbol failure isolation
                result = SymbolSyncResult(
                    symbol=symbol.symbol,
                    token=symbol.token,
                    latest_before=None,
                    requested_from=(override_from or now).isoformat(),
                    requested_to=now.isoformat(),
                    status="failed",
                    error=str(exc),
                )
            if not args.dry_run:
                update_progress(connection, result)
            results.append(result)

    report = {
        "generated_on": datetime.now(timezone.utc).isoformat(),
        "mode": "phase3f_angel_daily_sync",
        "dry_run": args.dry_run,
        "source_table": args.source_table,
        "symbols_seen": len(results),
        "summary": {
            "success": sum(1 for row in results if row.status == "success"),
            "up_to_date": sum(1 for row in results if row.status == "up_to_date"),
            "dry_run": sum(1 for row in results if row.status == "dry_run"),
            "failed": sum(1 for row in results if row.status == "failed"),
            "missing_tokens": sum(1 for row in results if not row.token),
            "fetched_rows": sum(row.fetched_rows for row in results),
            "upserted_rows": sum(row.inserted_or_updated_rows for row in results),
        },
        "results": [asdict(row) for row in results],
    }
    output_path = REPO_ROOT / args.output_json
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(json.dumps(report["summary"], indent=2))
    print(f"Wrote Angel sync report: {output_path}")
    return 1 if report["summary"]["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
