"""Run a Day 1 paper-trading session workflow."""

from __future__ import annotations

import json
import argparse
import subprocess
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
PAPER = ROOT / "results" / "sprint_2_8"


def _run_scanner() -> dict[str, object]:
    script = ROOT / "scripts" / "run_paper_scanner_dry_run.py"
    subprocess.run([sys.executable, str(script)], cwd=str(REPO), check=True)
    return json.loads((PAPER / "day0_scanner_dry_run_summary.json").read_text(encoding="utf-8"))


def _append_csv(path: Path, row: dict[str, object]) -> None:
    existing = pd.read_csv(path) if path.exists() else pd.DataFrame()
    updated = pd.concat([existing, pd.DataFrame([row])], ignore_index=True)
    updated.to_csv(path, index=False)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="Append even if the scan date is already logged.")
    args = parser.parse_args()
    PAPER.mkdir(parents=True, exist_ok=True)
    summary = _run_scanner()
    session = 1
    scan_date = str(summary["scan_date"])
    paper_log_path = PAPER / "paper_trade_log.csv"
    paper_log = pd.read_csv(paper_log_path) if paper_log_path.exists() else pd.DataFrame()
    if not args.force and not paper_log.empty and scan_date in paper_log.get("date", pd.Series(dtype=str)).astype(str).tolist():
        print(json.dumps({"status": "skipped_duplicate_scan_date", "scan_date": scan_date, "hint": "Use --force to append anyway."}, indent=2))
        return
    if not paper_log.empty and "session" in paper_log.columns:
        numeric_sessions = pd.to_numeric(paper_log["session"], errors="coerce").dropna()
        session = int(numeric_sessions.max()) + 1 if not numeric_sessions.empty else 1
    signals = pd.read_csv(PAPER / "day0_scanner_dry_run_signals.csv")

    order_rows = []
    for row in signals.itertuples(index=False):
        if bool(row.v4b_entry_signal):
            sleeve = "V4B"
        elif bool(row.vcp_entry_signal):
            sleeve = "VCP"
        else:
            continue
        order_rows.append(
            {
                "session": session,
                "order_date": scan_date,
                "execution_date": "",
                "sleeve": sleeve,
                "action": "BUY",
                "symbol": row.symbol,
                "signal_date": scan_date,
                "expected_fill_reference": "09:15 open T+1",
                "order_type": "PAPER_AMO_LIMIT_0.1_BUFFER",
                "limit_price": "",
                "quantity": "",
                "estimated_notional": "",
                "stop_loss": "",
                "planned_exit_date": "",
                "priority": "",
                "status": "PENDING_PAPER",
                "skip_reason": "",
                "notes": "",
            }
        )
    order_sheet = pd.DataFrame(order_rows)
    if order_sheet.empty:
        order_sheet = pd.read_csv(PAPER / "day1_order_sheet.csv").iloc[0:0]
    order_sheet.to_csv(PAPER / "day1_order_sheet.csv", index=False)

    _append_csv(
        PAPER / "paper_trade_log.csv",
        {
            "session": session,
            "date": scan_date,
            "scanner_run": "Y",
            "v4b_entry_signals": int(summary["v4b_signals"]),
            "v4b_exit_signals": 0,
            "vcp_entry_signals": int(summary["vcp_signals"]),
            "vcp_exit_signals": 0,
            "idle_capital": "",
            "mf_action": "NO_ACTION" if not order_rows else "REVIEW_CASH_NEEDS",
            "mf_invest_amount": "",
            "mf_redeem_amount": "",
            "mf_balance": "",
            "mf_nav_source_confirmed": "Y",
            "redemption_workflow_tested": "N",
            "bid_ask_spread_checked": "N",
            "caveat_notes": "Day 1 automated paper workflow.",
        },
    )

    _append_csv(
        PAPER / "mf_sweep_log.csv",
        {
            "session": session,
            "date": scan_date,
            "time": "15:45",
            "portfolio_equity": "",
            "v4b_deployed_value": "",
            "vcp_deployed_value": "",
            "idle_capital": "",
            "action": "NO_ACTION" if not order_rows else "CALCULATE_REDEMPTION_NEED",
            "amount": "",
            "nav": "",
            "units": "",
            "mf_balance": "",
            "settlement_status": "PAPER",
            "notes": "AMFI NAV source selected; manual NAV entry pending.",
        },
    )

    status_script = ROOT / "scripts" / "run_paper_trading_status.py"
    subprocess.run([sys.executable, str(status_script)], cwd=str(REPO), check=True)
    dashboard_script = ROOT / "scripts" / "build_paper_dashboard_html.py"
    subprocess.run([sys.executable, str(dashboard_script)], cwd=str(REPO), check=True)
    print(json.dumps({"session": session, "scan_date": scan_date, "orders": len(order_rows)}, indent=2))


if __name__ == "__main__":
    main()
