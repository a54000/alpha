from __future__ import annotations

from datetime import date, timedelta

from app.api.rolling_portfolio_service import RollingPortfolioRequest, RollingPortfolioSimulationService


def trading_dates(count: int, start: date = date(2026, 1, 5)) -> list[date]:
    cursor = start
    dates: list[date] = []
    while len(dates) < count:
        if cursor.weekday() < 5:
            dates.append(cursor)
        cursor += timedelta(days=1)
    return dates


def recommendations(signal_dates: list[date]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    symbols = ["AAA", "BBB", "CCC", "DDD", "EEE"]
    for signal_date in signal_dates:
        for index, symbol in enumerate(symbols, start=1):
            rows.append(
                {
                    "date": signal_date,
                    "rank": index,
                    "symbol": symbol,
                    "score": 80.0 - index,
                    "sector": "IT",
                }
            )
    return rows


def prices(symbols: list[str], dates: list[date]) -> dict[str, dict[date, dict[str, float]]]:
    return {
        symbol: {
            item: {
                "open": 100.0 + offset,
                "high": 102.0 + offset,
                "low": 99.0 + offset,
                "close": 101.0 + offset,
            }
            for offset, item in enumerate(dates)
        }
        for symbol in symbols
    }


def test_selected_week_marks_portfolio_on_entry_date_not_latest_available_date():
    dates = trading_dates(45)
    service = RollingPortfolioSimulationService(angel_engine=None)
    result = service._simulate(
        RollingPortfolioRequest(start_date=dates[0], weeks=1, initial_capital=100_000),
        recommendations([dates[0]]),
        prices(["AAA", "BBB", "CCC", "DDD", "EEE"], dates),
        [dates[0]],
    )

    assert result["summary"]["mark_date"] == dates[1].isoformat()
    assert result["summary"]["open_positions"] == 5
    assert result["summary"]["closed_trades"] == 0
    assert len(result["positions"]) == 5
    assert result["trades"] == []


def test_positions_close_only_after_step_reaches_planned_exit_date():
    dates = trading_dates(45)
    signal_dates = [dates[0], dates[5], dates[10], dates[15], dates[20]]
    service = RollingPortfolioSimulationService(angel_engine=None)
    result = service._simulate(
        RollingPortfolioRequest(start_date=dates[0], weeks=len(signal_dates), initial_capital=100_000),
        recommendations(signal_dates),
        prices(["AAA", "BBB", "CCC", "DDD", "EEE"], dates),
        signal_dates,
    )

    assert result["summary"]["mark_date"] == dates[21].isoformat()
    assert result["summary"]["closed_trades"] == 5
    assert {trade["exit_date"] for trade in result["trades"]} == {dates[20].isoformat()}
