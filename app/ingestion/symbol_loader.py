"""Symbol ingestion helpers.

Reads:
  - Iterable NSE500 constituent records supplied by the caller

Writes:
  - `symbol_master`
  - `universe_snapshot`

Does not:
  - Fetch constituents from external services
  - Compute indicators or scores
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Iterable

from sqlalchemy import select

from db.models import SymbolMaster, UniverseSnapshot


@dataclass(frozen=True)
class ConstituentRecord:
    symbol: str
    company_name: str | None = None
    sector: str | None = None
    subsector: str | None = None


@dataclass(frozen=True)
class SymbolLoadResult:
    symbols_loaded: int
    snapshot_rows_loaded: int
    failures: list[str]


class SymbolLoader:
    def __init__(self, session_factory):
        self.session_factory = session_factory

    def load(self, snapshot_date: date, constituents: Iterable[ConstituentRecord]) -> SymbolLoadResult:
        symbols_loaded = 0
        snapshot_rows_loaded = 0
        failures: list[str] = []

        with self.session_factory() as session:
            for record in constituents:
                try:
                    existing = session.execute(
                        select(SymbolMaster).where(SymbolMaster.symbol == record.symbol)
                    ).scalar_one_or_none()
                    if existing is None:
                        session.add(
                            SymbolMaster(
                                symbol=record.symbol,
                                company_name=record.company_name,
                                sector=record.sector,
                                subsector=record.subsector,
                                nse500=True,
                            )
                        )
                        symbols_loaded += 1

                    snapshot_exists = session.execute(
                        select(UniverseSnapshot).where(
                            UniverseSnapshot.date == snapshot_date,
                            UniverseSnapshot.symbol == record.symbol,
                            UniverseSnapshot.index_name == "NSE500",
                        )
                    ).scalar_one_or_none()
                    if snapshot_exists is None:
                        session.add(
                            UniverseSnapshot(date=snapshot_date, symbol=record.symbol, index_name="NSE500")
                        )
                        snapshot_rows_loaded += 1
                except Exception as exc:  # pragma: no cover - surfaced in result
                    failures.append(f"{record.symbol}: {exc}")
            session.commit()

        return SymbolLoadResult(symbols_loaded=symbols_loaded, snapshot_rows_loaded=snapshot_rows_loaded, failures=failures)
