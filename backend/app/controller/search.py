"""Поиск групп КТРУ по описанию товара."""

from fastapi import APIRouter

from app.controller.deps import GroupSearchDep
from app.controller.errors import error_responses
from app.controller.search_schemas import GroupMatchOut, MessageOut, SearchIn, SearchOut
from app.domain.errors import CatalogEmpty, ModelFailure, ModelNotConfigured
from app.usecase.search import SearchQuery

router = APIRouter(prefix="/api/v1/search", tags=["Поиск"])


@router.post(
    "",
    summary="Группы КТРУ по описанию: TF-IDF, эмбеддинги и синонимы, слитые RRF",
    responses=error_responses(CatalogEmpty, ModelFailure, ModelNotConfigured),
)
def search(body: SearchIn, groups: GroupSearchDep) -> SearchOut:
    result = groups.search(SearchQuery(body.text, body.category, body.limit))
    return SearchOut(
        text=body.text,
        groups=[GroupMatchOut.of(m) for m in result.groups],
        messages=[MessageOut.of(m) for m in result.messages],
    )
