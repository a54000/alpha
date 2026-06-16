"""Calibrate breakout confirmation on top of strict VCP candidate scoring."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "sprint_2_8"
SCORES = OUT / "vcp_strict_score_history.csv"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    scores = pd.read_csv(SCORES)
    rows = []
    for candidate_threshold in [50, 67, 75, 83]:
        candidates = scores.loc[scores["final_vcp_score"] >= candidate_threshold].copy()
        for volume_threshold in [1.0, 1.2, 1.5]:
            for close_location_threshold in [0.50, 0.60, 0.70]:
                relaxed = candidates.loc[
                    (candidates["breakout_volume_ratio"] >= volume_threshold)
                    & (candidates["close_location"] >= close_location_threshold)
                    & (candidates["distance_to_pivot_percent"] <= 0)
                ]
                rows.append(
                    {
                        "candidate_score_threshold": candidate_threshold,
                        "volume_ratio_threshold": volume_threshold,
                        "close_location_threshold": close_location_threshold,
                        "candidate_count": int(len(candidates)),
                        "volume_confirmed_count": int(len(relaxed)),
                        "unique_symbols": int(relaxed["symbol"].nunique()) if not relaxed.empty else 0,
                        "sessions": int(relaxed["date"].nunique()) if not relaxed.empty else 0,
                        "avg_signals_per_session": float(relaxed.groupby("date")["symbol"].count().mean()) if not relaxed.empty else 0.0,
                        "needs_close_location_instrumentation": False,
                    }
                )
    result = pd.DataFrame(rows)
    result.to_csv(OUT / "vcp_breakout_confirmation_calibration.csv", index=False)
    best = result.sort_values(["volume_confirmed_count", "candidate_score_threshold"], ascending=[False, False]).head(10)
    payload = {
        "input": str(SCORES),
        "output": str(OUT / "vcp_breakout_confirmation_calibration.csv"),
        "best_by_signal_surface": best.to_dict("records"),
        "note": "Relaxed breakout requires close > pivot, volume ratio threshold, and close-location threshold.",
    }
    (OUT / "vcp_breakout_confirmation_calibration.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(best.to_string(index=False))


if __name__ == "__main__":
    main()
