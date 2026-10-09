"""Сценарии справочника КТРУ: чтение позиций и синхронизация хранилища с источником.

Синхронизация идёт при старте бэкенда и из командной строки; она идемпотентна — повторный
запуск справочник не дублирует.
"""

from dataclasses import dataclass

from app.domain.aliases import Alias
from app.domain.catalog import Group, Position, outside_tree
from app.domain.errors import CatalogEmpty, GroupNotFound, PositionNotFound
from app.usecase.interface import (
    AliasesRepository,
    AliasesSource,
    CatalogRepository,
    CatalogSource,
    SearchVectorsRepository,
    UnitOfWork,
)


class CatalogQueries:
    def __init__(self, uow: UnitOfWork, catalog: CatalogRepository) -> None:
        self._uow = uow
        self._catalog = catalog

    def position(self, code: str) -> Position:
        with self._uow:
            found = self._catalog.position(code)
        if found is None:
            raise PositionNotFound()
        return found

    def positions(self, category: str | None = None) -> list[Position]:
        with self._uow:
            return self._catalog.positions(category)

    def groups(self, category: str | None = None) -> list[Position]:
        with self._uow:
            return self._catalog.groups(category)

    def group(self, code: str) -> Group:
        """Группа с конечными позициями; позиция, которая не группа, — `GroupNotFound`."""
        with self._uow:
            found = self._catalog.position(code)
            children = self._catalog.children(code)
        if found is None or not found.is_group:
            raise GroupNotFound()
        return Group.of(found, children)

    def ready(self) -> int:
        """Число позиций; пустой справочник — `CatalogEmpty`: без него анализ не работает."""
        with self._uow:
            count = self._catalog.count()
        if count == 0:
            raise CatalogEmpty()
        return count


@dataclass(frozen=True)
class SyncReport:
    positions: int
    # Позиции, чья группа не найдена: родитель отсутствует в справочнике или сам не группа.
    # Они хранятся, но ни в одну группу не входят.
    outside_tree: tuple[Position, ...] = ()
    aliases: int = 0
    invalid_aliases: tuple[Alias, ...] = ()


class CatalogSync:
    def __init__(
        self,
        uow: UnitOfWork,
        catalog: CatalogRepository,
        source: CatalogSource,
        aliases: AliasesRepository | None = None,
        aliases_source: AliasesSource | None = None,
        saved_vectors: SearchVectorsRepository | None = None,
    ) -> None:
        self._uow = uow
        self._catalog = catalog
        self._source = source
        self._aliases = aliases
        self._aliases_source = aliases_source
        self._saved_vectors = saved_vectors

    def run(self) -> SyncReport:
        """Кладёт справочник источника в хранилище."""
        positions = self._source.load()
        aliases = self._aliases_source.load() if self._aliases_source is not None else []
        groups = {p.code for p in positions if p.is_group}
        valid = [a for a in aliases if a.group_code in groups]
        invalid = tuple(a for a in aliases if a.group_code not in groups)
        with self._uow:
            if self._saved_vectors is not None:
                self._saved_vectors.replace(None)
            if self._aliases is not None:
                self._aliases.replace([])
            self._catalog.replace(positions)
            if self._aliases is not None:
                self._aliases.replace(valid)
        return SyncReport(len(positions), tuple(outside_tree(positions)), len(valid), invalid)
