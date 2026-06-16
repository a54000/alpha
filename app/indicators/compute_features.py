"""Feature computation and storage for the NSE Research Platform.

Reads:
  - `prices_daily`
  - `symbol_master`

Writes:
  - `features_daily`

Does not:
  - Perform scoring, ranking, sector rotation, or backtesting
  - Fetch market data from external APIs
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, timedelta
from pathlib import Path
import json
import math
from typing import Iterable

import pandas as pd
import numpy as np
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from db.models import FeaturesDaily, IndexPricesDaily, PricesDaily, SymbolMaster

WARMUP_DAYS = 300
STOCH_K_PERIOD = 14
STOCH_SMOOTH_K = 3
STOCH_D_PERIOD = 3

FEATURE_COLUMNS = {
    column.name
    for column in FeaturesDaily.__table__.columns
    if column.name not in {"symbol", "date"}
}


@dataclass(frozen=True)
class FeatureGenerationReport:
    symbols_processed: int
    rows_written: int
    failures: list[str]
    missing_data_summary: dict[str, int]


def write_feature_report(report: FeatureGenerationReport, output_path: str | Path) -> Path:
    path = Path(output_path)
    path.write_text(json.dumps(asdict(report), indent=2, sort_keys=True), encoding="utf-8")
    return path


def compute_stochastic(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    *,
    k_period: int = STOCH_K_PERIOD,
    smooth_k: int = STOCH_SMOOTH_K,
    d_period: int = STOCH_D_PERIOD,
) -> tuple[pd.Series, pd.Series]:
    """Slow stochastic oscillator per INDICATOR_SPEC (k=14, smooth_k=3, d=3)."""

    lowest_low = low.rolling(k_period).min()
    highest_high = high.rolling(k_period).max()
    denominator = (highest_high - lowest_low).replace(0, np.nan)
    raw_k = 100 * (close - lowest_low) / denominator
    stoch_k = raw_k.rolling(smooth_k).mean()
    stoch_d = stoch_k.rolling(d_period).mean()
    return stoch_k, stoch_d


def compute_rs_rank_pct(rs_vs_nifty_20d: pd.Series) -> pd.Series:
    """Cross-sectional percentile rank (0-100) for one trading date."""

    valid = rs_vs_nifty_20d.dropna()
    if valid.empty:
        return pd.Series(index=rs_vs_nifty_20d.index, dtype="float64")
    ranks = valid.rank(pct=True, method="average") * 100
    return ranks.reindex(rs_vs_nifty_20d.index)


class FeatureComputer:
    def __init__(self, session_factory):
        self.session_factory = session_factory

    def generate(self, start_date: date | None = None, end_date: date | None = None) -> FeatureGenerationReport:
        failures: list[str] = []
        rows_written = 0
        symbols_processed = 0
        missing_data_summary = {"missing_prices": 0}

        with self.session_factory() as session:
            symbols = [row[0] for row in session.execute(select(SymbolMaster.symbol).order_by(SymbolMaster.symbol)).all()]
            if not symbols:
                return FeatureGenerationReport(0, 0, [], missing_data_summary)

            if end_date is None:
                end_date = session.execute(select(PricesDaily.date).order_by(PricesDaily.date.desc())).scalars().first()
            if start_date is None:
                existing_latest = session.execute(select(FeaturesDaily.date).order_by(FeaturesDaily.date.desc())).scalars().first()
                if existing_latest is not None:
                    start_date = existing_latest + timedelta(days=1)
                else:
                    first_price = session.execute(select(PricesDaily.date).order_by(PricesDaily.date.asc())).scalars().first()
                    start_date = first_price

            if start_date is None or end_date is None or start_date > end_date:
                return FeatureGenerationReport(0, 0, [], missing_data_summary)

            load_start = start_date - timedelta(days=WARMUP_DAYS)
            sector_map = dict(session.execute(select(SymbolMaster.symbol, SymbolMaster.sector)).all())
            
            # Load Nifty500 index prices for relative strength calculation
            index_prices = self._load_index_frame(session, "NIFTY500", load_start, end_date)

            for symbol in symbols:
                try:
                    with session.begin_nested():
                        df = self._load_price_frame(session, symbol, load_start, end_date)
                        if df.empty:
                            continue
                        feature_rows = self._compute_symbol_features(symbol, df, index_prices=index_prices, sector=sector_map.get(symbol))
                        persist_rows = feature_rows[feature_rows["date"] >= start_date]
                        rows_written += self._upsert_features(session, persist_rows)
                        symbols_processed += 1
                except Exception as exc:  # pragma: no cover - surfaced in report
                    failures.append(f"{symbol}: {exc}")

            try:
                self._apply_rs_rank_pct(session, start_date, end_date)
            except Exception as exc:  # pragma: no cover - surfaced in report
                failures.append(f"rs_rank_pct: {exc}")

            session.commit()

        return FeatureGenerationReport(
            symbols_processed=symbols_processed,
            rows_written=rows_written,
            failures=failures,
            missing_data_summary=missing_data_summary,
        )

    def _load_price_frame(self, session, symbol: str, start_date: date, end_date: date) -> pd.DataFrame:
        rows = session.execute(
            select(PricesDaily).where(PricesDaily.symbol == symbol, PricesDaily.date.between(start_date, end_date)).order_by(PricesDaily.date)
        ).scalars().all()
        if not rows:
            return pd.DataFrame()
        frame = pd.DataFrame(
            [
                {
                    "date": row.date,
                    "open": float(row.open) if row.open is not None else math.nan,
                    "high": float(row.high) if row.high is not None else math.nan,
                    "low": float(row.low) if row.low is not None else math.nan,
                    "close": float(row.close) if row.close is not None else math.nan,
                    "volume": float(row.volume) if row.volume is not None else math.nan,
                }
                for row in rows
            ]
        )
        for column in ["open", "high", "low", "close", "volume"]:
            frame[column] = pd.to_numeric(frame[column], errors="coerce").astype("float64")
        frame = frame.set_index("date").sort_index()
        return frame

    def _load_index_frame(self, session, index_name: str, start_date: date, end_date: date) -> pd.DataFrame:
        rows = session.execute(
            select(IndexPricesDaily).where(
                IndexPricesDaily.index_name == index_name,
                IndexPricesDaily.date.between(start_date, end_date)
            ).order_by(IndexPricesDaily.date)
        ).scalars().all()
        if not rows:
            return pd.DataFrame()
        frame = pd.DataFrame(
            [
                {
                    "date": row.date,
                    "close": float(row.close) if row.close is not None else math.nan,
                }
                for row in rows
            ]
        )
        frame["close"] = pd.to_numeric(frame["close"], errors="coerce").astype("float64")
        frame = frame.set_index("date").sort_index()
        return frame

    def _compute_symbol_features(self, symbol: str, prices: pd.DataFrame, *, index_prices: pd.DataFrame | None = None, sector: str | None = None) -> pd.DataFrame:
        close = prices["close"]
        high = prices["high"]
        low = prices["low"]
        volume = prices["volume"]

        result = pd.DataFrame(index=prices.index)
        result["ema_5"] = close.ewm(span=5, adjust=False).mean()
        result["ema_13"] = close.ewm(span=13, adjust=False).mean()
        result["ema_20"] = close.ewm(span=20, adjust=False).mean()
        result["ema_50"] = close.ewm(span=50, adjust=False).mean()
        result["ema_150"] = close.ewm(span=150, adjust=False).mean()
        result["ema_200"] = close.ewm(span=200, adjust=False).mean()

        delta = close.diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.rolling(14).mean()
        avg_loss = loss.rolling(14).mean()
        rs = avg_gain / avg_loss.replace(0, pd.NA)
        rsi = 100 - (100 / (1 + rs))
        rsi = rsi.where(avg_loss != 0, 100.0)
        rsi = rsi.where(avg_gain != 0, 0.0)
        result["rsi_14"] = rsi

        ema12 = close.ewm(span=12, adjust=False).mean()
        ema26 = close.ewm(span=26, adjust=False).mean()
        result["macd_line"] = ema12 - ema26
        result["macd_signal"] = result["macd_line"].ewm(span=9, adjust=False).mean()
        result["macd_hist"] = result["macd_line"] - result["macd_signal"]
        result["macd_hist_prev"] = result["macd_hist"].shift(1)

        prev_close = close.shift(1)
        tr = pd.concat([(high - low), (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
        result["atr_14"] = tr.rolling(14).mean()

        up_move = high.diff()
        down_move = -low.diff()
        plus_dm = up_move.where((up_move > down_move) & (up_move > 0), 0.0)
        minus_dm = down_move.where((down_move > up_move) & (down_move > 0), 0.0)
        atr_wilder = tr.ewm(alpha=1 / 14, adjust=False).mean()
        plus_di = 100 * plus_dm.ewm(alpha=1 / 14, adjust=False).mean() / atr_wilder.replace(0, np.nan)
        minus_di = 100 * minus_dm.ewm(alpha=1 / 14, adjust=False).mean() / atr_wilder.replace(0, np.nan)
        dx = ((plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)) * 100
        result["adx_14"] = dx.ewm(alpha=1 / 14, adjust=False).mean()
        result["adx_prev"] = result["adx_14"].shift(1)

        mid = close.rolling(20).mean()
        std = close.rolling(20).std(ddof=0)
        upper = mid + (2 * std)
        lower = mid - (2 * std)
        result["bb_upper"] = upper
        result["bb_mid"] = mid
        result["bb_lower"] = lower
        result["bb_width"] = (upper - lower) / mid
        result["bb_width_20avg"] = result["bb_width"].rolling(20).mean()
        result["bb_pct"] = (close - lower) / (upper - lower).replace(0, np.nan)

        stoch_k, stoch_d = compute_stochastic(high, low, close)
        result["stoch_k"] = stoch_k
        result["stoch_d"] = stoch_d

        volume_20avg = volume.rolling(20).mean()
        result["volume_20avg"] = volume_20avg.round().astype("Int64")
        result["volume_ratio"] = volume / volume_20avg

        high_252 = high.rolling(252).max()
        low_252 = low.rolling(252).min()
        result["pct_from_52w_high"] = (close - high_252) / high_252 * 100
        result["distance_from_52w_high"] = high_252 - close
        result["pct_from_52w_low"] = (close - low_252) / low_252 * 100
        result["high_52w"] = high_252
        result["low_52w"] = low_252

        # Compute true relative strength using benchmark returns
        # Formula: stock_return_Nd - nifty500_return_Nd (subtraction for stability)
        stock_return_20d = close.pct_change(20)
        stock_return_60d = close.pct_change(60)
        
        if index_prices is not None and not index_prices.empty:
            # Align index close prices with stock dates first, then compute returns
            index_close = index_prices["close"]
            index_close_aligned = index_close.reindex(close.index)
            
            # Compute returns on aligned data
            index_return_20d = index_close_aligned.pct_change(20)
            index_return_60d = index_close_aligned.pct_change(60)
            
            # Compute relative strength: stock_return - index_return (subtraction for stability)
            # This avoids division-by-zero and overflow issues with the ratio formula
            result["rs_vs_nifty_20d"] = stock_return_20d - index_return_20d
            result["rs_vs_nifty_60d"] = stock_return_60d - index_return_60d
        else:
            # Fallback to absolute returns if index data unavailable (should not happen in production)
            result["rs_vs_nifty_20d"] = stock_return_20d
            result["rs_vs_nifty_60d"] = stock_return_60d

        result["avg_traded_value"] = close * volume
        result["is_eligible"] = (
            (result["avg_traded_value"].rolling(20).mean() >= 100_000_000)
            & (volume_20avg >= 100_000)
            & (close >= 10)
        )
        result["is_52w_breakout"] = result["pct_from_52w_high"] >= 0
        result["sector"] = sector

        result["symbol"] = symbol
        result["date"] = result.index
        return result.reset_index(drop=True)

    def _apply_rs_rank_pct(self, session, start_date: date, end_date: date) -> int:
        updated = 0
        dates = session.execute(
            select(FeaturesDaily.date)
            .where(FeaturesDaily.date.between(start_date, end_date))
            .distinct()
            .order_by(FeaturesDaily.date)
        ).scalars().all()

        for current_date in dates:
            # Filter to NSE500 universe only
            rows = session.execute(
                select(FeaturesDaily.symbol, FeaturesDaily.rs_vs_nifty_20d)
                .join(SymbolMaster, FeaturesDaily.symbol == SymbolMaster.symbol)
                .where(
                    FeaturesDaily.date == current_date,
                    SymbolMaster.nse500 == True,
                    SymbolMaster.nse500_from_date <= current_date,
                    (SymbolMaster.nse500_to_date >= current_date) | (SymbolMaster.nse500_to_date.is_(None))
                )
            ).all()
            if not rows:
                continue

            rank_frame = pd.Series(
                {symbol: float(value) if value is not None else math.nan for symbol, value in rows},
                dtype="float64",
            )
            rank_pct = compute_rs_rank_pct(rank_frame)

            for symbol, value in rank_pct.items():
                if pd.isna(value):
                    continue
                session.execute(
                    update(FeaturesDaily)
                    .where(FeaturesDaily.symbol == symbol, FeaturesDaily.date == current_date)
                    .values(rs_rank_pct=round(float(value), 2))
                )
                updated += 1
        return updated

    def _sanitize_payload(self, payload: dict[str, object]) -> dict[str, object]:
        numeric_limits = {
            "rsi_14": 9999.99,
            "adx_14": 9999.99,
            "adx_prev": 9999.99,
            "stoch_k": 9999.99,
            "stoch_d": 9999.99,
            "pct_from_52w_high": 9999.99,
            "distance_from_52w_high": 9999.99,
            "volume_ratio": 999999.99,
            "rs_rank_pct": 9999.99,
        }
        sanitized: dict[str, object] = {}
        for key, value in payload.items():
            if key not in FEATURE_COLUMNS:
                continue
            if value is None or (isinstance(value, float) and math.isnan(value)):
                sanitized[key] = None
                continue
            if key == "volume_20avg" and value is not pd.NA:
                try:
                    sanitized[key] = int(value)
                except (TypeError, ValueError):
                    sanitized[key] = None
                continue
            if key in numeric_limits:
                try:
                    number = float(value)
                except (TypeError, ValueError):
                    sanitized[key] = None
                    continue
                if math.isnan(number) or math.isinf(number) or abs(number) >= numeric_limits[key]:
                    sanitized[key] = None
                    continue
                sanitized[key] = number
                continue
            sanitized[key] = value
        return sanitized

    def _upsert_features(self, session, features: pd.DataFrame) -> int:
        written = 0
        dialect_name = session.bind.dialect.name if session.bind else "sqlite"
        for _, row in features.iterrows():
            payload = self._sanitize_payload(row.to_dict())
            payload["symbol"] = row["symbol"]
            payload["date"] = row["date"]
            insert_stmt = FeaturesDaily.__table__.insert().values(**payload)
            if dialect_name == "postgresql":
                insert_stmt = pg_insert(FeaturesDaily.__table__).values(**payload).on_conflict_do_update(
                    index_elements=["symbol", "date"],
                    set_=payload,
                )
            elif dialect_name == "sqlite":
                insert_stmt = sqlite_insert(FeaturesDaily.__table__).values(**payload).on_conflict_do_update(
                    index_elements=["symbol", "date"],
                    set_=payload,
                )
            result = session.execute(insert_stmt)
            written += int(getattr(result, "rowcount", 1) or 0)
        return written
