"""Mean-reversion universe pre-filter."""

from __future__ import annotations

from typing import List

import pandas as pd


def filter_mean_reversion_universe(df_all_symbols: pd.DataFrame) -> List[str]:
    """Filter the active universe to liquid, tradeable mean-reversion candidates.

    Args:
        df_all_symbols: One row per symbol with liquidity, trend, regime, and volatility columns.

    Returns:
        Symbols passing the Strategy 2.2 minimum viable universe gate.

    Raises:
        ValueError: If required columns are missing.
    """

    required = {
        "symbol",
        "avg_daily_turnover_20d",
        "adx_14",
        "atr_pct_20d",
        "close",
        "sma_200",
    }
    missing = sorted(required - set(df_all_symbols.columns))
    if missing:
        raise ValueError(f"missing universe filter columns: {missing}")

    item = df_all_symbols.copy()
    mask = (
        (item["avg_daily_turnover_20d"] > 20_000_000)
        & (item["close"] > item["sma_200"])
        & (item["adx_14"] < 25.0)
        & (item["atr_pct_20d"].between(1.5, 4.5, inclusive="both"))
    )
    return sorted(item.loc[mask, "symbol"].astype(str).tolist())
