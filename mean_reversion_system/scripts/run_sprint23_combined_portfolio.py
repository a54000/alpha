"""Sprint 2.3 combined portfolio simulation for V4b + VCP."""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "sprint_2_3"
START = pd.Timestamp("2022-05-10")
END = pd.Timestamp("2025-01-01")
INITIAL_CAPITAL = 1_000_000.0
V4B_ALLOC = 150_000.0
VCP_ALLOC = 600_000.0
CASH_ALLOC = 250_000.0
RISK_FREE_RATE = 0.065


def _max_drawdown(equity: pd.Series) -> tuple[float, int]:
    high_water = equity.cummax()
    drawdown = equity / high_water - 1
    max_duration = 0
    duration = 0
    for value in drawdown:
        if value < 0:
            duration += 1
            max_duration = max(max_duration, duration)
        else:
            duration = 0
    return float(drawdown.min()), int(max_duration)


def _load_curves() -> tuple[pd.DataFrame, pd.DataFrame]:
    v4b = pd.read_csv(ROOT / "reports" / "backtests" / "v4b_capital_productivity" / "daily_deployment.csv")
    vcp = pd.read_csv(ROOT / "results" / "sprint_2_2" / "atr_trail_positive_momentum" / "equity_curve.csv")
    for frame in (v4b, vcp):
        frame["date"] = pd.to_datetime(frame["date"])
    v4b = v4b.loc[(v4b["date"] >= START) & (v4b["date"] <= END)].copy()
    vcp = vcp.loc[(vcp["date"] >= START) & (vcp["date"] <= END)].copy()
    return v4b, vcp


def _allocation_for_variant(variant: str, regime: str) -> tuple[float, float, float]:
    if variant == "base_15_60_25":
        return 150_000.0, 600_000.0, 250_000.0
    if variant == "static_15_80_05":
        return 150_000.0, 800_000.0, 50_000.0
    if variant == "dynamic_regime":
        if regime == "UPTREND":
            return 100_000.0, 800_000.0, 100_000.0
        if regime == "RANGING":
            return 250_000.0, 500_000.0, 250_000.0
        return 100_000.0, 300_000.0, 600_000.0
    raise ValueError(f"unsupported allocation variant: {variant}")


