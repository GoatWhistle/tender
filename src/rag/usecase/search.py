import asyncio

from rag.domain.catalog import Position
from rag.domain.search import CANDIDATES, TOP_K, Hit, group_by_name, name_rank
from rag.usecase.interface import Catalog, Embeddings, VectorIndex

FOUND_LIMIT = 10


class PositionSearch:
    def __init__(
        self, catalog: Catalog, vectors: VectorIndex, embeddings: Embeddings
    ) -> None:
        self._catalog = catalog
        self._vectors = vectors
        self._embeddings = embeddings

    async def semantic(self, text: str, k: int = TOP_K) -> list[Hit]:
        [query] = await self._embeddings.embed_queries([text])
        scored = await asyncio.to_thread(self._vectors.nearest, query, CANDIDATES)
        return group_by_name(scored, self._catalog.positions(), k)

    def by_name(self, text: str, limit: int = FOUND_LIMIT) -> list[Position]:
        needle = text.strip().lower()
        ranked = sorted(
            (rank, len(lowered), code)
            for code, lowered in self._catalog.names()
            if (rank := name_rank(code, lowered, needle)) is not None
        )
        positions = self._catalog.positions()
        return [positions[code] for _, _, code in ranked[:limit]]
