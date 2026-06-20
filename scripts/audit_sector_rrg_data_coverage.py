#!/usr/bin/env python3
"""Audit data readiness for Sector Rotation RRG.

Read-only. Reports whether each sector has enough daily sector-index history
and matching NIFTY50 benchmark dates to compute RS-Ratio / RS-Momentum tails.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

DEFAULT_REPORT = REPO_ROOT / "reports" / "sector_rrg_data_coverage.csv"
DEFAULT_JSON = REPO_ROOT / "reports" / "sector_rrg_data_coverage.json"
DEFAULT_DOC = REPO_ROOT / "docs" / "SECTOR_RRG_DATA_COVERAGE_AUDIT.md"


def derive_angel_url(research_database_url: str | None, database_name: str = "angel_data") -> str | None:
    if not research_database_url:
        return None
    parts = urlsplit(research_database_url)
    return urlunsplit((parts.scheme, parts.netloc, f"/{database_name}", parts.query, parts.fragment))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit Sector Rotation RRG data coverage.")
    parser.add_argument("--as-of", type=date.fromisoformat, default=None)
    parser.add_argument("--pilot-schema", default="pilot_phase2a")
    parser.add_argument("--lookback-days", type=int, default=140)
    parser.add_argument("--min-rrg-sessions", type=int, default=35)
    parser.add_argument("--csv-out", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--doc-out", type=Path, default=DEFAULT_DOC)
    return parser.parse_args()


def engine_from_env():
    load_dotenv(REPO_ROOT / ".env")
    url = os.environ.get("ANGEL_DATABASE_URL") or derive_angel_url(os.environ.get("DATABASE_URL"))
    if not url:
        raise RuntimeError("ANGEL_DATABASE_URL is required.")
    return create_engine(url, future=True, pool_pre_ping=True, pool_size=1, max_overflow=0)


def load_frame(engine, schema: str, as_of: date, lookback_days: int) -> pd.DataFrame:
    query = text(
        f"""
        SELECT
            f.symbol,
            f.date,
            f.sector,
            b.close,
            b.volume
        FROM {schema}.features_daily f
        LEFT JOIN {schema}.daily_bars_clean b
          ON b.symbol = f.symbol
         AND b.date = f.date
        WHERE f.date BETWEEN :as_of - (:lookback_days || ' days')::interval AND :as_of
        ORDER BY f.sector, f.symbol, f.date
        """
    )
    frame = pd.read_sql_query(query, engine, params={"as_of": as_of, "lookback_days": lookback_days})
    if frame.empty:
        return frame
    frame["date"] = pd.to_datetime(frame["date"]).dt.date
    frame["close"] = pd.to_numeric(frame["close"], errors="coerce")
    frame["volume"] = pd.to_numeric(frame["volume"], errors="coerce")
    return frame


def load_nifty(engine, as_of: date, lookback_days: int) -> pd.DataFrame:
    query = text(
        """
        SELECT datetime::date AS date, close
        FROM ohlcv_15min
        WHERE symbol = 'NIFTY50'
          AND datetime::date BETWEEN :as_of - (:lookback_days || ' days')::interval AND :as_of
          AND datetime::time <= '15:15:00'
        ORDER BY datetime
        """
    )
    frame = pd.read_sql_query(query, engine, params={"as_of": as_of, "lookback_days": lookback_days})
    if frame.empty:
        return frame
    frame["date"] = pd.to_datetime(frame["date"]).dt.date
    frame["close"] = pd.to_numeric(frame["close"], errors="coerce")
    return frame.dropna(subset=["close"]).groupby("date", as_index=False).tail(1)[["date", "close"]]


def latest_feature_date(engine, schema: str) -> date | None:
    with engine.connect() as conn:
        return conn.execute(text(f"SELECT MAX(date) FROM {schema}.features_daily")).scalar_one_or_none()


def classify(row: dict[str, object]) -> tuple[str, str]:
    if int(row["sector_mapped_symbols"]) == 0:
        return "not_ready", "no_sector_mapping"
    if int(row["valid_price_symbols"]) == 0:
        return "not_ready", "no_valid_daily_prices"
    if int(row["nifty_overlap_sessions"]) < int(row["min_rrg_sessions"]):
        return "not_ready", "insufficient_nifty_overlap"
    if int(row["sector_valid_sessions"]) < int(row["min_rrg_sessions"]):
        return "not_ready", "insufficient_sector_history"
    if float(row["daily_price_coverage_pct"]) < 0.80:
        return "warning", "low_daily_price_coverage"
    return "ready", "ok"


def build_audit(frame: pd.DataFrame, nifty: pd.DataFrame, as_of: date, min_rrg_sessions: int) -> list[dict[str, object]]:
    nifty_dates = set(nifty["date"]) if not nifty.empty else set()
    rows: list[dict[str, object]] = []
    if frame.empty:
        return rows
    mapped = frame[frame["sector"].notna()].copy()
    for sector, group in mapped.groupby("sector"):
        symbols = set(map(str, group["symbol"].dropna().unique()))
        valid = group[group["close"].notna()].copy()
        valid_symbols = set(map(str, valid["symbol"].dropna().unique()))
        sector_dates = set(valid["date"].dropna().unique())
        overlap = sector_dates & nifty_dates
        expected_rows = len(symbols) * len(set(group["date"].dropna().unique()))
        valid_price_rows = int(valid.shape[0])
        audit_row: dict[str, object] = {
            "as_of": as_of.isoformat(),
            "sector": str(sector),
            "sector_mapped_symbols": len(symbols),
            "valid_price_symbols": len(valid_symbols),
            "feature_sessions": len(set(group["date"].dropna().unique())),
            "sector_valid_sessions": len(sector_dates),
            "nifty_sessions": len(nifty_dates),
            "nifty_overlap_sessions": len(overlap),
            "missing_daily_price_rows": max(0, expected_rows - valid_price_rows),
            "daily_price_coverage_pct": valid_price_rows / expected_rows if expected_rows else 0.0,
            "first_sector_date": min(sector_dates).isoformat() if sector_dates else None,
            "last_sector_date": max(sector_dates).isoformat() if sector_dates else None,
            "first_overlap_date": min(overlap).isoformat() if overlap else None,
            "last_overlap_date": max(overlap).isoformat() if overlap else None,
            "min_rrg_sessions": min_rrg_sessions,
        }
        status, reason = classify(audit_row)
        audit_row["status"] = status
        audit_row["reason"] = reason
        if reason == "insufficient_nifty_overlap":
            audit_row["recommended_fix"] = "Backfill or refresh NIFTY50 15-minute benchmark candles for the lookback window."
        elif reason == "insufficient_sector_history":
            audit_row["recommended_fix"] = "Backfill Angel candles and rerun daily bars/features for sector constituents."
        elif reason == "low_daily_price_coverage":
            audit_row["recommended_fix"] = "Audit missing daily bars for sector symbols; backfill missing Angel candles if needed."
        elif reason == "no_valid_daily_prices":
            audit_row["recommended_fix"] = "Generate pilot daily bars/features for mapped sector symbols."
        else:
            audit_row["recommended_fix"] = "No data fix required for RRG readiness."
        rows.append(audit_row)
    return sorted(rows, key=lambda item: (str(item["status"]), str(item["sector"])))


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
    rows = payload["sectors"]
    counts = payload["counts"]
    lines = [
        "# Sector RRG Data Coverage Audit",
        "",
        "Read-only audit of the data needed to compute real RS-Ratio / RS-Momentum sector rotation tails.",
        "",
        "## Summary",
        "",
        f"- As of: `{payload['as_of']}`",
        f"- Sectors audited: `{len(rows)}`",
        f"- Ready: `{counts.get('ready', 0)}`",
        f"- Warning: `{counts.get('warning', 0)}`",
        f"- Not ready: `{counts.get('not_ready', 0)}`",
        f"- Minimum required overlap sessions: `{payload['min_rrg_sessions']}`",
        "",
        "## Sector Results",
        "",
        "| Sector | Status | Reason | Valid Sessions | Nifty Overlap | Price Coverage | Fix |",
        "| --- | --- | --- | ---: | ---: | ---: | --- |",
    ]
    for row in rows:
        lines.append(
            f"| {row['sector']} | {row['status']} | {row['reason']} | "
            f"{row['sector_valid_sessions']} | {row['nifty_overlap_sessions']} | "
            f"{float(row['daily_price_coverage_pct']) * 100:.1f}% | {row['recommended_fix']} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- `ready` means enough sector and Nifty 50 history exists for a reliable RRG tail.",
            "- `warning` means the sector can compute, but some constituent daily bars are missing.",
            "- `not_ready` means the page should not make a rotation call for that sector yet.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    engine = engine_from_env()
    as_of = args.as_of or latest_feature_date(engine, args.pilot_schema)
    if as_of is None:
        raise RuntimeError("No pilot features_daily date found.")
    frame = load_frame(engine, args.pilot_schema, as_of, args.lookback_days)
    nifty = load_nifty(engine, as_of, args.lookback_days)
    rows = build_audit(frame, nifty, as_of, args.min_rrg_sessions)
    counts: dict[str, int] = {}
    for row in rows:
        counts[str(row["status"])] = counts.get(str(row["status"]), 0) + 1
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "as_of": as_of.isoformat(),
        "lookback_days": args.lookback_days,
        "min_rrg_sessions": args.min_rrg_sessions,
        "counts": counts,
        "sectors": rows,
    }
    write_csv(args.csv_out, rows)
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    args.doc_out.parent.mkdir(parents=True, exist_ok=True)
    args.doc_out.write_text(render_doc(payload), encoding="utf-8")
    print(json.dumps({"status": "success", "counts": counts, "csv": str(args.csv_out), "doc": str(args.doc_out)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
