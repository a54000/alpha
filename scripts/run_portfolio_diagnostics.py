#!/usr/bin/env python3
"""Generate diagnostics for the Swing V2.1 portfolio backtest."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime
import json
from pathlib import Path
import statistics
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
import os


RESULTS_PATH = Path("reports/portfolio_backtest_results.json")
OUTPUT_PATH = Path("reports/portfolio_diagnostics.json")


def pct_return(start: float, end: float) -> float | None:
    if start == 0:
        return None
    return end / start - 1


def parse_date(value: str):
    return datetime.strptime(value, "%Y-%m-%d").date()


def monthly_returns(equity_curve: list[dict[str, object]]) -> list[dict[str, object]]:
    by_month: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in equity_curve:
        by_month[str(row["date"])[:7]].append(row)
    result = []
    for month, rows in sorted(by_month.items()):
        start = float(rows[0]["equity"])
        end = float(rows[-1]["equity"])
        result.append({"month": month, "return": pct_return(start, end), "start_equity": start, "end_equity": end})
    return result


def rolling_returns(monthlies: list[dict[str, object]], window: int) -> list[dict[str, object]]:
    result = []
    for index in range(window - 1, len(monthlies)):
        chunk = monthlies[index - window + 1:index + 1]
        start = float(chunk[0]["start_equity"])
        end = float(chunk[-1]["end_equity"])
        result.append(
            {
                "end_month": chunk[-1]["month"],
                "window_months": window,
                "return": pct_return(start, end),
            }
        )
    return result


def factor_bucket_adx(value: float | None) -> str:
    if value is None:
        return "unknown"
    if value >= 40:
        return "adx_40_plus"
    if value >= 35:
        return "adx_35_40"
    if value >= 30:
        return "adx_30_35"
    if value >= 25:
        return "adx_25_30"
    return "adx_below_25"


def factor_bucket_sector_rank(value: float | None) -> str:
    if value is None:
        return "unknown"
    rank = int(value)
    if rank == 1:
        return "rank_1"
    if rank == 2:
        return "rank_2"
    if rank == 3:
        return "rank_3"
    if rank <= 5:
        return "rank_4_5"
    if rank <= 8:
        return "rank_6_8"
    return "rank_9_plus"


def aggregate_contribution(trades: list[dict[str, object]], key: str) -> list[dict[str, object]]:
    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for trade in trades:
        grouped[str(trade.get(key) or "UNKNOWN")].append(trade)
    rows = []
    for group, items in grouped.items():
        pnl = sum(float(item.get("pnl") or 0) for item in items)
        returns = [float(item["return"]) for item in items if item.get("return") is not None]
        rows.append(
            {
                key: group,
                "trade_count": len(items),
                "total_pnl": pnl,
                "avg_return": statistics.mean(returns) if returns else None,
                "win_rate": sum(1 for value in returns if value > 0) / len(returns) if returns else None,
            }
        )
    return sorted(rows, key=lambda row: row["total_pnl"], reverse=True)


def load_factor_data(trades: list[dict[str, object]]) -> dict[tuple[str, str], dict[str, float | None]]:
    load_dotenv(dotenv_path=Path(".env"))
    engine = create_engine(os.environ["DATABASE_URL"], future=True)
    keys = sorted({(trade["symbol"], trade["signal_date"]) for trade in trades})
    if not keys:
        return {}
    symbols = sorted({symbol for symbol, _ in keys})
    dates = sorted({date for _, date in keys})
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT f.symbol, f.date, f.adx_14, sd.rank_3m
                FROM features_daily f
                LEFT JOIN sector_daily sd ON sd.date = f.date AND sd.sector = f.sector
                WHERE f.symbol = ANY(:symbols)
                  AND f.date = ANY(CAST(:dates AS date[]))
                """
            ),
            {"symbols": symbols, "dates": dates},
        ).mappings().all()
    return {
        (row["symbol"], row["date"].isoformat()): {
            "adx": float(row["adx_14"]) if row["adx_14"] is not None else None,
            "sector_rank": float(row["rank_3m"]) if row["rank_3m"] is not None else None,
        }
        for row in rows
    }


