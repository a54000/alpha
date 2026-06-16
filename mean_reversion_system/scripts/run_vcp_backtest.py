"""Sprint 2.2 VCP sleeve research backtest."""

from __future__ import annotations

import json
import math
import sys
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from mean_reversion_system.src.backtest.costs import calculate_transaction_costs
from mean_reversion_system.src.data.db_connector import get_engine
from mean_reversion_system.src.strategy.sizing import apply_position_limits, calculate_position_size
from mean_reversion_system.src.strategy.vcp_signals import add_vcp_features, calculate_vcp_stop_loss, generate_vcp_long_signals

START = date(2021, 6, 14)
END = date(2026, 6, 12)
OUT = ROOT / "results" / "sprint_2_2"
INITIAL_CAPITAL = 1_000_000.0
RISK_PER_TRADE = 0.01
MAX_POSITIONS = 8
MAX_POSITION_PCT = 0.15
SLIPPAGE = 0.001
MAX_HOLD_SESSIONS = 60


@dataclass(frozen=True)
class VCPVariant:
    name: str
    min_rs_rank: float = 0.0
    max_pivot_tightness: float | None = None
    exit_mode: str = "ema20"
    market_mode: str = "constructive"


@dataclass
class VCPTrade:
    symbol: str
    signal_date: str
    entry_date: str
    exit_date: str
    entry_price: float
    exit_price: float
    quantity: int
    gross_pnl: float
    costs: float
    net_pnl: float
    return_pct: float
    exit_reason: str
    hold_sessions: int
    regime: str


def _load_daily_stock_bars() -> pd.DataFrame:
    query = """
        WITH bars AS (
            SELECT
                symbol,
                (datetime AT TIME ZONE 'Asia/Kolkata')::date AS session_date,
                datetime,
                open::double precision AS open,
                high::double precision AS high,
                low::double precision AS low,
                close::double precision AS close,
                volume::bigint AS volume
            FROM public.ohlcv_15min
            WHERE symbol NOT IN ('NIFTY50', 'BANKNIFTY')
              AND volume > 0
              AND (datetime AT TIME ZONE 'Asia/Kolkata')::date >= :start_date
              AND (datetime AT TIME ZONE 'Asia/Kolkata')::date <= :end_date
        ),
        ranked AS (
            SELECT
                *,
                row_number() OVER (PARTITION BY symbol, session_date ORDER BY datetime ASC) AS rn_open,
                row_number() OVER (PARTITION BY symbol, session_date ORDER BY datetime DESC) AS rn_close
            FROM bars
        )
        SELECT
            symbol,
            session_date AS date,
            max(open) FILTER (WHERE rn_open = 1) AS open,
            max(high) AS high,
            min(low) AS low,
            max(close) FILTER (WHERE rn_close = 1) AS close,
            sum(volume) AS volume
        FROM ranked
        GROUP BY symbol, session_date
        ORDER BY symbol, session_date
    """
    frame = pd.read_sql(text(query), get_engine(), params={"start_date": START, "end_date": END})
    frame["date"] = pd.to_datetime(frame["date"]).dt.date
    return frame


def _load_regime_labels() -> pd.DataFrame:
    labels_path = ROOT / "results" / "sprint_2_1" / "daily_regime_labels.csv"
    if not labels_path.exists():
        raise FileNotFoundError(labels_path)
    labels = pd.read_csv(labels_path)
    labels["date"] = pd.to_datetime(labels["session_date"]).dt.date
    labels["constructive_market"] = (
        (labels["regime_label"] == "UPTREND")
        | (
            (labels["regime_label"] == "RANGING")
            & (pd.to_numeric(labels["nifty_close"], errors="coerce") > pd.to_numeric(labels["sma200"], errors="coerce"))
            & (pd.to_numeric(labels["di_plus"], errors="coerce") >= pd.to_numeric(labels["di_minus"], errors="coerce"))
        )
    )
    nifty_close = pd.to_numeric(labels["nifty_close"], errors="coerce")
    labels["nifty_return_60d"] = nifty_close / nifty_close.shift(60) - 1
    labels["nifty_above_sma50"] = nifty_close > pd.to_numeric(labels["sma50"], errors="coerce")
    labels["nifty_momentum_60d_positive"] = labels["nifty_return_60d"] > 0
    return labels[["date", "regime_label", "constructive_market", "nifty_return_60d", "nifty_above_sma50", "nifty_momentum_60d_positive"]]


