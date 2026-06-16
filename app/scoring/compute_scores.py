"""Swing and positional score computation and persistence.

Reads:
  - `features_daily`
  - `prices_daily`
  - `symbol_master`
  - `sector_daily`
  - `model_version`

Writes:
  - `daily_scores`

Does not:
  - Compute long-term scores
  - Ingest fundamentals
  - Generate recommendations or run backtests
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, timedelta
from pathlib import Path
import json
import math
from typing import Any, Iterable

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from db.models import DailyScores, FeaturesDaily, ModelVersion, PricesDaily, SectorDaily, SymbolMaster


@dataclass(frozen=True)
class ScoreGenerationReport:
    symbols_processed: int
    dates_processed: int
    rows_written: int
    failures: list[str]


def write_score_report(report: ScoreGenerationReport, output_path: str | Path) -> Path:
    path = Path(output_path)
    path.write_text(json.dumps(asdict(report), indent=2, sort_keys=True), encoding="utf-8")
    return path


def _num(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _is_eligible(features: dict[str, Any]) -> bool:
    eligible = features.get("is_eligible")
    if eligible is None:
        return True
    return bool(eligible)


def score_swing_adx(adx_14: Any, adx_prev: Any) -> int:
    adx = _num(adx_14)
    prev = _num(adx_prev)
    if adx is None:
        return 0
    if prev is not None:
        if adx >= 35 and adx > prev:
            return 20
        if adx >= 25 and adx > prev:
            return 14
        if adx >= 25 and adx <= prev:
            return 8
    if adx >= 20:
        return 4
    return 0


def score_swing_ema(close: Any, ema_5: Any, ema_13: Any, ema_20: Any) -> int:
    c = _num(close)
    e5 = _num(ema_5)
    e13 = _num(ema_13)
    e20 = _num(ema_20)
    if c is None:
        return 0
    if e5 is not None and e13 is not None and c > e5 and e5 > e13:
        return 10
    if e13 is not None and c > e13:
        return 6
    if e20 is not None and c > e20:
        return 3
    return 0


def score_swing_rsi(rsi_14: Any) -> int:
    rsi = _num(rsi_14)
    if rsi is None:
        return 0
    if 55 <= rsi <= 68:
        return 15
    if 50 <= rsi < 55:
        return 9
    if 68 < rsi <= 75:
        return 7
    if 45 <= rsi < 50:
        return 4
    if rsi > 75:
        return 2
    return 0


def score_swing_macd(macd_hist: Any, macd_hist_prev: Any) -> int:
    hist = _num(macd_hist)
    prev = _num(macd_hist_prev)
    if hist is None or prev is None:
        return 0
    if hist > 0 and hist > prev:
        return 10
    if hist > 0 and hist <= prev:
        return 5
    if hist < 0 and hist > prev:
        return 3
    return 0


def score_swing_stochastic(stoch_k: Any, stoch_d: Any) -> int:
    k = _num(stoch_k)
    d = _num(stoch_d)
    if k is None or d is None:
        return 0
    if k <= d:
        return 0
    if 50 <= k <= 80:
        return 5
    if k < 50:
        return 3
    return 1


def score_swing_volume(volume_ratio: Any) -> int:
    ratio = _num(volume_ratio)
    if ratio is None:
        return 0
    if ratio >= 3.0:
        return 20
    if ratio >= 2.0:
        return 15
    if ratio >= 1.5:
        return 10
    if ratio >= 1.2:
        return 5
    return 0


def score_swing_52w_high(pct_from_52w_high: Any) -> int:
    pct = _num(pct_from_52w_high)
    if pct is None:
        return 0
    if pct >= -2:
        return 6
    if pct >= -5:
        return 4
    if pct >= -10:
        return 2
    return 0


def score_swing_bollinger(bb_width: Any, bb_width_20avg: Any) -> int:
    width = _num(bb_width)
    avg = _num(bb_width_20avg)
    if width is None or avg is None:
        return 0
    if width < avg * 0.70:
        return 4
    if width < avg * 0.85:
        return 2
    return 0


def score_swing_rs_rank(rs_rank_pct: Any) -> int:
    rank = _num(rs_rank_pct)
    if rank is None:
        return 0
    if rank >= 90:
        return 10
    if rank >= 75:
        return 7
    if rank >= 60:
        return 4
    if rank >= 50:
        return 2
    return 0


def score_swing_v2_adx(adx_14: Any, adx_prev: Any) -> int:
    adx = _num(adx_14)
    prev = _num(adx_prev)
    if adx is None:
        return 0
    rising = prev is not None and adx > prev
    if adx >= 35 and rising:
        return 25
    if adx >= 30 and rising:
        return 21
    if adx >= 25:
        return 16 if rising else 12
    if adx >= 20:
        return 6
    return 0


def score_swing_v2_bb_absolute(bb_width: Any) -> int:
    width = _num(bb_width)
    if width is None:
        return 0
    if width >= 0.12:
        return 25
    if width >= 0.08:
        return 20
    if width >= 0.05:
        return 14
    if width >= 0.03:
        return 8
    return 3


def score_swing_v2_bb_relative(bb_width: Any, bb_width_20avg: Any) -> int:
    width = _num(bb_width)
    avg = _num(bb_width_20avg)
    if width is None or avg is None or avg == 0:
        return 0
    ratio = width / avg
    if ratio >= 1.5:
        return 15
    if ratio >= 1.2:
        return 11
    if ratio >= 1.0:
        return 7
    if ratio >= 0.85:
        return 3
    return 0


def score_swing_v2_volume(volume_ratio: Any) -> int:
    ratio = _num(volume_ratio)
    if ratio is None:
        return 0
    if ratio >= 3.0:
        return 15
    if ratio >= 2.0:
        return 12
    if ratio >= 1.5:
        return 8
    if ratio >= 1.2:
        return 4
    return 0


def score_swing_v2_sector(sector_3m_rank: Any) -> int:
    rank = _num(sector_3m_rank)
    if rank is None:
        return 0
    rank_int = int(rank)
    if rank_int == 1:
        return 10
    if rank_int == 2:
        return 8
    if rank_int == 3:
        return 6
    if rank_int in (4, 5):
        return 4
    if 6 <= rank_int <= 8:
        return 2
    return 0


def compute_swing_score(features: dict[str, Any]) -> float | None:
    if not _is_eligible(features):
        return None
    total = (
        score_swing_adx(features.get("adx_14"), features.get("adx_prev"))
        + score_swing_ema(
            features.get("close"),
            features.get("ema_5"),
            features.get("ema_13"),
            features.get("ema_20"),
        )
        + score_swing_rsi(features.get("rsi_14"))
        + score_swing_macd(features.get("macd_hist"), features.get("macd_hist_prev"))
        + score_swing_stochastic(features.get("stoch_k"), features.get("stoch_d"))
        + score_swing_volume(features.get("volume_ratio"))
        + score_swing_52w_high(features.get("pct_from_52w_high"))
        + score_swing_bollinger(features.get("bb_width"), features.get("bb_width_20avg"))
        + score_swing_rs_rank(features.get("rs_rank_pct"))
    )
    return float(total)


def compute_swing_v2_score(features: dict[str, Any], sector_3m_rank: Any = None) -> float | None:
    if not _is_eligible(features):
        return None
    total = (
        score_swing_v2_adx(features.get("adx_14"), features.get("adx_prev"))
        + score_swing_ema(
            features.get("close"),
            features.get("ema_5"),
            features.get("ema_13"),
            features.get("ema_20"),
        )
        + score_swing_v2_bb_absolute(features.get("bb_width"))
        + score_swing_v2_bb_relative(features.get("bb_width"), features.get("bb_width_20avg"))
        + score_swing_v2_volume(features.get("volume_ratio"))
        + score_swing_v2_sector(sector_3m_rank if sector_3m_rank is not None else features.get("sector_3m_rank"))
    )
    return float(total)


def compute_swing_v2_1_score(features: dict[str, Any], sector_3m_rank: Any = None) -> float | None:
    if not _is_eligible(features):
        return None

    close = _num(features.get("close"))
    ema_200 = _num(features.get("ema_200"))
    prior_20d_return = _num(features.get("prior_20d_return"))
    if close is None or ema_200 is None or ema_200 == 0 or prior_20d_return is None:
        return None

    ema200_extension = (close - ema_200) / ema_200
    if ema200_extension > 0.25 or prior_20d_return > 0.15:
        return None

    total = (
        score_swing_v2_adx(features.get("adx_14"), features.get("adx_prev"))
        + score_swing_v2_sector(sector_3m_rank if sector_3m_rank is not None else features.get("sector_3m_rank"))
    )
    return float(total / 35 * 100)


def score_positional_ema_stage(close: Any, ema_50: Any, ema_150: Any, ema_200: Any) -> int:
    c = _num(close)
    e50 = _num(ema_50)
    e150 = _num(ema_150)
    e200 = _num(ema_200)
    if c is None or e200 is None:
        return 0
    if c < e200:
        return 0
    if e50 is not None and e150 is not None and c > e50 and e50 > e150 and e150 > e200:
        return 25
    if e50 is not None and c > e50 and c > e200:
        return 16
    if c > e200:
        return 8
    return 0


def score_positional_adx(adx_14: Any, adx_prev: Any) -> int:
    adx = _num(adx_14)
    prev = _num(adx_prev)
    if adx is None:
        return 0
    if prev is not None and adx >= 30 and adx > prev:
        return 15
    if adx >= 25:
        return 9
    if adx >= 20:
        return 4
    return 0


def score_positional_rs_rank(rs_rank_pct: Any) -> int:
    rank = _num(rs_rank_pct)
    if rank is None:
        return 0
    if rank >= 85:
        return 18
    if rank >= 70:
        return 12
    if rank >= 55:
        return 6
    return 0


def score_positional_rs_nifty(rs_vs_nifty_60d: Any) -> int:
    rs = _num(rs_vs_nifty_60d)
    if rs is None:
        return 0
    if rs >= 1.20:
        return 12
    if rs >= 1.10:
        return 8
    if rs >= 1.00:
        return 4
    return 0


def score_positional_sector(sector_3m_rank: Any) -> int:
    rank = _num(sector_3m_rank)
    if rank is None:
        return 0
    rank_int = int(rank)
    if rank_int == 1:
        return 20
    if rank_int == 2:
        return 17
    if rank_int == 3:
        return 14
    if rank_int in (4, 5):
        return 10
    if 6 <= rank_int <= 8:
        return 5
    return 0


def score_positional_volume(volume_ratio: Any) -> int:
    ratio = _num(volume_ratio)
    if ratio is None:
        return 0
    if ratio >= 2.0:
        return 10
    if ratio >= 1.5:
        return 7
    if ratio >= 1.2:
        return 4
    return 0


def score_positional_v2_ema_stage(close: Any, ema_50: Any, ema_150: Any, ema_200: Any) -> int:
    c = _num(close)
    e50 = _num(ema_50)
    e150 = _num(ema_150)
    e200 = _num(ema_200)
    if c is None or e200 is None or c < e200:
        return 0
    if e50 is not None and e150 is not None and c > e50 and e50 > e150 and e150 > e200:
        return 22
    if e50 is not None and c > e50 and c > e200:
        return 14
    return 7


def score_positional_v2_adx(adx_14: Any, adx_prev: Any) -> int:
    adx = _num(adx_14)
    prev = _num(adx_prev)
    if adx is None:
        return 0
    rising = prev is not None and adx > prev
    if adx >= 35 and rising:
        return 18
    if adx >= 30 and rising:
        return 15
    if adx >= 25:
        return 11 if rising else 8
    if adx >= 20:
        return 4
    return 0


def score_positional_v2_sector(sector_3m_rank: Any) -> int:
    rank = _num(sector_3m_rank)
    if rank is None:
        return 0
    rank_int = int(rank)
    if rank_int == 1:
        return 30
    if rank_int == 2:
        return 25
    if rank_int == 3:
        return 21
    if rank_int in (4, 5):
        return 15
    if 6 <= rank_int <= 8:
        return 8
    return 0


def score_positional_v2_bb_width(bb_width: Any, bb_width_20avg: Any) -> int:
    absolute = score_swing_v2_bb_absolute(bb_width)
    relative = score_swing_v2_bb_relative(bb_width, bb_width_20avg)
    return min(15, round((absolute / 25 * 9) + (relative / 15 * 6)))


def score_positional_v2_eligibility(features: dict[str, Any]) -> int:
    return 5 if _is_eligible(features) else 0


def compute_position_score(features: dict[str, Any], sector_3m_rank: Any = None) -> float | None:
    if not _is_eligible(features):
        return None
    total = (
        score_positional_ema_stage(
            features.get("close"),
            features.get("ema_50"),
            features.get("ema_150"),
            features.get("ema_200"),
        )
        + score_positional_adx(features.get("adx_14"), features.get("adx_prev"))
        + score_positional_rs_rank(features.get("rs_rank_pct"))
        + score_positional_rs_nifty(features.get("rs_vs_nifty_60d"))
        + score_positional_sector(sector_3m_rank if sector_3m_rank is not None else features.get("sector_3m_rank"))
        + score_positional_volume(features.get("volume_ratio"))
    )
    return float(total)


def compute_position_v2_score(features: dict[str, Any], sector_3m_rank: Any = None) -> float | None:
    if not _is_eligible(features):
        return None
    total = (
        score_positional_v2_ema_stage(
            features.get("close"),
            features.get("ema_50"),
            features.get("ema_150"),
            features.get("ema_200"),
        )
        + score_positional_v2_adx(features.get("adx_14"), features.get("adx_prev"))
        + score_positional_v2_sector(sector_3m_rank if sector_3m_rank is not None else features.get("sector_3m_rank"))
        + score_positional_v2_bb_width(features.get("bb_width"), features.get("bb_width_20avg"))
        + score_positional_volume(features.get("volume_ratio"))
        + score_positional_v2_eligibility(features)
    )
    return float(total)


class ScoreComputer:
    def __init__(self, session_factory):
        self.session_factory = session_factory

    def generate(
        self,
        start_date: date | None = None,
        end_date: date | None = None,
        model_version_id: int | None = None,
    ) -> ScoreGenerationReport:
        failures: list[str] = []
        rows_written = 0
        dates_processed = 0
        symbols_processed = 0

        with self.session_factory() as session:
            if model_version_id is None:
                model_version_id = session.execute(
                    select(ModelVersion.version_id).where(ModelVersion.is_active.is_(True)).limit(1)
                ).scalar_one_or_none()

            if end_date is None:
                end_date = session.execute(select(FeaturesDaily.date).order_by(FeaturesDaily.date.desc())).scalars().first()
            if start_date is None:
                existing_latest = session.execute(select(DailyScores.date).order_by(DailyScores.date.desc())).scalars().first()
                if existing_latest is not None:
                    start_date = existing_latest + timedelta(days=1)
                else:
                    start_date = session.execute(select(FeaturesDaily.date).order_by(FeaturesDaily.date.asc())).scalars().first()

            if start_date is None or end_date is None:
                return ScoreGenerationReport(0, 0, 0, failures)

            sector_ranks = self._load_sector_ranks(session, start_date, end_date)
            prior_20d_returns = self._load_prior_20d_returns(session, start_date, end_date)

            for current_date in self._date_range(start_date, end_date):
                feature_rows = session.execute(
                    select(FeaturesDaily, PricesDaily.close)
                    .join(PricesDaily, (FeaturesDaily.symbol == PricesDaily.symbol) & (FeaturesDaily.date == PricesDaily.date))
                    .where(FeaturesDaily.date == current_date)
                ).all()
                if not feature_rows:
                    continue

                date_symbols = 0
                for feature_row, close in feature_rows:
                    try:
                        symbol_map = dict(
                            session.execute(
                                select(SymbolMaster.symbol, SymbolMaster.sector).where(
                                    SymbolMaster.symbol == feature_row.symbol
                                )
                            ).all()
                        )
                        sector = symbol_map.get(feature_row.symbol) or feature_row.sector
                        sector_3m_rank = sector_ranks.get((current_date, sector))
                        features = self._feature_row_to_dict(feature_row, close)
                        swing_score = compute_swing_score(features)
                        position_score = compute_position_score(features, sector_3m_rank)
                        swing_v2_score = compute_swing_v2_score(features, sector_3m_rank)
                        features["prior_20d_return"] = prior_20d_returns.get((feature_row.symbol, current_date))
                        swing_v2_1_score = compute_swing_v2_1_score(features, sector_3m_rank)
                        position_v2_score = compute_position_v2_score(features, sector_3m_rank)
                        rows_written += self._upsert_score(
                            session,
                            symbol=feature_row.symbol,
                            score_date=current_date,
                            swing_score=swing_score,
                            position_score=position_score,
                            swing_v2_score=swing_v2_score,
                            swing_v2_1_score=swing_v2_1_score,
                            position_v2_score=position_v2_score,
                            model_version_id=model_version_id,
                        )
                        date_symbols += 1
                    except Exception as exc:  # pragma: no cover - surfaced in report
                        failures.append(f"{current_date}/{feature_row.symbol}: {exc}")
                if date_symbols:
                    dates_processed += 1
                    symbols_processed += date_symbols
            session.commit()

        return ScoreGenerationReport(
            symbols_processed=symbols_processed,
            dates_processed=dates_processed,
            rows_written=rows_written,
            failures=failures,
        )

    def _feature_row_to_dict(self, row: FeaturesDaily, close: Any) -> dict[str, Any]:
        return {
            "is_eligible": row.is_eligible,
            "close": close,
            "adx_14": row.adx_14,
            "adx_prev": row.adx_prev,
            "ema_5": row.ema_5,
            "ema_13": row.ema_13,
            "ema_20": row.ema_20,
            "ema_50": row.ema_50,
            "ema_150": row.ema_150,
            "ema_200": row.ema_200,
            "rsi_14": row.rsi_14,
            "macd_hist": row.macd_hist,
            "macd_hist_prev": row.macd_hist_prev,
            "stoch_k": row.stoch_k,
            "stoch_d": row.stoch_d,
            "volume_ratio": row.volume_ratio,
            "pct_from_52w_high": row.pct_from_52w_high,
            "bb_width": row.bb_width,
            "bb_width_20avg": row.bb_width_20avg,
            "rs_rank_pct": row.rs_rank_pct,
            "rs_vs_nifty_60d": row.rs_vs_nifty_60d,
        }

    def _load_sector_ranks(self, session, start_date: date, end_date: date) -> dict[tuple[date, str | None], int | None]:
        rows = session.execute(
            select(SectorDaily.date, SectorDaily.sector, SectorDaily.rank_3m).where(
                SectorDaily.date.between(start_date, end_date)
            )
        ).all()
        return {(row[0], row[1]): row[2] for row in rows}

    def _load_prior_20d_returns(self, session, start_date: date, end_date: date) -> dict[tuple[str, date], float]:
        load_start = start_date - timedelta(days=80)
        rows = session.execute(
            select(PricesDaily.symbol, PricesDaily.date, PricesDaily.close)
            .where(PricesDaily.date.between(load_start, end_date))
            .order_by(PricesDaily.symbol.asc(), PricesDaily.date.asc())
        ).all()

        by_symbol: dict[str, list[tuple[date, float]]] = {}
        for symbol, price_date, close in rows:
            if close is None:
                continue
            by_symbol.setdefault(symbol, []).append((price_date, float(close)))

        result: dict[tuple[str, date], float] = {}
        for symbol, values in by_symbol.items():
            for index, (price_date, close) in enumerate(values):
                if price_date < start_date or index < 20:
                    continue
                past_close = values[index - 20][1]
                if past_close == 0:
                    continue
                result[(symbol, price_date)] = (close / past_close) - 1
        return result

    def _upsert_score(
        self,
        session,
        *,
        symbol: str,
        score_date: date,
        swing_score: float | None,
        position_score: float | None,
        swing_v2_score: float | None,
        swing_v2_1_score: float | None,
        position_v2_score: float | None,
        model_version_id: int | None,
    ) -> int:
        payload = {
            "symbol": symbol,
            "date": score_date,
            "swing_score": swing_score,
            "position_score": position_score,
            "swing_v2_score": swing_v2_score,
            "swing_v2_1_score": swing_v2_1_score,
            "position_v2_score": position_v2_score,
            "model_version_id": model_version_id,
        }
        existing = session.execute(
            select(DailyScores).where(DailyScores.symbol == symbol, DailyScores.date == score_date)
        ).scalar_one_or_none()
        if existing is not None:
            existing.swing_v2_score = swing_v2_score
            existing.swing_v2_1_score = swing_v2_1_score
            existing.position_v2_score = position_v2_score
            return 1

        dialect_name = session.bind.dialect.name if session.bind else "sqlite"
        insert_stmt = DailyScores.__table__.insert().values(**payload)
        if dialect_name == "postgresql":
            insert_stmt = pg_insert(DailyScores.__table__).values(**payload).on_conflict_do_update(
                index_elements=["symbol", "date"],
                set_=payload,
            )
        elif dialect_name == "sqlite":
            insert_stmt = sqlite_insert(DailyScores.__table__).values(**payload).prefix_with("OR IGNORE")
        result = session.execute(insert_stmt)
        return int(getattr(result, "rowcount", 1) or 0)

    def _date_range(self, start_date: date, end_date: date) -> Iterable[date]:
        current = start_date
        while current <= end_date:
            yield current
            current += timedelta(days=1)
