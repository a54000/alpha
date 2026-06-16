"""On-demand historical trade analysis for frozen Swing V2.1.

The service is analysis-only. It reads pilot recommendations and cleaned daily
bars, reconstructs trades with the existing hold-to-planned-exit lifecycle, and
writes report artifacts to the filesystem.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import statistics
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

REPO_ROOT = Path(__file__).resolve().parents[2]
MODEL = "swing_v2_1"
SUPPORTED_RECOMMENDATION_MODELS = {"swing_v2_1", "sector_rotation_adx_1m3m"}
DEFAULT_HOLDING_PERIOD = 20
KNOWN_SPECIAL_SESSIONS = {
    date(2022, 10, 24),
    date(2023, 11, 12),
    date(2024, 3, 2),
    date(2024, 5, 18),
    date(2024, 11, 1),
}


class TradeAnalysisError(RuntimeError):
    """Raised when trade analysis cannot be generated or loaded."""


class TradeAnalysisValidationError(ValueError):
    """Raised when user supplied analysis parameters are invalid."""


@dataclass(frozen=True)
class TradeAnalysisRequest:
    start_date: date
    end_date: date
    strategy: str
    initial_capital: float
    charge_model: str = "ZERODHA_DEFAULT"
    recommendation_model: str = MODEL


@dataclass(frozen=True)
class StrategyConfig:
    strategy: str
    name: str
    portfolio_size: int
    max_positions_per_sector: int | None = None
    max_candidate_rank: int | None = None
    holding_period: int = DEFAULT_HOLDING_PERIOD
    required_recommendation_model: str | None = None
    entry_price_field: str = "open"
    previous_day_vwap_max_extension: float | None = None


@dataclass
class AnalysisPosition:
    symbol: str
    sector: str | None
    signal_date: date
    entry_date: date
    entry_price: float
    quantity: float
    planned_exit_date: date
    rank: int
    score: float | None
    entry_value: float
    buy_charges: dict[str, float]


STRATEGIES = {
    "TOP5_WEEKLY": StrategyConfig("TOP5_WEEKLY", "Top 5 Weekly", portfolio_size=5),
    "TOP10_WEEKLY": StrategyConfig("TOP10_WEEKLY", "Top 10 Weekly", portfolio_size=10),
    "TOP10_SECTOR_CAP": StrategyConfig(
        "TOP10_SECTOR_CAP",
        "Top 10 Weekly + Max 2 Sector",
        portfolio_size=10,
        max_positions_per_sector=2,
        max_candidate_rank=50,
    ),
    "SECTOR_ROTATION_ADX_ROLLING10": StrategyConfig(
        "SECTOR_ROTATION_ADX_ROLLING10",
        "Sector Rotation ADX Rolling 10",
        portfolio_size=10,
        max_candidate_rank=5,
        required_recommendation_model="sector_rotation_adx_1m3m",
        entry_price_field="entry_1030_open",
        previous_day_vwap_max_extension=0.025,
    ),
}

ARTIFACTS = {
    "trades.csv",
    "summary.md",
    "summary.json",
    "metadata.json",
    "equity_curve.csv",
    "weekly_equity.csv",
    "weekly_equity.svg",
    "financial_year_returns.csv",
}


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


def validate_request(payload: TradeAnalysisRequest) -> None:
    if payload.start_date > payload.end_date:
        raise TradeAnalysisValidationError("start_date must be on or before end_date.")
    if payload.strategy not in STRATEGIES:
        raise TradeAnalysisValidationError(f"Unsupported strategy: {payload.strategy}.")
    if payload.recommendation_model not in SUPPORTED_RECOMMENDATION_MODELS:
        raise TradeAnalysisValidationError(f"Unsupported recommendation_model: {payload.recommendation_model}.")
    config = STRATEGIES[payload.strategy]
    if config.required_recommendation_model and payload.recommendation_model != config.required_recommendation_model:
        raise TradeAnalysisValidationError(
            f"{config.name} requires recommendation_model={config.required_recommendation_model}."
        )
    if payload.initial_capital <= 0:
        raise TradeAnalysisValidationError("initial_capital must be greater than zero.")
    if payload.charge_model != "ZERODHA_DEFAULT":
        raise TradeAnalysisValidationError("Only ZERODHA_DEFAULT charge model is currently implemented.")


def zerodha_default_charges(entry_value: float, exit_value: float) -> dict[str, float]:
    """Approximate Indian equity delivery charges for analysis.

    Rates are intentionally centralized and documented in Phase 6C docs. They
    are not used for live order placement.
    """

    turnover = entry_value + exit_value
    brokerage = 0.0
    stt = 0.001 * turnover
    exchange_charges = 0.0000297 * turnover
    sebi_charges = 0.000001 * turnover
    stamp_duty = 0.00015 * entry_value
    gst = 0.18 * (brokerage + exchange_charges + sebi_charges)
    total = brokerage + stt + exchange_charges + gst + sebi_charges + stamp_duty
    return {
        "brokerage": brokerage,
        "STT": stt,
        "exchange_charges": exchange_charges,
        "GST": gst,
        "SEBI_charges": sebi_charges,
        "stamp_duty": stamp_duty,
        "charges": total,
    }


def buy_side_charges(entry_value: float) -> dict[str, float]:
    # Exit value is zero here so cash deployment remains conservative at entry.
    return zerodha_default_charges(entry_value, 0.0)


def all_trading_dates(prices: dict[str, dict[date, dict[str, float]]]) -> list[date]:
    return sorted({price_date for symbol_prices in prices.values() for price_date in symbol_prices})


def symbol_dates(prices: dict[str, dict[date, dict[str, float]]], symbol: str) -> list[date]:
    return sorted(prices.get(symbol, {}))


def regular_session_dates(dates: list[date]) -> list[date]:
    return [item for item in sorted(dates) if item not in KNOWN_SPECIAL_SESSIONS]


def weekly_signal_dates(signal_dates: list[date]) -> list[date]:
    weekly: list[date] = []
    seen: set[tuple[int, int]] = set()
    for signal_date in sorted(signal_dates):
        year, week, _ = signal_date.isocalendar()
        key = (year, week)
        if key not in seen:
            weekly.append(signal_date)
            seen.add(key)
    return weekly


def next_trading_day_after(dates: list[date], signal_date: date) -> date | None:
    for trading_date in dates:
        if trading_date > signal_date:
            return trading_date
    return None


def nth_trading_day_after(dates: list[date], entry_date: date, periods: int) -> date | None:
    sessions = regular_session_dates(dates)
    try:
        index = sessions.index(entry_date)
    except ValueError:
        return None
    exit_index = index + periods - 1
    return sessions[exit_index] if exit_index < len(sessions) else None


def trading_day_distance(dates: list[date], start: date, end: date) -> int | None:
    sessions = regular_session_dates(dates)
    try:
        return sessions.index(end) - sessions.index(start) + 1
    except ValueError:
        return None


def positions_value(
    positions: list[AnalysisPosition],
    prices: dict[str, dict[date, dict[str, float]]],
    current_date: date,
    field: str,
) -> float:
    total = 0.0
    for position in positions:
        price = prices.get(position.symbol, {}).get(current_date, {}).get(field)
        if price is not None:
            total += position.quantity * price
    return total


def passes_sector_cap(sector: str | None, positions: list[AnalysisPosition], config: StrategyConfig) -> bool:
    if config.max_positions_per_sector is None:
        return True
    sector_name = sector or "UNKNOWN"
    count = sum(1 for position in positions if (position.sector or "UNKNOWN") == sector_name)
    return count < config.max_positions_per_sector


def total_charges(charges: dict[str, float]) -> float:
    return float(charges.get("charges") or 0.0)


def summarize_equity(equity_curve: list[dict[str, object]], initial_capital: float) -> dict[str, float | None]:
    if not equity_curve:
        return {"ending_value": initial_capital, "total_return": 0.0, "cagr": 0.0, "max_drawdown": 0.0}
    values = [float(row["equity"]) for row in equity_curve]
    ending_value = values[-1]
    total_return = ending_value / initial_capital - 1 if initial_capital else 0.0
    days = max(1, len(values))
    cagr = (ending_value / initial_capital) ** (252 / days) - 1 if initial_capital and ending_value > 0 else -1.0
    peak = values[0]
    max_drawdown = 0.0
    for value in values:
        peak = max(peak, value)
        if peak:
            max_drawdown = min(max_drawdown, value / peak - 1)
    return {"ending_value": ending_value, "total_return": total_return, "cagr": cagr, "max_drawdown": max_drawdown}


def summarize_trades(trades: list[dict[str, object]]) -> dict[str, object]:
    net_returns = [float(row["net_return_pct"]) for row in trades]
    winners = [row for row in trades if float(row["net_pnl"]) > 0]
    losers = [row for row in trades if float(row["net_pnl"]) < 0]
    winner_returns = [float(row["net_return_pct"]) for row in winners]
    loser_returns = [float(row["net_return_pct"]) for row in losers]
    gross_pnl = sum(float(row["gross_pnl"]) for row in trades)
    charges = sum(float(row["charges"]) for row in trades)
    net_pnl = sum(float(row["net_pnl"]) for row in trades)
    return {
        "total_trades": len(trades),
        "winners": len(winners),
        "losers": len(losers),
        "win_rate": len(winners) / len(trades) if trades else 0.0,
        "average_return": statistics.mean(net_returns) if net_returns else 0.0,
        "median_return": statistics.median(net_returns) if net_returns else 0.0,
        "average_winner": statistics.mean(winner_returns) if winner_returns else 0.0,
        "average_loser": statistics.mean(loser_returns) if loser_returns else 0.0,
        "gross_pnl": gross_pnl,
        "total_charges": charges,
        "net_pnl": net_pnl,
    }


def build_trade_row(
    trade_id: int,
    position: AnalysisPosition,
    exit_date: date,
    exit_price: float,
    dates: list[date],
    strategy: str,
) -> dict[str, object]:
    exit_value = position.quantity * exit_price
    charges = zerodha_default_charges(position.entry_value, exit_value)
    gross_pnl = exit_value - position.entry_value
    net_pnl = gross_pnl - total_charges(charges)
    return {
        "trade_id": trade_id,
        "symbol": position.symbol,
        "sector": position.sector,
        "strategy": strategy,
        "entry_date": position.entry_date.isoformat(),
        "entry_price": position.entry_price,
        "exit_date": exit_date.isoformat(),
        "exit_price": exit_price,
        "holding_days": trading_day_distance(dates, position.entry_date, exit_date),
        "quantity": position.quantity,
        "entry_value": position.entry_value,
        "exit_value": exit_value,
        "gross_pnl": gross_pnl,
        "gross_return_pct": gross_pnl / position.entry_value if position.entry_value else 0.0,
        "charges": total_charges(charges),
        "net_pnl": net_pnl,
        "net_return_pct": net_pnl / position.entry_value if position.entry_value else 0.0,
        "brokerage": charges["brokerage"],
        "STT": charges["STT"],
        "exchange_charges": charges["exchange_charges"],
        "GST": charges["GST"],
        "SEBI_charges": charges["SEBI_charges"],
        "stamp_duty": charges["stamp_duty"],
    }


def reconstruct_trades(
    request: TradeAnalysisRequest,
    recommendations: list[dict[str, object]],
    prices: dict[str, dict[date, dict[str, float]]],
) -> dict[str, object]:
    validate_request(request)
    config = STRATEGIES[request.strategy]
    dates = [item for item in all_trading_dates(prices) if request.start_date <= item <= request.end_date]
    if not recommendations or not dates:
        return {
            "summary": {
                **asdict(request),
                "ending_value": request.initial_capital,
                "total_return": 0.0,
                "cagr": 0.0,
                "max_drawdown": 0.0,
                "total_trades": 0,
                "total_charges": 0.0,
            },
            "trades": [],
            "equity_curve": [],
            "incomplete_positions_forced_closed": 0,
        }

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
    equity_curve: list[dict[str, object]] = []
    trade_id = 1

    for current_date in dates:
        remaining: list[AnalysisPosition] = []
        closed_today: set[str] = set()
        for position in positions:
            close_price = prices.get(position.symbol, {}).get(current_date, {}).get("close")
            if current_date >= position.planned_exit_date and close_price is not None:
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
                open_price = price_row.get(config.entry_price_field)
                if open_price is None or open_price <= 0:
                    continue
                previous_day_vwap = rec.get("previous_day_vwap")
                if (
                    config.previous_day_vwap_max_extension is not None
                    and previous_day_vwap is not None
                    and float(previous_day_vwap) > 0
                    and (float(open_price) / float(previous_day_vwap) - 1.0) > config.previous_day_vwap_max_extension
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
                if planned_exit is None:
                    planned_exit = dates[-1]
                quantity = allocation / open_price
                cash -= allocation + total_charges(buy_charges)
                positions.append(
                    AnalysisPosition(
                        symbol=symbol,
                        sector=str(sector) if sector is not None else None,
                        signal_date=rec["date"],
                        entry_date=current_date,
                        entry_price=open_price,
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
        equity_curve.append(
            {
                "date": current_date.isoformat(),
                "equity": equity,
                "cash": cash,
                "position_count": len(positions),
            }
        )

    forced = 0
    if dates:
        final_date = dates[-1]
        for position in positions:
            close_price = prices.get(position.symbol, {}).get(final_date, {}).get("close")
            if close_price is None:
                continue
            row = build_trade_row(trade_id, position, final_date, close_price, symbol_dates(prices, position.symbol), request.strategy)
            trades.append(row)
            cash += float(row["exit_value"]) - (float(row["charges"]) - total_charges(position.buy_charges))
            trade_id += 1
            forced += 1
        equity_curve[-1]["equity"] = cash
        equity_curve[-1]["cash"] = cash
        equity_curve[-1]["position_count"] = 0

    trade_summary = summarize_trades(trades)
    net_pnl = float(trade_summary["net_pnl"])
    ending_value = request.initial_capital + net_pnl
    equity_summary = summarize_equity(equity_curve, request.initial_capital)
    total_return = net_pnl / request.initial_capital if request.initial_capital else 0.0
    days = max(1, len(equity_curve))
    cagr = (ending_value / request.initial_capital) ** (252 / days) - 1 if request.initial_capital and ending_value > 0 else -1.0
    summary = {
        "start_date": request.start_date.isoformat(),
        "end_date": request.end_date.isoformat(),
        "strategy": request.strategy,
        "strategy_name": config.name,
        "recommendation_model": request.recommendation_model,
        "initial_capital": request.initial_capital,
        "charge_model": request.charge_model,
        "ending_value": ending_value,
        "total_return": total_return,
        "cagr": cagr,
        "max_drawdown": equity_summary["max_drawdown"],
        **trade_summary,
        "incomplete_positions_forced_closed": forced,
    }
    return {"summary": summary, "trades": trades, "equity_curve": equity_curve, "incomplete_positions_forced_closed": forced}


class TradeAnalysisService:
    def __init__(
        self,
        angel_database_url: str | None = None,
        reports_dir: Path | None = None,
        pilot_schema: str = "pilot_phase2a",
        angel_engine: Engine | None = None,
    ) -> None:
        research_url = os.environ.get("DATABASE_URL")
        self.angel_database_url = angel_database_url or os.environ.get("ANGEL_DATABASE_URL") or derive_angel_url(research_url)
        self.reports_dir = reports_dir or REPO_ROOT / "reports" / "trade_analysis"
        self.pilot_schema = pilot_schema
        self.angel_engine = angel_engine or (make_engine(self.angel_database_url) if self.angel_database_url else None)

    def run(self, request: TradeAnalysisRequest) -> dict[str, object]:
        validate_request(request)
        if self.angel_engine is None:
            raise TradeAnalysisError("ANGEL_DATABASE_URL is required for trade analysis.")
        cached = self._cached_report(request)
        if cached is not None:
            cached["cache_hit"] = True
            return cached
        try:
            recommendations = self._load_recommendations(request)
            symbols = {str(row["symbol"]) for row in recommendations}
            prices = self._load_prices(request, symbols)
            result = reconstruct_trades(request, recommendations, prices)
        except TradeAnalysisValidationError:
            raise
        except Exception as exc:
            raise TradeAnalysisError(f"Trade analysis data load failed: {exc}") from exc
        report_id = self._report_id(request)
        report_dir = self.reports_dir / report_id
        try:
            report_dir.mkdir(parents=True, exist_ok=True)
            artifacts = self._write_artifacts(report_id, report_dir, request, result, len(recommendations), len(symbols))
        except OSError as exc:
            raise TradeAnalysisError(f"Trade analysis artifact write failed: {exc}") from exc
        metadata = {
            "report_id": report_id,
            "status": "completed",
            "cache_hit": False,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "parameters": self._request_payload(request),
            "summary": result["summary"],
            "artifacts": artifacts,
            "inputs": {
                "recommendations": f"{self.pilot_schema}.recommendations_daily",
                "prices": f"{self.pilot_schema}.daily_bars_clean",
                "recommendation_rows": len(recommendations),
                "symbols": len(symbols),
            },
            "constraints": {
                "scoring_changed": False,
                "ranking_changed": False,
                "recommendations_changed": False,
                "strategy_rules_changed": False,
                "paper_trading_lifecycle_changed": False,
                "broker_apis_connected": False,
                "orders_placed": False,
            },
        }
        (report_dir / "metadata.json").write_text(json.dumps(metadata, indent=2, default=str), encoding="utf-8")
        return metadata

    def get(self, report_id: str) -> dict[str, object]:
        path = self.report_dir(report_id) / "metadata.json"
        if not path.exists():
            raise TradeAnalysisError(f"Trade analysis report not found: {report_id}")
        return json.loads(path.read_text(encoding="utf-8"))

    def artifact_path(self, report_id: str, artifact_name: str) -> Path:
        if artifact_name not in ARTIFACTS:
            raise TradeAnalysisError(f"Unsupported artifact: {artifact_name}")
        path = self.report_dir(report_id) / artifact_name
        if not path.exists():
            raise TradeAnalysisError(f"Artifact not found: {artifact_name}")
        return path

    def report_dir(self, report_id: str) -> Path:
        if not report_id or any(char in report_id for char in "/\\:"):
            raise TradeAnalysisError("Invalid report_id.")
        return self.reports_dir / report_id

    def _report_id(self, request: TradeAnalysisRequest) -> str:
        digest = self._cache_key(request)[:10]
        return f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}_{request.strategy.lower()}_{request.recommendation_model.lower()}_{digest}"

    @staticmethod
    def _request_payload(request: TradeAnalysisRequest) -> dict[str, object]:
        return {
            "start_date": request.start_date.isoformat(),
            "end_date": request.end_date.isoformat(),
            "strategy": request.strategy,
            "recommendation_model": request.recommendation_model,
            "initial_capital": request.initial_capital,
            "charge_model": request.charge_model,
        }

    def _cache_key(self, request: TradeAnalysisRequest) -> str:
        return hashlib.sha256(json.dumps(self._request_payload(request), sort_keys=True).encode("utf-8")).hexdigest()

    def _cached_report(self, request: TradeAnalysisRequest) -> dict[str, object] | None:
        expected = self._request_payload(request)
        if not self.reports_dir.exists():
            return None
        for path in sorted(self.reports_dir.glob("*/metadata.json"), key=lambda item: item.stat().st_mtime, reverse=True):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if payload.get("parameters") == expected and self._artifacts_exist(payload):
                return payload
        return None

    def _artifacts_exist(self, metadata: dict[str, object]) -> bool:
        artifacts = metadata.get("artifacts")
        if not isinstance(artifacts, dict):
            return False
        required = ["trades_csv", "summary_md", "summary_json", "financial_year_returns_csv"]
        return all(Path(str(artifacts.get(key, ""))).exists() for key in required)

    def _load_recommendations(self, request: TradeAnalysisRequest) -> list[dict[str, object]]:
        query = text(
            f"""
            SELECT
                r.date,
                r.model,
                r.rank,
                r.symbol,
                r.score,
                r.sector,
                f.adx_14,
                f.ema200_extension,
                f.prior_20d_return,
                f.sector_rank_3m
            FROM {self.pilot_schema}.recommendations_daily r
            LEFT JOIN {self.pilot_schema}.features_daily f
              ON f.symbol = r.symbol
             AND f.date = r.date
            WHERE r.model = :model
              AND r.date BETWEEN :start_date AND :end_date
            ORDER BY r.date ASC, r.rank ASC, r.symbol ASC
            """
        )
        with self.angel_engine.connect() as connection:
            rows = connection.execute(
                query,
                {"model": request.recommendation_model, "start_date": request.start_date, "end_date": request.end_date},
            ).mappings().all()
        recommendations = [
            {
                "date": row["date"],
                "model": row["model"],
                "rank": int(row["rank"]),
                "symbol": row["symbol"],
                "score": float(row["score"]) if row["score"] is not None else None,
                "sector": row["sector"],
                "adx_14": float(row["adx_14"]) if row["adx_14"] is not None else None,
                "ema200_extension": float(row["ema200_extension"]) if row["ema200_extension"] is not None else None,
                "prior_20d_return": float(row["prior_20d_return"]) if row["prior_20d_return"] is not None else None,
                "sector_rank_3m": int(row["sector_rank_3m"]) if row["sector_rank_3m"] is not None else None,
                "previous_day_vwap": None,
            }
            for row in rows
        ]
        if STRATEGIES[request.strategy].previous_day_vwap_max_extension is not None:
            self._attach_signal_day_vwaps(request, recommendations)
        return recommendations

    def _attach_signal_day_vwaps(self, request: TradeAnalysisRequest, recommendations: list[dict[str, object]]) -> None:
        if not recommendations:
            return
        symbols = {str(row["symbol"]) for row in recommendations}
        vwaps = self._load_persisted_vwaps(request, symbols)
        if not vwaps:
            vwaps = self._load_vwaps_from_candles(request, symbols)
        for row in recommendations:
            row["previous_day_vwap"] = vwaps.get((str(row["symbol"]), row["date"]))

    def _load_persisted_vwaps(self, request: TradeAnalysisRequest, symbols: set[str]) -> dict[tuple[str, date], float]:
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
                rows = connection.execute(
                    query,
                    {"symbols": list(symbols), "start_date": request.start_date, "end_date": request.end_date},
                ).mappings().all()
        except Exception:
            return {}
        return {(str(row["symbol"]), row["date"]): float(row["daily_vwap"]) for row in rows if row["daily_vwap"] is not None}

    def _load_vwaps_from_candles(self, request: TradeAnalysisRequest, symbols: set[str]) -> dict[tuple[str, date], float]:
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
            rows = connection.execute(
                query,
                {"symbols": list(symbols), "start_date": request.start_date, "end_date": request.end_date},
            ).mappings().all()
        return {(str(row["symbol"]), row["date"]): float(row["daily_vwap"]) for row in rows if row["daily_vwap"] is not None}

    def _load_prices(self, request: TradeAnalysisRequest, symbols: set[str]) -> dict[str, dict[date, dict[str, float]]]:
        if not symbols:
            return {}
        query = text(
            f"""
            SELECT symbol, date, open, high, low, close
            FROM {self.pilot_schema}.daily_bars_clean
            WHERE symbol = ANY(:symbols)
              AND date BETWEEN :start_date AND :end_date
            ORDER BY symbol ASC, date ASC
            """
        )
        with self.angel_engine.connect() as connection:
            rows = connection.execute(
                query,
                {"symbols": list(symbols), "start_date": request.start_date, "end_date": request.end_date},
            ).mappings().all()
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
        self._attach_1030_entries(request, symbols, prices)
        return prices

    def _attach_1030_entries(self, request: TradeAnalysisRequest, symbols: set[str], prices: dict[str, dict[date, dict[str, float]]]) -> None:
        if request.strategy != "SECTOR_ROTATION_ADX_ROLLING10" or not symbols:
            return
        query = text(
            """
            SELECT symbol, datetime::date AS date, open
            FROM ohlcv_15min
            WHERE symbol = ANY(:symbols)
              AND datetime::date BETWEEN :start_date AND :end_date
              AND datetime::time = '10:30:00'
            ORDER BY symbol ASC, date ASC
            """
        )
        with self.angel_engine.connect() as connection:
            rows = connection.execute(query, {"symbols": list(symbols), "start_date": request.start_date, "end_date": request.end_date}).mappings().all()
        for row in rows:
            symbol = str(row["symbol"])
            row_date = row["date"]
            if symbol in prices and row_date in prices[symbol] and row["open"] is not None:
                prices[symbol][row_date]["entry_1030_open"] = float(row["open"])

    def _write_artifacts(
        self,
        report_id: str,
        report_dir: Path,
        request: TradeAnalysisRequest,
        result: dict[str, object],
        recommendation_rows: int,
        symbols: int,
    ) -> dict[str, str]:
        trades = result["trades"]
        equity_curve = result["equity_curve"]
        summary = result["summary"]
        weekly_equity = weekly_equity_curve(equity_curve)
        fy_returns = financial_year_returns(equity_curve)
        summary["financial_year_returns"] = fy_returns
        self._write_csv(report_dir / "trades.csv", trades)
        self._write_csv(report_dir / "equity_curve.csv", equity_curve)
        self._write_csv(report_dir / "weekly_equity.csv", weekly_equity)
        self._write_csv(report_dir / "financial_year_returns.csv", fy_returns)
        (report_dir / "weekly_equity.svg").write_text(render_weekly_equity_svg(weekly_equity), encoding="utf-8")
        (report_dir / "summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
        (report_dir / "summary.md").write_text(
            render_summary_markdown(report_id, request, summary, trades, recommendation_rows, symbols, weekly_equity, fy_returns),
            encoding="utf-8",
        )
        return {
            "trades_csv": str(report_dir / "trades.csv"),
            "summary_md": str(report_dir / "summary.md"),
            "summary_json": str(report_dir / "summary.json"),
            "equity_curve_csv": str(report_dir / "equity_curve.csv"),
            "weekly_equity_csv": str(report_dir / "weekly_equity.csv"),
            "weekly_equity_svg": str(report_dir / "weekly_equity.svg"),
            "financial_year_returns_csv": str(report_dir / "financial_year_returns.csv"),
            "metadata_json": str(report_dir / "metadata.json"),
        }

    @staticmethod
    def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        if not rows:
            path.write_text("", encoding="utf-8")
            return
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)


def fmt_money(value: object) -> str:
    return "n/a" if value is None else f"{float(value):,.2f}"


def fmt_pct(value: object) -> str:
    return "n/a" if value is None else f"{float(value) * 100:.2f}%"


def top_rows(trades: list[dict[str, object]], key: str, reverse: bool, limit: int = 5) -> list[dict[str, object]]:
    return sorted(trades, key=lambda row: float(row.get(key) or 0), reverse=reverse)[:limit]


def weekly_equity_curve(equity_curve: list[dict[str, object]]) -> list[dict[str, object]]:
    by_week: dict[tuple[int, int], dict[str, object]] = {}
    for row in equity_curve:
        row_date = date.fromisoformat(str(row["date"]))
        year, week, _ = row_date.isocalendar()
        by_week[(year, week)] = row
    rows = []
    previous_equity = None
    for key in sorted(by_week):
        row = by_week[key]
        equity = float(row["equity"])
        rows.append(
            {
                "week": f"{key[0]}-W{key[1]:02d}",
                "date": row["date"],
                "equity": equity,
                "weekly_return": (equity / previous_equity - 1) if previous_equity else None,
            }
        )
        previous_equity = equity
    return rows


def financial_year_label(row_date: date) -> str:
    start_year = row_date.year if row_date.month >= 4 else row_date.year - 1
    return f"FY{start_year}-{str(start_year + 1)[-2:]}"


def financial_year_returns(equity_curve: list[dict[str, object]]) -> list[dict[str, object]]:
    by_fy: dict[str, list[dict[str, object]]] = {}
    for row in equity_curve:
        row_date = date.fromisoformat(str(row["date"]))
        by_fy.setdefault(financial_year_label(row_date), []).append(row)

    rows: list[dict[str, object]] = []
    for fy_label in sorted(by_fy):
        year_rows = sorted(by_fy[fy_label], key=lambda item: str(item["date"]))
        start_equity = float(year_rows[0]["equity"])
        end_equity = float(year_rows[-1]["equity"])
        rows.append(
            {
                "financial_year": fy_label,
                "start_date": year_rows[0]["date"],
                "end_date": year_rows[-1]["date"],
                "start_equity": start_equity,
                "end_equity": end_equity,
                "return_pct": (end_equity / start_equity - 1) if start_equity else None,
                "trading_days": len(year_rows),
            }
        )
    return rows


def render_weekly_equity_svg(weekly_equity: list[dict[str, object]]) -> str:
    width = 920
    height = 320
    margin_left = 72
    margin_right = 24
    margin_top = 24
    margin_bottom = 44
    plot_width = width - margin_left - margin_right
    plot_height = height - margin_top - margin_bottom
    if not weekly_equity:
        return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <rect width="100%" height="100%" fill="#ffffff"/>
  <text x="{width / 2}" y="{height / 2}" text-anchor="middle" font-family="Arial, sans-serif" font-size="16" fill="#657184">No weekly equity data</text>
</svg>
"""
    values = [float(row["equity"]) for row in weekly_equity]
    min_value = min(values)
    max_value = max(values)
    if math.isclose(min_value, max_value):
        min_value *= 0.99
        max_value *= 1.01
    span = max_value - min_value
    points = []
    for index, value in enumerate(values):
        x = margin_left + (plot_width * index / max(1, len(values) - 1))
        y = margin_top + plot_height - ((value - min_value) / span * plot_height)
        points.append((x, y))
    polyline = " ".join(f"{x:.2f},{y:.2f}" for x, y in points)
    first = weekly_equity[0]["date"]
    last = weekly_equity[-1]["date"]
    y_ticks = []
    for step in range(5):
        value = min_value + span * step / 4
        y = margin_top + plot_height - (plot_height * step / 4)
        y_ticks.append((value, y))
    tick_lines = "\n".join(
        f'  <line x1="{margin_left}" y1="{y:.2f}" x2="{width - margin_right}" y2="{y:.2f}" stroke="#eef1f5"/>\n'
        f'  <text x="{margin_left - 10}" y="{y + 4:.2f}" text-anchor="end" font-family="Arial, sans-serif" font-size="12" fill="#657184">{value:,.0f}</text>'
        for value, y in y_ticks
    )
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <rect width="100%" height="100%" fill="#ffffff"/>
  <text x="{margin_left}" y="18" font-family="Arial, sans-serif" font-size="15" font-weight="700" fill="#17202a">Weekly Equity Curve</text>
{tick_lines}
  <line x1="{margin_left}" y1="{margin_top}" x2="{margin_left}" y2="{height - margin_bottom}" stroke="#d9dee7"/>
  <line x1="{margin_left}" y1="{height - margin_bottom}" x2="{width - margin_right}" y2="{height - margin_bottom}" stroke="#d9dee7"/>
  <polyline fill="none" stroke="#0f766e" stroke-width="3" points="{polyline}"/>
  <circle cx="{points[0][0]:.2f}" cy="{points[0][1]:.2f}" r="4" fill="#345995"/>
  <circle cx="{points[-1][0]:.2f}" cy="{points[-1][1]:.2f}" r="4" fill="#0f766e"/>
  <text x="{margin_left}" y="{height - 16}" font-family="Arial, sans-serif" font-size="12" fill="#657184">{first}</text>
  <text x="{width - margin_right}" y="{height - 16}" text-anchor="end" font-family="Arial, sans-serif" font-size="12" fill="#657184">{last}</text>
