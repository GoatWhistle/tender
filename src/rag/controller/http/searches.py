from fastapi import APIRouter

from rag.controller.http.deps import DiscoveriesDep
from rag.controller.http.schemas import DiscoveryOut, GroupIn, SessionOut, StartIn

router = APIRouter(prefix="/searches", tags=["Поиск"])


@router.post("", status_code=201)
async def create(body: StartIn, discoveries: DiscoveriesDep) -> DiscoveryOut:
    return DiscoveryOut.of(await discoveries.create(body.description))


@router.post("/{search_id}/candidates")
async def candidates(search_id: str, discoveries: DiscoveriesDep) -> DiscoveryOut:
    return DiscoveryOut.of(await discoveries.retrieve(search_id))


@router.post("/{search_id}/rerank")
async def rerank(search_id: str, discoveries: DiscoveriesDep) -> DiscoveryOut:
    return DiscoveryOut.of(await discoveries.rank(search_id))


@router.post("/{search_id}/select")
async def select(
    search_id: str, body: GroupIn, discoveries: DiscoveriesDep
) -> SessionOut:
    return SessionOut.of(await discoveries.select(search_id, body.code, body.automatic))