def _market_allowed(item: pd.DataFrame, variant: VCPVariant) -> pd.Series:
    if variant.market_mode == "constructive":
        return item["constructive_market"].fillna(False).astype(bool)
    if variant.market_mode == "constructive_above_sma50":
        return item["constructive_market"].fillna(False).astype(bool) & item["nifty_above_sma50"].fillna(False).astype(bool)
    if variant.market_mode == "uptrend_only":
        return item["regime_label"].eq("UPTREND")
    if variant.market_mode == "positive_momentum":
        return item["constructive_market"].fillna(False).astype(bool) & item["nifty_momentum_60d_positive"].fillna(False).astype(bool)
    raise ValueError(f"unsupported market_mode: {variant.market_mode}")


def _prepare_symbol_frames(daily: pd.DataFrame, labels: pd.DataFrame, variant: VCPVariant) -> dict[str, pd.DataFrame]:
    frames: dict[str, pd.DataFrame] = {}
    for symbol, group in daily.groupby("symbol", sort=False):
        item = add_vcp_features(group.sort_values("date").reset_index(drop=True))
        item = item.merge(labels, on="date", how="left")
        item["stock_return_60d"] = pd.to_numeric(item["close"], errors="coerce") / pd.to_numeric(item["close"], errors="coerce").shift(60) - 1
        item["rs_score"] = item["stock_return_60d"] - item["nifty_return_60d"]
        raw_signal = generate_vcp_long_signals(item)
        if variant.max_pivot_tightness is not None:
            raw_signal &= pd.to_numeric(item["pivot_tightness_10d"], errors="coerce") <= variant.max_pivot_tightness
        item["vcp_signal"] = raw_signal & _market_allowed(item, variant)
        frames[str(symbol)] = item.reset_index(drop=True)
    if variant.min_rs_rank > 0:
        ranks = []
        for symbol, frame in frames.items():
            ranks.append(pd.DataFrame({"symbol": symbol, "date": frame["date"], "rs_score": frame["rs_score"]}))
        rank_frame = pd.concat(ranks, ignore_index=True)
        rank_frame["rs_rank"] = rank_frame.groupby("date")["rs_score"].rank(pct=True)
        rank_lookup = {(row.symbol, row.date): row.rs_rank for row in rank_frame.itertuples(index=False)}
        for symbol, frame in frames.items():
            frame["rs_rank"] = [rank_lookup.get((symbol, row_date), np.nan) for row_date in frame["date"]]
            frame["vcp_signal"] = frame["vcp_signal"] & (pd.to_numeric(frame["rs_rank"], errors="coerce") >= variant.min_rs_rank)
    return frames


def _metrics(equity_curve: pd.DataFrame, trades: list[VCPTrade]) -> dict[str, object]:
    equity = pd.to_numeric(equity_curve["equity"], errors="coerce")
    dates = pd.to_datetime(equity_curve["date"])
    years = max((dates.max() - dates.min()).days / 365.25, 1 / 365.25)
    total_return = float(equity.iloc[-1] / INITIAL_CAPITAL - 1)
    cagr = float((equity.iloc[-1] / INITIAL_CAPITAL) ** (1 / years) - 1)
    returns = equity.pct_change().dropna()
    sharpe = float(((returns.mean() - 0.065 / 252) / returns.std()) * math.sqrt(252)) if len(returns) > 1 and returns.std() else 0.0
    drawdown = equity / equity.cummax() - 1
    wins = [trade for trade in trades if trade.net_pnl > 0]
    losses = [trade for trade in trades if trade.net_pnl < 0]
    gross_win = sum(trade.net_pnl for trade in wins)
    gross_loss = abs(sum(trade.net_pnl for trade in losses))
    avg_deploy = float(equity_curve["deployed_pct"].mean()) if "deployed_pct" in equity_curve else 0.0
    return {
        "initial_capital": INITIAL_CAPITAL,
        "final_capital": float(equity.iloc[-1]),
        "total_return": total_return,
        "cagr": cagr,
        "max_drawdown": float(drawdown.min()) if len(drawdown) else 0.0,
        "sharpe_ratio": sharpe,
        "win_rate": len(wins) / len(trades) if trades else 0.0,
        "profit_factor": gross_win / gross_loss if gross_loss else 0.0,
        "trade_count": len(trades),
        "avg_hold_sessions": float(np.mean([trade.hold_sessions for trade in trades])) if trades else 0.0,
        "avg_deployment": avg_deploy,
        "deployed_cagr": cagr / avg_deploy if avg_deploy > 0 else 0.0,
    }


