from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from db.base import Base
from db.models import PaperPortfolio


REPO_ROOT = Path(__file__).resolve().parents[1]


def load_script():
    name = "initialize_paper_portfolio"
    spec = importlib.util.spec_from_file_location(name, REPO_ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_find_existing_prefers_configured_id_and_prevents_duplicate():
    script = load_script()
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, future=True)

    with factory() as session:
        session.add(
            PaperPortfolio(
                portfolio_id=1,
                name="Swing V2.1 Rolling 10 Slot Paper",
                strategy="swing_v2_1_rolling_10_slot",
                portfolio_size=10,
                initial_capital=1_000_000,
                cash=1_000_000,
                current_nav=1_000_000,
                benchmark_symbol="NIFTY500",
                status="active",
            )
        )
        session.commit()

    with factory() as session:
        portfolio, reason = script.find_existing(
            session,
            1,
            "Swing V2.1 Rolling 10 Slot Paper",
            "swing_v2_1_rolling_10_slot",
        )

    assert portfolio is not None
    assert portfolio.portfolio_id == 1
    assert reason == "configured_id"
