"""Index price ingestion helpers.

Reads:
  - Caller-supplied index names and date ranges

Writes:
  - `index_prices_daily`

Does not:
  - Compute indicators, scores, or sector metrics
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Iterable

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from db.models import IndexPricesDaily


@dataclass(frozen=True)
class IndexPriceBar:
    index_name: str
    date: date
    open: float | None
    high: float | None
    low: float | None
    close: float | None
    volume: int | None


@dataclass(frozen=True)
class IndexLoadResult:
    rows_loaded: int
    failures: list[str]


# Symbol mapping assumptions:
# NIFTY500: ^CRSLDX (Nifty500 Total Return Index from yfinance)
# This is the total return index which includes dividends, which is appropriate
# for relative strength calculations as it reflects total investor return.
INDEX_SYMBOL_MAP = {
    "NIFTY500": "^CRSLDX",
}


def _coerce_float(value) -> float | None:
    if value is None:
        return None
    if hasattr(value, "item"):
        try:
            value = value.item()
        except ValueError:
            value = value.iloc[0]
    try:
        if value != value:  # NaN
            return None
    except Exception:
        pass
    return float(value)


def _coerce_int(value) -> int | None:
    number = _coerce_float(value)
    return None if number is None else int(number)


def default_yfinance_index_fetcher(index_name: str, start_date: date, end_date: date) -> Iterable[IndexPriceBar]:
    """Download daily OHLCV rows for one index using yfinance."""
    import yfinance as yf

    # Map index name to yfinance ticker
    ticker = INDEX_SYMBOL_MAP.get(index_name, index_name)

    frame = yf.download(
        ticker,
        start=start_date.isoformat(),
        end=end_date.isoformat(),
        interval="1d",
        auto_adjust=False,
        progress=False,
        group_by="column",
        threads=False,
    )
    if frame.empty:
        return []

    bars: list[IndexPriceBar] = []
    for index, row in frame.iterrows():
        bars.append(
            IndexPriceBar(
                index_name=index_name,
                date=index.date(),
                open=_coerce_float(row.get("Open")),
                high=_coerce_float(row.get("High")),
                low=_coerce_float(row.get("Low")),
                close=_coerce_float(row.get("Close")),
                volume=_coerce_int(row.get("Volume")),
            )
        )
    return bars


class IndexLoader:
    def __init__(self, session_factory, index_fetcher=default_yfinance_index_fetcher):
        self.session_factory = session_factory
        self.index_fetcher = index_fetcher

    def load(self, start_date: date, end_date: date, index_names: Iterable[str]) -> IndexLoadResult:
        rows_loaded = 0
        failures: list[str] = []

        with self.session_factory() as session:
            for index_name in index_names:
                try:
                    bars = list(self.index_fetcher(index_name, start_date, end_date))
                    for bar in bars:
                        row = {
                            "index_name": bar.index_name,
                            "date": bar.date,
                            "open": bar.open,
                            "high": bar.high,
                            "low": bar.low,
                            "close": bar.close,
                            "volume": bar.volume,
                        }
                        dialect_name = session.bind.dialect.name if session.bind else "sqlite"
                        if dialect_name == "postgresql":
                            insert_stmt = pg_insert(IndexPricesDaily.__table__).values(**row).on_conflict_do_nothing(
                                index_elements=["index_name", "date"],
                            )
                        elif dialect_name == "sqlite":
                            insert_stmt = sqlite_insert(IndexPricesDaily.__table__).values(**row).prefix_with("OR IGNORE")
                        else:
                            insert_stmt = IndexPricesDaily.__table__.insert().values(**row)
                        result = session.execute(insert_stmt)
                        rows_loaded += int(getattr(result, "rowcount", 1) or 0)
                except Exception as exc:  # pragma: no cover - surfaced in result
                    failures.append(f"{index_name}: {exc}")
            session.commit()

        return IndexLoadResult(rows_loaded=rows_loaded, failures=failures)

    def backfill(self, index_name: str, start_date: date, end_date: date) -> IndexLoadResult:
        """Backfill historical data for a single index."""
        return self.load(start_date, end_date, [index_name])

    def incremental_update(self, index_name: str, start_date: date, end_date: date) -> IndexLoadResult:
        """Incrementally update data for a single index (typically recent dates)."""
        return self.load(start_date, end_date, [index_name])
