"""Порты — всё, что можно заменить другой реализацией, даже если она сейчас одна
(docs/adr/0001-layers-and-ports.md). На входе и выходе только типы из `app.domain`: без ORM,
Pydantic и типов библиотек. Реализации — в `app.adapter` и `app.repository`.
"""

from collections.abc import Iterable
from types import TracebackType
from typing import Protocol, Self

from app.domain.catalog import Position


class UnitOfWork(Protocol):
    """Единица работы — граница транзакции: блок `with uow:` в сценарии.

    Выход из блока без исключения фиксирует всё записанное в нём, с исключением — откатывает и
    пробрасывает исключение дальше. Вложенный вход — ошибка. Кроме единицы работы изменения не
    фиксирует никто. Сейчас — SQLite (`app.repository.unit_of_work`) и in-memory для тестов
    (`app.repository.memory`).
    """

    def __enter__(self) -> Self:
        """Начало блока; вложенный вход — `RuntimeError`."""
        ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None: ...


class RequestUnitOfWork(UnitOfWork, Protocol):
    """Единица работы одного HTTP-запроса: блоки сценариев идут в ней по очереди. Сейчас —
    SQLite (`app.repository.unit_of_work`)."""

    def close(self) -> None:
        """Конец запроса: соединение возвращается в пул."""
        ...


class CatalogSource(Protocol):
    """Откуда берётся справочник КТРУ. Сейчас — XML-выгрузка ЕИС (`app.adapter.ktru_xml`) и
    JSON-снимок `var/ktru.json` (`app.adapter.ktru_json`)."""

    def load(self) -> list[Position]: ...


class CatalogRepository(Protocol):
    """Справочник КТРУ в хранилище. Пишет только внутри единицы работы и сам не фиксирует.
    Сейчас — SQLite (`app.repository.catalog`) и in-memory (`app.repository.memory.catalog`)."""

    def position(self, code: str) -> Position | None: ...

    def positions(self, category: str | None = None) -> list[Position]:
        """По коду; с `category` — только позиции этой категории выгрузки."""
        ...

    def count(self) -> int: ...

    def replace(self, positions: Iterable[Position]) -> None:
        """Справочник целиком заменяется переданным: повторный вызов с тем же набором ничего не
        меняет."""
        ...
