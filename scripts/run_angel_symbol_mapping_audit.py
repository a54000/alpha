#!/usr/bin/env python3
"""Build a read-only symbol mapping audit between research and Angel universes."""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from db.session import build_session_factory


KNOWN_MAPPINGS = {
    "ADANITRANS": "ADANIENSOL",
    "AMARAJABAT": "ARE&M",
    "CADILAHC": "ZYDUSLIFE",
    "GMRINFRA": "GMRP&UI",
    "IBULHSGFIN": "SAMMAANCAP",
    "INFRATEL": "INDUSTOWER",
    "ISEC": "ICICISEC",
    "KALPATPOWR": "KPIL",
    "LTI": "LTIM",
    "MAHINDCIE": "CIEINDIA",
    "MINDTREE": "LTIM",
    "MCDOWELL-N": "UNITDSPR",
    "MINDAIND": "UNOMINDA",
    "MOTHERSUMI": "MSUMI",
    "NIITTECH": "COFORGE",
    "PEL": "PIRAMALENT",
    "PHILIPCARB": "PCBL",
    "RNAM": "NAM-INDIA",
    "SRTRANSFIN": "SHRIRAMFIN",
    "TATAGLOBAL": "TATACONSUM",
    "WABCOINDIA": "ZFCVINDIA",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit research-to-Angel symbol mappings without modifying data.")
    parser.add_argument("--angel-database-url", default=os.environ.get("ANGEL_DATABASE_URL"))
    parser.add_argument("--research-database-url", default=os.environ.get("DATABASE_URL"))
    parser.add_argument("--database-name", default="angel_data")
    parser.add_argument("--table", default="ohlcv_15min")
    parser.add_argument("--output", default="reports/angel_symbol_mapping.csv")
    return parser.parse_args()


def derive_angel_url(research_database_url: str | None, database_name: str) -> str | None:
    if not research_database_url:
        return None
    parts = urlsplit(research_database_url)
    return urlunsplit((parts.scheme, parts.netloc, f"/{database_name}", parts.query, parts.fragment))


def normalize(symbol: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", symbol.upper())


def research_symbols(database_url: str) -> list[str]:
    session_factory = build_session_factory(database_url)
    with session_factory() as session:
        snapshot_date = session.execute(text("SELECT MAX(date) FROM universe_snapshot WHERE index_name = 'NSE500'")).scalar()
        if snapshot_date is not None:
            return list(
                session.execute(
                    text(
                        """
                        SELECT symbol
                        FROM universe_snapshot
                        WHERE index_name = 'NSE500' AND date = :snapshot_date
                        ORDER BY symbol
                        """
                    ),
                    {"snapshot_date": snapshot_date},
                ).scalars()
            )
        return list(session.execute(text("SELECT symbol FROM symbol_master WHERE nse500 = true ORDER BY symbol")).scalars())


def angel_symbols(database_url: str, table_name: str) -> list[str]:
    engine = create_engine(database_url, future=True)
    with engine.connect() as connection:
        return list(connection.execute(text(f"SELECT DISTINCT symbol FROM {table_name} ORDER BY symbol")).scalars())


def classify_mapping(symbol: str, angel_set: set[str], normalized_index: dict[str, list[str]]) -> tuple[str, str, str]:
    if symbol in angel_set:
        return symbol, "exact", "Exact symbol match."

    known = KNOWN_MAPPINGS.get(symbol)
    if known and known in angel_set:
        return known, "known_rename", "Known rename or corporate-action symbol change; verify before production use."

    normalized = normalize(symbol)
    normalized_matches = normalized_index.get(normalized, [])
    if len(normalized_matches) == 1:
        return normalized_matches[0], "normalized_match", "Matches after removing punctuation."
    if len(normalized_matches) > 1:
        return "|".join(normalized_matches), "ambiguous", "Multiple Angel symbols match after normalization."

    prefix_matches = sorted(
        candidate
        for candidate in angel_set
        if normalize(candidate).startswith(normalized[:5]) or normalized.startswith(normalize(candidate)[:5])
    )
    if len(prefix_matches) == 1:
        return prefix_matches[0], "potential", "Potential one-to-one prefix similarity; manual review required."
    if len(prefix_matches) > 1:
        return "|".join(prefix_matches[:10]), "ambiguous", "Multiple prefix-similar Angel symbols; manual review required."

    return "", "unmatched", "No exact, known, normalized, or prefix candidate found."


def build_mapping(research: list[str], angel: list[str]) -> list[dict[str, str]]:
    angel_set = set(angel)
    normalized_index: dict[str, list[str]] = defaultdict(list)
    for symbol in angel:
        normalized_index[normalize(symbol)].append(symbol)

    rows: list[dict[str, str]] = []
    for symbol in research:
        mapped, status, notes = classify_mapping(symbol, angel_set, normalized_index)
        rows.append(
            {
                "research_symbol": symbol,
                "angel_symbol": mapped,
                "mapping_status": status,
                "research_normalized": normalize(symbol),
                "angel_normalized": normalize(mapped) if mapped and "|" not in mapped else "",
                "notes": notes,
            }
        )

    mapped_angel = {row["angel_symbol"] for row in rows if row["angel_symbol"] and "|" not in row["angel_symbol"]}
    for symbol in angel:
        if symbol not in mapped_angel:
            rows.append(
                {
                    "research_symbol": "",
                    "angel_symbol": symbol,
                    "mapping_status": "angel_only",
                    "research_normalized": "",
                    "angel_normalized": normalize(symbol),
                    "notes": "Present in Angel source but not mapped to current research universe.",
                }
            )
    return rows


def write_csv(rows: list[dict[str, str]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "research_symbol",
        "angel_symbol",
        "mapping_status",
        "research_normalized",
        "angel_normalized",
        "notes",
    ]
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    load_dotenv(REPO_ROOT / ".env")
    args = parse_args()
    research_url = args.research_database_url or os.environ.get("DATABASE_URL")
    angel_url = args.angel_database_url or derive_angel_url(research_url, args.database_name)
    if not research_url or not angel_url:
        raise RuntimeError("DATABASE_URL/ANGEL_DATABASE_URL is required for symbol mapping audit.")

    research = research_symbols(research_url)
    angel = angel_symbols(angel_url, args.table)
    rows = build_mapping(research, angel)
    output_path = REPO_ROOT / args.output
    write_csv(rows, output_path)

    status_counts: dict[str, int] = defaultdict(int)
    for row in rows:
        status_counts[row["mapping_status"]] += 1
    research_rows = [row for row in rows if row["research_symbol"]]
    matched_rows = [row for row in research_rows if row["mapping_status"] not in {"unmatched", "ambiguous"}]
    summary = {
        "generated_on": date.today().isoformat(),
        "research_symbol_count": len(research),
        "angel_symbol_count": len(angel),
        "mapped_research_symbols": len(matched_rows),
        "coverage_pct": round(len(matched_rows) / len(research) * 100, 2) if research else 0.0,
        "status_counts": dict(sorted(status_counts.items())),
        "output": str(output_path),
    }
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
