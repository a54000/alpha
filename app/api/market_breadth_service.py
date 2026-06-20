"""Read-only market breadth service."""

from __future__ import annotations

import json
import os
import time
from copy import deepcopy
from datetime import date, datetime, timezone
from pathlib import Path
from threading import Lock
from urllib.parse import urlsplit, urlunsplit

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


class MarketBreadthError(RuntimeError):
    """Raised when market breadth cannot be generated."""


_CACHE_LOCK = Lock()
_CACHE: dict[tuple[str, str, str], tuple[float, dict[str, object]]] = {}
_LATEST_DATE_CACHE: dict[str, tuple[float, date | None]] = {}
REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_READY_UNIVERSE = REPO_ROOT / "reports" / "nifty500_backfill_status.csv"
MARKET_LENS_SNAPSHOT_DIR = REPO_ROOT / "reports" / "market_lens_snapshots"


def derive_angel_url(research_database_url: str | None, database_name: str = "angel_data") -> str | None:
    if not research_database_url:
        return None
    parts = urlsplit(research_database_url)
    return urlunsplit((parts.scheme, parts.netloc, f"/{database_name}", parts.query, parts.fragment))


def make_engine(database_url: str) -> Engine:
    return create_engine(database_url, future=True, pool_pre_ping=True, pool_size=1, max_overflow=0)


