"""Поиск групп по описанию с объяснением вкладов методов."""

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field, field_validator

from app.controller.deps import GroupSearchDep
from app.controller.errors import error_responses
from app.domain.errors import CatalogEmpty, ModelFailure, ModelNotConfigured
from app.domain.search import SearchHit, SearchResult

router = APIRouter(prefix="/api/v1/search", tags=["Поиск"])


class SearchRequest(BaseModel):
    description: str = Field(min_length=1, max_length=16000)
    category: Literal["Одежда", "Мебель", "Инструменты"] | None = None
    limit: int = Field(default=10, ge=1, le=50)

    @field_validator("description")
    @classmethod
    def not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Описание не должно быть пустым")
        return value


class MethodOut(BaseModel):
    rank: int | None
    contribution: float


class HitOut(BaseModel):
    code: str
    name: str
    category: str
    score: float
    methods: dict[str, MethodOut]
    found_by: str

    @classmethod
    def of(cls, hit: SearchHit) -> "HitOut":
        return cls(
            code=hit.group.code,
            name=hit.group.name,
            category=hit.group.category,
            score=hit.score,
            found_by=hit.found_by,
            methods={
                name: MethodOut(rank=m.rank, contribution=m.contribution)
                for name, m in (
                    ("lexical", hit.lexical),
                    ("vector", hit.vector),
                    ("synonym", hit.synonym),
                )
            },
        )


class SearchOut(BaseModel):
    description: str
    groups: list[HitOut]
    messages: list[str]

    @classmethod
    def of(cls, result: SearchResult) -> "SearchOut":
        return cls(
            description=result.description,
            groups=[HitOut.of(h) for h in result.groups],
            messages=list(result.messages),
        )


@router.post("", responses=error_responses(CatalogEmpty, ModelFailure, ModelNotConfigured))
def search(body: SearchRequest, queries: GroupSearchDep) -> SearchOut:
    return SearchOut.of(queries.run(body.description, body.category, body.limit))
