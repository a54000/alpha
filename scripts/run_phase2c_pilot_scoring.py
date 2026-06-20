#!/usr/bin/env python3
"""Phase 2C pilot Swing V2.1 scoring.

Reads:
  - angel_data.pilot_phase2a.features_daily

Writes:
  - angel_data.pilot_phase2a.scores_daily
  - reports/phase2c_*.csv
  - reports/phase2c_scoring_validation.json

Does not:
  - Modify production tables
  - Generate recommendations
  - Run backtests
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

from app.scoring.compute_scores import compute_swing_v2_1_score, score_swing_v2_adx, score_swing_v2_sector

DEFAULT_START_DATE = date(2022, 5, 25)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate pilot-only Swing V2.1 scores from Phase 2B features.")
    parser.add_argument("--research-database-url", default=os.environ.get("DATABASE_URL"))
    parser.add_argument("--angel-database-url", default=os.environ.get("ANGEL_DATABASE_URL"))
    parser.add_argument("--angel-database-name", default="angel_data")
    parser.add_argument("--pilot-schema", default="pilot_phase2a")
    parser.add_argument("--start-date", default=DEFAULT_START_DATE.isoformat())
    parser.add_argument("--universe-csv", help="Optional universe CSV used to filter symbols before scoring.")
    parser.add_argument("--output-json", default="reports/phase2c_scoring_validation.json")
    parser.add_argument("--coverage-csv", default="reports/phase2c_scoring_coverage_by_date.csv")
    parser.add_argument("--monthly-csv", default="reports/phase2c_scoring_coverage_by_month.csv")
    parser.add_argument("--distribution-csv", default="reports/phase2c_score_distribution_by_date.csv")
    parser.add_argument("--symbol-csv", default="reports/phase2c_scoring_coverage_by_symbol.csv")
    return parser.parse_args()


def derive_angel_url(research_database_url: str | None, database_name: str) -> str | None:
    if not research_database_url:
        return None
    parts = urlsplit(research_database_url)
    return urlunsplit((parts.scheme, parts.netloc, f"/{database_name}", parts.query, parts.fragment))


def load_features(angel_url: str, schema: str, start_date: date) -> pd.DataFrame:
    engine = create_engine(angel_url, future=True)
    query = text(
        f"""
        SELECT
            symbol,
            date,
            sector,
            close,
            ema_200,
            ema200_extension,
            prior_20d_return,
            adx_14,
            adx_prev,
            sector_rank_3m,
            history_days,
            has_ema200_warmup,
            has_prior20_warmup,
            has_adx_warmup
        FROM {schema}.features_daily
        WHERE date >= :start_date
        ORDER BY date, symbol
        """
    )
    frame = pd.read_sql_query(query, engine, params={"start_date": start_date})
    frame["date"] = pd.to_datetime(frame["date"]).dt.date
    for column in [
        "close",
        "ema_200",
        "ema200_extension",
        "prior_20d_return",
        "adx_14",
        "adx_prev",
        "sector_rank_3m",
        "history_days",
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


def production_eligible(row: pd.Series) -> bool:
    close = row["close"]
    ema_200 = row["ema_200"]
    prior = row["prior_20d_return"]
    if pd.isna(close) or pd.isna(ema_200) or float(ema_200) == 0 or pd.isna(prior):
        return False
    return ((float(close) - float(ema_200)) / float(ema_200)) <= 0.25 and float(prior) <= 0.15


def strict_warmup_eligible(row: pd.Series) -> bool:
    return (
        production_eligible(row)
        and not pd.isna(row["history_days"])
        and int(row["history_days"]) >= 200
        and not pd.isna(row["adx_14"])
        and not pd.isna(row["adx_prev"])
        and not pd.isna(row["sector_rank_3m"])
    )


def compute_scores(features: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for row in features.itertuples(index=False):
        row_dict = row._asdict()
        features_dict = {
            "close": row_dict["close"],
            "ema_200": row_dict["ema_200"],
            "prior_20d_return": row_dict["prior_20d_return"],
            "adx_14": row_dict["adx_14"],
            "adx_prev": row_dict["adx_prev"],
        }
        sector_rank = row_dict["sector_rank_3m"]
        swing_v2_1_score = compute_swing_v2_1_score(features_dict, sector_rank)
        adx_points = score_swing_v2_adx(row_dict["adx_14"], row_dict["adx_prev"])
        sector_points = score_swing_v2_sector(sector_rank)
        rows.append(
            {
                "symbol": row_dict["symbol"],
                "date": row_dict["date"],
                "sector": row_dict["sector"],
                "swing_v2_1_score": swing_v2_1_score,
                "adx_points": adx_points,
                "sector_points": sector_points,
                "ema200_extension": row_dict["ema200_extension"],
                "prior_20d_return": row_dict["prior_20d_return"],
                "sector_rank_3m": sector_rank,
                "history_days": row_dict["history_days"],
                "production_eligible": swing_v2_1_score is not None,
                "strict_warmup_eligible": strict_warmup_eligible(pd.Series(row_dict)),
            }
        )
    return pd.DataFrame(rows)


def create_table(connection, schema: str) -> None:
    connection.execute(
        text(
            f"""
            CREATE TABLE IF NOT EXISTS {schema}.scores_daily (
                symbol text NOT NULL,
                date date NOT NULL,
                sector text,
                swing_v2_1_score numeric,
                adx_points integer,
                sector_points integer,
                ema200_extension numeric,
                prior_20d_return numeric,
                sector_rank_3m integer,
                history_days integer,
                production_eligible boolean NOT NULL,
                strict_warmup_eligible boolean NOT NULL,
                generated_at timestamp DEFAULT now(),
                PRIMARY KEY (symbol, date)
            )
            """
        )
    )
    connection.execute(text(f"CREATE INDEX IF NOT EXISTS ix_phase2c_scores_date ON {schema}.scores_daily (date)"))
    connection.execute(text(f"CREATE INDEX IF NOT EXISTS ix_phase2c_scores_symbol_date ON {schema}.scores_daily (symbol, date)"))


def write_scores(angel_url: str, schema: str, scores: pd.DataFrame, start_date: date) -> None:
    engine = create_engine(angel_url, future=True)
    with engine.begin() as connection:
        create_table(connection, schema)
        connection.execute(text(f"DELETE FROM {schema}.scores_daily WHERE date >= :start_date"), {"start_date": start_date})

    out = scores.copy()
    for column in ["adx_points", "sector_points", "sector_rank_3m", "history_days"]:
        out[column] = out[column].astype("Int64")
    out.to_sql("scores_daily", engine, schema=schema, if_exists="append", index=False, method="multi", chunksize=5000)


def summarize(features: pd.DataFrame, scores: pd.DataFrame, start_date: date) -> dict[str, object]:
    scored = scores[scores["swing_v2_1_score"].notna()].copy()
    date_rows = []
    for score_date, date_scores in scores.groupby("date", sort=True):
        feature_rows = features[features["date"] == score_date]
        scored_date = date_scores[date_scores["swing_v2_1_score"].notna()]
        date_rows.append(
            {
                "date": score_date.isoformat(),
                "feature_rows": int(len(feature_rows)),
                "production_eligible": int(date_scores["production_eligible"].sum()),
                "strict_warmup_eligible": int(date_scores["strict_warmup_eligible"].sum()),
                "scored_rows": int(len(scored_date)),
                "min_score": None if scored_date.empty else round(float(scored_date["swing_v2_1_score"].min()), 6),
                "p25_score": None if scored_date.empty else round(float(scored_date["swing_v2_1_score"].quantile(0.25)), 6),
                "median_score": None if scored_date.empty else round(float(scored_date["swing_v2_1_score"].median()), 6),
                "p75_score": None if scored_date.empty else round(float(scored_date["swing_v2_1_score"].quantile(0.75)), 6),
                "max_score": None if scored_date.empty else round(float(scored_date["swing_v2_1_score"].max()), 6),
                "avg_score": None if scored_date.empty else round(float(scored_date["swing_v2_1_score"].mean()), 6),
            }
        )

    coverage = pd.DataFrame(date_rows)
    monthly = []
    if not coverage.empty:
        coverage_dates = pd.to_datetime(coverage["date"])
        coverage["_month"] = coverage_dates.dt.to_period("M").astype(str)
        for month, month_frame in coverage.groupby("_month", sort=True):
            monthly.append(
                {
                    "month": month,
                    "trading_days": int(len(month_frame)),
                    "avg_scored_rows": round(float(month_frame["scored_rows"].mean()), 2),
                    "min_scored_rows": int(month_frame["scored_rows"].min()),
                    "max_scored_rows": int(month_frame["scored_rows"].max()),
                    "avg_score": round(float(month_frame["avg_score"].dropna().mean()), 6)
                    if not month_frame["avg_score"].dropna().empty
                    else None,
                }
            )
        coverage = coverage.drop(columns=["_month"])

    symbol_rows = []
    for symbol, symbol_scores in scores.groupby("symbol", sort=True):
        symbol_scored = symbol_scores[symbol_scores["swing_v2_1_score"].notna()]
        symbol_rows.append(
            {
                "symbol": symbol,
                "rows": int(len(symbol_scores)),
                "scored_rows": int(len(symbol_scored)),
                "first_score_date": None if symbol_scored.empty else symbol_scored["date"].min().isoformat(),
                "last_score_date": None if symbol_scored.empty else symbol_scored["date"].max().isoformat(),
                "avg_score": None if symbol_scored.empty else round(float(symbol_scored["swing_v2_1_score"].mean()), 6),
            }
        )

    distribution = [
        {
            "bucket": "0",
            "rows": int((scored["swing_v2_1_score"] == 0).sum()),
        },
        {
            "bucket": "(0,20]",
            "rows": int(((scored["swing_v2_1_score"] > 0) & (scored["swing_v2_1_score"] <= 20)).sum()),
        },
        {
            "bucket": "(20,40]",
            "rows": int(((scored["swing_v2_1_score"] > 20) & (scored["swing_v2_1_score"] <= 40)).sum()),
        },
        {
            "bucket": "(40,60]",
            "rows": int(((scored["swing_v2_1_score"] > 40) & (scored["swing_v2_1_score"] <= 60)).sum()),
        },
        {
            "bucket": "(60,80]",
            "rows": int(((scored["swing_v2_1_score"] > 60) & (scored["swing_v2_1_score"] <= 80)).sum()),
        },
        {
            "bucket": "(80,100]",
            "rows": int(((scored["swing_v2_1_score"] > 80) & (scored["swing_v2_1_score"] <= 100)).sum()),
        },
    ]

    return {
        "generated_on": date.today().isoformat(),
        "mode": "phase2c_pilot_scoring",
        "scoring_start_date": start_date.isoformat(),
        "production_tables_modified": False,
        "recommendations_generated": False,
        "backtests_run": False,
        "summary": {
            "input_feature_rows": int(len(features)),
            "score_rows_written": int(len(scores)),
            "scored_rows": int(len(scored)),
            "symbols_seen": int(scores["symbol"].nunique()),
            "symbols_scored": int(scored["symbol"].nunique()),
            "first_score_date": None if scored.empty else scored["date"].min().isoformat(),
            "last_score_date": None if scored.empty else scored["date"].max().isoformat(),
            "min_score": None if scored.empty else round(float(scored["swing_v2_1_score"].min()), 6),
            "median_score": None if scored.empty else round(float(scored["swing_v2_1_score"].median()), 6),
            "max_score": None if scored.empty else round(float(scored["swing_v2_1_score"].max()), 6),
        },
        "production_logic_comparison": {
            "function_used": "app.scoring.compute_scores.compute_swing_v2_1_score",
            "eligibility": "Production function return value decides score eligibility.",
            "ema200_extension_filter": "<= 0.25 inside production function.",
            "prior_20d_return_filter": "<= 0.15 inside production function.",
            "adx": "score_swing_v2_adx from production code.",
            "sector_rank": "score_swing_v2_sector from production code using pilot sector_rank_3m.",
            "research_filters_added": False,
        },
        "coverage_by_date": date_rows,
        "coverage_by_month": monthly,
        "score_distribution": distribution,
        "coverage_by_symbol": symbol_rows,
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
    start_date = date.fromisoformat(args.start_date)
    research_url = args.research_database_url or os.environ.get("DATABASE_URL")
    angel_url = args.angel_database_url or derive_angel_url(research_url, args.angel_database_name)
    if not angel_url:
        raise RuntimeError("Angel database URL is required.")

    features = load_features(angel_url, args.pilot_schema, start_date)
    universe_symbols = load_universe_symbols(args.universe_csv)
    if universe_symbols:
        features = features[features["symbol"].astype(str).str.upper().isin(universe_symbols)].copy()
    scores = compute_scores(features)
    write_scores(angel_url, args.pilot_schema, scores, start_date)
    report = summarize(features, scores, start_date)

    output_path = REPO_ROOT / args.output_json
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    write_csv(REPO_ROOT / args.coverage_csv, report["coverage_by_date"])
    write_csv(REPO_ROOT / args.monthly_csv, report["coverage_by_month"])
    write_csv(REPO_ROOT / args.distribution_csv, report["score_distribution"])
    write_csv(REPO_ROOT / args.symbol_csv, report["coverage_by_symbol"])

    print(json.dumps(report["summary"], indent=2, default=str))
    print(f"Wrote Phase 2C scoring validation report: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
