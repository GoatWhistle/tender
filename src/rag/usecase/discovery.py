from rag.domain.correction import MAX_DESCRIPTION
from rag.domain.discovery import Discovery, DiscoveryStage
from rag.domain.errors import IndexNotReady, InputError, SearchNotFound, StageError
from rag.domain.sessions import Session
from rag.usecase.correction import Corrector
from rag.usecase.interface import Catalog, DiscoveriesRepository
from rag.usecase.locks import KeyedLocks
from rag.usecase.rerank import Reranker
from rag.usecase.search import PositionSearch
from rag.usecase.sessions import Sessions


class Discoveries:
    def __init__(
        self,
        repository: DiscoveriesRepository,
        catalog: Catalog,
        corrector: Corrector,
        search: PositionSearch,
        reranker: Reranker,
        sessions: Sessions,
    ) -> None:
        self._repository = repository
        self._catalog = catalog
        self._corrector = corrector
        self._search = search
        self._reranker = reranker
        self._sessions = sessions
        self._locks = KeyedLocks()

    def _get(self, discovery_id: str) -> Discovery:
        found = self._repository.get(discovery_id)
        if found is None:
            raise SearchNotFound()
        return found

    async def create(self, text: str) -> Discovery:
        if not self._catalog.ready:
            raise IndexNotReady()
        text = text.strip()
        if not text or len(text) > MAX_DESCRIPTION:
            raise InputError(
                f"описание должно содержать от 1 до {MAX_DESCRIPTION} символов"
            )
        discovery = Discovery(await self._corrector.run(text))
        self._repository.add(discovery)
        return discovery

    async def retrieve(self, discovery_id: str) -> Discovery:
        d = self._get(discovery_id)
        async with self._locks(d.id):
            if d.stage in (DiscoveryStage.CANDIDATES, DiscoveryStage.RANKED):
                return d
            d.found(await self._search.semantic(d.corrected.corrected))
            return d

    async def rank(self, discovery_id: str) -> Discovery:
        d = self._get(discovery_id)
        async with self._locks(d.id):
            if d.stage == DiscoveryStage.RANKED:
                return d
            if d.stage != DiscoveryStage.CANDIDATES:
                raise StageError("сначала получите кандидатов")
            d.rank(await self._reranker.run(d.corrected.corrected, d.hits))
            return d

    async def select(self, discovery_id: str, code: str, automatic: bool) -> Session:
        d = self._get(discovery_id)
        async with self._locks(d.id):
            d.check_selection(code, automatic)
            s = Session.of(d.corrected, d.ranked)
            await self._sessions.enter_ranked_group(s, code)
            if automatic:
                s.selection_reason = d.auto_select_reason
            return self._sessions.adopt(s)
