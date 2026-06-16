"""Price ingestion helpers.

Reads:
  - Caller-supplied symbols and a price fetcher

Writes:
  - `prices_daily`

Does not:
  - Compute indicators, scores, or sector metrics
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Iterable, Protocol

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from db.models import PricesDaily


@dataclass(frozen=True)
class PriceBar:
    symbol: str
    date: date
    open: float | None
    high: float | None
    low: float | None
    close: float | None
    volume: int | None


@dataclass(frozen=True)
class PriceLoadResult:
    rows_loaded: int
    failures: list[str]


class PriceFetcher(Protocol):
    def __call__(self, symbol: str, start_date: date, end_date: date) -> Iterable[PriceBar]:
        ...


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


def default_yfinance_fetcher(symbol: str, start_date: date, end_date: date) -> Iterable[PriceBar]:
    """Download daily OHLCV rows for one symbol using yfinance."""

    import yfinance as yf

    frame = yf.download(
        symbol,
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

    bars: list[PriceBar] = []
    for index, row in frame.iterrows():
        bars.append(
            PriceBar(
                symbol=symbol,
                date=index.date(),
                open=_coerce_float(row.get("Open")),
                high=_coerce_float(row.get("High")),
                low=_coerce_float(row.get("Low")),
                close=_coerce_float(row.get("Close")),
                volume=_coerce_int(row.get("Volume")),
            )
        )
    return bars


class PriceLoader:
    def __init__(self, session_factory, price_fetcher: PriceFetcher):
        self.session_factory = session_factory
        self.price_fetcher = price_fetcher

    def load(self, start_date: date, end_date: date, symbols: Iterable[str]) -> PriceLoadResult:
        rows_loaded = 0
        failures: list[str] = []

        with self.session_factory() as session:
            for symbol in symbols:
                try:
                    bars = list(self.price_fetcher(symbol, start_date, end_date))
                    for bar in bars:
                        row = {
                            "symbol": bar.symbol,
                            "date": bar.date,
                            "open": bar.open,
                            "high": bar.high,
                            "low": bar.low,
                            "close": bar.close,
                            "volume": bar.volume,
                        }
                        dialect_name = session.bind.dialect.name if session.bind else "sqlite"
                        if dialect_name == "postgresql":
                            insert_stmt = pg_insert(PricesDaily.__table__).values(**row).on_conflict_do_nothing(
                                index_elements=["symbol", "date"],
                            )
                        elif dialect_name == "sqlite":
                            insert_stmt = sqlite_insert(PricesDaily.__table__).values(**row).prefix_with("OR IGNORE")
                        else:
                            insert_stmt = PricesDaily.__table__.insert().values(**row)
                        result = session.execute(insert_stmt)
                        rows_loaded += int(getattr(result, "rowcount", 1) or 0)
                except Exception as exc:  # pragma: no cover - surfaced in result
                    failures.append(f"{symbol}: {exc}")
            session.commit()

        return PriceLoadResult(rows_loaded=rows_loaded, failures=failures)
