"""Daily paper trading update entry point.

This module updates an existing paper portfolio using the frozen
PaperTradingService behavior. It does not place broker orders.
"""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

from app.paper_trading.data_source import PaperTradingSourceConfig, build_data_source, normalize_source_name, source_config_from_env
from app.paper_trading.service import SWING_V2_1_MODE, PaperTradingService, paper_trading_config_for_mode
from db.session import build_session_factory


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Update an existing paper portfolio for one cycle date.")
    parser.add_argument("--cycle-date", required=True)
    parser.add_argument("--portfolio-id", type=int, required=True)
    parser.add_argument("--portfolio-size", type=int, default=10)
    parser.add_argument("--max-candidate-rank", type=int, default=5)
    parser.add_argument("--holding-period", type=int, default=20)
    parser.add_argument("--strategy-mode", default="sector_rotation_adx_r10_vwap25")
    parser.add_argument("--rebalance", action="store_true", help="Also run weekly rebalance for the cycle date.")
    parser.add_argument("--data-source", choices=["production", "pilot_phase2a"], help="Override PAPER_TRADING_DATA_SOURCE.")
    parser.add_argument("--output-json", default="reports/latest_paper_update.json")
    return parser.parse_args()


def main() -> int:
    load_dotenv()
    args = parse_args()
    cycle_date = date.fromisoformat(args.cycle_date)
    source_config = source_config_from_env()
    if args.data_source:
        source_config = PaperTradingSourceConfig(
            name=normalize_source_name(args.data_source),
            pilot_schema=source_config.pilot_schema,
            angel_database_url=source_config.angel_database_url,
        )
    service = PaperTradingService(build_session_factory(), data_source=build_data_source(source_config))
    config = paper_trading_config_for_mode(
        args.strategy_mode,
        portfolio_size=args.portfolio_size,
        max_candidate_rank=args.max_candidate_rank,
        holding_period=args.holding_period,
        lifecycle_mode="hold_to_planned_exit",
    )
    validation: list[dict[str, object]] = []
    if args.rebalance:
        validation.append(service.rebalance_weekly(args.portfolio_id, cycle_date, config))
    validation.append(service.update_daily(args.portfolio_id, cycle_date))
    report = service.performance_report(args.portfolio_id)
    payload = {"performance": report, "validation": validation}
    output_path = Path(args.output_json)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print(json.dumps(payload, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
