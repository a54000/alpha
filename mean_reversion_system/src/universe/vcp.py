"""Universe filters for the VCP trend-following sleeve."""

from __future__ import annotations

import pandas as pd


def filter_vcp_universe(df_all_symbols: pd.DataFrame) -> list[str]:
    """Return symbols eligible for VCP breakout scanning.

    The filter is intentionally structural: liquidity, Stage 2 trend, proximity
    to highs, and tolerable volatility. Base quality belongs in the signal layer.
    """

    required = {"symbol", "avg_daily_turnover_20d", "close", "sma150", "sma200", "week52_high", "atr_pct_20d"}
    missing = required.difference(df_all_symbols.columns)
    if missing:
        raise ValueError(f"missing required columns: {sorted(missing)}")
    frame = df_all_symbols.copy()
    mask = (
        (pd.to_numeric(frame["avg_daily_turnover_20d"], errors="coerce") > 20_000_000)
        & (pd.to_numeric(frame["close"], errors="coerce") > pd.to_numeric(frame["sma150"], errors="coerce"))
        & (pd.to_numeric(frame["close"], errors="coerce") > pd.to_numeric(frame["sma200"], errors="coerce"))
        & (pd.to_numeric(frame["sma150"], errors="coerce") > pd.to_numeric(frame["sma200"], errors="coerce"))
        & (pd.to_numeric(frame["close"], errors="coerce") >= 0.75 * pd.to_numeric(frame["week52_high"], errors="coerce"))
        & (pd.to_numeric(frame["atr_pct_20d"], errors="coerce") <= 4.5)
    )
    return frame.loc[mask.fillna(False), "symbol"].astype(str).tolist()

