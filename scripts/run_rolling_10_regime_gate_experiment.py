#!/usr/bin/env python3
"""Research-only Rolling 10 market-regime gate experiment."""

from __future__ import annotations

import json
import os
import sys
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import numpy as np
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from scripts.run_rolling_20_cohort_backtest import (  # noqa: E402
    deployment_summary,
    load_prices,
    load_recommendations,
    run_backtest,
)
from scripts.run_phase2e_pilot_portfolio_backtest import (  # noqa: E402
    END_DATE,
    START_DATE,
    PilotBacktestConfig,
    write_csv,
)


def derive_angel_url(research_database_url: str | None, database_name: str) -> str | None:
    if not research_database_url:
        return None
    parts = urlsplit(research_database_url)
    return urlunsplit((parts.scheme, parts.netloc, f"/{database_name}", parts.query, parts.fragment))


def compute_adx(frame: pd.DataFrame, period: int = 14) -> pd.Series:
    high = frame["high"].astype(float)
    low = frame["low"].astype(float)
    close = frame["close"].astype(float)
    prev_close = close.shift(1)
    tr = pd.concat([(high - low), (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
    up_move = high.diff()
    down_move = -low.diff()
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
    atr = tr.ewm(alpha=1 / period, adjust=False).mean()
    plus_di = 100 * pd.Series(plus_dm, index=frame.index).ewm(alpha=1 / period, adjust=False).mean() / atr
    minus_di = 100 * pd.Series(minus_dm, index=frame.index).ewm(alpha=1 / period, adjust=False).mean() / atr
    dx = (100 * (plus_di - minus_di).abs() / (plus_di + minus_di)).replace([np.inf, -np.inf], np.nan)
    return dx.ewm(alpha=1 / period, adjust=False).mean()


def load_nifty50_regime() -> pd.DataFrame:
    import yfinance as yf

    frame = yf.download("^NSEI", start="2021-01-01", end="2026-06-14", progress=False, auto_adjust=False)
    if frame.empty:
        raise RuntimeError("Unable to download ^NSEI from yfinance.")
    if isinstance(frame.columns, pd.MultiIndex):
        frame.columns = [column[0].lower().replace(" ", "_") for column in frame.columns]
    else:
        frame.columns = [str(column).lower().replace(" ", "_") for column in frame.columns]
    frame = frame.reset_index().rename(columns={"Date": "date", "date": "date"})
    frame["date"] = pd.to_datetime(frame["date"]).dt.date
    frame = frame[["date", "open", "high", "low", "close"]].copy()
    frame["nifty_sma50"] = frame["close"].rolling(50).mean()
    frame["nifty_adx14"] = compute_adx(frame)
    return frame


def load_sector_breadth(angel_url: str, schema: str) -> pd.DataFrame:
    engine = create_engine(angel_url, future=True)
    frame = pd.read_sql_query(
        text(
            f"""
            SELECT date, COUNT(*) FILTER (WHERE return_3m > 0) AS positive_sector_count
            FROM {schema}.sector_daily
            WHERE date BETWEEN :start_date AND :end_date
            GROUP BY date
            ORDER BY date
            """
        ),
        engine,
        params={"start_date": START_DATE, "end_date": END_DATE},
    )
    frame["date"] = pd.to_datetime(frame["date"]).dt.date
    frame["positive_sector_count"] = frame["positive_sector_count"].astype(int)
    return frame


def build_regime_table(angel_url: str, schema: str) -> pd.DataFrame:
    nifty = load_nifty50_regime()
    breadth = load_sector_breadth(angel_url, schema)
    regime = nifty.merge(breadth, on="date", how="left")
    regime["positive_sector_count"] = regime["positive_sector_count"].fillna(0).astype(int)
    regime["nifty_adx_gt_20"] = regime["nifty_adx14"] > 20
    regime["nifty_above_sma50"] = regime["close"] > regime["nifty_sma50"]
    regime["breadth_ok"] = regime["positive_sector_count"] >= 2
    regime["regime_on"] = regime["nifty_adx_gt_20"] & regime["nifty_above_sma50"] & regime["breadth_ok"]
    return regime


def filter_recommendations(recommendations: list[dict[str, object]], regime: pd.DataFrame) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    by_date = {row.date: row for row in regime.itertuples(index=False)}
    kept: list[dict[str, object]] = []
    blocked: list[dict[str, object]] = []
    for rec in recommendations:
        row = by_date.get(rec["date"])
        if row is not None and bool(row.regime_on):
            kept.append(rec)
        else:
            blocked.append(rec)
    return kept, blocked


def yearly_rows(equity_curve: list[dict[str, object]]) -> list[dict[str, object]]:
    frame = pd.DataFrame(equity_curve)
    frame["date"] = pd.to_datetime(frame["date"])
    rows = []
    for year, group in frame.groupby(frame["date"].dt.year):
        start = float(group.iloc[0]["equity"])
        end = float(group.iloc[-1]["equity"])
        peak = group["equity"].cummax()
        rows.append(
            {
                "year": int(year),
                "start_date": group.iloc[0]["date"].date().isoformat(),
                "end_date": group.iloc[-1]["date"].date().isoformat(),
                "start_equity": start,
                "end_equity": end,
                "year_return": end / start - 1 if start else None,
                "max_drawdown": float((group["equity"] / peak - 1).min()),
                "avg_cash_pct": float((group["cash"] / group["equity"]).mean()),
                "avg_positions": float(group["position_count"].mean()),
            }
        )
    return rows


def write_markdown(path: Path, output: dict[str, object]) -> None:
    metrics = output["metrics"]
    baseline = output["baseline_metrics"]
    lines = [
        "# Rolling 10 Regime Gate Experiment",
        "",
        "Research-only test. Existing 20-day holds complete normally; the gate blocks new entries only.",
        "",
        "## Gate",
        "",
        "- Nifty 50 ADX14 > 20.",
        "- Nifty 50 close > 50-day SMA.",
        "- At least 2 sectors have positive 3-month sector return.",
        "",
        "## Result",
        "",
        f"- Baseline CAGR: {baseline['cagr']:.2%}",
        f"- Gated CAGR: {metrics['cagr']:.2%}",
        f"- Baseline Sharpe: {baseline['sharpe_ratio']:.2f}",
        f"- Gated Sharpe: {metrics['sharpe_ratio']:.2f}",
        f"- Baseline Max DD: {baseline['max_drawdown']:.2%}",
        f"- Gated Max DD: {metrics['max_drawdown']:.2%}",
        f"- Blocked recommendation rows: {output['regime_summary']['blocked_recommendation_rows']}",
        "",
        "## Year By Year",
        "",
        "| Year | Baseline Return | Gated Return | Baseline DD | Gated DD | Gate-On Weeks | Gate-Off Weeks |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    baseline_years = {row["year"]: row for row in output["baseline_yearly"]}
    gate_years = {row["year"]: row for row in output["yearly"]}
    gate_counts = {int(row["year"]): row for row in output["regime_yearly_counts"]}
    for year in sorted(gate_years):
        base = baseline_years.get(year, {})
        gate = gate_years[year]
        counts = gate_counts.get(year, {})
        lines.append(
            f"| {year} | {base.get('year_return', 0):.2%} | {gate['year_return']:.2%} | "
            f"{base.get('max_drawdown', 0):.2%} | {gate['max_drawdown']:.2%} | "
            f"{counts.get('gate_on_signal_dates', 0)} | {counts.get('gate_off_signal_dates', 0)} |"
        )
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    load_dotenv(REPO_ROOT / ".env")
    angel_url = os.environ.get("ANGEL_DATABASE_URL") or derive_angel_url(os.environ.get("DATABASE_URL"), "angel_data")
    if not angel_url:
        raise RuntimeError("ANGEL_DATABASE_URL is required.")

    schema = "pilot_phase2a"
    recommendations = load_recommendations(angel_url, schema, minimum_score=70.0, weekly_picks=5)
    regime = build_regime_table(angel_url, schema)
    gated_recommendations, blocked = filter_recommendations(recommendations, regime)
    symbols = {str(row["symbol"]) for row in recommendations}
    prices = load_prices(angel_url, schema, symbols)

    config = PilotBacktestConfig("rolling_10_regime_gate", "Rolling 10 + Nifty Regime Gate", portfolio_size=10, holding_period=20)
    result = run_backtest(config, gated_recommendations, prices, weekly_picks=5, max_open_positions=10, holding_period=20)
    deploy = deployment_summary(result["equity_curve"], result["weekly_deployment"], 10)

    baseline = json.loads((REPO_ROOT / "reports/phase5_20_rolling_10_cohort_backtest_post_fix.json").read_text(encoding="utf-8"))
    baseline_metrics = baseline["variants"]["rolling_20_cohort"]["metrics"]
    baseline_yearly = pd.read_csv(REPO_ROOT / "results/fix_validation/post_fix_year_by_year_baseline_vs_stop10.csv")
    baseline_yearly = baseline_yearly[baseline_yearly["variant"] == "rolling_10_post_fix"].to_dict("records")

    signal_dates = sorted({row["date"] for row in recommendations})
    regime_by_date = {row.date: bool(row.regime_on) for row in regime.itertuples(index=False)}
    counts = []
    for year in sorted({item.year for item in signal_dates}):
        year_dates = [item for item in signal_dates if item.year == year]
        counts.append(
            {
                "year": year,
                "gate_on_signal_dates": sum(1 for item in year_dates if regime_by_date.get(item, False)),
                "gate_off_signal_dates": sum(1 for item in year_dates if not regime_by_date.get(item, False)),
                "total_signal_dates": len(year_dates),
            }
        )

    output = {
        "generated_on": date.today().isoformat(),
        "experiment": "rolling_10_nifty50_adx_sma50_sector_breadth_gate",
        "constraints": {
            "strategy_logic_changed": False,
            "signal_generation_changed": False,
            "position_sizing_changed": False,
            "entry_fill_changed": False,
            "exit_fill_changed": False,
            "research_only": True,
        },
        "gate": {
            "nifty50_adx14_min": 20,
            "nifty50_above_sma50": True,
            "positive_3m_sector_count_min": 2,
            "entry_behavior": "block new entries on regime-off signal dates; existing positions remain until planned exit",
        },
        "regime_summary": {
            "input_recommendation_rows": len(recommendations),
            "kept_recommendation_rows": len(gated_recommendations),
            "blocked_recommendation_rows": len(blocked),
            "gate_on_signal_dates": sum(1 for item in signal_dates if regime_by_date.get(item, False)),
            "gate_off_signal_dates": sum(1 for item in signal_dates if not regime_by_date.get(item, False)),
        },
        "baseline_metrics": baseline_metrics,
        "metrics": result["metrics"],
        "deployment_summary": deploy,
        "baseline_yearly": baseline_yearly,
        "yearly": yearly_rows(result["equity_curve"]),
        "regime_yearly_counts": counts,
    }

    reports = REPO_ROOT / "reports"
    docs = REPO_ROOT / "docs"
    write_csv(reports / "phase5_25_rolling_10_regime_gate_equity_curve.csv", result["equity_curve"])
    write_csv(reports / "phase5_25_rolling_10_regime_gate_trade_ledger.csv", result["closed_trades"])
    write_csv(reports / "phase5_25_rolling_10_regime_gate_weekly_deployment.csv", result["weekly_deployment"])
    regime.to_csv(reports / "phase5_25_nifty50_regime_gate_daily.csv", index=False)
    Path(reports / "phase5_25_rolling_10_regime_gate.json").write_text(json.dumps(output, indent=2, default=str), encoding="utf-8")
    pd.DataFrame(output["yearly"]).to_csv(REPO_ROOT / "results/fix_validation/rolling_10_regime_gate_year_by_year.csv", index=False)
    write_markdown(docs / "PHASE5_25_ROLLING_10_REGIME_GATE_EXPERIMENT.md", output)
    print(json.dumps({"metrics": result["metrics"], "regime_summary": output["regime_summary"]}, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
