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
    AliasesRepository,
    AliasesSource,
    CatalogRepository,
    CatalogSource,
    DecisionBackend,
    Embeddings,
    FactExtractor,
    LexicalIndex,
    SearchVectorsRepository,
    UnitOfWork,
    VectorIndex,
)
from app.usecase.model_checks import (
    CheckedDecisionBackend,
    CheckedEmbeddings,
    CheckedFactExtractor,
)
from app.usecase.search import GroupSearch, SearchSnapshot
from app.usecase.search_vectors import BuildSearchVectors


@dataclass(frozen=True)
class Repositories[U: UnitOfWork]:
    """Фабрики репозиториев от единицы работы `U`: SQLite берёт сессию из неё, in-memory —
    общее хранилище."""

    catalog: Callable[[U], CatalogRepository]
    aliases: Callable[[U], AliasesRepository] | None = None
    saved_vectors: Callable[[U], SearchVectorsRepository] | None = None


@dataclass(frozen=True)
class Usecases[U: UnitOfWork]:
    catalog_queries: Callable[[U], CatalogQueries]
    catalog_sync: Callable[[U], CatalogSync]
    group_search: Callable[[U], GroupSearch]
    build_search_vectors: Callable[[U], BuildSearchVectors] | None


def build_usecases[U: UnitOfWork](
    repositories: Repositories[U],
    *,
    catalog_source: CatalogSource,
    lexical: LexicalIndex | None = None,
    vector: VectorIndex | None = None,
    embeddings: Embeddings | None = None,
    aliases_source: AliasesSource | None = None,
) -> Usecases[U]:
    r = repositories
    vectors_factory = r.saved_vectors
    snapshot = SearchSnapshot()
    return Usecases(
        build_search_vectors=(
            lambda uow: BuildSearchVectors(uow, r.catalog(uow), vectors_factory(uow), embeddings)
        )
        if vectors_factory is not None and embeddings is not None
        else None,
        group_search=lambda uow: GroupSearch(
            uow,
            r.catalog(uow),
            snapshot,
            lexical,
            vector,
            embeddings,
            r.aliases(uow) if r.aliases is not None else None,
            r.saved_vectors(uow) if r.saved_vectors is not None else None,
        ),
        catalog_queries=lambda uow: CatalogQueries(uow, r.catalog(uow)),
        catalog_sync=lambda uow: CatalogSync(
            uow,
            r.catalog(uow),
            catalog_source,
            r.aliases(uow) if r.aliases is not None else None,
            aliases_source,
            r.saved_vectors(uow) if r.saved_vectors is not None else None,
        ),
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
