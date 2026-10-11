from collections.abc import Callable
from typing import Annotated, Any

from fastapi import Depends, Request

from rag.usecase.catalog import CatalogQueries
from rag.usecase.discovery import Discoveries
from rag.usecase.sessions import Sessions


def _usecase(name: str) -> Callable[[Request], Any]:
    def get(request: Request) -> Any:
        return getattr(request.app.state.usecases, name)

    return get


CatalogDep = Annotated[CatalogQueries, Depends(_usecase("catalog"))]
SessionsDep = Annotated[Sessions, Depends(_usecase("sessions"))]
DiscoveriesDep = Annotated[Discoveries, Depends(_usecase("discoveries"))]
