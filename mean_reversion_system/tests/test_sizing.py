from __future__ import annotations

from mean_reversion_system.src.backtest.costs import calculate_transaction_costs
from mean_reversion_system.src.strategy.sizing import calculate_portfolio_heat, calculate_position_size, apply_position_limits


def test_position_size_matches_manual_calculation():
    size = calculate_position_size(capital=1_000_000, entry_price=100.0, stop_loss=95.0, risk_pct=0.01)

    assert size == 2000


def test_position_size_zero_when_stop_equals_entry():
    size = calculate_position_size(capital=1_000_000, entry_price=100.0, stop_loss=100.0, risk_pct=0.01)

    assert size == 0


def test_apply_position_limits_caps_single_position_value():
    capped = apply_position_limits(size=2000, capital=1_000_000, entry_price=100.0, max_position_pct=0.15)

    assert capped == 1500


def test_portfolio_heat_for_mixed_long_short_book():
    positions = [
        {"capital": 1_000_000, "quantity": 100, "entry_price": 100.0, "stop_loss": 95.0},
        {"capital": 1_000_000, "quantity": 200, "entry_price": 100.0, "stop_loss": 103.0},
    ]

    heat = calculate_portfolio_heat(positions)

    assert heat == 0.0011


def test_delivery_round_trip_cost_on_one_lakh_trade_uses_zero_brokerage():
    costs = calculate_transaction_costs(100_000, trade_type="delivery", side="round_trip")

    assert 300 <= costs["total"] <= 360
    assert costs["brokerage"] == 0
    assert costs["stt"] == 100


def test_intraday_round_trip_cost_on_one_lakh_trade_charges_brokerage():
    costs = calculate_transaction_costs(100_000, trade_type="intraday", side="round_trip")

    assert costs["brokerage"] == 40
    assert costs["stt"] == 25
