#!/usr/bin/env python3
"""Generate a daily monitoring report for frozen Swing V2.1 paper trading.

Reads:
  - Phase 3F JSON reports
  - Angel/pilot data tables when available
  - paper trading tables

Writes:
  - reports/daily_paper_report_<date>.md

Does not:
  - Modify strategy, scoring, recommendations, factors, or portfolio rules
  - Connect broker APIs or place trades
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from dotenv import load_dotenv
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

DEFAULT_DRAWDOWN_ALERT = -0.10
DEFAULT_CONCENTRATION_ALERT = 0.40
DEFAULT_ABNORMAL_RECOMMENDATION_LOW = 3
DEFAULT_ABNORMAL_RECOMMENDATION_HIGH = 20


@dataclass(frozen=True)
class Alert:
    severity: str
    category: str
    message: str


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate daily paper trading monitoring report.")
    parser.add_argument("--report-date", default=date.today().isoformat())
    parser.add_argument("--research-database-url", default=os.environ.get("DATABASE_URL"))
    parser.add_argument("--angel-database-url", default=os.environ.get("ANGEL_DATABASE_URL"))
    parser.add_argument("--angel-database-name", default="angel_data")
    parser.add_argument("--pilot-schema", default="pilot_phase2a")
    parser.add_argument("--portfolio-id", type=int, default=int(os.environ.get("PAPER_PORTFOLIO_ID", "0") or 0))
    parser.add_argument("--model", default="swing_v2_1")
    parser.add_argument("--output-md")
    parser.add_argument("--drawdown-alert", type=float, default=DEFAULT_DRAWDOWN_ALERT)
    parser.add_argument("--concentration-alert", type=float, default=DEFAULT_CONCENTRATION_ALERT)
    parser.add_argument("--recommendation-low-alert", type=int, default=DEFAULT_ABNORMAL_RECOMMENDATION_LOW)
    parser.add_argument("--recommendation-high-alert", type=int, default=DEFAULT_ABNORMAL_RECOMMENDATION_HIGH)
    return parser.parse_args(argv)


def derive_angel_url(research_database_url: str | None, database_name: str) -> str | None:
    if not research_database_url:
        return None
    parts = urlsplit(research_database_url)
    return urlunsplit((parts.scheme, parts.netloc, f"/{database_name}", parts.query, parts.fragment))


def make_engine(database_url: str | None) -> Engine | None:
    if not database_url:
        return None
    return create_engine(database_url, future=True)


def table_exists(engine: Engine | None, table: str, schema: str | None = None) -> bool:
    if engine is None:
        return False
    try:
        return inspect(engine).has_table(table, schema=schema)
    except Exception:
        return False


def load_json(path: Path) -> dict[str, object] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def scalar(engine: Engine | None, query: str, params: dict[str, object] | None = None):
    if engine is None:
        return None
    try:
        with engine.connect() as connection:
            return connection.execute(text(query), params or {}).scalar_one_or_none()
    except Exception:
        return None


def mappings(engine: Engine | None, query: str, params: dict[str, object] | None = None) -> list[dict[str, object]]:
    if engine is None:
        return []
    try:
        with engine.connect() as connection:
            return [dict(row) for row in connection.execute(text(query), params or {}).mappings().all()]
    except Exception:
        return []


def latest_pipeline_status(report_date: date) -> dict[str, object]:
    cycle_report = load_json(REPO_ROOT / "reports" / "phase3f_daily_cycle.json")
    if cycle_report is None:
        cycle_report = load_json(REPO_ROOT / "reports" / "phase3f_daily_cycle_dry_run.json")
    sync_report = load_json(REPO_ROOT / "reports" / "phase3f_angel_daily_sync.json")
    feature_report = load_json(REPO_ROOT / "reports" / "phase3f_feature_validation.json")
    recommendation_report = load_json(REPO_ROOT / "reports" / "phase3f_recommendation_validation.json")
    return {
        "report_date": report_date.isoformat(),
        "cycle_report": cycle_report,
        "sync_report": sync_report,
        "feature_report": feature_report,
        "recommendation_report": recommendation_report,
    }


def latest_candle_from_sync_report() -> datetime | None:
    sync_report = load_json(REPO_ROOT / "reports" / "phase3f_angel_daily_sync.json")
    latest: datetime | None = None
    for row in sync_report.get("results", []) if isinstance(sync_report, dict) else []:
        if not isinstance(row, dict):
            continue
        value = row.get("latest_before")
        if not value:
            continue
        try:
            parsed = datetime.fromisoformat(str(value))
        except ValueError:
            continue
        if latest is None or parsed > latest:
            latest = parsed
    return latest


def data_freshness(angel_engine: Engine | None, schema: str, report_date: date) -> dict[str, object]:
    latest_candle = latest_candle_from_sync_report() or (
        scalar(angel_engine, "SELECT datetime FROM ohlcv_15min ORDER BY datetime DESC LIMIT 1")
        if table_exists(angel_engine, "ohlcv_15min")
        else None
    )
    latest_daily = None
    latest_clean = None
    latest_features = None
    latest_recommendations = None
    if table_exists(angel_engine, "daily_bars", schema=schema):
        latest_daily = scalar(angel_engine, f"SELECT MAX(date) FROM {schema}.daily_bars")
    if table_exists(angel_engine, "daily_bars_clean", schema=schema):
        latest_clean = scalar(angel_engine, f"SELECT MAX(date) FROM {schema}.daily_bars_clean")
    if table_exists(angel_engine, "features_daily", schema=schema):
        latest_features = scalar(angel_engine, f"SELECT MAX(date) FROM {schema}.features_daily")
    if table_exists(angel_engine, "recommendations_daily", schema=schema):
        latest_recommendations = scalar(angel_engine, f"SELECT MAX(date) FROM {schema}.recommendations_daily")

    latest_date = None
    if latest_candle is not None:
        latest_date = latest_candle.date() if hasattr(latest_candle, "date") else date.fromisoformat(str(latest_candle)[:10])
    stale_days = (report_date - latest_date).days if latest_date else None
    return {
        "latest_candle_at": latest_candle,
        "latest_candle_date": latest_date,
        "latest_daily_bar_date": latest_daily,
        "latest_clean_bar_date": latest_clean,
        "latest_feature_date": latest_features,
        "latest_recommendation_date": latest_recommendations,
        "stale_days": stale_days,
    }


def latest_sync_status(angel_engine: Engine | None) -> dict[str, object]:
    if not table_exists(angel_engine, "fetch_progress"):
        return {"available": False}
    rows = mappings(
        angel_engine,
        """
        SELECT
            COUNT(*) AS symbols,
            COUNT(*) FILTER (WHERE status = 'success') AS success_symbols,
            COUNT(*) FILTER (WHERE status = 'failed') AS failed_symbols,
            MAX(last_success_at) AS last_success_at,
            MAX(latest_candle_at) AS latest_candle_at
        FROM fetch_progress
        """,
    )
    return {"available": True, **(rows[0] if rows else {})}


def latest_quality(angel_engine: Engine | None, schema: str, report_date: date) -> dict[str, object]:
    if not table_exists(angel_engine, "daily_bars_clean", schema=schema):
        return {"available": False}
    rows = mappings(
        angel_engine,
        f"""
        SELECT
            COUNT(*) AS clean_rows,
            COUNT(DISTINCT symbol) AS symbols,
            COUNT(*) FILTER (
                WHERE open IS NULL OR high IS NULL OR low IS NULL OR close IS NULL
                   OR high < low OR high < open OR high < close OR low > open OR low > close
                   OR open <= 0 OR high <= 0 OR low <= 0 OR close <= 0
            ) AS invalid_ohlc_rows,
            COUNT(*) FILTER (WHERE COALESCE(volume, 0) = 0) AS zero_volume_rows
        FROM {schema}.daily_bars_clean
        WHERE date = :report_date
        """,
        {"report_date": report_date},
    )
    return {"available": True, **(rows[0] if rows else {})}


def latest_recommendations(angel_engine: Engine | None, schema: str, report_date: date, model: str) -> dict[str, object]:
    if not table_exists(angel_engine, "recommendations_daily", schema=schema):
        return {"available": False, "rows": []}
    rows = mappings(
        angel_engine,
        f"""
        SELECT symbol, rank, score, sector
        FROM {schema}.recommendations_daily
        WHERE date = :report_date AND model = :model
        ORDER BY rank ASC, symbol ASC
        """,
        {"report_date": report_date, "model": model},
    )
    scores = [float(row["score"]) for row in rows if row.get("score") is not None]
    return {
        "available": True,
        "rows": rows,
        "recommendation_count": len(rows),
        "average_score": sum(scores) / len(scores) if scores else None,
        "min_score": min(scores) if scores else None,
        "max_score": max(scores) if scores else None,
    }


def portfolio_status(research_engine: Engine | None, portfolio_id: int | None, report_date: date) -> dict[str, object]:
    if not portfolio_id or not table_exists(research_engine, "paper_portfolios"):
        return {"available": False}
    portfolio_rows = mappings(
        research_engine,
        """
        SELECT portfolio_id, name, strategy, portfolio_size, initial_capital, cash, current_nav, benchmark_symbol, status
        FROM paper_portfolios
        WHERE portfolio_id = :portfolio_id
        """,
        {"portfolio_id": portfolio_id},
    )
    if not portfolio_rows:
        return {"available": False}
    snapshot_rows = mappings(
        research_engine,
        """
        SELECT date, cash, market_value, nav, realized_pnl, unrealized_pnl, turnover,
               benchmark_close, benchmark_return, open_positions
        FROM paper_daily_snapshots
        WHERE portfolio_id = :portfolio_id AND date <= :report_date
        ORDER BY date DESC
        LIMIT 1
        """,
        {"portfolio_id": portfolio_id, "report_date": report_date},
    )
    open_positions = mappings(
        research_engine,
        """
        SELECT symbol, sector, entry_date, entry_price, quantity, capital_allocated,
               current_price, market_value, unrealized_pnl, planned_exit_date
        FROM paper_positions
        WHERE portfolio_id = :portfolio_id AND status = 'open'
        ORDER BY market_value DESC NULLS LAST, symbol ASC
        """,
        {"portfolio_id": portfolio_id},
    )
    trades_today = mappings(
        research_engine,
        """
        SELECT COALESCE(SUM(turnover), 0) AS turnover, COUNT(*) AS trades
        FROM paper_trades
        WHERE portfolio_id = :portfolio_id AND exit_date = :report_date
        """,
        {"portfolio_id": portfolio_id, "report_date": report_date},
    )
    nav_history = mappings(
        research_engine,
        """
        SELECT date, nav
        FROM paper_daily_snapshots
        WHERE portfolio_id = :portfolio_id AND date <= :report_date
        ORDER BY date ASC
        """,
        {"portfolio_id": portfolio_id, "report_date": report_date},
    )
    return {
        "available": True,
        "portfolio": portfolio_rows[0],
        "snapshot": snapshot_rows[0] if snapshot_rows else None,
        "open_positions": open_positions,
        "trades_today": trades_today[0] if trades_today else {"turnover": 0, "trades": 0},
        "nav_history": nav_history,
    }


def compute_drawdown(nav_history: list[dict[str, object]]) -> float | None:
    if not nav_history:
        return None
    peak = None
    current_dd = None
    for row in nav_history:
        nav = float(row["nav"])
        peak = nav if peak is None else max(peak, nav)
        current_dd = (nav / peak) - 1 if peak else 0.0
    return current_dd


def sector_concentration(open_positions: list[dict[str, object]]) -> tuple[dict[str, float], float]:
    totals: dict[str, float] = {}
    total_value = 0.0
    for position in open_positions:
        sector = str(position.get("sector") or "Unknown")
        value = float(position.get("market_value") or 0)
        totals[sector] = totals.get(sector, 0.0) + value
        total_value += value
    weights = {sector: value / total_value for sector, value in totals.items()} if total_value else {}
    max_weight = max(weights.values()) if weights else 0.0
    return weights, max_weight


def compute_risk(portfolio: dict[str, object]) -> dict[str, object]:
    snapshot = portfolio.get("snapshot") if portfolio.get("available") else None
    open_positions = portfolio.get("open_positions", []) if portfolio.get("available") else []
    nav = float(snapshot.get("nav")) if snapshot and snapshot.get("nav") is not None else None
    market_value = float(snapshot.get("market_value")) if snapshot and snapshot.get("market_value") is not None else 0.0
    turnover = float((portfolio.get("trades_today") or {}).get("turnover") or 0.0)
    sector_weights, max_sector_weight = sector_concentration(open_positions)
    return {
        "current_drawdown": compute_drawdown(portfolio.get("nav_history", [])) if portfolio.get("available") else None,
        "exposure": market_value / nav if nav else None,
        "sector_weights": sector_weights,
        "max_sector_weight": max_sector_weight,
        "turnover": turnover,
        "turnover_pct_nav": turnover / nav if nav else None,
    }


def build_alerts(
    freshness: dict[str, object],
    quality: dict[str, object],
    recommendations: dict[str, object],
    risk: dict[str, object],
    drawdown_alert: float,
    concentration_alert: float,
    recommendation_low_alert: int,
    recommendation_high_alert: int,
) -> list[Alert]:
    alerts: list[Alert] = []
    stale_days = freshness.get("stale_days")
    if stale_days is None:
        alerts.append(Alert("critical", "missing_data", "No latest Angel candle timestamp was available."))
    elif int(stale_days) > 1:
        alerts.append(Alert("high", "missing_data", f"Latest Angel candle is {stale_days} calendar days stale."))

    if quality.get("available") and int(quality.get("invalid_ohlc_rows") or 0) > 0:
        alerts.append(Alert("high", "invalid_ohlc", f"Invalid OHLC rows on report date: {quality.get('invalid_ohlc_rows')}."))
    if quality.get("available") and int(quality.get("zero_volume_rows") or 0) > 0:
        alerts.append(Alert("medium", "zero_volume", f"Zero-volume clean daily bars on report date: {quality.get('zero_volume_rows')}."))

    rec_count = int(recommendations.get("recommendation_count") or 0)
    if recommendations.get("available") and rec_count == 0:
        alerts.append(Alert("critical", "zero_recommendations", "No Swing V2.1 recommendations were generated for the report date."))
    elif recommendations.get("available") and rec_count < recommendation_low_alert:
        alerts.append(Alert("medium", "abnormal_recommendation_count", f"Recommendation count is unusually low: {rec_count}."))
    elif recommendations.get("available") and rec_count > recommendation_high_alert:
        alerts.append(Alert("medium", "abnormal_recommendation_count", f"Recommendation count is unusually high: {rec_count}."))

    drawdown = risk.get("current_drawdown")
    if drawdown is not None and float(drawdown) <= drawdown_alert:
        alerts.append(Alert("high", "drawdown_threshold", f"Current drawdown {format_pct(float(drawdown))} breached threshold {format_pct(drawdown_alert)}."))

    max_sector_weight = float(risk.get("max_sector_weight") or 0.0)
    if max_sector_weight >= concentration_alert:
        alerts.append(Alert("medium", "excessive_concentration", f"Max sector concentration is {format_pct(max_sector_weight)}."))
    return alerts


def format_money(value: object) -> str:
    if value is None:
        return "n/a"
    return f"{float(value):,.2f}"


def format_pct(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value * 100:.2f}%"


def md_table(headers: list[str], rows: list[list[object]]) -> str:
    if not rows:
        return "_No rows._"
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    for row in rows:
        lines.append("| " + " | ".join(str(value) for value in row) + " |")
    return "\n".join(lines)


def render_report(
    report_date: date,
    pipeline: dict[str, object],
    sync: dict[str, object],
    freshness: dict[str, object],
    quality: dict[str, object],
    portfolio: dict[str, object],
    risk: dict[str, object],
    recommendations: dict[str, object],
    alerts: list[Alert],
) -> str:
    cycle = pipeline.get("cycle_report") or {}
    feature_report = pipeline.get("feature_report") or {}
    recommendation_report = pipeline.get("recommendation_report") or {}
    snapshot = portfolio.get("snapshot") if portfolio.get("available") else None
    portfolio_row = portfolio.get("portfolio") if portfolio.get("available") else None
    positions = portfolio.get("open_positions", []) if portfolio.get("available") else []
    rec_rows = recommendations.get("rows", [])

    lines = [
        f"# Daily Paper Trading Report - {report_date.isoformat()}",
        "",
        "## Alerts",
    ]
    if alerts:
        lines.extend(f"- **{alert.severity.upper()}** `{alert.category}`: {alert.message}" for alert in alerts)
    else:
        lines.append("- No alerts.")

    lines.extend(
        [
            "",
            "## Pipeline Status",
            "",
            md_table(
                ["Check", "Value"],
                [
                    ["Cycle status", (cycle.get("summary") or {}).get("status", "n/a")],
                    ["Data freshness", freshness.get("latest_candle_at") or "n/a"],
                    ["Latest trading date", freshness.get("latest_candle_date") or "n/a"],
                    ["Last successful sync", sync.get("last_success_at") or "n/a"],
                    ["Feature generation status", (feature_report.get("summary") or {}).get("last_date", freshness.get("latest_feature_date") or "n/a")],
                    ["Recommendation generation status", (recommendation_report.get("summary") or {}).get("last_recommendation_date", freshness.get("latest_recommendation_date") or "n/a")],
                    ["Invalid OHLC rows", quality.get("invalid_ohlc_rows", "n/a")],
                    ["Zero-volume rows", quality.get("zero_volume_rows", "n/a")],
                ],
            ),
            "",
            "## Portfolio Status",
            "",
        ]
    )
    if snapshot and portfolio_row:
        lines.append(
            md_table(
                ["Metric", "Value"],
                [
                    ["Portfolio", f"{portfolio_row.get('name')} ({portfolio_row.get('strategy')})"],
                    ["NAV", format_money(snapshot.get("nav"))],
                    ["Cash", format_money(snapshot.get("cash"))],
                    ["Invested amount", format_money(snapshot.get("market_value"))],
                    ["Open positions", snapshot.get("open_positions")],
                    ["Realized PnL", format_money(snapshot.get("realized_pnl"))],
                    ["Unrealized PnL", format_money(snapshot.get("unrealized_pnl"))],
                ],
            )
        )
    else:
        lines.append("_No paper portfolio snapshot available._")

    lines.extend(
        [
            "",
            "## Risk Metrics",
            "",
            md_table(
                ["Metric", "Value"],
                [
                    ["Current drawdown", format_pct(risk.get("current_drawdown"))],
                    ["Exposure", format_pct(risk.get("exposure"))],
                    ["Max sector concentration", format_pct(risk.get("max_sector_weight"))],
                    ["Turnover", format_money(risk.get("turnover"))],
                    ["Turnover / NAV", format_pct(risk.get("turnover_pct_nav"))],
                ],
            ),
            "",
            "### Sector Concentration",
            "",
            md_table(
                ["Sector", "Weight"],
                [[sector, format_pct(weight)] for sector, weight in sorted((risk.get("sector_weights") or {}).items(), key=lambda item: item[1], reverse=True)],
            ),
            "",
            "## Strategy Health",
            "",
            md_table(
                ["Metric", "Value"],
                [
                    ["Recommendation count", recommendations.get("recommendation_count", "n/a")],
                    ["Average score", f"{recommendations.get('average_score'):.2f}" if recommendations.get("average_score") is not None else "n/a"],
                    ["Minimum score", f"{recommendations.get('min_score'):.2f}" if recommendations.get("min_score") is not None else "n/a"],
                    ["Maximum score", f"{recommendations.get('max_score'):.2f}" if recommendations.get("max_score") is not None else "n/a"],
                ],
            ),
            "",
            "### Top Ranked Stocks",
            "",
            md_table(
                ["Rank", "Symbol", "Score", "Sector"],
                [[row.get("rank"), row.get("symbol"), row.get("score"), row.get("sector") or ""] for row in rec_rows[:10]],
            ),
            "",
            "## Open Positions",
            "",
            md_table(
                ["Symbol", "Sector", "Entry", "Market Value", "Unrealized PnL", "Planned Exit"],
                [
                    [
                        row.get("symbol"),
                        row.get("sector") or "",
                        row.get("entry_date"),
                        format_money(row.get("market_value")),
                        format_money(row.get("unrealized_pnl")),
                        row.get("planned_exit_date") or "",
                    ]
                    for row in positions
                ],
            ),
            "",
            "## Benchmark Comparison",
            "",
        ]
    )
    if snapshot:
        lines.append(
            md_table(
                ["Metric", "Value"],
                [
                    ["Benchmark close", format_money(snapshot.get("benchmark_close"))],
                    ["Benchmark daily return", format_pct(float(snapshot.get("benchmark_return"))) if snapshot.get("benchmark_return") is not None else "n/a"],
                ],
            )
        )
    else:
        lines.append("_No benchmark snapshot available._")

    lines.extend(
        [
            "",
            "## Constraints",
            "",
            "- Strategy changed: no",
            "- Scoring changed: no",
            "- Factors added: no",
            "- Broker APIs connected: no",
            "- Trades placed: no",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    load_dotenv(REPO_ROOT / ".env")
    args = parse_args()
    report_date = date.fromisoformat(args.report_date)
    research_url = args.research_database_url or os.environ.get("DATABASE_URL")
    angel_url = args.angel_database_url or derive_angel_url(research_url, args.angel_database_name)
    research_engine = make_engine(research_url)
    angel_engine = make_engine(angel_url)

    pipeline = latest_pipeline_status(report_date)
    sync = latest_sync_status(angel_engine)
    freshness = data_freshness(angel_engine, args.pilot_schema, report_date)
    quality = latest_quality(angel_engine, args.pilot_schema, report_date)
    recommendations = latest_recommendations(angel_engine, args.pilot_schema, report_date, args.model)
    portfolio = portfolio_status(research_engine, args.portfolio_id, report_date)
    risk = compute_risk(portfolio)
    alerts = build_alerts(
        freshness,
        quality,
        recommendations,
        risk,
        args.drawdown_alert,
        args.concentration_alert,
        args.recommendation_low_alert,
        args.recommendation_high_alert,
    )
    content = render_report(report_date, pipeline, sync, freshness, quality, portfolio, risk, recommendations, alerts)
    output_path = Path(args.output_md) if args.output_md else REPO_ROOT / "reports" / f"daily_paper_report_{report_date.isoformat()}.md"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")
    print(f"Wrote daily paper report: {output_path}")
    print(f"Alerts: {len(alerts)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
