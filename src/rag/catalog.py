from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from rag.ktru import value_text

router = APIRouter()


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


@router.get("/catalog/{code}")
async def position_details(code: str, request: Request) -> CatalogPosition:
    index = request.app.state.index
    if index is None:
        raise HTTPException(503, "индекс КТРУ не настроен")
    position = index.positions.get(code)
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
