"""Small in-memory cache for stable read-only API responses."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, time, timedelta
import os
from threading import Lock
from typing import Callable, Hashable, TypeVar
from zoneinfo import ZoneInfo


T = TypeVar("T")

_IST = ZoneInfo("Asia/Kolkata")
_CACHE: dict[Hashable, tuple[float, object]] = {}
_LOCK = Lock()


def _now_ts() -> float:
    return datetime.now(tz=_IST).timestamp()


def _seconds_until_ist_midnight() -> int:
    now = datetime.now(tz=_IST)
    tomorrow = now.date() + timedelta(days=1)
    midnight = datetime.combine(tomorrow, time.min, tzinfo=_IST)
    return max(60, int((midnight - now).total_seconds()))


def default_daily_ttl_seconds() -> int:
    configured = os.getenv("DAILY_READ_CACHE_TTL_SECONDS")
    if configured:
        try:
            return max(1, int(configured))
        except ValueError:
            pass
    return _seconds_until_ist_midnight()


def get_or_set(
    key: Hashable,
    producer: Callable[[], T],
    *,
    refresh: bool = False,
    ttl_seconds: int | None = None,
) -> T:
    """Return a cached value or compute one.

    The copy-on-read/write behavior prevents route code or JSON rendering from
    mutating the object stored in cache.
    """
    if os.getenv("DISABLE_DAILY_READ_CACHE", "").lower() in {"1", "true", "yes"}:
        return producer()

    now = _now_ts()
    with _LOCK:
        if refresh:
            _CACHE.pop(key, None)
        else:
            cached = _CACHE.get(key)
            if cached is not None:
                expires_at, payload = cached
                if expires_at > now:
                    return deepcopy(payload)  # type: ignore[return-value]
                _CACHE.pop(key, None)

    payload = producer()
    expires_at = now + (ttl_seconds if ttl_seconds is not None else default_daily_ttl_seconds())
    with _LOCK:
        _CACHE[key] = (expires_at, deepcopy(payload))
    return payload


def clear_cache() -> int:
    with _LOCK:
        count = len(_CACHE)
        _CACHE.clear()
    return count
