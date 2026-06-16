"""Data validation helpers for ingested market data.

Reads:
  - `prices_daily`
  - Existing `data_quality_log` rows

Writes:
  - `data_quality_log`

Does not:
  - Fetch external market data
  - Modify indicators, scoring, or backtest state
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import func, select

from db.models import DataQualityLog, PricesDaily


@dataclass(frozen=True)
class ValidationResult:
    duplicate_count: int
    missing_trading_date_count: int
    invalid_price_count: int
    zero_volume_count: int


class DataValidator:
    def __init__(self, session_factory):
        self.session_factory = session_factory

    def validate_prices(self, validation_date: date, symbols: list[str]) -> ValidationResult:
        with self.session_factory() as session:
            duplicate_count = sum(
                count - 1
                for (count,) in session.execute(
                    select(func.count())
                    .select_from(PricesDaily)
                    .where(PricesDaily.date == validation_date, PricesDaily.symbol.in_(symbols))
                    .group_by(PricesDaily.symbol, PricesDaily.date)
                ).all()
                if count > 1
            )
            invalid_price_count = session.execute(
                select(func.count())
                .select_from(PricesDaily)
                .where(
                    PricesDaily.date == validation_date,
                    PricesDaily.symbol.in_(symbols),
                    (
                        PricesDaily.open.is_(None)
                        | PricesDaily.high.is_(None)
                        | PricesDaily.low.is_(None)
                        | PricesDaily.close.is_(None)
                        | (PricesDaily.low > PricesDaily.high)
                        | (PricesDaily.open < 0)
                        | (PricesDaily.close < 0)
                    ),
                )
            ).scalar_one()
            zero_volume_count = session.execute(
                select(func.count())
                .select_from(PricesDaily)
                .where(
                    PricesDaily.date == validation_date,
                    PricesDaily.symbol.in_(symbols),
                    PricesDaily.volume == 0,
                )
            ).scalar_one()
            missing_trading_date_count = self._count_missing_dates(session, validation_date, symbols)

            error_message = (
                f"duplicates={duplicate_count}, invalid_prices={invalid_price_count}, "
                f"zero_volume={zero_volume_count}, missing_dates={missing_trading_date_count}"
            )
            session.add(
                DataQualityLog(
                    date=validation_date,
                    job_name="price_validation",
                    records_expected=len(symbols),
                    records_loaded=len(symbols),
                    status="ok"
                    if not any([duplicate_count, invalid_price_count, zero_volume_count, missing_trading_date_count])
                    else "partial",
                    error_message=None
                    if not any([duplicate_count, invalid_price_count, zero_volume_count, missing_trading_date_count])
                    else error_message,
                )
            )
            session.commit()

        return ValidationResult(
            duplicate_count=duplicate_count,
            missing_trading_date_count=missing_trading_date_count,
            invalid_price_count=invalid_price_count,
            zero_volume_count=zero_volume_count,
        )

    def _count_missing_dates(self, session, validation_date: date, symbols: list[str]) -> int:
        expected_dates = {validation_date - timedelta(days=offset) for offset in range(0, 5)}
        loaded_dates = {
            row[0]
            for row in session.execute(
                select(PricesDaily.date)
                .where(PricesDaily.symbol.in_(symbols), PricesDaily.date.in_(expected_dates))
                .group_by(PricesDaily.date)
            ).all()
        }
        return len(expected_dates - loaded_dates)
