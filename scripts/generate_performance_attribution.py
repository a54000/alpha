#!/usr/bin/env python3
"""Generate read-only portfolio performance attribution reports.

Reads:
  - paper_positions
  - paper_trades
  - paper_daily_snapshots
  - reports/phase2e_portfolio_metrics.json

Writes:
  - reports/phase6a_performance_attribution.json
  - reports/phase6a_performance_attribution.md

Does not:
  - Change scoring, ranking, factors, strategy rules, or portfolio rules
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import date
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

REPO_ROOT = Path(__file__).resolve().parents[1]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate Swing V2.1 portfolio attribution.")
    parser.add_argument("--database-url", default=os.environ.get("DATABASE_URL"))
    parser.add_argument("--portfolio-id", type=int, default=int(os.environ.get("PAPER_PORTFOLIO_ID", "0") or 0))
    parser.add_argument("--as-of-date", default=date.today().isoformat())
    parser.add_argument("--metrics-json", default="reports/phase2e_portfolio_metrics.json")
    parser.add_argument("--output-json", default="reports/phase6a_performance_attribution.json")
    parser.add_argument("--output-md", default="reports/phase6a_performance_attribution.md")
    return parser.parse_args(argv)


def mappings(engine: Engine | None, query: str, params: dict[str, object] | None = None) -> list[dict[str, object]]:
    if engine is None:
        return []
    try:
        with engine.connect() as connection:
            return [dict(row) for row in connection.execute(text(query), params or {}).mappings().all()]
    except Exception:
        return []


def load_phase2e_metrics(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def position_contribution(engine: Engine | None, portfolio_id: int | None) -> list[dict[str, object]]:
    if not portfolio_id:
        return []
    closed = mappings(
        engine,
        """
        SELECT
            symbol,
            sector,
            MIN(entry_date) AS first_entry_date,
            MAX(exit_date) AS last_exit_date,
            COUNT(*) AS closed_trades,
            COALESCE(SUM(realized_pnl), 0) AS realized_contribution,
            0 AS unrealized_contribution
        FROM paper_trades
        WHERE portfolio_id = :portfolio_id
        GROUP BY symbol, sector
        """,
        {"portfolio_id": portfolio_id},
    )
    open_rows = mappings(
        engine,
        """
        SELECT
            symbol,
            sector,
            MIN(entry_date) AS first_entry_date,
            MAX(planned_exit_date) AS planned_exit_date,
            0 AS closed_trades,
            0 AS realized_contribution,
            COALESCE(SUM(unrealized_pnl), 0) AS unrealized_contribution
        FROM paper_positions
        WHERE portfolio_id = :portfolio_id AND status = 'open'
        GROUP BY symbol, sector
        """,
        {"portfolio_id": portfolio_id},
    )
    by_symbol: dict[tuple[str, str | None], dict[str, object]] = {}
    for row in closed + open_rows:
        key = (str(row.get("symbol")), row.get("sector"))
        bucket = by_symbol.setdefault(
            key,
            {
                "symbol": key[0],
                "sector": key[1],
                "first_entry_date": row.get("first_entry_date"),
                "last_exit_or_planned_date": row.get("last_exit_date") or row.get("planned_exit_date"),
                "closed_trades": 0,
                "realized_contribution": 0.0,
                "unrealized_contribution": 0.0,
            },
        )
        bucket["closed_trades"] = int(bucket["closed_trades"]) + int(row.get("closed_trades") or 0)
        bucket["realized_contribution"] = float(bucket["realized_contribution"]) + float(row.get("realized_contribution") or 0)
        bucket["unrealized_contribution"] = float(bucket["unrealized_contribution"]) + float(row.get("unrealized_contribution") or 0)
        if row.get("first_entry_date") and (bucket.get("first_entry_date") is None or str(row["first_entry_date"]) < str(bucket["first_entry_date"])):
            bucket["first_entry_date"] = row["first_entry_date"]
        end_value = row.get("last_exit_date") or row.get("planned_exit_date")
        if end_value and (bucket.get("last_exit_or_planned_date") is None or str(end_value) > str(bucket["last_exit_or_planned_date"])):
            bucket["last_exit_or_planned_date"] = end_value
    rows = []
    for item in by_symbol.values():
        item["total_contribution"] = float(item["realized_contribution"]) + float(item["unrealized_contribution"])
        item["holding_period"] = f"{item.get('first_entry_date') or 'n/a'} to {item.get('last_exit_or_planned_date') or 'open'}"
        rows.append(item)
    return sorted(rows, key=lambda row: float(row["total_contribution"]), reverse=True)


def sector_attribution(engine: Engine | None, portfolio_id: int | None, positions: list[dict[str, object]]) -> list[dict[str, object]]:
    if not portfolio_id:
        return []
    exposure_rows = mappings(
        engine,
        """
        SELECT sector, COALESCE(SUM(market_value), 0) AS exposure
        FROM paper_positions
        WHERE portfolio_id = :portfolio_id AND status = 'open'
        GROUP BY sector
        """,
        {"portfolio_id": portfolio_id},
    )
    contribution_by_sector: dict[str, float] = {}
    for row in positions:
        sector = str(row.get("sector") or "Unknown")
        contribution_by_sector[sector] = contribution_by_sector.get(sector, 0.0) + float(row.get("total_contribution") or 0)
    total_exposure = sum(float(row.get("exposure") or 0) for row in exposure_rows)
    sectors = {str(row.get("sector") or "Unknown") for row in exposure_rows} | set(contribution_by_sector)
    output = []
    for sector in sorted(sectors):
        exposure = sum(float(row.get("exposure") or 0) for row in exposure_rows if str(row.get("sector") or "Unknown") == sector)
        output.append(
            {
                "sector": sector,
                "sector_exposure": exposure,
                "sector_return_contribution": contribution_by_sector.get(sector, 0.0),
                "concentration_percentage": exposure / total_exposure if total_exposure else 0.0,
            }
        )
    return sorted(output, key=lambda row: float(row["sector_return_contribution"]), reverse=True)


def strategy_attribution(metrics: dict[str, object]) -> list[dict[str, object]]:
    variants = metrics.get("variants", {}) if isinstance(metrics, dict) else {}
    rows = []
    for variant in ["top5_weekly", "top10_weekly"]:
        payload = variants.get(variant, {}) if isinstance(variants, dict) else {}
        metric = payload.get("metrics", {}) if isinstance(payload, dict) else {}
        rows.append(
            {
                "strategy": variant,
                "return_contribution": metric.get("total_return"),
                "drawdown_contribution": metric.get("max_drawdown"),
                "turnover_contribution": metric.get("turnover"),
                "closed_trades": metric.get("closed_trades") or payload.get("closed_trade_count"),
                "final_equity": metric.get("final_equity"),
            }
        )
    return rows


def build_report(engine: Engine | None, portfolio_id: int | None, as_of_date: date, metrics: dict[str, object]) -> dict[str, object]:
    positions = position_contribution(engine, portfolio_id)
    sectors = sector_attribution(engine, portfolio_id, positions)
    strategies = strategy_attribution(metrics)
    return {
        "generated_on": date.today().isoformat(),
        "mode": "phase6a_performance_attribution",
        "as_of_date": as_of_date.isoformat(),
        "portfolio_id": portfolio_id,
        "constraints": {
            "scoring_changed": False,
            "ranking_changed": False,
            "factors_added": False,
            "portfolio_rules_changed": False,
            "parameters_optimized": False,
        },
        "summary": {
            "positions": len(positions),
            "sectors": len(sectors),
            "strategies_compared": len(strategies),
            "total_realized_contribution": sum(float(row.get("realized_contribution") or 0) for row in positions),
            "total_unrealized_contribution": sum(float(row.get("unrealized_contribution") or 0) for row in positions),
        },
        "position_contribution": positions,
        "sector_attribution": sectors,
        "strategy_attribution": strategies,
    }


def format_money(value: object) -> str:
    return "n/a" if value is None else f"{float(value):,.2f}"


def format_pct(value: object) -> str:
    return "n/a" if value is None else f"{float(value) * 100:.2f}%"


def render_markdown(report: dict[str, object]) -> str:
    lines = [
        f"# Phase 6A Performance Attribution - {report['as_of_date']}",
        "",
        "## Summary",
        "",
        f"- Positions: {report['summary']['positions']}",
        f"- Sectors: {report['summary']['sectors']}",
        f"- Total realized contribution: {format_money(report['summary']['total_realized_contribution'])}",
        f"- Total unrealized contribution: {format_money(report['summary']['total_unrealized_contribution'])}",
        "",
        "## Position Contribution",
        "",
        "| Symbol | Holding period | Realized | Unrealized | Total |",
        "|---|---|---:|---:|---:|",
    ]
    for row in report["position_contribution"]:
        lines.append(
            f"| {row['symbol']} | {row['holding_period']} | {format_money(row['realized_contribution'])} | "
            f"{format_money(row['unrealized_contribution'])} | {format_money(row['total_contribution'])} |"
        )
    lines.extend(["", "## Sector Attribution", "", "| Sector | Exposure | Return contribution | Concentration |", "|---|---:|---:|---:|"])
    for row in report["sector_attribution"]:
        lines.append(
            f"| {row['sector']} | {format_money(row['sector_exposure'])} | "
            f"{format_money(row['sector_return_contribution'])} | {format_pct(row['concentration_percentage'])} |"
        )
    lines.extend(["", "## Strategy Attribution", "", "| Strategy | Return | Drawdown | Turnover | Closed trades |", "|---|---:|---:|---:|---:|"])
    for row in report["strategy_attribution"]:
        lines.append(
            f"| {row['strategy']} | {format_pct(row['return_contribution'])} | {format_pct(row['drawdown_contribution'])} | "
            f"{format_pct(row['turnover_contribution'])} | {row['closed_trades'] or 'n/a'} |"
        )
    lines.extend(["", "## Constraints", "", "- Scoring changed: no", "- Ranking changed: no", "- Factors added: no", "- Portfolio rules changed: no", "- Parameters optimized: no", ""])
    return "\n".join(lines)


def main() -> int:
    load_dotenv(REPO_ROOT / ".env")
    args = parse_args()
    engine = create_engine(args.database_url, future=True) if args.database_url else None
    metrics = load_phase2e_metrics(REPO_ROOT / args.metrics_json)
    report = build_report(engine, args.portfolio_id or None, date.fromisoformat(args.as_of_date), metrics)
    json_path = REPO_ROOT / args.output_json
    md_path = REPO_ROOT / args.output_md
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")
    print(json.dumps(report["summary"], indent=2, default=str))
    print(f"Wrote attribution JSON: {json_path}")
    print(f"Wrote attribution Markdown: {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
