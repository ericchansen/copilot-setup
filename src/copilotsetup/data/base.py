"""Base protocols for data providers.

Split into ``ReadProvider`` (all tabs) and ``WriteProvider`` (mutable tabs)
so that read-only tabs never need a ``save()`` stub.
"""

from __future__ import annotations

from typing import Protocol, TypeVar, runtime_checkable

T = TypeVar("T")


@runtime_checkable
class ReadProvider(Protocol[T]):
    """Contract for any data source that can load items."""

    def load(self) -> list[T]:
        """Return all items.  Must never raise — return ``[]`` on error."""
        ...


@runtime_checkable
class WriteProvider(ReadProvider[T], Protocol[T]):
    """Extended contract for data sources that also support persistence."""

    def save(self, items: list[T]) -> None:
        """Persist *items* back to the underlying store."""
        ...
