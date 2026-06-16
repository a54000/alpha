#!/usr/bin/env python3
"""Build and validate Angel symbol-token mapping from an instrument master export.

This is an offline utility. It does not call Angel APIs, place orders, modify
database schema, or change strategy/recommendation behavior.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from sqlalchemy import create_engine, inspect, text

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

DEFAULT_OUTPUT = "config/angel_symbol_token_map.csv"
DEFAULT_REPORT = "reports/phase5_12_token_map_validation.json"
ALLOWED_EXCHANGES = {"NSE"}
EQUITY_INSTRUMENT_TYPES = {"", "EQ", "EQUITY"}


@dataclass(frozen=True)
class InstrumentRow:
    symbol: str
    angel_token: str
    exchange: str
    instrument_type: str = ""
    expiry: str = ""


@dataclass(frozen=True)
class ValidationReport:
    total_mappings: int
    duplicate_symbols: list[str]
    duplicate_tokens: list[str]
    invalid_exchange_symbols: list[str]
    missing_symbols: list[str]
    covered_symbols: list[str]
    extra_symbols: list[str]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build config/angel_symbol_token_map.csv from an Angel instrument master export.")
    parser.add_argument("--instrument-master", required=True, help="Path to Angel instrument master JSON or CSV export.")
    parser.add_argument("--output-csv", default=DEFAULT_OUTPUT)
    parser.add_argument("--report-json", default=DEFAULT_REPORT)
    parser.add_argument("--database-url", default=os.environ.get("ANGEL_DATABASE_URL") or os.environ.get("DATABASE_URL"))
    parser.add_argument("--pilot-schema", default="pilot_phase2a")
    parser.add_argument("--skip-db-coverage", action="store_true", help="Do not compare against pilot_phase2a universe.")
    parser.add_argument("--include-non-equity", action="store_true", help="Include non-equity instruments from the master.")
    parser.add_argument("--include-other-exchanges", action="store_true", help="Include non-NSE exchanges for diagnostics.")
    parser.add_argument("--dry-run", action="store_true", help="Validate and report without writing output CSV.")
    return parser.parse_args(argv)


def repo_path(path: str | Path) -> Path:
    resolved = Path(path)
    return resolved if resolved.is_absolute() else REPO_ROOT / resolved


def normalize_symbol(value: Any) -> str:
    symbol = str(value or "").strip().upper()
    if symbol.endswith("-EQ"):
        return symbol[:-3]
    return symbol


def normalize_instrument_type(value: Any) -> str:
    return str(value or "").strip().upper()


def pick(row: dict[str, Any], *names: str) -> str:
    lower = {str(key).strip().lower(): value for key, value in row.items()}
    for name in names:
        value = lower.get(name.lower())
        if value not in (None, ""):
            return str(value).strip()
    return ""


def normalize_instrument_row(row: dict[str, Any]) -> InstrumentRow | None:
    symbol = normalize_symbol(pick(row, "symbol", "name", "tradingsymbol", "trading_symbol"))
    token = pick(row, "token", "angel_token", "symboltoken", "symbol_token", "instrument_token")
    exchange = pick(row, "exch_seg", "exchange", "exch", "segment").upper()
    instrument_type = normalize_instrument_type(pick(row, "instrumenttype", "instrument_type", "instrument", "series"))
    expiry = pick(row, "expiry", "expiry_date")
    if not symbol or not token:
        return None
    return InstrumentRow(
        symbol=symbol,
        angel_token=str(token).strip(),
        exchange=exchange or "NSE",
        instrument_type=instrument_type,
        expiry=expiry,
    )


def load_instrument_master(path: str | Path, include_non_equity: bool = False, include_other_exchanges: bool = False) -> list[InstrumentRow]:
    source = repo_path(path)
    if not source.exists():
        raise FileNotFoundError(f"Instrument master not found: {source}")

    if source.suffix.lower() == ".json":
        payload = json.loads(source.read_text(encoding="utf-8-sig"))
        if isinstance(payload, dict):
            rows = payload.get("data") or payload.get("result") or payload.get("instruments") or []
        else:
            rows = payload
        raw_rows = [row for row in rows if isinstance(row, dict)]
    else:
        with source.open(newline="", encoding="utf-8-sig") as handle:
            raw_rows = list(csv.DictReader(handle))

    normalized: list[InstrumentRow] = []
    for raw in raw_rows:
        row = normalize_instrument_row(raw)
        if row is None:
            continue
        if row.exchange not in ALLOWED_EXCHANGES:
            if include_other_exchanges:
                normalized.append(row)
            continue
        if include_non_equity or row.instrument_type in EQUITY_INSTRUMENT_TYPES:
            normalized.append(row)
    return normalized


def write_token_map(path: str | Path, rows: list[InstrumentRow]) -> None:
    output = repo_path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["symbol", "angel_token", "exchange", "instrument_type", "expiry"])
        writer.writeheader()
        for row in sorted(rows, key=lambda item: (item.symbol, item.exchange, item.instrument_type, item.expiry)):
            writer.writerow(asdict(row))


def duplicate_values(values: list[str]) -> list[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    return sorted(duplicates)


def read_pilot_symbols(database_url: str | None, pilot_schema: str) -> list[str]:
    if not database_url:
        return []
    engine = create_engine(database_url, future=True)
    with engine.connect() as connection:
        inspector = inspect(connection)
        if not inspector.has_schema(pilot_schema) or not inspector.has_table("exact_match_universe", schema=pilot_schema):
            return []
        rows = connection.execute(text(f"SELECT DISTINCT angel_symbol FROM {pilot_schema}.exact_match_universe ORDER BY angel_symbol")).scalars().all()
    return [normalize_symbol(row) for row in rows]


def validate_mapping(rows: list[InstrumentRow], pilot_symbols: list[str] | None = None) -> ValidationReport:
    pilot_set = set(pilot_symbols or [])
    symbol_set = {row.symbol for row in rows}
    duplicate_symbols = duplicate_values([row.symbol for row in rows])
    duplicate_tokens = duplicate_values([row.angel_token for row in rows])
    invalid_exchange_symbols = sorted({row.symbol for row in rows if row.exchange not in ALLOWED_EXCHANGES})
    missing_symbols = sorted(pilot_set - symbol_set)
    covered_symbols = sorted(pilot_set & symbol_set)
    extra_symbols = sorted(symbol_set - pilot_set) if pilot_set else sorted(symbol_set)
    return ValidationReport(
        total_mappings=len(rows),
        duplicate_symbols=duplicate_symbols,
        duplicate_tokens=duplicate_tokens,
        invalid_exchange_symbols=invalid_exchange_symbols,
        missing_symbols=missing_symbols,
        covered_symbols=covered_symbols,
        extra_symbols=extra_symbols,
    )


def write_report(path: str | Path, report: ValidationReport, output_csv: str, dry_run: bool) -> None:
    target = repo_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "mode": "phase5_12_angel_token_map_build",
        "dry_run": dry_run,
        "output_csv": str(repo_path(output_csv)),
        "summary": {
            "total_mappings": report.total_mappings,
            "duplicate_symbol_count": len(report.duplicate_symbols),
            "duplicate_token_count": len(report.duplicate_tokens),
            "invalid_exchange_symbol_count": len(report.invalid_exchange_symbols),
            "covered_symbol_count": len(report.covered_symbols),
            "missing_symbol_count": len(report.missing_symbols),
            "extra_symbol_count": len(report.extra_symbols),
        },
        "details": asdict(report),
    }
    target.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    load_dotenv(REPO_ROOT / ".env")
    args = parse_args(argv)
    rows = load_instrument_master(
        args.instrument_master,
        include_non_equity=args.include_non_equity,
        include_other_exchanges=args.include_other_exchanges,
    )
    pilot_symbols = [] if args.skip_db_coverage else read_pilot_symbols(args.database_url, args.pilot_schema)
    report = validate_mapping(rows, pilot_symbols)

    if not args.dry_run:
        write_token_map(args.output_csv, rows)
    write_report(args.report_json, report, args.output_csv, args.dry_run)

    print(json.dumps({
        "total_mappings": report.total_mappings,
        "covered_symbols": len(report.covered_symbols),
        "missing_symbols": len(report.missing_symbols),
        "duplicate_symbols": len(report.duplicate_symbols),
        "duplicate_tokens": len(report.duplicate_tokens),
        "invalid_exchange_symbols": len(report.invalid_exchange_symbols),
    }, indent=2))
    print(f"Wrote validation report: {repo_path(args.report_json)}")
    if not args.dry_run:
        print(f"Wrote token map: {repo_path(args.output_csv)}")
    return 1 if report.duplicate_symbols or report.duplicate_tokens or report.invalid_exchange_symbols else 0


if __name__ == "__main__":
    raise SystemExit(main())
