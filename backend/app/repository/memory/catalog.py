"""Справочник КТРУ в памяти — реализация порта `CatalogRepository`."""

from collections.abc import Iterable

from app.domain.catalog import Position
from app.repository.memory.unit_of_work import MemoryStore


class MemoryCatalog:
    def __init__(self, store: MemoryStore) -> None:
        self._store = store

    def _positions(self) -> dict[str, Position]:
        return self._store.collection("positions")  # type: ignore[return-value]

    def position(self, code: str) -> Position | None:
        return self._positions().get(code)

    def positions(self, category: str | None = None) -> list[Position]:
        return sorted(
            (p for p in self._positions().values() if category in (None, p.category)),
            key=lambda p: p.code,
        )

    def count(self) -> int:
        return len(self._positions())

    def replace(self, positions: Iterable[Position]) -> None:
        records = self._positions()
        records.clear()
        records.update((p.code, p) for p in positions)
