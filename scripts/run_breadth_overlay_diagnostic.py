"""Read-only breadth diagnostic for the frozen Swing V2.1 portfolio.

The script does not change recommendations, scoring, or portfolio rules. It
reconstructs historical trades with the existing trade-analysis lifecycle, then
annotates each trade with market and sector breadth available at entry.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import statistics
import sys
from dataclasses import asdict
from datetime import date, datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.api.trade_analysis_service import (
    STRATEGIES,
    TradeAnalysisRequest,
    TradeAnalysisService,
    reconstruct_trades,
)


OUTPUT_DIR = REPO_ROOT / "results" / "breadth_overlay_diagnostic"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run read-only breadth diagnostic for Swing V2.1 trades.")
    parser.add_argument("--start-date", type=date.fromisoformat, default=date(2022, 5, 25))
    parser.add_argument("--end-date", type=date.fromisoformat, default=date(2026, 6, 11))
    parser.add_argument("--strategy", choices=sorted(STRATEGIES), default="TOP10_WEEKLY")
    parser.add_argument("--initial-capital", type=float, default=1_000_000.0)
    parser.add_argument("--pilot-schema", default="pilot_phase2a")
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    return parser.parse_args()


def pct(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def bucket(value: float | None) -> str:
    if value is None:
        return "unknown"
    if value >= 0.60:
        return "high"
    if value >= 0.40:
        return "medium"
    return "low"


def mean(values: list[float]) -> float | None:
    return statistics.mean(values) if values else None


def median(values: list[float]) -> float | None:
    return statistics.median(values) if values else None


def max_drawdown(values: list[float]) -> float:
    if not values:
        return 0.0
    peak = values[0]
    drawdown = 0.0
    for value in values:
        peak = max(peak, value)
        if peak:
            drawdown = min(drawdown, value / peak - 1.0)
    return drawdown


def sharpe_from_returns(returns: list[float]) -> float | None:
    if len(returns) < 2:
        return None
    std = statistics.stdev(returns)
    if math.isclose(std, 0.0):
        return None
    return statistics.mean(returns) / std * math.sqrt(252)


def load_feature_breadth(engine, schema: str, start_date: date, end_date: date) -> dict[date, dict[str, object]]:
    query = text(
        f"""
        SELECT
            date,
            sector,
            COUNT(*) AS total_symbols,
            COUNT(*) FILTER (WHERE close > ema_50) AS above_ema50,
            COUNT(*) FILTER (WHERE close > ema_200) AS above_ema200,
            COUNT(*) FILTER (WHERE prior_20d_return > 0) AS positive_20d,
            COUNT(*) FILTER (WHERE adx_14 >= 20) AS adx20_count
        FROM {schema}.features_daily
        WHERE date BETWEEN :start_date AND :end_date
          AND close IS NOT NULL
          AND sector IS NOT NULL
        GROUP BY GROUPING SETS ((date), (date, sector))
        ORDER BY date ASC, sector ASC NULLS FIRST
        """
    )
    breadth: dict[date, dict[str, object]] = {}
    with engine.connect() as connection:
        rows = connection.execute(query, {"start_date": start_date, "end_date": end_date}).mappings().all()
    for row in rows:
        day = row["date"]
        target = breadth.setdefault(day, {"market": None, "sectors": {}})
        total = int(row["total_symbols"] or 0)
        metrics = {
            "total_symbols": total,
            "above_ema50_pct": pct(int(row["above_ema50"] or 0), total),
            "above_ema200_pct": pct(int(row["above_ema200"] or 0), total),
            "positive_20d_pct": pct(int(row["positive_20d"] or 0), total),
            "adx20_pct": pct(int(row["adx20_count"] or 0), total),
        }
        if row["sector"] is None:
            target["market"] = metrics
        else:
            target["sectors"][str(row["sector"])] = metrics
    return breadth


def enrich_trades(trades: list[dict[str, object]], breadth: dict[date, dict[str, object]]) -> list[dict[str, object]]:
    enriched: list[dict[str, object]] = []
    for trade in trades:
        entry_date = date.fromisoformat(str(trade["entry_date"]))
        sector = str(trade.get("sector") or "UNKNOWN")
        day = breadth.get(entry_date, {})
        market = day.get("market") or {}
        sector_metrics = (day.get("sectors") or {}).get(sector, {})
        sector_positive = sector_metrics.get("positive_20d_pct")
        market_positive = market.get("positive_20d_pct")
        row = {
            **trade,
            "market_total_symbols": market.get("total_symbols"),
            "market_above_ema50_pct": market.get("above_ema50_pct"),
            "market_above_ema200_pct": market.get("above_ema200_pct"),
            "market_positive_20d_pct": market_positive,
            "market_adx20_pct": market.get("adx20_pct"),
            "market_breadth_bucket": bucket(market_positive),
            "sector_total_symbols": sector_metrics.get("total_symbols"),
            "sector_above_ema50_pct": sector_metrics.get("above_ema50_pct"),
            "sector_above_ema200_pct": sector_metrics.get("above_ema200_pct"),
            "sector_positive_20d_pct": sector_positive,
            "sector_adx20_pct": sector_metrics.get("adx20_pct"),
            "sector_breadth_bucket": bucket(sector_positive),
        }
        enriched.append(row)
    return enriched


def summarize_bucket(rows: list[dict[str, object]], key: str) -> list[dict[str, object]]:
    output: list[dict[str, object]] = []
    for name in ["high", "medium", "low", "unknown"]:
        bucket_rows = [row for row in rows if row.get(key) == name]
        returns = [float(row["net_return_pct"]) for row in bucket_rows]
        pnls = [float(row["net_pnl"]) for row in bucket_rows]
        output.append(
            {
                "bucket_type": key,
                "bucket": name,
                "trade_count": len(bucket_rows),
                "win_rate": pct(sum(1 for row in bucket_rows if float(row["net_pnl"]) > 0), len(bucket_rows)),
                "avg_return": mean(returns),
                "median_return": median(returns),
                "total_net_pnl": sum(pnls),
                "avg_sector_positive_20d_pct": mean(
                    [float(row["sector_positive_20d_pct"]) for row in bucket_rows if row.get("sector_positive_20d_pct") is not None]
                ),
                "avg_market_positive_20d_pct": mean(
                    [float(row["market_positive_20d_pct"]) for row in bucket_rows if row.get("market_positive_20d_pct") is not None]
                ),
            }
        )
    return output


def simulate_closed_trade_overlay(
    trades: list[dict[str, object]],
    initial_capital: float,
    multipliers: dict[str, float],
) -> dict[str, object]:
    equity = initial_capital
    curve = [{"date": None, "equity": equity, "return": 0.0}]
    skipped = 0
    scaled_pnl = 0.0
    for row in sorted(trades, key=lambda item: (str(item["exit_date"]), int(item["trade_id"]))):
        multiplier = multipliers.get(str(row.get("sector_breadth_bucket")), 1.0)
        if math.isclose(multiplier, 0.0):
            skipped += 1
        pnl = float(row["net_pnl"]) * multiplier
        previous = equity
        equity += pnl
        scaled_pnl += pnl
        curve.append(
            {
                "date": row["exit_date"],
                "equity": equity,
                "return": (equity / previous - 1.0) if previous else 0.0,
            }
        )
    returns = [float(row["return"]) for row in curve[1:]]
    return {
        "ending_equity": equity,
        "total_return": equity / initial_capital - 1.0,
        "net_pnl": scaled_pnl,
        "max_drawdown": max_drawdown([float(row["equity"]) for row in curve]),
        "closed_trade_sharpe": sharpe_from_returns(returns),
        "trades_scaled_or_kept": len(trades) - skipped,
        "trades_skipped": skipped,
        "multipliers": multipliers,
    }


def low_breadth_loser_diagnostic(rows: list[dict[str, object]]) -> dict[str, object]:
    losers = [row for row in rows if float(row["net_pnl"]) < 0]
    low_sector_losers = [row for row in losers if row.get("sector_breadth_bucket") == "low"]
    low_market_losers = [row for row in losers if row.get("market_breadth_bucket") == "low"]
    return {
        "loser_count": len(losers),
        "low_sector_loser_count": len(low_sector_losers),
        "low_sector_loser_share": pct(len(low_sector_losers), len(losers)),
        "low_market_loser_count": len(low_market_losers),
        "low_market_loser_share": pct(len(low_market_losers), len(losers)),
        "low_sector_total_pnl": sum(float(row["net_pnl"]) for row in [item for item in rows if item.get("sector_breadth_bucket") == "low"]),
        "low_market_total_pnl": sum(float(row["net_pnl"]) for row in [item for item in rows if item.get("market_breadth_bucket") == "low"]),
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


def fmt_pct(value: object) -> str:
    if value is None:
        return "n/a"
    return f"{float(value) * 100:.2f}%"


def fmt_money(value: object) -> str:
    if value is None:
        return "n/a"
    return f"{float(value):,.0f}"


def render_report(summary: dict[str, object], bucket_rows: list[dict[str, object]], overlay_rows: list[dict[str, object]]) -> str:
    lines = [
        "# Breadth Overlay Diagnostic",
        "",
        "This is a read-only diagnostic. It does not change scoring, recommendations, trade lifecycle, or portfolio rules.",
        "",
        "## Inputs",
        "",
        f"- Strategy: {summary['strategy']}",
        f"- Date range: {summary['start_date']} to {summary['end_date']}",
        f"- Trades analyzed: {summary['trade_count']}",
        "- Market breadth: full pilot feature universe on each entry date.",
        "- Sector breadth: stocks in the candidate trade's sector on each entry date.",
        "- Primary breadth bucket: sector positive 20-day return participation.",
        "",
        "## Bucket Results",
        "",
        "| Bucket Type | Bucket | Trades | Win Rate | Avg Return | Median Return | Net PnL |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in bucket_rows:
        lines.append(
            f"| {row['bucket_type']} | {row['bucket']} | {row['trade_count']} | {fmt_pct(row['win_rate'])} | "
            f"{fmt_pct(row['avg_return'])} | {fmt_pct(row['median_return'])} | {fmt_money(row['total_net_pnl'])} |"
        )
    lines.extend(
        [
            "",
            "## Low Breadth And Losers",
            "",
            f"- Losers: {summary['loser_count']}",
            f"- Low sector-breadth losers: {summary['low_sector_loser_count']} ({fmt_pct(summary['low_sector_loser_share'])})",
            f"- Low market-breadth losers: {summary['low_market_loser_count']} ({fmt_pct(summary['low_market_loser_share'])})",
            f"- Low sector-breadth total PnL: {fmt_money(summary['low_sector_total_pnl'])}",
            f"- Low market-breadth total PnL: {fmt_money(summary['low_market_total_pnl'])}",
            "",
            "## Sizing Overlay Diagnostic",
            "",
            "These are closed-trade diagnostic overlays, not executable portfolio backtests. They scale realized trade PnL by breadth bucket to test whether breadth has useful separation.",
            "",
            "| Overlay | Total Return | Max Drawdown | Closed-Trade Sharpe | Trades Kept/Scaled | Trades Skipped |",
            "| --- | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in overlay_rows:
        lines.append(
            f"| {row['overlay']} | {fmt_pct(row['total_return'])} | {fmt_pct(row['max_drawdown'])} | "
            f"{row['closed_trade_sharpe'] if row['closed_trade_sharpe'] is not None else 'n/a'} | "
            f"{row['trades_scaled_or_kept']} | {row['trades_skipped']} |"
        )
    lines.extend(
        [
            "",
            "## Preliminary Verdict",
            "",
            str(summary["verdict"]),
            "",
            "## Artifacts",
            "",
            "- `trade_breadth_diagnostic.csv`: every trade with market and sector breadth at entry.",
            "- `breadth_bucket_summary.csv`: grouped return statistics by market and sector breadth bucket.",
            "- `breadth_overlay_summary.json`: summary and sizing overlay diagnostics.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    load_dotenv(REPO_ROOT / ".env")
    angel_url = os.environ.get("ANGEL_DATABASE_URL")
    if not angel_url:
        raise RuntimeError("ANGEL_DATABASE_URL is required.")

    engine = create_engine(angel_url, future=True, pool_pre_ping=True)
    service = TradeAnalysisService(angel_engine=engine, pilot_schema=args.pilot_schema)
    request = TradeAnalysisRequest(
        start_date=args.start_date,
        end_date=args.end_date,
        strategy=args.strategy,
        initial_capital=args.initial_capital,
    )
    recommendations = service._load_recommendations(request)
    prices = service._load_prices(request, {str(row["symbol"]) for row in recommendations})
    result = reconstruct_trades(request, recommendations, prices)
    trades = result["trades"]

    breadth = load_feature_breadth(engine, args.pilot_schema, args.start_date, args.end_date)
    enriched = enrich_trades(trades, breadth)
    bucket_rows = summarize_bucket(enriched, "sector_breadth_bucket") + summarize_bucket(enriched, "market_breadth_bucket")
    loser_summary = low_breadth_loser_diagnostic(enriched)

    overlays = [
        ("baseline_no_breadth_scaling", {"high": 1.0, "medium": 1.0, "low": 1.0, "unknown": 1.0}),
        ("half_size_low_sector_breadth", {"high": 1.0, "medium": 1.0, "low": 0.5, "unknown": 1.0}),
        ("skip_low_sector_breadth", {"high": 1.0, "medium": 1.0, "low": 0.0, "unknown": 1.0}),
        ("high_full_medium_half_low_skip", {"high": 1.0, "medium": 0.5, "low": 0.0, "unknown": 1.0}),
    ]
    overlay_rows = []
    for name, multipliers in overlays:
        overlay_rows.append({"overlay": name, **simulate_closed_trade_overlay(enriched, args.initial_capital, multipliers)})

    baseline = overlay_rows[0]
    best_overlay = max(overlay_rows[1:], key=lambda row: float(row["total_return"]))
    low_sector_bucket = next(row for row in bucket_rows if row["bucket_type"] == "sector_breadth_bucket" and row["bucket"] == "low")
    verdict = (
        "Low sector breadth appears useful as a risk overlay candidate."
        if (low_sector_bucket["trade_count"] and float(low_sector_bucket["avg_return"] or 0) < 0 and float(best_overlay["max_drawdown"]) >= float(baseline["max_drawdown"]))
        else "Breadth separation is mixed; do not promote it to strategy logic without a full portfolio backtest."
    )
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "start_date": args.start_date.isoformat(),
        "end_date": args.end_date.isoformat(),
        "strategy": args.strategy,
        "initial_capital": args.initial_capital,
        "trade_count": len(enriched),
        "recommendation_rows": len(recommendations),
        **loser_summary,
        "verdict": verdict,
        "constraints": {
            "scoring_changed": False,
            "recommendations_changed": False,
            "strategy_rules_changed": False,
            "database_modified": False,
        },
    }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(args.output_dir / "trade_breadth_diagnostic.csv", enriched)
    write_csv(args.output_dir / "breadth_bucket_summary.csv", bucket_rows)
    write_csv(args.output_dir / "breadth_overlay_diagnostic.csv", overlay_rows)
    (args.output_dir / "breadth_overlay_summary.json").write_text(
        json.dumps({"summary": summary, "bucket_summary": bucket_rows, "overlay_summary": overlay_rows}, indent=2, default=str),
        encoding="utf-8",
    )
    (args.output_dir / "BREADTH_OVERLAY_DIAGNOSTIC.md").write_text(render_report(summary, bucket_rows, overlay_rows), encoding="utf-8")

    print(json.dumps({"output_dir": str(args.output_dir), "summary": summary, "overlay_summary": overlay_rows}, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
