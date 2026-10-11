from typing import Annotated, Literal

from fastapi import APIRouter, Query

from rag.controller.http.deps import CatalogDep
from rag.controller.http.schemas import CatalogComparison, CatalogFound, CatalogPosition

router = APIRouter(prefix="/catalog", tags=["Каталог"])


@router.get("")
async def find_positions(
    catalog: CatalogDep,
    q: Annotated[str, Query(min_length=1, max_length=500)],
    mode: Literal["text", "semantic"] = "text",
) -> list[CatalogFound]:
    return [
        CatalogFound.of(p) for p in await catalog.find(q, semantic=mode == "semantic")
    ]


@router.get("/compare")
async def compare_positions(
    catalog: CatalogDep, codes: Annotated[list[str], Query()]
) -> CatalogComparison:
    return CatalogComparison.of(catalog.compare(codes))


@router.get("/{code}")
async def position_details(code: str, catalog: CatalogDep) -> CatalogPosition:
    return CatalogPosition.of(catalog.details(code))
