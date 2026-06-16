from __future__ import annotations

import importlib.util
import sys
from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text


REPO_ROOT = Path(__file__).resolve().parents[1]


def load_attribution():
    name = "generate_performance_attribution"
    spec = importlib.util.spec_from_file_location(name, REPO_ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def seed_engine():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE paper_trades (portfolio_id integer, symbol text, sector text, entry_date date, exit_date date, realized_pnl numeric)"))
        connection.execute(text("CREATE TABLE paper_positions (portfolio_id integer, symbol text, sector text, entry_date date, planned_exit_date date, unrealized_pnl numeric, market_value numeric, status text)"))
        connection.execute(
            text("INSERT INTO paper_trades VALUES (1, 'AAA', 'IT', '2026-01-01', '2026-01-21', 1000), (1, 'BBB', 'Energy', '2026-01-01', '2026-01-21', -250)")
        )
        connection.execute(
            text("INSERT INTO paper_positions VALUES (1, 'AAA', 'IT', '2026-02-01', '2026-02-21', 300, 6000, 'open'), (1, 'CCC', 'IT', '2026-02-01', '2026-02-21', 200, 4000, 'open')")
        )
    return engine


def test_position_and_sector_attribution():
    attribution = load_attribution()
    engine = seed_engine()

    positions = attribution.position_contribution(engine, 1)
    sectors = attribution.sector_attribution(engine, 1, positions)

    aaa = next(row for row in positions if row["symbol"] == "AAA")
    assert aaa["realized_contribution"] == pytest.approx(1000)
    assert aaa["unrealized_contribution"] == pytest.approx(300)
    assert aaa["total_contribution"] == pytest.approx(1300)

    it = next(row for row in sectors if row["sector"] == "IT")
    assert it["sector_exposure"] == pytest.approx(10000)
    assert it["sector_return_contribution"] == pytest.approx(1500)
    assert it["concentration_percentage"] == pytest.approx(1.0)


def test_strategy_attribution_uses_top5_and_top10():
    attribution = load_attribution()
    metrics = {
        "variants": {
            "top5_weekly": {"metrics": {"total_return": 0.2, "max_drawdown": -0.1, "turnover": 2, "closed_trades": 10}},
            "top10_weekly": {"metrics": {"total_return": 0.1, "max_drawdown": -0.2, "turnover": 3, "closed_trades": 20}},
        }
    }

    rows = attribution.strategy_attribution(metrics)

    assert [row["strategy"] for row in rows] == ["top5_weekly", "top10_weekly"]
    assert rows[0]["return_contribution"] == 0.2
    assert rows[1]["drawdown_contribution"] == -0.2


def test_build_report_preserves_constraints():
    attribution = load_attribution()
    report = attribution.build_report(seed_engine(), 1, date(2026, 6, 12), {"variants": {}})

    assert report["constraints"]["scoring_changed"] is False
    assert report["summary"]["positions"] == 3
