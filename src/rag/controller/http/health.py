from fastapi import APIRouter

from rag.controller.http.deps import CatalogDep

router = APIRouter(tags=["Служебное"])


@router.get("/health")
async def health(catalog: CatalogDep) -> dict[str, str]:
    catalog.require()
    return {"status": "ok"}
