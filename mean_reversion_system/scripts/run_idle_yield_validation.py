"""Validate practical idle-yield assumptions for the combined portfolio."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, asdict
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "sprint_2_4b"
SOURCE_LOG = ROOT / "results" / "sprint_2_3" / "static_15_80_05" / "daily_portfolio_log.csv"
INITIAL_CAPITAL = 1_000_000.0


@dataclass(frozen=True)
class YieldScenario:
    name: str
    gross_yield: float
    expense_ratio: float
    tax_rate: float
    investable_fraction: float
    liquidity_buffer_note: str


def _max_drawdown(equity: pd.Series) -> float:
    drawdown = equity / equity.cummax() - 1
    return float(drawdown.min())


def _evaluate(log: pd.DataFrame, scenario: YieldScenario) -> dict[str, object]:
    work = log.copy()
    net_yield = max(scenario.gross_yield - scenario.expense_ratio, 0.0) * (1 - scenario.tax_rate)
    daily_rate = (1 + net_yield) ** (1 / 252) - 1
    accrued = 0.0
    idle_values = []
    for _, row in work.iterrows():
        deployed_pct = float(row["total_deployed_pct"])
        idle_notional = max(float(row["total_equity"]) * (1 - deployed_pct), 0.0)
        investable_idle = idle_notional * scenario.investable_fraction
        accrued += investable_idle * daily_rate
        idle_values.append(accrued)
    work["idle_yield_value"] = idle_values
    work["total_equity_with_yield"] = work["total_equity"] + work["idle_yield_value"]
    equity = work["total_equity_with_yield"]
    dates = pd.to_datetime(work["date"])
    years = max((dates.max() - dates.min()).days / 365.25, 1 / 365.25)
    returns = equity.pct_change().dropna()
    return {
        **asdict(scenario),
        "net_yield_after_tax_expense": net_yield,
        "effective_yield_on_idle_after_buffer": net_yield * scenario.investable_fraction,
        "final_equity": float(equity.iloc[-1]),
        "total_return": float(equity.iloc[-1] / INITIAL_CAPITAL - 1),
        "cagr": float((equity.iloc[-1] / INITIAL_CAPITAL) ** (1 / years) - 1),
        "max_drawdown": _max_drawdown(equity),
        "sharpe": float(((returns.mean() - 0.065 / 252) / returns.std()) * math.sqrt(252)) if len(returns) > 1 and returns.std() else 0.0,
        "idle_yield_rupees": float(work["idle_yield_value"].iloc[-1]),
        "passes_12pct_gate": float((equity.iloc[-1] / INITIAL_CAPITAL) ** (1 / years) - 1) > 0.12,
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    log = pd.read_csv(SOURCE_LOG)
    scenarios = [
        YieldScenario("optimistic_research_6_5pct_no_tax", 0.065, 0.0, 0.0, 1.0, "Research upper bound only."),
        YieldScenario("t_bill_91d_taxable_30pct", 0.053, 0.0, 0.312, 1.0, "91D T-bill proxy, taxed at 30% slab plus 4% cess."),
        YieldScenario("liquid_etf_taxed_with_10pct_buffer", 0.053, 0.0028, 0.312, 0.90, "Liquid ETF/fund proxy with expense, slab tax, and 10% haircut/liquidity buffer."),
        YieldScenario("conservative_net_3pct", 0.03, 0.0, 0.0, 0.90, "Conservative post-tax/post-friction yield with 10% liquidity buffer."),
    ]
    rows = [_evaluate(log, scenario) for scenario in scenarios]
    summary = pd.DataFrame(rows)
    summary.to_csv(OUT / "idle_yield_realism_scenarios.csv", index=False)
    verdict_lines = [
        "IDLE YIELD PRACTICAL VALIDATION",
        "Disha | Liquid Collateral / Treasury Sweep Sleeve",
        "",
        "SOURCE PORTFOLIO: static_15_80_05",
        "",
        "SCENARIOS:",
    ]
    for row in rows:
        verdict_lines.append(
            f"  {row['name']}: net idle yield {row['effective_yield_on_idle_after_buffer']:.2%}, "
            f"CAGR {row['cagr']:.2%}, DD {row['max_drawdown']:.2%}, gate {'PASS' if row['passes_12pct_gate'] else 'FAIL'}"
        )
    realistic = rows[2]
    verdict_lines += [
        "",
        "PRACTICAL VERDICT:",
        "  The 6.5% no-tax idle-yield assumption is too optimistic for production.",
        "  A more realistic liquid ETF / T-bill sweep after tax, expense, and buffer does not clear the 12% CAGR gate.",
        f"  Realistic scenario CAGR: {realistic['cagr']:.2%}.",
        "",
        "IMPLEMENTATION REQUIREMENTS:",
        "  Keep a liquidity buffer for settlement and order placement.",
        "  Model tax at the user's applicable slab rate.",
        "  Treat pledged liquid ETFs/funds as cash-equivalent collateral only after haircut.",
        "  Do not assume all idle capital can be instantly redeployed without pledge/redemption frictions.",
    ]
    (OUT / "IDLE_YIELD_VALIDATION_VERDICT.txt").write_text("\n".join(verdict_lines), encoding="utf-8")
    print("\n".join(verdict_lines))


if __name__ == "__main__":
    main()
