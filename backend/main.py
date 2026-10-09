"""Сборка прода — вручную, без DI-контейнера (docs/adr/0001-layers-and-ports.md): здесь только
выбор реализаций портов, сценарии из них собирает общая проводка `composition`.

На уровне модуля только определения функций: объект приложения строит
`uvicorn --factory main:create_app`, поэтому импорт `main` не читает конфиг и не открывает базу.
Новый роутер подключается в `create_app`. Синхронизация справочника — `sync_catalog`: её вызывают
и старт контейнера, и командная строка (`python -c 'import main; main.sync_catalog()'`).
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, closing

from fastapi import FastAPI
from sqlalchemy.orm import Session, sessionmaker

from app.adapter.ktru_xml import XmlKtruSource
from app.controller.catalog import router as catalog_router
from app.controller.errors import install_error_handlers
from app.controller.health import router as health_router
from app.repository.catalog import SqlCatalog
from app.repository.database import create_db_engine
from app.repository.unit_of_work import SqlUnitOfWork
from app.usecase.interface import CatalogSource
from composition import Repositories, Usecases, build_usecases
from settings import Settings


def sql_repositories() -> Repositories[SqlUnitOfWork]:
    return Repositories[SqlUnitOfWork](catalog=lambda uow: SqlCatalog(uow.session))


def production_usecases(
    settings: Settings, catalog_source: CatalogSource | None = None
) -> Usecases[SqlUnitOfWork]:
    return build_usecases(
        sql_repositories(),
        catalog_source=catalog_source or XmlKtruSource(settings.ktru_xml_dir),
    )


def create_app(
    settings: Settings | None = None, catalog_source: CatalogSource | None = None
) -> FastAPI:
    settings = settings or Settings()
    engine = create_db_engine(settings.database_url)
    session_factory = sessionmaker(engine)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
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
    app.state.usecases = production_usecases(settings, catalog_source)

    install_error_handlers(app)
    app.include_router(health_router)
    app.include_router(catalog_router)
    return app


def sync_catalog(
    settings: Settings | None = None, catalog_source: CatalogSource | None = None
) -> int:
    """Кладёт справочник КТРУ в базу; возвращает число позиций. Схема должна быть на месте —
    `alembic upgrade head`."""
    settings = settings or Settings()
    engine = create_db_engine(settings.database_url)
    try:
        usecases = production_usecases(settings, catalog_source)
        with closing(SqlUnitOfWork(Session(engine))) as uow:
            return usecases.catalog_sync(uow).run()
    finally:
        engine.dispose()