def main() -> int:
    payload = json.loads(RESULTS_PATH.read_text(encoding="utf-8"))
    v21 = payload["V2.1"]
    equity_curve = v21["equity_curve"] if "equity_curve" in v21 else []
    if not equity_curve:
        # The compact report may omit equity. Fall back to CSV.
        import csv
        with Path("reports/portfolio_equity_curves.csv").open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            equity_curve = [
                {"date": row["date"], "equity": float(row["V2_1_equity"]), "cash": float(row["V2_1_cash"] or 0), "position_count": int(row["V2_1_positions"] or 0)}
                for row in reader
                if row.get("V2_1_equity")
            ]

    trades = v21["closed_trades"]
    factor_data = load_factor_data(trades)
    for trade in trades:
        data = factor_data.get((trade["symbol"], trade["signal_date"]), {})
        trade["adx"] = data.get("adx")
        trade["sector_rank"] = data.get("sector_rank")
        trade["adx_bucket"] = factor_bucket_adx(trade["adx"])
        trade["sector_rank_bucket"] = factor_bucket_sector_rank(trade["sector_rank"])

    monthlies = monthly_returns(equity_curve)
    rolling_3 = rolling_returns(monthlies, 3)
    rolling_6 = rolling_returns(monthlies, 6)
    sorted_trades = sorted(trades, key=lambda trade: float(trade.get("return") or 0), reverse=True)

    position_changes = Counter(trade["entry_date"] for trade in trades)
    avg_position_changes = statistics.mean(position_changes.values()) if position_changes else 0.0

    # Equal weight model; largest single-stock exposure is approximately 1 / portfolio size when fully invested.
    max_positions = max((int(row.get("position_count") or 0) for row in equity_curve), default=0)
    largest_single_stock_exposure = 1 / max_positions if max_positions else 0.0

    sector_concentration = v21["metrics"]["sector_concentration"]
    diagnostics = {
        "model": "V2.1",
        "summary": {
            "turnover": v21["metrics"]["turnover"],
            "average_holding_period": v21["metrics"]["average_holding_period"],
            "average_position_changes_per_rebalance": avg_position_changes,
            "largest_sector_exposure": sector_concentration["top_sector_avg_weight"],
            "largest_sector": sector_concentration["top_sector"],
            "largest_single_stock_exposure_estimate": largest_single_stock_exposure,
            "closed_trades": len(trades),
        },
        "top_50_winners": sorted_trades[:50],
        "top_50_losers": list(reversed(sorted_trades[-50:])),
        "monthly_returns": monthlies,
        "best_months": sorted(monthlies, key=lambda row: row["return"] or 0, reverse=True)[:10],
        "worst_months": sorted(monthlies, key=lambda row: row["return"] or 0)[:10],
        "rolling_3_month_returns": rolling_3,
        "rolling_6_month_returns": rolling_6,
        "sector_contribution": aggregate_contribution(trades, "sector"),
        "factor_contribution": {
            "adx_bucket": aggregate_contribution(trades, "adx_bucket"),
            "sector_rank_bucket": aggregate_contribution(trades, "sector_rank_bucket"),
        },
        "answers": {},
    }

    winners_pnl = sum(float(trade.get("pnl") or 0) for trade in sorted_trades[:10])
    total_pnl = sum(float(trade.get("pnl") or 0) for trade in trades)
    top_sector_pnl = diagnostics["sector_contribution"][0]["total_pnl"] if diagnostics["sector_contribution"] else 0
    negative_months = [row for row in monthlies if (row["return"] or 0) < 0]
    diagnostics["answers"] = {
        "performance_driven_by_small_number_of_trades": abs(winners_pnl / total_pnl) if total_pnl else None,
        "performance_driven_by_one_sector": abs(top_sector_pnl / total_pnl) if total_pnl else None,
        "negative_month_count": len(negative_months),
        "monthly_return_positive_ratio": (len(monthlies) - len(negative_months)) / len(monthlies) if monthlies else None,
        "worst_3_month_return": min((row["return"] for row in rolling_3 if row["return"] is not None), default=None),
        "worst_6_month_return": min((row["return"] for row in rolling_6 if row["return"] is not None), default=None),
    }

    OUTPUT_PATH.write_text(json.dumps(diagnostics, indent=2, default=str), encoding="utf-8")
    print(f"Wrote {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
