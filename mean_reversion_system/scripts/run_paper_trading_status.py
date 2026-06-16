"""Summarise Disha paper-trading readiness and progress."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PAPER = ROOT / "results" / "sprint_2_8"


def _count_rows(path: Path) -> int:
    if not path.exists():
        return 0
    frame = pd.read_csv(path)
    return int(len(frame))


def main() -> None:
    required = [
        "PAPER_TRADING_PLAN.md",
        "LOCKED_RULES.yaml",
        "DAY_0_CHECKLIST.md",
        "paper_trade_log.csv",
        "position_ledger.csv",
        "mf_sweep_log.csv",
        "fill_quality_log.csv",
        "scanner_reconciliation_log.csv",
    ]
    missing = [name for name in required if not (PAPER / name).exists()]
    status = {
        "paper_folder": str(PAPER),
        "ready": not missing,
        "missing_files": missing,
        "sessions_logged": _count_rows(PAPER / "paper_trade_log.csv"),
        "scanner_reconciliations": _count_rows(PAPER / "scanner_reconciliation_log.csv"),
        "mf_sweep_events": _count_rows(PAPER / "mf_sweep_log.csv"),
        "fill_checks": _count_rows(PAPER / "fill_quality_log.csv"),
        "open_positions_logged": _count_rows(PAPER / "position_ledger.csv"),
    }
    (PAPER / "paper_trading_status.json").write_text(json.dumps(status, indent=2), encoding="utf-8")
    print(json.dumps(status, indent=2))


if __name__ == "__main__":
    main()

