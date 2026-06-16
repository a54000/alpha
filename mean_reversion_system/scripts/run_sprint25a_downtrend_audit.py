"""Sprint 2.5a downtrend regime audit for Sleeve 3 pre-build validation."""

from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from mean_reversion_system.src.data.db_connector import get_engine

START = pd.Timestamp("2022-05-10")
END = pd.Timestamp("2025-01-01")
OUT = ROOT / "results" / "sprint_2_5a"


@dataclass(frozen=True)
class DowntrendStreak:
    streak_id: int
    start_date: str
    end_date: str
    duration_sessions: int
    nifty_return_pct: float
    max_drawdown_pct: float
    avg_adx: float
    clean_trend: bool
    viability_flag: str


def _load_labels() -> pd.DataFrame:
    path = ROOT / "results" / "sprint_2_1" / "daily_regime_labels.csv"
    labels = pd.read_csv(path)
    labels["session_date"] = pd.to_datetime(labels["session_date"])
    labels = labels.loc[(labels["session_date"] >= START) & (labels["session_date"] <= END)].copy()
    labels = labels.sort_values("session_date").reset_index(drop=True)
    return labels


def _load_nifty_daily() -> pd.DataFrame:
    query = """
        WITH bars AS (
            SELECT
                (datetime AT TIME ZONE 'Asia/Kolkata')::date AS session_date,
                datetime,
                open::double precision AS open,
                high::double precision AS high,
                low::double precision AS low,
                close::double precision AS close
            FROM public.ohlcv_15min
            WHERE symbol = 'NIFTY50'
              AND (datetime AT TIME ZONE 'Asia/Kolkata')::date >= :start_date
              AND (datetime AT TIME ZONE 'Asia/Kolkata')::date <= :end_date
        ),
        ranked AS (
            SELECT
                *,
                row_number() OVER (PARTITION BY session_date ORDER BY datetime ASC) AS rn_open,
                row_number() OVER (PARTITION BY session_date ORDER BY datetime DESC) AS rn_close
            FROM bars
        )
        SELECT
            session_date,
            max(open) FILTER (WHERE rn_open = 1) AS open,
            max(high) AS high,
            min(low) AS low,
            max(close) FILTER (WHERE rn_close = 1) AS close
        FROM ranked
        GROUP BY session_date
        ORDER BY session_date
    """
    frame = pd.read_sql(text(query), get_engine(), params={"start_date": START.date(), "end_date": END.date()})
    frame["session_date"] = pd.to_datetime(frame["session_date"])
    return frame


def _find_downtrend_streaks(labels: pd.DataFrame, nifty: pd.DataFrame) -> pd.DataFrame:
    merged = labels.merge(nifty, on="session_date", how="left", suffixes=("_label", ""))
    streaks: list[pd.DataFrame] = []
    current: list[int] = []
    for idx, row in merged.iterrows():
        if row["regime_label"] == "DOWNTREND":
            current.append(idx)
        elif current:
            streaks.append(merged.loc[current].copy())
            current = []
    if current:
        streaks.append(merged.loc[current].copy())

    rows: list[DowntrendStreak] = []
    for streak_id, streak in enumerate(streaks, start=1):
        first = streak.iloc[0]
        last = streak.iloc[-1]
        closes = pd.to_numeric(streak["close"], errors="coerce")
        start_close = float(first["close"])
        end_close = float(last["close"])
        nifty_return = end_close / start_close - 1 if start_close else 0.0
        drawdown = closes / closes.cummax() - 1
        avg_adx = float(pd.to_numeric(streak["adx"], errors="coerce").mean())
        clean_trend = bool((pd.to_numeric(streak["adx"], errors="coerce") > 25).mean() > 0.70)
        duration = int(len(streak))
        if duration < 10:
            flag = "TOO_SHORT"
        elif clean_trend:
            flag = "VIABLE"
        else:
            flag = "MARGINAL"
        rows.append(
            DowntrendStreak(
                streak_id=streak_id,
                start_date=first["session_date"].date().isoformat(),
                end_date=last["session_date"].date().isoformat(),
                duration_sessions=duration,
                nifty_return_pct=float(nifty_return),
                max_drawdown_pct=float(drawdown.min()) if len(drawdown) else 0.0,
                avg_adx=avg_adx,
                clean_trend=clean_trend,
                viability_flag=flag,
            )
        )
    return pd.DataFrame([asdict(row) for row in rows])


