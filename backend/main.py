"""Сборка прода — вручную, без DI-контейнера (docs/adr/0001-layers-and-ports.md): здесь только
выбор реализаций портов, сценарии из них собирает общая проводка `composition`.

На уровне модуля только определения функций: объект приложения строит
`uvicorn --factory main:create_app`, поэтому импорт `main` не читает конфиг и не открывает базу.
Новый роутер подключается в `create_app`. Синхронизация справочника — `sync_catalog`: её вызывают
и старт контейнера, и командная строка (`python -c 'import main; main.sync_catalog()'`).
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, closing

from fastapi import FastAPI
from sqlalchemy.orm import Session, sessionmaker

from app.adapter.aliases import CsvAliasesSource
from app.adapter.decision import OpenJevDecision
from app.adapter.embeddings import OpenAIEmbeddings
from app.adapter.enum_similarity import DamerauMatcher
from app.adapter.extractor import QwenExtractor
from app.adapter.facts import DeterministicFactExtractor
from app.adapter.ktru_xml import XmlKtruSource
from app.adapter.search import MatrixIndex, TfidfIndex
from app.adapter.spelling import QwenSpelling, UnconfiguredSpelling
from app.adapter.value_aliases import ReviewedValueAliases
from app.controller.catalog import groups_router
from app.controller.catalog import router as catalog_router
from app.controller.errors import install_error_handlers
from app.controller.health import router as health_router
from app.controller.search import router as search_router
from app.controller.sessions import router as sessions_router
from app.domain.enum_mapping import AutoAcceptance
from app.repository.aliases import SqlAliases
from app.repository.catalog import SqlCatalog
from app.repository.database import create_db_engine
from app.repository.search_vectors import SqlSearchVectors
from app.repository.sessions import SqlSessions
from app.repository.unit_of_work import SqlUnitOfWork
from app.usecase.catalog import SyncReport
from app.usecase.extraction import VerificationPolicy
from app.usecase.interface import CatalogSource, Embeddings
from composition import Repositories, Usecases, build_usecases, checked_embeddings
from settings import Settings


def sql_repositories() -> Repositories[SqlUnitOfWork]:
    return Repositories[SqlUnitOfWork](
        catalog=lambda uow: SqlCatalog(uow.session),
        sessions=lambda uow: SqlSessions(uow.session),
        aliases=lambda uow: SqlAliases(uow.session),
        saved_vectors=lambda uow: SqlSearchVectors(uow.session),
    )


def production_usecases(
    settings: Settings,
    catalog_source: CatalogSource | None = None,
    embeddings: Embeddings | None = None,
) -> Usecases[SqlUnitOfWork]:
    embeddings = checked_embeddings(embeddings) if embeddings is not None else None
    return build_usecases(
        sql_repositories(),
        decision=OpenJevDecision(settings.decision_url, timeout=settings.decision_timeout)
        if settings.decision_url
        else None,
        model_extractor=QwenExtractor(
            settings.extractor_url,
            revision=settings.extractor_revision,
            timeout=settings.extractor_timeout,
            api_key=settings.extractor_api_key.get_secret_value()
            if settings.extractor_api_key
            else None,
        )
        if settings.extractor_url
        else None,
        verification_policy=VerificationPolicy(
            settings.verifier_threshold,
            settings.verifier_revision,
            settings.verifier_auto_accept_enabled,
        ),
        enum_policy=AutoAcceptance(
            settings.decision_auto_accept_threshold, settings.decision_revision
        )
        if settings.decision_auto_accept_enabled
        else AutoAcceptance(),
        fact_extractor=DeterministicFactExtractor(ReviewedValueAliases().all()),
        enum_matcher=DamerauMatcher(),
        value_aliases=ReviewedValueAliases(),
        spelling=QwenSpelling(
            settings.spelling_url,
            settings.spelling_model,
            settings.spelling_api_key.get_secret_value() if settings.spelling_api_key else None,
        )
        if settings.spelling_url
        else UnconfiguredSpelling(),
        lexical=TfidfIndex() if embeddings is not None else None,
        vector=MatrixIndex(
            embeddings, model=settings.embeddings_model, revision=settings.embeddings_revision
        )
        if embeddings is not None
        else None,
        embeddings=embeddings,
        aliases_source=CsvAliasesSource(settings.aliases_path),
        catalog_source=catalog_source or XmlKtruSource(settings.ktru_xml_dir),
        min_similarity=settings.search_min_similarity,
    )


def create_app(
    settings: Settings | None = None,
    catalog_source: CatalogSource | None = None,
    *,
    embeddings: Embeddings | None = None,
) -> FastAPI:
    settings = settings or Settings()
    if embeddings is None:
        embeddings = configured_embeddings(settings)
    engine = create_db_engine(settings.database_url)
    session_factory = sessionmaker(engine)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        try:
            with closing(SqlUnitOfWork(session_factory())) as uow:
                app.state.usecases.group_search(uow).build()
            yield
        finally:
            engine.dispose()

    app = FastAPI(
        title="Автозаполнение СТЕ и подбор КТРУ",
        version="0.1.0",
        docs_url="/api/docs",
        redoc_url=None,
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )
    app.state.engine = engine
    app.state.unit_of_work = lambda: SqlUnitOfWork(session_factory())
    app.state.usecases = production_usecases(settings, catalog_source, embeddings)

    install_error_handlers(app)
    app.include_router(health_router)
    app.include_router(catalog_router)
    app.include_router(groups_router)
    app.include_router(search_router)
    app.include_router(sessions_router)
    return app


def configured_embeddings(settings: Settings) -> Embeddings | None:
    if settings.embeddings_url:
        return OpenAIEmbeddings(
            settings.embeddings_url,
            model=settings.embeddings_model,
            api_key=settings.embeddings_api_key.get_secret_value()
            if settings.embeddings_api_key
            else None,
            dimension=settings.embeddings_dimension,
            revision=settings.embeddings_revision,
            query_instruction=settings.embeddings_query_instruction,
        )
    return None


def sync_catalog(
    settings: Settings | None = None, catalog_source: CatalogSource | None = None
) -> SyncReport:
    """Кладёт справочник КТРУ в базу. Схема должна быть на месте — `alembic upgrade head`.
    Позиции вне дерева групп пишутся в лог предупреждением."""
    settings = settings or Settings()
    engine = create_db_engine(settings.database_url)
    try:
        usecases = production_usecases(settings, catalog_source)
        with closing(SqlUnitOfWork(Session(engine))) as uow:
            report = usecases.catalog_sync(uow).run()
    finally:
        engine.dispose()
    log = logging.getLogger(__name__)
    for p in report.outside_tree:
        log.warning(
            "Позиция КТРУ %s вне групп: родитель %s не найден или не группа", p.code, p.parent
        )
    for alias in report.invalid_aliases:
        log.warning(
            "Синоним %s ссылается на отсутствующую группу %s", alias.alias, alias.group_code
        )
    return report