def _build_daily_log(v4b: pd.DataFrame, vcp: pd.DataFrame, variant: str = "base_15_60_25", liquid_yield: bool = False, idle_yield: bool = False) -> pd.DataFrame:
    merged = v4b.merge(vcp, on="date", how="inner", suffixes=("_v4b", "_vcp"))
    labels = pd.read_csv(ROOT / "results" / "sprint_2_1" / "daily_regime_labels.csv")
    labels["date"] = pd.to_datetime(labels["session_date"])
    merged = merged.merge(labels[["date", "regime_label"]], on="date", how="left")
    allocations = merged["regime_label"].fillna("RANGING").apply(lambda regime: _allocation_for_variant(variant, str(regime)))
    merged["v4b_alloc"] = [item[0] for item in allocations]
    merged["vcp_alloc"] = [item[1] for item in allocations]
    merged["cash_alloc"] = [item[2] for item in allocations]
    merged["v4b_equity"] = merged["v4b_alloc"] * pd.to_numeric(merged["equity_v4b"], errors="coerce") / INITIAL_CAPITAL
    merged["vcp_equity"] = merged["vcp_alloc"] * pd.to_numeric(merged["equity_vcp"], errors="coerce") / INITIAL_CAPITAL
    daily_rate = (1 + RISK_FREE_RATE) ** (1 / 252) - 1
    cash_values = []
    cash_value = float(merged["cash_alloc"].iloc[0])
    previous_cash_alloc = cash_value
    for cash_alloc in merged["cash_alloc"]:
        cash_alloc = float(cash_alloc)
        if cash_alloc != previous_cash_alloc:
            cash_value += cash_alloc - previous_cash_alloc
            previous_cash_alloc = cash_alloc
        if liquid_yield:
            cash_value *= 1 + daily_rate
        cash_values.append(cash_value)
    merged["cash_value"] = cash_values
    merged["total_equity"] = merged["v4b_equity"] + merged["vcp_equity"] + merged["cash_value"]
    merged["v4b_daily_pnl"] = merged["v4b_equity"].diff().fillna(0.0)
    merged["vcp_daily_pnl"] = merged["vcp_equity"].diff().fillna(0.0)
    merged["combined_daily_pnl"] = merged["total_equity"].diff().fillna(0.0)
    merged["v4b_positions_open"] = merged["open_positions_v4b"].astype(int)
    merged["vcp_positions_open"] = merged["open_positions_vcp"].astype(int)
    merged["v4b_deployed_value"] = merged["v4b_alloc"] * pd.to_numeric(merged["deployment_pct"], errors="coerce").fillna(0.0)
    merged["vcp_deployed_value"] = merged["vcp_alloc"] * pd.to_numeric(merged["deployed_pct"], errors="coerce").fillna(0.0)
    merged["total_deployed_pct"] = (merged["v4b_deployed_value"] + merged["vcp_deployed_value"]) / merged["total_equity"]
    merged["v4b_deployment_pct_total"] = merged["v4b_deployed_value"] / merged["total_equity"]
    merged["vcp_deployment_pct_total"] = merged["vcp_deployed_value"] / merged["total_equity"]
    merged["both_active"] = (merged["v4b_positions_open"] > 0) & (merged["vcp_positions_open"] > 0)
    merged["only_v4b"] = (merged["v4b_positions_open"] > 0) & (merged["vcp_positions_open"] == 0)
    merged["only_vcp"] = (merged["v4b_positions_open"] == 0) & (merged["vcp_positions_open"] > 0)
    merged["neither_active"] = (merged["v4b_positions_open"] == 0) & (merged["vcp_positions_open"] == 0)
    if idle_yield:
        idle_values = []
        accrued_idle = 0.0
        for _, row in merged.iterrows():
            idle_notional = max(float(row["total_equity"]) - float(row["v4b_deployed_value"]) - float(row["vcp_deployed_value"]), 0.0)
            accrued_idle += idle_notional * daily_rate
            idle_values.append(accrued_idle)
        merged["idle_yield_value"] = idle_values
        merged["total_equity"] = merged["total_equity"] + merged["idle_yield_value"]
        merged["combined_daily_pnl"] = merged["total_equity"].diff().fillna(0.0)
        merged["total_deployed_pct"] = (merged["v4b_deployed_value"] + merged["vcp_deployed_value"]) / merged["total_equity"]
    else:
        merged["idle_yield_value"] = 0.0
    columns = [
        "date",
        "regime_label",
        "v4b_alloc",
        "vcp_alloc",
        "cash_alloc",
        "v4b_equity",
        "vcp_equity",
        "cash_value",
        "idle_yield_value",
        "total_equity",
        "v4b_daily_pnl",
        "vcp_daily_pnl",
        "combined_daily_pnl",
        "v4b_positions_open",
        "vcp_positions_open",
        "total_deployed_pct",
        "v4b_deployment_pct_total",
        "vcp_deployment_pct_total",
        "both_active",
        "only_v4b",
        "only_vcp",
        "neither_active",
    ]
    return merged[columns].copy()


def _conflicts() -> pd.DataFrame:
    v4b_entries = pd.read_csv(ROOT / "reports" / "backtests" / "v4b_capital_productivity" / "entries.csv")
    vcp_trades = pd.read_csv(ROOT / "results" / "sprint_2_2" / "atr_trail_positive_momentum" / "trades.csv")
    v4b_entries["signal_date"] = pd.to_datetime(v4b_entries["signal_date"])
    vcp_trades["signal_date"] = pd.to_datetime(vcp_trades["signal_date"])
    conflicts = vcp_trades.merge(
        v4b_entries[["symbol", "signal_date"]],
        on=["symbol", "signal_date"],
        how="inner",
    )
    conflicts["reason"] = "SYMBOL_CONFLICT_SKIPPED"
    return conflicts.loc[(conflicts["signal_date"] >= START) & (conflicts["signal_date"] <= END)].copy()


