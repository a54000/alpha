#!/usr/bin/env python3
"""Research-only relative-strength improvement + 60-minute RSI experiment.

Signal definition:
  - 66-session stock return minus Nifty 50 66-session return.
  - Relative strength is improving when the spread is higher than 5 sessions ago
    and also higher than the previous session.
  - 60-minute RSI14, computed from Angel 15-minute candles, must be below 60.

Portfolio construction:
  - Rank candidates by 5-session relative-strength improvement.
  - Enter the top weekly candidates at the next session's 10:30 open.
  - Rolling 10 portfolio, 20 trading-day planned exit.

This is analysis-only. It does not write to databases or change production
strategy, recommendations, or paper-trading state.
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
from datetime import date, datetime, time, timezone
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

OUTPUT_DIR = REPO_ROOT / "results" / "rs_rsi60_experiment"
DOC_PATH = REPO_ROOT / "docs" / "RS_RSI60_EXPERIMENT.md"


@dataclass(frozen=True)
class Config:
    start_date: date
    end_date: date
    initial_capital: float
    pilot_schema: str
    portfolio_size: int
    weekly_picks: int
    holding_period: int
    rs_lookback: int
    rs_improvement_lookback: int
    rsi_threshold: float
    entry_time: time
    min_rs_spread: float | None = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run RS improvement + 60-minute RSI research experiment.")
    parser.add_argument("--start-date", type=date.fromisoformat, default=date(2022, 5, 25))
    parser.add_argument("--end-date", type=date.fromisoformat, default=date(2026, 6, 11))
    parser.add_argument("--initial-capital", type=float, default=1_000_000.0)
    parser.add_argument("--pilot-schema", default="pilot_phase2a")
    parser.add_argument("--portfolio-size", type=int, default=10)
    parser.add_argument("--weekly-picks", type=int, default=5)
    parser.add_argument("--holding-period", type=int, default=20)
    parser.add_argument("--rs-lookback", type=int, default=66)
    parser.add_argument("--rs-improvement-lookback", type=int, default=5)
    parser.add_argument("--rsi-threshold", type=float, default=60.0)
    parser.add_argument("--entry-time", type=time.fromisoformat, default=time(10, 30))
    parser.add_argument("--min-rs-spread", type=float, default=None)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    parser.add_argument("--doc-path", type=Path, default=DOC_PATH)
    return parser.parse_args()


def make_engine_from_env() -> object:
    load_dotenv(REPO_ROOT / ".env")
    url = os.environ.get("ANGEL_DATABASE_URL")
    if not url:
        raise RuntimeError("ANGEL_DATABASE_URL is required.")
    return create_engine(url, future=True, pool_pre_ping=True, pool_size=1, max_overflow=0)


def load_daily_prices(engine, schema: str, start_date: date, end_date: date) -> pd.DataFrame:
    query = text(
        f"""
        SELECT symbol, date, open, high, low, close
        FROM {schema}.daily_bars_clean
        WHERE date BETWEEN :start_date - INTERVAL '140 days' AND :end_date
        ORDER BY symbol, date
        """
    )
    frame = pd.read_sql_query(query, engine, params={"start_date": start_date, "end_date": end_date})
    frame["date"] = pd.to_datetime(frame["date"]).dt.date
    for column in ["open", "high", "low", "close"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame.dropna(subset=["symbol", "date", "close"])


def load_nifty50_daily(engine, start_date: date, end_date: date) -> pd.DataFrame:
    query = text(
        """
        SELECT datetime::date AS date, close
        FROM ohlcv_15min
        WHERE symbol = 'NIFTY50'
          AND datetime::date BETWEEN :start_date - INTERVAL '140 days' AND :end_date
          AND datetime::time <= '15:15:00'
        ORDER BY datetime
        """
    )
    frame = pd.read_sql_query(query, engine, params={"start_date": start_date, "end_date": end_date})
    frame["date"] = pd.to_datetime(frame["date"]).dt.date
    frame["close"] = pd.to_numeric(frame["close"], errors="coerce")
    return frame.dropna().groupby("date", as_index=False).tail(1)[["date", "close"]].rename(columns={"close": "nifty_close"})


def load_entry_prices(engine, symbols: set[str], start_date: date, end_date: date, entry_time: time) -> dict[tuple[str, date], float]:
    query = text(
        """
        SELECT symbol, datetime::date AS date, open
        FROM ohlcv_15min
        WHERE symbol = ANY(:symbols)
          AND datetime::date BETWEEN :start_date AND :end_date
          AND datetime::time = :entry_time
        """
    )
    rows = pd.read_sql_query(
        query,
        engine,
        params={"symbols": list(symbols), "start_date": start_date, "end_date": end_date, "entry_time": entry_time},
    )
    if rows.empty:
        return {}
    rows["date"] = pd.to_datetime(rows["date"]).dt.date
    return {(str(row.symbol), row.date): float(row.open) for row in rows.itertuples(index=False)}


def load_rsi60(engine, symbols: set[str], start_date: date, end_date: date) -> dict[tuple[str, date], float]:
    query = text(
        """
        SELECT symbol, datetime, close
        FROM ohlcv_15min
        WHERE symbol = ANY(:symbols)
          AND datetime::date BETWEEN :start_date - INTERVAL '45 days' AND :end_date
          AND datetime::time >= '09:15:00'
          AND datetime::time <= '15:15:00'
        ORDER BY symbol, datetime
        """
    )
    frame = pd.read_sql_query(query, engine, params={"symbols": list(symbols), "start_date": start_date, "end_date": end_date})
    if frame.empty:
        return {}
    frame["datetime"] = pd.to_datetime(frame["datetime"])
    frame["date"] = frame["datetime"].dt.date
    minutes = (frame["datetime"].dt.hour * 60 + frame["datetime"].dt.minute) - (9 * 60 + 15)
    frame["bucket"] = (minutes // 60).clip(lower=0)
    hourly = frame.sort_values("datetime").groupby(["symbol", "date", "bucket"], as_index=False).tail(1)
    hourly = hourly.sort_values(["symbol", "datetime"]).copy()
    hourly["close"] = pd.to_numeric(hourly["close"], errors="coerce")
    delta = hourly.groupby("symbol")["close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.groupby(hourly["symbol"]).transform(lambda series: series.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean())
    avg_loss = loss.groupby(hourly["symbol"]).transform(lambda series: series.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean())
    rs = avg_gain / avg_loss.replace(0, pd.NA)
    hourly["rsi_60m_14"] = 100 - (100 / (1 + rs))
    hourly.loc[(avg_loss == 0) & (avg_gain > 0), "rsi_60m_14"] = 100
    hourly.loc[(avg_loss == 0) & (avg_gain == 0), "rsi_60m_14"] = 50
    daily = hourly.dropna(subset=["rsi_60m_14"]).groupby(["symbol", "date"], as_index=False).tail(1)
    return {(str(row.symbol), row.date): float(row.rsi_60m_14) for row in daily.itertuples(index=False)}


def build_price_dict(frame: pd.DataFrame, start_date: date, end_date: date) -> dict[str, dict[date, dict[str, float]]]:
    frame = frame[(frame["date"] >= start_date) & (frame["date"] <= end_date)].copy()
    prices: dict[str, dict[date, dict[str, float]]] = {}
    for row in frame.itertuples(index=False):
        prices.setdefault(str(row.symbol), {})[row.date] = {
            "open": float(row.open),
            "high": float(row.high),
            "low": float(row.low),
            "close": float(row.close),
        }
    return prices


def all_trading_dates(prices: dict[str, dict[date, dict[str, float]]]) -> list[date]:
    return sorted({day for values in prices.values() for day in values})


def build_signals(daily: pd.DataFrame, nifty: pd.DataFrame, rsi60: dict[tuple[str, date], float], cfg: Config) -> list[dict[str, object]]:
    nifty = nifty.sort_values("date").copy()
    nifty_return_col = f"nifty_return_{cfg.rs_lookback}d"
    stock_return_col = f"stock_return_{cfg.rs_lookback}d"
    rs_spread_col = f"rs_spread_{cfg.rs_lookback}d"
    rs_prev_col = f"{rs_spread_col}_prev"
    rs_ago_col = f"{rs_spread_col}_{cfg.rs_improvement_lookback}d_ago"
    rs_improvement_col = f"rs_improvement_{cfg.rs_improvement_lookback}d"
    nifty[nifty_return_col] = nifty["nifty_close"].pct_change(cfg.rs_lookback)
    frame = daily.merge(nifty[["date", nifty_return_col]], on="date", how="left")
    frame = frame.sort_values(["symbol", "date"]).copy()
    frame[stock_return_col] = frame.groupby("symbol")["close"].pct_change(cfg.rs_lookback)
    frame[rs_spread_col] = frame[stock_return_col] - frame[nifty_return_col]
    frame[rs_prev_col] = frame.groupby("symbol")[rs_spread_col].shift(1)
    frame[rs_ago_col] = frame.groupby("symbol")[rs_spread_col].shift(cfg.rs_improvement_lookback)
    frame[rs_improvement_col] = frame[rs_spread_col] - frame[rs_ago_col]
    frame["rsi_60m_14"] = [rsi60.get((str(row.symbol), row.date)) for row in frame.itertuples(index=False)]
    eligible = frame[
        (frame["date"] >= cfg.start_date)
        & (frame["date"] <= cfg.end_date)
        & (frame[rs_spread_col] > frame[rs_prev_col])
        & (frame[rs_improvement_col] > 0)
        & (frame["rsi_60m_14"] < cfg.rsi_threshold)
    ].copy()
    if cfg.min_rs_spread is not None:
        eligible = eligible[eligible[rs_spread_col] >= cfg.min_rs_spread].copy()
    eligible = eligible.dropna(subset=[rs_spread_col, rs_improvement_col, "rsi_60m_14"])
    signals: list[dict[str, object]] = []
    for signal_date, group in eligible.groupby("date"):
        ranked = group.sort_values([rs_improvement_col, rs_spread_col, "symbol"], ascending=[False, False, True])
        for rank, row in enumerate(ranked.itertuples(index=False), start=1):
            signals.append(
                {
                    "date": signal_date,
                    "rank": rank,
                    "symbol": str(row.symbol),
                    "score": float(getattr(row, rs_improvement_col)),
                    "sector": None,
                    "stock_return": float(getattr(row, stock_return_col)),
                    "nifty_return": float(getattr(row, nifty_return_col)),
                    "rs_spread": float(getattr(row, rs_spread_col)),
                    "rs_improvement": float(getattr(row, rs_improvement_col)),
                    "rsi_60m_14": float(row.rsi_60m_14),
                }
            )
    return signals


def returns_from_equity(curve: list[dict[str, object]]) -> list[float]:
    out: list[float] = []
    previous: float | None = None
    for row in curve:
        equity = float(row["equity"])
        if previous and previous > 0:
            out.append(equity / previous - 1.0)
        previous = equity
    return out


def max_drawdown(values: list[float]) -> float:
    peak = values[0] if values else 0.0
    drawdown = 0.0
    for value in values:
        peak = max(peak, value)
        if peak:
            drawdown = min(drawdown, value / peak - 1.0)
    return drawdown


def metrics(initial_capital: float, curve: list[dict[str, object]], trades: list[dict[str, object]], turnover: float) -> dict[str, object]:
    values = [float(row["equity"]) for row in curve]
    returns = returns_from_equity(curve)
    downside = [value for value in returns if value < 0]
    gross_profit = sum(float(row["net_pnl"]) for row in trades if float(row["net_pnl"]) > 0)
    gross_loss = abs(sum(float(row["net_pnl"]) for row in trades if float(row["net_pnl"]) < 0))
    stdev = statistics.stdev(returns) if len(returns) > 1 else 0.0
    downside_stdev = statistics.stdev(downside) if len(downside) > 1 else 0.0
    ending = values[-1] if values else initial_capital
    return {
        "ending_equity": ending,
        "total_return": ending / initial_capital - 1.0,
        "cagr": (ending / initial_capital) ** (252 / max(1, len(curve))) - 1.0 if ending > 0 else -1.0,
        "max_drawdown": max_drawdown(values),
        "sharpe_ratio": statistics.mean(returns) / stdev * math.sqrt(252) if stdev else 0.0,
        "sortino_ratio": statistics.mean(returns) / downside_stdev * math.sqrt(252) if downside_stdev else 0.0,
        "profit_factor": gross_profit / gross_loss if gross_loss else None,
        "win_rate": sum(1 for row in trades if float(row["net_pnl"]) > 0) / len(trades) if trades else 0.0,
        "closed_trades": len(trades),
        "turnover": turnover / initial_capital,
        "avg_cash_pct": statistics.mean([float(row["cash"]) / float(row["equity"]) for row in curve if float(row["equity"])]) if curve else 0.0,
        "avg_position_count": statistics.mean([int(row["position_count"]) for row in curve]) if curve else 0.0,
    }


def fy_label(day: date) -> str:
    start_year = day.year if day.month >= 4 else day.year - 1
    return f"FY{start_year}-{str(start_year + 1)[-2:]}"


def fy_returns(curve: list[dict[str, object]]) -> list[dict[str, object]]:
    groups: dict[str, list[dict[str, object]]] = {}
    for row in curve:
        groups.setdefault(fy_label(date.fromisoformat(str(row["date"]))), []).append(row)
    out: list[dict[str, object]] = []
    for label, group in sorted(groups.items()):
        group.sort(key=lambda item: str(item["date"]))
        start = float(group[0]["equity"])
        end = float(group[-1]["equity"])
        out.append(
            {
                "financial_year": label,
                "start_date": group[0]["date"],
                "end_date": group[-1]["date"],
                "start_equity": start,
                "end_equity": end,
                "return_pct": end / start - 1.0 if start else None,
                "max_drawdown": max_drawdown([float(row["equity"]) for row in group]),
            }
        )
    return out


def run_backtest(
    signals: list[dict[str, object]],
    prices: dict[str, dict[date, dict[str, float]]],
    entry_prices: dict[tuple[str, date], float],
    cfg: Config,
) -> dict[str, object]:
    dates = [day for day in all_trading_dates(prices) if cfg.start_date <= day <= cfg.end_date]
    signals_by_date: dict[date, list[dict[str, object]]] = {}
    for row in signals:
        signals_by_date.setdefault(row["date"], []).append(row)
    for rows in signals_by_date.values():
        rows.sort(key=lambda item: (int(item["rank"]), str(item["symbol"])))
    entries_by_date: dict[date, tuple[date, list[dict[str, object]]]] = {}
    for signal_date in weekly_signal_dates(list(signals_by_date)):
        entry_date = next_trading_day_after(dates, signal_date)
        if entry_date:
            entries_by_date[entry_date] = (signal_date, signals_by_date[signal_date][: cfg.weekly_picks])

    cash = cfg.initial_capital
    positions: list[AnalysisPosition] = []
    trades: list[dict[str, object]] = []
    curve: list[dict[str, object]] = []
    entry_log: list[dict[str, object]] = []
    turnover = 0.0
    trade_id = 1

    for current_date in dates:
        remaining: list[AnalysisPosition] = []
        closed_today: set[str] = set()
        for position in positions:
            close_price = prices.get(position.symbol, {}).get(current_date, {}).get("close")
            if current_date >= position.planned_exit_date and close_price is not None:
                row = build_trade_row(trade_id, position, current_date, close_price, symbol_dates(prices, position.symbol), "rs66_rsi60")
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
            target_value = equity_at_open / cfg.portfolio_size
            for rec in candidates:
                symbol = str(rec["symbol"])
                base = {
                    "signal_date": signal_date.isoformat(),
                    "entry_date": current_date.isoformat(),
                    "symbol": symbol,
                    "rank": int(rec["rank"]),
                    "rs_spread": rec["rs_spread"],
                    "rs_improvement": rec["rs_improvement"],
                    "rsi_60m_14": rec["rsi_60m_14"],
                }
                if len(positions) >= cfg.portfolio_size:
                    entry_log.append({**base, "status": "skipped", "reason": "portfolio_full"})
                    continue
                if symbol in held or symbol in closed_today:
                    entry_log.append({**base, "status": "skipped", "reason": "already_held_or_closed_today"})
                    continue
                entry_price = entry_prices.get((symbol, current_date))
                if entry_price is None or entry_price <= 0:
                    entry_log.append({**base, "status": "skipped", "reason": "missing_1030_entry_price"})
                    continue
                allocation = min(target_value, cash)
                if allocation <= 0:
                    entry_log.append({**base, "status": "skipped", "reason": "insufficient_cash"})
                    continue
                buy_charges = buy_side_charges(allocation)
                if allocation + total_charges(buy_charges) > cash:
                    allocation = cash / (1.0 + (total_charges(buy_charges) / allocation if allocation else 0.0))
                    buy_charges = buy_side_charges(allocation)
                planned_exit = nth_trading_day_after(symbol_dates(prices, symbol), current_date, cfg.holding_period)
                if planned_exit is None:
                    entry_log.append({**base, "status": "skipped", "reason": "missing_planned_exit"})
                    continue
                quantity = allocation / entry_price
                cash -= allocation + total_charges(buy_charges)
                turnover += allocation
                positions.append(
                    AnalysisPosition(
                        symbol=symbol,
                        sector=None,
                        signal_date=signal_date,
                        entry_date=current_date,
                        entry_price=entry_price,
                        quantity=quantity,
                        planned_exit_date=planned_exit,
                        rank=int(rec["rank"]),
                        score=float(rec["score"]),
                        entry_value=allocation,
                        buy_charges=buy_charges,
                    )
                )
                held.add(symbol)
                entry_log.append({**base, "status": "entered", "reason": "entered", "entry_price": entry_price, "planned_exit_date": planned_exit.isoformat()})

        equity = cash + positions_value(positions, prices, current_date, "close")
        curve.append({"date": current_date.isoformat(), "equity": equity, "cash": cash, "position_count": len(positions)})

    return {
        "metrics": metrics(cfg.initial_capital, curve, trades, turnover),
        "equity_curve": curve,
        "trades": trades,
        "entry_log": entry_log,
        "fy_returns": fy_returns(curve),
    }


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def pct(value: object) -> str:
    if value is None:
        return "n/a"
    return f"{float(value) * 100:.2f}%"


def render_doc(payload: dict[str, object]) -> str:
    metrics_row = payload["metrics"]
    params = payload["parameters"]
    artifacts = payload["artifacts"]
    lines = [
        "# Relative Strength + 60-Minute RSI Experiment",
        "",
        "Research-only test. No production strategy, recommendation, paper-trading, or database state was changed.",
        "",
        "## Setup",
        "",
        f"- Signal: {params['rs_lookback']}-session stock return minus Nifty 50 {params['rs_lookback']}-session return.",
        f"- Improvement: relative-strength spread higher than {params['rs_improvement_lookback']} sessions ago and higher than the prior session.",
        f"- Entry filter: 60-minute RSI14 below {params['rsi_threshold']:.0f} on the signal day.",
        f"- Minimum relative-strength spread: {params.get('min_rs_spread', 'none')}.",
        "- Construction: Rolling 10, top 5 weekly candidates, 10:30 next-session entry, 20 trading-day planned exit.",
        "",
        "## Results",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
        f"| CAGR | {pct(metrics_row['cagr'])} |",
        f"| Total return | {pct(metrics_row['total_return'])} |",
        f"| Max drawdown | {pct(metrics_row['max_drawdown'])} |",
        f"| Sharpe | {float(metrics_row['sharpe_ratio']):.2f} |",
        f"| Sortino | {float(metrics_row['sortino_ratio']):.2f} |",
        f"| Profit factor | {float(metrics_row['profit_factor']):.2f} |" if metrics_row["profit_factor"] is not None else "| Profit factor | n/a |",
        f"| Win rate | {pct(metrics_row['win_rate'])} |",
        f"| Closed trades | {metrics_row['closed_trades']} |",
        f"| Average cash | {pct(metrics_row['avg_cash_pct'])} |",
        "",
        "## Financial-Year Returns",
        "",
        "| FY | Return | Max DD |",
        "| --- | ---: | ---: |",
    ]
    for row in payload["fy_returns"]:
        lines.append(f"| {row['financial_year']} | {pct(row['return_pct'])} | {pct(row['max_drawdown'])} |")
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "This experiment tests whether stock-level relative-strength acceleration plus a non-overheated intraday RSI filter can stand on its own.",
            "It should be compared with SectorEdge 10 before considering any promotion.",
            "",
            "## Artifacts",
            "",
            f"- `{artifacts['signals_csv']}`",
            f"- `{artifacts['trades_csv']}`",
            f"- `{artifacts['equity_curve_csv']}`",
            f"- `{artifacts['financial_year_returns_csv']}`",
            f"- `{artifacts['entry_log_csv']}`",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    cfg = Config(
        start_date=args.start_date,
        end_date=args.end_date,
        initial_capital=args.initial_capital,
        pilot_schema=args.pilot_schema,
        portfolio_size=args.portfolio_size,
        weekly_picks=args.weekly_picks,
        holding_period=args.holding_period,
        rs_lookback=args.rs_lookback,
        rs_improvement_lookback=args.rs_improvement_lookback,
        rsi_threshold=args.rsi_threshold,
        entry_time=args.entry_time,
        min_rs_spread=args.min_rs_spread,
    )
    engine = make_engine_from_env()
    daily = load_daily_prices(engine, cfg.pilot_schema, cfg.start_date, cfg.end_date)
    symbols = set(map(str, daily["symbol"].unique()))
    nifty = load_nifty50_daily(engine, cfg.start_date, cfg.end_date)
    rsi60 = load_rsi60(engine, symbols, cfg.start_date, cfg.end_date)
    signals = build_signals(daily, nifty, rsi60, cfg)
    prices = build_price_dict(daily, cfg.start_date, cfg.end_date)
    entry_prices = load_entry_prices(engine, symbols, cfg.start_date, cfg.end_date, cfg.entry_time)
    result = run_backtest(signals, prices, entry_prices, cfg)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    signal_rows = [{**row, "date": row["date"].isoformat()} for row in signals]
    write_csv(args.output_dir / "signals.csv", signal_rows)
    write_csv(args.output_dir / "trades.csv", result["trades"])
    write_csv(args.output_dir / "equity_curve.csv", result["equity_curve"])
    write_csv(args.output_dir / "financial_year_returns.csv", result["fy_returns"])
    write_csv(args.output_dir / "entry_log.csv", result["entry_log"])
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "parameters": {
            "start_date": cfg.start_date.isoformat(),
            "end_date": cfg.end_date.isoformat(),
            "portfolio_size": cfg.portfolio_size,
            "weekly_picks": cfg.weekly_picks,
            "holding_period": cfg.holding_period,
            "rs_lookback": cfg.rs_lookback,
            "rs_improvement_lookback": cfg.rs_improvement_lookback,
            "rsi_threshold": cfg.rsi_threshold,
            "entry_time": cfg.entry_time.isoformat(),
            "min_rs_spread": cfg.min_rs_spread,
        },
        "signal_count": len(signals),
        "metrics": result["metrics"],
        "fy_returns": result["fy_returns"],
        "artifacts": {
            "signals_csv": str(args.output_dir / "signals.csv"),
            "trades_csv": str(args.output_dir / "trades.csv"),
            "equity_curve_csv": str(args.output_dir / "equity_curve.csv"),
            "financial_year_returns_csv": str(args.output_dir / "financial_year_returns.csv"),
            "entry_log_csv": str(args.output_dir / "entry_log.csv"),
            "doc": str(args.doc_path),
        },
    }
    (args.output_dir / "summary.json").write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    args.doc_path.parent.mkdir(parents=True, exist_ok=True)
    args.doc_path.write_text(render_doc(payload), encoding="utf-8")
    print(json.dumps({"status": "success", "signals": len(signals), "trades": result["metrics"]["closed_trades"], "cagr": result["metrics"]["cagr"], "doc": str(args.doc_path)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
