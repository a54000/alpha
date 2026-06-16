"""Position sizing utilities for the mean reversion strategy."""

from __future__ import annotations

import math
from typing import Mapping


def calculate_position_size(capital: float, entry_price: float, stop_loss: float, risk_pct: float) -> int:
    """Calculate share quantity from capital-at-risk.

    Args:
        capital: Available capital.
        entry_price: Planned entry price.
        stop_loss: Stop-loss price.
        risk_pct: Fraction of capital to risk.

    Returns:
        Whole-share quantity.

    Raises:
        RuntimeError: Never raised; invalid inputs return zero.
    """

    risk_per_share = abs(float(entry_price) - float(stop_loss))
    if capital <= 0 or entry_price <= 0 or risk_pct <= 0 or risk_per_share <= 0:
        return 0
    return int(math.floor((float(capital) * float(risk_pct)) / risk_per_share))


def apply_position_limits(size: int, capital: float, entry_price: float, max_position_pct: float = 0.15) -> int:
    """Cap position quantity by maximum position value.

    Args:
        size: Requested share quantity.
        capital: Available capital.
        entry_price: Planned entry price.
        max_position_pct: Maximum single-position value as capital fraction.

    Returns:
        Capped whole-share quantity.

    Raises:
        RuntimeError: Never raised; invalid inputs return zero.
    """

    if size <= 0 or capital <= 0 or entry_price <= 0 or max_position_pct <= 0:
        return 0
    max_size = int(math.floor((float(capital) * float(max_position_pct)) / float(entry_price)))
    return max(0, min(int(size), max_size))


def calculate_portfolio_heat(open_positions: list[Mapping[str, float]]) -> float:
    """Calculate total portfolio risk across open trades.

    Args:
        open_positions: Position mappings with capital, quantity, entry_price, and stop_loss.

    Returns:
        Portfolio heat as fraction of capital.

    Raises:
        RuntimeError: Never raised; malformed positions are ignored.
    """

    total_risk = 0.0
    capital_base = 0.0
    for position in open_positions:
        capital = float(position.get("capital", 0.0))
        quantity = float(position.get("quantity", 0.0))
        entry_price = float(position.get("entry_price", 0.0))
        stop_loss = float(position.get("stop_loss", 0.0))
        if capital <= 0 or quantity <= 0:
            continue
        capital_base = max(capital_base, capital)
        total_risk += abs(entry_price - stop_loss) * quantity
    if capital_base <= 0:
        return 0.0
    return total_risk / capital_base
