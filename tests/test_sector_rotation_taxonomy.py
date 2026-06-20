from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

from app.api.sector_rotation_service import INDUSTRY_TAXONOMY


REPO_ROOT = Path(__file__).resolve().parents[1]
SERVICE_FILE = REPO_ROOT / "app" / "api" / "sector_rotation_service.py"


def _taxonomy_source_block() -> str:
    text = SERVICE_FILE.read_text(encoding="utf-8")
    start = text.index("INDUSTRY_TAXONOMY: dict[str, str] = {")
    class_marker = "\n\nclass SectorRotationError"
    end = text.index(class_marker, start)
    return text[start:end]


def test_taxonomy_source_has_no_duplicate_keys() -> None:
    block = _taxonomy_source_block()
    keys = re.findall(r'"([^"]+)"\s*:', block)
    counts = Counter(keys)
    duplicates = sorted(key for key, count in counts.items() if count > 1)
    assert duplicates == []


def test_taxonomy_anchor_mappings_are_stable() -> None:
    expected = {
        "HDFCBANK": "Private Banks",
        "ICICIBANK": "Private Banks",
        "SBIN": "PSU Banks",
        "TCS": "IT Services",
        "SUNPHARMA": "Pharma",
        "MARUTI": "Passenger Vehicles",
        "RELIANCE": "Oil & Gas",
        "ACC": "Cement",
        "BHARTIARTL": "Telecom Services",
    }
    for symbol, industry in expected.items():
        assert INDUSTRY_TAXONOMY[symbol] == industry
