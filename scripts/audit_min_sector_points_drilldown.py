#!/usr/bin/env python3
"""Drilldown for min-sector-points bisection.

Read-only diagnostic over artifacts from audit_min_sector_points_bisection.py.
Focuses on:

- Sector concentration of recommendations removed by the sector guard.
- Trade-level false positives / false negatives caused by the guard.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[1]
INPUT_DIR = REPO_ROOT / "reports" / "min_sector_points_bisection"
OUTPUT_DIR = REPO_ROOT / "reports" / "min_sector_points_drilldown"


def pct(value: float | None) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    return f"{value * 100:.2f}%"


def money(value: float | None) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    return f"Rs {value:,.0f}"


def load_csv(path: Path) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size == 0:
        return pd.DataFrame()
    return pd.read_csv(path)


def summarize_trades(frame: pd.DataFrame) -> dict[str, object]:
    if frame.empty:
        return {
            "trades": 0,
            "winners": 0,
            "losers": 0,
            "win_rate": None,
            "net_pnl": 0.0,
            "winner_pnl": 0.0,
            "loser_pnl": 0.0,
        }
    winners = frame[frame["net_pnl"] > 0]
    losers = frame[frame["net_pnl"] <= 0]
    return {
        "trades": int(len(frame)),
        "winners": int(len(winners)),
        "losers": int(len(losers)),
        "win_rate": len(winners) / len(frame) if len(frame) else None,
        "net_pnl": float(frame["net_pnl"].sum()),
        "winner_pnl": float(winners["net_pnl"].sum()) if not winners.empty else 0.0,
        "loser_pnl": float(losers["net_pnl"].sum()) if not losers.empty else 0.0,
        "largest_winner": winners.sort_values("net_pnl", ascending=False).head(1).to_dict(orient="records")[0] if not winners.empty else None,
        "largest_loser": losers.sort_values("net_pnl").head(1).to_dict(orient="records")[0] if not losers.empty else None,
    }


def sector_breakdown(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame()
    grouped = frame.groupby("sector", dropna=False).agg(
        removed_recommendations=("symbol", "size"),
        unique_symbols=("symbol", "nunique"),
        avg_score=("score", "mean"),
        avg_sector_rank_used=("sector_rank_used", "mean"),
    )
    grouped = grouped.reset_index().sort_values("removed_recommendations", ascending=False)
    total = grouped["removed_recommendations"].sum()
    grouped["share_of_removed"] = grouped["removed_recommendations"] / total if total else 0
    return grouped


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    payload: dict[str, object] = {"periods": {}}
    summary_rows = []

    for period in ["FY2024-25", "FY2025-26"]:
        removed_recs = load_csv(INPUT_DIR / f"{period}_recommendations_removed_by_sector_guard.csv")
        removed_trades = load_csv(INPUT_DIR / f"{period}_trades_removed_by_sector_guard.csv")
        added_trades = load_csv(INPUT_DIR / f"{period}_trades_added_after_sector_guard_path_change.csv")

        sector_rows = sector_breakdown(removed_recs)
        sector_rows.to_csv(OUTPUT_DIR / f"{period}_removed_recommendation_sector_breakdown.csv", index=False)
        removed_trades.to_csv(OUTPUT_DIR / f"{period}_removed_trades.csv", index=False)
        added_trades.to_csv(OUTPUT_DIR / f"{period}_added_trades_after_path_change.csv", index=False)

        removed_summary = summarize_trades(removed_trades)
        added_summary = summarize_trades(added_trades)
        top_sectors = sector_rows.head(10).to_dict(orient="records") if not sector_rows.empty else []
        payload["periods"][period] = {
            "removed_recommendation_count": int(len(removed_recs)),
            "removed_recommendation_sector_count": int(removed_recs["sector"].nunique()) if not removed_recs.empty else 0,
            "top_removed_recommendation_sectors": top_sectors,
            "removed_trade_summary": removed_summary,
            "added_trade_summary": added_summary,
        }
        summary_rows.append(
            {
                "period": period,
                "removed_recommendations": int(len(removed_recs)),
                "removed_recommendation_sectors": int(removed_recs["sector"].nunique()) if not removed_recs.empty else 0,
                "removed_trades": removed_summary["trades"],
                "removed_winners": removed_summary["winners"],
                "removed_losers": removed_summary["losers"],
                "removed_win_rate": removed_summary["win_rate"],
                "removed_net_pnl": removed_summary["net_pnl"],
                "removed_winner_pnl": removed_summary["winner_pnl"],
                "removed_loser_pnl": removed_summary["loser_pnl"],
                "added_trades": added_summary["trades"],
                "added_winners": added_summary["winners"],
                "added_losers": added_summary["losers"],
                "added_win_rate": added_summary["win_rate"],
                "added_net_pnl": added_summary["net_pnl"],
            }
        )

    pd.DataFrame(summary_rows).to_csv(OUTPUT_DIR / "min_sector_points_drilldown_summary.csv", index=False)
    (OUTPUT_DIR / "summary.json").write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

    lines = [
        "# Min Sector Points Drilldown",
        "",
        "This read-only drilldown checks whether `min_sector_points=1` removes genuinely weak trades or merely changes recommendation volume.",
        "",
        "## Trade-Level Impact",
        "",
        "| Period | Removed Trades | Removed Win Rate | Removed Net PnL | Removed Winners PnL | Removed Losers PnL | Added Trades | Added Win Rate | Added Net PnL |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in summary_rows:
        lines.append(
            f"| {row['period']} | {row['removed_trades']} | {pct(row['removed_win_rate'])} | {money(row['removed_net_pnl'])} | "
            f"{money(row['removed_winner_pnl'])} | {money(row['removed_loser_pnl'])} | {row['added_trades']} | "
            f"{pct(row['added_win_rate'])} | {money(row['added_net_pnl'])} |"
        )
    lines.extend(["", "## Removed Recommendation Sector Concentration", ""])
    for period, data in payload["periods"].items():
        lines.extend([f"### {period}", "", "| Sector | Removed Recos | Unique Symbols | Share | Avg Score | Avg Sector Rank |", "| --- | ---: | ---: | ---: | ---: | ---: |"])
        for sector in data["top_removed_recommendation_sectors"][:8]:
            lines.append(
                f"| {sector['sector']} | {sector['removed_recommendations']} | {sector['unique_symbols']} | "
                f"{pct(sector['share_of_removed'])} | {sector['avg_score']:.2f} | {sector['avg_sector_rank_used']:.2f} |"
            )
        lines.append("")
    lines.extend(
        [
            "## Interpretation",
            "",
            "- The recommendation-level filter is large, but the actual trade-level impact is much smaller.",
            "- A low win rate and negative net PnL among removed trades would support the guard as a quality rule.",
            "- Concentration in a few sectors would mean the rule behaves partly like a sector-exclusion rule.",
            "- This is diagnostic only; no strategy logic or database rows were changed.",
        ]
    )
    (OUTPUT_DIR / "MIN_SECTOR_POINTS_DRILLDOWN.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(payload, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
