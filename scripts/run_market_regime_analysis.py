#!/usr/bin/env python3
"""Analyze Swing V2.1 portfolio behavior across market regimes."""

from __future__ import annotations

from collections import defaultdict
from datetime import date
import json
import math
from pathlib import Path
import statistics
import sys

from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.backtesting.portfolio_backtest import PortfolioBacktestConfig, PortfolioBacktesterV1
from db.models import FeaturesDaily, IndexPricesDaily, PricesDaily
from db.session import build_session_factory


MODEL = "swing_v2_1"
OUTPUT_PATH = Path("reports/market_regime_analysis.json")

VARIANTS = [
    ("top5_weekly", "Top 5 Weekly", PortfolioBacktestConfig(model=MODEL, portfolio_size=5)),
    ("top10_weekly", "Top 10 Weekly", PortfolioBacktestConfig(model=MODEL, portfolio_size=10)),
    (
        "top10_weekly_max2_sector",
        "Top 10 Weekly + Max 2 Positions Per Sector",
        PortfolioBacktestConfig(model=MODEL, portfolio_size=10, max_positions_per_sector=2, max_candidate_rank=50),
    ),
]


def parse_date(value: str) -> date:
    return date.fromisoformat(value)


def load_index_data(start: date, end: date) -> dict[date, dict[str, float]]:
    with build_session_factory()() as session:
        rows = session.execute(
            select(IndexPricesDaily.date, IndexPricesDaily.open, IndexPricesDaily.close)
            .where(
                IndexPricesDaily.index_name == "NIFTY500",
                IndexPricesDaily.date >= start,
                IndexPricesDaily.date <= end,
            )
            .order_by(IndexPricesDaily.date.asc())
        ).all()
    return {
        row.date: {
            "open": float(row.open or row.close),
            "close": float(row.close or row.open),
        }
        for row in rows
        if row.open is not None or row.close is not None
    }


def classify_trend(index_data: dict[date, dict[str, float]]) -> dict[date, str]:
    dates = sorted(index_data)
    labels: dict[date, str] = {}
    closes = [index_data[item]["close"] for item in dates]
    for idx, item in enumerate(dates):
        if idx < 200 or idx < 60:
            labels[item] = "neutral"
            continue
        dma200 = statistics.mean(closes[idx - 199 : idx + 1])
        ret60 = closes[idx] / closes[idx - 60] - 1 if closes[idx - 60] else 0.0
        close = closes[idx]
        if close > dma200 and ret60 > 0:
            labels[item] = "bull_trend"
        elif close < dma200 and ret60 < 0:
            labels[item] = "bear_trend"
        else:
            labels[item] = "neutral"
    return labels


def classify_volatility(index_data: dict[date, dict[str, float]]) -> dict[date, str]:
    dates = sorted(index_data)
    daily_returns: list[float | None] = [None]
    for left, right in zip(dates, dates[1:]):
        left_close = index_data[left]["close"]
        right_close = index_data[right]["close"]
        daily_returns.append(right_close / left_close - 1 if left_close else None)

    vol_by_date: dict[date, float] = {}
    for idx, item in enumerate(dates):
        if idx < 20:
            continue
        window = [value for value in daily_returns[idx - 19 : idx + 1] if value is not None]
        if len(window) > 1:
            vol_by_date[item] = statistics.stdev(window) * math.sqrt(252)
    vols = sorted(vol_by_date.values())
    if not vols:
        return {item: "normal_volatility" for item in dates}
    low_cut = vols[int(len(vols) * 0.25)]
    high_cut = vols[int(len(vols) * 0.75)]
    labels = {}
    for item in dates:
        vol = vol_by_date.get(item)
        if vol is None:
            labels[item] = "normal_volatility"
        elif vol <= low_cut:
            labels[item] = "low_volatility"
        elif vol >= high_cut:
            labels[item] = "high_volatility"
        else:
            labels[item] = "normal_volatility"
    return labels


def classify_breadth(start: date, end: date) -> dict[date, str]:
    with build_session_factory()() as session:
        rows = session.execute(
            select(PricesDaily.date, PricesDaily.close, FeaturesDaily.ema_200)
            .join(FeaturesDaily, (FeaturesDaily.symbol == PricesDaily.symbol) & (FeaturesDaily.date == PricesDaily.date))
            .where(
                PricesDaily.date >= start,
                PricesDaily.date <= end,
                PricesDaily.close.is_not(None),
                FeaturesDaily.ema_200.is_not(None),
            )
        ).all()
    counts: dict[date, list[int]] = defaultdict(lambda: [0, 0])
    for item_date, close, ema200 in rows:
        counts[item_date][1] += 1
        if float(close) > float(ema200):
            counts[item_date][0] += 1
    labels = {}
    for item_date, (above, total) in counts.items():
        pct = above / total if total else 0.0
        if pct > 0.70:
            labels[item_date] = "strong_breadth"
        elif pct < 0.30:
            labels[item_date] = "weak_breadth"
        else:
            labels[item_date] = "neutral_breadth"
    return labels


