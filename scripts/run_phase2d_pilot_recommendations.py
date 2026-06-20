#!/usr/bin/env python3
"""Phase 2D pilot Swing V2.1 recommendation generation.

Reads:
  - angel_data.pilot_phase2a.scores_daily

Writes:
  - angel_data.pilot_phase2a.recommendations_daily
  - reports/phase2d_*.csv
  - reports/phase2d_recommendation_validation.json

Does not:
  - Modify production tables
  - Run backtests
  - Run portfolio simulation
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from app.recommendations.generate_recommendations import SWING_V2_1_RECOMMENDATION_CONFIG, rank_recommendations

EMA200_EXTENSION_MIN = 0.0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate pilot-only Swing V2.1 recommendations from Phase 2C scores.")
    parser.add_argument("--research-database-url", default=os.environ.get("DATABASE_URL"))
    parser.add_argument("--angel-database-url", default=os.environ.get("ANGEL_DATABASE_URL"))
    parser.add_argument("--angel-database-name", default="angel_data")
    parser.add_argument("--pilot-schema", default="pilot_phase2a")
    parser.add_argument("--universe-csv", help="Optional universe CSV used to filter symbols before ranking.")
    parser.add_argument("--output-json", default="reports/phase2d_recommendation_validation.json")
    parser.add_argument("--coverage-csv", default="reports/phase2d_recommendation_coverage_by_date.csv")
    parser.add_argument("--symbol-csv", default="reports/phase2d_recommendations_by_symbol.csv")
    parser.add_argument("--distribution-csv", default="reports/phase2d_recommendation_score_distribution.csv")
    return parser.parse_args()


def derive_angel_url(research_database_url: str | None, database_name: str) -> str | None:
    if not research_database_url:
        return None
    parts = urlsplit(research_database_url)
    return urlunsplit((parts.scheme, parts.netloc, f"/{database_name}", parts.query, parts.fragment))


def load_scores(angel_url: str, schema: str) -> pd.DataFrame:
    engine = create_engine(angel_url, future=True)
    query = f"""
        SELECT
            symbol,
            date,
            sector,
            swing_v2_1_score,
            adx_points,
            sector_points,
            ema200_extension,
            prior_20d_return,
            sector_rank_3m,
            production_eligible,
            strict_warmup_eligible
        FROM {schema}.scores_daily
        ORDER BY date, symbol
    """
    frame = pd.read_sql_query(query, engine)
    frame["date"] = pd.to_datetime(frame["date"]).dt.date
    for column in [
        "swing_v2_1_score",
        "adx_points",
        "sector_points",
        "ema200_extension",
        "prior_20d_return",
        "sector_rank_3m",
    ]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame


def load_universe_symbols(universe_csv: str | None) -> set[str]:
    if not universe_csv:
        return set()
    path = REPO_ROOT / universe_csv
    if not path.exists():
        return set()
    frame = pd.read_csv(path)
    if "symbol" not in frame.columns:
        return set()
    if "status" in frame.columns:
        frame = frame[frame["status"].astype(str).str.lower() == "ready"]
    return {str(symbol).strip().upper() for symbol in frame["symbol"].dropna().tolist() if str(symbol).strip()}


def generate_recommendations(scores: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    config = SWING_V2_1_RECOMMENDATION_CONFIG
    for score_date, date_scores in scores.groupby("date", sort=True):
        candidates = [
            (row.symbol, float(row.swing_v2_1_score), None)
            for row in date_scores.itertuples(index=False)
            if recommendation_eligible(row)
        ]
        ranked = rank_recommendations(
            candidates,
            minimum_score=config.minimum_score,
            top_n=config.top_n,
        )
        score_lookup = date_scores.set_index("symbol").to_dict(orient="index")
        for rank, (symbol, score, _model_version_id) in enumerate(ranked, start=1):
            source = score_lookup[symbol]
            rows.append(
                {
                    "date": score_date,
                    "model": config.recommendation_type,
                    "rank": rank,
                    "symbol": symbol,
                    "score": score,
                    "sector": source.get("sector"),
                    "adx_points": source.get("adx_points"),
                    "sector_points": source.get("sector_points"),
                    "ema200_extension": source.get("ema200_extension"),
                    "prior_20d_return": source.get("prior_20d_return"),
                    "sector_rank_3m": source.get("sector_rank_3m"),
                    "production_eligible": source.get("production_eligible"),
                    "strict_warmup_eligible": source.get("strict_warmup_eligible"),
                }
            )
    return pd.DataFrame(rows)


def recommendation_eligible(row) -> bool:
    if pd.isna(row.swing_v2_1_score):
        return False
    if pd.isna(row.ema200_extension):
        return False
    return float(row.ema200_extension) > EMA200_EXTENSION_MIN


def create_table(connection, schema: str) -> None:
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
                PRIMARY KEY (date, model, symbol),
                UNIQUE (date, model, rank)
            )
            """
        )
    )
    connection.execute(text(f"CREATE INDEX IF NOT EXISTS ix_phase2d_recommendations_date ON {schema}.recommendations_daily (date)"))
    connection.execute(text(f"CREATE INDEX IF NOT EXISTS ix_phase2d_recommendations_symbol ON {schema}.recommendations_daily (symbol)"))


