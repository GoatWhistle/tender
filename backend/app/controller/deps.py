"""Зависимости эндпоинтов: единица работы запроса и сценарии на ней.

Реализации и фабрики сценариев кладёт в `app.state` сборка в `backend/main.py`; контроллер
реализаций не знает.
"""

from collections.abc import Callable, Iterator
from typing import Annotated, Any

from fastapi import Depends, Request

from app.usecase.catalog import CatalogQueries
from app.usecase.interface import RequestUnitOfWork
from app.usecase.search import GroupSearch


def unit_of_work(request: Request) -> Iterator[RequestUnitOfWork]:
    uow: RequestUnitOfWork = request.app.state.unit_of_work()
    try:
        yield uow
    finally:
        uow.close()


UnitOfWorkDep = Annotated[RequestUnitOfWork, Depends(unit_of_work)]


def _usecase(name: str) -> Callable[[Request, RequestUnitOfWork], Any]:
    def build(request: Request, uow: UnitOfWorkDep) -> Any:
        return getattr(request.app.state.usecases, name)(uow)

    return build


CatalogQueriesDep = Annotated[CatalogQueries, Depends(_usecase("catalog_queries"))]
GroupSearchDep = Annotated[GroupSearch, Depends(_usecase("group_search"))]