def _correlation_report(log: pd.DataFrame) -> pd.DataFrame:
    rows = []
    overall_corr = log["v4b_daily_pnl"].corr(log["vcp_daily_pnl"])
    rows.append(
        {
            "year": "ALL",
            "v4b_pnl": float(log["v4b_daily_pnl"].sum()),
            "vcp_pnl": float(log["vcp_daily_pnl"].sum()),
            "correlation": float(overall_corr) if pd.notna(overall_corr) else 0.0,
            "interpretation": "low diversification correlation" if pd.notna(overall_corr) and overall_corr < 0.3 else "correlation above target",
        }
    )
    log = log.copy()
    log["year"] = log["date"].dt.year
    for year, group in log.groupby("year"):
        corr = group["v4b_daily_pnl"].corr(group["vcp_daily_pnl"])
        rows.append(
            {
                "year": int(year),
                "v4b_pnl": float(group["v4b_daily_pnl"].sum()),
                "vcp_pnl": float(group["vcp_daily_pnl"].sum()),
                "correlation": float(corr) if pd.notna(corr) else 0.0,
                "interpretation": "negative/hedging" if pd.notna(corr) and corr < 0 else ("low" if pd.notna(corr) and corr < 0.3 else "high"),
            }
        )
    return pd.DataFrame(rows)


def _yearly_contribution(log: pd.DataFrame) -> pd.DataFrame:
    rows = []
    work = log.copy()
    work["year"] = work["date"].dt.year
    for year, group in work.groupby("year"):
        start_total = float(group["total_equity"].iloc[0])
        v4b_pnl = float(group["v4b_equity"].iloc[-1] - group["v4b_equity"].iloc[0])
        vcp_pnl = float(group["vcp_equity"].iloc[-1] - group["vcp_equity"].iloc[0])
        combined_pnl = float(group["total_equity"].iloc[-1] - group["total_equity"].iloc[0])
        rows.append(
            {
                "year": int(year),
                "v4b_pnl": v4b_pnl,
                "vcp_pnl": vcp_pnl,
                "cash_pnl": 0.0,
                "combined_pnl": combined_pnl,
                "v4b_return_pct": v4b_pnl / start_total,
                "vcp_return_pct": vcp_pnl / start_total,
                "combined_return_pct": combined_pnl / start_total,
                "dominant_sleeve": "V4b" if abs(v4b_pnl) > abs(vcp_pnl) else "VCP",
            }
        )
    return pd.DataFrame(rows)


