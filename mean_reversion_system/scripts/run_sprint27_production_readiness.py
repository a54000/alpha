"""Sprint 2.7 production assumption validation and paper-readiness artifacts."""

from __future__ import annotations

import json
import math
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "sprint_2_7"
STATIC_LOG = ROOT / "results" / "sprint_2_3" / "static_15_80_05" / "daily_portfolio_log.csv"
INITIAL_CAPITAL = 1_000_000.0


def _max_drawdown(equity: pd.Series) -> float:
    return float((equity / equity.cummax() - 1).min())


def _simulate_idle_yield(rate: float) -> dict[str, float]:
    log = pd.read_csv(STATIC_LOG)
    log["date"] = pd.to_datetime(log["date"])
    daily_rate = (1 + rate) ** (1 / 252) - 1
    accrued = 0.0
    values = []
    for _, row in log.iterrows():
        idle_notional = max(float(row["total_equity"]) * (1 - float(row["total_deployed_pct"])), 0.0)
        accrued += idle_notional * daily_rate
        values.append(accrued)
    log["idle_yield_value"] = values
    log["total_equity_with_yield"] = log["total_equity"] + log["idle_yield_value"]
    equity = log["total_equity_with_yield"]
    years = max((log["date"].max() - log["date"].min()).days / 365.25, 1 / 365.25)
    returns = equity.pct_change().dropna()
    return {
        "backtest_cagr_at_rate": float((equity.iloc[-1] / INITIAL_CAPITAL) ** (1 / years) - 1),
        "total_return_at_rate": float(equity.iloc[-1] / INITIAL_CAPITAL - 1),
        "max_drawdown_at_rate": _max_drawdown(equity),
        "sharpe_at_rate": float(((returns.mean() - 0.065 / 252) / returns.std()) * math.sqrt(252)) if len(returns) > 1 and returns.std() else 0.0,
        "idle_yield_rupees": float(log["idle_yield_value"].iloc[-1]),
    }


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    production = _simulate_idle_yield(0.0481)
    research = _simulate_idle_yield(0.065)
    tax_payload = {
        "instrument": "Liquid Mutual Fund",
        "examples": ["Nippon Liquid Fund", "HDFC Liquid Fund", "Axis Liquid Fund"],
        "gross_yield": 0.070,
        "expense_ratio": 0.0015,
        "net_pre_tax_yield": 0.0685,
        "tax_rate": 0.312,
        "net_post_tax_yield": 0.0481,
        **production,
        "production_cagr_est": production["backtest_cagr_at_rate"],
        "research_case_cagr_6_5pct": research["backtest_cagr_at_rate"],
        "vs_research_case": production["backtest_cagr_at_rate"] - research["backtest_cagr_at_rate"],
    }
    _write_json(OUT / "tax_adjusted_yield.json", tax_payload)

    broker_payload = {
        "entry_mechanics": {
            "signal_time": "After market close on T",
            "recommended_order_time": "16:00 IST on signal day T using AMO",
            "order_type": "Limit at previous close plus 0.1% buffer for buys; avoid pure market on thin names",
            "risk": "09:15 open fills may be worse than daily backtest assumption on wide-spread names",
            "unvalidated_live_data_needed": "09:15 bid-ask spread history by symbol",
        },
        "exit_mechanics": {
            "recommended": "Scheduled job at 15:14 IST for market/limitable exit; fallback manual checklist",
            "alternative": "Exit at 15:30 close for operational simplicity; requires separate slippage validation",
            "gtt_limitation": "GTT is price-triggered, not a time-based exit scheduler",
        },
        "position_ledger_schema": {
            "trade_id": "uuid",
            "sleeve": "V4B | VCP",
            "symbol": "str",
            "entry_date": "date",
            "entry_price": "float",
            "shares": "int",
            "planned_exit_date": "date",
            "stop_loss": "float | null",
            "status": "OPEN | CLOSED | STOPPED",
            "exit_price": "float | null",
            "pnl": "float | null",
        },
    }
    _write_json(OUT / "broker_mechanics_validation.json", broker_payload)

    ledger_columns = [
        "trade_id",
        "sleeve",
        "symbol",
        "entry_date",
        "entry_price",
        "shares",
        "planned_exit_date",
        "stop_loss",
        "status",
        "exit_price",
        "pnl",
    ]
    pd.DataFrame(columns=ledger_columns).to_csv(OUT / "position_ledger_schema.csv", index=False)

    checklist = [
        {"time": "08:30", "task": "Review previous evening signals and required cash."},
        {"time": "08:35", "task": "Redeem liquid fund units if expected orders need cash."},
        {"time": "09:00", "task": "Verify AMO/order book and margin availability."},
        {"time": "09:15", "task": "Confirm entry fills and update position ledger."},
        {"time": "15:14", "task": "Run scheduled exits and stop/time-exit checks."},
        {"time": "15:45", "task": "Calculate idle capital and submit liquid fund sweep."},
        {"time": "16:00", "task": "Run scanners, generate next-day orders, archive logs."},
    ]
    pd.DataFrame(checklist).to_csv(OUT / "paper_trading_daily_checklist.csv", index=False)

    risk_controls = {
        "portfolio": {
            "max_drawdown_alert": 0.05,
            "max_drawdown_halt": 0.08,
            "daily_loss_alert": 0.015,
            "daily_loss_halt": 0.025,
        },
        "sleeves": {
            "V4B": {"allocation": 0.15, "halt_after_consecutive_losses": 5},
            "VCP": {"allocation": 0.80, "market_gate": "constructive market + NIFTY 60D return > 0"},
            "IDLE_YIELD": {"allocation": "undeployed capital", "min_liquidity_buffer": 5000},
        },
        "manual_overrides": ["Broker outage", "Data outage", "Corporate action mismatch", "Liquidity/spread abnormality"],
    }
    _write_json(OUT / "risk_controls.json", risk_controls)

    verdict = [
        "SPRINT 2.7 - PRODUCTION ASSUMPTION VALIDATION",
        "Disha | Pre-Live Checklist",
        "",
        f"Production net idle-yield CAGR estimate: {production['backtest_cagr_at_rate']:.2%}",
        f"Production max DD estimate: {production['max_drawdown_at_rate']:.2%}",
        f"Production Sharpe estimate: {production['sharpe_at_rate']:.2f}",
        "",
        "READINESS VERDICT:",
        "  PAPER-TRADING READY WITH CAVEATS",
        "",
        "CAVEATS:",
        "  09:15 bid-ask spread validation requires live/order-book data.",
        "  Liquid fund API/NAV source must be selected before automation.",
        "  Redemption/sweep mechanics should be paper-tested for at least 20 sessions.",
    ]
    (OUT / "SPRINT_2_7_READINESS_VERDICT.txt").write_text("\n".join(verdict), encoding="utf-8")
    print("\n".join(verdict))


if __name__ == "__main__":
    main()

