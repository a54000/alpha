#!/usr/bin/env python3
"""Dry-run Phase 1B security master reconciliation.

Reads:
  - Current research database symbols
  - Angel database symbols
  - reports/angel_symbol_mapping.csv

Writes:
  - Dry-run proposal files under reports/

Does not:
  - Insert, update, or delete database rows
  - Reconcile aliases in production
  - Cut over application code
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from db.session import build_session_factory


APPROVED_MAPPING_STATUSES = {"exact", "known_rename", "normalized_match"}
REVIEW_MAPPING_STATUSES = {"potential", "ambiguous", "unmatched", "angel_only"}


@dataclass(frozen=True)
class ProposedSecurity:
    proposal_id: str
    canonical_symbol: str
    canonical_name: str | None
    exchange: str
    instrument_type: str
    status: str
    created_from_source: str
    review_status: str
    notes: str


@dataclass(frozen=True)
class ProposedAlias:
    proposal_id: str
    security_proposal_id: str
    source: str
    symbol: str
    normalized_symbol: str
    alias_reason: str
    confidence: str
    review_status: str
    notes: str


@dataclass(frozen=True)
class ManualReviewItem:
    research_symbol: str
    angel_symbol: str
    mapping_status: str
    priority: str
    reason: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate Phase 1B reconciliation proposals without database writes.")
    parser.add_argument("--mapping-csv", default="reports/angel_symbol_mapping.csv")
    parser.add_argument("--research-database-url", default=os.environ.get("DATABASE_URL"))
    parser.add_argument("--angel-database-url", default=os.environ.get("ANGEL_DATABASE_URL"))
    parser.add_argument("--angel-database-name", default="angel_data")
    parser.add_argument("--angel-table", default="ohlcv_15min")
    parser.add_argument("--output-json", default="reports/phase1b_reconciliation_dry_run.json")
    parser.add_argument("--output-securities-csv", default="reports/phase1b_security_master_proposals.csv")
    parser.add_argument("--output-aliases-csv", default="reports/phase1b_alias_proposals.csv")
    parser.add_argument("--output-review-csv", default="reports/phase1b_manual_review_queue.csv")
    return parser.parse_args()


def normalize_symbol(symbol: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", symbol.upper())


def derive_angel_url(research_database_url: str | None, database_name: str) -> str | None:
    if not research_database_url:
        return None
    parts = urlsplit(research_database_url)
    return urlunsplit((parts.scheme, parts.netloc, f"/{database_name}", parts.query, parts.fragment))


def load_mapping_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def load_research_metadata(database_url: str) -> dict[str, dict[str, str | None]]:
    factory = build_session_factory(database_url)
    with factory() as session:
        rows = session.execute(
            text(
                """
                SELECT symbol, company_name, sector
                FROM symbol_master
                ORDER BY symbol
                """
            )
        ).mappings()
        return {row["symbol"]: dict(row) for row in rows}


def load_angel_symbols(database_url: str, table_name: str) -> set[str]:
    engine = create_engine(database_url, future=True)
    with engine.connect() as connection:
        return set(connection.execute(text(f"SELECT DISTINCT symbol FROM {table_name}")).scalars())


def confidence_for_status(status: str) -> str:
    if status == "exact":
        return "high"
    if status == "known_rename":
        return "medium"
    if status == "normalized_match":
        return "medium"
    if status == "potential":
        return "low"
    return "pending"


def alias_reason_for_status(status: str) -> str:
    if status == "exact":
        return "exact"
    if status == "known_rename":
        return "rename"
    if status == "normalized_match":
        return "vendor_format"
    if status == "potential":
        return "unknown"
    return "unknown"


def make_proposals(
    mapping_rows: list[dict[str, str]],
    research_metadata: dict[str, dict[str, str | None]],
    angel_symbols: set[str],
) -> tuple[list[ProposedSecurity], list[ProposedAlias], list[ManualReviewItem], dict[str, object]]:
    securities: dict[str, ProposedSecurity] = {}
    aliases: list[ProposedAlias] = []
    review_queue: list[ManualReviewItem] = []
    security_counter = 0

    def add_security(canonical_symbol: str, source: str, review_status: str, notes: str) -> str:
        nonlocal security_counter
        key = canonical_symbol
        if key in securities:
            return securities[key].proposal_id
        security_counter += 1
        proposal_id = f"SEC-PROP-{security_counter:05d}"
        meta = research_metadata.get(canonical_symbol, {})
        securities[key] = ProposedSecurity(
            proposal_id=proposal_id,
            canonical_symbol=canonical_symbol,
            canonical_name=meta.get("company_name"),
            exchange="NSE",
            instrument_type="equity",
            status="active",
            created_from_source=source,
            review_status=review_status,
            notes=notes,
        )
        return proposal_id

    def add_alias(security_id: str, source: str, symbol: str, status: str, notes: str) -> None:
        aliases.append(
            ProposedAlias(
                proposal_id=f"ALIAS-PROP-{len(aliases) + 1:05d}",
                security_proposal_id=security_id,
                source=source,
                symbol=symbol,
                normalized_symbol=normalize_symbol(symbol),
                alias_reason=alias_reason_for_status(status),
                confidence=confidence_for_status(status),
                review_status="approved" if status == "exact" else "needs_review",
                notes=notes,
            )
        )

    for row in mapping_rows:
        research_symbol = (row.get("research_symbol") or "").strip()
        angel_symbol = (row.get("angel_symbol") or "").strip()
        status = (row.get("mapping_status") or "").strip()

        if status in APPROVED_MAPPING_STATUSES and research_symbol and angel_symbol and "|" not in angel_symbol:
            canonical = angel_symbol if status in {"known_rename", "normalized_match"} else research_symbol
            security_id = add_security(
                canonical,
                "mapping_csv",
                "approved" if status == "exact" else "needs_review",
                f"Dry-run proposal from {status} mapping.",
            )
            add_alias(security_id, "research", research_symbol, status, f"Research symbol from {status} mapping.")
            add_alias(security_id, "angel", angel_symbol, status, f"Angel symbol from {status} mapping.")
            continue

        if status == "angel_only" and angel_symbol:
            security_id = add_security(
                angel_symbol,
                "angel",
                "needs_review",
                "Angel-only symbol; candidate current NSE security missing from research universe.",
            )
            add_alias(security_id, "angel", angel_symbol, status, "Angel-only dry-run alias proposal.")
            review_queue.append(
                ManualReviewItem(
                    research_symbol="",
                    angel_symbol=angel_symbol,
                    mapping_status=status,
                    priority="medium",
                    reason="Angel-only symbol needs universe membership decision.",
                )
            )
            continue

        if status in REVIEW_MAPPING_STATUSES:
            review_queue.append(
                ManualReviewItem(
                    research_symbol=research_symbol,
                    angel_symbol=angel_symbol,
                    mapping_status=status,
                    priority="high" if status in {"ambiguous", "potential"} else "medium",
                    reason="Not safe for production alias insertion without manual review.",
                )
            )

    mapped_research = {
        row["research_symbol"]
        for row in mapping_rows
        if row.get("research_symbol") and row.get("mapping_status") in APPROVED_MAPPING_STATUSES
    }
    summary = {
        "generated_on": date.today().isoformat(),
        "mode": "dry_run",
        "database_writes": 0,
        "mapping_rows": len(mapping_rows),
        "research_symbols_seen": len({row.get("research_symbol") for row in mapping_rows if row.get("research_symbol")}),
        "angel_symbols_seen": len(angel_symbols),
        "proposed_security_master_records": len(securities),
        "proposed_alias_records": len(aliases),
        "manual_review_items": len(review_queue),
        "approved_or_seedable_research_symbols": len(mapped_research),
        "mapping_status_counts": dict(sorted(_count_statuses(mapping_rows).items())),
    }
    return list(securities.values()), aliases, review_queue, summary


def _count_statuses(rows: list[dict[str, str]]) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for row in rows:
        counts[row.get("mapping_status") or ""] += 1
    return counts


def write_csv(path: Path, rows: list[object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = [asdict(row) for row in rows]
    if not payload:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(payload[0].keys()))
        writer.writeheader()
        writer.writerows(payload)


def main() -> int:
    load_dotenv(REPO_ROOT / ".env")
    args = parse_args()
    research_url = args.research_database_url or os.environ.get("DATABASE_URL")
    angel_url = args.angel_database_url or derive_angel_url(research_url, args.angel_database_name)
    if not research_url or not angel_url:
        raise RuntimeError("DATABASE_URL and Angel database URL are required for dry-run reconciliation.")

    mapping_rows = load_mapping_rows(REPO_ROOT / args.mapping_csv)
    research_metadata = load_research_metadata(research_url)
    angel_symbols = load_angel_symbols(angel_url, args.angel_table)
    securities, aliases, review_queue, summary = make_proposals(mapping_rows, research_metadata, angel_symbols)

    output_json = REPO_ROOT / args.output_json
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(
        json.dumps(
            {
                "summary": summary,
                "proposed_security_master_records": [asdict(row) for row in securities],
                "proposed_alias_records": [asdict(row) for row in aliases],
                "manual_review_queue": [asdict(row) for row in review_queue],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    write_csv(REPO_ROOT / args.output_securities_csv, securities)
    write_csv(REPO_ROOT / args.output_aliases_csv, aliases)
    write_csv(REPO_ROOT / args.output_review_csv, review_queue)

    print(json.dumps(summary, indent=2))
    print(f"Wrote dry-run JSON: {output_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
