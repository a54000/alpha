"""Sector strength computation and persistence.

Reads:
  - `symbol_master`
  - `prices_daily`

Writes:
  - `sector_daily`

Does not:
  - Score stocks
  - Rank stocks
  - Perform backtesting or external API calls
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, timedelta
from pathlib import Path
import json
from typing import Iterable

import pandas as pd
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from db.models import PricesDaily, SectorDaily, SymbolMaster


@dataclass(frozen=True)
class SectorStrengthReport:
    sectors_processed: int
    dates_processed: int
    rows_written: int
    failures: list[str]
    missing_data_summary: dict[str, int]


def write_sector_strength_report(report: SectorStrengthReport, output_path: str | Path) -> Path:
    path = Path(output_path)
    path.write_text(json.dumps(asdict(report), indent=2, sort_keys=True), encoding="utf-8")
    return path


class SectorStrengthComputer:
    def __init__(self, session_factory):
        self.session_factory = session_factory

    def generate(self, start_date: date | None = None, end_date: date | None = None) -> SectorStrengthReport:
        failures: list[str] = []
        rows_written = 0
        dates_processed = 0
        sectors_processed = 0
        missing_data_summary = {"insufficient_history": 0}

        with self.session_factory() as session:
            sectors = [
                row[0]
                for row in session.execute(
                    select(SymbolMaster.sector).where(SymbolMaster.sector.is_not(None)).distinct().order_by(SymbolMaster.sector)
                ).all()
            ]
            if not sectors:
                return SectorStrengthReport(0, 0, 0, [], missing_data_summary)

            if end_date is None:
                end_date = session.execute(select(PricesDaily.date).order_by(PricesDaily.date.desc())).scalars().first()
            if start_date is None:
                existing_latest = session.execute(select(SectorDaily.date).order_by(SectorDaily.date.desc())).scalars().first()
                if existing_latest is not None:
                    start_date = existing_latest + timedelta(days=1)
                else:
                    start_date = session.execute(select(PricesDaily.date).order_by(PricesDaily.date.asc())).scalars().first()

            if start_date is None or end_date is None:
                return SectorStrengthReport(0, 0, 0, [], missing_data_summary)

            price_frame = self._load_prices(session, sectors, start_date - timedelta(days=200), end_date)
            if price_frame.empty:
                return SectorStrengthReport(0, 0, 0, [], missing_data_summary)

            for current_date in self._date_range(start_date, end_date):
                date_frame = price_frame[price_frame["date"] <= current_date]
                if date_frame.empty:
                    missing_data_summary["insufficient_history"] += 1
                    continue

                sector_rows = self._compute_date(date_frame, current_date)
                if sector_rows.empty:
                    missing_data_summary["insufficient_history"] += 1
                    continue

                try:
                    dates_processed += 1
                    sectors_processed += len(sector_rows)
                    rows_written += self._upsert_rows(session, sector_rows)
                except Exception as exc:  # pragma: no cover - surfaced in report
                    failures.append(f"{current_date}: {exc}")
            session.commit()

        return SectorStrengthReport(
            sectors_processed=sectors_processed,
            dates_processed=dates_processed,
            rows_written=rows_written,
            failures=failures,
            missing_data_summary=missing_data_summary,
        )

    def _load_prices(self, session, sectors: list[str], start_date: date, end_date: date) -> pd.DataFrame:
        symbols = [
            row[0]
            for row in session.execute(
                select(SymbolMaster.symbol).where(SymbolMaster.sector.in_(sectors), SymbolMaster.nse500.is_(True))
            ).all()
        ]
        if not symbols:
            return pd.DataFrame()

        rows = session.execute(
            select(PricesDaily.symbol, PricesDaily.date, PricesDaily.close)
            .where(PricesDaily.symbol.in_(symbols), PricesDaily.date.between(start_date, end_date))
            .order_by(PricesDaily.date, PricesDaily.symbol)
        ).all()
        if not rows:
            return pd.DataFrame()

        frame = pd.DataFrame(rows, columns=["symbol", "date", "close"])
        frame["close"] = pd.to_numeric(frame["close"], errors="coerce")
        return frame

    def _compute_date(self, price_frame: pd.DataFrame, current_date: date) -> pd.DataFrame:
        current_date = pd.Timestamp(current_date).date()
        with self.session_factory() as session:
            symbol_map = dict(
                session.execute(
                    select(SymbolMaster.symbol, SymbolMaster.sector).where(SymbolMaster.symbol.in_(price_frame["symbol"].unique()))
                ).all()
            )

        price_frame = price_frame.copy()
        price_frame["sector"] = price_frame["symbol"].map(symbol_map)

        result_rows = []
        for sector, sector_frame in price_frame.groupby("sector"):
            stock_count = int(sector_frame["symbol"].nunique())

            return_1m = self._sector_period_return(sector_frame, 21, current_date)
            return_3m = self._sector_period_return(sector_frame, 63, current_date)
            return_6m = self._sector_period_return(sector_frame, 126, current_date)
            if return_1m is None and return_3m is None and return_6m is None:
                continue

            sector_score = (
                (return_1m or 0.0) * 0.20
                + (return_3m or 0.0) * 0.50
                + (return_6m or 0.0) * 0.30
            )

            result_rows.append(
                {
                    "date": current_date,
                    "sector": sector,
                    "return_1m": return_1m,
                    "return_3m": return_3m,
                    "return_6m": return_6m,
                    "sector_score": sector_score,
                    "sector_rank": None,
                    "sector_return_1m": return_1m,
                    "sector_return_3m": return_3m,
                    "sector_return_6m": return_6m,
                    "composite_score": sector_score,
                    "rank_3m": None,
                    "rank_composite": None,
                    "stock_count": stock_count,
                }
            )

        if not result_rows:
            return pd.DataFrame()

        result = pd.DataFrame(result_rows)
        result["sector_rank"] = result["sector_score"].rank(ascending=False, method="min", na_option="bottom").fillna(len(result) + 1).astype(int)
        result["rank_3m"] = result["return_3m"].rank(ascending=False, method="min", na_option="bottom").fillna(len(result) + 1).astype(int)
        result["rank_composite"] = result["sector_score"].rank(ascending=False, method="min", na_option="bottom").fillna(len(result) + 1).astype(int)
        result["sector_return_1m"] = result["return_1m"]
        result["sector_return_3m"] = result["return_3m"]
        result["sector_return_6m"] = result["return_6m"]
        result["composite_score"] = result["sector_score"]
        return result

    def _sector_period_return(self, sector_frame: pd.DataFrame, periods_back: int, current_date: date) -> float | None:
        stock_returns: list[float] = []
        for _, symbol_frame in sector_frame.groupby("symbol"):
            close = symbol_frame.set_index("date")["close"].sort_index()
            stock_return = self._period_return(close, periods_back, current_date)
            if stock_return is not None:
                stock_returns.append(stock_return)
        if not stock_returns:
            return None
        return float(sum(stock_returns) / len(stock_returns))

    def _period_return(self, series: pd.Series, periods_back: int, current_date: date) -> float | None:
        current_date = pd.Timestamp(current_date).date()
        if current_date not in series.index:
            return None
        current_position = series.index.get_loc(current_date)
        if isinstance(current_position, slice):
            current_position = current_position.start
        lookback_position = current_position - periods_back
        if lookback_position < 0:
            return None
        current_close = series.iloc[current_position]
        past_close = series.iloc[lookback_position]
        if pd.isna(current_close) or pd.isna(past_close) or past_close == 0:
            return None
        return float((current_close / past_close) - 1)

    def _upsert_rows(self, session, sector_rows: pd.DataFrame) -> int:
        written = 0
        dialect_name = session.bind.dialect.name if session.bind else "sqlite"
        for _, row in sector_rows.iterrows():
            payload = row.to_dict()
            existing = session.execute(
                select(SectorDaily).where(SectorDaily.sector == payload["sector"], SectorDaily.date == payload["date"])
            ).scalar_one_or_none()
            if existing is not None:
                continue
            insert_stmt = SectorDaily.__table__.insert().values(**payload)
            if dialect_name == "postgresql":
                insert_stmt = pg_insert(SectorDaily.__table__).values(**payload).on_conflict_do_update(
                    index_elements=["sector", "date"],
                    set_=payload,
                )
            elif dialect_name == "sqlite":
                insert_stmt = sqlite_insert(SectorDaily.__table__).values(**payload).prefix_with("OR IGNORE")
            result = session.execute(insert_stmt)
            written += int(getattr(result, "rowcount", 1) or 0)
        return written

    def _date_range(self, start_date: date, end_date: date) -> Iterable[date]:
        current = start_date
        while current <= end_date:
            yield current
            current += timedelta(days=1)