def _portfolio_report(log: pd.DataFrame, correlation: pd.DataFrame, conflicts: pd.DataFrame, variant: str = "base_15_60_25", liquid_yield: bool = False, idle_yield: bool = False) -> dict[str, object]:
    equity = log["total_equity"]
    dates = log["date"]
    years = max((dates.max() - dates.min()).days / 365.25, 1 / 365.25)
    returns = equity.pct_change().dropna()
    downside = returns.loc[returns < 0]
    max_dd, dd_duration = _max_drawdown(equity)
    monthly = log.set_index("date")["total_equity"].resample("ME").last().pct_change().dropna()
    yearly = log.set_index("date")["total_equity"].resample("YE").last().pct_change().dropna()
    return {
        "allocation": {
            "variant": variant,
            "liquid_yield": liquid_yield,
            "idle_yield": idle_yield,
            "risk_free_rate": RISK_FREE_RATE if liquid_yield or idle_yield else 0.0,
            "avg_v4b_alloc": float(log["v4b_alloc"].mean()),
            "avg_vcp_alloc": float(log["vcp_alloc"].mean()),
            "avg_cash_alloc": float(log["cash_alloc"].mean()),
        },
        "window": {"start": START.date().isoformat(), "end": END.date().isoformat(), "sessions": int(len(log))},
        "return_metrics": {
            "total_return": float(equity.iloc[-1] / INITIAL_CAPITAL - 1),
            "cagr": float((equity.iloc[-1] / INITIAL_CAPITAL) ** (1 / years) - 1),
            "year_by_year_return": {str(k.year): float(v) for k, v in yearly.items()},
        },
        "risk_metrics": {
            "max_drawdown": max_dd,
            "max_drawdown_duration_days": dd_duration,
            "sharpe_ratio": float(((returns.mean() - 0.065 / 252) / returns.std()) * math.sqrt(252)) if len(returns) > 1 and returns.std() else 0.0,
            "sortino_ratio": float(((returns.mean() - 0.065 / 252) / downside.std()) * math.sqrt(252)) if len(downside) > 1 and downside.std() else 0.0,
            "calmar_ratio": float(((equity.iloc[-1] / INITIAL_CAPITAL) ** (1 / years) - 1) / abs(max_dd)) if max_dd else 0.0,
        },
        "deployment_metrics": {
            "avg_total_deployment": float(log["total_deployed_pct"].mean()),
            "avg_v4b_deployment_total": float(log["v4b_deployment_pct_total"].mean()),
            "avg_vcp_deployment_total": float(log["vcp_deployment_pct_total"].mean()),
            "sessions_both_active": int(log["both_active"].sum()),
            "sessions_both_active_pct": float(log["both_active"].mean()),
            "sessions_only_v4b": int(log["only_v4b"].sum()),
            "sessions_only_v4b_pct": float(log["only_v4b"].mean()),
            "sessions_only_vcp": int(log["only_vcp"].sum()),
            "sessions_only_vcp_pct": float(log["only_vcp"].mean()),
            "sessions_neither": int(log["neither_active"].sum()),
            "sessions_neither_pct": float(log["neither_active"].mean()),
        },
        "diversification_metrics": {
            "v4b_vcp_daily_pnl_correlation": float(correlation.loc[correlation["year"].astype(str) == "ALL", "correlation"].iloc[0]),
            "pct_months_positive": float((monthly > 0).mean()) if len(monthly) else 0.0,
            "worst_single_month": float(monthly.min()) if len(monthly) else 0.0,
            "best_single_month": float(monthly.max()) if len(monthly) else 0.0,
            "symbol_conflicts": int(len(conflicts)),
        },
    }


def _verdict(report: dict[str, object], yearly: pd.DataFrame, correlation: pd.DataFrame, variant: str = "base_15_60_25") -> str:
    returns = report["return_metrics"]
    risk = report["risk_metrics"]
    deploy = report["deployment_metrics"]
    div = report["diversification_metrics"]
    cagr = returns["cagr"]
    max_dd = risk["max_drawdown"]
    corr = div["v4b_vcp_daily_pnl_correlation"]
    avg_deploy = deploy["avg_total_deployment"]
    y2022 = yearly.loc[yearly["year"] == 2022]
    y2022_return = float(y2022["combined_return_pct"].iloc[0]) if not y2022.empty else 0.0
    passes = {
        "combined_cagr_gt_12": cagr > 0.12,
        "max_drawdown_lt_10": abs(max_dd) < 0.10,
        "correlation_lt_0_3": corr < 0.30,
        "combined_2022_gt_minus_3": y2022_return > -0.03,
    }
    lines = [
        "SPRINT 2.3 - COMBINED PORTFOLIO VERDICT",
        "Disha | V4b Mean Reversion + VCP Breakout",
        "",
        "ALLOCATION:",
        f"  Variant: {variant}",
        "",
        "RESULTS:",
        f"  Total return: {returns['total_return']:.2%}",
        f"  CAGR: {cagr:.2%}",
        f"  Max drawdown: {max_dd:.2%}",
        f"  Sharpe: {risk['sharpe_ratio']:.2f}",
        f"  Avg deployment: {avg_deploy:.2%}",
        f"  V4b/VCP daily PnL correlation: {corr:.3f}",
        f"  2022 combined return: {y2022_return:.2%}",
        f"  Symbol conflicts skipped: {div['symbol_conflicts']}",
        "",
        "PRIMARY GATES:",
        f"  Combined CAGR > 12%: {'PASS' if passes['combined_cagr_gt_12'] else 'FAIL'}",
        f"  Max DD < 10%: {'PASS' if passes['max_drawdown_lt_10'] else 'FAIL'}",
        f"  Correlation < 0.3: {'PASS' if passes['correlation_lt_0_3'] else 'FAIL'}",
        f"  2022 combined return > -3%: {'PASS' if passes['combined_2022_gt_minus_3'] else 'FAIL'}",
        "",
        "YEARLY CONTRIBUTION:",
    ]
    for row in yearly.itertuples(index=False):
        lines.append(
            f"  {row.year}: V4b {row.v4b_pnl:.2f}, VCP {row.vcp_pnl:.2f}, combined {row.combined_return_pct:.2%}"
        )
    decision = "PASS: proceed to Sprint 2.4" if all(passes.values()) else "FAIL: combined sleeve architecture improves diversification but does not meet the return gate yet"
    lines += ["", f"DECISION: {decision}"]
    return "\n".join(lines)


