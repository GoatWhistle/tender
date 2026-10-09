"""Сценарии справочника КТРУ: чтение позиций и синхронизация хранилища с источником.

Синхронизация идёт при старте бэкенда и из командной строки; она идемпотентна — повторный
запуск справочник не дублирует.
"""

from app.domain.catalog import Position
from app.domain.errors import CatalogEmpty, PositionNotFound
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

    def ready(self) -> int:
        """Число позиций; пустой справочник — `CatalogEmpty`: без него анализ не работает."""
        with self._uow:
            count = self._catalog.count()
        if count == 0:
            raise CatalogEmpty()
        return count


class CatalogSync:
    def __init__(self, uow: UnitOfWork, catalog: CatalogRepository, source: CatalogSource) -> None:
        self._uow = uow
        self._catalog = catalog
        self._source = source

    def run(self) -> int:
        """Кладёт справочник источника в хранилище; возвращает число позиций."""
        positions = self._source.load()
        with self._uow:
            self._catalog.replace(positions)
        return len(positions)
