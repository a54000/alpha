from __future__ import annotations

import importlib.util
import sys
from datetime import date
from pathlib import Path

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[1]


def load_script(name: str):
    spec = importlib.util.spec_from_file_location(name, REPO_ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_phase2d_recommendations_require_price_above_ema200():
    recs = load_script("run_phase2d_pilot_recommendations")
    scores = pd.DataFrame(
        [
            {
                "symbol": "BELOW",
                "date": date(2026, 6, 12),
                "sector": "TEST",
                "swing_v2_1_score": 99.0,
                "adx_points": 30,
                "sector_points": 30,
                "ema200_extension": -0.01,
                "prior_20d_return": 0.01,
                "sector_rank_3m": 1,
                "production_eligible": True,
                "strict_warmup_eligible": True,
            },
            {
                "symbol": "ABOVE",
                "date": date(2026, 6, 12),
                "sector": "TEST",
                "swing_v2_1_score": 80.0,
                "adx_points": 20,
                "sector_points": 30,
                "ema200_extension": 0.01,
                "prior_20d_return": 0.01,
                "sector_rank_3m": 2,
                "production_eligible": True,
                "strict_warmup_eligible": True,
            },
        ]
    )

    recommendations = recs.generate_recommendations(scores)

    assert recommendations["symbol"].tolist() == ["ABOVE"]
    assert int(recommendations.iloc[0]["rank"]) == 1


def test_phase2d_recommendation_eligibility_rejects_zero_extension():
    recs = load_script("run_phase2d_pilot_recommendations")
    row = pd.Series({"swing_v2_1_score": 90.0, "ema200_extension": 0.0})

    assert recs.recommendation_eligible(row) is False
