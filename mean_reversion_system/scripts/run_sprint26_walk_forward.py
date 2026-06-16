"""Sprint 2.6 walk-forward validation for the locked three-sleeve portfolio."""

from __future__ import annotations

import json
import math
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "sprint_2_6"
STATIC_LOG = ROOT / "results" / "sprint_2_3" / "static_15_80_05_idle_yield" / "daily_portfolio_log.csv"
INITIAL_CAPITAL = 1_000_000.0


def _max_drawdown(equity: pd.Series) -> float:
    return float((equity / equity.cummax() - 1).min())


def _metrics(frame: pd.DataFrame, capital_base: float) -> dict[str, float]:
    equity = pd.to_numeric(frame["total_equity"], errors="coerce")
    dates = pd.to_datetime(frame["date"])
    years = max((dates.max() - dates.min()).days / 365.25, 1 / 365.25)
    returns = equity.pct_change().dropna()
    cagr = float((equity.iloc[-1] / capital_base) ** (1 / years) - 1)
    return {
        "sessions": float(len(frame)),
        "total_return": float(equity.iloc[-1] / capital_base - 1),
        "cagr": cagr,
        "max_drawdown": _max_drawdown(equity),
        "sharpe": float(((returns.mean() - 0.065 / 252) / returns.std()) * math.sqrt(252)) if len(returns) > 1 and returns.std() else 0.0,
        "avg_deployment": float(frame["total_deployed_pct"].mean()),
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    if not STATIC_LOG.exists():
        raise FileNotFoundError(STATIC_LOG)
    log = pd.read_csv(STATIC_LOG)
    log["date"] = pd.to_datetime(log["date"])
    log = log.sort_values("date").reset_index(drop=True)
    full = _metrics(log, INITIAL_CAPITAL)
    rows = []
    for year, group in log.groupby(log["date"].dt.year):
        if len(group) < 5:
            continue
        rows.append({"window": str(year), **_metrics(group, float(group["total_equity"].iloc[0]))})
    windows = [
        ("2022_2023", "2022-05-10", "2023-12-31"),
        ("2023_2024", "2023-01-01", "2024-12-31"),
        ("2024_2025", "2024-01-01", "2025-01-01"),
    ]
    for name, start, end in windows:
        group = log.loc[(log["date"] >= pd.Timestamp(start)) & (log["date"] <= pd.Timestamp(end))]
        if len(group) < 5:
            continue
        rows.append({"window": name, **_metrics(group, float(group["total_equity"].iloc[0]))})
    wf = pd.DataFrame(rows)
    wf.to_csv(OUT / "walk_forward_windows.csv", index=False)
    gate = {
        "full_cagr": full["cagr"],
        "full_max_drawdown": full["max_drawdown"],
        "windows_positive": int((wf["total_return"] > 0).sum()),
        "window_count": int(len(wf)),
        "worst_window_return": float(wf["total_return"].min()) if len(wf) else 0.0,
        "worst_window_drawdown": float(wf["max_drawdown"].min()) if len(wf) else 0.0,
        "passed": bool(full["cagr"] > 0.12 and abs(full["max_drawdown"]) < 0.10 and (wf["total_return"] > 0).mean() >= 0.75),
    }
    (OUT / "walk_forward_summary.json").write_text(json.dumps({"full": full, "gate": gate}, indent=2), encoding="utf-8")
    lines = [
        "SPRINT 2.6 - WALK-FORWARD VALIDATION",
        "Disha | Locked Three-Sleeve Portfolio",
        "",
        f"Full CAGR: {full['cagr']:.2%}",
        f"Full max DD: {full['max_drawdown']:.2%}",
        f"Windows positive: {gate['windows_positive']} / {gate['window_count']}",
        f"Worst window return: {gate['worst_window_return']:.2%}",
        f"Worst window DD: {gate['worst_window_drawdown']:.2%}",
        "",
        f"VERDICT: {'PASS' if gate['passed'] else 'FAIL'}",
    ]
    (OUT / "SPRINT_2_6_VERDICT.txt").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()

