"""Живость процесса и готовность к анализу."""

from fastapi import APIRouter
from pydantic import BaseModel

from app.controller.deps import CatalogQueriesDep
from app.controller.errors import error_responses
from app.domain.errors import CatalogEmpty

router = APIRouter(prefix="/health", tags=["Служебное"])


class Ready(BaseModel):
    positions: int


@router.get("/live", summary="Процесс работает")
def live() -> dict[str, str]:
    return {"status": "ok"}


@router.get(
    "/ready",
    summary="Справочник загружен",
    responses=error_responses(CatalogEmpty),
)
def ready(queries: CatalogQueriesDep) -> Ready:
    return Ready(positions=queries.ready())
