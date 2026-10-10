"""Общая проводка сценариев из портов (docs/adr/0001-layers-and-ports.md).

Точка сборки (`main.py`, тесты, скрипты замеров) только выбирает реализации портов и передаёт их
сюда; сценарии собираются здесь одинаково для всех. Сценарий живёт на единице работы: проводка
отдаёт фабрики сценариев от неё, репозитории приходят фабриками от неё же.

Пакет замеров `evals` отсюда не импортируется — это проверяет тест на импорты.
"""

from collections.abc import Callable
from dataclasses import dataclass

from app.domain.enum_mapping import AutoAcceptance
from app.usecase.catalog import CatalogQueries, CatalogSync
from app.usecase.diagnostics import Diagnostics
from app.usecase.enum_mapping import EnumMapper
from app.usecase.extraction import VerificationPolicy, VerifiedExtractor
from app.usecase.interface import (
    AliasesRepository,
    AliasesSource,
    CatalogRepository,
    CatalogSource,
    DecisionBackend,
    Embeddings,
    EnumMatcher,
    FactExtractor,
    GroupSearcher,
    LexicalIndex,
    ModelFactExtractor,
    SearchVectorsRepository,
    SessionsRepository,
    SpellingService,
    UnitOfWork,
    ValueAliases,
    VectorIndex,
)
from app.usecase.model_checks import (
    CheckedDecisionBackend,
    CheckedEmbeddings,
    CheckedFactExtractor,
)
from app.usecase.search import GroupSearch, SearchSnapshot
from app.usecase.search_vectors import BuildSearchVectors
from app.usecase.sessions import Sessions


@dataclass(frozen=True)
class Repositories[U: UnitOfWork]:
    """Фабрики репозиториев от единицы работы `U`: SQLite берёт сессию из неё, in-memory —
    общее хранилище."""

    catalog: Callable[[U], CatalogRepository]
    aliases: Callable[[U], AliasesRepository] | None = None
    saved_vectors: Callable[[U], SearchVectorsRepository] | None = None
    sessions: Callable[[U], SessionsRepository] | None = None


@dataclass(frozen=True)
class Usecases[U: UnitOfWork]:
    catalog_queries: Callable[[U], CatalogQueries]
    catalog_sync: Callable[[U], CatalogSync]
    group_search: Callable[[U], GroupSearch]
    build_search_vectors: Callable[[U], BuildSearchVectors] | None
    sessions: Callable[[U], Sessions] | None


def build_usecases[U: UnitOfWork](
    repositories: Repositories[U],
    *,
    catalog_source: CatalogSource,
    lexical: LexicalIndex | None = None,
    vector: VectorIndex | None = None,
    embeddings: Embeddings | None = None,
    aliases_source: AliasesSource | None = None,
    searcher: GroupSearcher | None = None,
    fact_extractor: FactExtractor | None = None,
    decision: DecisionBackend | None = None,
    enum_policy: AutoAcceptance | None = None,
    model_extractor: ModelFactExtractor | None = None,
    verification_policy: VerificationPolicy | None = None,
    enum_matcher: EnumMatcher | None = None,
    value_aliases: ValueAliases | None = None,
    spelling: SpellingService | None = None,
    min_similarity: float = 0.0,
) -> Usecases[U]:
    if model_extractor is not None and decision is None:
        raise ValueError("Извлечение требует DecisionBackend для проверки фактов")
    r = repositories
    vectors_factory = r.saved_vectors
    snapshot = SearchSnapshot()
    sessions_factory = r.sessions
    if sessions_factory is not None and fact_extractor is None:
        raise ValueError("Для сессий нужен FactExtractor")

    def group_search(uow: U) -> GroupSearch:
        return GroupSearch(
            uow,
            r.catalog(uow),
            snapshot,
            lexical,
            vector,
            embeddings,
            r.aliases(uow) if r.aliases else None,
            r.saved_vectors(uow) if r.saved_vectors else None,
        )

    return Usecases(
        sessions=(
            lambda uow: Sessions(
                uow,
                sessions_factory(uow),
                searcher or group_search(uow),
                r.catalog(uow),
                fact_extractor,
                enum_mapper=EnumMapper(checked_decision(decision), enum_policy or AutoAcceptance())
                if decision
                else None,
                diagnostics=Diagnostics(enum_matcher, value_aliases)
                if enum_matcher is not None
                else None,
                spelling=spelling,
                verified_extractor=VerifiedExtractor(
                    checked_extractor(model_extractor),
                    checked_decision(decision),
                    verification_policy or VerificationPolicy(),
                )
                if model_extractor and decision
                else None,
                decision=checked_decision(decision) if decision else None,
                min_similarity=min_similarity,
            )
        )
        if sessions_factory and fact_extractor is not None
        else None,
        build_search_vectors=(
            lambda uow: BuildSearchVectors(uow, r.catalog(uow), vectors_factory(uow), embeddings)
        )
        if vectors_factory is not None and embeddings is not None
        else None,
        group_search=group_search,
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


def checked_extractor(extractor: ModelFactExtractor) -> ModelFactExtractor:
    return CheckedFactExtractor(extractor)
