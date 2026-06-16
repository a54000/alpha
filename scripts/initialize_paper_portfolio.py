"""Initialize the frozen Swing V2.1 paper portfolio.

This script is idempotent: it reuses an existing configured portfolio when
possible and avoids creating duplicate active portfolios for the same
name/strategy pair.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.paper_trading import SWING_V2_1_MODE, PaperTradingService, paper_trading_config_for_mode
from db.connection import build_engine, load_dotenv
from db.models import PaperPortfolio


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Initialize the Swing V2.1 paper portfolio.")
    parser.add_argument("--database-url", default=None)
    parser.add_argument("--portfolio-id", type=int, default=None)
    parser.add_argument("--name", default="Swing V2.1 Rolling 10 Slot Paper")
    parser.add_argument("--strategy", default=None)
    parser.add_argument("--strategy-mode", default=SWING_V2_1_MODE)
    parser.add_argument("--portfolio-size", type=int, default=10)
    parser.add_argument("--initial-capital", type=float, default=1_000_000.0)
    parser.add_argument("--holding-period", type=int, default=20)
    parser.add_argument("--benchmark-symbol", default="NIFTY500")
    parser.add_argument("--lifecycle-mode", default="hold_to_planned_exit")
    return parser.parse_args()


def configured_portfolio_id(explicit: int | None) -> int | None:
    if explicit is not None:
        return explicit
    value = os.environ.get("PAPER_PORTFOLIO_ID")
    return int(value) if value else None


def find_existing(session, portfolio_id: int | None, name: str, strategy: str):
    if portfolio_id is not None:
        portfolio = session.get(PaperPortfolio, portfolio_id)
        if portfolio is not None:
            return portfolio, "configured_id"

    portfolio = session.execute(
        select(PaperPortfolio)
        .where(
            PaperPortfolio.name == name,
            PaperPortfolio.strategy == strategy,
            PaperPortfolio.status == "active",
        )
        .order_by(PaperPortfolio.portfolio_id.asc())
        .limit(1)
    ).scalar_one_or_none()
    if portfolio is not None:
        return portfolio, "name_strategy"
    return None, None


def main() -> int:
    load_dotenv()
    args = parse_args()
    config = paper_trading_config_for_mode(
        args.strategy_mode,
        **({"strategy": args.strategy} if args.strategy else {}),
        portfolio_size=args.portfolio_size,
        initial_capital=args.initial_capital,
        holding_period=args.holding_period,
        benchmark_symbol=args.benchmark_symbol,
        lifecycle_mode=args.lifecycle_mode,
    )
    portfolio_id = configured_portfolio_id(args.portfolio_id)
    engine = build_engine(args.database_url)
    session_factory = sessionmaker(bind=engine, future=True)

    with session_factory() as session:
        existing, reason = find_existing(session, portfolio_id, args.name, config.strategy)
        if existing is not None:
            print(f"reused portfolio_id={existing.portfolio_id} reason={reason}")
            print(f"name={existing.name}")
            print(f"strategy={existing.strategy}")
            print(f"cash={existing.cash}")
            print(f"current_nav={existing.current_nav}")
            return 0

    service = PaperTradingService(session_factory)
    created_id = service.initialize_portfolio(args.name, config)

    with session_factory() as session:
        portfolio = session.get(PaperPortfolio, created_id)
        if portfolio is not None:
            now = datetime.now(UTC).replace(tzinfo=None)
            portfolio.created_at = portfolio.created_at or now
            portfolio.updated_at = now
            session.commit()

    print(f"created portfolio_id={created_id}")
    print(f"name={args.name}")
    print(f"strategy={config.strategy}")
    print(f"initial_capital={args.initial_capital}")
    print(f"benchmark_symbol={args.benchmark_symbol}")
    print(f"lifecycle_mode={args.lifecycle_mode}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
