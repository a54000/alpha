"""Sprint 2.1 regime-overlap cross-check."""

from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from mean_reversion_system.src.data.db_connector import get_engine

START = date(2021, 6, 14)
END = date(2026, 6, 13)
OVERLAP_START = date(2022, 5, 10)
OVERLAP_END = date(2025, 1, 1)
OUT = ROOT / "results" / "sprint_2_1"


@dataclass(frozen=True)
class Streak:
    regime_label: str
    streak_start: date
    streak_end: date
    duration_sessions: int


def _load_nifty50_daily() -> pd.DataFrame:
    query = """
        WITH bars AS (
            SELECT
                (datetime AT TIME ZONE 'Asia/Kolkata')::date AS session_date,
                datetime,
                open::double precision AS open,
                high::double precision AS high,
                low::double precision AS low,
                close::double precision AS close,
                volume::bigint AS volume
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
            session_date AS date,
            max(open) FILTER (WHERE rn_open = 1) AS open,
            max(high) AS high,
            min(low) AS low,
            max(close) FILTER (WHERE rn_close = 1) AS close,
            sum(volume) AS volume
        FROM ranked
        GROUP BY session_date
        ORDER BY session_date
    """
    frame = pd.read_sql(text(query), get_engine(), params={"start_date": START, "end_date": END})
    if frame.empty:
        raise RuntimeError("No NIFTY50 rows found in public.ohlcv_15min for Sprint 2.1.")
    frame["date"] = pd.to_datetime(frame["date"]).dt.date
    frame = frame.set_index("date").sort_index()
    return frame