def run_backtest(variant: VCPVariant, daily: pd.DataFrame | None = None, labels: pd.DataFrame | None = None) -> tuple[pd.DataFrame, list[VCPTrade], dict[str, object]]:
    OUT.mkdir(parents=True, exist_ok=True)
    daily = _load_daily_stock_bars() if daily is None else daily
    labels = _load_regime_labels() if labels is None else labels
    frames = _prepare_symbol_frames(daily, labels, variant)
    sessions = sorted(set(daily["date"]))
    row_lookup = {
        symbol: {row_date: idx for idx, row_date in enumerate(frame["date"].tolist())}
        for symbol, frame in frames.items()
    }
    signals_by_date: dict[date, list[dict[str, object]]] = {}
    for symbol, frame in frames.items():
        signal_rows = frame.loc[frame["vcp_signal"], ["date", "regime_label"]]
        for _, row in signal_rows.iterrows():
            signals_by_date.setdefault(row["date"], []).append({"symbol": symbol, "date": row["date"], "regime": row["regime_label"]})
    cash = INITIAL_CAPITAL
    open_positions: list[dict[str, object]] = []
    trades: list[VCPTrade] = []
    equity_rows: list[dict[str, object]] = []
    pending_signals: list[dict[str, object]] = []

    for session in sessions:
        # Fill signals from previous session at today's open.
        for signal in list(pending_signals):
            if len(open_positions) >= MAX_POSITIONS:
                pending_signals.remove(signal)
                continue
            frame = frames[str(signal["symbol"])]
            row_idx = row_lookup[str(signal["symbol"])].get(session)
            if row_idx is None:
                pending_signals.remove(signal)
                continue
            row = frame.iloc[row_idx]
            entry_price = float(row["open"]) * (1 + SLIPPAGE)
            history = frame.iloc[: row_idx + 1]
            try:
                stop = calculate_vcp_stop_loss(history.iloc[:-1], entry_price)
            except ValueError:
                pending_signals.remove(signal)
                continue
            quantity = calculate_position_size(cash, entry_price, stop, RISK_PER_TRADE)
            quantity = apply_position_limits(quantity, cash, entry_price, MAX_POSITION_PCT)
            if quantity <= 0 or quantity * entry_price > cash:
                pending_signals.remove(signal)
                continue
            entry_cost = calculate_transaction_costs(quantity * entry_price, trade_type="delivery", side="buy")["total"]
            cash -= quantity * entry_price + entry_cost
            open_positions.append(
                {
                    "symbol": signal["symbol"],
                    "signal_date": signal["date"],
                    "entry_date": session,
                    "entry_price": entry_price,
                    "quantity": quantity,
                    "stop": stop,
                    "entry_cost": entry_cost,
                    "entry_idx": row_idx,
                    "regime": signal["regime"],
                }
            )
            pending_signals.remove(signal)

        # Manage open positions on today's bar.
        for position in list(open_positions):
            frame = frames[str(position["symbol"])]
            row_idx = row_lookup[str(position["symbol"])].get(session)
            if row_idx is None:
                continue
            row = frame.iloc[row_idx]
            hold = row_idx - int(position["entry_idx"]) + 1
            exit_reason = ""
            exit_price = 0.0
            if float(row["low"]) <= float(position["stop"]):
                exit_reason = "stop_loss"
                exit_price = float(position["stop"]) * (1 - SLIPPAGE)
            elif variant.exit_mode == "ema10" and pd.notna(row["ema10"]) and float(row["close"]) < float(row["ema10"]):
                exit_reason = "ema10_exit"
                exit_price = float(row["close"]) * (1 - SLIPPAGE)
            elif variant.exit_mode == "ema20" and pd.notna(row["ema20"]) and float(row["close"]) < float(row["ema20"]):
                exit_reason = "ema20_exit"
                exit_price = float(row["close"]) * (1 - SLIPPAGE)
            elif variant.exit_mode == "atr_trail" and pd.notna(row["atr20"]) and float(row["close"]) < max(float(position["stop"]), float(row["high"]) - 3.0 * float(row["atr20"])):
                exit_reason = "atr_trail_exit"
                exit_price = float(row["close"]) * (1 - SLIPPAGE)
            elif hold >= MAX_HOLD_SESSIONS:
                exit_reason = "time_exit"
                exit_price = float(row["close"]) * (1 - SLIPPAGE)
            if not exit_reason:
                continue
            quantity = int(position["quantity"])
            sell_cost = calculate_transaction_costs(quantity * exit_price, trade_type="delivery", side="sell")["total"]
            cash += quantity * exit_price - sell_cost
            gross_pnl = (exit_price - float(position["entry_price"])) * quantity
            costs = float(position["entry_cost"]) + sell_cost
            trades.append(
                VCPTrade(
                    symbol=str(position["symbol"]),
                    signal_date=str(position["signal_date"]),
                    entry_date=str(position["entry_date"]),
                    exit_date=str(session),
                    entry_price=float(position["entry_price"]),
                    exit_price=exit_price,
                    quantity=quantity,
                    gross_pnl=gross_pnl,
                    costs=costs,
                    net_pnl=gross_pnl - costs,
                    return_pct=(gross_pnl - costs) / (float(position["entry_price"]) * quantity),
                    exit_reason=exit_reason,
                    hold_sessions=hold,
                    regime=str(position["regime"]),
                )
            )
            open_positions.remove(position)

        # Create pending signals for the next session.
        active_symbols = {str(position["symbol"]) for position in open_positions}
        for signal in signals_by_date.get(session, []):
            if str(signal["symbol"]) not in active_symbols:
                pending_signals.append(signal)

        position_value = 0.0
        for position in open_positions:
            frame = frames[str(position["symbol"])]
            row_idx = row_lookup[str(position["symbol"])].get(session)
            mark = float(position["entry_price"]) if row_idx is None else float(frame.iloc[row_idx]["close"])
            position_value += int(position["quantity"]) * mark
        equity = cash + position_value
        equity_rows.append(
            {
                "date": session,
                "equity": equity,
                "cash": cash,
                "open_positions": len(open_positions),
                "deployed_pct": position_value / equity if equity > 0 else 0.0,
            }
        )

    equity_curve = pd.DataFrame(equity_rows)
    metrics = _metrics(equity_curve, trades)
    return equity_curve, trades, metrics


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    daily = _load_daily_stock_bars()
    labels = _load_regime_labels()
    variants = [
        VCPVariant("baseline"),
        VCPVariant("rs_top_40", min_rs_rank=0.60),
        VCPVariant("tight_pivot", max_pivot_tightness=0.08),
        VCPVariant("ema10_exit", exit_mode="ema10"),
        VCPVariant("atr_trail_exit", exit_mode="atr_trail"),
        VCPVariant("atr_trail_above_sma50", exit_mode="atr_trail", market_mode="constructive_above_sma50"),
        VCPVariant("atr_trail_uptrend_only", exit_mode="atr_trail", market_mode="uptrend_only"),
        VCPVariant("atr_trail_positive_momentum", exit_mode="atr_trail", market_mode="positive_momentum"),
    ]
    summaries = []
    for variant in variants:
        equity_curve, trades, metrics = run_backtest(variant, daily=daily, labels=labels)
        metrics = {"variant": variant.name, **metrics}
        variant_dir = OUT / variant.name
        variant_dir.mkdir(parents=True, exist_ok=True)
        equity_curve.to_csv(variant_dir / "equity_curve.csv", index=False)
        pd.DataFrame([asdict(trade) for trade in trades]).to_csv(variant_dir / "trades.csv", index=False)
        if variant.name == "baseline":
            equity_curve.to_csv(OUT / "equity_curve.csv", index=False)
            pd.DataFrame([asdict(trade) for trade in trades]).to_csv(OUT / "trades.csv", index=False)
        if trades:
            trade_frame = pd.DataFrame([asdict(trade) for trade in trades])
            trade_frame["entry_year"] = pd.to_datetime(trade_frame["entry_date"]).dt.year
            yearly = trade_frame.groupby("entry_year").agg(trades=("symbol", "count"), net_pnl=("net_pnl", "sum"), win_rate=("net_pnl", lambda s: float((s > 0).mean())))
            regime = trade_frame.groupby("regime").agg(trades=("symbol", "count"), net_pnl=("net_pnl", "sum"), win_rate=("net_pnl", lambda s: float((s > 0).mean())))
            yearly.to_csv(variant_dir / "yearly_breakdown.csv")
            regime.to_csv(variant_dir / "regime_breakdown.csv")
            if variant.name == "baseline":
                yearly.to_csv(OUT / "yearly_breakdown.csv")
                regime.to_csv(OUT / "regime_breakdown.csv")
        (variant_dir / "metrics.json").write_text(json.dumps(metrics, indent=2, default=str), encoding="utf-8")
        if variant.name == "baseline":
            (OUT / "metrics.json").write_text(json.dumps(metrics, indent=2, default=str), encoding="utf-8")
        summaries.append(metrics)
    pd.DataFrame(summaries).to_csv(OUT / "variant_summary.csv", index=False)
    print(pd.DataFrame(summaries).to_string(index=False))


if __name__ == "__main__":
    main()