def benchmark_return(index_data: dict[date, dict[str, float]], entry: date, exit_date: date) -> float | None:
    if entry not in index_data or exit_date not in index_data:
        return None
    entry_price = index_data[entry]["open"]
    exit_price = index_data[exit_date]["close"]
    return exit_price / entry_price - 1 if entry_price else None


def trade_group_metrics(
    trades: list[dict[str, object]],
    labels: dict[date, str],
    index_data: dict[date, dict[str, float]],
    default_label: str,
) -> dict[str, dict[str, float | int]]:
    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for trade in trades:
        entry = parse_date(str(trade["entry_date"]))
        grouped[labels.get(entry, default_label)].append(trade)
    output = {}
    for label, label_trades in sorted(grouped.items()):
        returns = [float(trade["return"]) for trade in label_trades]
        wins = [value for value in returns if value > 0]
        losses = [value for value in returns if value < 0]
        bench_returns = [
            benchmark_return(index_data, parse_date(str(trade["entry_date"])), parse_date(str(trade["exit_date"])))
            for trade in label_trades
        ]
        valid_bench = [value for value in bench_returns if value is not None]
        output[label] = {
            "trade_count": len(returns),
            "avg_return": statistics.mean(returns) if returns else 0.0,
            "win_rate": len(wins) / len(returns) if returns else 0.0,
            "profit_factor": sum(wins) / abs(sum(losses)) if losses else (float("inf") if wins else 0.0),
            "benchmark_avg_return": statistics.mean(valid_bench) if valid_bench else None,
            "alpha": (statistics.mean(returns) - statistics.mean(valid_bench)) if returns and valid_bench else None,
            "total_pnl": sum(float(trade.get("pnl") or 0.0) for trade in label_trades),
        }
    return output


def equity_group_metrics(equity_curve: list[dict[str, object]], labels: dict[date, str]) -> dict[str, dict[str, float | int]]:
    by_label: dict[str, list[float]] = defaultdict(list)
    previous_equity = None
    for row in equity_curve:
        row_date = parse_date(str(row["date"]))
        equity = float(row["equity"])
        if previous_equity is not None and previous_equity > 0:
            by_label[labels.get(row_date, "neutral")].append(equity / previous_equity - 1)
        previous_equity = equity
    output = {}
    for label, returns in sorted(by_label.items()):
        total_return = math.prod(1 + value for value in returns) - 1 if returns else 0.0
        cagr = (1 + total_return) ** (252 / len(returns)) - 1 if returns and total_return > -1 else 0.0
        vol = statistics.stdev(returns) if len(returns) > 1 else 0.0
        output[label] = {
            "days": len(returns),
            "total_return": total_return,
            "cagr": cagr,
            "sharpe": statistics.mean(returns) / vol * math.sqrt(252) if vol else 0.0,
        }
    return output


def regime_counts(labels: dict[date, str]) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for label in labels.values():
        counts[label] += 1
    return dict(sorted(counts.items()))


def main() -> int:
    backtester = PortfolioBacktesterV1(build_session_factory())
    portfolio_results = {
        label: {"name": name, "result": backtester.run(config)}
        for label, name, config in VARIANTS
    }
    dates = [
        parse_date(str(row["date"]))
        for item in portfolio_results.values()
        for row in item["result"]["equity_curve"]
    ]
    start, end = min(dates), max(dates)
    index_data = load_index_data(start, end)
    trend_labels = classify_trend(index_data)
    volatility_labels = classify_volatility(index_data)
    breadth_labels = classify_breadth(start, end)

    analysis = {}
    for label, item in portfolio_results.items():
        result = item["result"]
        analysis[label] = {
            "name": item["name"],
            "gross_metrics": result["metrics"],
            "trend_regime": {
                "trade_metrics": trade_group_metrics(result["closed_trades"], trend_labels, index_data, "neutral"),
                "portfolio_metrics": equity_group_metrics(result["equity_curve"], trend_labels),
            },
            "breadth_regime": {
                "trade_metrics": trade_group_metrics(result["closed_trades"], breadth_labels, index_data, "neutral_breadth"),
            },
            "volatility_regime": {
                "trade_metrics": trade_group_metrics(result["closed_trades"], volatility_labels, index_data, "normal_volatility"),
            },
        }

    output = {
        "model": MODEL,
        "date_range": {"start": start.isoformat(), "end": end.isoformat()},
        "methodology": {
            "trade_regime_assignment": "entry_date",
            "trend": "bull close>200dma and 60d return>0; bear close<200dma and 60d return<0; else neutral",
            "breadth": "percent of stocks with close>ema200 using features_daily and prices_daily",
            "volatility": "nifty500 20d realized volatility quartiles",
            "alpha": "trade avg return minus matched NIFTY500 entry-open to exit-close avg return",
        },
        "regime_counts": {
            "trend": regime_counts(trend_labels),
            "breadth": regime_counts(breadth_labels),
            "volatility": regime_counts(volatility_labels),
        },
        "portfolio_structures": analysis,
    }
    OUTPUT_PATH.parent.mkdir(exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(output, indent=2, default=str), encoding="utf-8")
    print(f"Wrote {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

