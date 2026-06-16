#!/usr/bin/env python3
"""Generate pilot recommendation rows for the Rolling 10 1M/3M candidate.

This appends/replaces only the candidate model rows in the pilot schema. It
does not overwrite frozen Swing V2.1 recommendation rows.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.run_sector_1m3m_rank_experiment import (  # noqa: E402
    generate_recommendations,
    load_features_and_sector_returns,
    score_frame,
)

MODEL = "sector_rotation_adx_1m3m"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate pilot 1M/3M sector recommendation rows.")
    parser.add_argument("--research-database-url", default=os.environ.get("DATABASE_URL"))
    parser.add_argument("--angel-database-url", default=os.environ.get("ANGEL_DATABASE_URL"))
    parser.add_argument("--angel-database-name", default="angel_data")
    parser.add_argument("--pilot-schema", default="pilot_phase2a")
    parser.add_argument("--start-date", type=date.fromisoformat, default=date(2022, 5, 25))
    parser.add_argument("--end-date", type=date.fromisoformat, default=date.today())
    parser.add_argument("--minimum-score", type=float, default=70.0)
    parser.add_argument("--top-n", type=int, default=20)
    parser.add_argument("--weight-1m", type=float, default=0.40)
    parser.add_argument("--weight-3m", type=float, default=0.60)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--output-json", default="reports/rolling10_1m3m_candidate_recommendations.json")
    return parser.parse_args()


def derive_angel_url(research_database_url: str | None, database_name: str) -> str | None:
    if not research_database_url:
        return None
    parts = urlsplit(research_database_url)
    return urlunsplit((parts.scheme, parts.netloc, f"/{database_name}", parts.query, parts.fragment))


def ensure_table(connection, schema: str) -> None:
    connection.execute(
        text(
            f"""
            CREATE TABLE IF NOT EXISTS {schema}.recommendations_daily (
                date date NOT NULL,
                model text NOT NULL,
                rank integer NOT NULL,
                symbol text NOT NULL,
                score numeric,
                sector text,
                adx_points integer,
                sector_points integer,
                ema200_extension numeric,
                prior_20d_return numeric,
                sector_rank_3m integer,
                production_eligible boolean,
                strict_warmup_eligible boolean,
                generated_at timestamp DEFAULT now(),
                PRIMARY KEY (date, model, symbol)
            )
            """
        )
    )
    connection.execute(text(f"CREATE INDEX IF NOT EXISTS ix_recommendations_daily_model_date ON {schema}.recommendations_daily (model, date)"))


def write_candidate_rows(engine, schema: str, rows: list[dict[str, object]], start_date: date, end_date: date) -> None:
    payload = [
        {
            "date": row["date"],
            "model": row["model"],
            "rank": row["rank"],
            "symbol": row["symbol"],
            "score": row["score"],
            "sector": row["sector"],
            "adx_points": row["adx_points"],
            "sector_points": row["sector_points"],
            "ema200_extension": row["ema200_extension"],
            "prior_20d_return": row["prior_20d_return"],
            "sector_rank_3m": row["sector_rank_used"],
        }
        for row in rows
    ]
    with engine.begin() as connection:
        ensure_table(connection, schema)
        connection.execute(
            text(
                f"""
                DELETE FROM {schema}.recommendations_daily
                WHERE model = :model
                  AND date BETWEEN :start_date AND :end_date
                """
            ),
            {"model": MODEL, "start_date": start_date, "end_date": end_date},
        )
        if payload:
            connection.execute(
                text(
                    f"""
                    INSERT INTO {schema}.recommendations_daily (
                        date, model, rank, symbol, score, sector, adx_points,
                        sector_points, ema200_extension, prior_20d_return,
                        sector_rank_3m
                    )
                    VALUES (
                        :date, :model, :rank, :symbol, :score, :sector, :adx_points,
                        :sector_points, :ema200_extension, :prior_20d_return,
                        :sector_rank_3m
                    )
                    """
                ),
                payload,
            )


def main() -> int:
    load_dotenv(REPO_ROOT / ".env")
    args = parse_args()
    angel_url = args.angel_database_url or derive_angel_url(args.research_database_url, args.angel_database_name)
    if not angel_url:
        raise RuntimeError("ANGEL_DATABASE_URL or DATABASE_URL is required.")

    engine = create_engine(angel_url, future=True, pool_pre_ping=True)
    features = load_features_and_sector_returns(engine, args.pilot_schema, args.start_date, args.end_date, args.weight_1m, args.weight_3m)
    scores = score_frame(features, "sector_rank_1m3m", "score_1m3m")
    rows = generate_recommendations(scores, "score_1m3m", args.minimum_score, args.top_n, MODEL)
    if not args.dry_run:
        write_candidate_rows(engine, args.pilot_schema, rows, args.start_date, args.end_date)

    dates = sorted({row["date"] for row in rows})
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model": MODEL,
        "dry_run": bool(args.dry_run),
        "production_tables_modified": False,
        "legacy_recommendation_model_modified": False,
        "date_range": {"start": args.start_date.isoformat(), "end": args.end_date.isoformat()},
        "recommendation_rows": len(rows),
        "recommendation_dates": len(dates),
        "first_recommendation_date": dates[0].isoformat() if dates else None,
        "last_recommendation_date": dates[-1].isoformat() if dates else None,
    }
    output_path = REPO_ROOT / args.output_json
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"Wrote candidate recommendation report: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
