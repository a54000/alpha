#!/usr/bin/env python3
"""Audit recommendation fallback / effective-end-date behavior.

Read-only diagnostic. Compares the current TradeAnalysisService recommendation
loader against a strict model/date loader for SectorEdge 10 requests.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import date
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import text


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.api.trade_analysis_service import TradeAnalysisRequest, TradeAnalysisService  # noqa: E402


MODEL = "sector_rotation_adx_1m3m"
FALLBACK_MODEL = "swing_v2_1"


def strict_rows(service: TradeAnalysisService, start_date: date, end_date: date, model: str) -> list[dict[str, object]]:
    query = text(
        f"""
        SELECT r.date, r.model, r.rank, r.symbol, r.score, r.sector
        FROM {service.pilot_schema}.recommendations_daily r
        WHERE r.model = :model
          AND r.date BETWEEN :start_date AND :end_date
        ORDER BY r.date ASC, r.rank ASC, r.symbol ASC
        """
    )
    with service.angel_engine.connect() as connection:
        return [dict(row) for row in connection.execute(query, {"model": model, "start_date": start_date, "end_date": end_date}).mappings().all()]


def model_status(service: TradeAnalysisService, model: str) -> dict[str, object]:
    query = text(
        f"""
        SELECT COUNT(*) rows,
               COUNT(DISTINCT date) dates,
               MIN(date) first_date,
               MAX(date) last_date
        FROM {service.pilot_schema}.recommendations_daily
        WHERE model = :model
        """
    )
    with service.angel_engine.connect() as connection:
        row = connection.execute(query, {"model": model}).mappings().one()
    return {
        "model": model,
        "rows": int(row["rows"] or 0),
        "dates": int(row["dates"] or 0),
        "first_date": row["first_date"].isoformat() if row["first_date"] else None,
        "last_date": row["last_date"].isoformat() if row["last_date"] else None,
    }


def key(row: dict[str, object]) -> str:
    return f"{row.get('date')}|{row.get('model')}|{row.get('rank')}|{row.get('symbol')}"


def audit_period(service: TradeAnalysisService, label: str, start_date: date, end_date: date) -> dict[str, object]:
    request = TradeAnalysisRequest(
        start_date=start_date,
        end_date=end_date,
        strategy="SECTOR_ROTATION_ADX_ROLLING10",
        recommendation_model=MODEL,
        initial_capital=1_000_000,
    )
    current = service._load_recommendations(request)
    strict = strict_rows(service, start_date, end_date, MODEL)
    current_keys = {key(row) for row in current}
    strict_keys = {key(row) for row in strict}
    current_models = sorted({str(row.get("model")) for row in current})
    latest_model_date = model_status(service, MODEL)["last_date"]
    return {
        "period": label,
        "start_date": start_date.isoformat(),
        "requested_end_date": end_date.isoformat(),
        "model_latest_available": latest_model_date,
        "current_loader_rows": len(current),
        "strict_loader_rows": len(strict),
        "current_loader_models": current_models,
        "fallback_used": any(str(row.get("model")) != MODEL for row in current),
        "rows_only_current": len(current_keys - strict_keys),
        "rows_only_strict": len(strict_keys - current_keys),
        "effective_end_cap_applied": latest_model_date is not None and end_date.isoformat() > latest_model_date,
        "last_current_date": max([row["date"] for row in current]).isoformat() if current else None,
        "last_strict_date": max([row["date"] for row in strict]).isoformat() if strict else None,
    }


def main() -> int:
    load_dotenv(REPO_ROOT / ".env")
    service = TradeAnalysisService(angel_database_url=os.environ.get("ANGEL_DATABASE_URL"), pilot_schema="pilot_phase2a")
    output_dir = REPO_ROOT / "reports" / "recommendation_loading_audit"
    output_dir.mkdir(parents=True, exist_ok=True)

    periods = [
        ("FY2024-25", date(2024, 4, 1), date(2025, 3, 31)),
        ("FY2025-26", date(2025, 4, 1), date(2026, 3, 31)),
        ("Full Current Report Window", date(2022, 5, 26), date(2026, 6, 18)),
        ("Future End-Date Probe", date(2026, 4, 1), date(2026, 12, 31)),
    ]
    rows = [audit_period(service, label, start, end) for label, start, end in periods]
    status = [model_status(service, MODEL), model_status(service, FALLBACK_MODEL)]

    pd.DataFrame(rows).to_csv(output_dir / "recommendation_loading_audit.csv", index=False)
    payload = {"status": "success", "model_status": status, "periods": rows}
    (output_dir / "summary.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")

    lines = [
        "# Recommendation Loading Logic Audit",
        "",
        "This read-only audit checks whether model fallback or effective-end-date capping changes SectorEdge 10 recommendation inputs.",
        "",
        "## Model Status",
        "",
        "| Model | Rows | Dates | First Date | Last Date |",
        "| --- | ---: | ---: | --- | --- |",
    ]
    for row in status:
        lines.append(f"| {row['model']} | {row['rows']} | {row['dates']} | {row['first_date']} | {row['last_date']} |")
    lines.extend(
        [
            "",
            "## Loader Comparison",
            "",
            "| Period | Current Rows | Strict Rows | Models Used | Fallback Used | End Cap Applied | Only Current | Only Strict | Last Current Date |",
            "| --- | ---: | ---: | --- | --- | --- | ---: | ---: | --- |",
        ]
    )
    for row in rows:
        lines.append(
            f"| {row['period']} | {row['current_loader_rows']} | {row['strict_loader_rows']} | "
            f"{', '.join(row['current_loader_models'])} | {row['fallback_used']} | {row['effective_end_cap_applied']} | "
            f"{row['rows_only_current']} | {row['rows_only_strict']} | {row['last_current_date']} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- If current and strict rows match for normal SectorEdge 10 windows, fallback logic is inert for those reports.",
            "- Effective-end-date capping is only material when the requested end date is later than the latest available recommendation date.",
            "- This audit did not modify recommendations, tables, or strategy logic.",
        ]
    )
    (output_dir / "RECOMMENDATION_LOADING_AUDIT.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
