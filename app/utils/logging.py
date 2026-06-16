"""Logging helpers for application bootstrap.

Reads:
  - Optional log level from configuration

Writes:
  - Python logger instances only

Does not:
  - Emit to external services
  - Decide pipeline status
"""

from __future__ import annotations

import logging
from typing import Any


def build_logger(name: str, level: str | int = logging.INFO) -> logging.Logger:
    """Return a configured application logger."""

    logger = logging.getLogger(name)
    logger.setLevel(level)
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    logger.propagate = False
    return logger


def configure_root_logging(log_level: str | int) -> logging.Logger:
    """Configure and return the root platform logger."""

    return build_logger("nse_research_platform", log_level)

