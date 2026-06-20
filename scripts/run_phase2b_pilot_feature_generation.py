#!/usr/bin/env python3
"""Phase 2B pilot feature generation for Swing V2.1 prerequisites.

Reads:
  - angel_data.pilot_phase2a.daily_bars_clean
  - research symbol_master sector metadata

Writes:
  - angel_data.pilot_phase2a.sector_daily
  - angel_data.pilot_phase2a.features_daily
  - feature validation reports under reports/

Does not:
  - Modify production feature tables
  - Generate scores, recommendations, or backtests
"""

from __future__ import annotations

import argparse
import csv
import json
import os
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import numpy as np
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

REPO_ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate pilot-only Swing V2.1 features from cleaned daily bars.")
    parser.add_argument("--research-database-url", default=os.environ.get("DATABASE_URL"))
    parser.add_argument("--angel-database-url", default=os.environ.get("ANGEL_DATABASE_URL"))
    parser.add_argument("--angel-database-name", default="angel_data")
    parser.add_argument("--pilot-schema", default="pilot_phase2a")
    parser.add_argument("--nifty500-csv", help="Optional Nifty 500 CSV used as a sector-map fallback for expanded pilot symbols.")
    parser.add_argument("--output-json", default="reports/phase2b_feature_validation.json")
    parser.add_argument("--coverage-csv", default="reports/phase2b_feature_coverage_by_symbol.csv")
    parser.add_argument("--nulls-csv", default="reports/phase2b_feature_null_rates.csv")
    return parser.parse_args()


def derive_angel_url(research_database_url: str | None, database_name: str) -> str | None:
    if not research_database_url:
        return None
    parts = urlsplit(research_database_url)
    return urlunsplit((parts.scheme, parts.netloc, f"/{database_name}", parts.query, parts.fragment))


def load_sector_map(research_url: str, nifty500_csv: str | None = None) -> dict[str, str | None]:
    engine = create_engine(research_url, future=True)
    with engine.connect() as connection:
        rows = connection.execute(text("SELECT symbol, sector FROM symbol_master")).all()
    sector_map = {str(row[0]).upper(): row[1] for row in rows}
    if nifty500_csv:
        path = REPO_ROOT / nifty500_csv
        with path.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                symbol = str(row.get("Symbol") or row.get("symbol") or "").strip().upper()
                sector = row.get("Industry") or row.get("industry")
                if symbol and sector and not sector_map.get(symbol):
                    sector_map[symbol] = str(sector).strip().upper()
    return sector_map


