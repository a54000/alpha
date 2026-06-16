"""Calibrate strict explainable VCP thresholds for signal surface."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from mean_reversion_system.scripts.run_paper_scanner_dry_run import _load_daily_bars
from mean_reversion_system.src.strategy.vcp_signals import add_vcp_features, score_vcp_setup

OUT = ROOT / "results" / "sprint_2_8"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    daily = _load_daily_bars()
    rows = []
    for symbol, group in daily.groupby("symbol", sort=False):
        base = group.sort_values("date").reset_index(drop=True)
        if len(base) < 260:
            continue
        item = add_vcp_features(base)
        for pos in range(260, len(item)):
            try:
                score = score_vcp_setup(item.iloc[: pos + 1])
            except (ValueError, OverflowError):
                continue
            latest = item.iloc[pos]
            close_location = (float(latest["close"]) - float(latest["low"])) / max(float(latest["high"]) - float(latest["low"]), 1e-9)
            rows.append(
                {
                    "date": latest["date"],
                    "symbol": symbol,
                    "final_vcp_score": score.final_vcp_score,
                    "is_breakout": score.is_vcp_breakout,
                    "trend_score": score.trend_score,
                    "high_position_score": score.high_position_score,
                    "contraction_score": score.contraction_score,
                    "volatility_score": score.volatility_score,
                    "volume_dryup_score": score.volume_dryup_score,
                    "breakout_score": score.breakout_score,
                    "distance_to_pivot_percent": score.distance_to_pivot_percent,
                    "breakout_volume_ratio": score.breakout_volume_ratio,
                    "close_location": close_location,
                }
            )
    scores = pd.DataFrame(rows)
    scores.to_csv(OUT / "vcp_strict_score_history.csv", index=False)
    summary_rows = []
    for threshold in [50, 60, 67, 75, 83, 100]:
        subset = scores.loc[scores["final_vcp_score"] >= threshold]
        summary_rows.append(
            {
                "score_threshold": threshold,
                "symbol_day_count": int(len(subset)),
                "unique_symbols": int(subset["symbol"].nunique()) if not subset.empty else 0,
                "sessions": int(subset["date"].nunique()) if not subset.empty else 0,
                "avg_candidates_per_session": float(subset.groupby("date")["symbol"].count().mean()) if not subset.empty else 0.0,
                "breakout_count": int(subset["is_breakout"].sum()) if not subset.empty else 0,
            }
        )
    summary = pd.DataFrame(summary_rows)
    summary.to_csv(OUT / "vcp_strict_calibration_summary.csv", index=False)
    payload = {
        "symbols_scanned": int(daily["symbol"].nunique()),
        "score_rows": int(len(scores)),
        "output_scores": str(OUT / "vcp_strict_score_history.csv"),
        "output_summary": str(OUT / "vcp_strict_calibration_summary.csv"),
    }
    (OUT / "vcp_strict_calibration_summary.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