class MarketBreadthService:
    """Compute top-of-funnel market breadth from pilot daily bars."""

    def __init__(
        self,
        angel_database_url: str | None = None,
        pilot_schema: str = "pilot_phase2a",
        ready_universe_csv: Path | None = None,
    ) -> None:
        research_url = os.environ.get("DATABASE_URL")
        self.angel_database_url = angel_database_url or os.environ.get("ANGEL_DATABASE_URL") or derive_angel_url(research_url)
        if not self.angel_database_url:
            raise MarketBreadthError("ANGEL_DATABASE_URL is required for market breadth.")
        self.engine = make_engine(self.angel_database_url)
        self.pilot_schema = pilot_schema
        self.ready_universe_csv = ready_universe_csv or DEFAULT_READY_UNIVERSE
        self.cache_ttl_seconds = int(os.environ.get("MARKET_BREADTH_CACHE_TTL_SECONDS", "900"))
        self.latest_date_cache_ttl_seconds = int(os.environ.get("MARKET_BREADTH_LATEST_DATE_CACHE_TTL_SECONDS", "120"))

    def breadth(self, as_of: date | None = None) -> dict[str, object]:
        latest = as_of or self._cached_latest_date()
        if latest is None:
            return {"as_of": None, "summary": {}, "chart": []}
        cache_key = (self.pilot_schema, latest.isoformat(), self._ready_universe_signature())
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached
        bars = self._load_bars(latest)
        nifty = self._load_nifty(latest)
        if bars.empty or nifty.empty:
            return {"as_of": latest.isoformat(), "summary": {"message": "Insufficient data."}, "chart": []}
        enriched = self._enrich_bars(bars)
        latest_rows = enriched[enriched["date"] == latest].copy()
        ready_symbol_count = len(self._ready_symbols())
        summary = self._summary(latest_rows, enriched, nifty, latest, ready_symbol_count)
        chart = self._chart(enriched, nifty)
        snapshot_path = self._write_market_lens_snapshot(latest, summary.get("market_lens"), ready_symbol_count)
        payload = {
            "as_of": latest.isoformat(),
            "universe": "ready_symbols",
            "summary": summary,
            "chart": chart,
            "market_lens_snapshot_path": snapshot_path,
            "cache": {
                "hit": False,
                "ttl_seconds": self.cache_ttl_seconds,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
        }
        self._cache_set(cache_key, payload)
        return deepcopy(payload)

    def _cache_get(self, cache_key: tuple[str, str, str]) -> dict[str, object] | None:
        if self.cache_ttl_seconds <= 0:
            return None
        now = time.monotonic()
        with _CACHE_LOCK:
            cached = _CACHE.get(cache_key)
            if cached is None:
                return None
            created_at, payload = cached
            if now - created_at > self.cache_ttl_seconds:
                _CACHE.pop(cache_key, None)
                return None
            response = deepcopy(payload)
        cache_meta = dict(response.get("cache") or {})
        cache_meta["hit"] = True
        response["cache"] = cache_meta
        return response

    def _cache_set(self, cache_key: tuple[str, str, str], payload: dict[str, object]) -> None:
        if self.cache_ttl_seconds <= 0:
            return
        with _CACHE_LOCK:
            _CACHE[cache_key] = (time.monotonic(), deepcopy(payload))

    def _cached_latest_date(self) -> date | None:
        if self.latest_date_cache_ttl_seconds <= 0:
            return self._latest_date()
        now = time.monotonic()
        with _CACHE_LOCK:
            cached = _LATEST_DATE_CACHE.get(self.pilot_schema)
            if cached is not None:
                created_at, latest = cached
                if now - created_at <= self.latest_date_cache_ttl_seconds:
                    return latest
        latest = self._latest_date()
        with _CACHE_LOCK:
            _LATEST_DATE_CACHE[self.pilot_schema] = (time.monotonic(), latest)
        return latest

    def _latest_date(self) -> date | None:
        with self.engine.connect() as connection:
            return connection.execute(text(f"SELECT MAX(date) FROM {self.pilot_schema}.daily_bars_clean")).scalar_one_or_none()

    def _load_bars(self, latest: date) -> pd.DataFrame:
        query = text(
            f"""
            SELECT symbol, date, close, high, low
            FROM {self.pilot_schema}.daily_bars_clean
            WHERE date BETWEEN :latest - INTERVAL '420 days' AND :latest
            ORDER BY symbol, date
            """
        )
        frame = pd.read_sql_query(query, self.engine, params={"latest": latest})
        if frame.empty:
            return frame
        frame["date"] = pd.to_datetime(frame["date"]).dt.date
        for column in ["close", "high", "low"]:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
        frame = frame.dropna(subset=["symbol", "date", "close"])
        ready_symbols = self._ready_symbols()
        if ready_symbols:
            frame = frame[frame["symbol"].isin(ready_symbols)]
        return frame

    def _load_nifty(self, latest: date) -> pd.DataFrame:
        query = text(
            """
            SELECT datetime::date AS date, high, low, close
            FROM ohlcv_15min
            WHERE symbol = 'NIFTY50'
              AND datetime::date BETWEEN :latest - INTERVAL '420 days' AND :latest
              AND datetime::time <= '15:15:00'
            ORDER BY datetime
            """
        )
        frame = pd.read_sql_query(query, self.engine, params={"latest": latest})
        if frame.empty:
            return frame
        frame["date"] = pd.to_datetime(frame["date"]).dt.date
        for column in ["high", "low", "close"]:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
        daily_close = frame.dropna(subset=["close"]).groupby("date", as_index=False).tail(1)[["date", "close"]]
        daily_range = frame.dropna(subset=["high", "low"]).groupby("date", as_index=False).agg({"high": "max", "low": "min"})
        daily = daily_close.merge(daily_range, on="date", how="left")
        daily = daily.sort_values("date").copy()
        daily["sma_50"] = daily["close"].rolling(50, min_periods=20).mean()
        daily["sma_200"] = daily["close"].rolling(200, min_periods=80).mean()
        daily["ema_50"] = daily["close"].ewm(span=50, adjust=False).mean()
        daily["ema_200"] = daily["close"].ewm(span=200, adjust=False).mean()

        prev_close = daily["close"].shift(1)
        true_range = pd.concat(
            [
                daily["high"] - daily["low"],
                (daily["high"] - prev_close).abs(),
                (daily["low"] - prev_close).abs(),
            ],
            axis=1,
        ).max(axis=1)
        daily["atr_14"] = true_range.ewm(alpha=1 / 14, adjust=False).mean()
        return daily

    def _ready_symbols(self) -> set[str]:
        try:
            frame = pd.read_csv(self.ready_universe_csv)
        except FileNotFoundError:
            return set()
        except Exception:
            return set()
        if "status" not in frame.columns or "symbol" not in frame.columns:
            return set()
        ready = frame[frame["status"].astype(str).str.lower() == "ready"]
        return {str(symbol).strip().upper() for symbol in ready["symbol"].dropna().tolist() if str(symbol).strip()}

    def _ready_universe_signature(self) -> str:
        try:
            stat = self.ready_universe_csv.stat()
            return f"{self.ready_universe_csv.name}:{int(stat.st_mtime)}:{stat.st_size}"
        except OSError:
            return "no-ready-universe-file"

    @staticmethod
    def _enrich_bars(frame: pd.DataFrame) -> pd.DataFrame:
        item = frame.sort_values(["symbol", "date"]).copy()
        item["prev_close"] = item.groupby("symbol")["close"].shift(1)
        item["ema_50"] = item.groupby("symbol")["close"].transform(lambda values: values.ewm(span=50, adjust=False).mean())
        item["sma_50"] = item.groupby("symbol")["close"].transform(lambda values: values.rolling(50, min_periods=35).mean())
        item["sma_200"] = item.groupby("symbol")["close"].transform(lambda values: values.rolling(200, min_periods=120).mean())
        item["rolling_252_high"] = item.groupby("symbol")["high"].transform(lambda values: values.rolling(252, min_periods=180).max())
        item["rolling_252_low"] = item.groupby("symbol")["low"].transform(lambda values: values.rolling(252, min_periods=180).min())
        return item

    def _summary(
        self,
        latest_rows: pd.DataFrame,
        enriched: pd.DataFrame,
        nifty: pd.DataFrame,
        latest: date,
        ready_symbol_count: int,
    ) -> dict[str, object]:
        total = int(latest_rows["symbol"].nunique())
        advancing = int((latest_rows["close"] > latest_rows["prev_close"]).sum())
        declining = int((latest_rows["close"] < latest_rows["prev_close"]).sum())
        unchanged = max(0, total - advancing - declining)
        above_50 = latest_rows[latest_rows["sma_50"].notna()]
        above_50ema = latest_rows[latest_rows["ema_50"].notna()]
        above_200 = latest_rows[latest_rows["sma_200"].notna()]
        pct_above_50 = float((above_50["close"] > above_50["sma_50"]).mean()) if not above_50.empty else None
        pct_above_200 = float((above_200["close"] > above_200["sma_200"]).mean()) if not above_200.empty else None
        high_rows = latest_rows[latest_rows["rolling_252_high"].notna()]
        low_rows = latest_rows[latest_rows["rolling_252_low"].notna()]
        new_highs = int((high_rows["high"] >= high_rows["rolling_252_high"]).sum())
        new_lows = int((low_rows["low"] <= low_rows["rolling_252_low"]).sum())
        divergence = self._divergence(enriched, nifty, latest, pct_above_50)
        nifty_latest = nifty.iloc[-1]
        advancer_pct = advancing / (advancing + declining) if (advancing + declining) else None
        composite = self._composite_status(
            pct_above_50=pct_above_50,
            pct_above_200=pct_above_200,
            advancer_pct=advancer_pct,
            new_highs=new_highs,
            new_lows=new_lows,
            divergence=divergence,
        )
        previous = self._previous_composite(enriched, nifty, latest)
        if previous and previous.get("status") != composite["status"]:
            composite["persistence_note"] = (
                f"Previous session was {previous.get('status')}. Treat the new label as provisional until it persists."
            )
            composite["previous_status"] = previous.get("status")
        pct_above_50ema = float((above_50ema["close"] > above_50ema["ema_50"]).mean()) if not above_50ema.empty else None
        market_lens = self._market_lens(enriched, nifty, latest, pct_above_50ema)
        return {
            "total_symbols": ready_symbol_count or total,
            "symbols_with_current_bar": total,
            "current_bar_coverage_pct": (total / ready_symbol_count) if ready_symbol_count else None,
            "advancing": advancing,
            "declining": declining,
            "unchanged": unchanged,
            "advancer_pct": advancer_pct,
            "pct_above_50dma": pct_above_50,
            "pct_above_50ema": pct_above_50ema,
            "pct_below_50dma": 1.0 - pct_above_50 if pct_above_50 is not None else None,
            "pct_above_200dma": pct_above_200,
            "pct_above_50dma_count": int((above_50["close"] > above_50["sma_50"]).sum()) if not above_50.empty else 0,
            "pct_above_50dma_denominator": int(len(above_50)),
            "pct_above_200dma_count": int((above_200["close"] > above_200["sma_200"]).sum()) if not above_200.empty else 0,
            "pct_above_200dma_denominator": int(len(above_200)),
            "new_52w_highs": new_highs,
            "new_52w_lows": new_lows,
            "nifty_close": float(nifty_latest["close"]),
            "nifty_sma_50": self._float_or_none(nifty_latest.get("sma_50")),
            "nifty_sma_200": self._float_or_none(nifty_latest.get("sma_200")),
            "divergence": divergence,
            "composite": composite,
            "market_lens": market_lens,
        }

    def _market_lens(self, enriched: pd.DataFrame, nifty: pd.DataFrame, latest_date: date, breadth_50ema: float | None) -> dict[str, object]:
        if nifty.empty:
            return {
                "lens": "Unknown",
                "colour": "grey",
                "instruction": "Market lens is unavailable because benchmark data is missing.",
                "long_bias": None,
                "signals": {},
            }

        latest = nifty.iloc[-1]
        close_date = latest.get("date")
        close = self._float_or_none(latest.get("close"))
        ema_50 = self._float_or_none(latest.get("ema_50"))
        ema_200 = self._float_or_none(latest.get("ema_200"))
        atr_14 = self._float_or_none(latest.get("atr_14"))
        above_50ema = bool(close is not None and ema_50 is not None and close > ema_50)
        above_200ema = bool(close is not None and ema_200 is not None and close > ema_200)
        momentum_3m = None
        if close is not None and len(nifty) >= 64:
            base = self._float_or_none(nifty.iloc[-64].get("close"))
            if base:
                momentum_3m = (close / base) - 1
        atr_pct = (atr_14 / close) if close and atr_14 is not None else None

        raw_result = self._classify_market_lens(above_200ema, above_50ema, breadth_50ema)
        persistence = self._lens_persistence(enriched, nifty, latest_date)
        confirmed_lens = str(persistence.get("confirmed_lens") or raw_result["lens"])
        result_base = self._classify_market_lens(
            above_200ema=confirmed_lens in {"Bullish", "Selective"},
            above_50ema=confirmed_lens == "Bullish",
            breadth_50ema=0.61 if confirmed_lens == "Bullish" else 0.46 if confirmed_lens == "Selective" else 0.41 if confirmed_lens == "Cautious" else 0.0,
        )
        lens = str(result_base["lens"])
        colour = str(result_base["colour"])
        instruction = str(result_base["instruction"])
        long_bias = float(result_base["long_bias"])

        result = {
            "lens": lens,
            "raw_lens": raw_result["lens"],
            "colour": colour,
            "benchmark_used": "NIFTY50",
            "benchmark_note": (
                "NIFTY500 index history is not yet available locally. "
                "Using NIFTY50 as a proxy; expected difference in lens signal is low."
            ),
            "instruction": instruction,
            "long_bias": long_bias,
            "short_bias": 1 - long_bias,
            "persistence": persistence,
            "read_only": True,
            "signals": {
                "nifty_close_date": close_date.isoformat() if hasattr(close_date, "isoformat") else str(close_date) if close_date is not None else None,
                "nifty_close": close,
                "nifty_ema_50": ema_50,
                "nifty_ema_200": ema_200,
                "nifty_above_50ema": above_50ema,
                "nifty_above_200ema": above_200ema,
                "breadth_50ema": breadth_50ema,
                "nifty_3m_return": momentum_3m,
                "atr_pct": atr_pct,
            },
        }
        return self._apply_signal_modifiers(result, momentum_3m, atr_pct, above_50ema)

    def _write_market_lens_snapshot(self, as_of: date, market_lens: object, ready_symbol_count: int) -> str | None:
        if not isinstance(market_lens, dict):
            return None
        try:
            MARKET_LENS_SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
            generated_at = datetime.now(timezone.utc)
            snapshot = {
                "generated_at": generated_at.isoformat(),
                "as_of": as_of.isoformat(),
                "pilot_schema": self.pilot_schema,
                "ready_universe_csv": str(self.ready_universe_csv),
                "ready_universe_signature": self._ready_universe_signature(),
                "ready_symbol_count": ready_symbol_count,
                "market_lens": market_lens,
            }
            snapshot_name = f"market_lens_{as_of.isoformat()}_{generated_at.strftime('%Y%m%dT%H%M%SZ')}.json"
            snapshot_path = MARKET_LENS_SNAPSHOT_DIR / snapshot_name
            with snapshot_path.open("w", encoding="utf-8") as handle:
                json.dump(snapshot, handle, indent=2, sort_keys=True)
                handle.write("\n")
            return str(snapshot_path)
        except OSError:
            return None

    @staticmethod
    def _classify_market_lens(above_200ema: bool, above_50ema: bool, breadth_50ema: float | None) -> dict[str, object]:
        if above_200ema and above_50ema and breadth_50ema is not None and breadth_50ema > 0.60:
            return {
                "lens": "Bullish",
                "colour": "green",
                "instruction": "Broad market supports normal long exposure. Fresh entries can be considered in leading sectors.",
                "long_bias": 0.80,
            }
        if above_200ema and breadth_50ema is not None and breadth_50ema > 0.45:
            return {
                "lens": "Selective",
                "colour": "cyan",
                "instruction": "Use confirmed longs only. Avoid weak sectors and low-quality setups.",
                "long_bias": 0.65,
            }
        if (not above_200ema) and breadth_50ema is not None and breadth_50ema > 0.40:
            return {
                "lens": "Cautious",
                "colour": "amber",
                "instruction": "Reduce fresh entries. Prefer smaller size and wait for stronger confirmation.",
                "long_bias": 0.40,
            }
        return {
            "lens": "Bearish",
            "colour": "red",
            "instruction": "Preserve capital. Avoid new entries except exceptional leadership setups.",
            "long_bias": 0.20,
        }

    def _lens_persistence(self, enriched: pd.DataFrame, nifty: pd.DataFrame, latest_date: date, persistence_days: int = 2) -> dict[str, object]:
        raw_history = self._raw_lens_history(enriched, nifty, latest_date)
        if not raw_history:
            return {
                "confirmed_lens": None,
                "changed": False,
                "pending": False,
                "pending_lens": None,
                "pending_days": 0,
                "days_needed": 0,
                "history": [],
                "persistence_days": persistence_days,
            }

        current_lens = str(raw_history[0]["raw"])
        pending_lens: str | None = None
        pending_days = 0
        changed = False
        from_lens: str | None = None
        persisted_history: list[dict[str, object]] = []

        for item in raw_history:
            raw_lens = str(item["raw"])
            status = "held"
            changed = False
            from_lens = None
            if raw_lens == current_lens:
                pending_lens = None
                pending_days = 0
            elif raw_lens == pending_lens:
                pending_days += 1
                status = "pending"
                if pending_days >= persistence_days:
                    from_lens = current_lens
                    current_lens = raw_lens
                    pending_lens = None
                    pending_days = 0
                    status = "confirmed"
                    changed = True
            else:
                pending_lens = raw_lens
                pending_days = 1
                status = "pending_start"

            persisted_history.append(
                {
                    "date": item["date"],
                    "raw": raw_lens,
                    "status": status,
                    "confirmed": current_lens,
                }
            )

        pending = pending_lens is not None
        return {
            "confirmed_lens": current_lens,
            "changed": changed,
            "from_lens": from_lens,
            "pending": pending,
            "pending_lens": pending_lens,
            "pending_days": pending_days,
            "days_needed": max(0, persistence_days - pending_days) if pending else 0,
            "history": persisted_history[-10:],
            "persistence_days": persistence_days,
        }

    def _raw_lens_history(self, enriched: pd.DataFrame, nifty: pd.DataFrame, latest_date: date) -> list[dict[str, object]]:
        if enriched.empty or nifty.empty:
            return []
        dates = sorted(day for day in enriched["date"].dropna().unique() if day <= latest_date)
        if not dates:
            return []
        dates = dates[-20:]
        nifty_by_date = nifty.drop_duplicates("date", keep="last").set_index("date")
        history: list[dict[str, object]] = []
        for item_date in dates:
            if item_date not in nifty_by_date.index:
                continue
            rows = enriched[enriched["date"] == item_date]
            rows_50ema = rows[rows["ema_50"].notna()]
            breadth_50ema = float((rows_50ema["close"] > rows_50ema["ema_50"]).mean()) if not rows_50ema.empty else None
            nifty_row = nifty_by_date.loc[item_date]
            close = self._float_or_none(nifty_row.get("close"))
            ema_50 = self._float_or_none(nifty_row.get("ema_50"))
            ema_200 = self._float_or_none(nifty_row.get("ema_200"))
            raw = self._classify_market_lens(
                above_200ema=bool(close is not None and ema_200 is not None and close > ema_200),
                above_50ema=bool(close is not None and ema_50 is not None and close > ema_50),
                breadth_50ema=breadth_50ema,
            )
            history.append({"date": item_date.isoformat(), "raw": raw["lens"]})
        return history

    @staticmethod
    def _apply_signal_modifiers(
        base_result: dict[str, object],
        momentum_3m: float | None,
        atr_ratio: float | None,
        above_50ema: bool,
    ) -> dict[str, object]:
        """Fine-tune long/short bias without changing the market lens label."""
        long_bias = base_result.get("long_bias")
        if not isinstance(long_bias, (int, float)):
            return base_result

        long_bias = float(long_bias)
        modifiers: list[str] = []
        signals = base_result.get("signals") if isinstance(base_result.get("signals"), dict) else {}

        if momentum_3m is not None:
            if momentum_3m > 0.08:
                long_bias = min(0.90, long_bias + 0.05)
                modifiers.append("Strong 3M momentum: long bias +5%")
            elif momentum_3m < -0.05:
                long_bias = max(0.10, long_bias - 0.05)
                modifiers.append("Negative 3M momentum: short bias +5%")

        if atr_ratio is not None:
            if atr_ratio > 0.02:
                long_bias = (long_bias * 0.90) + (0.50 * 0.10)
                modifiers.append(f"High ATR {atr_ratio * 100:.1f}%: bias moderated")
            elif atr_ratio < 0.008:
                if long_bias >= 0.50:
                    long_bias = min(0.90, long_bias + 0.05)
                else:
                    long_bias = max(0.10, long_bias - 0.05)
                modifiers.append(f"Low ATR {atr_ratio * 100:.1f}%: dominant bias strengthened")

        if bool(signals.get("nifty_above_200ema")) and not above_50ema:
            long_bias = max(0.10, long_bias - 0.05)
            modifiers.append("Above 200 EMA but below 50 EMA: caution modifier")

        long_bias = round(long_bias, 2)
        base_result["long_bias"] = long_bias
        base_result["short_bias"] = round(1 - long_bias, 2)
        base_result["bias_modifiers"] = modifiers
        return base_result

    def _previous_composite(self, enriched: pd.DataFrame, nifty: pd.DataFrame, latest: date) -> dict[str, object] | None:
        prior_dates = sorted(day for day in enriched["date"].dropna().unique() if day < latest)
        if not prior_dates:
            return None
        previous_date = prior_dates[-1]
        previous_rows = enriched[enriched["date"] == previous_date]
        if previous_rows.empty:
            return None
        total_adv = int((previous_rows["close"] > previous_rows["prev_close"]).sum())
        total_dec = int((previous_rows["close"] < previous_rows["prev_close"]).sum())
        rows_50 = previous_rows[previous_rows["sma_50"].notna()]
        rows_200 = previous_rows[previous_rows["sma_200"].notna()]
        high_rows = previous_rows[previous_rows["rolling_252_high"].notna()]
        low_rows = previous_rows[previous_rows["rolling_252_low"].notna()]
        pct_above_50 = float((rows_50["close"] > rows_50["sma_50"]).mean()) if not rows_50.empty else None
        pct_above_200 = float((rows_200["close"] > rows_200["sma_200"]).mean()) if not rows_200.empty else None
        advancer_pct = total_adv / (total_adv + total_dec) if (total_adv + total_dec) else None
        previous_nifty = nifty[nifty["date"] <= previous_date]
        divergence = self._divergence(enriched, previous_nifty, previous_date, pct_above_50) if not previous_nifty.empty else {"status": "none"}
        return self._composite_status(
            pct_above_50=pct_above_50,
            pct_above_200=pct_above_200,
            advancer_pct=advancer_pct,
            new_highs=int((high_rows["high"] >= high_rows["rolling_252_high"]).sum()),
            new_lows=int((low_rows["low"] <= low_rows["rolling_252_low"]).sum()),
            divergence=divergence,
        )

    @staticmethod
    def _breadth_band(value: float | None) -> str:
        if value is None:
            return "unknown"
        if value < 0.40:
            return "bearish"
        if value > 0.60:
            return "bullish"
        return "sideways"

    @staticmethod
    def _high_low_band(new_highs: int, new_lows: int) -> str:
        if new_highs <= 0 and new_lows <= 0:
            return "sideways"
        if new_lows > new_highs * 2:
            return "bearish"
        if new_highs > new_lows * 2:
            return "bullish"
        return "sideways"

    def _composite_status(
        self,
        pct_above_50: float | None,
        pct_above_200: float | None,
        advancer_pct: float | None,
        new_highs: int,
        new_lows: int,
        divergence: dict[str, object],
    ) -> dict[str, object]:
        votes = [
            {"metric": "% above 50DMA", "band": self._breadth_band(pct_above_50), "weight": 1},
            {"metric": "% above 200DMA", "band": self._breadth_band(pct_above_200), "weight": 2},
            {"metric": "Advancers %", "band": self._breadth_band(advancer_pct), "weight": 1},
            {"metric": "New highs vs lows", "band": self._high_low_band(new_highs, new_lows), "weight": 1},
        ]
        score_map = {"bearish": -1, "sideways": 0, "bullish": 1, "unknown": 0}
        weighted_score = sum(score_map[vote["band"]] * int(vote["weight"]) for vote in votes)
        if weighted_score >= 2:
            status = "Bullish"
        elif weighted_score <= -2:
            status = "Bearish"
        else:
            status = "Sideways"
        capped_by_divergence = bool(divergence.get("status") == "bearish" and status == "Bullish")
        if capped_by_divergence:
            status = "Sideways"
        return {
            "status": status,
            "weighted_score": weighted_score,
            "capped_by_divergence": capped_by_divergence,
            "votes": votes,
            "method": "200DMA breadth counts double; 50DMA, advancers, and 52-week highs/lows count single. Bearish divergence caps Bullish to Sideways.",
        }

    def _chart(self, enriched: pd.DataFrame, nifty: pd.DataFrame) -> list[dict[str, object]]:
        breadth = []
        for day, group in enriched.groupby("date"):
            rows = group[group["sma_50"].notna()]
            pct_above = float((rows["close"] > rows["sma_50"]).mean()) if not rows.empty else None
            breadth.append({"date": day, "pct_above_50dma": pct_above})
        breadth_frame = pd.DataFrame(breadth)
        merged = nifty.merge(breadth_frame, on="date", how="left").tail(90)
        return [
            {
                "date": row.date.isoformat() if hasattr(row.date, "isoformat") else str(row.date),
                "nifty_close": float(row.close),
                "pct_above_50dma": self._float_or_none(row.pct_above_50dma),
            }
            for row in merged.itertuples(index=False)
        ]

    def _divergence(self, enriched: pd.DataFrame, nifty: pd.DataFrame, latest: date, pct_above_50: float | None) -> dict[str, object]:
        if pct_above_50 is None or len(nifty) < 63:
            return {"status": "none", "message": "Insufficient history for divergence check."}
        nifty_tail = nifty.tail(63)
        latest_close = float(nifty.iloc[-1]["close"])
        high_3m = float(nifty_tail["close"].max())
        near_high = latest_close >= high_3m * 0.99
        past_date = nifty_tail.iloc[0]["date"]
        past_rows = enriched[enriched["date"] == past_date]
        past_rows = past_rows[past_rows["sma_50"].notna()]
        past_pct = float((past_rows["close"] > past_rows["sma_50"]).mean()) if not past_rows.empty else None
        drop = (past_pct - pct_above_50) if past_pct is not None else None
        if near_high and drop is not None and drop >= 0.15:
            return {
                "status": "bearish",
                "message": (
                    f"Nifty 50 is within 1% of its 3-month high while only {pct_above_50:.0%} "
                    f"of stocks trade above their 50-day average, down from {past_pct:.0%} three months ago."
                ),
                "nifty_within_1pct_3m_high": True,
                "pct_above_50dma_now": pct_above_50,
                "pct_above_50dma_3m_ago": past_pct,
            }
        return {
            "status": "none",
            "message": "No major Nifty 50 versus 50-DMA breadth divergence detected.",
            "nifty_within_1pct_3m_high": near_high,
            "pct_above_50dma_now": pct_above_50,
            "pct_above_50dma_3m_ago": past_pct,
        }

    @staticmethod
    def _float_or_none(value: object) -> float | None:
        try:
            if pd.isna(value):
                return None
            return float(value)
        except (TypeError, ValueError):
            return None
