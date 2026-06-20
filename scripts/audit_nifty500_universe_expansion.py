#!/usr/bin/env python3
"""Audit readiness to expand the pilot universe to Nifty 500.

Read-only. Compares:
  - data/ind_nifty500list.csv
  - config/angel_symbol_token_map.csv
  - angel_data.ohlcv_15min
  - pilot_phase2a.daily_bars_clean/features_daily
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

DEFAULT_NIFTY = REPO_ROOT / "data" / "ind_nifty500list.csv"
DEFAULT_TOKEN_MAP = REPO_ROOT / "config" / "angel_symbol_token_map.csv"
DEFAULT_GAP = REPO_ROOT / "reports" / "nifty500_universe_gap.csv"
DEFAULT_TOKEN = REPO_ROOT / "reports" / "nifty500_token_coverage.csv"
DEFAULT_STATUS = REPO_ROOT / "reports" / "nifty500_backfill_status.csv"
DEFAULT_JSON = REPO_ROOT / "reports" / "nifty500_universe_expansion_audit.json"
DEFAULT_DOC = REPO_ROOT / "docs" / "PHASE7A_NIFTY500_UNIVERSE_EXPANSION.md"


def derive_angel_url(research_database_url: str | None, database_name: str = "angel_data") -> str | None:
    if not research_database_url:
        return None
    parts = urlsplit(research_database_url)
    return urlunsplit((parts.scheme, parts.netloc, f"/{database_name}", parts.query, parts.fragment))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit Nifty 500 expansion readiness.")
    parser.add_argument("--nifty500-csv", type=Path, default=DEFAULT_NIFTY)
    parser.add_argument("--token-map-csv", type=Path, default=DEFAULT_TOKEN_MAP)
    parser.add_argument("--pilot-schema", default="pilot_phase2a")
    parser.add_argument("--gap-csv", type=Path, default=DEFAULT_GAP)
    parser.add_argument("--token-csv", type=Path, default=DEFAULT_TOKEN)
    parser.add_argument("--status-csv", type=Path, default=DEFAULT_STATUS)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--doc-out", type=Path, default=DEFAULT_DOC)
    return parser.parse_args()


def make_engine():
    load_dotenv(REPO_ROOT / ".env")
    url = os.environ.get("ANGEL_DATABASE_URL") or derive_angel_url(os.environ.get("DATABASE_URL"))
    if not url:
        raise RuntimeError("ANGEL_DATABASE_URL is required.")
    return create_engine(url, future=True, pool_pre_ping=True, pool_size=1, max_overflow=0)


def normalize_symbol(value: object) -> str:
    symbol = str(value or "").strip().upper()
    if symbol.endswith("-EQ"):
        symbol = symbol[:-3]
    return symbol


def load_nifty(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    frame["symbol"] = frame["Symbol"].map(normalize_symbol)
    frame["company_name"] = frame["Company Name"].fillna("")
    frame["industry"] = frame["Industry"].fillna("")
    frame["isin"] = frame["ISIN Code"].fillna("")
    return frame[["symbol", "company_name", "industry", "isin"]].drop_duplicates("symbol")


def load_token_map(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    frame["symbol"] = frame["symbol"].map(normalize_symbol)
    frame["angel_token"] = frame["angel_token"].astype(str)
    frame["exchange"] = frame.get("exchange", "NSE")
    return frame[["symbol", "angel_token", "exchange"]].drop_duplicates("symbol")


def load_db_coverage(engine, schema: str) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    candle_query = text(
        """
        SELECT symbol, COUNT(*) AS candle_rows, MIN(datetime)::date AS first_candle_date, MAX(datetime)::date AS last_candle_date
        FROM ohlcv_15min
        GROUP BY symbol
        """
    )
    daily_query = text(
        f"""
        SELECT symbol, COUNT(*) AS daily_rows, MIN(date) AS first_daily_date, MAX(date) AS last_daily_date
        FROM {schema}.daily_bars_clean
        GROUP BY symbol
        """
    )
    feature_query = text(
        f"""
        SELECT symbol, COUNT(*) AS feature_rows, MIN(date) AS first_feature_date, MAX(date) AS last_feature_date,
               MAX(sector) AS pilot_sector
        FROM {schema}.features_daily
        GROUP BY symbol
        """
    )
    candles = pd.read_sql_query(candle_query, engine)
    daily = pd.read_sql_query(daily_query, engine)
    features = pd.read_sql_query(feature_query, engine)
    for frame in [candles, daily, features]:
        if not frame.empty:
            frame["symbol"] = frame["symbol"].map(normalize_symbol)
    return candles, daily, features


def classify(row: pd.Series) -> tuple[str, str, str]:
    has_token = pd.notna(row.get("angel_token"))
    candle_rows = int(0 if pd.isna(row.get("candle_rows")) else row.get("candle_rows"))
    daily_rows = int(0 if pd.isna(row.get("daily_rows")) else row.get("daily_rows"))
    feature_rows = int(0 if pd.isna(row.get("feature_rows")) else row.get("feature_rows"))
    if not has_token:
        return "not_ready", "missing_angel_token", "Refresh Angel instrument master/token map or resolve symbol naming."
    if candle_rows == 0:
        return "not_ready", "needs_angel_backfill", "Run Angel historical sync/backfill for this symbol."
    if daily_rows == 0:
        return "not_ready", "needs_daily_aggregation", "Aggregate existing 15-minute candles into pilot daily bars."
    if feature_rows == 0:
        return "not_ready", "needs_feature_generation", "Run pilot feature generation and sector mapping for this symbol."
    return "ready", "usable", "No universe expansion fix required."


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def render_doc(payload: dict[str, object]) -> str:
    counts = payload["counts"]
    reason_counts = payload["reason_counts"]
    lines = [
        "# Phase 7A Nifty 500 Universe Expansion Audit",
        "",
        "Read-only audit. No data was downloaded, no tables were modified, and no strategy logic was changed.",
        "",
        "## Summary",
        "",
        f"- Nifty 500 symbols in source file: `{payload['nifty500_symbols']}`",
        f"- Currently usable in pilot features: `{counts.get('ready', 0)}`",
        f"- Not ready: `{counts.get('not_ready', 0)}`",
        f"- Token coverage: `{payload['token_coverage_pct']:.2%}`",
        f"- Pilot feature coverage: `{payload['feature_coverage_pct']:.2%}`",
        "",
        "## Gap Reasons",
        "",
        "| Reason | Count | Meaning |",
        "| --- | ---: | --- |",
    ]
    meaning = {
        "missing_angel_token": "No Angel token was found in config/angel_symbol_token_map.csv.",
        "needs_angel_backfill": "Token exists, but no 15-minute candles exist in angel_data.ohlcv_15min.",
        "needs_daily_aggregation": "15-minute candles exist, but pilot daily bars are missing.",
        "needs_feature_generation": "Daily bars exist, but pilot features/sector rows are missing.",
        "usable": "Token, candles, daily bars, and features exist.",
    }
    for reason, count in sorted(reason_counts.items()):
        lines.append(f"| {reason} | {count} | {meaning.get(reason, '')} |")
    lines.extend(
        [
            "",
            "## Safe Expansion Path",
            "",
            "1. Resolve `missing_angel_token` symbols first.",
            "2. Backfill `needs_angel_backfill` symbols using Angel historical sync.",
            "3. Run daily aggregation for symbols with candles but no daily bars.",
            "4. Run feature generation and sector mapping.",
            "5. Re-run this audit until usable coverage is acceptable.",
            "",
            "## Generated Reports",
            "",
            "- `reports/nifty500_universe_gap.csv`",
            "- `reports/nifty500_token_coverage.csv`",
            "- `reports/nifty500_backfill_status.csv`",
            "- `reports/nifty500_universe_expansion_audit.json`",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    engine = make_engine()
    nifty = load_nifty(args.nifty500_csv)
    token_map = load_token_map(args.token_map_csv)
    candles, daily, features = load_db_coverage(engine, args.pilot_schema)
    merged = (
        nifty.merge(token_map, on="symbol", how="left")
        .merge(candles, on="symbol", how="left")
        .merge(daily, on="symbol", how="left")
        .merge(features, on="symbol", how="left")
    )
    rows: list[dict[str, object]] = []
    for _, item in merged.sort_values("symbol").iterrows():
        status, reason, fix = classify(item)
        rows.append(
            {
                "symbol": item["symbol"],
                "company_name": item["company_name"],
                "nifty_industry": item["industry"],
                "isin": item["isin"],
                "angel_token": item.get("angel_token"),
                "candle_rows": int(0 if pd.isna(item.get("candle_rows")) else item.get("candle_rows")),
                "first_candle_date": item.get("first_candle_date"),
                "last_candle_date": item.get("last_candle_date"),
                "daily_rows": int(0 if pd.isna(item.get("daily_rows")) else item.get("daily_rows")),
                "first_daily_date": item.get("first_daily_date"),
                "last_daily_date": item.get("last_daily_date"),
                "feature_rows": int(0 if pd.isna(item.get("feature_rows")) else item.get("feature_rows")),
                "first_feature_date": item.get("first_feature_date"),
                "last_feature_date": item.get("last_feature_date"),
                "pilot_sector": item.get("pilot_sector"),
                "status": status,
                "reason": reason,
                "recommended_fix": fix,
            }
        )
    counts: dict[str, int] = {}
    reason_counts: dict[str, int] = {}
    for row in rows:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
        reason_counts[row["reason"]] = reason_counts.get(row["reason"], 0) + 1
    token_rows = [
        {
            "symbol": row["symbol"],
            "company_name": row["company_name"],
            "has_angel_token": bool(row["angel_token"] == row["angel_token"] and row["angel_token"]),
            "angel_token": row["angel_token"],
            "reason": row["reason"],
        }
        for row in rows
    ]
    status_rows = [
        {
            "symbol": row["symbol"],
            "status": row["status"],
            "reason": row["reason"],
            "candle_rows": row["candle_rows"],
            "daily_rows": row["daily_rows"],
            "feature_rows": row["feature_rows"],
            "recommended_fix": row["recommended_fix"],
        }
        for row in rows
    ]
    gap_rows = [row for row in rows if row["status"] != "ready"]
    write_csv(args.gap_csv, gap_rows)
    write_csv(args.token_csv, token_rows)
    write_csv(args.status_csv, status_rows)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "nifty500_source": str(args.nifty500_csv),
        "token_map_source": str(args.token_map_csv),
        "nifty500_symbols": len(rows),
        "counts": counts,
        "reason_counts": reason_counts,
        "token_coverage_pct": sum(1 for row in rows if row["angel_token"] == row["angel_token"] and row["angel_token"]) / len(rows) if rows else 0.0,
        "feature_coverage_pct": counts.get("ready", 0) / len(rows) if rows else 0.0,
        "sample_gaps": gap_rows[:25],
    }
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    args.doc_out.parent.mkdir(parents=True, exist_ok=True)
    args.doc_out.write_text(render_doc(payload), encoding="utf-8")
    print(json.dumps({"status": "success", "counts": counts, "reason_counts": reason_counts, "doc": str(args.doc_out)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
