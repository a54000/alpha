"""Mean-reversion universe filters."""

from __future__ import annotations

from typing import List

import pandas as pd

from mean_reversion_system.src.universe.filter import filter_mean_reversion_universe


def filter_mean_reversion_universe_minimal(df_all: pd.DataFrame) -> List[str]:
    """Return symbols passing the four-condition minimum viable filter."""

    return filter_mean_reversion_universe(df_all)
