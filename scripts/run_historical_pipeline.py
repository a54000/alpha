#!/usr/bin/env python3
"""One-shot historical pipeline load for PostgreSQL."""

from __future__ import annotations

import csv
import json
import sys
from datetime import date, timedelta
from pathlib import Path

from sqlalchemy import func, select, text

from app.indicators.compute_features import FeatureComputer
from app.ingestion.price_loader import PriceBar, PriceLoader, default_yfinance_fetcher
from app.ingestion.symbol_loader import ConstituentRecord, SymbolLoader
from app.recommendations.generate_recommendations import RecommendationGenerator
from app.scoring.compute_scores import ScoreComputer
from app.sectors.compute_sector_strength import SectorStrengthComputer
from app.utils.config import load_config
from db.models import (
    DailyScores,
    FeaturesDaily,
    ModelVersion,
    PricesDaily,
    RecommendationHistory,
    SectorDaily,
    SymbolMaster,
)
from db.session import build_session_factory


def load_constituents(csv_path: Path) -> list[ConstituentRecord]:
    records: list[ConstituentRecord] = []
    with csv_path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            symbol = (row.get("Symbol") or "").strip()
            if not symbol:
                continue
            records.append(
                ConstituentRecord(
                    symbol=symbol,
                    company_name=(row.get("Company Name") or "").strip() or None,
                    sector=(row.get("Industry") or "").strip() or None,
                )
            )
    return records


def yfinance_nse_fetcher(symbol: str, start_date: date, end_date: date):
    ticker = symbol if symbol.startswith("^") else f"{symbol}.NS"
    for bar in default_yfinance_fetcher(ticker, start_date, end_date):
        yield PriceBar(
            symbol=symbol,
            date=bar.date,
            open=bar.open,
            high=bar.high,
            low=bar.low,
            close=bar.close,
            volume=bar.volume,
        )


def load_prices_with_progress(session_factory, start_date: date, end_date: date, symbols: list[str]) -> tuple[int, list[str]]:
    loader = PriceLoader(session_factory, yfinance_nse_fetcher)
    rows_loaded = 0
    failures: list[str] = []
    total = len(symbols)
    for index, symbol in enumerate(symbols, start=1):
        result = loader.load(start_date, end_date, [symbol])
        rows_loaded += result.rows_loaded
        failures.extend(result.failures)
        if index % 25 == 0 or index == total:
            print(f"  prices progress: {index}/{total} symbols, rows_loaded={rows_loaded}, failures={len(failures)}")
    return rows_loaded, failures


def ensure_model_version(session_factory) -> None:
    with session_factory() as session:
        existing = session.execute(select(ModelVersion.version_id).limit(1)).scalar_one_or_none()
        if existing is not None:
            return
        session.add(
            ModelVersion(
                version_tag="v1.0",
                model="swing",
                weights_json={},
                is_active=True,
                notes="Initial pipeline seed",
            )
        )
        session.commit()


def table_stats(session_factory, table_name: str, *, date_column: str | None = "date") -> dict[str, object]:
    with session_factory() as session:
        count = session.execute(text(f"SELECT COUNT(*) FROM {table_name}")).scalar_one()
        stats: dict[str, object] = {"rows": int(count)}
        if date_column:
            min_date = session.execute(text(f"SELECT MIN({date_column}) FROM {table_name}")).scalar_one()
            max_date = session.execute(text(f"SELECT MAX({date_column}) FROM {table_name}")).scalar_one()
            stats["min_date"] = str(min_date) if min_date else None
            stats["max_date"] = str(max_date) if max_date else None
        return stats


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    config = load_config(repo_root / "configs" / "config.yaml")
    csv_path = repo_root / "data" / "ind_nifty500list.csv"
    if not csv_path.exists():
        print(f"Missing universe file: {csv_path}", file=sys.stderr)
        return 1

    end_date = date.today()
    start_date = end_date - timedelta(days=365 * 2)
    snapshot_date = end_date
    benchmark = config.raw.get("data", {}).get("nifty500_symbol", "^CRSLDX")

    session_factory = build_session_factory()
    failures: dict[str, list[str]] = {}

    print("=== Step 1: symbol_master ===")
    constituents = load_constituents(csv_path)
    symbol_result = SymbolLoader(session_factory).load(snapshot_date, constituents)
    print(symbol_result)
    failures["symbol_loader"] = symbol_result.failures

    symbols = [record.symbol for record in constituents]
    price_symbols = symbols + [benchmark]

    if benchmark not in symbols:
        with session_factory() as session:
            existing = session.execute(
                select(SymbolMaster.symbol).where(SymbolMaster.symbol == benchmark)
            ).scalar_one_or_none()
            if existing is None:
                session.add(
                    SymbolMaster(
                        symbol=benchmark,
                        company_name="NIFTY500 Total Return Index",
                        sector="INDEX",
                        nse500=False,
                    )
                )
                session.commit()
                print(f"  registered benchmark symbol: {benchmark}")

    print(f"=== Step 2: prices_daily ({start_date} to {end_date}) ===")
    price_rows, price_failures = load_prices_with_progress(session_factory, start_date, end_date, price_symbols)
    print({"rows_loaded": price_rows, "failures": len(price_failures)})
    failures["price_loader"] = price_failures

    print("=== Step 3: features_daily ===")
    feature_result = FeatureComputer(session_factory).generate()
    print(feature_result)
    failures["features"] = feature_result.failures

    print("=== Step 4: sector_daily ===")
    sector_result = SectorStrengthComputer(session_factory).generate()
    print(sector_result)
    failures["sectors"] = sector_result.failures

    ensure_model_version(session_factory)

    print("=== Step 5: daily_scores ===")
    score_result = ScoreComputer(session_factory).generate()
    print(score_result)
    failures["scores"] = score_result.failures

    print("=== Step 6: recommendation_history ===")
    rec_result = RecommendationGenerator(session_factory).generate()
    print(rec_result)
    failures["recommendations"] = rec_result.failures

    print("\n=== TABLE SUMMARY ===")
    tables = [
        "symbol_master",
        "prices_daily",
        "features_daily",
        "sector_daily",
        "daily_scores",
        "recommendation_history",
    ]
    summary = {
        "symbol_master": table_stats(session_factory, "symbol_master", date_column=None),
        **{table: table_stats(session_factory, table) for table in tables if table != "symbol_master"},
    }
    print(json.dumps(summary, indent=2))

    print("\n=== FAILURES ===")
    print(json.dumps({k: v[:20] if len(v) > 20 else v for k, v in failures.items()}, indent=2))
    total_failures = sum(len(v) for v in failures.values())
    print(f"total_failures={total_failures}")
    return 0 if total_failures == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