def _run_variant(v4b: pd.DataFrame, vcp: pd.DataFrame, conflicts: pd.DataFrame, variant: str, out_dir: Path, liquid_yield: bool = False, idle_yield: bool = False) -> dict[str, object]:
    log = _build_daily_log(v4b, vcp, variant, liquid_yield=liquid_yield, idle_yield=idle_yield)
    correlation = _correlation_report(log)
    yearly = _yearly_contribution(log)
    report = _portfolio_report(log, correlation, conflicts, variant, liquid_yield=liquid_yield, idle_yield=idle_yield)
    out_dir.mkdir(parents=True, exist_ok=True)
    log.to_csv(out_dir / "daily_portfolio_log.csv", index=False)
    log[["date", "total_equity"]].rename(columns={"total_equity": "equity"}).to_csv(out_dir / "combined_equity_curve.csv", index=False)
    correlation.to_csv(out_dir / "correlation_analysis.csv", index=False)
    yearly.to_csv(out_dir / "year_by_year_contribution.csv", index=False)
    (out_dir / "combined_portfolio_report.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    verdict = _verdict(report, yearly, correlation, variant)
    (out_dir / "SPRINT_2_3_VERDICT.txt").write_text(verdict, encoding="utf-8")
    return {
        "variant": variant,
        "liquid_yield": liquid_yield,
        "idle_yield": idle_yield,
        "total_return": report["return_metrics"]["total_return"],
        "cagr": report["return_metrics"]["cagr"],
        "max_drawdown": report["risk_metrics"]["max_drawdown"],
        "sharpe": report["risk_metrics"]["sharpe_ratio"],
        "avg_deployment": report["deployment_metrics"]["avg_total_deployment"],
        "correlation": report["diversification_metrics"]["v4b_vcp_daily_pnl_correlation"],
        "symbol_conflicts": report["diversification_metrics"]["symbol_conflicts"],
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    v4b, vcp = _load_curves()
    conflicts = _conflicts()
    conflicts.to_csv(OUT / "symbol_conflicts.csv", index=False)
    summaries = []
    for variant in ["base_15_60_25", "static_15_80_05", "dynamic_regime"]:
        variant_dir = OUT if variant == "base_15_60_25" else OUT / variant
        summaries.append(_run_variant(v4b, vcp, conflicts, variant, variant_dir))
    for variant in ["base_15_60_25", "static_15_80_05"]:
        summaries.append(_run_variant(v4b, vcp, conflicts, variant, OUT / f"{variant}_liquid_yield", liquid_yield=True))
        summaries.append(_run_variant(v4b, vcp, conflicts, variant, OUT / f"{variant}_idle_yield", idle_yield=True))
    summary = pd.DataFrame(summaries)
    summary.to_csv(OUT / "allocation_variant_summary.csv", index=False)
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
