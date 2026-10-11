from dataclasses import dataclass

from rag.usecase.catalog import CatalogQueries
from rag.usecase.clarify import CharacteristicReader
from rag.usecase.conversation import Conversation
from rag.usecase.correction import Corrector
from rag.usecase.discovery import Discoveries
from rag.usecase.flow import SessionFlow
from rag.usecase.interface import (
    AnalogsIndex,
    Catalog,
    DiscoveriesRepository,
    Embeddings,
    LanguageModel,
    SessionsRepository,
    VectorIndex,
)
from rag.usecase.rerank import Reranker
from rag.usecase.search import PositionSearch
from rag.usecase.sessions import Sessions
from rag.usecase.spec import ExtraValidator
from rag.usecase.suggest import Suggester


@dataclass(frozen=True, slots=True)
class Ports:
    llm: LanguageModel
    embeddings: Embeddings
    catalog: Catalog
    vectors: VectorIndex
    analogs: AnalogsIndex
    sessions: SessionsRepository
    discoveries: DiscoveriesRepository


@dataclass(frozen=True, slots=True)
class Usecases:
    ports: Ports
    corrector: Corrector
    search: PositionSearch
    reranker: Reranker
    catalog: CatalogQueries
    sessions: Sessions
    discoveries: Discoveries


def build_usecases(ports: Ports) -> Usecases:
    corrector = Corrector(ports.llm)
    search = PositionSearch(ports.catalog, ports.vectors, ports.embeddings)
    reranker = Reranker(ports.llm)
    reader = CharacteristicReader(ports.llm)
    validator = ExtraValidator(ports.llm)
    flow = SessionFlow(ports.catalog, reader)
    sessions = Sessions(
        ports.sessions,
        flow,
        corrector,
        search,
        reranker,
        reader,
        validator,
        Suggester(ports.llm, ports.analogs),
        Conversation(ports.llm, flow, validator),
    )
    return Usecases(
        ports=ports,
        corrector=corrector,
        search=search,
        reranker=reranker,
        catalog=CatalogQueries(ports.catalog, search),
        sessions=sessions,
        discoveries=Discoveries(
            ports.discoveries, ports.catalog, corrector, search, reranker, sessions
        ),
    )
