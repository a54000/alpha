"""Lightweight dependency injection hooks.

Reads:
  - Constructor callables registered by the application

Writes:
  - In-memory provider registry

Does not:
  - Build concrete ingestion, scoring, or backtest implementations
  - Touch the database
"""

from __future__ import annotations

from collections.abc import Callable


class Container:
    """Minimal service registry for application bootstrap."""

    def __init__(self) -> None:
        self._providers: dict[str, Callable[[], object]] = {}

    def register(self, name: str, provider: Callable[[], object]) -> None:
        self._providers[name] = provider

    def resolve(self, name: str) -> object:
        return self._providers[name]()

    def has(self, name: str) -> bool:
        return name in self._providers