def write_recommendations(angel_url: str, schema: str, recommendations: pd.DataFrame) -> None:
    engine = create_engine(angel_url, future=True)
    with engine.begin() as connection:
        create_table(connection, schema)
        connection.execute(text(f"TRUNCATE TABLE {schema}.recommendations_daily"))

    out = recommendations.copy()
    for column in ["rank", "adx_points", "sector_points", "sector_rank_3m"]:
        out[column] = out[column].astype("Int64")
    out.to_sql("recommendations_daily", engine, schema=schema, if_exists="append", index=False, method="multi", chunksize=5000)


def summarize(scores: pd.DataFrame, recommendations: pd.DataFrame) -> dict[str, object]:
    config = SWING_V2_1_RECOMMENDATION_CONFIG
    coverage_rows = []
    for score_date, date_scores in scores.groupby("date", sort=True):
        scored = date_scores[date_scores["swing_v2_1_score"].notna()]
        eligible = scored[scored["ema200_extension"].notna() & (scored["ema200_extension"] > EMA200_EXTENSION_MIN)]
        qualified = eligible[eligible["swing_v2_1_score"] >= config.minimum_score]
        recs = recommendations[recommendations["date"] == score_date]
        coverage_rows.append(
            {
                "date": score_date.isoformat(),
                "scored_rows": int(len(scored)),
                "qualified_rows": int(len(qualified)),
                "recommendations": int(len(recs)),
                "expected_recommendations": int(min(config.top_n, len(qualified))),
                "min_recommendation_score": None if recs.empty else round(float(recs["score"].min()), 6),
                "median_recommendation_score": None if recs.empty else round(float(recs["score"].median()), 6),
                "max_recommendation_score": None if recs.empty else round(float(recs["score"].max()), 6),
            }
        )

    symbol_rows = []
    if not recommendations.empty:
        for symbol, symbol_recs in recommendations.groupby("symbol", sort=True):
            symbol_rows.append(
                {
                    "symbol": symbol,
                    "recommendation_count": int(len(symbol_recs)),
                    "first_recommendation_date": symbol_recs["date"].min().isoformat(),
                    "last_recommendation_date": symbol_recs["date"].max().isoformat(),
                    "best_rank": int(symbol_recs["rank"].min()),
                    "avg_rank": round(float(symbol_recs["rank"].mean()), 4),
                    "avg_score": round(float(symbol_recs["score"].mean()), 6),
                    "max_score": round(float(symbol_recs["score"].max()), 6),
                }
            )

    distribution = []
    if recommendations.empty:
        distribution = [
            {"bucket": "[70,80)", "rows": 0},
            {"bucket": "[80,90)", "rows": 0},
            {"bucket": "[90,100]", "rows": 0},
        ]
    else:
        scores_rec = recommendations["score"]
        distribution = [
            {"bucket": "[70,80)", "rows": int(((scores_rec >= 70) & (scores_rec < 80)).sum())},
            {"bucket": "[80,90)", "rows": int(((scores_rec >= 80) & (scores_rec < 90)).sum())},
            {"bucket": "[90,100]", "rows": int(((scores_rec >= 90) & (scores_rec <= 100)).sum())},
        ]

    mismatched_counts = [row for row in coverage_rows if row["recommendations"] != row["expected_recommendations"]]
    rank_violations = 0
    if not recommendations.empty:
        for _score_date, recs in recommendations.groupby("date"):
            expected_symbols = [
                symbol
                for symbol, _score, _version in rank_recommendations(
                    [
                        (row.symbol, float(row.swing_v2_1_score), None)
                        for row in scores[scores["date"] == _score_date].itertuples(index=False)
                        if recommendation_eligible(row)
                    ],
                    minimum_score=config.minimum_score,
                    top_n=config.top_n,
                )
            ]
            actual_symbols = recs.sort_values("rank")["symbol"].tolist()
            if actual_symbols != expected_symbols:
                rank_violations += 1

    return {
        "generated_on": date.today().isoformat(),
        "mode": "phase2d_pilot_recommendations",
        "production_tables_modified": False,
        "backtests_run": False,
        "portfolio_simulation_run": False,
        "summary": {
            "score_dates_seen": int(scores["date"].nunique()),
            "recommendation_dates": int(recommendations["date"].nunique()) if not recommendations.empty else 0,
            "recommendation_rows": int(len(recommendations)),
            "symbols_recommended": int(recommendations["symbol"].nunique()) if not recommendations.empty else 0,
            "first_recommendation_date": None if recommendations.empty else recommendations["date"].min().isoformat(),
            "last_recommendation_date": None if recommendations.empty else recommendations["date"].max().isoformat(),
            "minimum_score": config.minimum_score,
            "top_n": config.top_n,
            "ema200_extension_min": EMA200_EXTENSION_MIN,
            "ema200_positive_gate": "signal close must be greater than signal EMA200",
        },
        "production_logic_comparison": {
            "config_used": "SWING_V2_1_RECOMMENDATION_CONFIG",
            "recommendation_type": config.recommendation_type,
            "score_field": config.score_field,
            "minimum_score": config.minimum_score,
            "top_n": config.top_n,
            "ranking_function": "app.recommendations.generate_recommendations.rank_recommendations",
            "ranking_order": "score descending, symbol ascending for ties",
            "new_filters_added": True,
            "new_filter": "ema200_extension > 0, equivalent to price > EMA200 on the daily signal date",
        },
        "validation": {
            "count_mismatch_dates": len(mismatched_counts),
            "rank_mismatch_dates": rank_violations,
            "recommendations_below_minimum_score": int((recommendations["score"] < config.minimum_score).sum()) if not recommendations.empty else 0,
            "dates_above_top_n": int((pd.DataFrame(coverage_rows)["recommendations"] > config.top_n).sum()) if coverage_rows else 0,
        },
        "coverage_by_date": coverage_rows,
        "coverage_by_symbol": symbol_rows,
        "score_distribution": distribution,
    }


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    load_dotenv(REPO_ROOT / ".env")
    args = parse_args()
    research_url = args.research_database_url or os.environ.get("DATABASE_URL")
    angel_url = args.angel_database_url or derive_angel_url(research_url, args.angel_database_name)
    if not angel_url:
        raise RuntimeError("Angel database URL is required.")

    scores = load_scores(angel_url, args.pilot_schema)
    universe_symbols = load_universe_symbols(args.universe_csv)
    if universe_symbols:
        scores = scores[scores["symbol"].astype(str).str.upper().isin(universe_symbols)].copy()
    recommendations = generate_recommendations(scores)
    write_recommendations(angel_url, args.pilot_schema, recommendations)
    report = summarize(scores, recommendations)

    output_path = REPO_ROOT / args.output_json
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    write_csv(REPO_ROOT / args.coverage_csv, report["coverage_by_date"])
    write_csv(REPO_ROOT / args.symbol_csv, report["coverage_by_symbol"])
    write_csv(REPO_ROOT / args.distribution_csv, report["score_distribution"])

    print(json.dumps(report["summary"], indent=2, default=str))
    print(f"Wrote Phase 2D recommendation validation report: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
