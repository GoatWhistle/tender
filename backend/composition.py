"""Общая проводка сценариев из портов (docs/adr/0001-layers-and-ports.md).

Точка сборки (`main.py`, тесты, скрипты замеров) только выбирает реализации портов и передаёт их
сюда; сценарии собираются здесь одинаково для всех. Сценарий живёт на единице работы: проводка
отдаёт фабрики сценариев от неё, репозитории приходят фабриками от неё же.

Пакет замеров `evals` отсюда не импортируется — это проверяет тест на импорты.
"""

from collections.abc import Callable
from dataclasses import dataclass

from app.usecase.catalog import CatalogQueries, CatalogSync
from app.usecase.interface import (
    CatalogRepository,
    CatalogSource,
    DecisionBackend,
    Embeddings,
    FactExtractor,
    UnitOfWork,
)
from app.usecase.model_checks import (
    CheckedDecisionBackend,
    CheckedEmbeddings,
    CheckedFactExtractor,
)


@dataclass(frozen=True)
class Repositories[U: UnitOfWork]:
    """Фабрики репозиториев от единицы работы `U`: SQLite берёт сессию из неё, in-memory —
    общее хранилище."""

    catalog: Callable[[U], CatalogRepository]


@dataclass(frozen=True)
class Usecases[U: UnitOfWork]:
    catalog_queries: Callable[[U], CatalogQueries]
    catalog_sync: Callable[[U], CatalogSync]


def build_usecases[U: UnitOfWork](
    repositories: Repositories[U], *, catalog_source: CatalogSource
) -> Usecases[U]:
    r = repositories
    return Usecases(
        catalog_queries=lambda uow: CatalogQueries(uow, r.catalog(uow)),
        catalog_sync=lambda uow: CatalogSync(uow, r.catalog(uow), catalog_source),
    )


# Модели: точка сборки выбирает реализацию порта, сценарии получают её только за общей
# проверкой ответа (`app.usecase.model_checks`). Заглушку вместо отсутствующей модели здесь не
# подставляют.


def checked_embeddings(embeddings: Embeddings) -> Embeddings:
    return CheckedEmbeddings(embeddings)


def checked_decision(decision: DecisionBackend) -> DecisionBackend:
    return CheckedDecisionBackend(decision)


def checked_extractor(extractor: FactExtractor) -> FactExtractor:
    return CheckedFactExtractor(extractor)
