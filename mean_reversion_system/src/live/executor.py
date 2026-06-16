"""SQLite-backed paper portfolio executor for Disha."""

from __future__ import annotations

import sqlite3
import uuid
from dataclasses import asdict
from datetime import date, datetime
from pathlib import Path
from typing import Mapping

import pandas as pd

from mean_reversion_system.src.live.scanner import ScanResult

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = ROOT / "results" / "sprint_2_8" / "paper_portfolio.sqlite"
PAPER_TRADES = ROOT / "results" / "paper_trades.csv"


class PaperPortfolio:
    """Persisted paper-trading portfolio."""

    def __init__(self, db_path: str | Path = DEFAULT_DB, initial_capital: float = 1_000_000.0) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.initial_capital = float(initial_capital)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS positions (
                    trade_id TEXT PRIMARY KEY,
                    sleeve TEXT,
                    symbol TEXT,
                    signal_type TEXT,
                    entry_date TEXT,
                    entry_price REAL,
                    shares INTEGER,
                    stop_loss REAL,
                    target_price REAL,
                    status TEXT,
                    exit_date TEXT,
                    exit_price REAL,
                    pnl REAL,
                    rationale TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS daily_pnl (
                    log_date TEXT PRIMARY KEY,
                    equity REAL,
                    open_positions INTEGER,
                    realised_pnl REAL,
                    heat REAL
                )
                """
            )

    def open_position(self, scan_result: ScanResult, entry_date: date | None = None) -> str:
        """Record a virtual trade at the next open/reference price."""

        trade_id = str(uuid.uuid4())
        sleeve = "VCP" if scan_result.signal_type.startswith("VCP") else "V4B"
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO positions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    trade_id,
                    sleeve,
                    scan_result.symbol,
                    scan_result.signal_type,
                    (entry_date or datetime.now().date()).isoformat(),
                    float(scan_result.entry_price),
                    int(scan_result.position_size),
                    float(scan_result.sl_price),
                    float(scan_result.target_price),
                    "OPEN",
                    None,
                    None,
                    None,
                    scan_result.rationale,
                ),
            )
        return trade_id

    def check_exits(self, current_prices: Mapping[str, float], item_date: date | None = None) -> list[dict[str, object]]:
        """Close positions hitting stop or target."""

        closed: list[dict[str, object]] = []
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM positions WHERE status = 'OPEN'").fetchall()
            columns = [item[1] for item in conn.execute("PRAGMA table_info(positions)").fetchall()]
            for raw in rows:
                row = dict(zip(columns, raw))
                price = current_prices.get(str(row["symbol"]))
                if price is None:
                    continue
                reason = None
                if float(price) <= float(row["stop_loss"]):
                    reason = "STOPPED"
                elif float(price) >= float(row["target_price"]):
                    reason = "CLOSED"
                if reason is None:
                    continue
                pnl = (float(price) - float(row["entry_price"])) * int(row["shares"])
                conn.execute(
                    "UPDATE positions SET status=?, exit_date=?, exit_price=?, pnl=? WHERE trade_id=?",
                    (reason, (item_date or datetime.now().date()).isoformat(), float(price), pnl, row["trade_id"]),
                )
                row.update({"status": reason, "exit_price": float(price), "pnl": pnl})
                closed.append(row)
        self._append_paper_trades(closed)
        return closed

    def get_portfolio_summary(self) -> dict[str, object]:
        """Return current paper portfolio summary."""

        with self._connect() as conn:
            open_rows = conn.execute("SELECT entry_price, shares, stop_loss FROM positions WHERE status = 'OPEN'").fetchall()
            realised = conn.execute("SELECT COALESCE(SUM(pnl), 0) FROM positions WHERE pnl IS NOT NULL").fetchone()[0]
        open_notional = sum(float(price) * int(shares) for price, shares, _ in open_rows)
        heat = sum(abs(float(price) - float(stop)) * int(shares) for price, shares, stop in open_rows) / self.initial_capital if self.initial_capital else 0.0
        return {
            "initial_capital": self.initial_capital,
            "realised_pnl": float(realised or 0.0),
            "open_positions": len(open_rows),
            "open_notional": open_notional,
            "heat": heat,
            "equity_estimate": self.initial_capital + float(realised or 0.0),
        }

    def log_daily_pnl(self, item_date: date | None = None) -> dict[str, object]:
        """Persist daily portfolio summary."""

        summary = self.get_portfolio_summary()
        log_date = (item_date or datetime.now().date()).isoformat()
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO daily_pnl VALUES (?, ?, ?, ?, ?)",
                (log_date, summary["equity_estimate"], summary["open_positions"], summary["realised_pnl"], summary["heat"]),
            )
        return {"log_date": log_date, **summary}

    @staticmethod
    def _append_paper_trades(rows: list[dict[str, object]]) -> None:
        if not rows:
            return
        PAPER_TRADES.parent.mkdir(parents=True, exist_ok=True)
        frame = pd.DataFrame(rows)
        if PAPER_TRADES.exists():
            existing = pd.read_csv(PAPER_TRADES)
            frame = pd.concat([existing, frame], ignore_index=True)
        frame.to_csv(PAPER_TRADES, index=False)

