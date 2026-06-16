"""Build market regime labels and V4b idle-capital overlap diagnostics."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from mean_reversion_system.scripts.run_backtest import _load_all_daily
from mean_reversion_system.src.data.fetcher import fetch_active_universe
from mean_reversion_system.src.market.regime import detect_market_regime


def _parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def _build_equal_weight_proxy(daily: dict[str, pd.DataFrame]) -> pd.DataFrame:
    closes = []
    highs = []
    lows = []
    opens = []
    volumes = []
    for symbol, frame in daily.items():
        item = frame.copy()
        if item.empty:
            continue
        base = pd.to_numeric(item["close"], errors="coerce").dropna()
        if base.empty:
            continue
        first = float(base.iloc[0])
        if first <= 0:
            continue
        opens.append(pd.to_numeric(item["open"], errors="coerce") / first * 100)
        highs.append(pd.to_numeric(item["high"], errors="coerce") / first * 100)
        lows.append(pd.to_numeric(item["low"], errors="coerce") / first * 100)
        closes.append(pd.to_numeric(item["close"], errors="coerce") / first * 100)
        volumes.append(pd.to_numeric(item["volume"], errors="coerce"))
    proxy = pd.DataFrame(
        {
            "open": pd.concat(opens, axis=1).mean(axis=1),
            "high": pd.concat(highs, axis=1).mean(axis=1),
            "low": pd.concat(lows, axis=1).mean(axis=1),
            "close": pd.concat(closes, axis=1).mean(axis=1),
            "volume": pd.concat(volumes, axis=1).sum(axis=1),
        }
    ).dropna(subset=["open", "high", "low", "close"])
    proxy.index = pd.to_datetime(proxy.index).date
    return proxy


def _known_period_accuracy(regimes: pd.Series) -> list[dict[str, object]]:
    checks = [
        ("2021 bull run", date(2021, 6, 14), date(2021, 12, 31), "uptrend"),
        ("2022 bear phase", date(2022, 1, 1), date(2022, 6, 30), "downtrend"),
        ("2023 H1 range", date(2023, 1, 1), date(2023, 6, 30), "ranging"),
        ("2023 H2-2024 uptrend", date(2023, 7, 1), date(2024, 12, 31), "uptrend"),
    ]
    rows = []
    for label, start, end, expected in checks:
        subset = regimes.loc[(regimes.index >= start) & (regimes.index <= end)]
        rows.append(
            {
                "period": label,
                "expected": expected,
                "days": int(len(subset)),
                "accuracy": float((subset == expected).mean()) if len(subset) else 0.0,
                "dominant": str(subset.value_counts().idxmax()) if len(subset) else "none",
            }
        )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", default="2020-01-01")
    parser.add_argument("--end", default="2025-01-01")
    args = parser.parse_args()
    start = _parse_date(args.start)
    end = _parse_date(args.end)
    out_dir = ROOT / "reports" / "regime"
    out_dir.mkdir(parents=True, exist_ok=True)

    symbols = fetch_active_universe()
    raw = _load_all_daily(symbols, date(max(2020, start.year - 1), 1, 1), end)
    proxy = _build_equal_weight_proxy(raw)
    proxy = proxy.loc[(pd.Series(proxy.index, index=proxy.index) >= start) & (pd.Series(proxy.index, index=proxy.index) <= end)]
    regimes = detect_market_regime(proxy)
    labels = pd.DataFrame({"date": regimes.index, "regime": regimes.values})
    labels.to_csv(out_dir / "market_regime_labels.csv", index=False)

    deployment_path = ROOT / "reports" / "backtests" / "v4b_capital_productivity" / "daily_deployment.csv"
    deployment = pd.read_csv(deployment_path)
    deployment["date"] = pd.to_datetime(deployment["date"]).dt.date
    merged = deployment.merge(labels, on="date", how="left")
    merged["idle"] = merged["open_positions"] == 0
    overlap = (
        merged.groupby("regime", dropna=False)
        .agg(days=("date", "count"), idle_days=("idle", "sum"), avg_deployment=("deployment_pct", "mean"))
        .reset_index()
    )
    overlap["idle_pct"] = overlap["idle_days"] / overlap["days"]
    overlap.to_csv(out_dir / "v4b_idle_overlap_by_regime.csv", index=False)
    regime_dist = labels["regime"].value_counts(normalize=True).to_dict()
    accuracy = _known_period_accuracy(regimes)
    summary = {
        "source": "equal_weight_active_universe_proxy",
        "date_range": {"start": start.isoformat(), "end": end.isoformat()},
        "regime_distribution": regime_dist,
        "known_period_accuracy": accuracy,
        "overall_known_accuracy": sum(row["accuracy"] for row in accuracy) / len(accuracy),
        "idle_overlap_by_regime": overlap.to_dict("records"),
        "vcp_recommendation_basis": "uptrend idle overlap" if "uptrend" in regime_dist else "insufficient uptrend labels",
    }
    (out_dir / "sprint21_regime_summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    print(json.dumps(summary, indent=2, default=str))


if __name__ == "__main__":
    main()
