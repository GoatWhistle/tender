"""Словарь синонимов в памяти."""

from collections.abc import Iterable

from app.domain.aliases import Alias
from app.repository.memory.unit_of_work import MemoryStore


class MemoryAliases:
    def __init__(self, store: MemoryStore) -> None:
        self._store = store

    def all(self) -> list[Alias]:
        return sorted(
            self._store.collection("aliases").values(), key=lambda a: (a.group_code, a.alias)
        )

    def replace(self, aliases: Iterable[Alias]) -> None:
        records = self._store.collection("aliases")
        records.clear()
        records.update(((a.group_code, a.alias), a) for a in aliases)
