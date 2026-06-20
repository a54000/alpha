#!/usr/bin/env python3
"""Read-only entry/VWAP bisection for Sector Rotation ADX Rolling 10.

Runs the current reconstruction lifecycle while toggling:

- entry price source: daily open vs 10:30 candle open
- previous-day VWAP extension filter: off vs 2.5%

Also audits liquidity for the universe-expansion added-symbol trades.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import replace
from datetime import date
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import text


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.api.trade_analysis_service import (  # noqa: E402
    AnalysisPosition,
    STRATEGIES,
    StrategyConfig,
    TradeAnalysisRequest,
    TradeAnalysisService,
    all_trading_dates,
    build_open_position_row,
    build_trade_row,
    buy_side_charges,
    financial_year_returns,
    next_trading_day_after,
    nth_trading_day_after,
    passes_sector_cap,
    positions_value,
    summarize_equity,
    summarize_trades,
    symbol_dates,
    total_charges,
    weekly_signal_dates,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit entry/VWAP sensitivity for current engine.")
    parser.add_argument("--initial-capital", type=float, default=1_000_000)
    parser.add_argument("--pilot-schema", default="pilot_phase2a")
    parser.add_argument("--expanded-universe-csv", default="reports/nifty500_expansion_universe_symbols.csv")
    parser.add_argument("--original-alias-csv", default="reports/phase1b_alias_proposals.csv")
    parser.add_argument("--output-dir", default="reports/entry_vwap_bisection")
    return parser.parse_args()


def load_expanded_ready_symbols(path: Path) -> set[str]:
    frame = pd.read_csv(path)
    if "reason" in frame.columns:
        frame = frame[frame["reason"].astype(str) == "usable"]
    return {str(symbol).strip().upper() for symbol in frame["symbol"].dropna() if str(symbol).strip()}


def load_original_exact_symbols(path: Path) -> set[str]:
    frame = pd.read_csv(path)
    exact = frame[
        (frame["source"].astype(str) == "research")
        & (frame["alias_reason"].astype(str) == "exact")
        & (frame["confidence"].astype(str) == "high")
        & (frame["review_status"].astype(str) == "approved")
    ]
    return {str(symbol).strip().upper() for symbol in exact["symbol"].dropna() if str(symbol).strip()}


def reconstruct_with_config(
    request: TradeAnalysisRequest,
    config: StrategyConfig,
    recommendations: list[dict[str, object]],
    prices: dict[str, dict[date, dict[str, float]]],
) -> dict[str, object]:
    dates = [item for item in all_trading_dates(prices) if request.start_date <= item <= request.end_date]
    if not recommendations or not dates:
        return {"summary": {}, "trades": [], "open_positions": [], "equity_curve": []}

    recs_by_date: dict[date, list[dict[str, object]]] = {}
    for row in recommendations:
        recs_by_date.setdefault(row["date"], []).append(row)
    for rows in recs_by_date.values():
        rows.sort(key=lambda row: (int(row["rank"]), str(row["symbol"])))

    entries_by_date: dict[date, list[dict[str, object]]] = {}
    for signal_date in weekly_signal_dates(list(recs_by_date)):
        entry_date = next_trading_day_after(dates, signal_date)
        if entry_date is not None:
            entries_by_date[entry_date] = recs_by_date[signal_date]

    cash = float(request.initial_capital)
    positions: list[AnalysisPosition] = []
    trades: list[dict[str, object]] = []
    open_positions: list[dict[str, object]] = []
    equity_curve: list[dict[str, object]] = []
    trade_id = 1

    for current_date in dates:
        remaining: list[AnalysisPosition] = []
        closed_today: set[str] = set()
        for position in positions:
            close_price = prices.get(position.symbol, {}).get(current_date, {}).get("close")
            if position.planned_exit_date is not None and current_date >= position.planned_exit_date and close_price is not None:
                row = build_trade_row(trade_id, position, current_date, close_price, symbol_dates(prices, position.symbol), request.strategy)
                cash += float(row["exit_value"]) - (float(row["charges"]) - total_charges(position.buy_charges))
                trades.append(row)
                closed_today.add(position.symbol)
                trade_id += 1
            else:
                remaining.append(position)
        positions = remaining

        if current_date in entries_by_date and len(positions) < config.portfolio_size:
            held = {position.symbol for position in positions}
            equity_at_open = cash + positions_value(positions, prices, current_date, "open")
            target_value = equity_at_open / float(config.portfolio_size)
            max_rank = config.max_candidate_rank or config.portfolio_size
            candidates = [
                row
                for row in entries_by_date[current_date]
                if int(row["rank"]) <= max_rank and str(row["symbol"]) not in held and str(row["symbol"]) not in closed_today
            ]
            for rec in candidates:
                if len(positions) >= config.portfolio_size:
                    break
                symbol = str(rec["symbol"])
                sector = rec.get("sector")
                if not passes_sector_cap(sector, positions, config):
                    continue
                price_row = prices.get(symbol, {}).get(current_date, {})
                entry_price = price_row.get(config.entry_price_field)
                if entry_price is None or entry_price <= 0:
                    continue
                previous_day_vwap = rec.get("previous_day_vwap")
                if (
                    config.previous_day_vwap_max_extension is not None
                    and previous_day_vwap is not None
                    and float(previous_day_vwap) > 0
                    and (float(entry_price) / float(previous_day_vwap) - 1.0) > config.previous_day_vwap_max_extension
                ):
                    continue
                allocation = min(target_value, cash)
                if allocation <= 0:
                    break
                buy_charges = buy_side_charges(allocation)
                if allocation + total_charges(buy_charges) > cash:
                    allocation = cash / (1.0 + (total_charges(buy_charges) / allocation if allocation else 0.0))
                    buy_charges = buy_side_charges(allocation)
                planned_exit = nth_trading_day_after(symbol_dates(prices, symbol), current_date, config.holding_period)
                quantity = allocation / entry_price
                cash -= allocation + total_charges(buy_charges)
                positions.append(
                    AnalysisPosition(
                        symbol=symbol,
                        sector=str(sector) if sector is not None else None,
                        signal_date=rec["date"],
                        entry_date=current_date,
                        entry_price=entry_price,
                        quantity=quantity,
                        planned_exit_date=planned_exit,
                        rank=int(rec["rank"]),
                        score=float(rec["score"]) if rec.get("score") is not None else None,
                        entry_value=allocation,
                        buy_charges=buy_charges,
                    )
                )
                held.add(symbol)

        equity = cash + positions_value(positions, prices, current_date, "close")
        equity_curve.append({"date": current_date.isoformat(), "equity": equity, "cash": cash, "position_count": len(positions)})

    if dates:
        final_date = dates[-1]
        for position_id, position in enumerate(positions, start=1):
            close_price = prices.get(position.symbol, {}).get(final_date, {}).get("close")
            if close_price is None:
                continue
            open_positions.append(build_open_position_row(position_id, position, final_date, close_price, symbol_dates(prices, position.symbol), request.strategy))

    trade_summary = summarize_trades(trades)
    equity_summary = summarize_equity(equity_curve, request.initial_capital)
    summary = {
        "start_date": request.start_date.isoformat(),
        "end_date": request.end_date.isoformat(),
        "strategy": request.strategy,
        "entry_price_field": config.entry_price_field,
        "vwap_extension_limit": config.previous_day_vwap_max_extension,
        "ending_value": equity_summary["ending_value"],
        "total_return": equity_summary["total_return"],
        "cagr": equity_summary["cagr"],
        "max_drawdown": equity_summary["max_drawdown"],
        **trade_summary,
        "open_positions": len(open_positions),
        "open_unrealized_pnl": sum(float(row["unrealized_pnl"]) for row in open_positions),
    }
    summary["financial_year_returns"] = financial_year_returns(equity_curve, trades)
    return {"summary": summary, "trades": trades, "open_positions": open_positions, "equity_curve": equity_curve}


def load_case_inputs(
    service: TradeAnalysisService,
    request: TradeAnalysisRequest,
    allowed_symbols: set[str],
) -> tuple[list[dict[str, object]], dict[str, dict[date, dict[str, float]]]]:
    recommendations = service._load_recommendations(request)
    recommendations = [row for row in recommendations if str(row["symbol"]).upper() in allowed_symbols]
    service._attach_signal_day_vwaps(request, recommendations)
    symbols = {str(row["symbol"]) for row in recommendations}
    prices = service._load_prices(request, symbols)
    service._attach_1030_entries(request, symbols, prices)
    return recommendations, prices


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False)


def summarize_case(period: str, case_name: str, result: dict[str, object]) -> dict[str, object]:
    summary = result["summary"]
    return {
        "period": period,
        "case": case_name,
        "entry_price_field": summary.get("entry_price_field"),
        "vwap_extension_limit": summary.get("vwap_extension_limit"),
        "ending_value": summary.get("ending_value"),
        "total_return": summary.get("total_return"),
        "cagr": summary.get("cagr"),
        "max_drawdown": summary.get("max_drawdown"),
        "closed_trades": summary.get("total_trades"),
        "open_positions": summary.get("open_positions"),
        "win_rate": summary.get("win_rate"),
        "net_pnl": summary.get("net_pnl"),
        "total_charges": summary.get("total_charges"),
    }


def pct(value: object) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    return f"{float(value) * 100:.2f}%"


def money(value: object) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    return f"Rs {float(value):,.0f}"


def add_liquidity_metrics(service: TradeAnalysisService, trades: pd.DataFrame) -> pd.DataFrame:
    if trades.empty:
        return trades
    symbols = sorted({str(symbol) for symbol in trades["symbol"].dropna()})
    start_date = pd.to_datetime(trades["entry_date"]).min().date()
    end_date = pd.to_datetime(trades["entry_date"]).max().date()
    query = text(
        """
        SELECT symbol,
               datetime::date AS date,
               SUM(close * volume) AS traded_value,
               SUM(volume) AS volume
        FROM ohlcv_15min
        WHERE symbol = ANY(:symbols)
          AND datetime::date BETWEEN :start_date AND :end_date
        GROUP BY symbol, datetime::date
        """
    )
    with service.angel_engine.connect() as connection:
        rows = connection.execute(query, {"symbols": symbols, "start_date": start_date, "end_date": end_date}).mappings().all()
    liquidity = {(str(row["symbol"]), row["date"].isoformat()): row for row in rows}
    item = trades.copy()
    item["entry_date"] = pd.to_datetime(item["entry_date"]).dt.date.astype(str)
    item["entry_day_traded_value"] = [
        float(liquidity.get((str(row.symbol), str(row.entry_date)), {}).get("traded_value") or 0.0)
        for row in item.itertuples(index=False)
    ]
    item["position_to_traded_value_pct"] = item.apply(
        lambda row: (float(row["entry_value"]) / row["entry_day_traded_value"]) if row["entry_day_traded_value"] else None,
        axis=1,
    )
    return item


def main() -> int:
    args = parse_args()
    load_dotenv(REPO_ROOT / ".env")
    output_dir = REPO_ROOT / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    expanded_symbols = load_expanded_ready_symbols(REPO_ROOT / args.expanded_universe_csv)
    original_symbols = load_original_exact_symbols(REPO_ROOT / args.original_alias_csv)
    added_symbols = expanded_symbols - original_symbols

    service = TradeAnalysisService(angel_database_url=os.environ.get("ANGEL_DATABASE_URL"), pilot_schema=args.pilot_schema)
    base_config = STRATEGIES["SECTOR_ROTATION_ADX_ROLLING10"]
    configs = {
        "daily_open_no_vwap": replace(base_config, entry_price_field="open", previous_day_vwap_max_extension=None),
        "daily_open_vwap_2p5": replace(base_config, entry_price_field="open", previous_day_vwap_max_extension=0.025),
        "entry_1030_no_vwap": replace(base_config, entry_price_field="entry_1030_open", previous_day_vwap_max_extension=None),
        "entry_1030_vwap_2p5": replace(base_config, entry_price_field="entry_1030_open", previous_day_vwap_max_extension=0.025),
    }
    periods = {
        "FY2024-25": (date(2024, 4, 1), date(2025, 3, 31)),
        "FY2025-26": (date(2025, 4, 1), date(2026, 3, 31)),
    }

    summary_rows: list[dict[str, object]] = []
    report: dict[str, object] = {"status": "success", "periods": {}, "universe": "expanded_ready_386"}
    for period, (start_date, end_date) in periods.items():
        request = TradeAnalysisRequest(
            start_date=start_date,
            end_date=end_date,
            strategy="SECTOR_ROTATION_ADX_ROLLING10",
            recommendation_model="sector_rotation_adx_1m3m",
            initial_capital=args.initial_capital,
        )
        recommendations, prices = load_case_inputs(service, request, expanded_symbols)
        report["periods"][period] = {"recommendation_rows": len(recommendations), "recommendation_symbols": len({str(row["symbol"]) for row in recommendations})}
        for case_name, config in configs.items():
            result = reconstruct_with_config(request, config, recommendations, prices)
            write_csv(output_dir / f"{period}_{case_name}_trades.csv", result["trades"])
            write_csv(output_dir / f"{period}_{case_name}_open_positions.csv", result["open_positions"])
            write_csv(output_dir / f"{period}_{case_name}_equity_curve.csv", result["equity_curve"])
            summary_rows.append(summarize_case(period, case_name, result))

    summary_frame = pd.DataFrame(summary_rows)
    summary_frame.to_csv(output_dir / "entry_vwap_summary.csv", index=False)

    added_path = REPO_ROOT / "reports/universe_expansion_bisection/expanded_added_symbol_trades.csv"
    common_path = REPO_ROOT / "reports/universe_expansion_bisection/expanded_ready_386_trades.csv"
    liquidity_summary: list[dict[str, object]] = []
    if added_path.exists() and common_path.exists():
        added_trades = pd.read_csv(added_path)
        all_trades = pd.read_csv(common_path)
        all_trades["added_symbol"] = all_trades["symbol"].astype(str).str.upper().isin(added_symbols)
        all_liquidity = add_liquidity_metrics(service, all_trades)
        added_liquidity = all_liquidity[all_liquidity["added_symbol"]].copy()
        original_liquidity = all_liquidity[~all_liquidity["added_symbol"]].copy()
        all_liquidity.to_csv(output_dir / "expanded_universe_trade_liquidity.csv", index=False)
        added_liquidity.to_csv(output_dir / "added_symbol_trade_liquidity.csv", index=False)
        for label, frame in [("added_symbols", added_liquidity), ("original_symbols_in_expanded_case", original_liquidity)]:
            liquidity_summary.append(
                {
                    "group": label,
                    "trades": int(len(frame)),
                    "median_entry_day_traded_value": float(frame["entry_day_traded_value"].median()) if not frame.empty else None,
                    "average_entry_day_traded_value": float(frame["entry_day_traded_value"].mean()) if not frame.empty else None,
                    "median_position_to_traded_value_pct": float(frame["position_to_traded_value_pct"].median()) if not frame.empty else None,
                    "max_position_to_traded_value_pct": float(frame["position_to_traded_value_pct"].max()) if not frame.empty else None,
                }
            )
    pd.DataFrame(liquidity_summary).to_csv(output_dir / "liquidity_summary.csv", index=False)

    payload = {
        **report,
        "summary": summary_rows,
        "liquidity_summary": liquidity_summary,
    }
    (output_dir / "summary.json").write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

    lines = [
        "# Entry / VWAP Bisection",
        "",
        "This read-only diagnostic isolates daily-open vs 10:30 entry and VWAP filtering across FY2024-25 and FY2025-26 using the expanded ready universe.",
        "",
        "| Period | Case | Return | CAGR | Max DD | Closed Trades | Win Rate |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in summary_rows:
        lines.append(
            f"| {row['period']} | {row['case']} | {pct(row['total_return'])} | {pct(row['cagr'])} | "
            f"{pct(row['max_drawdown'])} | {row['closed_trades']} | {pct(row['win_rate'])} |"
        )
    lines.extend(["", "## Liquidity Check", ""])
    if liquidity_summary:
        lines.extend(["| Group | Trades | Median Traded Value | Avg Traded Value | Median Position/Value | Max Position/Value |", "| --- | ---: | ---: | ---: | ---: | ---: |"])
        for row in liquidity_summary:
            lines.append(
                f"| {row['group']} | {row['trades']} | {money(row['median_entry_day_traded_value'])} | "
                f"{money(row['average_entry_day_traded_value'])} | {pct(row['median_position_to_traded_value_pct'])} | {pct(row['max_position_to_traded_value_pct'])} |"
            )
    else:
        lines.append("Liquidity inputs were not available.")
    lines.extend(
        [
            "",
            "## Artifacts",
            "",
            "- `entry_vwap_summary.csv`",
            "- `{period}_{case}_trades.csv`",
            "- `{period}_{case}_equity_curve.csv`",
            "- `expanded_universe_trade_liquidity.csv`",
            "- `added_symbol_trade_liquidity.csv`",
            "- `liquidity_summary.csv`",
        ]
    )
    (output_dir / "ENTRY_VWAP_BISECTION.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(payload, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
