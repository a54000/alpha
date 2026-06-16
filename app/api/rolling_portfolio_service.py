"""Interactive rolling 10-slot portfolio construction simulator.

This service is analysis-only. It reads frozen Swing V2.1 pilot recommendations
and cleaned pilot daily bars, then reconstructs the preferred rolling 10-slot
portfolio state through a user-selected number of weekly cohorts.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from app.api.trade_analysis_service import (
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

REPO_ROOT = Path(__file__).resolve().parents[2]
MODEL = "swing_v2_1"
FINAL_RECOMMENDATION_MODEL = "sector_rotation_adx_1m3m"
SUPPORTED_RECOMMENDATION_MODELS = {"swing_v2_1", "sector_rotation_adx_1m3m"}
FISCAL_YEAR_START_MONTH = 4
FINAL_ENTRY_PRICE_FIELD = "entry_1030_open"
FINAL_ENTRY_TIME = "10:30:00"
FINAL_PREVIOUS_DAY_VWAP_MAX_EXTENSION = 0.025


class RollingPortfolioError(RuntimeError):
    """Raised when rolling portfolio simulation cannot run."""


class RollingPortfolioValidationError(ValueError):
    """Raised when simulation parameters are invalid."""


@dataclass(frozen=True)
class RollingPortfolioRequest:
    start_date: date
    weeks: int
    initial_capital: float = 1_000_000.0
    recommendation_model: str = MODEL


def derive_angel_url(research_database_url: str | None, database_name: str = "angel_data") -> str | None:
    if not research_database_url:
        return None
    parts = urlsplit(research_database_url)
    return urlunsplit((parts.scheme, parts.netloc, f"/{database_name}", parts.query, parts.fragment))


def make_engine(database_url: str) -> Engine:
    kwargs: dict[str, object] = {"future": True, "pool_pre_ping": True}
    if not database_url.startswith("sqlite"):
        kwargs.update({"pool_size": 1, "max_overflow": 0})
    return create_engine(database_url, **kwargs)


def validate_request(request: RollingPortfolioRequest) -> None:
    if request.weeks < 1:
        raise RollingPortfolioValidationError("weeks must be at least 1.")
    if request.weeks > 260:
        raise RollingPortfolioValidationError("weeks cannot exceed 260.")
    if request.initial_capital <= 0:
        raise RollingPortfolioValidationError("initial_capital must be greater than zero.")
    if request.recommendation_model not in SUPPORTED_RECOMMENDATION_MODELS:
        raise RollingPortfolioValidationError(f"Unsupported recommendation_model: {request.recommendation_model}.")


def serialize_position(position: AnalysisPosition, prices: dict[str, dict[date, dict[str, float]]], mark_date: date) -> dict[str, object]:
    close_price = prices.get(position.symbol, {}).get(mark_date, {}).get("close")
    market_value = position.quantity * close_price if close_price is not None else None
    unrealized_pnl = market_value - position.entry_value if market_value is not None else None
    return {
        "symbol": position.symbol,
        "sector": position.sector,
        "signal_date": position.signal_date.isoformat(),
        "entry_date": position.entry_date.isoformat(),
        "entry_price": position.entry_price,
        "quantity": position.quantity,
        "entry_value": position.entry_value,
        "planned_exit_date": position.planned_exit_date.isoformat(),
        "rank": position.rank,
        "score": position.score,
        "mark_price": close_price,
        "market_value": market_value,
        "unrealized_pnl": unrealized_pnl,
    }


def serialize_closed_trade(row: dict[str, object]) -> dict[str, object]:
    return {
        **row,
        "exit_reason": row.get("exit_reason") or "planned_exit",
        "status": "closed",
    }


def fiscal_year_label(value: date) -> str:
    start_year = value.year if value.month >= FISCAL_YEAR_START_MONTH else value.year - 1
    return f"FY{start_year}-{str(start_year + 1)[-2:]}"


class RollingPortfolioSimulationService:
    def __init__(
        self,
        angel_database_url: str | None = None,
        pilot_schema: str = "pilot_phase2a",
        angel_engine: Engine | None = None,
    ) -> None:
        research_url = os.environ.get("DATABASE_URL")
        self.angel_database_url = angel_database_url or os.environ.get("ANGEL_DATABASE_URL") or derive_angel_url(research_url)
        self.pilot_schema = pilot_schema
        self.angel_engine = angel_engine or (make_engine(self.angel_database_url) if self.angel_database_url else None)

    def defaults(self, recommendation_model: str = MODEL) -> dict[str, object]:
        if self.angel_engine is None:
            raise RollingPortfolioError("ANGEL_DATABASE_URL is required for rolling portfolio defaults.")
        if recommendation_model not in SUPPORTED_RECOMMENDATION_MODELS:
            raise RollingPortfolioValidationError(f"Unsupported recommendation_model: {recommendation_model}.")
        query = text(
            f"""
            SELECT MIN(date) AS earliest_recommendation_date,
                   MAX(date) AS latest_recommendation_date,
                   COUNT(DISTINCT date) AS recommendation_dates,
                   COUNT(*) AS recommendation_rows
            FROM {self.pilot_schema}.recommendations_daily
            WHERE model = :model
            """
        )
        with self.angel_engine.connect() as connection:
            row = connection.execute(query, {"model": recommendation_model}).mappings().one()
        earliest = row.get("earliest_recommendation_date")
        latest = row.get("latest_recommendation_date")
        return {
            "default_start_date": earliest.isoformat() if hasattr(earliest, "isoformat") else earliest,
            "earliest_recommendation_date": earliest.isoformat() if hasattr(earliest, "isoformat") else earliest,
            "latest_recommendation_date": latest.isoformat() if hasattr(latest, "isoformat") else latest,
            "recommendation_dates": int(row.get("recommendation_dates") or 0),
            "recommendation_rows": int(row.get("recommendation_rows") or 0),
            "recommendation_model": recommendation_model,
            "source": f"{self.pilot_schema}.recommendations_daily",
        }

    def simulate(self, request: RollingPortfolioRequest) -> dict[str, object]:
        validate_request(request)
        if self.angel_engine is None:
            raise RollingPortfolioError("ANGEL_DATABASE_URL is required for rolling portfolio simulation.")
        try:
            recommendations = self._load_recommendations(request.start_date, request.recommendation_model)
            if not recommendations:
                return self._empty_response(request, "No recommendations found on or after start_date.")
            signal_dates = weekly_signal_dates([row["date"] for row in recommendations])
            selected_signal_dates = signal_dates[: request.weeks]
            if not selected_signal_dates:
                return self._empty_response(request, "No weekly recommendation dates found.")
            symbols = {str(row["symbol"]) for row in recommendations if row["date"] <= selected_signal_dates[-1]}
            prices = self._load_prices(min(selected_signal_dates), symbols)
            return self._simulate(request, recommendations, prices, selected_signal_dates)
        except RollingPortfolioValidationError:
            raise
        except Exception as exc:
            raise RollingPortfolioError(f"Rolling portfolio simulation failed: {exc}") from exc

    def _empty_response(self, request: RollingPortfolioRequest, message: str) -> dict[str, object]:
        return {
            "status": "empty",
            "message": message,
            "parameters": {
                "start_date": request.start_date.isoformat(),
                "weeks": request.weeks,
                "initial_capital": request.initial_capital,
                "recommendation_model": request.recommendation_model,
            },
            "summary": {
                "cash": request.initial_capital,
                "equity": request.initial_capital,
                "open_positions": 0,
                "closed_trades": 0,
                "portfolio_size": 10,
                "max_candidate_rank": 5,
                "recommendation_model": request.recommendation_model,
            },
            "weekly_log": [],
            "positions": [],
            "trades": [],
        }

    def _simulate(
        self,
        request: RollingPortfolioRequest,
        recommendations: list[dict[str, object]],
        prices: dict[str, dict[date, dict[str, float]]],
        selected_signal_dates: list[date],
    ) -> dict[str, object]:
        all_dates = sorted({price_date for rows in prices.values() for price_date in rows})
        if not all_dates:
            return self._empty_response(request, "No price data found for selected recommendations.")

        recs_by_date: dict[date, list[dict[str, object]]] = {}
        for row in recommendations:
            recs_by_date.setdefault(row["date"], []).append(row)
        for rows in recs_by_date.values():
            rows.sort(key=lambda row: (int(row["rank"]), str(row["symbol"])))

        entries_by_date: dict[date, tuple[date, list[dict[str, object]]]] = {}
        weekly_log: list[dict[str, object]] = []
        for signal_date in selected_signal_dates:
            entry_date = next_trading_day_after(all_dates, signal_date)
            rows = recs_by_date.get(signal_date, [])[:5]
            weekly_log.append(
                {
                    "week_number": len(weekly_log) + 1,
                    "signal_date": signal_date.isoformat(),
                    "entry_date": entry_date.isoformat() if entry_date else None,
                    "recommendations": [
                        {
                            "rank": int(row["rank"]),
                            "symbol": row["symbol"],
                            "sector": row.get("sector"),
                            "score": row.get("score"),
                            "ema200_extension": row.get("ema200_extension"),
                            "prior_20d_return": row.get("prior_20d_return"),
                        }
                        for row in rows
                    ],
                    "entered": [],
                    "skipped": [],
                }
            )
            if entry_date is not None:
                entries_by_date[entry_date] = (signal_date, rows)

        selected_entry_dates = list(entries_by_date)
        mark_date = max(selected_entry_dates) if selected_entry_dates else selected_signal_dates[-1]
        simulation_dates = [item for item in all_dates if item <= mark_date]
        cash = float(request.initial_capital)
        positions: list[AnalysisPosition] = []
        trades: list[dict[str, object]] = []
        equity_curve: list[dict[str, object]] = []
        trade_id = 1
        log_by_signal = {date.fromisoformat(str(row["signal_date"])): row for row in weekly_log}

        for current_date in simulation_dates:
            remaining: list[AnalysisPosition] = []
            closed_today: set[str] = set()
            for position in positions:
                close_price = prices.get(position.symbol, {}).get(current_date, {}).get("close")
                if current_date >= position.planned_exit_date and close_price is not None:
                    row = build_trade_row(trade_id, position, current_date, close_price, symbol_dates(prices, position.symbol), "ROLLING_10_SLOT")
                    row["exit_reason"] = "planned_exit"
                    row["status"] = "closed"
                    cash += float(row["exit_value"]) - (float(row["charges"]) - total_charges(position.buy_charges))
                    trades.append(row)
                    closed_today.add(position.symbol)
                    trade_id += 1
                else:
                    remaining.append(position)
            positions = remaining

            if current_date in entries_by_date:
                signal_date, candidates = entries_by_date[current_date]
                log_row = log_by_signal[signal_date]
                held = {position.symbol for position in positions}
                equity_at_open = cash + positions_value(positions, prices, current_date, "open")
                target_value = equity_at_open / 10.0
                for rec in candidates:
                    symbol = str(rec["symbol"])
                    if len(positions) >= 10:
                        log_row["skipped"].append({"symbol": symbol, "reason": "portfolio_full"})
                        continue
                    if symbol in held:
                        log_row["skipped"].append({"symbol": symbol, "reason": "already_held"})
                        continue
                    if symbol in closed_today:
                        log_row["skipped"].append({"symbol": symbol, "reason": "closed_same_day"})
                        continue
                    price_row = prices.get(symbol, {}).get(current_date, {})
                    entry_price_field = FINAL_ENTRY_PRICE_FIELD if request.recommendation_model == FINAL_RECOMMENDATION_MODEL else "open"
                    entry_price = price_row.get(entry_price_field)
                    if entry_price is None or entry_price <= 0:
                        log_row["skipped"].append({"symbol": symbol, "reason": "missing_entry_price"})
                        continue
                    previous_day_vwap = rec.get("previous_day_vwap")
                    entry_vs_vwap_pct = None
                    if request.recommendation_model == FINAL_RECOMMENDATION_MODEL:
                        if previous_day_vwap is None or float(previous_day_vwap) <= 0:
                            log_row["skipped"].append({"symbol": symbol, "reason": "missing_previous_day_vwap"})
                            continue
                        entry_vs_vwap_pct = (float(entry_price) / float(previous_day_vwap)) - 1.0
                        if entry_vs_vwap_pct > FINAL_PREVIOUS_DAY_VWAP_MAX_EXTENSION:
                            log_row["skipped"].append(
                                {
                                    "symbol": symbol,
                                    "reason": "entry_gt_prevday_vwap_threshold",
                                    "entry_price": float(entry_price),
                                    "reference_vwap": float(previous_day_vwap),
                                    "entry_vs_reference_vwap_pct": entry_vs_vwap_pct,
                                }
                            )
                            continue
                    allocation = min(target_value, cash)
                    if allocation <= 0:
                        log_row["skipped"].append({"symbol": symbol, "reason": "insufficient_cash"})
                        continue
                    buy_charges = buy_side_charges(allocation)
                    if allocation + total_charges(buy_charges) > cash:
                        allocation = cash / (1.0 + (total_charges(buy_charges) / allocation if allocation else 0.0))
                        buy_charges = buy_side_charges(allocation)
                    planned_exit = nth_trading_day_after(symbol_dates(prices, symbol), current_date, 20) or all_dates[-1]
                    position = AnalysisPosition(
                        symbol=symbol,
                        sector=str(rec["sector"]) if rec.get("sector") is not None else None,
                        signal_date=signal_date,
                        entry_date=current_date,
                        entry_price=float(entry_price),
                        quantity=allocation / float(entry_price),
                        planned_exit_date=planned_exit,
                        rank=int(rec["rank"]),
                        score=float(rec["score"]) if rec.get("score") is not None else None,
                        entry_value=allocation,
                        buy_charges=buy_charges,
                    )
                    cash -= allocation + total_charges(buy_charges)
                    positions.append(position)
                    held.add(symbol)
                    log_row["entered"].append(
                        {
                            "symbol": symbol,
                            "entry_price": float(entry_price),
                            "entry_value": allocation,
                            "entry_time": FINAL_ENTRY_TIME if request.recommendation_model == FINAL_RECOMMENDATION_MODEL else "daily_open",
                            "reference_vwap": float(previous_day_vwap) if previous_day_vwap is not None else None,
                            "entry_vs_reference_vwap_pct": entry_vs_vwap_pct,
                        }
                    )

            market_value_today = positions_value(positions, prices, current_date, "close")
            equity_curve.append(
                {
                    "date": current_date,
                    "cash": cash,
                    "market_value": market_value_today,
                    "equity": cash + market_value_today,
                }
            )

        market_value = positions_value(positions, prices, mark_date, "close")
        equity = cash + market_value
        invested_value = sum(position.entry_value for position in positions)
        return {
            "status": "completed",
            "parameters": {
                "requested_start_date": request.start_date.isoformat(),
                "effective_start_date": selected_signal_dates[0].isoformat(),
                "weeks": request.weeks,
                "initial_capital": request.initial_capital,
                "recommendation_model": request.recommendation_model,
            },
            "summary": {
                "mark_date": mark_date.isoformat(),
                "cash": cash,
                "market_value": market_value,
                "equity": equity,
                "invested_value": invested_value,
                "cash_pct": cash / equity if equity else None,
                "open_positions": len(positions),
                "closed_trades": len(trades),
                "portfolio_size": 10,
                "max_candidate_rank": 5,
                "holding_period": 20,
                "recommendation_model": request.recommendation_model,
                "entry_time": FINAL_ENTRY_TIME if request.recommendation_model == FINAL_RECOMMENDATION_MODEL else "daily_open",
                "vwap_skip_threshold": FINAL_PREVIOUS_DAY_VWAP_MAX_EXTENSION if request.recommendation_model == FINAL_RECOMMENDATION_MODEL else None,
            },
            "weekly_log": weekly_log,
            "positions": [serialize_position(position, prices, mark_date) for position in sorted(positions, key=lambda item: item.symbol)],
            "trades": [serialize_closed_trade(row) for row in trades],
            "financial_year_returns": self._financial_year_returns(equity_curve),
            "constraints": {
                "scoring_changed": False,
                "ranking_changed": False,
                "recommendations_changed": False,
                "portfolio_rules_changed": False,
                "entry_uses_1030": request.recommendation_model == FINAL_RECOMMENDATION_MODEL,
                "vwap_filter_enabled": request.recommendation_model == FINAL_RECOMMENDATION_MODEL,
                "database_modified": False,
                "orders_placed": False,
            },
        }

    def _financial_year_returns(self, equity_curve: list[dict[str, object]]) -> list[dict[str, object]]:
        grouped: dict[str, list[dict[str, object]]] = {}
        for row in equity_curve:
            row_date = row.get("date")
            if not isinstance(row_date, date):
                continue
            grouped.setdefault(fiscal_year_label(row_date), []).append(row)

        returns: list[dict[str, object]] = []
        for label, rows in sorted(grouped.items()):
            rows.sort(key=lambda item: item["date"])
            start = rows[0]
            end = rows[-1]
            start_equity = float(start.get("equity") or 0)
            end_equity = float(end.get("equity") or 0)
            returns.append(
                {
                    "financial_year": label,
                    "start_date": start["date"].isoformat(),
                    "end_date": end["date"].isoformat(),
                    "start_equity": start_equity,
                    "end_equity": end_equity,
                    "return_pct": (end_equity / start_equity) - 1 if start_equity else None,
                }
            )
        return returns

    def _load_recommendations(self, start_date: date, request_model: str) -> list[dict[str, object]]:
        query = text(
            f"""
            SELECT
                r.date,
                r.model,
                r.rank,
                r.symbol,
                r.score,
                r.sector,
                f.ema200_extension,
                f.prior_20d_return
            FROM {self.pilot_schema}.recommendations_daily r
            LEFT JOIN {self.pilot_schema}.features_daily f
              ON f.symbol = r.symbol
             AND f.date = r.date
            WHERE r.model = :model
              AND r.date >= :start_date
            ORDER BY r.date ASC, r.rank ASC, r.symbol ASC
            """
        )
        with self.angel_engine.connect() as connection:
            rows = connection.execute(query, {"model": request_model, "start_date": start_date}).mappings().all()
        recommendations = [
            {
                "date": row["date"],
                "model": row["model"],
                "rank": int(row["rank"]),
                "symbol": row["symbol"],
                "score": float(row["score"]) if row["score"] is not None else None,
                "sector": row["sector"],
                "ema200_extension": float(row["ema200_extension"]) if row["ema200_extension"] is not None else None,
                "prior_20d_return": float(row["prior_20d_return"]) if row["prior_20d_return"] is not None else None,
                "previous_day_vwap": None,
            }
            for row in rows
        ]
        if request_model == FINAL_RECOMMENDATION_MODEL and rows:
            self._attach_signal_day_vwaps(start_date, rows[-1]["date"], recommendations)
        return recommendations

    def _attach_signal_day_vwaps(self, start_date: date, end_date: date, recommendations: list[dict[str, object]]) -> None:
        if not recommendations:
            return
        symbols = {str(row["symbol"]) for row in recommendations}
        vwaps = self._load_persisted_vwaps(start_date, end_date, symbols)
        if not vwaps:
            vwaps = self._load_vwaps_from_candles(start_date, end_date, symbols)
        for row in recommendations:
            row["previous_day_vwap"] = vwaps.get((str(row["symbol"]), row["date"]))

    def _load_persisted_vwaps(self, start_date: date, end_date: date, symbols: set[str]) -> dict[tuple[str, date], float]:
        query = text(
            f"""
            SELECT symbol, date, daily_vwap
            FROM {self.pilot_schema}.daily_vwap
            WHERE symbol = ANY(:symbols)
              AND date BETWEEN :start_date AND :end_date
            """
        )
        try:
            with self.angel_engine.connect() as connection:
                rows = connection.execute(query, {"symbols": list(symbols), "start_date": start_date, "end_date": end_date}).mappings().all()
        except Exception:
            return {}
        return {(str(row["symbol"]), row["date"]): float(row["daily_vwap"]) for row in rows if row["daily_vwap"] is not None}

    def _load_vwaps_from_candles(self, start_date: date, end_date: date, symbols: set[str]) -> dict[tuple[str, date], float]:
        query = text(
            """
            SELECT symbol,
                   datetime::date AS date,
                   SUM(((high + low + close) / 3.0) * volume) / NULLIF(SUM(volume), 0) AS daily_vwap
            FROM ohlcv_15min
            WHERE symbol = ANY(:symbols)
              AND datetime::date BETWEEN :start_date AND :end_date
              AND volume > 0
            GROUP BY symbol, datetime::date
            """
        )
        with self.angel_engine.connect() as connection:
            rows = connection.execute(query, {"symbols": list(symbols), "start_date": start_date, "end_date": end_date}).mappings().all()
        return {(str(row["symbol"]), row["date"]): float(row["daily_vwap"]) for row in rows if row["daily_vwap"] is not None}

    def _load_prices(self, start_date: date, symbols: set[str]) -> dict[str, dict[date, dict[str, float]]]:
        if not symbols:
            return {}
        query = text(
            f"""
            SELECT symbol, date, open, high, low, close
            FROM {self.pilot_schema}.daily_bars_clean
            WHERE symbol = ANY(:symbols)
              AND date >= :start_date
            ORDER BY symbol ASC, date ASC
            """
        )
        with self.angel_engine.connect() as connection:
            rows = connection.execute(query, {"symbols": list(symbols), "start_date": start_date}).mappings().all()
        prices: dict[str, dict[date, dict[str, float]]] = {}
        for row in rows:
            open_price = row["open"]
            close_price = row["close"]
            if open_price is None and close_price is None:
                continue
            prices.setdefault(str(row["symbol"]), {})[row["date"]] = {
                "open": float(open_price if open_price is not None else close_price),
                "high": float(row["high"]) if row["high"] is not None else float(close_price or open_price),
                "low": float(row["low"]) if row["low"] is not None else float(close_price or open_price),
                "close": float(close_price if close_price is not None else open_price),
            }
        self._attach_1030_entries(start_date, symbols, prices)
        return prices

    def _attach_1030_entries(self, start_date: date, symbols: set[str], prices: dict[str, dict[date, dict[str, float]]]) -> None:
        if not symbols:
            return
        query = text(
            """
            SELECT symbol, datetime::date AS date, open
            FROM ohlcv_15min
            WHERE symbol = ANY(:symbols)
              AND datetime::date >= :start_date
              AND datetime::time = '10:30:00'
            ORDER BY symbol ASC, date ASC
            """
        )
        with self.angel_engine.connect() as connection:
            rows = connection.execute(query, {"symbols": list(symbols), "start_date": start_date}).mappings().all()
        for row in rows:
            symbol = str(row["symbol"])
            row_date = row["date"]
            if symbol in prices and row_date in prices[symbol] and row["open"] is not None:
                prices[symbol][row_date][FINAL_ENTRY_PRICE_FIELD] = float(row["open"])
