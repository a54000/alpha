"""Ingestion reporting helpers."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import json


@dataclass(frozen=True)
class IngestionReport:
    symbols_loaded: int
    rows_loaded: int
    failures: list[str]
    missing_data_summary: dict[str, int]


def write_report(report: IngestionReport, output_path: str | Path) -> Path:
    path = Path(output_path)
    path.write_text(json.dumps(asdict(report), indent=2, sort_keys=True), encoding="utf-8")
    return path
