"""Сценарии справочника КТРУ: чтение позиций и синхронизация хранилища с источником.

Синхронизация идёт при старте бэкенда и из командной строки; она идемпотентна — повторный
запуск справочник не дублирует.
"""

from dataclasses import dataclass

from app.domain.catalog import Group, Position, outside_tree
from app.domain.errors import CatalogEmpty, GroupNotFound, PositionNotFound
from app.usecase.interface import CatalogRepository, CatalogSource, UnitOfWork


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


class CatalogSync:
    def __init__(self, uow: UnitOfWork, catalog: CatalogRepository, source: CatalogSource) -> None:
        self._uow = uow
        self._catalog = catalog
        self._source = source

    def run(self) -> SyncReport:
        """Кладёт справочник источника в хранилище."""
        positions = self._source.load()
        with self._uow:
            self._catalog.replace(positions)
        return SyncReport(len(positions), tuple(outside_tree(positions)))
