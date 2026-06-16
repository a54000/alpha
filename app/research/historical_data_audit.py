"""Read-only audits for historical data expansion.

Reads:
  - Current research database tables
  - Optional Angel SmartAPI source database

Writes:
  - Nothing

Does not:
  - Create factors, scores, recommendations, or market filters
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
from typing import Any

from sqlalchemy import bindparam, create_engine, func, select, text
from sqlalchemy.engine import Engine

from db.models import PricesDaily, SymbolMaster, UniverseSnapshot


@dataclass(frozen=True)
class DailyCoverageSummary:
    symbols_expected: int
    symbols_with_prices: int
    earliest_date: str | None
    latest_date: str | None
    total_rows: int
    median_rows_per_symbol: int
    symbols_with_less_than_5y: int


@dataclass(frozen=True)
class SourceCoverageSummary:
    available: bool
    table_name: str
    symbols_with_rows: int = 0
    earliest_datetime: str | None = None
    latest_datetime: str | None = None
    total_rows: int = 0
    symbols_missing_from_source: list[str] | None = None
    error: str | None = None


@dataclass(frozen=True)
class HistoricalDataAudit:
    generated_on: str
    current_daily: DailyCoverageSummary
    missing_price_symbols: list[str]
    sparse_price_symbols: list[dict[str, Any]]
    corporate_action_candidates: list[dict[str, Any]]
    source_15min: SourceCoverageSummary | None
    etl_plan: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def run_historical_data_audit(
    session_factory,
    *,
    source_database_url: str | None = None,
    source_table: str = "ohlcv_15min",
    min_years: int = 5,
    discontinuity_threshold_pct: float = 40.0,
    max_examples: int = 50,
) -> HistoricalDataAudit:
    """Build the next-phase historical data audit without mutating data."""

    expected_symbols = _active_nse500_symbols(session_factory)
    current_daily = _daily_coverage_summary(session_factory, expected_symbols, min_years=min_years)
    missing_price_symbols = _missing_price_symbols(session_factory, expected_symbols)
    sparse_price_symbols = _sparse_price_symbols(session_factory, expected_symbols, min_years=min_years, limit=max_examples)
    corporate_action_candidates = _corporate_action_candidates(
        session_factory,
        expected_symbols,
        threshold_pct=discontinuity_threshold_pct,
        limit=max_examples,
    )
    source_15min = None
    if source_database_url:
        source_engine = create_engine(source_database_url, future=True)
        source_15min = _source_15min_coverage(source_engine, source_table, expected_symbols)

    return HistoricalDataAudit(
        generated_on=date.today().isoformat(),
        current_daily=current_daily,
        missing_price_symbols=missing_price_symbols[:max_examples],
        sparse_price_symbols=sparse_price_symbols,
        corporate_action_candidates=corporate_action_candidates,
        source_15min=source_15min,
        etl_plan=_etl_plan(),
    )


def _active_nse500_symbols(session_factory) -> list[str]:
    with session_factory() as session:
        snapshot_date = session.execute(select(func.max(UniverseSnapshot.date))).scalar_one_or_none()
        if snapshot_date is not None:
            symbols = session.execute(
                select(UniverseSnapshot.symbol)
                .where(UniverseSnapshot.date == snapshot_date, UniverseSnapshot.index_name == "NSE500")
                .order_by(UniverseSnapshot.symbol)
            ).scalars().all()
            if symbols:
                return list(symbols)
        return list(
            session.execute(
                select(SymbolMaster.symbol).where(SymbolMaster.nse500.is_(True)).order_by(SymbolMaster.symbol)
            ).scalars()
        )


def _daily_coverage_summary(session_factory, expected_symbols: list[str], *, min_years: int) -> DailyCoverageSummary:
    with session_factory() as session:
        rows = session.execute(
            select(
                PricesDaily.symbol,
                func.count(PricesDaily.date),
                func.min(PricesDaily.date),
                func.max(PricesDaily.date),
            )
            .where(PricesDaily.symbol.in_(expected_symbols))
            .group_by(PricesDaily.symbol)
        ).all()

    row_counts = sorted(int(row[1]) for row in rows)
    median_rows = row_counts[len(row_counts) // 2] if row_counts else 0
    min_required_rows = min_years * 240
    earliest = min((row[2] for row in rows if row[2] is not None), default=None)
    latest = max((row[3] for row in rows if row[3] is not None), default=None)

    priced_symbol_count = len(row_counts)
    missing_symbol_count = max(0, len(expected_symbols) - priced_symbol_count)

    return DailyCoverageSummary(
        symbols_expected=len(expected_symbols),
        symbols_with_prices=priced_symbol_count,
        earliest_date=str(earliest) if earliest else None,
        latest_date=str(latest) if latest else None,
        total_rows=sum(row_counts),
        median_rows_per_symbol=median_rows,
        symbols_with_less_than_5y=missing_symbol_count + sum(1 for count in row_counts if count < min_required_rows),
    )


def _missing_price_symbols(session_factory, expected_symbols: list[str]) -> list[str]:
    with session_factory() as session:
        priced = set(
            session.execute(
                select(PricesDaily.symbol).where(PricesDaily.symbol.in_(expected_symbols)).group_by(PricesDaily.symbol)
            ).scalars()
        )
    return [symbol for symbol in expected_symbols if symbol not in priced]


def _sparse_price_symbols(session_factory, expected_symbols: list[str], *, min_years: int, limit: int) -> list[dict[str, Any]]:
    min_required_rows = min_years * 240
    with session_factory() as session:
        rows = session.execute(
            select(
                PricesDaily.symbol,
                func.count(PricesDaily.date).label("rows"),
                func.min(PricesDaily.date),
                func.max(PricesDaily.date),
            )
            .where(PricesDaily.symbol.in_(expected_symbols))
            .group_by(PricesDaily.symbol)
            .having(func.count(PricesDaily.date) < min_required_rows)
            .order_by("rows")
            .limit(limit)
        ).all()
    return [
        {"symbol": row[0], "rows": int(row[1]), "first_date": str(row[2]), "last_date": str(row[3])}
        for row in rows
    ]


def _corporate_action_candidates(
    session_factory,
    expected_symbols: list[str],
    *,
    threshold_pct: float,
    limit: int,
) -> list[dict[str, Any]]:
    if not expected_symbols:
        return []

    with session_factory() as session:
        dialect = session.bind.dialect.name if session.bind else ""
        if dialect == "sqlite":
            pct_expr = "ABS((CAST(close AS REAL) - CAST(prev_close AS REAL)) / CAST(prev_close AS REAL)) * 100.0"
        else:
            pct_expr = "ABS((close - prev_close) / NULLIF(prev_close, 0)) * 100.0"
        sql = text(
            f"""
            WITH ordered_prices AS (
                SELECT
                    symbol,
                    date,
                    close,
                    LAG(close) OVER (PARTITION BY symbol ORDER BY date) AS prev_close
                FROM prices_daily
                WHERE symbol IN :symbols
            )
            SELECT symbol, date, prev_close, close, {pct_expr} AS move_pct
            FROM ordered_prices
            WHERE prev_close IS NOT NULL
              AND prev_close > 0
              AND {pct_expr} >= :threshold_pct
            ORDER BY move_pct DESC
            LIMIT :limit
            """
        ).bindparams(
            bindparam("symbols", expanding=True),
            bindparam("threshold_pct"),
            bindparam("limit"),
        )
        rows = session.execute(
            sql,
            {"symbols": expected_symbols, "threshold_pct": threshold_pct, "limit": limit},
        ).all()

    return [
        {
            "symbol": row[0],
            "date": str(row[1]),
            "previous_close": float(row[2]),
            "close": float(row[3]),
            "move_pct": float(row[4]),
            "review_reason": "large close-to-close discontinuity; check split/bonus/dividend adjustment",
        }
        for row in rows
    ]


def _source_15min_coverage(engine: Engine, table_name: str, expected_symbols: list[str]) -> SourceCoverageSummary:
    try:
        with engine.connect() as connection:
            table_exists = connection.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM information_schema.tables
                    WHERE table_name = :table_name
                    """
                ),
                {"table_name": table_name},
            ).scalar_one()
            if int(table_exists) == 0:
                return SourceCoverageSummary(available=False, table_name=table_name, error="source table not found")

            coverage = connection.execute(
                text(
                    f"""
                    SELECT COUNT(DISTINCT symbol), MIN(datetime), MAX(datetime), COUNT(*)
                    FROM {table_name}
                    """
                )
            ).one()
            source_symbols = set(connection.execute(text(f"SELECT DISTINCT symbol FROM {table_name}")).scalars())
    except Exception as exc:  # pragma: no cover - depends on external source DB
        return SourceCoverageSummary(available=False, table_name=table_name, error=str(exc))

    missing = [symbol for symbol in expected_symbols if symbol not in source_symbols]
    return SourceCoverageSummary(
        available=True,
        table_name=table_name,
        symbols_with_rows=int(coverage[0] or 0),
        earliest_datetime=str(coverage[1]) if coverage[1] else None,
        latest_datetime=str(coverage[2]) if coverage[2] else None,
        total_rows=int(coverage[3] or 0),
        symbols_missing_from_source=missing,
    )


def _etl_plan() -> list[str]:
    return [
        "Freeze Swing V2.1 logic and expand only the underlying historical OHLCV input.",
        "Audit Angel 15-minute coverage by symbol and earliest timestamp before loading any rows.",
        "Aggregate 15-minute bars to daily OHLCV with exchange-session boundaries and one row per symbol/date.",
        "Load into a staging table first; compare staged daily bars against existing prices_daily overlaps.",
        "Review large price discontinuities for split/bonus adjustment before feature recomputation.",
        "Backfill prices_daily only after coverage and corporate-action checks pass.",
        "Recompute features_daily, sector_daily, daily_scores, and recommendation_history for the expanded range.",
        "Re-run the frozen Swing V2.1 trade and portfolio backtests over the longest validated range.",
    ]
