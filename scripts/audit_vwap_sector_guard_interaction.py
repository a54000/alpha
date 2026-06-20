#!/usr/bin/env python3
"""2x2 interaction audit for VWAP and min-sector-points.

Read-only diagnostic:

- 10:30 entry is fixed ON.
- Expanded ready universe is fixed.
- Compare min_sector_points 0/1 and VWAP filter off/on.

This checks whether the accepted baseline components interact unexpectedly.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import date
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.api.trade_analysis_service import (  # noqa: E402
    STRATEGIES,
    TradeAnalysisRequest,
    TradeAnalysisService,
    financial_year_returns,
)
from scripts.audit_entry_vwap_bisection import reconstruct_with_config  # noqa: E402
from scripts.run_sector_1m3m_rank_experiment import generate_recommendations, load_features_and_sector_returns, score_frame  # noqa: E402


MODEL = "sector_rotation_adx_1m3m"


def load_expanded_ready_symbols(path: Path) -> set[str]:
    frame = pd.read_csv(path)
    if "reason" in frame.columns:
        frame = frame[frame["reason"].astype(str) == "usable"]
    return {str(symbol).strip().upper() for symbol in frame["symbol"].dropna() if str(symbol).strip()}


def prepare_recommendations(service: TradeAnalysisService, schema: str, start_date: date, end_date: date, symbols: set[str], min_sector_points: int) -> list[dict[str, object]]:
    features = load_features_and_sector_returns(service.angel_engine, schema, start_date, end_date, 0.40, 0.60)
    features = features[features["symbol"].astype(str).str.upper().isin(symbols)].copy()
    scores = score_frame(features, "sector_rank_1m3m", "score_1m3m")
    return generate_recommendations(scores, "score_1m3m", 70.0, 20, MODEL, min_sector_points)


def run_case(service: TradeAnalysisService, request: TradeAnalysisRequest, recommendations: list[dict[str, object]], vwap_on: bool) -> dict[str, object]:
    recs = [dict(row) for row in recommendations]
    service._attach_signal_day_vwaps(request, recs)
    symbols = {str(row["symbol"]) for row in recs}
    prices = service._load_prices(request, symbols)
    config = STRATEGIES["SECTOR_ROTATION_ADX_ROLLING10"]
    if not vwap_on:
        config = type(config)(
            config.strategy,
            config.name,
            config.portfolio_size,
            config.max_positions_per_sector,
            config.max_candidate_rank,
            config.holding_period,
            config.required_recommendation_model,
            config.entry_price_field,
            None,
        )
    result = reconstruct_with_config(request, config, recs, prices)
    result["summary"]["financial_year_returns"] = financial_year_returns(result["equity_curve"], result["trades"])
    return result


def pct(value: object) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    return f"{float(value) * 100:.2f}%"


def summarize(period: str, case: str, min_sector_points: int, vwap_on: bool, recs: list[dict[str, object]], result: dict[str, object]) -> dict[str, object]:
    summary = result["summary"]
    return {
        "period": period,
        "case": case,
        "min_sector_points": min_sector_points,
        "vwap_on": vwap_on,
        "recommendation_rows": len(recs),
        "zero_sector_recommendations": sum(1 for row in recs if int(row.get("sector_points") or 0) == 0),
        "ending_value": summary.get("ending_value"),
        "total_return": summary.get("total_return"),
        "cagr": summary.get("cagr"),
        "max_drawdown": summary.get("max_drawdown"),
        "closed_trades": summary.get("total_trades"),
        "win_rate": summary.get("win_rate"),
        "net_pnl": summary.get("net_pnl"),
    }


def main() -> int:
    load_dotenv(REPO_ROOT / ".env")
    output_dir = REPO_ROOT / "reports" / "vwap_sector_guard_interaction"
    output_dir.mkdir(parents=True, exist_ok=True)
    service = TradeAnalysisService(angel_database_url=os.environ.get("ANGEL_DATABASE_URL"), pilot_schema="pilot_phase2a")
    symbols = load_expanded_ready_symbols(REPO_ROOT / "reports/nifty500_expansion_universe_symbols.csv")
    periods = {
        "FY2023-24": (date(2023, 4, 1), date(2024, 3, 31)),
        "FY2024-25": (date(2024, 4, 1), date(2025, 3, 31)),
        "FY2025-26": (date(2025, 4, 1), date(2026, 3, 31)),
    }

    rows: list[dict[str, object]] = []
    payload: dict[str, object] = {"status": "success", "periods": {}}
    for period, (start_date, end_date) in periods.items():
        request = TradeAnalysisRequest(start_date, end_date, "SECTOR_ROTATION_ADX_ROLLING10", 1_000_000, recommendation_model=MODEL)
        payload["periods"][period] = {}
        for min_points in [0, 1]:
            recs = prepare_recommendations(service, "pilot_phase2a", start_date, end_date, symbols, min_points)
            for vwap_on in [False, True]:
                case = f"min{min_points}_{'vwap' if vwap_on else 'no_vwap'}"
                result = run_case(service, request, recs, vwap_on)
                pd.DataFrame(result["trades"]).to_csv(output_dir / f"{period}_{case}_trades.csv", index=False)
                row = summarize(period, case, min_points, vwap_on, recs, result)
                rows.append(row)
                payload["periods"][period][case] = row

    frame = pd.DataFrame(rows)
    frame.to_csv(output_dir / "interaction_summary.csv", index=False)
    (output_dir / "summary.json").write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

    lines = [
        "# VWAP And Sector Guard Interaction Audit",
        "",
        "10:30 entry is fixed on. Expanded ready universe is fixed. This tests whether VWAP and `min_sector_points=1` interact unexpectedly.",
        "",
        "| Period | Case | Return | CAGR | Max DD | Trades | Win Rate |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            f"| {row['period']} | {row['case']} | {pct(row['total_return'])} | {pct(row['cagr'])} | "
            f"{pct(row['max_drawdown'])} | {row['closed_trades']} | {pct(row['win_rate'])} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- `min1_vwap` is the accepted candidate baseline configuration.",
            "- If `min1_vwap` is consistently better than `min1_no_vwap`, VWAP survives after sector guard is fixed on.",
            "- If `min1_vwap` is consistently better than `min0_vwap`, the sector guard survives after VWAP is fixed on.",
            "- This is diagnostic only; no database rows were modified.",
        ]
    )
    (output_dir / "VWAP_SECTOR_GUARD_INTERACTION.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(payload, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