</svg>
"""


def render_trade_table(rows: list[dict[str, object]]) -> list[str]:
    if not rows:
        return ["_No trades._"]
    output = ["| Symbol | Entry | Exit | Net PnL | Net Return |", "| --- | --- | --- | ---: | ---: |"]
    for row in rows:
        output.append(
            f"| {row['symbol']} | {row['entry_date']} | {row['exit_date']} | {fmt_money(row['net_pnl'])} | {fmt_pct(row['net_return_pct'])} |"
        )
    return output


def render_summary_markdown(
    report_id: str,
    request: TradeAnalysisRequest,
    summary: dict[str, object],
    trades: list[dict[str, object]],
    recommendation_rows: int,
    symbols: int,
    weekly_equity: list[dict[str, object]],
    fy_returns: list[dict[str, object]],
) -> str:
    winners = top_rows(trades, "net_pnl", True)
    losers = top_rows(trades, "net_pnl", False)
    lines = [
        f"# Trade Analysis Summary - {report_id}",
        "",
        "## Parameters",
        "",
        f"- Date range: {request.start_date.isoformat()} to {request.end_date.isoformat()}",
        f"- Strategy: {STRATEGIES[request.strategy].name}",
        f"- Starting capital: {fmt_money(request.initial_capital)}",
        f"- Charge model: {request.charge_model}",
        f"- Recommendation rows read: {recommendation_rows}",
        f"- Symbols read: {symbols}",
        "",
        "## Portfolio",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
        f"| Starting capital | {fmt_money(summary.get('initial_capital'))} |",
        f"| Ending value | {fmt_money(summary.get('ending_value'))} |",
        f"| Total return | {fmt_pct(summary.get('total_return'))} |",
        f"| CAGR | {fmt_pct(summary.get('cagr'))} |",
        f"| Max drawdown | {fmt_pct(summary.get('max_drawdown'))} |",
        "",
        "## Financial Year Returns",
        "",
        "| FY | Start Date | End Date | Start Equity | End Equity | Return | Trading Days |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: |",
        *[
            f"| {row['financial_year']} | {row['start_date']} | {row['end_date']} | {fmt_money(row['start_equity'])} | {fmt_money(row['end_equity'])} | {fmt_pct(row.get('return_pct'))} | {row['trading_days']} |"
            for row in fy_returns
        ],
        "",
        "## Weekly Equity Curve",
        "",
        "![Weekly Equity Curve](weekly_equity.svg)",
        "",
        "| Week | Date | Equity | Weekly Return |",
        "| --- | --- | ---: | ---: |",
        *[
            f"| {row['week']} | {row['date']} | {fmt_money(row['equity'])} | {fmt_pct(row.get('weekly_return'))} |"
            for row in weekly_equity[-12:]
        ],
        "",
        "## Trades",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
        f"| Total trades | {summary.get('total_trades')} |",
        f"| Winners | {summary.get('winners')} |",
        f"| Losers | {summary.get('losers')} |",
        f"| Win rate | {fmt_pct(summary.get('win_rate'))} |",
        f"| Average winner | {fmt_pct(summary.get('average_winner'))} |",
        f"| Average loser | {fmt_pct(summary.get('average_loser'))} |",
        f"| Total charges | {fmt_money(summary.get('total_charges'))} |",
        "",
        "## Top 5 Winners",
        "",
        *render_trade_table(winners),
        "",
        "## Top 5 Losers",
        "",
        *render_trade_table(losers),
        "",
        "## Constraints",
        "",
        "- Scoring changed: no",
        "- Ranking changed: no",
        "- Recommendation generation changed: no",
        "- Strategy rules changed: no",
        "- Broker APIs connected: no",
        "- Orders placed: no",
    ]
    return "\n".join(lines) + "\n"
