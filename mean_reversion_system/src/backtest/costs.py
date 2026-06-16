"""Transaction cost model for realistic Indian equity backtests."""

from __future__ import annotations


def calculate_transaction_costs(trade_value: float, trade_type: str = "delivery", side: str = "round_trip") -> dict[str, float]:
    """Calculate Zerodha-style transaction costs.

    Args:
        trade_value: Notional value per leg. For round_trip, this is one leg value.
        trade_type: Trade type, either delivery or intraday.
        side: buy, sell, or round_trip.

    Returns:
        Cost breakdown including brokerage, stt, exchange, sebi, gst, stamp_duty, slippage, and total.

    Raises:
        ValueError: If trade_type or side is unsupported.
    """

    if trade_type not in {"delivery", "intraday"}:
        raise ValueError("trade_type must be delivery or intraday")
    if side not in {"buy", "sell", "round_trip"}:
        raise ValueError("side must be buy, sell, or round_trip")
    value = float(trade_value)
    if value <= 0:
        return {"brokerage": 0.0, "stt": 0.0, "exchange": 0.0, "sebi": 0.0, "gst": 0.0, "stamp_duty": 0.0, "slippage": 0.0, "total": 0.0}

    legs = 2 if side == "round_trip" else 1
    turnover = value * legs
    brokerage = 0.0 if trade_type == "delivery" else min(20.0, value * 0.0003) * legs
    stt_rate = 0.001 if trade_type == "delivery" else 0.00025
    stt = value * stt_rate if side in {"sell", "round_trip"} else 0.0
    exchange = turnover * 0.0000325
    sebi = turnover * 0.000001
    gst = 0.18 * (brokerage + exchange)
    stamp_duty = value * 0.00015 if side in {"buy", "round_trip"} else 0.0
    slippage = turnover * 0.001
    total = brokerage + stt + exchange + sebi + gst + stamp_duty + slippage
    return {
        "brokerage": brokerage,
        "stt": stt,
        "exchange": exchange,
        "sebi": sebi,
        "gst": gst,
        "stamp_duty": stamp_duty,
        "slippage": slippage,
        "total": total,
    }
