import asyncio
from typing import Annotated, Literal

import aiohttp
from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from rag.comparison import characteristic_rows, match
from rag.ktru import value_text
from rag.models import Position
from rag.search import Index, query_vector

router = APIRouter()

COMPARE_LIMIT = 4
FOUND_LIMIT = 10


class CatalogCharacteristic(BaseModel):
    code: str
    name: str
    kind: str
    required: bool
    values: list[str]


class CatalogPosition(BaseModel):
    code: str
    name: str
    okpd2: str
    okpd2_name: str
    units: list[str]
    rubrics: list[str]
    characteristics: list[CatalogCharacteristic]


class CatalogFound(BaseModel):
    code: str
    name: str
    okpd2: str
    okpd2_name: str


class ComparisonRow(BaseModel):
    field: Literal["okpd2", "units", "characteristic"]
    name: str | None = None
    values: list[list[str] | None]
    differs: bool


class CatalogComparison(BaseModel):
    positions: list[CatalogFound]
    rows: list[ComparisonRow]


def require_index(request: Request) -> Index:
    index = request.app.state.index
    if index is None:
        raise HTTPException(503, "индекс КТРУ не настроен")
    return index


def found(position: Position) -> CatalogFound:
    return CatalogFound(
        code=position.code,
        name=position.name,
        okpd2=position.okpd2,
        okpd2_name=position.okpd2_name,
    )


def meta_row(
    field: Literal["okpd2", "units"], values: list[list[str]]
) -> ComparisonRow:
    return ComparisonRow(
        field=field,
        values=list(values),
        differs=len({tuple(sorted(v)) for v in values}) > 1,
    )


@router.get("/catalog")
async def find_positions(
    request: Request,
    q: Annotated[str, Query(min_length=1, max_length=500)],
    mode: Literal["text", "semantic"] = "text",
) -> list[CatalogFound]:
    index = require_index(request)
    if mode == "semantic":
        try:
            vector = await query_vector(q.strip())
        except aiohttp.ClientError as exc:
            raise HTTPException(502, f"сервис эмбеддингов недоступен: {exc}") from exc
        hits = await asyncio.to_thread(index.search, vector, FOUND_LIMIT)
        return [found(hit.position) for hit in hits]
    needle = q.strip().lower()
    ranked = sorted(
        (rank, len(lowered), code)
        for code, lowered in index.names
        if (rank := match(code, lowered, needle)) is not None
    )
    return [found(index.positions[code]) for _, _, code in ranked[:FOUND_LIMIT]]


@router.get("/catalog/compare")
async def compare_positions(
    request: Request, codes: Annotated[list[str], Query()]
) -> CatalogComparison:
    index = require_index(request)
    unique = list(dict.fromkeys(codes))
    if not 2 <= len(unique) <= COMPARE_LIMIT:
        raise HTTPException(422, f"сравниваются от 2 до {COMPARE_LIMIT} позиций")
    missing = [code for code in unique if code not in index.positions]
    if missing:
        raise HTTPException(404, f"нет таких позиций КТРУ: {', '.join(missing)}")
    positions = [index.positions[code] for code in unique]
    rows = [
        meta_row("okpd2", [[p.okpd2] for p in positions]),
        meta_row("units", [sorted(p.units) for p in positions]),
        *(
            ComparisonRow(
                field="characteristic",
                name=name,
                values=[list(v) if v is not None else None for v in values],
                differs=differs,
            )
            for name, values, differs in characteristic_rows(positions)
        ),
    ]
    return CatalogComparison(positions=[found(p) for p in positions], rows=rows)


@router.get("/catalog/{code}")
async def position_details(code: str, request: Request) -> CatalogPosition:
    position = require_index(request).positions.get(code)
    if position is None:
        raise HTTPException(404, "нет такой позиции КТРУ")
    return CatalogPosition(
        code=position.code,
        name=position.name,
        okpd2=position.okpd2,
        okpd2_name=position.okpd2_name,
        units=list(position.units),
        rubrics=list(position.rubrics),
        characteristics=[
            CatalogCharacteristic(
                code=c.code,
                name=c.name,
                kind=c.kind,
                required=c.required,
                values=[value_text(v) for v in c.values],
            )
            for c in position.characteristics
        ],
    )
