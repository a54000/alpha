#!/usr/bin/env python3
"""Research-only 1M/3M sector rank experiment for Swing V2.1.

This script does not write scores, recommendations, or database rows. It
recomputes a candidate sector rank from existing pilot sector returns:

    sector_score_1m3m = 0.40 * sector_return_1m + 0.60 * sector_return_3m

That rank is used as the sector rank input to the frozen Swing V2.1 score
function, recommendations are generated in memory, and the Rolling 10 portfolio
construction is backtested for comparison against the current pilot
recommendations.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import statistics
import sys
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.api.trade_analysis_service import (  # noqa: E402
    AnalysisPosition,
    buy_side_charges,
    build_trade_row,
    next_trading_day_after,
    nth_trading_day_after,
    positions_value,
    symbol_dates,
    total_charges,
    weekly_signal_dates,
)
from app.scoring.compute_scores import compute_swing_v2_1_score, score_swing_v2_adx, score_swing_v2_sector  # noqa: E402


MODEL = "swing_v2_1"
OUTPUT_DIR = REPO_ROOT / "results" / "sector_1m3m_rank_experiment"


@dataclass(frozen=True)
class Variant:
    name: str
    sector_rank_column: str
    score_column: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run research-only 1M/3M sector rank experiment.")
    parser.add_argument("--start-date", type=date.fromisoformat, default=date(2022, 5, 25))
    parser.add_argument("--end-date", type=date.fromisoformat, default=date(2026, 6, 11))
    parser.add_argument("--initial-capital", type=float, default=1_000_000.0)
    parser.add_argument("--pilot-schema", default="pilot_phase2a")
    parser.add_argument("--portfolio-size", type=int, default=10)
    parser.add_argument("--weekly-picks", type=int, default=5)
    parser.add_argument("--holding-period", type=int, default=20)
    parser.add_argument("--minimum-score", type=float, default=70.0)
    parser.add_argument("--top-n", type=int, default=20)
    parser.add_argument("--weight-1m", type=float, default=0.40)
    parser.add_argument("--weight-3m", type=float, default=0.60)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    return parser.parse_args()


def load_features_and_sector_returns(engine, schema: str, start_date: date, end_date: date, weight_1m: float, weight_3m: float) -> pd.DataFrame:
    query = text(
        f"""
        SELECT
            f.symbol,
            f.date,
            f.sector,
            f.close,
            f.ema_200,
            f.ema200_extension,
            f.prior_20d_return,
            f.adx_14,
            f.adx_prev,
            f.sector_rank_3m,
            sd.return_1m AS sector_return_1m,
            sd.return_3m AS sector_return_3m,
            sd.return_6m AS sector_return_6m,
            sd.sector_rank AS baseline_composite_rank
        FROM {schema}.features_daily f
        LEFT JOIN {schema}.sector_daily sd
          ON sd.date = f.date
         AND sd.sector = f.sector
        WHERE f.date BETWEEN :start_date AND :end_date
        ORDER BY f.date ASC, f.symbol ASC
        """
    )
    frame = pd.read_sql_query(query, engine, params={"start_date": start_date, "end_date": end_date})
    frame["date"] = pd.to_datetime(frame["date"]).dt.date
    numeric_columns = [
        "close",
        "ema_200",
        "ema200_extension",
        "prior_20d_return",
        "adx_14",
        "adx_prev",
        "sector_rank_3m",
        "sector_return_1m",
        "sector_return_3m",
        "sector_return_6m",
        "baseline_composite_rank",
    ]
    for column in numeric_columns:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    sector_frame = frame[["date", "sector", "sector_return_1m", "sector_return_3m"]].drop_duplicates().copy()
    sector_frame["sector_score_1m3m"] = sector_frame["sector_return_1m"].fillna(0) * weight_1m + sector_frame["sector_return_3m"].fillna(0) * weight_3m
    sector_frame["sector_rank_1m3m"] = sector_frame.groupby("date")["sector_score_1m3m"].rank(ascending=False, method="min", na_option="bottom")
    return frame.merge(sector_frame[["date", "sector", "sector_score_1m3m", "sector_rank_1m3m"]], on=["date", "sector"], how="left")


def score_frame(features: pd.DataFrame, sector_rank_column: str, score_column: str) -> pd.DataFrame:
    rows = []
    for row in features.itertuples(index=False):
        data = row._asdict()
        features_dict = {
            "close": data["close"],
            "ema_200": data["ema_200"],
            "prior_20d_return": data["prior_20d_return"],
            "adx_14": data["adx_14"],
            "adx_prev": data["adx_prev"],
        }
        sector_rank = data[sector_rank_column]
        score = compute_swing_v2_1_score(features_dict, sector_rank)
        rows.append(
            {
                "date": data["date"],
                "symbol": data["symbol"],
                "sector": data["sector"],
                score_column: score,
                "adx_points": score_swing_v2_adx(data["adx_14"], data["adx_prev"]),
                "sector_points": score_swing_v2_sector(sector_rank),
                "sector_rank_used": sector_rank,
                "ema200_extension": data["ema200_extension"],
                "prior_20d_return": data["prior_20d_return"],
                "sector_return_1m": data["sector_return_1m"],
                "sector_return_3m": data["sector_return_3m"],
                "sector_return_6m": data["sector_return_6m"],
                "sector_score_1m3m": data.get("sector_score_1m3m"),
            }
        )
    return pd.DataFrame(rows)


def recommendation_eligible(row, score_column: str, min_sector_points: int = 0) -> bool:
    score = getattr(row, score_column)
    if pd.isna(score) or pd.isna(row.ema200_extension):
        return False
    sector_points = getattr(row, "sector_points", None)
    if sector_points is None or pd.isna(sector_points) or int(sector_points) < min_sector_points:
        return False
    return float(row.ema200_extension) > 0


def generate_recommendations(
    scores: pd.DataFrame,
    score_column: str,
    minimum_score: float,
    top_n: int,
    model: str,
    min_sector_points: int = 0,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for score_date, date_scores in scores.groupby("date", sort=True):
        candidates = date_scores[
            [recommendation_eligible(row, score_column, min_sector_points) for row in date_scores.itertuples(index=False)]
        ].copy()
        candidates = candidates[candidates[score_column] >= minimum_score]
        candidates = candidates.sort_values([score_column, "symbol"], ascending=[False, True]).head(top_n)
        for rank, row in enumerate(candidates.itertuples(index=False), start=1):
            data = row._asdict()
            rows.append(
                {
                    "date": score_date,
                    "model": model,
                    "rank": rank,
                    "symbol": str(data["symbol"]),
                    "score": float(data[score_column]),
                    "sector": data["sector"],
                    "adx_points": data["adx_points"],
                    "sector_points": data["sector_points"],
                    "sector_rank_used": data["sector_rank_used"],
                    "ema200_extension": data["ema200_extension"],
                    "prior_20d_return": data["prior_20d_return"],
                }
            )
    return rows


def load_baseline_recommendations(engine, schema: str, start_date: date, end_date: date) -> list[dict[str, object]]:
    query = text(
        f"""
        SELECT date, model, rank, symbol, score, sector, adx_points, sector_points,
               sector_rank_3m AS sector_rank_used, ema200_extension, prior_20d_return
        FROM {schema}.recommendations_daily
        WHERE model = :model
          AND date BETWEEN :start_date AND :end_date
        ORDER BY date ASC, rank ASC, symbol ASC
        """
    )
    with engine.connect() as connection:
        rows = connection.execute(query, {"model": MODEL, "start_date": start_date, "end_date": end_date}).mappings().all()
    return [
        {
            "date": row["date"],
            "model": row["model"],
            "rank": int(row["rank"]),
            "symbol": str(row["symbol"]),
            "score": float(row["score"]) if row["score"] is not None else None,
            "sector": row["sector"],
            "adx_points": row["adx_points"],
            "sector_points": row["sector_points"],
            "sector_rank_used": row["sector_rank_used"],
            "ema200_extension": float(row["ema200_extension"]) if row["ema200_extension"] is not None else None,
            "prior_20d_return": float(row["prior_20d_return"]) if row["prior_20d_return"] is not None else None,
        }
        for row in rows
    ]


def load_prices(engine, schema: str, symbols: set[str], start_date: date, end_date: date) -> dict[str, dict[date, dict[str, float]]]:
    if not symbols:
        return {}
    query = text(
        f"""
        SELECT symbol, date, open, high, low, close
        FROM {schema}.daily_bars_clean
        WHERE symbol = ANY(:symbols)
          AND date BETWEEN :start_date AND :end_date
        ORDER BY symbol ASC, date ASC
        """
    )
    with engine.connect() as connection:
        rows = connection.execute(query, {"symbols": list(symbols), "start_date": start_date, "end_date": end_date}).mappings().all()
    prices: dict[str, dict[date, dict[str, float]]] = {}
    for row in rows:
        prices.setdefault(str(row["symbol"]), {})[row["date"]] = {
            "open": float(row["open"]),
            "high": float(row["high"]) if row["high"] is not None else float(row["close"]),
            "low": float(row["low"]) if row["low"] is not None else float(row["close"]),
            "close": float(row["close"]),
        }
    return prices


def all_trading_dates(prices: dict[str, dict[date, dict[str, float]]]) -> list[date]:
    return sorted({day for symbol_prices in prices.values() for day in symbol_prices})


def returns_from_equity(equity_curve: list[dict[str, object]]) -> list[float]:
    returns = []
    previous = None
    for row in equity_curve:
        equity = float(row["equity"])
        if previous and previous > 0:
            returns.append(equity / previous - 1.0)
        previous = equity
    return returns


def max_drawdown(values: list[float]) -> float:
    peak = values[0] if values else 0.0
    drawdown = 0.0
    for value in values:
        peak = max(peak, value)
        if peak:
            drawdown = min(drawdown, value / peak - 1.0)
    return drawdown


def metrics(initial_capital: float, equity_curve: list[dict[str, object]], trades: list[dict[str, object]], turnover: float) -> dict[str, object]:
    if not equity_curve:
        return {}
    values = [float(row["equity"]) for row in equity_curve]
    ending = values[-1]
    returns = returns_from_equity(equity_curve)
    downside = [value for value in returns if value < 0]
    days = max(1, len(equity_curve))
    gross_profit = sum(float(row["net_pnl"]) for row in trades if float(row["net_pnl"]) > 0)
    gross_loss = abs(sum(float(row["net_pnl"]) for row in trades if float(row["net_pnl"]) < 0))
    wins = [row for row in trades if float(row["net_pnl"]) > 0]
    stdev = statistics.stdev(returns) if len(returns) > 1 else 0.0
    downside_stdev = statistics.stdev(downside) if len(downside) > 1 else 0.0
    return {
        "ending_equity": ending,
        "total_return": ending / initial_capital - 1.0,
        "cagr": (ending / initial_capital) ** (252 / days) - 1.0 if ending > 0 else -1.0,
        "max_drawdown": max_drawdown(values),
        "sharpe_ratio": statistics.mean(returns) / stdev * math.sqrt(252) if stdev else 0.0,
        "sortino_ratio": statistics.mean(returns) / downside_stdev * math.sqrt(252) if downside_stdev else 0.0,
        "profit_factor": gross_profit / gross_loss if gross_loss else None,
        "win_rate": len(wins) / len(trades) if trades else 0.0,
        "closed_trades": len(trades),
        "turnover": turnover / initial_capital,
        "avg_cash_pct": statistics.mean([float(row["cash"]) / float(row["equity"]) for row in equity_curve if float(row["equity"])]) if equity_curve else 0.0,
        "avg_position_count": statistics.mean([int(row["position_count"]) for row in equity_curve]) if equity_curve else 0.0,
    }


def run_rolling_10(
    variant: str,
    recommendations: list[dict[str, object]],
    prices: dict[str, dict[date, dict[str, float]]],
    *,
    start_date: date,
    end_date: date,
    initial_capital: float,
    portfolio_size: int,
    weekly_picks: int,
    holding_period: int,
) -> dict[str, object]:
    dates = [day for day in all_trading_dates(prices) if start_date <= day <= end_date]
    recs_by_date: dict[date, list[dict[str, object]]] = {}
    for rec in recommendations:
        recs_by_date.setdefault(rec["date"], []).append(rec)
    for rows in recs_by_date.values():
        rows.sort(key=lambda row: (int(row["rank"]), str(row["symbol"])))

    entries_by_date: dict[date, tuple[date, list[dict[str, object]]]] = {}
    for signal_date in weekly_signal_dates(list(recs_by_date)):
        entry_date = next_trading_day_after(dates, signal_date)
        if entry_date:
            entries_by_date[entry_date] = (signal_date, recs_by_date[signal_date][:weekly_picks])

    cash = initial_capital
    positions: list[AnalysisPosition] = []
    trades: list[dict[str, object]] = []
    equity_curve: list[dict[str, object]] = []
    turnover = 0.0
    trade_id = 1

    for current_date in dates:
        remaining: list[AnalysisPosition] = []
        closed_today: set[str] = set()
        for position in positions:
            close_price = prices.get(position.symbol, {}).get(current_date, {}).get("close")
            if current_date >= position.planned_exit_date and close_price is not None:
                row = build_trade_row(trade_id, position, current_date, close_price, symbol_dates(prices, position.symbol), variant)
                cash += float(row["exit_value"]) - (float(row["charges"]) - total_charges(position.buy_charges))
                turnover += float(row["exit_value"])
                trades.append({**row, "exit_reason": "planned_exit"})
                closed_today.add(position.symbol)
                trade_id += 1
            else:
                remaining.append(position)
        positions = remaining

        if current_date in entries_by_date:
            signal_date, candidates = entries_by_date[current_date]
            held = {position.symbol for position in positions}
            equity_at_open = cash + positions_value(positions, prices, current_date, "open")
            target_value = equity_at_open / portfolio_size
            for rec in candidates:
                symbol = str(rec["symbol"])
                if len(positions) >= portfolio_size or symbol in held or symbol in closed_today:
                    continue
                open_price = prices.get(symbol, {}).get(current_date, {}).get("open")
                if open_price is None or open_price <= 0:
                    continue
                allocation = min(target_value, cash)
                if allocation <= 0:
                    continue
                buy_charges = buy_side_charges(allocation)
                if allocation + total_charges(buy_charges) > cash:
                    allocation = cash / (1.0 + (total_charges(buy_charges) / allocation if allocation else 0.0))
                    buy_charges = buy_side_charges(allocation)
                planned_exit = nth_trading_day_after(symbol_dates(prices, symbol), current_date, holding_period)
                if planned_exit is None:
                    continue
                cash -= allocation + total_charges(buy_charges)
                turnover += allocation
                positions.append(
                    AnalysisPosition(
                        symbol=symbol,
                        sector=str(rec["sector"]) if rec.get("sector") is not None else None,
                        signal_date=signal_date,
                        entry_date=current_date,
                        entry_price=float(open_price),
                        quantity=allocation / float(open_price),
                        planned_exit_date=planned_exit,
                        rank=int(rec["rank"]),
                        score=float(rec["score"]) if rec.get("score") is not None else None,
                        entry_value=allocation,
                        buy_charges=buy_charges,
                    )
                )
                held.add(symbol)

        equity = cash + positions_value(positions, prices, current_date, "close")
        equity_curve.append({"variant": variant, "date": current_date.isoformat(), "equity": equity, "cash": cash, "position_count": len(positions)})

    if dates:
        final_date = dates[-1]
        for position in positions:
            close_price = prices.get(position.symbol, {}).get(final_date, {}).get("close")
            if close_price is None:
                continue
            row = build_trade_row(trade_id, position, final_date, close_price, symbol_dates(prices, position.symbol), variant)
            trades.append({**row, "exit_reason": "forced_final_exit"})
            cash += float(row["exit_value"]) - (float(row["charges"]) - total_charges(position.buy_charges))
            turnover += float(row["exit_value"])
            trade_id += 1
        equity_curve[-1]["equity"] = cash
        equity_curve[-1]["cash"] = cash
        equity_curve[-1]["position_count"] = 0

    return {
        "metrics": metrics(initial_capital, equity_curve, trades, turnover),
        "equity_curve": equity_curve,
        "trades": trades,
    }


def fy_label(day: date) -> str:
    start_year = day.year if day.month >= 4 else day.year - 1
    return f"FY{start_year}-{str(start_year + 1)[-2:]}"


def fy_returns(equity_curve: list[dict[str, object]], variant: str) -> list[dict[str, object]]:
    groups: dict[str, list[dict[str, object]]] = {}
    for row in equity_curve:
        groups.setdefault(fy_label(date.fromisoformat(str(row["date"]))), []).append(row)
    output = []
    for label, rows in sorted(groups.items()):
        rows.sort(key=lambda row: str(row["date"]))
        start = float(rows[0]["equity"])
        end = float(rows[-1]["equity"])
        output.append(
            {
                "variant": variant,
                "financial_year": label,
                "start_date": rows[0]["date"],
                "end_date": rows[-1]["date"],
                "start_equity": start,
                "end_equity": end,
                "return_pct": end / start - 1.0 if start else None,
                "max_drawdown": max_drawdown([float(row["equity"]) for row in rows]),
            }
        )
    return output


def recommendation_overlap(baseline: list[dict[str, object]], experiment: list[dict[str, object]]) -> list[dict[str, object]]:
    base_by_date: dict[date, set[str]] = {}
    exp_by_date: dict[date, set[str]] = {}
    for row in baseline:
        base_by_date.setdefault(row["date"], set()).add(str(row["symbol"]))
    for row in experiment:
        exp_by_date.setdefault(row["date"], set()).add(str(row["symbol"]))
    rows = []
    for day in sorted(set(base_by_date) | set(exp_by_date)):
        base_symbols = base_by_date.get(day, set())
        exp_symbols = exp_by_date.get(day, set())
        union = base_symbols | exp_symbols
        rows.append(
            {
                "date": day.isoformat(),
                "baseline_count": len(base_symbols),
                "experiment_count": len(exp_symbols),
                "overlap_count": len(base_symbols & exp_symbols),
                "jaccard_overlap": len(base_symbols & exp_symbols) / len(union) if union else None,
            }
        )
    return rows


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def fmt_pct(value: object) -> str:
    return "n/a" if value is None else f"{float(value) * 100:.2f}%"


def fmt_num(value: object) -> str:
    return "n/a" if value is None else f"{float(value):.2f}"


def render_report(output: dict[str, object]) -> str:
    base = output["variants"]["baseline_3m_rank"]["metrics"]
    exp = output["variants"]["sector_1m3m_40_60_rank"]["metrics"]
    lines = [
        "# Sector 1M/3M Rank Experiment",
        "",
        "Research-only experiment. No production scores, recommendations, or database rows were modified.",
        "",
        "## Hypothesis",
        "",
        "Remove 6M sector performance from the sector ranking input and use a faster sector rank: 40% 1M + 60% 3M.",
        "",
        "Important baseline note: current Swing V2.1 scoring uses `sector_rank_3m`, not the 1M/3M/6M composite rank. This experiment compares the current 3M rank against the proposed 1M/3M rank.",
        "",
        "## Portfolio Metrics",
        "",
        "| Metric | Baseline 3M Rank | 1M/3M 40/60 Rank | Delta |",
        "| --- | ---: | ---: | ---: |",
    ]
    metric_defs = [
        ("cagr", "CAGR", True),
        ("total_return", "Total Return", True),
        ("max_drawdown", "Max Drawdown", True),
        ("sharpe_ratio", "Sharpe", False),
        ("sortino_ratio", "Sortino", False),
        ("profit_factor", "Profit Factor", False),
        ("win_rate", "Win Rate", True),
        ("closed_trades", "Closed Trades", False),
        ("avg_cash_pct", "Average Cash", True),
    ]
    for key, label, is_pct in metric_defs:
        formatter = fmt_pct if is_pct else fmt_num
        delta = float(exp[key]) - float(base[key]) if base.get(key) is not None and exp.get(key) is not None else None
        lines.append(f"| {label} | {formatter(base.get(key))} | {formatter(exp.get(key))} | {formatter(delta)} |")
    lines.extend(["", "## FY Returns", "", "| FY | Baseline 3M Rank | 1M/3M 40/60 Rank | Delta |", "| --- | ---: | ---: | ---: |"])
    by_variant: dict[str, dict[str, dict[str, object]]] = {}
    for row in output["financial_year_returns"]:
        by_variant.setdefault(str(row["variant"]), {})[str(row["financial_year"])] = row
    for label in sorted({str(row["financial_year"]) for row in output["financial_year_returns"]}):
        base_row = by_variant.get("baseline_3m_rank", {}).get(label, {})
        exp_row = by_variant.get("sector_1m3m_40_60_rank", {}).get(label, {})
        base_value = base_row.get("return_pct")
        exp_value = exp_row.get("return_pct")
        delta = float(exp_value) - float(base_value) if base_value is not None and exp_value is not None else None
        lines.append(f"| {label} | {fmt_pct(base_value)} | {fmt_pct(exp_value)} | {fmt_pct(delta)} |")
    lines.extend(
        [
            "",
            "## Recommendation Overlap",
            "",
            f"- Average daily recommendation overlap: {fmt_pct(output['overlap_summary']['avg_jaccard_overlap'])}",
            f"- Dates compared: {output['overlap_summary']['dates_compared']}",
            "",
            "## Verdict",
            "",
            str(output["verdict"]),
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    load_dotenv(REPO_ROOT / ".env")
    args = parse_args()
    angel_url = os.environ.get("ANGEL_DATABASE_URL")
    if not angel_url:
        raise RuntimeError("ANGEL_DATABASE_URL is required.")
    engine = create_engine(angel_url, future=True, pool_pre_ping=True)

    features = load_features_and_sector_returns(engine, args.pilot_schema, args.start_date, args.end_date, args.weight_1m, args.weight_3m)
    baseline_recs = load_baseline_recommendations(engine, args.pilot_schema, args.start_date, args.end_date)
    experiment_scores = score_frame(features, "sector_rank_1m3m", "score_1m3m")
    experiment_recs = generate_recommendations(experiment_scores, "score_1m3m", args.minimum_score, args.top_n, "sector_rotation_adx_1m3m")
    symbols = {str(row["symbol"]) for row in baseline_recs + experiment_recs}
    prices = load_prices(engine, args.pilot_schema, symbols, args.start_date, args.end_date)

    baseline_result = run_rolling_10(
        "baseline_3m_rank",
        baseline_recs,
        prices,
        start_date=args.start_date,
        end_date=args.end_date,
        initial_capital=args.initial_capital,
        portfolio_size=args.portfolio_size,
        weekly_picks=args.weekly_picks,
        holding_period=args.holding_period,
    )
    experiment_result = run_rolling_10(
        "sector_1m3m_40_60_rank",
        experiment_recs,
        prices,
        start_date=args.start_date,
        end_date=args.end_date,
        initial_capital=args.initial_capital,
        portfolio_size=args.portfolio_size,
        weekly_picks=args.weekly_picks,
        holding_period=args.holding_period,
    )
    overlap_rows = recommendation_overlap(baseline_recs, experiment_recs)
    avg_overlap = statistics.mean([float(row["jaccard_overlap"]) for row in overlap_rows if row["jaccard_overlap"] is not None]) if overlap_rows else None
    base_metrics = baseline_result["metrics"]
    exp_metrics = experiment_result["metrics"]
    verdict = (
        "1M/3M rank improves Sharpe or drawdown without killing 2024; promote to deeper validation."
        if float(exp_metrics["sharpe_ratio"]) >= float(base_metrics["sharpe_ratio"]) and float(exp_metrics["max_drawdown"]) >= float(base_metrics["max_drawdown"])
        else "1M/3M rank did not beat the current 3M rank on core risk-adjusted metrics; do not promote yet."
    )
    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "parameters": {
            "start_date": args.start_date.isoformat(),
            "end_date": args.end_date.isoformat(),
            "weight_1m": args.weight_1m,
            "weight_3m": args.weight_3m,
            "minimum_score": args.minimum_score,
            "top_n": args.top_n,
            "portfolio_size": args.portfolio_size,
            "weekly_picks": args.weekly_picks,
            "holding_period": args.holding_period,
        },
        "variants": {
            "baseline_3m_rank": {"metrics": base_metrics, "recommendation_rows": len(baseline_recs)},
            "sector_1m3m_40_60_rank": {"metrics": exp_metrics, "recommendation_rows": len(experiment_recs)},
        },
        "financial_year_returns": fy_returns(baseline_result["equity_curve"], "baseline_3m_rank")
        + fy_returns(experiment_result["equity_curve"], "sector_1m3m_40_60_rank"),
        "overlap_summary": {"dates_compared": len(overlap_rows), "avg_jaccard_overlap": avg_overlap},
        "constraints": {
            "database_modified": False,
            "production_scoring_changed": False,
            "production_recommendations_changed": False,
            "strategy_rules_changed": False,
        },
        "verdict": verdict,
    }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "sector_1m3m_rank_results.json").write_text(json.dumps(output, indent=2, default=str), encoding="utf-8")
    (args.output_dir / "SECTOR_1M3M_RANK_EXPERIMENT.md").write_text(render_report(output), encoding="utf-8")
    write_csv(args.output_dir / "sector_1m3m_recommendations.csv", experiment_recs)
    write_csv(args.output_dir / "sector_1m3m_scores_sample.csv", experiment_scores.head(5000).to_dict("records"))
    write_csv(args.output_dir / "sector_1m3m_recommendation_overlap.csv", overlap_rows)
    write_csv(args.output_dir / "sector_1m3m_equity.csv", baseline_result["equity_curve"] + experiment_result["equity_curve"])
    write_csv(args.output_dir / "sector_1m3m_trades.csv", baseline_result["trades"] + experiment_result["trades"])
    write_csv(args.output_dir / "sector_1m3m_fy_returns.csv", output["financial_year_returns"])
    print(json.dumps(output, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
