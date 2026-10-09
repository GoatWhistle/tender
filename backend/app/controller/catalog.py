"""Справочник КТРУ: список позиций и позиция с характеристиками."""

from fastapi import APIRouter

from app.controller.catalog_schemas import PositionOut, PositionSummary
from app.controller.deps import CatalogQueriesDep
from app.controller.errors import error_responses
from app.domain.errors import PositionNotFound

router = APIRouter(prefix="/api/v1/positions", tags=["КТРУ"])


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
