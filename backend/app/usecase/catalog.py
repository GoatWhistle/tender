"""Сценарии справочника КТРУ: чтение позиций и синхронизация хранилища с источником.

Синхронизация идёт при старте бэкенда и из командной строки; она идемпотентна — повторный
запуск справочник не дублирует. Вместе со справочником она кладёт словарь синонимов групп.
"""

from dataclasses import dataclass

from app.domain.catalog import Group, Position, outside_tree
from app.domain.errors import CatalogEmpty, GroupNotFound, PositionNotFound
from app.domain.search import Alias
from app.usecase.interface import (
    AliasRepository,
    AliasSource,
    CatalogRepository,
    CatalogSource,
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
    # Синонимы, чьей группы нет в справочнике: хранятся, но поиск их не находит.
    orphan_aliases: tuple[Alias, ...] = ()


class CatalogSync:
    def __init__(
        self,
        uow: UnitOfWork,
        catalog: CatalogRepository,
        source: CatalogSource,
        aliases: AliasRepository,
        alias_source: AliasSource,
    ) -> None:
        self._uow = uow
        self._catalog = catalog
        self._source = source
        self._aliases = aliases
        self._alias_source = alias_source

    def run(self) -> SyncReport:
        """Кладёт справочник и словарь синонимов источников в хранилище."""
        positions = self._source.load()
        aliases = self._alias_source.load()
        with self._uow:
            self._catalog.replace(positions)
            self._aliases.replace(aliases)
        groups = {p.code for p in positions if p.is_group}
        return SyncReport(
            len(positions),
            tuple(outside_tree(positions)),
            len(aliases),
            tuple(a for a in aliases if a.group_code not in groups),
        )