def load_clean_bars(angel_url: str, schema: str) -> pd.DataFrame:
    engine = create_engine(angel_url, future=True)
    query = f"""
        SELECT symbol, date, open, high, low, close, volume
        FROM {schema}.daily_bars_clean
        ORDER BY symbol, date
    """
    frame = pd.read_sql_query(query, engine)
    frame["date"] = pd.to_datetime(frame["date"]).dt.date
    for column in ["open", "high", "low", "close", "volume"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame


def compute_symbol_features(frame: pd.DataFrame, sector_map: dict[str, str | None]) -> pd.DataFrame:
    rows: list[pd.DataFrame] = []
    for symbol, symbol_frame in frame.groupby("symbol", sort=True):
        df = symbol_frame.sort_values("date").copy()
        close = df["close"].astype(float)
        high = df["high"].astype(float)
        low = df["low"].astype(float)

        result = pd.DataFrame(
            {
                "symbol": symbol,
                "date": df["date"],
                "sector": sector_map.get(symbol),
                "open": df["open"].astype(float),
                "high": high,
                "low": low,
                "close": close,
                "volume": df["volume"].astype("Int64"),
            }
        )
        result["ema_50"] = close.ewm(span=50, adjust=False).mean()
        result["ema_200"] = close.ewm(span=200, adjust=False).mean()
        result["ema200_extension"] = (close - result["ema_200"]) / result["ema_200"].replace(0, np.nan)
        result["prior_20d_return"] = close / close.shift(20) - 1

        prev_close = close.shift(1)
        tr = pd.concat([(high - low), (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
        up_move = high.diff()
        down_move = -low.diff()
        plus_dm = up_move.where((up_move > down_move) & (up_move > 0), 0.0)
        minus_dm = down_move.where((down_move > up_move) & (down_move > 0), 0.0)
        atr_wilder = tr.ewm(alpha=1 / 14, adjust=False).mean()
        plus_di = 100 * plus_dm.ewm(alpha=1 / 14, adjust=False).mean() / atr_wilder.replace(0, np.nan)
        minus_di = 100 * minus_dm.ewm(alpha=1 / 14, adjust=False).mean() / atr_wilder.replace(0, np.nan)
        dx = ((plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)) * 100
        result["adx_14"] = dx.ewm(alpha=1 / 14, adjust=False).mean()
        result["adx_prev"] = result["adx_14"].shift(1)

        result["history_days"] = np.arange(1, len(result) + 1)
        result["has_ema200_warmup"] = result["history_days"] >= 200
        result["has_prior20_warmup"] = result["history_days"] > 20
        result["has_adx_warmup"] = result["history_days"] >= 28
        rows.append(result)
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()


def compute_sector_daily(features: pd.DataFrame) -> pd.DataFrame:
    close_wide = features.pivot(index="date", columns="symbol", values="close").sort_index()
    sector_by_symbol = features.drop_duplicates("symbol").set_index("symbol")["sector"].to_dict()
    rows = []
    for current_date in close_wide.index:
        current_pos = close_wide.index.get_loc(current_date)
        if isinstance(current_pos, slice):
            current_pos = current_pos.start
        for sector in sorted({s for s in sector_by_symbol.values() if s}):
            symbols = [symbol for symbol, symbol_sector in sector_by_symbol.items() if symbol_sector == sector and symbol in close_wide.columns]
            if not symbols:
                continue
            sector_returns = {}
            for period in [21, 63, 126]:
                lookback_pos = current_pos - period
                if lookback_pos < 0:
                    sector_returns[period] = np.nan
                    continue
                current_values = close_wide.loc[current_date, symbols]
                past_values = close_wide.iloc[lookback_pos][symbols]
                returns = current_values / past_values.replace(0, np.nan) - 1
                sector_returns[period] = float(returns.dropna().mean()) if not returns.dropna().empty else np.nan
            rows.append(
                {
                    "date": current_date,
                    "sector": sector,
                    "return_1m": sector_returns[21],
                    "return_3m": sector_returns[63],
                    "return_6m": sector_returns[126],
                    "sector_score": (0 if pd.isna(sector_returns[21]) else sector_returns[21] * 0.20)
                    + (0 if pd.isna(sector_returns[63]) else sector_returns[63] * 0.50)
                    + (0 if pd.isna(sector_returns[126]) else sector_returns[126] * 0.30),
                    "stock_count": len(symbols),
                }
            )
    sector_daily = pd.DataFrame(rows)
    if sector_daily.empty:
        return sector_daily
    sector_daily["rank_3m"] = sector_daily.groupby("date")["return_3m"].rank(ascending=False, method="min", na_option="bottom")
    sector_daily["rank_composite"] = sector_daily.groupby("date")["sector_score"].rank(ascending=False, method="min", na_option="bottom")
    sector_daily["sector_rank"] = sector_daily["rank_composite"]
    return sector_daily


def create_tables(connection, schema: str) -> None:
    connection.execute(
        text(
            f"""
            CREATE TABLE IF NOT EXISTS {schema}.features_daily (
                symbol text NOT NULL,
                date date NOT NULL,
                sector text,
                open numeric,
                high numeric,
                low numeric,
                close numeric,
                volume bigint,
                ema_50 numeric,
                ema_200 numeric,
                ema200_extension numeric,
                prior_20d_return numeric,
                adx_14 numeric,
                adx_prev numeric,
                sector_rank integer,
                sector_rank_3m integer,
                sector_composite_rank integer,
                history_days integer,
                has_ema200_warmup boolean,
                has_prior20_warmup boolean,
                has_adx_warmup boolean,
                generated_at timestamp DEFAULT now(),
                PRIMARY KEY (symbol, date)
            )
            """
        )
    )
    connection.execute(
        text(
            f"""
            CREATE TABLE IF NOT EXISTS {schema}.sector_daily (
                date date NOT NULL,
                sector text NOT NULL,
                return_1m numeric,
                return_3m numeric,
                return_6m numeric,
                sector_score numeric,
                sector_rank integer,
                rank_3m integer,
                rank_composite integer,
                stock_count integer,
                generated_at timestamp DEFAULT now(),
                PRIMARY KEY (date, sector)
            )
            """
        )
    )
    connection.execute(text(f"CREATE INDEX IF NOT EXISTS ix_phase2b_features_date ON {schema}.features_daily (date)"))
    connection.execute(text(f"CREATE INDEX IF NOT EXISTS ix_phase2b_features_symbol_date ON {schema}.features_daily (symbol, date)"))
    connection.execute(text(f"CREATE INDEX IF NOT EXISTS ix_phase2b_sector_date ON {schema}.sector_daily (date)"))


def merge_sector_ranks(features: pd.DataFrame, sector_daily: pd.DataFrame) -> pd.DataFrame:
    merged = features.merge(
        sector_daily[["date", "sector", "sector_rank", "rank_3m", "rank_composite"]],
        on=["date", "sector"],
        how="left",
    )
    merged = merged.rename(columns={"rank_3m": "sector_rank_3m", "rank_composite": "sector_composite_rank"})
    for column in ["sector_rank", "sector_rank_3m", "sector_composite_rank", "history_days"]:
        merged[column] = merged[column].astype("Int64")
    return merged


def write_tables(angel_url: str, schema: str, features: pd.DataFrame, sector_daily: pd.DataFrame) -> None:
    engine = create_engine(angel_url, future=True)
    with engine.begin() as connection:
        create_tables(connection, schema)
        connection.execute(text(f"TRUNCATE TABLE {schema}.features_daily"))
        connection.execute(text(f"TRUNCATE TABLE {schema}.sector_daily"))

    sector_out = sector_daily.copy()
    for column in ["sector_rank", "rank_3m", "rank_composite", "stock_count"]:
        sector_out[column] = sector_out[column].astype("Int64")
    sector_out.to_sql("sector_daily", engine, schema=schema, if_exists="append", index=False, method="multi", chunksize=5000)

    merged = merge_sector_ranks(features, sector_daily)
    columns = [
        "symbol",
        "date",
        "sector",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "ema_50",
        "ema_200",
        "ema200_extension",
        "prior_20d_return",
        "adx_14",
        "adx_prev",
        "sector_rank",
        "sector_rank_3m",
        "sector_composite_rank",
        "history_days",
        "has_ema200_warmup",
        "has_prior20_warmup",
        "has_adx_warmup",
    ]
    merged[columns].to_sql("features_daily", engine, schema=schema, if_exists="append", index=False, method="multi", chunksize=5000)


def build_report(features: pd.DataFrame, sector_daily: pd.DataFrame) -> dict[str, object]:
    features_with_ranks = merge_sector_ranks(features, sector_daily)
    required = ["ema_50", "ema_200", "ema200_extension", "prior_20d_return", "adx_14", "adx_prev"]
    null_rates = []
    for column in required + ["sector_rank_3m"]:
        null_count = int(features_with_ranks[column].isna().sum())
        total = int(len(features_with_ranks))
        null_rates.append({"feature": column, "null_count": null_count, "total_rows": total, "null_pct": round(null_count / total * 100, 4)})

    coverage = []
    for symbol, frame in features_with_ranks.groupby("symbol"):
        coverage.append(
            {
                "symbol": symbol,
                "rows": int(len(frame)),
                "first_date": str(frame["date"].min()),
                "last_date": str(frame["date"].max()),
                "ema200_ready_rows": int(frame["has_ema200_warmup"].sum()),
                "prior20_ready_rows": int(frame["has_prior20_warmup"].sum()),
                "adx_ready_rows": int(frame["has_adx_warmup"].sum()),
                "ema200_null_rows": int(frame["ema_200"].isna().sum()),
                "prior20_null_rows": int(frame["prior_20d_return"].isna().sum()),
                "adx_null_rows": int(frame["adx_14"].isna().sum()),
                "sector_rank_3m_null_rows": int(frame["sector_rank_3m"].isna().sum()),
            }
        )

    return {
        "generated_on": date.today().isoformat(),
        "mode": "phase2b_pilot_feature_generation",
        "production_tables_modified": False,
        "scores_generated": False,
        "recommendations_generated": False,
        "backtests_run": False,
        "summary": {
            "feature_rows": int(len(features)),
            "symbols": int(features["symbol"].nunique()),
            "first_date": str(features["date"].min()),
            "last_date": str(features["date"].max()),
            "sector_rows": int(len(sector_daily)),
            "sectors": int(sector_daily["sector"].nunique()) if not sector_daily.empty else 0,
            "dates": int(features["date"].nunique()),
        },
        "null_rates": null_rates,
        "coverage_by_symbol": coverage,
        "lookback_sufficiency": {
            "rows_with_ema200_warmup": int(features["has_ema200_warmup"].sum()),
            "rows_with_prior20_warmup": int(features["has_prior20_warmup"].sum()),
            "rows_with_adx_warmup": int(features["has_adx_warmup"].sum()),
        },
        "production_definition_comparison": {
            "adx_14": "Matches production Wilder-style EWM ADX formula in app.indicators.compute_features.",
            "ema_50": "Matches production close.ewm(span=50, adjust=False).mean().",
            "ema_200": "Matches production close.ewm(span=200, adjust=False).mean().",
            "prior_20d_return": "Matches scoring helper semantics: close / close.shift(20) - 1 by symbol.",
            "sector_rank_3m": "Pilot computes sector 63-trading-day return rank, matching ScoreComputer use of SectorDaily.rank_3m.",
        },
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


def json_default(value):
    return str(value)


def main() -> int:
    load_dotenv(REPO_ROOT / ".env")
    args = parse_args()
    research_url = args.research_database_url or os.environ.get("DATABASE_URL")
    angel_url = args.angel_database_url or derive_angel_url(research_url, args.angel_database_name)
    if not research_url or not angel_url:
        raise RuntimeError("Research and Angel database URLs are required.")

    sector_map = load_sector_map(research_url, args.nifty500_csv)
    clean_bars = load_clean_bars(angel_url, args.pilot_schema)
    features = compute_symbol_features(clean_bars, sector_map)
    sector_daily = compute_sector_daily(features)
    write_tables(angel_url, args.pilot_schema, features, sector_daily)

    report = build_report(features, sector_daily)
    output_path = REPO_ROOT / args.output_json
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, default=json_default), encoding="utf-8")
    write_csv(REPO_ROOT / args.coverage_csv, report["coverage_by_symbol"])
    write_csv(REPO_ROOT / args.nulls_csv, report["null_rates"])

    print(json.dumps(report["summary"], indent=2, default=json_default))
    print(f"Wrote feature validation report: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
