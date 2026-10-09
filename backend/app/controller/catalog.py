"""Справочник КТРУ: позиции с характеристиками и группы с конечными позициями."""

from fastapi import APIRouter

from app.controller.catalog_schemas import GroupOut, PositionOut, PositionSummary
from app.controller.deps import CatalogQueriesDep
from app.controller.errors import error_responses
from app.domain.errors import GroupNotFound, PositionNotFound

router = APIRouter(prefix="/api/v1/positions", tags=["КТРУ"])
groups_router = APIRouter(prefix="/api/v1/groups", tags=["КТРУ"])


@router.get("", summary="Позиции КТРУ")
def positions(queries: CatalogQueriesDep, category: str | None = None) -> list[PositionSummary]:
    return [PositionSummary.of(p) for p in queries.positions(category)]


@router.get(
    "/{code}",
    summary="Позиция КТРУ с характеристиками",
    responses=error_responses(PositionNotFound),
)
def position(code: str, queries: CatalogQueriesDep) -> PositionOut:
    return PositionOut.of(queries.position(code))


@groups_router.get("", summary="Группы КТРУ: шаблоны и позиции без родителя")
def groups(queries: CatalogQueriesDep, category: str | None = None) -> list[PositionSummary]:
    return [PositionSummary.of(p) for p in queries.groups(category)]


@groups_router.get(
    "/{code}",
    summary="Группа КТРУ с конечными позициями",
    responses=error_responses(GroupNotFound),
)
def group(code: str, queries: CatalogQueriesDep) -> GroupOut:
    return GroupOut.of(queries.group(code))
