"""Read-only data access for the Swing Research Cockpit API."""

from __future__ import annotations

import json
import logging
import os
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine

REPO_ROOT = Path(__file__).resolve().parents[2]
LOGGER = logging.getLogger(__name__)


class CockpitConfigurationError(RuntimeError):
    """Raised when the cockpit API is missing required runtime configuration."""


class CockpitDatabaseError(RuntimeError):
    """Raised when a configured cockpit database cannot satisfy a read query."""


def derive_angel_url(research_database_url: str | None, database_name: str = "angel_data") -> str | None:
    if not research_database_url:
        return None
    parts = urlsplit(research_database_url)
    return urlunsplit((parts.scheme, parts.netloc, f"/{database_name}", parts.query, parts.fragment))


def make_engine(database_url: str | None) -> Engine | None:
    if not database_url:
        return None
    return create_engine(database_url, future=True)


class CockpitReadService:
    """Read-only dashboard queries with graceful empty-state handling."""

    def __init__(
        self,
        research_database_url: str | None = None,
        angel_database_url: str | None = None,
        paper_portfolio_id: int | None = None,
        reports_dir: Path | None = None,
        pilot_schema: str = "pilot_phase2a",
        research_engine: Engine | None = None,
        angel_engine: Engine | None = None,
        validate_config: bool = True,
    ) -> None:
        self.research_database_url = research_database_url or os.environ.get("DATABASE_URL")
        self.angel_database_url = angel_database_url or os.environ.get("ANGEL_DATABASE_URL")
        self.paper_portfolio_id = paper_portfolio_id if paper_portfolio_id is not None else self._env_portfolio_id()
        if validate_config:
            self.validate_configuration()
        self.research_engine = research_engine or make_engine(self.research_database_url)
        self.angel_engine = angel_engine or make_engine(self.angel_database_url)
        self.reports_dir = reports_dir or REPO_ROOT / "reports"
        self.results_dir = REPO_ROOT / "results"
        self.pilot_schema = pilot_schema

    @staticmethod
    def _env_portfolio_id() -> int | None:
        value = os.environ.get("PAPER_PORTFOLIO_ID")
        if not value:
            return None
        try:
            return int(value)
        except ValueError as exc:
            raise CockpitConfigurationError("PAPER_PORTFOLIO_ID must be an integer.") from exc

    def validate_configuration(self) -> None:
        missing = []
        if not self.research_database_url:
            missing.append("DATABASE_URL")
        if not self.angel_database_url:
            missing.append("ANGEL_DATABASE_URL")
        if self.paper_portfolio_id is None:
            missing.append("PAPER_PORTFOLIO_ID")
        if missing:
            raise CockpitConfigurationError(f"Missing required cockpit configuration: {', '.join(missing)}.")
        if self.research_database_url == self.angel_database_url:
            raise CockpitConfigurationError("DATABASE_URL and ANGEL_DATABASE_URL must point to separate databases.")

    def dashboard(self) -> dict[str, object]:
        portfolio = self.portfolio()
        status = self.pipeline_status()
        metrics = self.research_metrics()
        return {
            "portfolio": portfolio.get("summary", {}),
            "risk": portfolio.get("risk", {}),
            "benchmark": portfolio.get("benchmark", {}),
            "system_health": status.get("summary", {}),
            "research": metrics.get("summary", {}),
            "read_only": True,
        }

    def latest_recommendations(self, model: str = "swing_v2_1", limit: int = 20) -> dict[str, object]:
        latest = self._scalar(self.angel_engine, f"SELECT MAX(date) FROM {self.pilot_schema}.recommendations_daily WHERE model = :model", {"model": model})
        source = "pilot_phase2a.recommendations_daily"
        if latest is None:
            latest = self._scalar(self.research_engine, "SELECT MAX(date) FROM recommendation_history WHERE model = :model", {"model": model})
            source = "recommendation_history"
        if latest is None:
            return {"date": None, "model": model, "source": source, "recommendations": []}
        if source.startswith("pilot"):
            rows = self._mappings(
                self.angel_engine,
                f"""
                SELECT symbol, rank, score, sector, adx_points, sector_points, ema200_extension,
                       prior_20d_return, sector_rank_3m
                FROM {self.pilot_schema}.recommendations_daily
                WHERE date = :date AND model = :model
                  AND COALESCE(sector_points, 0) > 0
                ORDER BY rank ASC, symbol ASC
                LIMIT :limit
                """,
                {"date": latest, "model": model, "limit": limit},
            )
        else:
            rows = self._mappings(
                self.research_engine,
                """
                SELECT rh.symbol, rh.rank, rh.score, sm.sector, rh.adx_14, rh.sector_rank,
                       rh.reason_codes
                FROM recommendation_history rh
                LEFT JOIN symbol_master sm ON sm.symbol = rh.symbol
                WHERE rh.date = :date AND rh.model = :model
                ORDER BY rh.rank ASC, rh.symbol ASC
                LIMIT :limit
                """,
                {"date": latest, "model": model, "limit": limit},
            )
        current_symbols = {str(row.get("symbol")) for row in rows if row.get("symbol")}
        paper_update = self._read_json("latest_paper_update.json") or {}
        return {
            "date": self._iso(latest),
            "model": model,
            "source": source,
            "recommendations": self._jsonable(rows),
            "paper_update": self._recommendation_paper_update(paper_update, current_symbols, latest),
        }

    def recommendation_explanation(
        self,
        symbol: str,
        recommendation_type: str = "swing_v2_1",
        business_date: date | None = None,
    ) -> dict[str, object]:
        symbol = symbol.upper()
        date_filter = "AND business_date = :business_date" if business_date else ""
        params: dict[str, object] = {"symbol": symbol, "recommendation_type": recommendation_type}
        if business_date:
            params["business_date"] = business_date
        rows = self._mappings(
            self.research_engine,
            f"""
            SELECT business_date, symbol, rank, score, recommendation_type, sector,
                   feature_snapshot_json, created_at
            FROM recommendation_decision_journal
            WHERE symbol = :symbol
              AND recommendation_type = :recommendation_type
              {date_filter}
            ORDER BY business_date DESC, rank ASC
            LIMIT 1
            """,
            params,
        )
        if rows:
            row = rows[0]
            snapshot = row.get("feature_snapshot_json") or {}
            if isinstance(snapshot, str):
                try:
                    snapshot = json.loads(snapshot)
                except json.JSONDecodeError:
                    snapshot = {"raw": snapshot}
            return {
                "source": "recommendation_decision_journal",
                "business_date": self._iso(row.get("business_date")),
                "symbol": row.get("symbol"),
                "rank": row.get("rank"),
                "score": row.get("score"),
                "recommendation_type": row.get("recommendation_type"),
                "sector": row.get("sector"),
                "feature_snapshot": self._jsonable(snapshot),
                "created_at": self._iso(row.get("created_at")),
            }

        latest = business_date or self._scalar(
            self.angel_engine,
            f"SELECT MAX(date) FROM {self.pilot_schema}.recommendations_daily WHERE model = :model AND symbol = :symbol",
            {"model": recommendation_type, "symbol": symbol},
        )
        if latest is None:
            return {
                "source": "none",
                "business_date": None,
                "symbol": symbol,
                "recommendation_type": recommendation_type,
                "feature_snapshot": {},
            }
        fallback = self._mappings(
            self.angel_engine,
            f"""
            SELECT
                r.date AS business_date,
                r.symbol,
                r.rank,
                r.score,
                r.model AS recommendation_type,
                r.sector,
                f.sector_rank_3m,
                f.adx_14,
                f.ema_200,
                f.ema200_extension,
                f.prior_20d_return
            FROM {self.pilot_schema}.recommendations_daily r
            LEFT JOIN {self.pilot_schema}.features_daily f
              ON f.symbol = r.symbol
             AND f.date = r.date
            WHERE r.date = :business_date
              AND r.model = :model
              AND r.symbol = :symbol
            ORDER BY r.rank ASC
            LIMIT 1
            """,
            {"business_date": latest, "model": recommendation_type, "symbol": symbol},
        )
        if not fallback:
            return {
                "source": "none",
                "business_date": self._iso(latest),
                "symbol": symbol,
                "recommendation_type": recommendation_type,
                "feature_snapshot": {},
            }
        row = fallback[0]
        return {
            "source": f"{self.pilot_schema}.recommendations_daily",
            "business_date": self._iso(row.get("business_date")),
            "symbol": row.get("symbol"),
            "rank": row.get("rank"),
            "score": row.get("score"),
            "recommendation_type": row.get("recommendation_type"),
            "sector": row.get("sector"),
            "feature_snapshot": self._jsonable(
                {
                    "sector_rank_3m": row.get("sector_rank_3m"),
                    "adx_14": row.get("adx_14"),
                    "ema_200": row.get("ema_200"),
                    "ema200_extension": row.get("ema200_extension"),
                    "prior_20d_return": row.get("prior_20d_return"),
                    "final_score": row.get("score"),
                }
            ),
            "created_at": None,
        }

    def portfolio(self, portfolio_id: int | None = None) -> dict[str, object]:
        portfolio_id = portfolio_id or self._default_portfolio_id()
        if not portfolio_id:
            return {"summary": {}, "positions": [], "trades": [], "risk": {}, "benchmark": {}}
        portfolio = self._mappings(
            self.research_engine,
            """
            SELECT portfolio_id, name, strategy, portfolio_size, initial_capital, cash,
                   current_nav, benchmark_symbol, status
            FROM paper_portfolios
            WHERE portfolio_id = :portfolio_id
            """,
            {"portfolio_id": portfolio_id},
        )
        snapshot = self._mappings(
            self.research_engine,
            """
            SELECT date, cash, market_value, nav, realized_pnl, unrealized_pnl,
                   turnover, benchmark_close, benchmark_return, open_positions
            FROM paper_daily_snapshots
            WHERE portfolio_id = :portfolio_id
            ORDER BY date DESC
            LIMIT 1
            """,
            {"portfolio_id": portfolio_id},
        )
        positions = self._mappings(
            self.research_engine,
            """
            SELECT symbol, sector, entry_date, entry_price, quantity, capital_allocated,
                   current_price, market_value, unrealized_pnl, planned_exit_date, status
            FROM paper_positions
            WHERE portfolio_id = :portfolio_id
            ORDER BY status DESC, market_value DESC NULLS LAST, symbol ASC
            """,
            {"portfolio_id": portfolio_id},
        )
        trades = self.trades(portfolio_id=portfolio_id, limit=25).get("trades", [])
        nav_history = self._mappings(
            self.research_engine,
            """
            SELECT date, nav
            FROM paper_daily_snapshots
            WHERE portfolio_id = :portfolio_id
            ORDER BY date ASC
            """,
            {"portfolio_id": portfolio_id},
        )
        risk = self._risk(snapshot[0] if snapshot else {}, positions, nav_history)
        benchmark_return = None
        if portfolio and snapshot:
            benchmark_return = self._benchmark_return_since_start(
                str(portfolio[0].get("benchmark_symbol") or "NIFTY500"),
                portfolio_id,
                snapshot[0].get("date"),
            )
        if benchmark_return is None and snapshot:
            benchmark_return = snapshot[0].get("benchmark_return")
        benchmark = {
            "symbol": portfolio[0].get("benchmark_symbol") if portfolio else None,
            "close": snapshot[0].get("benchmark_close") if snapshot else None,
            "return": benchmark_return,
            "return_start_date": self._benchmark_start_date(portfolio_id) if portfolio and snapshot else None,
            "latest_available_date": self._latest_benchmark_date(str(portfolio[0].get("benchmark_symbol") or "NIFTY500")) if portfolio else None,
            "nav_return": self._nav_return(portfolio[0] if portfolio else {}, snapshot[0] if snapshot else {}),
        }
        paper_update = self._read_json("latest_paper_update.json") or {}
        paper_update_message = self._paper_update_message(paper_update)
        return {
            "summary": self._jsonable(
                {
                    **(portfolio[0] if portfolio else {}),
                    **(snapshot[0] if snapshot else {}),
                    "latest_paper_update_message": paper_update_message,
                }
            ),
            "positions": self._jsonable(positions),
            "trades": trades,
            "risk": risk,
            "benchmark": self._jsonable(benchmark),
            "paper_update": self._jsonable(paper_update),
        }

    def _benchmark_return_since_start(self, symbol: str, portfolio_id: int, latest_date: object | None) -> float | None:
        if latest_date is None:
            return None
        start_date = self._benchmark_start_date(portfolio_id)
        if start_date is None:
            return None
        rows = self._mappings(
            self.research_engine,
            """
            SELECT date, close
            FROM index_prices_daily
            WHERE index_name = :symbol
              AND date >= :start_date
              AND date <= :latest_date
            ORDER BY date ASC
            """,
            {"symbol": symbol, "start_date": start_date, "latest_date": latest_date},
        )
        if len(rows) < 2:
            return None
        start_close = self._float(rows[0].get("close"))
        latest_close = self._float(rows[-1].get("close"))
        if not start_close or latest_close is None:
            return None
        return (latest_close / start_close) - 1

    def _benchmark_start_date(self, portfolio_id: int):
        rows = self._mappings(
            self.research_engine,
            """
            SELECT MIN(entry_date) AS start_date
            FROM (
                SELECT entry_date FROM paper_positions WHERE portfolio_id = :portfolio_id
                UNION ALL
                SELECT entry_date FROM paper_trades WHERE portfolio_id = :portfolio_id
            ) AS entries
            """,
            {"portfolio_id": portfolio_id},
        )
        return rows[0].get("start_date") if rows else None

    def _latest_benchmark_date(self, symbol: str):
        return self._scalar(
            self.research_engine,
            """
            SELECT MAX(date)
            FROM index_prices_daily
            WHERE index_name = :symbol
            """,
            {"symbol": symbol},
        )

    @staticmethod
    def _nav_return(portfolio: dict[str, object], snapshot: dict[str, object]) -> float | None:
        initial_capital = CockpitReadService._float(portfolio.get("initial_capital"))
        nav = CockpitReadService._float(snapshot.get("nav") or portfolio.get("current_nav"))
        if not initial_capital or nav is None:
            return None
        return (nav / initial_capital) - 1

    def _paper_update_message(self, paper_update: dict[str, object]) -> str | None:
        validation = paper_update.get("validation") if isinstance(paper_update, dict) else None
        if not isinstance(validation, list):
            return None
        for step in validation:
            if not isinstance(step, dict) or step.get("step") != "rebalance_weekly":
                continue
            entered = step.get("symbols_entered") if isinstance(step.get("symbols_entered"), list) else []
            skipped = step.get("symbols_skipped") if isinstance(step.get("symbols_skipped"), list) else []
            if entered:
                return f"Entered {len(entered)} symbol(s): {', '.join(map(str, entered))}."
            if skipped:
                first = skipped[0] if isinstance(skipped[0], dict) else {}
                symbol = first.get("symbol") or "candidate"
                reason = first.get("reason") or "skipped"
                entry_date = first.get("candidate_entry_date") or step.get("price_date_used")
                if reason == "missing_or_invalid_entry_price":
                    return f"{symbol} skipped: missing required 10:30 entry candle for {entry_date or 'entry day'}."
                if reason == "entry_gt_prevday_vwap_threshold":
                    pct = first.get("entry_vs_reference_vwap_pct")
                    suffix = f" ({float(pct) * 100:.2f}% above VWAP)" if pct is not None else ""
                    return f"{symbol} skipped: entry above previous-day VWAP threshold{suffix}."
                return f"{symbol} skipped: {reason}."
        return None

    def _recommendation_paper_update(
        self,
        paper_update: dict[str, object],
        current_symbols: set[str],
        recommendation_date: object,
    ) -> dict[str, object] | None:
        validation = paper_update.get("validation") if isinstance(paper_update, dict) else None
        if not isinstance(validation, list):
            return None
        for step in validation:
            if not isinstance(step, dict) or step.get("step") != "rebalance_weekly":
                continue
            if self._iso(step.get("recommendation_date_used")) != self._iso(recommendation_date):
                return None
            entered = step.get("symbols_entered") if isinstance(step.get("symbols_entered"), list) else []
            skipped = step.get("symbols_skipped") if isinstance(step.get("symbols_skipped"), list) else []
            entered = [str(symbol) for symbol in entered if str(symbol) in current_symbols]
            considered = [
                str(symbol)
                for symbol in (step.get("symbols_considered") if isinstance(step.get("symbols_considered"), list) else [])
                if str(symbol) in current_symbols
            ]
            skipped_rows = []
            for item in skipped:
                if not isinstance(item, dict):
                    continue
                symbol = str(item.get("symbol") or "")
                if symbol not in current_symbols:
                    continue
                skipped_rows.append(
                    {
                        "symbol": symbol,
                        "reason": item.get("reason"),
                        "message": self._paper_skip_message(item, step),
                    }
                )
            return self._jsonable(
                {
                    "recommendation_date_used": step.get("recommendation_date_used"),
                    "price_date_used": step.get("price_date_used"),
                    "symbols_considered": considered,
                    "symbols_entered": entered,
                    "symbols_skipped": skipped_rows,
                }
            )
        return None

    def _paper_skip_message(self, item: dict[str, object], step: dict[str, object]) -> str:
        symbol = item.get("symbol") or "Candidate"
        reason = item.get("reason") or "skipped"
        entry_date = item.get("candidate_entry_date") or step.get("price_date_used")
        if reason == "missing_or_invalid_entry_price":
            return f"{symbol} was not entered because the required entry price was not available for {entry_date or 'the entry day'}."
        if reason == "entry_gt_prevday_vwap_threshold":
            return f"{symbol} was not entered because it did not pass the entry-quality check."
        if reason == "no_next_trading_day":
            return f"{symbol} was not entered because the required entry price was not available."
        if reason == "already_held":
            return f"{symbol} was not entered because it is already held in the paper portfolio."
        if reason == "portfolio_full":
            return f"{symbol} was not entered because all portfolio slots are already in use."
        if reason == "insufficient_cash":
            return f"{symbol} was not entered because available cash was not sufficient."
        return f"{symbol} was not entered: {reason}."

    def portfolio_attribution(self, portfolio_id: int | None = None) -> dict[str, object]:
        report = self._read_json("phase6a_performance_attribution.json")
        if report:
            return report
        try:
            from scripts.generate_performance_attribution import build_report

            metrics = self._read_json("phase2e_portfolio_metrics.json")
            return self._jsonable(
                build_report(
                    self.research_engine,
                    portfolio_id or self._default_portfolio_id(),
                    date.today(),
                    metrics,
                )
            )
        except Exception:
            return {
                "mode": "phase6a_performance_attribution",
                "summary": {},
                "position_contribution": [],
                "sector_attribution": [],
                "strategy_attribution": [],
            }

    def trades(self, portfolio_id: int | None = None, limit: int = 100) -> dict[str, object]:
        params = {"limit": limit}
        where = ""
        if portfolio_id:
            where = "WHERE portfolio_id = :portfolio_id"
            params["portfolio_id"] = portfolio_id
        rows = self._mappings(
            self.research_engine,
            f"""
            SELECT trade_id, portfolio_id, symbol, sector, signal_date, entry_date, exit_date,
                   entry_price, exit_price, quantity, capital_allocated, proceeds,
                   realized_pnl, return_pct, fees, slippage, turnover, exit_reason
            FROM paper_trades
            {where}
            ORDER BY exit_date DESC, trade_id DESC
            LIMIT :limit
            """,
            params,
        )
        return {"trades": self._jsonable(rows)}

    def pipeline_status(self) -> dict[str, object]:
        rows = self._mappings(
            self.research_engine,
            """
            SELECT business_date, step_name, status, started_at, completed_at, error_message
            FROM pipeline_runs
            WHERE business_date = (SELECT MAX(business_date) FROM pipeline_runs)
            ORDER BY started_at ASC NULLS LAST, step_name ASC
            """,
        )
        latest_candle = self._latest_candle_from_sync_report() or self._scalar(
            self.angel_engine,
            "SELECT datetime FROM ohlcv_15min ORDER BY datetime DESC LIMIT 1",
        )
        latest_feature = self._scalar(self.angel_engine, f"SELECT MAX(date) FROM {self.pilot_schema}.features_daily")
        latest_recommendation = self._scalar(self.angel_engine, f"SELECT MAX(date) FROM {self.pilot_schema}.recommendations_daily")
        failed = [row for row in rows if row.get("status") == "failed"]
        latest_step = rows[-1] if rows else {}
        last_completed = next((row for row in reversed(rows) if row.get("status") == "success"), latest_step)
        latest_log_path = self._latest_daily_pipeline_log()
        return {
            "summary": {
                "latest_candle_at": self._iso(latest_candle),
                "latest_feature_date": self._iso(latest_feature),
                "latest_recommendation_date": self._iso(latest_recommendation),
                "current_step": latest_step.get("step_name"),
                "last_completed_step": last_completed.get("step_name"),
                "latest_log_path": latest_log_path,
                "steps": len(rows),
                "failed_steps": len(failed),
                "status": "failed" if failed else ("success" if rows else "unknown"),
            },
            "steps": self._jsonable(rows),
            "monitoring_reports": self._monitoring_reports(),
        }

    def _latest_daily_pipeline_log(self) -> str | None:
        logs_dir = REPO_ROOT / "logs" / "daily_pipeline"
        if not logs_dir.exists():
            return None
        candidates = sorted(
            (path for path in logs_dir.glob("*.log") if path.is_file()),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        return str(candidates[0]) if candidates else None

    def research_metrics(self) -> dict[str, object]:
        phase2e = self._read_json("phase2e_portfolio_metrics.json")
        phase2g = self._read_json("phase2g_walk_forward.json")
        phase3e = self._read_json("phase3e_full_replay.json")
        sector_1m3m = self._read_json("sector_1m3m_rank_experiment/sector_1m3m_rank_results.json", root=self.results_dir)
        sector_points_filter = self._read_json(
            "sector_points_filter_comparison/sector_points_filter_comparison.json",
            root=self.results_dir,
        )
        monte_carlo = self._read_json("sector_1m3m_monte_carlo/sector_1m3m_monte_carlo_summary.json", root=self.results_dir)
        cash_sweep = self._read_json("liquid_fund_cash_overlay/liquid_fund_cash_overlay.json", root=self.results_dir)
        summary = {}
        if phase2e:
            summary["phase2e_available"] = True
            summary["phase2e_keys"] = list(phase2e.keys())[:10]
        if phase2g:
            summary["walk_forward_available"] = True
        if phase3e:
            summary["phase3e_available"] = True
        final_metrics = None
        final_parameters = None
        validation_source = "sector_1m3m_rank_experiment"
        if isinstance(sector_points_filter, dict):
            final_metrics = (
                sector_points_filter.get("variants", {})
                .get("sector_points_ge_1", {})
                .get("metrics")
            )
            final_parameters = sector_points_filter.get("parameters")
            validation_source = "sector_points_filter_comparison"
        if isinstance(sector_1m3m, dict):
            final_metrics = final_metrics or (
                sector_1m3m.get("variants", {})
                .get("sector_1m3m_40_60_rank", {})
                .get("metrics")
            )
            final_parameters = final_parameters or sector_1m3m.get("parameters")
        monte_carlo_summary = None
        if isinstance(monte_carlo, dict):
            monte_carlo_summary = next(
                (
                    row for row in monte_carlo.get("summary_rows", [])
                    if row.get("variant") == "sector_1m3m_40_60_rank" and row.get("simulation_type") == "bootstrap"
                ),
                None,
            )
        cash_sweep_base = None
        if isinstance(cash_sweep, dict):
            cash_sweep_base = next(
                (
                    row for row in cash_sweep.get("summary", [])
                    if row.get("variant") == "sector_points_ge_1"
                    and row.get("scenario") == "base_6_3_net_2bps_churn"
                ),
                None,
            )
        return {
            "summary": summary,
            "portfolio_metrics": phase2e,
            "walk_forward": phase2g,
            "paper_replay": phase3e.get("summary") if isinstance(phase3e, dict) else None,
            "sector_1m3m": {
                "parameters": final_parameters,
                "metrics": final_metrics,
                "monte_carlo": monte_carlo_summary,
                "validation_source": validation_source,
            },
            "cash_sweep_overlay": {
                "method": cash_sweep.get("method") if isinstance(cash_sweep, dict) else None,
                "assumptions": cash_sweep.get("assumptions") if isinstance(cash_sweep, dict) else None,
                "scenario": cash_sweep_base,
                "source": "liquid_fund_cash_overlay",
            },
        }

    def _default_portfolio_id(self) -> int | None:
        return self.paper_portfolio_id

    def health(self) -> dict[str, object]:
        research = self._connection_health(self.research_engine, "research")
        angel = self._connection_health(self.angel_engine, "angel")
        portfolio = self._portfolio_health() if research["connected"] else {
            "configured": self.paper_portfolio_id is not None,
            "portfolio_id": self.paper_portfolio_id,
            "exists": False,
        }
        ok = bool(research["connected"] and angel["connected"] and portfolio["configured"] and portfolio["exists"])
        return {
            "status": "ok" if ok else "degraded",
            "research_db": research,
            "angel_db": angel,
            "paper_portfolio": portfolio,
        }

    def _connection_health(self, engine: Engine | None, label: str) -> dict[str, object]:
        if engine is None:
            return {"connected": False, "error": f"{label} database engine is not configured."}
        try:
            with engine.connect() as connection:
                if engine.dialect.name == "postgresql":
                    database = connection.execute(text("SELECT current_database()")).scalar_one_or_none()
                else:
                    connection.execute(text("SELECT 1")).scalar_one()
                    database = engine.dialect.name
            return {"connected": True, "database": database}
        except Exception as exc:
            LOGGER.exception("%s database health check failed", label)
            return {"connected": False, "error": str(exc)}

    def _portfolio_health(self) -> dict[str, object]:
        if self.paper_portfolio_id is None:
            return {"configured": False, "portfolio_id": None, "exists": False}
        rows = self._mappings(
            self.research_engine,
            "SELECT portfolio_id, status FROM paper_portfolios WHERE portfolio_id = :portfolio_id",
            {"portfolio_id": self.paper_portfolio_id},
        )
        return {
            "configured": True,
            "portfolio_id": self.paper_portfolio_id,
            "exists": bool(rows),
            "status": rows[0].get("status") if rows else None,
        }

    def _risk(self, snapshot: dict[str, object], positions: list[dict[str, object]], nav_history: list[dict[str, object]]) -> dict[str, object]:
        nav = float(snapshot.get("nav") or 0)
        market_value = float(snapshot.get("market_value") or 0)
        peak = 0.0
        drawdown = None
        for row in nav_history:
            current = float(row.get("nav") or 0)
            peak = max(peak, current)
            drawdown = (current / peak) - 1 if peak else 0.0
        sectors: dict[str, float] = {}
        for row in positions:
            if row.get("status") != "open":
                continue
            sectors[str(row.get("sector") or "Unknown")] = sectors.get(str(row.get("sector") or "Unknown"), 0.0) + float(row.get("market_value") or 0)
        sector_weights = {sector: value / market_value for sector, value in sectors.items()} if market_value else {}
        return {
            "drawdown": drawdown,
            "exposure": market_value / nav if nav else None,
            "sector_weights": sector_weights,
            "max_sector_weight": max(sector_weights.values()) if sector_weights else 0.0,
        }

    def _monitoring_reports(self) -> list[dict[str, object]]:
        rows = []
        for path in sorted(self.reports_dir.glob("daily_paper_report_*.md"), reverse=True)[:10]:
            rows.append({"name": path.name, "path": str(path), "modified_at": self._iso(date.fromtimestamp(path.stat().st_mtime))})
        return rows

    def _latest_candle_from_sync_report(self) -> datetime | None:
        report = self._read_json("phase3f_angel_daily_sync.json")
        latest: datetime | None = None
        for row in report.get("results", []) if isinstance(report, dict) else []:
            if not isinstance(row, dict):
                continue
            value = row.get("latest_before")
            if not value:
                continue
            try:
                parsed = datetime.fromisoformat(str(value))
            except ValueError:
                continue
            if latest is None or parsed > latest:
                latest = parsed
        return latest

    def _read_json(self, name: str, root: Path | None = None) -> dict[str, object]:
        path = (root or self.reports_dir) / name
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}

    def _scalar(self, engine: Engine | None, query: str, params: dict[str, object] | None = None):
        if engine is None:
            raise CockpitDatabaseError("Database engine is not configured.")
        try:
            with engine.connect() as connection:
                return connection.execute(text(query), params or {}).scalar_one_or_none()
        except Exception as exc:
            LOGGER.exception("Cockpit scalar query failed: %s", query.strip().splitlines()[0])
            raise CockpitDatabaseError(f"Database query failed: {exc}") from exc

    def _mappings(self, engine: Engine | None, query: str, params: dict[str, object] | None = None) -> list[dict[str, object]]:
        if engine is None:
            raise CockpitDatabaseError("Database engine is not configured.")
        try:
            with engine.connect() as connection:
                return [dict(row) for row in connection.execute(text(query), params or {}).mappings().all()]
        except Exception as exc:
            LOGGER.exception("Cockpit mapping query failed: %s", query.strip().splitlines()[0])
            raise CockpitDatabaseError(f"Database query failed: {exc}") from exc

    def _iso(self, value):
        if value is None:
            return None
        if hasattr(value, "isoformat"):
            return value.isoformat()
        return str(value)

    @staticmethod
    def _float(value) -> float | None:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _jsonable(self, value):
        if isinstance(value, list):
            return [self._jsonable(item) for item in value]
        if isinstance(value, dict):
            return {key: self._jsonable(item) for key, item in value.items()}
        if hasattr(value, "isoformat"):
            return value.isoformat()
        if isinstance(value, (int, float, str, bool)) or value is None:
            return value
        try:
            return float(value)
        except Exception:
            return str(value)
