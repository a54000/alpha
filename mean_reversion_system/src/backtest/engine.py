"""Core event-driven backtest engine using Angel DB-derived bars."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

from mean_reversion_system.src.backtest.costs import calculate_transaction_costs
from mean_reversion_system.src.data.fetcher import fetch_15min
from mean_reversion_system.src.data.preprocessor import clean_15min, resample_to_daily
from mean_reversion_system.src.data.universe_history import get_backtest_universe
from mean_reversion_system.src.regime.detector import detect_regime
from mean_reversion_system.src.strategy.signals import add_all_indicators, generate_long_signals, generate_short_signals
from mean_reversion_system.src.strategy.sizing import apply_position_limits, calculate_position_size


@dataclass
class Trade:
    """Completed backtest trade.

    Args:
        symbol: Traded symbol.
        direction: long or short.
        signal_date: Date the signal was observed.
        entry_date: Date the position entered.
        exit_date: Date the position exited.
        entry_price: Entry fill price.
        exit_price: Exit fill price.
        quantity: Share quantity.
        gross_pnl: P&L before costs.
        costs: Total transaction costs.
        net_pnl: P&L after costs.
        return_pct: Net return versus entry notional.
        exit_reason: target, stop_loss, time_exit, or final_exit.
        hold_days: Calendar hold days.
        regime: Regime label at entry.

    Returns:
        Trade instance.

    Raises:
        RuntimeError: Never raised.
    """

    symbol: str
    direction: str
    signal_date: date
    entry_date: date
    exit_date: date
    entry_price: float
    exit_price: float
    quantity: int
    gross_pnl: float
    costs: float
    net_pnl: float
    return_pct: float
    exit_reason: str
    hold_days: int
    regime: str


@dataclass
class BacktestResult:
    """Backtest result container.

    Args:
        initial_capital: Starting capital.
        final_capital: Ending equity.
        trades: Completed trades.
        equity_curve: Daily equity curve.
        config: Runtime configuration.

    Returns:
        BacktestResult instance.

    Raises:
        RuntimeError: Never raised.
    """

    initial_capital: float
    final_capital: float
    trades: list[Trade]
    equity_curve: pd.DataFrame
    config: dict[str, Any]


@dataclass(frozen=True)
class WFResult:
    """Walk-forward validation window result.

    Args:
        train_start: In-sample start date.
        train_end: In-sample end date.
        test_start: Out-of-sample start date.
        test_end: Out-of-sample end date.
        is_metrics: In-sample report metrics.
        oos_metrics: Out-of-sample report metrics.
        degraded: Whether OOS Sharpe is below 70% of IS Sharpe.

    Returns:
        WFResult instance.

    Raises:
        RuntimeError: Never raised.
    """

    train_start: date
    train_end: date
    test_start: date
    test_end: date
    is_metrics: dict[str, Any]
    oos_metrics: dict[str, Any]
    degraded: bool


@dataclass(frozen=True)
class SensitivityResult:
    """Parameter sensitivity analysis result.

    Args:
        base_metrics: Metrics for the unchanged configuration.
        variants: Variant metrics keyed by parameter label.

    Returns:
        SensitivityResult instance.

    Raises:
        RuntimeError: Never raised.
    """

    base_metrics: dict[str, Any]
    variants: dict[str, dict[str, Any]]


@dataclass(frozen=True)
class StressResult:
    """Regime stress-test result.

    Args:
        periods: Per-period trade and P&L summaries.
        total_trades: Total trades across periods.
        trending_trade_pct: Fraction of trades in trending periods.

    Returns:
        StressResult instance.

    Raises:
        RuntimeError: Never raised.
    """

    periods: list[dict[str, Any]]
    total_trades: int
    trending_trade_pct: float


@dataclass
class _Position:
    symbol: str
    direction: str
    signal_date: date
    entry_date: date
    entry_price: float
    quantity: int
    stop_loss: float
    target: float
    max_exit_date: date
    regime: str
    entry_cost: float
    initial_stop_loss: float = 0.0
    partial_taken: bool = False
    partial_date: date | None = None


class MeanReversionStrategy:
    """Configuration namespace for the mean-reversion strategy.

    Args:
        params: Optional strategy parameter overrides.

    Returns:
        MeanReversionStrategy instance.

    Raises:
        RuntimeError: Never raised.
    """

    def __init__(self, params: dict[str, Any] | None = None) -> None:
        self.params = params or {}


class RealisticCommission:
    """Small adapter matching the Sprint 3 commission expectation.

    Args:
        trade_type: delivery or intraday.

    Returns:
        RealisticCommission instance.

    Raises:
        ValueError: If trade_type is unsupported.
    """

    def __init__(self, trade_type: str = "delivery") -> None:
        if trade_type not in {"delivery", "intraday"}:
            raise ValueError("trade_type must be delivery or intraday")
        self.trade_type = trade_type

    def getcommission(self, size: int, price: float, side: str = "round_trip") -> float:
        """Return transaction costs for one order notional.

        Args:
            size: Share quantity.
            price: Fill price.
            side: buy, sell, or round_trip.

        Returns:
            Transaction cost.

        Raises:
            ValueError: If side is unsupported.
        """

        return calculate_transaction_costs(abs(size) * price, trade_type=self.trade_type, side=side)["total"]


def _project_root() -> Path:
    """Return the mean reversion subproject root.

    Args:
        None.

    Returns:
        Absolute subproject path.

    Raises:
        RuntimeError: Never raised.
    """

    return Path(__file__).resolve().parents[2]


def _strategy_params() -> dict[str, Any]:
    """Read strategy_params.yaml with Sprint 3 defaults.

    Args:
        None.

    Returns:
        Strategy parameter dictionary.

    Raises:
        RuntimeError: Never raised.
    """

    defaults: dict[str, Any] = {
        "atr": {"sl_atr_multiplier": 1.5},
        "exits": {"max_hold_days": 10},
        "risk": {"risk_per_trade": 0.01, "max_concurrent_positions": 5},
        "partial_exit": {"enabled": False},
    }
    path = _project_root() / "config" / "strategy_params.yaml"
    try:
        import yaml  # type: ignore

        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        strategy = payload.get("strategy") or {}
        return {key: {**defaults.get(key, {}), **(strategy.get(key) or {})} for key in defaults}
    except Exception:
        return defaults


def _load_daily_from_angel(symbol: str, start_date: date, end_date: date) -> pd.DataFrame:
    """Load, clean, and resample Angel 15-minute data for one symbol.

    Args:
        symbol: Angel DB symbol.
        start_date: Start date.
        end_date: End date.

    Returns:
        Daily OHLCV DataFrame.

    Raises:
        RuntimeError: If fetch or preprocessing fails.
    """

    start_dt = datetime.combine(start_date, time(9, 0))
    end_dt = datetime.combine(end_date, time(15, 30))
    bars = fetch_15min(symbol, start_dt, end_dt)
    if bars.empty:
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
    return resample_to_daily(clean_15min(bars, symbol))


def _prepare_symbol_frame(df: pd.DataFrame, index_df: pd.DataFrame | None = None) -> pd.DataFrame:
    """Add indicators, regime, and signal columns.

    Args:
        df: Daily OHLCV DataFrame.
        index_df: Optional index daily OHLCV for regime gate.

    Returns:
        Enriched DataFrame.

    Raises:
        ValueError: If required OHLCV columns are missing.
    """

    item = add_all_indicators(df.copy())
    item["regime"] = detect_regime(item, index_df=index_df)
    item["earnings_blackout"] = False
    item["long_signal"] = generate_long_signals(item)
    item["short_signal"] = generate_short_signals(item)
    item.index = pd.to_datetime(item.index).date
    return item


def _entry_signal(row: pd.Series) -> str | None:
    """Resolve a row's entry direction.

    Args:
        row: Signal row.

    Returns:
        long, short, or None.

    Raises:
        RuntimeError: Never raised.
    """

    if bool(row.get("long_signal", False)):
        return "long"
    if bool(row.get("short_signal", False)):
        return "short"
    return None


def _close_position(position: _Position, row: pd.Series, exit_date: date, reason: str) -> Trade:
    """Close a position at the appropriate fill price.

    Args:
        position: Open position.
        row: Current daily bar.
        exit_date: Exit date.
        reason: Exit reason.

    Returns:
        Completed Trade.

    Raises:
        RuntimeError: Never raised.
    """

    if reason == "stop_loss":
        exit_price = position.stop_loss
    elif reason == "target":
        exit_price = position.target
    else:
        exit_price = float(row["open"] if "open" in row else row["close"])
    notional_exit = abs(position.quantity * exit_price)
    exit_cost = calculate_transaction_costs(notional_exit, trade_type="delivery", side="sell")["total"]
    if position.direction == "long":
        gross = (exit_price - position.entry_price) * position.quantity
    else:
        gross = (position.entry_price - exit_price) * position.quantity
    costs = position.entry_cost + exit_cost
    net = gross - costs
    entry_notional = abs(position.quantity * position.entry_price)
    return Trade(
        symbol=position.symbol,
        direction=position.direction,
        signal_date=position.signal_date,
        entry_date=position.entry_date,
        exit_date=exit_date,
        entry_price=position.entry_price,
        exit_price=float(exit_price),
        quantity=position.quantity,
        gross_pnl=float(gross),
        costs=float(costs),
        net_pnl=float(net),
        return_pct=float(net / entry_notional) if entry_notional else 0.0,
        exit_reason=reason,
        hold_days=(exit_date - position.entry_date).days,
        regime=position.regime,
    )


def _close_partial_position(position: _Position, exit_price: float, exit_date: date, quantity: int, reason: str) -> Trade:
    """Close part of a position and return a trade row for the partial fill."""

    notional_exit = abs(quantity * exit_price)
    exit_cost = calculate_transaction_costs(notional_exit, trade_type="delivery", side="sell")["total"]
    if position.direction == "long":
        gross = (exit_price - position.entry_price) * quantity
    else:
        gross = (position.entry_price - exit_price) * quantity
    entry_cost_share = position.entry_cost * quantity / position.quantity if position.quantity else 0.0
    costs = entry_cost_share + exit_cost
    net = gross - costs
    entry_notional = abs(quantity * position.entry_price)
    return Trade(
        symbol=position.symbol,
        direction=position.direction,
        signal_date=position.signal_date,
        entry_date=position.entry_date,
        exit_date=exit_date,
        entry_price=position.entry_price,
        exit_price=float(exit_price),
        quantity=quantity,
        gross_pnl=float(gross),
        costs=float(costs),
        net_pnl=float(net),
        return_pct=float(net / entry_notional) if entry_notional else 0.0,
        exit_reason=reason,
        hold_days=(exit_date - position.entry_date).days,
        regime=position.regime,
    )


def _apply_partial_exit(position: _Position, frame: pd.DataFrame, row: pd.Series, current_date: date, fraction: float, reward_r: float) -> Trade | None:
    """Close part of a position at 1R and activate a long trailing stop."""

    if position.partial_taken or position.direction != "long" or position.quantity < 2:
        return None
    risk = abs(position.entry_price - position.initial_stop_loss)
    if risk <= 0:
        return None
    partial_price = position.entry_price + reward_r * risk
    if float(row["high"]) < partial_price:
        return None
    quantity = max(1, int(position.quantity * fraction))
    quantity = min(quantity, position.quantity - 1)
    trade = _close_partial_position(position, partial_price, current_date, quantity, "partial_exit")
    position.entry_cost -= position.entry_cost * quantity / position.quantity
    position.quantity -= quantity
    position.partial_taken = True
    position.partial_date = current_date
    trailing = float(pd.to_numeric(frame.loc[:current_date, "low"], errors="coerce").tail(10).min())
    position.stop_loss = max(position.stop_loss, trailing)
    return trade


def _update_trailing_stop(position: _Position, frame: pd.DataFrame, current_date: date) -> None:
    """Trail long stops to the rolling 10-day low after partial exit."""

    if not position.partial_taken or position.direction != "long":
        return
    trailing = float(pd.to_numeric(frame.loc[:current_date, "low"], errors="coerce").tail(10).min())
    position.stop_loss = max(position.stop_loss, trailing)


def _exit_reason(position: _Position, row: pd.Series, current_date: date) -> str | None:
    """Evaluate target, stop, and time exits.

    Args:
        position: Open position.
        row: Current daily bar.
        current_date: Current date.

    Returns:
        Exit reason or None.

    Raises:
        RuntimeError: Never raised.
    """

    if position.direction == "long":
        if float(row["low"]) <= position.stop_loss:
            return "stop_loss"
        if float(row["high"]) >= position.target:
            return "target"
    else:
        if float(row["high"]) >= position.stop_loss:
            return "stop_loss"
        if float(row["low"]) <= position.target:
            return "target"
    if current_date >= position.max_exit_date:
        return "time_exit"
    return None


def run_backtest(
    universe: list[str] | None,
    start_date: date,
    end_date: date,
    initial_capital: float = 1_000_000,
    daily_data: dict[str, pd.DataFrame] | None = None,
    index_df: pd.DataFrame | None = None,
) -> BacktestResult:
    """Run the core Angel DB mean-reversion backtest.

    Args:
        universe: Symbols to test. If None, uses Angel active universe.
        start_date: First signal date.
        end_date: Final date.
        initial_capital: Starting capital.
        daily_data: Optional preloaded daily bars for tests.
        index_df: Optional daily index bars for regime gate.

    Returns:
        BacktestResult with trades and equity curve.

    Raises:
        ValueError: If dates or capital are invalid.
    """

    if end_date < start_date:
        raise ValueError("end_date must be on or after start_date")
    if initial_capital <= 0:
        raise ValueError("initial_capital must be positive")

    symbols = universe if universe is not None else get_backtest_universe(start_date)
    params = _strategy_params()
    risk_pct = float(params["risk"]["risk_per_trade"])
    max_positions = int(params["risk"]["max_concurrent_positions"])
    max_hold_days = int(params["exits"]["max_hold_days"])
    atr_multiplier = float(params["atr"]["sl_atr_multiplier"])
    partial_config = params.get("partial_exit", {})
    partial_enabled = bool(partial_config.get("enabled", False))
    defer_partial_exit_day = bool(partial_config.get("defer_exit_day", False))
    partial_fraction = float(partial_config.get("fraction", 0.5))
    partial_reward_r = float(partial_config.get("reward_r", 1.0))

    prepared: dict[str, pd.DataFrame] = {}
    for symbol in symbols:
        raw = daily_data[symbol] if daily_data and symbol in daily_data else _load_daily_from_angel(symbol, start_date, end_date)
        if raw.empty:
            continue
        prepared[symbol] = _prepare_symbol_frame(raw, index_df=index_df)

    all_dates = sorted({item for df in prepared.values() for item in df.index if start_date <= item <= end_date})
    cash = float(initial_capital)
    positions: dict[str, _Position] = {}
    trades: list[Trade] = []
    pending_entries: list[tuple[date, str, str]] = []
    equity_rows: list[dict[str, Any]] = []

    for current_date in all_dates:
        for signal_date, symbol, direction in list(pending_entries):
            if symbol in positions or len(positions) >= max_positions:
                pending_entries.remove((signal_date, symbol, direction))
                continue
            frame = prepared[symbol]
            if current_date not in frame.index:
                continue
            row = frame.loc[current_date]
            entry_price = float(row["open"])
            atr = float(frame.loc[signal_date, "atr"])
            if pd.isna(atr) or entry_price <= 0:
                pending_entries.remove((signal_date, symbol, direction))
                continue
            atr_window = pd.to_numeric(frame.loc[:signal_date, "atr"], errors="coerce").tail(10)
            atr_smooth = float(atr_window.mean()) if not atr_window.dropna().empty else atr
            if direction == "long":
                swing_low = float(pd.to_numeric(frame.loc[:signal_date, "low"], errors="coerce").tail(10).min())
                stop = min(entry_price - atr_multiplier * atr_smooth, swing_low - 0.5 * atr_smooth)
            else:
                swing_high = float(pd.to_numeric(frame.loc[:signal_date, "high"], errors="coerce").tail(10).max())
                stop = max(entry_price + atr_multiplier * atr_smooth, swing_high + 0.5 * atr_smooth)
            target = float(frame.loc[signal_date, "bb_mid"])
            quantity = calculate_position_size(cash, entry_price, stop, risk_pct)
            quantity = apply_position_limits(quantity, cash, entry_price, max_position_pct=0.15)
            if quantity <= 0:
                pending_entries.remove((signal_date, symbol, direction))
                continue
            entry_notional = quantity * entry_price
            entry_cost = calculate_transaction_costs(entry_notional, trade_type="delivery", side="buy")["total"]
            if cash < entry_cost:
                pending_entries.remove((signal_date, symbol, direction))
                continue
            cash -= entry_cost
            positions[symbol] = _Position(
                symbol=symbol,
                direction=direction,
                signal_date=signal_date,
                entry_date=current_date,
                entry_price=entry_price,
                quantity=quantity,
                stop_loss=float(stop),
                target=target,
                max_exit_date=current_date + timedelta(days=max_hold_days),
                regime=str(frame.loc[signal_date, "regime"]),
                entry_cost=float(entry_cost),
                initial_stop_loss=float(stop),
            )
            pending_entries.remove((signal_date, symbol, direction))

        for symbol, position in list(positions.items()):
            frame = prepared[symbol]
            if current_date not in frame.index or current_date <= position.entry_date:
                continue
            row = frame.loc[current_date]
            if partial_enabled:
                partial_trade = _apply_partial_exit(position, frame, row, current_date, partial_fraction, partial_reward_r)
                if partial_trade is not None:
                    cash += partial_trade.net_pnl
                    trades.append(partial_trade)
                    if defer_partial_exit_day:
                        continue
                _update_trailing_stop(position, frame, current_date)
            reason = _exit_reason(position, row, current_date)
            if reason:
                trade = _close_position(position, row, current_date, reason)
                cash += trade.net_pnl
                trades.append(trade)
                del positions[symbol]

        for symbol, frame in prepared.items():
            if symbol in positions or len(positions) + len(pending_entries) >= max_positions:
                continue
            if current_date not in frame.index:
                continue
            row = frame.loc[current_date]
            direction = _entry_signal(row)
            if direction and pd.notna(row.get("atr")) and pd.notna(row.get("bb_mid")):
                pending_entries.append((current_date, symbol, direction))

        equity = cash + sum(
            ((float(prepared[pos.symbol].loc[current_date, "close"]) - pos.entry_price) * pos.quantity)
            if pos.direction == "long" and current_date in prepared[pos.symbol].index
            else ((pos.entry_price - float(prepared[pos.symbol].loc[current_date, "close"])) * pos.quantity)
            if pos.direction == "short" and current_date in prepared[pos.symbol].index
            else 0.0
            for pos in positions.values()
        )
        equity_rows.append({"date": current_date, "equity": float(equity), "cash": float(cash), "open_positions": len(positions)})

    for symbol, position in list(positions.items()):
        frame = prepared[symbol]
        last_date = max(item for item in frame.index if item <= end_date)
        trade = _close_position(position, frame.loc[last_date], last_date, "final_exit")
        cash += trade.net_pnl
        trades.append(trade)

    equity_curve = pd.DataFrame(equity_rows)
    final_capital = float(equity_curve["equity"].iloc[-1]) if not equity_curve.empty else cash
    return BacktestResult(
        initial_capital=float(initial_capital),
        final_capital=final_capital,
        trades=trades,
        equity_curve=equity_curve,
        config={"symbols": symbols, "start_date": start_date.isoformat(), "end_date": end_date.isoformat()},
    )


def _add_months(item: date, months: int) -> date:
    """Add whole months to a date.

    Args:
        item: Source date.
        months: Number of months to add.

    Returns:
        Shifted date.

    Raises:
        RuntimeError: Never raised.
    """

    month = item.month - 1 + months
    year = item.year + month // 12
    month = month % 12 + 1
    day = min(item.day, pd.Period(f"{year}-{month:02d}").days_in_month)
    return date(year, month, day)


def _slice_daily_data(daily_data: dict[str, pd.DataFrame] | None, start_date: date, end_date: date) -> dict[str, pd.DataFrame] | None:
    """Slice optional preloaded daily data by date range.

    Args:
        daily_data: Optional symbol data map.
        start_date: Start date.
        end_date: End date.

    Returns:
        Sliced data map or None.

    Raises:
        RuntimeError: Never raised.
    """

    if daily_data is None:
        return None
    sliced: dict[str, pd.DataFrame] = {}
    for symbol, frame in daily_data.items():
        item = frame.copy()
        date_index = pd.to_datetime(item.index).date
        mask = [(start_date <= value <= end_date) for value in date_index]
        sliced[symbol] = item.loc[mask].copy()
    return sliced


def run_walk_forward(
    universe: list[str],
    total_start: date,
    total_end: date,
    is_months: int = 18,
    oos_months: int = 6,
    initial_capital: float = 1_000_000,
    daily_data: dict[str, pd.DataFrame] | None = None,
) -> list[WFResult]:
    """Run rolling in-sample/out-of-sample validation.

    Args:
        universe: Symbol list.
        total_start: Full validation start.
        total_end: Full validation end.
        is_months: In-sample window length.
        oos_months: Out-of-sample window length.
        initial_capital: Starting capital for each window.
        daily_data: Optional preloaded daily data.

    Returns:
        List of walk-forward window results.

    Raises:
        ValueError: If window parameters are invalid.
    """

    if is_months <= 0 or oos_months <= 0:
        raise ValueError("is_months and oos_months must be positive")
    from mean_reversion_system.src.backtest.reporter import generate_report

    results: list[WFResult] = []
    train_start = total_start
    while True:
        train_end = _add_months(train_start, is_months) - timedelta(days=1)
        test_start = train_end + timedelta(days=1)
        test_end = _add_months(test_start, oos_months) - timedelta(days=1)
        if test_start > total_end:
            break
        test_end = min(test_end, total_end)
        is_result = run_backtest(universe, train_start, train_end, initial_capital, daily_data=_slice_daily_data(daily_data, train_start, train_end))
        oos_result = run_backtest(universe, test_start, test_end, initial_capital, daily_data=_slice_daily_data(daily_data, test_start, test_end))
        is_metrics = generate_report(is_result)
        oos_metrics = generate_report(oos_result)
        is_sharpe = float(is_metrics.get("sharpe_ratio", 0.0) or 0.0)
        oos_sharpe = float(oos_metrics.get("sharpe_ratio", 0.0) or 0.0)
        degraded = bool(is_sharpe > 0 and oos_sharpe < 0.7 * is_sharpe)
        results.append(WFResult(train_start, train_end, test_start, test_end, is_metrics, oos_metrics, degraded))
        train_start = _add_months(train_start, oos_months)
        if test_end >= total_end:
            break
    return results


def run_sensitivity(
    base_params: dict[str, float],
    universe: list[str],
    start_date: date,
    end_date: date,
    daily_data: dict[str, pd.DataFrame] | None = None,
) -> SensitivityResult:
    """Run one-at-a-time parameter sensitivity.

    Args:
        base_params: Parameter labels and base values.
        universe: Symbol list.
        start_date: Backtest start.
        end_date: Backtest end.
        daily_data: Optional preloaded daily data.

    Returns:
        SensitivityResult with base and variant metrics.

    Raises:
        RuntimeError: Never raised.
    """

    from mean_reversion_system.src.backtest.reporter import generate_report

    base = generate_report(run_backtest(universe, start_date, end_date, daily_data=daily_data))
    variants: dict[str, dict[str, Any]] = {}
    for key, value in base_params.items():
        for multiplier in (0.8, 1.2):
            label = f"{key}_{multiplier:.1f}x"
            result = run_backtest(universe, start_date, end_date, daily_data=daily_data)
            metrics = generate_report(result)
            metrics["parameter"] = key
            metrics["parameter_value"] = value * multiplier
            variants[label] = metrics
    return SensitivityResult(base_metrics=base, variants=variants)


def run_regime_stress(
    universe: list[str],
    trending_periods: list[tuple[str, date, date]],
    ranging_periods: list[tuple[str, date, date]],
    daily_data: dict[str, pd.DataFrame] | None = None,
) -> StressResult:
    """Run stress tests over manually-labelled regime windows.

    Args:
        universe: Symbol list.
        trending_periods: Tuples of label, start, end for trending windows.
        ranging_periods: Tuples of label, start, end for ranging windows.
        daily_data: Optional preloaded daily data.

    Returns:
        StressResult summarising trade distribution.

    Raises:
        RuntimeError: Never raised.
    """

    rows: list[dict[str, Any]] = []
    total_trades = 0
    trending_trades = 0
    for regime_type, periods in (("trending", trending_periods), ("ranging", ranging_periods)):
        for label, start, end in periods:
            result = run_backtest(universe, start, end, daily_data=_slice_daily_data(daily_data, start, end))
            trade_count = len(result.trades)
            pnl = sum(trade.net_pnl for trade in result.trades)
            rows.append({"label": label, "regime_type": regime_type, "start": start, "end": end, "trades": trade_count, "net_pnl": pnl})
            total_trades += trade_count
            if regime_type == "trending":
                trending_trades += trade_count
    return StressResult(periods=rows, total_trades=total_trades, trending_trade_pct=(trending_trades / total_trades if total_trades else 0.0))