def _adx_shifted(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    high = pd.to_numeric(df["high"], errors="coerce")
    low = pd.to_numeric(df["low"], errors="coerce")
    close = pd.to_numeric(df["close"], errors="coerce")
    up_move = high.diff()
    down_move = -low.diff()
    plus_dm = pd.Series(np.where((up_move > down_move) & (up_move > 0), up_move, 0.0), index=df.index)
    minus_dm = pd.Series(np.where((down_move > up_move) & (down_move > 0), down_move, 0.0), index=df.index)
    previous_close = close.shift(1)
    true_range = pd.concat([(high - low), (high - previous_close).abs(), (low - previous_close).abs()], axis=1).max(axis=1)
    atr = true_range.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    di_plus = 100 * plus_dm.ewm(alpha=1 / period, adjust=False, min_periods=period).mean() / atr.replace(0, np.nan)
    di_minus = 100 * minus_dm.ewm(alpha=1 / period, adjust=False, min_periods=period).mean() / atr.replace(0, np.nan)
    dx = 100 * (di_plus - di_minus).abs() / (di_plus + di_minus).replace(0, np.nan)
    adx = dx.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    return pd.DataFrame({"adx": adx.shift(1), "di_plus": di_plus.shift(1), "di_minus": di_minus.shift(1)}, index=df.index)


def _confidence(row: pd.Series) -> float:
    if pd.isna(row["adx"]) or pd.isna(row["sma50"]) or pd.isna(row["sma200"]):
        return 0.0
    close_score = 0.0
    if row["regime_label"] == "UPTREND":
        close_score = min(max((row["label_close"] / row["sma50"] - 1) / 0.05, 0.0), 1.0)
        di_score = min(max((row["di_plus"] - row["di_minus"]) / 20.0, 0.0), 1.0)
    elif row["regime_label"] == "DOWNTREND":
        close_score = min(max((1 - row["label_close"] / row["sma200"]) / 0.05, 0.0), 1.0)
        di_score = min(max((row["di_minus"] - row["di_plus"]) / 20.0, 0.0), 1.0)
    else:
        close_score = 1.0 if row["adx"] < 20 else min(abs(row["di_plus"] - row["di_minus"]) / 20.0, 1.0)
        di_score = 1.0 - min(abs(row["di_plus"] - row["di_minus"]) / 20.0, 1.0)
    adx_score = min(max((row["adx"] - 20.0) / 20.0, 0.0), 1.0) if row["regime_label"] != "RANGING" else 1.0 - min(max((row["adx"] - 20.0) / 20.0, 0.0), 1.0)
    return float(np.mean([close_score, di_score, adx_score]))


def _label_regimes(proxy: pd.DataFrame) -> pd.DataFrame:
    item = proxy.copy()
    indicators = _adx_shifted(item)
    item["nifty_close"] = item["close"].shift(1)
    item["label_close"] = item["close"].shift(1)
    item["sma50"] = item["close"].rolling(50, min_periods=50).mean().shift(1)
    item["sma200"] = item["close"].rolling(200, min_periods=200).mean().shift(1)
    item = item.join(indicators)
    downtrend = (item["label_close"] < item["sma200"]) & (item["adx"] > 20) & (item["di_minus"] > item["di_plus"])
    uptrend = (item["label_close"] > item["sma50"]) & (item["label_close"] > item["sma200"]) & (item["adx"] > 20) & (item["di_plus"] > item["di_minus"])
    item["regime_label"] = "RANGING"
    item.loc[uptrend, "regime_label"] = "UPTREND"
    item.loc[downtrend, "regime_label"] = "DOWNTREND"
    item["regime_confidence"] = item.apply(_confidence, axis=1)
    result = item.loc[(pd.Series(item.index, index=item.index) >= START) & (pd.Series(item.index, index=item.index) <= END)].copy()
    result.insert(0, "session_date", result.index)
    return result[["session_date", "nifty_close", "sma50", "sma200", "adx", "di_plus", "di_minus", "regime_label", "regime_confidence"]]


def _streaks(labels: pd.DataFrame, proxy: pd.DataFrame) -> pd.DataFrame:
    rows: list[Streak] = []
    current = None
    start = None
    prev = None
    count = 0
    for _, row in labels.iterrows():
        label = row["regime_label"]
        session = row["session_date"]
        if current is None:
            current, start, prev, count = label, session, session, 1
            continue
        if label == current:
            prev = session
            count += 1
        else:
            rows.append(Streak(str(current), start, prev, count))
            current, start, prev, count = label, session, session, 1
    if current is not None:
        rows.append(Streak(str(current), start, prev, count))
    frame = pd.DataFrame([asdict(row) for row in rows])
    returns = []
    for _, row in frame.iterrows():
        start_close = float(proxy.loc[row["streak_start"], "close"]) if row["streak_start"] in proxy.index else np.nan
        end_close = float(proxy.loc[row["streak_end"], "close"]) if row["streak_end"] in proxy.index else np.nan
        returns.append(end_close / start_close - 1 if start_close and not pd.isna(start_close) else np.nan)
    frame["nifty_return_during_streak"] = returns
    frame["viable_for_vcp"] = (frame["regime_label"] == "UPTREND") & (frame["duration_sessions"] >= 15)
    return frame


def _write_distribution(labels: pd.DataFrame, streaks: pd.DataFrame) -> pd.DataFrame:
    total = len(labels)
    overall = labels["regime_label"].value_counts().reindex(["UPTREND", "RANGING", "DOWNTREND"], fill_value=0)
    rows = [
        {"scope": "overall", "year": "ALL", "regime": key, "sessions": int(value), "pct": float(value / total) if total else 0.0}
        for key, value in overall.items()
    ]
    labels["year"] = pd.to_datetime(labels["session_date"]).dt.year
    for year, group in labels.groupby("year"):
        counts = group["regime_label"].value_counts().reindex(["UPTREND", "RANGING", "DOWNTREND"], fill_value=0)
        dominant = str(counts.idxmax())
        for regime, sessions in counts.items():
            rows.append({"scope": "year", "year": int(year), "regime": regime, "sessions": int(sessions), "pct": float(sessions / len(group)), "dominant_regime": dominant})
    dist = pd.DataFrame(rows)
    dist.to_csv(OUT / "regime_distribution.csv", index=False)
    streaks.to_csv(OUT / "regime_streaks.csv", index=False)
    return dist


def _overlap(labels: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    deployment = pd.read_csv(ROOT / "reports" / "backtests" / "v4b_capital_productivity" / "daily_deployment.csv")
    deployment["session_date"] = pd.to_datetime(deployment["date"]).dt.date
    deployment = deployment.loc[(deployment["session_date"] >= OVERLAP_START) & (deployment["session_date"] <= OVERLAP_END)].copy()
    merged = deployment.merge(labels, on="session_date", how="inner")
    merged["v4b_open_positions"] = merged["open_positions"]
    merged["v4b_is_idle"] = merged["v4b_open_positions"] == 0
    merged["v4b_state"] = np.where(merged["v4b_is_idle"], "IDLE", "DEPLOYED")
    matrix = pd.crosstab(merged["v4b_state"], merged["regime_label"]).reindex(index=["IDLE", "DEPLOYED"], columns=["UPTREND", "RANGING", "DOWNTREND"], fill_value=0)
    matrix["TOTAL"] = matrix.sum(axis=1)
    total_row = matrix.sum(axis=0).to_frame().T
    total_row.index = ["TOTAL"]
    matrix = pd.concat([matrix, total_row])
    matrix.to_csv(OUT / "idle_capital_regime_overlap.csv")
    idle = merged.loc[merged["v4b_is_idle"]]
    deployed = merged.loc[~merged["v4b_is_idle"]]
    payload = {
        "counts": matrix.to_dict(),
        "pct_of_all_sessions": (matrix / len(merged)).to_dict(),
        "uptrend_idle_pct": float((idle["regime_label"] == "UPTREND").mean()) if len(idle) else 0.0,
        "idle_regime_pct": idle["regime_label"].value_counts(normalize=True).reindex(["UPTREND", "RANGING", "DOWNTREND"], fill_value=0).to_dict(),
        "deployed_regime_pct": deployed["regime_label"].value_counts(normalize=True).reindex(["UPTREND", "RANGING", "DOWNTREND"], fill_value=0).to_dict(),
        "v4b_deployed_in_ranging": float((deployed["regime_label"] == "RANGING").mean()) if len(deployed) else 0.0,
        "sessions_joined": int(len(merged)),
    }
    (OUT / "overlap_matrix.json").write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    return merged, payload


def _load_stock_daily() -> pd.DataFrame:
    query = """
        WITH bars AS (
            SELECT
                symbol,
                (datetime AT TIME ZONE 'Asia/Kolkata')::date AS session_date,
                datetime,
                open::double precision AS open,
                high::double precision AS high,
                low::double precision AS low,
                close::double precision AS close,
                volume::bigint AS volume
            FROM public.ohlcv_15min
            WHERE symbol NOT IN ('NIFTY50', 'BANKNIFTY')
              AND volume > 0
              AND (datetime AT TIME ZONE 'Asia/Kolkata')::date >= :start_date
              AND (datetime AT TIME ZONE 'Asia/Kolkata')::date <= :end_date
        ),
        ranked AS (
            SELECT
                *,
                row_number() OVER (PARTITION BY symbol, session_date ORDER BY datetime ASC) AS rn_open,
                row_number() OVER (PARTITION BY symbol, session_date ORDER BY datetime DESC) AS rn_close
            FROM bars
        )
        SELECT
            symbol,
            session_date AS date,
            max(open) FILTER (WHERE rn_open = 1) AS open,
            max(high) AS high,
            min(low) AS low,
            max(close) FILTER (WHERE rn_close = 1) AS close,
            sum(volume) AS volume
        FROM ranked
        GROUP BY symbol, session_date
        ORDER BY symbol, session_date
    """
    frame = pd.read_sql(text(query), get_engine(), params={"start_date": START, "end_date": END})
    if frame.empty:
        raise RuntimeError("No stock rows found in public.ohlcv_15min for Sprint 2.1 VCP opportunity test.")
    frame["date"] = pd.to_datetime(frame["date"]).dt.date
    return frame


def _stock_vcp_opportunities(labels: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    stock_daily = _load_stock_daily()
    frames = []
    for symbol, group in stock_daily.groupby("symbol", sort=False):
        item = group.sort_values("date").copy()
        close = item["close"].astype(float)
        high = item["high"].astype(float)
        low = item["low"].astype(float)
        previous_close = close.shift(1)
        true_range = pd.concat([(high - low), (high - previous_close).abs(), (low - previous_close).abs()], axis=1).max(axis=1)
        sma20 = close.rolling(20, min_periods=20).mean()
        std20 = close.rolling(20, min_periods=20).std(ddof=0)
        bb_width = ((sma20 + 2 * std20) - (sma20 - 2 * std20)) / sma20.replace(0, np.nan)
        atr20 = true_range.rolling(20, min_periods=20).mean()
        item["sma150"] = close.rolling(150, min_periods=150).mean().shift(1)
        item["sma200"] = close.rolling(200, min_periods=200).mean().shift(1)
        item["week52_high"] = high.rolling(252, min_periods=126).max().shift(1)
        item["bb_width"] = bb_width.shift(1)
        item["atr_pct_20d"] = (atr20 / close * 100.0).shift(1)
        item["bb_width_60d_median"] = bb_width.rolling(60, min_periods=40).median().shift(1)
        item["avg_volume_20d"] = item["volume"].rolling(20, min_periods=20).mean().shift(1)
        item["avg_volume_60d"] = item["volume"].rolling(60, min_periods=40).mean().shift(1)
        item["label_close"] = close.shift(1)
        item["stage2"] = (item["label_close"] > item["sma150"]) & (item["label_close"] > item["sma200"]) & (item["sma150"] > item["sma200"])
        item["near_52w_high"] = item["label_close"] >= item["week52_high"] * 0.75
        item["price_contraction"] = (item["bb_width"] <= 0.12) & (item["bb_width"] <= item["bb_width_60d_median"] * 0.90)
        item["volatility_ok"] = item["atr_pct_20d"] <= 4.5
        item["volume_contraction"] = item["avg_volume_20d"] <= item["avg_volume_60d"] * 0.90
        item["contraction_base"] = item["price_contraction"] & item["volatility_ok"] & item["volume_contraction"]
        item["vcp_candidate"] = item["stage2"] & item["near_52w_high"] & item["contraction_base"]
        frames.append(item[["date", "symbol", "label_close", "sma150", "sma200", "week52_high", "bb_width", "atr_pct_20d", "stage2", "near_52w_high", "price_contraction", "volatility_ok", "volume_contraction", "contraction_base", "vcp_candidate"]])
    features = pd.concat(frames, ignore_index=True)
    labels_key = labels.copy()
    labels_key["constructive_market"] = (
        (labels_key["regime_label"] == "UPTREND")
        | (
            (labels_key["regime_label"] == "RANGING")
            & (labels_key["nifty_close"] > labels_key["sma200"])
            & (labels_key["di_plus"] >= labels_key["di_minus"])
        )
    )
    merged = features.merge(labels_key[["session_date", "regime_label", "constructive_market"]], left_on="date", right_on="session_date", how="inner")
    merged["vcp_opportunity"] = merged["constructive_market"] & merged["vcp_candidate"]
    merged.to_csv(OUT / "vcp_stock_opportunities.csv", index=False)

    daily = (
        merged.groupby("date")
        .agg(
            market_regime=("regime_label", "first"),
            constructive_market=("constructive_market", "first"),
            symbols_tested=("symbol", "nunique"),
            stage2_symbols=("stage2", "sum"),
            near_high_symbols=("near_52w_high", "sum"),
            contraction_base_symbols=("contraction_base", "sum"),
            vcp_candidate_symbols=("vcp_candidate", "sum"),
            vcp_opportunity_symbols=("vcp_opportunity", "sum"),
        )
        .reset_index()
    )
    daily.to_csv(OUT / "vcp_stock_opportunity_daily.csv", index=False)
    eligible = daily.loc[daily["constructive_market"]]
    opportunity_days = daily.loc[daily["vcp_opportunity_symbols"] > 0]
    summary = {
        "symbols_tested": int(merged["symbol"].nunique()),
        "sessions_tested": int(daily.shape[0]),
        "constructive_market_sessions": int(eligible.shape[0]),
        "constructive_market_pct": float(eligible.shape[0] / daily.shape[0]) if len(daily) else 0.0,
        "opportunity_days": int(opportunity_days.shape[0]),
        "opportunity_days_pct": float(opportunity_days.shape[0] / daily.shape[0]) if len(daily) else 0.0,
        "opportunity_days_during_constructive_market_pct": float((eligible["vcp_opportunity_symbols"] > 0).mean()) if len(eligible) else 0.0,
        "avg_opportunities_per_constructive_session": float(eligible["vcp_opportunity_symbols"].mean()) if len(eligible) else 0.0,
        "median_opportunities_per_constructive_session": float(eligible["vcp_opportunity_symbols"].median()) if len(eligible) else 0.0,
        "max_opportunities_in_session": int(daily["vcp_opportunity_symbols"].max()) if len(daily) else 0,
        "total_symbol_day_opportunities": int(merged["vcp_opportunity"].sum()),
        "symbols_with_at_least_one_opportunity": int(merged.loc[merged["vcp_opportunity"], "symbol"].nunique()),
    }
    (OUT / "vcp_stock_opportunity_summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    return daily, summary


def _verdict(labels: pd.DataFrame, streaks: pd.DataFrame, overlap: dict, vcp_summary: dict) -> str:
    counts = labels["regime_label"].value_counts().reindex(["UPTREND", "RANGING", "DOWNTREND"], fill_value=0)
    pct = counts / len(labels)
    avg_durations = streaks.groupby("regime_label")["duration_sessions"].mean().reindex(["UPTREND", "RANGING", "DOWNTREND"], fill_value=0)
    uptrend_idle_pct = overlap["uptrend_idle_pct"]
    v4b_deployed = overlap["deployed_regime_pct"]
    alignment = "STRONG" if overlap["v4b_deployed_in_ranging"] > 0.60 else ("MODERATE" if overlap["v4b_deployed_in_ranging"] >= 0.50 else "WEAK")
    hypothesis = "CONFIRMED" if uptrend_idle_pct > 0.40 else ("PARTIAL" if uptrend_idle_pct >= 0.25 else "WEAK")
    viability = (
        "SUFFICIENT"
        if vcp_summary["opportunity_days"] >= 100 and vcp_summary["symbols_with_at_least_one_opportunity"] >= 50
        else ("PARTIAL" if vcp_summary["opportunity_days"] >= 50 and vcp_summary["symbols_with_at_least_one_opportunity"] >= 25 else "INSUFFICIENT")
    )
    if hypothesis == "CONFIRMED" and viability == "SUFFICIENT":
        decision = "CONFIRMED + STOCK-LEVEL SUFFICIENT: Sprint 2.2 should build VCP entry signal logic."
    elif hypothesis in {"CONFIRMED", "PARTIAL"} and viability in {"SUFFICIENT", "PARTIAL"}:
        decision = "PARTIAL + STOCK-LEVEL VIABLE: Build VCP next, but size allocation conservatively until backtest confirms realized edge."
    else:
        decision = "WEAK or INSUFFICIENT: VCP needs a narrower build/test or sleeve alternatives should be compared."
    lines = [
        "------------------------------------------------------------",
        "SPRINT 2.1 - REGIME DIAGNOSIS VERDICT",
        "Disha | Mean Reversion + Complementary Sleeve Selection",
        "------------------------------------------------------------",
        "",
        f"DATA SOURCE: public.ohlcv_15min actual NIFTY50 index data, resampled to daily from 15-minute bars.",
        "",
        f"REGIME DISTRIBUTION ({START.isoformat()} to {END.isoformat()}):",
        f"  UPTREND   : {int(counts['UPTREND'])} sessions ({pct['UPTREND']:.2%})",
        f"  RANGING   : {int(counts['RANGING'])} sessions ({pct['RANGING']:.2%})",
        f"  DOWNTREND : {int(counts['DOWNTREND'])} sessions ({pct['DOWNTREND']:.2%})",
        f"  Avg regime duration: UPTREND {avg_durations['UPTREND']:.1f}d | RANGING {avg_durations['RANGING']:.1f}d | DOWNTREND {avg_durations['DOWNTREND']:.1f}d",
        "",
        "V4B ALIGNMENT:",
        f"  V4b deployed in RANGING regime : {v4b_deployed.get('RANGING', 0):.2%} (target > 60%)",
        f"  V4b deployed in UPTREND regime : {v4b_deployed.get('UPTREND', 0):.2%}",
        f"  V4b deployed in DOWNTREND      : {v4b_deployed.get('DOWNTREND', 0):.2%}",
        f"  Alignment verdict: {alignment}",
        "",
        "IDLE CAPITAL OVERLAP:",
        f"  Idle sessions in UPTREND  : {overlap['idle_regime_pct'].get('UPTREND', 0):.2%}",
        f"  Idle sessions in RANGING  : {overlap['idle_regime_pct'].get('RANGING', 0):.2%}",
        f"  Idle sessions in DOWNTREND: {overlap['idle_regime_pct'].get('DOWNTREND', 0):.2%}",
        f"  Hypothesis verdict: {hypothesis}",
        "",
        "STOCK-LEVEL VCP OPPORTUNITY:",
        f"  Symbols tested                         : {vcp_summary['symbols_tested']}",
        f"  Constructive market sessions           : {vcp_summary['constructive_market_sessions']} ({vcp_summary['constructive_market_pct']:.2%})",
        f"  Days with >=1 VCP stock opportunity    : {vcp_summary['opportunity_days']} ({vcp_summary['opportunity_days_pct']:.2%})",
        f"  Opportunity days during constructive mkt: {vcp_summary['opportunity_days_during_constructive_market_pct']:.2%}",
        f"  Avg VCP opportunities / constructive day: {vcp_summary['avg_opportunities_per_constructive_session']:.2f}",
        f"  Symbols with at least one opportunity  : {vcp_summary['symbols_with_at_least_one_opportunity']}",
        f"  Viability verdict: {viability}",
        "",
        "------------------------------------------------------------",
        "DECISION:",
        f"  {decision}",
        "------------------------------------------------------------",
    ]
    return "\n".join(lines)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    proxy = _load_nifty50_daily()
    labels = _label_regimes(proxy)
    labels.to_csv(OUT / "daily_regime_labels.csv", index=False)
    streak_frame = _streaks(labels, proxy)
    _write_distribution(labels.copy(), streak_frame)
    viable = streak_frame.loc[streak_frame["viable_for_vcp"]].copy()
    viable[["streak_start", "streak_end", "duration_sessions", "nifty_return_during_streak", "viable_for_vcp"]].to_csv(OUT / "vcp_viability_windows.csv", index=False)
    _, overlap = _overlap(labels)
    _, vcp_summary = _stock_vcp_opportunities(labels)
    verdict = _verdict(labels, streak_frame, overlap, vcp_summary)
    (OUT / "SPRINT_2_1_VERDICT.txt").write_text(verdict, encoding="utf-8")
    print(verdict)


if __name__ == "__main__":
    main()
