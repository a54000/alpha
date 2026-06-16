#!/usr/bin/env python3
"""Capture read-only explainability snapshots for generated recommendations.

Reads:
  - pilot_phase2a.recommendations_daily
  - pilot_phase2a.features_daily

Writes:
  - recommendation_decision_journal

Does not:
  - Modify scoring
  - Modify ranking
  - Add factors
  - Change strategy rules
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from dotenv import load_dotenv
from sqlalchemy import Column, Date, DateTime, Integer, JSON, MetaData, Numeric, String, Table, Text, UniqueConstraint, create_engine, text
from sqlalchemy.engine import Engine

REPO_ROOT = Path(__file__).resolve().parents[1]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Capture recommendation decision journal snapshots.")
    parser.add_argument("--business-date", help="Date to capture. Defaults to latest recommendation date.")
    parser.add_argument("--recommendation-type", default="swing_v2_1")
    parser.add_argument("--research-database-url", default=os.environ.get("DATABASE_URL"))
    parser.add_argument("--angel-database-url", default=os.environ.get("ANGEL_DATABASE_URL"))
    parser.add_argument("--angel-database-name", default="angel_data")
    parser.add_argument("--pilot-schema", default="pilot_phase2a")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--output-json", default="reports/phase5_1_decision_journal_capture.json")
    return parser.parse_args(argv)


def derive_angel_url(research_database_url: str | None, database_name: str) -> str | None:
    if not research_database_url:
        return None
    parts = urlsplit(research_database_url)
    return urlunsplit((parts.scheme, parts.netloc, f"/{database_name}", parts.query, parts.fragment))


def ensure_journal_table(engine: Engine) -> None:
    metadata = MetaData()
    Table(
        "recommendation_decision_journal",
        metadata,
        Column("journal_id", Integer, primary_key=True, autoincrement=True),
        Column("business_date", Date, nullable=False),
        Column("symbol", String(40), nullable=False),
        Column("rank", Integer, nullable=False),
        Column("score", Numeric(10, 4)),
        Column("recommendation_type", String(40), nullable=False),
        Column("sector", String(80)),
        Column("feature_snapshot_json", JSON, nullable=False),
        Column("created_at", DateTime),
        UniqueConstraint("business_date", "symbol", "recommendation_type", name="uq_recommendation_decision_journal_date_symbol_type"),
    )
    metadata.create_all(engine, checkfirst=True)


def latest_recommendation_date(angel_engine: Engine, schema: str, recommendation_type: str) -> date | None:
    with angel_engine.connect() as connection:
        return connection.execute(
            text(f"SELECT MAX(date) FROM {schema}.recommendations_daily WHERE model = :model"),
            {"model": recommendation_type},
        ).scalar_one_or_none()


def load_snapshots(angel_engine: Engine, schema: str, business_date: date, recommendation_type: str) -> list[dict[str, object]]:
    with angel_engine.connect() as connection:
        rows = connection.execute(
            text(
                f"""
                SELECT
                    r.date AS business_date,
                    r.symbol,
                    r.rank,
                    r.score,
                    r.model AS recommendation_type,
                    r.sector,
                    f.sector_rank_3m,
                    f.adx_14,
                    f.ema_200,
                    f.ema200_extension,
                    f.prior_20d_return
                FROM {schema}.recommendations_daily r
                LEFT JOIN {schema}.features_daily f
                  ON f.symbol = r.symbol
                 AND f.date = r.date
                WHERE r.date = :business_date
                  AND r.model = :model
                ORDER BY r.rank ASC, r.symbol ASC
                """
            ),
            {"business_date": business_date, "model": recommendation_type},
        ).mappings().all()
    snapshots = []
    for row in rows:
        feature_snapshot = {
            "sector_rank_3m": row["sector_rank_3m"],
            "adx_14": row["adx_14"],
            "ema_200": row["ema_200"],
            "ema200_extension": row["ema200_extension"],
            "prior_20d_return": row["prior_20d_return"],
            "final_score": row["score"],
        }
        snapshots.append(
            {
                "business_date": row["business_date"],
                "symbol": row["symbol"],
                "rank": row["rank"],
                "score": row["score"],
                "recommendation_type": row["recommendation_type"],
                "sector": row["sector"],
                "feature_snapshot_json": json.loads(json.dumps(feature_snapshot, default=str)),
            }
        )
    return snapshots


def upsert_snapshots(research_engine: Engine, snapshots: list[dict[str, object]]) -> int:
    if not snapshots:
        return 0
    with research_engine.begin() as connection:
        dialect = connection.dialect.name
        if dialect == "postgresql":
            connection.execute(
                text(
                    """
                    INSERT INTO recommendation_decision_journal (
                        business_date, symbol, rank, score, recommendation_type, sector, feature_snapshot_json, created_at
                    )
                    VALUES (
                        :business_date, :symbol, :rank, :score, :recommendation_type, :sector,
                        CAST(:feature_snapshot_json AS json), CURRENT_TIMESTAMP
                    )
                    ON CONFLICT (business_date, symbol, recommendation_type) DO UPDATE SET
                        rank = EXCLUDED.rank,
                        score = EXCLUDED.score,
                        sector = EXCLUDED.sector,
                        feature_snapshot_json = EXCLUDED.feature_snapshot_json
                    """
                ),
                [
                    {**row, "feature_snapshot_json": json.dumps(row["feature_snapshot_json"], default=str)}
                    for row in snapshots
                ],
            )
        else:
            for row in snapshots:
                existing = connection.execute(
                    text(
                        """
                        SELECT journal_id
                        FROM recommendation_decision_journal
                        WHERE business_date = :business_date
                          AND symbol = :symbol
                          AND recommendation_type = :recommendation_type
                        """
                    ),
                    row,
                ).scalar_one_or_none()
                payload = {**row, "feature_snapshot_json": json.dumps(row["feature_snapshot_json"], default=str)}
                if existing is None:
                    connection.execute(
                        text(
                            """
                            INSERT INTO recommendation_decision_journal (
                                business_date, symbol, rank, score, recommendation_type, sector, feature_snapshot_json, created_at
                            )
                            VALUES (
                                :business_date, :symbol, :rank, :score, :recommendation_type, :sector,
                                :feature_snapshot_json, CURRENT_TIMESTAMP
                            )
                            """
                        ),
                        payload,
                    )
                else:
                    connection.execute(
                        text(
                            """
                            UPDATE recommendation_decision_journal
                               SET rank = :rank,
                                   score = :score,
                                   sector = :sector,
                                   feature_snapshot_json = :feature_snapshot_json
                             WHERE journal_id = :journal_id
                            """
                        ),
                        {**payload, "journal_id": existing},
                    )
    return len(snapshots)


def main() -> int:
    load_dotenv(REPO_ROOT / ".env")
    args = parse_args()
    research_url = args.research_database_url or os.environ.get("DATABASE_URL")
    angel_url = args.angel_database_url or derive_angel_url(research_url, args.angel_database_name)
    if not research_url or not angel_url:
        raise RuntimeError("DATABASE_URL and Angel database URL are required.")
    research_engine = create_engine(research_url, future=True)
    angel_engine = create_engine(angel_url, future=True)
    if not args.dry_run:
        ensure_journal_table(research_engine)
    business_date = date.fromisoformat(args.business_date) if args.business_date else latest_recommendation_date(
        angel_engine,
        args.pilot_schema,
        args.recommendation_type,
    )
    if business_date is None:
        raise RuntimeError("No recommendation date found to capture.")
    snapshots = load_snapshots(angel_engine, args.pilot_schema, business_date, args.recommendation_type)
    written = 0 if args.dry_run else upsert_snapshots(research_engine, snapshots)
    report = {
        "business_date": business_date.isoformat(),
        "recommendation_type": args.recommendation_type,
        "dry_run": args.dry_run,
        "snapshots_seen": len(snapshots),
        "snapshots_written": written,
        "constraints": {
            "scoring_changed": False,
            "ranking_changed": False,
            "factors_added": False,
            "strategy_rules_changed": False,
        },
    }
    output_path = REPO_ROOT / args.output_json
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(json.dumps(report, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
