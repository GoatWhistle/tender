"""Порты — всё, что можно заменить другой реализацией, даже если она сейчас одна
(docs/adr/0001-layers-and-ports.md). На входе и выходе только типы из `app.domain`: без ORM,
Pydantic и типов библиотек. Реализации — в `app.adapter` и `app.repository`.
"""

from collections.abc import Iterable, Sequence
from types import TracebackType
from typing import Protocol, Self

from app.domain.aliases import Alias
from app.domain.catalog import Group, Position
from app.domain.diagnostics import SpellingSuggestion, ValueAlias
from app.domain.facts import Fact
from app.domain.inference import (
    ChoiceBatch,
    ChoiceQuestion,
    Claim,
    ClaimBatch,
    EmbeddingBatch,
    Extraction,
    ExtractionRequest,
    ModelHealth,
    Vector,
)
from app.domain.search import RankedGroup, SearchResult
from app.domain.search_vectors import SearchVectors
from app.domain.sessions import Message, Revision, SessionState


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

    def groups(self, category: str | None = None) -> list[Position]:
        """Группы КТРУ (`Position.is_group`) по коду; с `category` — только этой категории."""
        ...

    def children(self, code: str) -> list[Position]:
        """Позиции, у которых родитель — `code`, по коду."""
        ...

    def count(self) -> int: ...

    def replace(self, positions: Iterable[Position]) -> None:
        """Справочник целиком заменяется переданным: повторный вызов с тем же набором ничего не
        меняет."""
        ...


class Embeddings(Protocol):
    """Тексты → векторы размерности `dimension` единичной длины: нормализация — часть контракта,
    вызывающий её не делает. Сейчас — заглушка `app.adapter.stub`."""

    @property
    def dimension(self) -> int: ...

    def embed_queries(self, texts: Sequence[str]) -> EmbeddingBatch:
        """По вектору на текст, в порядке текстов."""
        ...

    def embed_documents(self, texts: Sequence[str]) -> EmbeddingBatch:
        """Документы без инструкции запроса; по вектору на текст."""
        ...

    def health(self) -> ModelHealth: ...


class DecisionBackend(Protocol):
    """Decision-модель (раздел 7.4 плана): выбор из вариантов и проверка утверждений (раздел
    8.5). Отвечает распределениями, порог принятия — в сценарии. Сейчас — заглушка
    `app.adapter.stub`."""

    def choose(self, context: str, questions: Sequence[ChoiceQuestion]) -> ChoiceBatch:
        """По ответу на каждый вопрос пакета: распределение по `option_ids`, выбор или отказ."""
        ...

    def verify(self, context: str, claims: Sequence[Claim]) -> ClaimBatch:
        """По каждому утверждению — распределение по `Verdict`: следует ли оно из контекста."""
        ...

    def health(self) -> ModelHealth: ...


class ModelFactExtractor(Protocol):
    """Генеративный извлекатель фактов (разделы 8.2–8.3 плана): ищет значения только
    переданных характеристик в переданных сообщениях. Сейчас — заглушка `app.adapter.stub`."""

    def extract(self, request: ExtractionRequest) -> Extraction: ...

    def health(self) -> ModelHealth: ...


class LexicalIndex(Protocol):
    def build(self, groups: Sequence[Position]) -> None: ...

    def rank(self, description: str, category: str | None = None) -> list[RankedGroup]: ...


class VectorIndex(Protocol):
    def build(self, groups: Sequence[Position], saved: SearchVectors | None = None) -> None: ...

    def rank(self, query: Vector, category: str | None = None) -> list[RankedGroup]: ...


class AliasesSource(Protocol):
    def load(self) -> list[Alias]: ...


class AliasesRepository(Protocol):
    def all(self) -> list[Alias]: ...

    def replace(self, aliases: Iterable[Alias]) -> None: ...


class SearchVectorsRepository(Protocol):
    def load(self) -> SearchVectors | None: ...

    def replace(self, snapshot: SearchVectors | None) -> None: ...


class SessionsRepository(Protocol):
    """Снимки ревизий; запись только внутри единицы работы.

    lock=True сериализует обновления до чтения снимка и проверки ключа.
    """

    def latest(self, session_id: str, *, lock: bool = False) -> SessionState | None: ...

    def replay(self, session_id: str, key: str) -> Revision | None: ...

    def save(self, revision: Revision) -> None: ...


class GroupSearcher(Protocol):
    def run(
        self, description: str, category: str | None = None, limit: int = 10
    ) -> SearchResult: ...


class FactExtractor(Protocol):
    """Извлечение фактов по всем сообщениям в контексте конечных позиций группы."""

    def extract(
        self, messages: Sequence[Message], group: Group
    ) -> tuple[tuple[Fact, ...], tuple[str, ...]]: ...


class EnumMatcher(Protocol):
    def rank(self, value: str, allowed: Sequence[str]) -> tuple[tuple[str, int], ...]: ...


class SpellingService(Protocol):
    def suggest(self, message: Message) -> tuple[SpellingSuggestion, ...]: ...


class ValueAliases(Protocol):
    def all(self) -> tuple[ValueAlias, ...]: ...
