"""Research-only VCP pattern scan with market gate ignored."""

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
        latest = item.iloc[-1]
        try:
            score = score_vcp_setup(item)
        except ValueError:
            continue
        if score.final_vcp_score >= 50 or score.is_vcp_breakout:
            rows.append(
                {
                    "date": latest["date"],
                    "symbol": symbol,
                    "final_vcp_score": score.final_vcp_score,
                    "full_vcp_signal": score.is_vcp_breakout,
                    "trend_score": score.trend_score,
                    "high_position_score": score.high_position_score,
                    "contraction_score": score.contraction_score,
                    "volatility_score": score.volatility_score,
                    "volume_dryup_score": score.volume_dryup_score,
                    "breakout_score": score.breakout_score,
                    "contraction_depths": "|".join(f"{depth:.4f}" for depth in score.contraction_depths),
                    "pivot_price": score.pivot_price,
                    "distance_to_pivot_percent": score.distance_to_pivot_percent,
                    "atr_percent": score.atr_percent,
                    "breakout_volume_ratio": score.breakout_volume_ratio,
                    "close": float(latest["close"]),
                }
            )
    result = pd.DataFrame(rows).sort_values(["full_vcp_signal", "final_vcp_score"], ascending=[False, False]) if rows else pd.DataFrame()
    result.to_csv(OUT / "vcp_research_pattern_scan.csv", index=False)
    summary = {
        "symbols_scanned": int(daily["symbol"].nunique()),
        "candidates_score_50_plus": int(len(result)),
        "full_vcp_signals": int(result["full_vcp_signal"].sum()) if not result.empty else 0,
        "output": str(OUT / "vcp_research_pattern_scan.csv"),
    }
    (OUT / "vcp_research_pattern_scan_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    if not result.empty:
        print(result.head(20).to_string(index=False))


if __name__ == "__main__":
    main()
