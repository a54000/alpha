from __future__ import annotations

import importlib.util
import sys
from datetime import date
from pathlib import Path

from sqlalchemy import create_engine, text


REPO_ROOT = Path(__file__).resolve().parents[1]


def load_capture_script():
    name = "capture_recommendation_decision_journal"
    spec = importlib.util.spec_from_file_location(name, REPO_ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_journal_upsert_is_idempotent_and_preserves_feature_snapshot():
    capture = load_capture_script()
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    capture.ensure_journal_table(engine)
    snapshot = {
        "business_date": date(2026, 6, 12),
        "symbol": "ABC",
        "rank": 1,
        "score": 90,
        "recommendation_type": "swing_v2_1",
        "sector": "IT",
        "feature_snapshot_json": {
            "sector_rank_3m": 1,
            "adx_14": 25,
            "ema_200": 100,
            "ema200_extension": 0.1,
            "prior_20d_return": 0.05,
            "final_score": 90,
        },
    }

    capture.upsert_snapshots(engine, [snapshot])
    capture.upsert_snapshots(engine, [{**snapshot, "rank": 2, "score": 91}])

    with engine.connect() as connection:
        rows = connection.execute(
            text("SELECT symbol, rank, score, feature_snapshot_json FROM recommendation_decision_journal")
        ).mappings().all()

    assert len(rows) == 1
    assert rows[0]["symbol"] == "ABC"
    assert rows[0]["rank"] == 2
    assert "sector_rank_3m" in rows[0]["feature_snapshot_json"]
    assert "final_score" in rows[0]["feature_snapshot_json"]
