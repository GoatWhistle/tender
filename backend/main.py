"""Сборка прода — вручную, без DI-контейнера (docs/adr/0001-layers-and-ports.md): здесь только
выбор реализаций портов, сценарии из них собирает общая проводка `composition`.

На уровне модуля только определения функций: объект приложения строит
`uvicorn --factory main:create_app`, поэтому импорт `main` не читает конфиг и не открывает базу.
Новый роутер подключается в `create_app`. Синхронизация справочника и словаря синонимов —
`sync_catalog`: её вызывают и старт контейнера, и командная строка
(`python -c 'import main; main.sync_catalog()'`). Индекс поиска строится при старте приложения:
после синхронизации на работающем сервере — перезапуск.
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, closing

from fastapi import FastAPI
from sqlalchemy.orm import Session, sessionmaker

from app.adapter.aliases_csv import CsvAliasSource
from app.adapter.embeddings_http import HttpEmbeddings, UnconfiguredEmbeddings
from app.adapter.ktru_xml import XmlKtruSource
from app.adapter.tfidf import TfidfLexicalIndex
from app.adapter.vector_numpy import NumpyVectorIndex
from app.controller.catalog import groups_router
from app.controller.catalog import router as catalog_router
from app.controller.errors import install_error_handlers
from app.controller.health import router as health_router
from app.controller.search import router as search_router
from app.domain.errors import DomainError
from app.repository.aliases import SqlAliases
from app.repository.catalog import SqlCatalog
from app.repository.database import create_db_engine
from app.repository.unit_of_work import SqlUnitOfWork
from app.usecase.catalog import SyncReport
from app.usecase.interface import CatalogSource, Embeddings
from composition import Repositories, Usecases, build_usecases
from settings import Settings


def sql_repositories() -> Repositories[SqlUnitOfWork]:
    return Repositories[SqlUnitOfWork](
        catalog=lambda uow: SqlCatalog(uow.session),
        aliases=lambda uow: SqlAliases(uow.session),
    )


def embeddings_of(settings: Settings) -> Embeddings:
    """Модель эмбеддингов из настроек; без адреса — не настроена, заглушкой не подменяется."""
    if not settings.embeddings_url:
        return UnconfiguredEmbeddings()
    return HttpEmbeddings(
        settings.embeddings_url, settings.embeddings_model, settings.embeddings_api_key
    )


def production_usecases(
    settings: Settings,
    catalog_source: CatalogSource | None = None,
    embeddings: Embeddings | None = None,
) -> Usecases[SqlUnitOfWork]:
    return build_usecases(
        sql_repositories(),
        catalog_source=catalog_source or XmlKtruSource(settings.ktru_xml_dir),
        alias_source=CsvAliasSource(settings.aliases_csv),
        embeddings=embeddings or embeddings_of(settings),
        lexical_index=TfidfLexicalIndex(),
        vector_index=NumpyVectorIndex(),
    )


def create_app(
    settings: Settings | None = None,
    catalog_source: CatalogSource | None = None,
    embeddings: Embeddings | None = None,
) -> FastAPI:
    """`embeddings` — реализация порта вместо модели из настроек: заглушка в тестах."""
    settings = settings or Settings()
    engine = create_db_engine(settings.database_url)
    session_factory = sessionmaker(engine)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        # Индекс поиска — после загрузки справочника. Без справочника или модели приложение
        # стартует, поиск пробует построить индекс на каждом запросе и отвечает ошибкой.
        with closing(app.state.unit_of_work()) as uow:
            try:
                app.state.usecases.group_search(uow).warm()
            except DomainError as error:
                logging.getLogger(__name__).warning("Индекс поиска не построен: %s", error)
            except Exception:
                # Например, база без миграций: остальные эндпоинты покажут это сами.
                logging.getLogger(__name__).exception("Индекс поиска не построен")
        yield
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
    return app


def sync_catalog(
    settings: Settings | None = None, catalog_source: CatalogSource | None = None
) -> SyncReport:
    """Кладёт справочник КТРУ в базу. Схема должна быть на месте — `alembic upgrade head`.
    Позиции вне дерева групп и синонимы несуществующих групп пишутся в лог предупреждением."""
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
    for a in report.orphan_aliases:
        log.warning("Синоним «%s»: группы %s нет в справочнике", a.alias, a.group_code)
    return report