def _opportunity(streaks: pd.DataFrame, nifty: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for row in streaks.itertuples(index=False):
        if row.viability_flag != "VIABLE":
            continue
        window = nifty.loc[(nifty["session_date"] >= pd.Timestamp(row.start_date)) & (nifty["session_date"] <= pd.Timestamp(row.end_date))].copy()
        if window.empty:
            continue
        entry = float(window.iloc[0]["open"])
        exit_price = float(window.iloc[-1]["close"])
        lows = pd.to_numeric(window["low"], errors="coerce")
        highs = pd.to_numeric(window["high"], errors="coerce")
        naive_return = (entry - exit_price) / entry if entry else 0.0
        peak_gain = (entry - float(lows.min())) / entry if entry else 0.0
        max_adverse = (float(highs.max()) - entry) / entry if entry else 0.0
        rows.append(
            {
                "streak_id": row.streak_id,
                "start_date": row.start_date,
                "end_date": row.end_date,
                "duration_sessions": row.duration_sessions,
                "entry_price": entry,
                "exit_price": exit_price,
                "naive_short_return_pct": naive_return,
                "peak_gain_pct": peak_gain,
                "max_adverse_excursion_pct": max_adverse,
                "capture_efficiency_ceiling": naive_return / peak_gain if peak_gain > 0 else 0.0,
            }
        )
    return pd.DataFrame(rows)


def _cost_placeholder(opportunity: pd.DataFrame) -> dict[str, object]:
    if opportunity.empty:
        avg_return = 0.0
        avg_adverse = 0.0
    else:
        avg_return = float(opportunity["naive_short_return_pct"].mean())
        avg_adverse = float(opportunity["max_adverse_excursion_pct"].mean())
    return {
        "status": "placeholder",
        "note": "Prompt was truncated at futures cost model. Costs were not used to change viability.",
        "minimum_meaningful_naive_return_threshold": 0.03,
        "strong_naive_return_threshold": 0.08,
        "avg_naive_short_return_pct": avg_return,
        "avg_max_adverse_excursion_pct": avg_adverse,
        "cost_model_required_before_build": True,
    }


def _verdict(labels: pd.DataFrame, streaks: pd.DataFrame, opportunity: pd.DataFrame, cost: dict[str, object]) -> str:
    counts = labels["regime_label"].value_counts().reindex(["UPTREND", "RANGING", "DOWNTREND"], fill_value=0)
    total = int(len(labels))
    downtrend_days = int(counts["DOWNTREND"])
    viable = streaks.loc[streaks["viability_flag"] == "VIABLE"]
    marginal = streaks.loc[streaks["viability_flag"] == "MARGINAL"]
    too_short = streaks.loc[streaks["viability_flag"] == "TOO_SHORT"]
    avg_return = float(opportunity["naive_short_return_pct"].mean()) if not opportunity.empty else 0.0
    avg_adverse = float(opportunity["max_adverse_excursion_pct"].mean()) if not opportunity.empty else 0.0
    enough_days = downtrend_days >= 60
    enough_streaks = len(viable) >= 3
    meaningful_return = avg_return >= 0.03
    decision = (
        "VIABLE ENOUGH FOR RESEARCH BUILD"
        if enough_days and enough_streaks and meaningful_return
        else "DATA THIN / DO NOT BUILD FULL FUTURES SHORT YET"
    )
    lines = [
        "SPRINT 2.5a - DOWNTREND REGIME AUDIT",
        "Disha | Sleeve 3 Pre-Build Validation",
        "",
        f"WINDOW: {START.date().isoformat()} to {END.date().isoformat()}",
        "",
        "REGIME DISTRIBUTION:",
        f"  Total sessions: {total}",
        f"  UPTREND: {int(counts['UPTREND'])} ({counts['UPTREND'] / total:.2%})",
        f"  RANGING: {int(counts['RANGING'])} ({counts['RANGING'] / total:.2%})",
        f"  DOWNTREND: {downtrend_days} ({downtrend_days / total:.2%})",
        "",
        "DOWNTREND STREAKS:",
        f"  Total streaks: {len(streaks)}",
        f"  VIABLE: {len(viable)}",
        f"  MARGINAL: {len(marginal)}",
        f"  TOO_SHORT: {len(too_short)}",
        "",
        "NAIVE FUTURES SHORT OPPORTUNITY:",
        f"  Avg naive short return on viable streaks: {avg_return:.2%}",
        f"  Avg max adverse excursion: {avg_adverse:.2%}",
        f"  Cost placeholder avg return: {float(cost['avg_naive_short_return_pct']):.2%}",
        "",
        "GATES:",
        f"  Total downtrend days >= 60: {'PASS' if enough_days else 'FAIL'}",
        f"  Viable streak count >= 3: {'PASS' if enough_streaks else 'FAIL'}",
        f"  Avg naive short return >= 3%: {'PASS' if meaningful_return else 'FAIL'}",
        "",
        f"DECISION: {decision}",
    ]
    return "\n".join(lines)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    labels = _load_labels()
    nifty = _load_nifty_daily()
    downtrend_sessions = labels.loc[labels["regime_label"] == "DOWNTREND"].copy()
    downtrend_sessions.to_csv(OUT / "downtrend_sessions.csv", index=False)
    streaks = _find_downtrend_streaks(labels, nifty)
    opportunity = _opportunity(streaks, nifty)
    cost = _cost_placeholder(opportunity)
    streaks.to_csv(OUT / "downtrend_streaks.csv", index=False)
    opportunity.to_csv(OUT / "downtrend_opportunity.csv", index=False)
    (OUT / "futures_cost_model_placeholder.json").write_text(json.dumps(cost, indent=2), encoding="utf-8")
    verdict = _verdict(labels, streaks, opportunity, cost)
    (OUT / "SPRINT_2_5A_VERDICT.txt").write_text(verdict, encoding="utf-8")
    print(verdict)


if __name__ == "__main__":
    main()

