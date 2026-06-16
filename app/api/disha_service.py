"""Read-only facade over the Disha research and paper-trading artifacts."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from mean_reversion_system.src.live.executor import PaperPortfolio


class DishaReadServiceError(RuntimeError):
    """Raised when a Disha artifact cannot be read."""


class DishaReadService:
    """Read Disha state from the existing research system without rewriting it."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = root or Path(__file__).resolve().parents[2] / "mean_reversion_system"
        self.results = self.root / "results"
        self.paper = self.results / "sprint_2_8"

    def health(self) -> dict[str, Any]:
        required = {
            "locked_rules": self.paper / "LOCKED_RULES.yaml",
            "paper_status": self.paper / "paper_trading_status.json",
            "scanner_signals": self.paper / "day0_scanner_dry_run_signals.csv",
            "regime_labels": self.results / "sprint_2_1" / "daily_regime_labels.csv",
            "research_closure": self.results / "RESEARCH_PHASE_COMPLETE.md",
        }
        return {
            "status": "ok" if all(path.exists() for path in required.values()) else "degraded",
            "artifacts": {name: {"exists": path.exists(), "path": str(path)} for name, path in required.items()},
        }

    def readiness(self) -> dict[str, Any]:
        """Return read-only artifact and paper-trading readiness checks."""

        health = self.health()
        artifact_checks = {}
        for name, item in health["artifacts"].items():
            path = Path(str(item["path"]))
            modified_at = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat() if path.exists() else None
            artifact_checks[name] = {
                **item,
                "modified_at": modified_at,
                "status": "ok" if item["exists"] else "missing",
            }
        paper = self.paper_status() if (self.paper / "paper_trading_status.json").exists() else {}
        paper_ready = bool(paper.get("ready"))
        scanner_rows = 0
        signals_path = self.paper / "day0_scanner_dry_run_signals.csv"
        if signals_path.exists():
            scanner_rows = int(len(pd.read_csv(signals_path)))
        status = "ok" if health["status"] == "ok" and paper_ready else "degraded"
        return {
            "status": status,
            "artifact_checks": artifact_checks,
            "paper": {
                "ready": paper_ready,
                "sessions_logged": paper.get("sessions_logged", 0),
                "scanner_reconciliations": paper.get("scanner_reconciliations", 0),
                "mf_sweep_events": paper.get("mf_sweep_events", 0),
                "fill_checks": paper.get("fill_checks", 0),
                "open_positions_logged": paper.get("open_positions_logged", 0),
            },
            "scanner": {
                "latest_rows": scanner_rows,
                "signals_file": str(signals_path),
            },
        }

    def locked_rules(self) -> dict[str, Any]:
        return self._read_yaml(self.paper / "LOCKED_RULES.yaml")

    def backtest_summary(self) -> dict[str, Any]:
        closure_path = self.results / "RESEARCH_PHASE_COMPLETE.md"
        text = self._read_text(closure_path)
        return {
            "source": str(closure_path),
            "portfolio": self._extract_metrics(text, ["CAGR", "Max DD", "Sharpe", "Walk-forward", "Worst window"]),
            "sleeves": {
                "v4b_mean_reversion": self._extract_section_metrics(text, "Sleeve 1 - V4b Mean Reversion"),
                "vcp_breakout": self._extract_section_metrics(text, "Sleeve 2 - VCP Breakout"),
                "idle_yield_proxy": self._extract_section_metrics(text, "Sleeve 3 - Idle Yield Proxy"),
            },
            "key_findings": self._extract_bullets(text, "## Key Findings"),
            "open_caveats": self._extract_numbered(text, "## Open Caveats For Paper Trading"),
        }

    def market_regime(self) -> dict[str, Any]:
        path = self.results / "sprint_2_1" / "daily_regime_labels.csv"
        frame = self._read_csv(path)
        if frame.empty:
            raise DishaReadServiceError(f"empty regime label file: {path}")
        latest = frame.iloc[-1].to_dict()
        distribution = frame["regime_label"].value_counts(dropna=False).to_dict() if "regime_label" in frame.columns else {}
        total = max(len(frame), 1)
        return {
            "source": str(path),
            "latest": self._jsonable(latest),
            "distribution": {str(key): {"sessions": int(value), "pct": round(float(value) / total, 4)} for key, value in distribution.items()},
            "total_sessions": int(len(frame)),
        }

    def signals_today(self) -> dict[str, Any]:
        signals_path = self.paper / "day0_scanner_dry_run_signals.csv"
        summary_path = self.paper / "day0_scanner_dry_run_summary.json"
        signals = self._read_csv(signals_path)
        records = [self._jsonable(row) for row in signals.to_dict(orient="records")]
        summary = self._read_json(summary_path) if summary_path.exists() else {}
        return {
            "source": str(signals_path),
            "summary": summary,
            "count": len(records),
            "signals": records,
        }

    def portfolio_summary(self) -> dict[str, Any]:
        portfolio = PaperPortfolio()
        summary = portfolio.get_portfolio_summary()
        return {"source": str(portfolio.db_path), "summary": self._jsonable(summary)}

    def paper_status(self) -> dict[str, Any]:
        status_path = self.paper / "paper_trading_status.json"
        status = self._read_json(status_path)
        status["source"] = str(status_path)
        return status

    def paper_logs(self, limit: int = 50) -> dict[str, Any]:
        logs: dict[str, list[dict[str, Any]]] = {}
        for name in ["paper_trade_log", "mf_sweep_log", "fill_quality_log", "scanner_reconciliation_log", "position_ledger"]:
            path = self.paper / f"{name}.csv"
            if path.exists():
                frame = self._read_csv(path).tail(limit)
                logs[name] = [self._jsonable(row) for row in frame.to_dict(orient="records")]
            else:
                logs[name] = []
        return {"source_folder": str(self.paper), "limit": limit, "logs": logs}

    def _read_text(self, path: Path) -> str:
        if not path.exists():
            raise DishaReadServiceError(f"missing Disha artifact: {path}")
        return path.read_text(encoding="utf-8")

    def _read_json(self, path: Path) -> dict[str, Any]:
        if not path.exists():
            raise DishaReadServiceError(f"missing Disha artifact: {path}")
        return json.loads(path.read_text(encoding="utf-8"))

    def _read_yaml(self, path: Path) -> dict[str, Any]:
        if not path.exists():
            raise DishaReadServiceError(f"missing Disha artifact: {path}")
        try:
            import yaml  # type: ignore

            return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except ImportError:
            return self._read_simple_yaml(path)

    def _read_csv(self, path: Path) -> pd.DataFrame:
        if not path.exists():
            raise DishaReadServiceError(f"missing Disha artifact: {path}")
        return pd.read_csv(path)

    def _read_simple_yaml(self, path: Path) -> dict[str, Any]:
        """Parse the locked rules file when PyYAML is not installed."""

        root: dict[str, Any] = {}
        stack: list[tuple[int, dict[str, Any]]] = [(-1, root)]
        for raw in path.read_text(encoding="utf-8").splitlines():
            if not raw.strip() or raw.lstrip().startswith("#"):
                continue
            indent = len(raw) - len(raw.lstrip(" "))
            key, _, raw_value = raw.strip().partition(":")
            while stack and indent <= stack[-1][0]:
                stack.pop()
            parent = stack[-1][1]
            if raw_value.strip():
                parent[key] = self._parse_scalar(raw_value.strip())
            else:
                child: dict[str, Any] = {}
                parent[key] = child
                stack.append((indent, child))
        return root

    @staticmethod
    def _jsonable(value: Any) -> Any:
        if isinstance(value, dict):
            return {str(key): DishaReadService._jsonable(item) for key, item in value.items()}
        if isinstance(value, list):
            return [DishaReadService._jsonable(item) for item in value]
        if pd.isna(value):
            return None
        if hasattr(value, "item"):
            return value.item()
        return value

    @staticmethod
    def _parse_scalar(value: str) -> Any:
        value = value.strip().strip('"').strip("'")
        if value.lower() in {"true", "false"}:
            return value.lower() == "true"
        try:
            return int(value)
        except ValueError:
            pass
        try:
            return float(value)
        except ValueError:
            return value

    @staticmethod
    def _extract_metrics(text: str, labels: list[str]) -> dict[str, str]:
        metrics: dict[str, str] = {}
        for label in labels:
            match = re.search(rf"- {re.escape(label)}:\s*(.+)", text)
            if match:
                metrics[label.lower().replace(" ", "_").replace("-", "_")] = match.group(1).strip()
        return metrics

    @staticmethod
    def _extract_section_metrics(text: str, heading: str) -> dict[str, str]:
        pattern = rf"### {re.escape(heading)}\n(?P<body>.*?)(?:\n### |\n## |\Z)"
        match = re.search(pattern, text, flags=re.S)
        if not match:
            return {}
        return DishaReadService._extract_metrics(
            match.group("body"),
            ["Allocation", "Signal", "Entry", "Exit", "Deployed CAGR", "Max DD", "Instrument", "Net post-tax yield", "Role"],
        )

    @staticmethod
    def _extract_bullets(text: str, heading: str) -> list[str]:
        body = DishaReadService._section_body(text, heading)
        return [line[2:].strip() for line in body.splitlines() if line.startswith("- ")]

    @staticmethod
    def _extract_numbered(text: str, heading: str) -> list[str]:
        body = DishaReadService._section_body(text, heading)
        return [re.sub(r"^\d+\.\s*", "", line).strip() for line in body.splitlines() if re.match(r"^\d+\.", line)]

    @staticmethod
    def _section_body(text: str, heading: str) -> str:
        pattern = rf"{re.escape(heading)}\n(?P<body>.*?)(?:\n## |\Z)"
        match = re.search(pattern, text, flags=re.S)
        return match.group("body") if match else ""
