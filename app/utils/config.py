"""Configuration loading helpers.

Reads:
  - YAML configuration from `configs/config.yaml`

Writes:
  - Nothing

Does not:
  - Connect to databases
  - Validate business rules
  - Interpret scoring logic
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class AppConfig:
    """Thin wrapper around the parsed platform configuration."""

    raw: dict[str, Any]
    path: Path


def load_config(config_path: str | Path) -> AppConfig:
    """Load the canonical configuration file using a small YAML subset parser."""

    path = Path(config_path)
    lines = path.read_text(encoding="utf-8").splitlines()
    parsed, _ = _parse_block(lines, 0, 0)
    return AppConfig(raw=parsed, path=path)


def _parse_block(lines: list[str], start_index: int, indent: int) -> tuple[dict[str, Any], int]:
    data: dict[str, Any] = {}
    index = start_index

    while index < len(lines):
        raw_line = lines[index]
        stripped = raw_line.strip()

        if not stripped or stripped.startswith("#"):
            index += 1
            continue

        current_indent = len(raw_line) - len(raw_line.lstrip(" "))
        if current_indent < indent:
            break
        if current_indent > indent:
            index += 1
            continue

        key, value_text = [part.strip() for part in stripped.split(":", 1)]
        if value_text:
            data[key] = _parse_scalar(value_text)
            index += 1
            continue

        next_index = index + 1
        while next_index < len(lines) and not lines[next_index].strip():
            next_index += 1
        if next_index >= len(lines):
            data[key] = {}
            index = next_index
            continue

        next_line = lines[next_index]
        next_indent = len(next_line) - len(next_line.lstrip(" "))
        if next_line.strip().startswith("- "):
            data[key], index = _parse_list(lines, next_index, next_indent)
        else:
            data[key], index = _parse_block(lines, next_index, next_indent)

    return data, index


def _parse_list(lines: list[str], start_index: int, indent: int) -> tuple[list[Any], int]:
    values: list[Any] = []
    index = start_index

    while index < len(lines):
        raw_line = lines[index]
        stripped = raw_line.strip()
        if not stripped:
            index += 1
            continue

        current_indent = len(raw_line) - len(raw_line.lstrip(" "))
        if current_indent < indent or not stripped.startswith("- "):
            break

        values.append(_parse_scalar(stripped[2:].strip()))
        index += 1

    return values, index


def _parse_scalar(value: str) -> Any:
    lowered = value.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if value.startswith('"') and value.endswith('"'):
        return value[1:-1]
    if value.startswith("'") and value.endswith("'"):
        return value[1:-1]
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [_parse_scalar(part.strip()) for part in inner.split(",")]
    if "." in value:
        try:
            return float(value.replace("_", ""))
        except ValueError:
            return value
    try:
        return int(value.replace("_", ""))
    except ValueError:
        return value
