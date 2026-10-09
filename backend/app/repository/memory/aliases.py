"""Словарь синонимов в памяти — реализация порта `AliasRepository`."""

from collections.abc import Iterable

from app.domain.search import Alias
from app.repository.memory.unit_of_work import MemoryStore


class MemoryAliases:
    def __init__(self, store: MemoryStore) -> None:
        self._store = store

    def _aliases(self) -> dict[int, Alias]:
        return self._store.collection("aliases")  # type: ignore[return-value]

    def aliases(self) -> list[Alias]:
        records = self._aliases()
        return [records[i] for i in sorted(records)]

    def replace(self, aliases: Iterable[Alias]) -> None:
        records = self._aliases()
        records.clear()
        records.update(enumerate(aliases))
