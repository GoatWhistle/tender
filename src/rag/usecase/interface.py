from collections.abc import Iterator, Mapping, Sequence
from typing import Any, Protocol

from rag.domain.catalog import Position
from rag.domain.discovery import Discovery
from rag.domain.inference import Completion, StructuredRequest, Vector
from rag.domain.search import Scored
from rag.domain.sessions import Session
from rag.domain.suggestions import SteItem


class LanguageModel(Protocol):
    async def complete(self, request: StructuredRequest) -> Completion: ...


class Embeddings(Protocol):
    async def embed_queries(self, texts: Sequence[str]) -> list[Vector]: ...

    async def embed_documents(self, texts: Sequence[str]) -> list[Vector]: ...

    async def aclose(self) -> None: ...


class CatalogSource(Protocol):
    def records(self) -> Iterator[tuple[Position, dict[str, Any]]]: ...


class Catalog(Protocol):
    @property
    def ready(self) -> bool: ...

    def positions(self) -> Mapping[str, Position]: ...

    def position(self, code: str) -> Position | None: ...

    def leaves(self, p: Position) -> list[Position]: ...

    def names(self) -> Sequence[tuple[str, str]]: ...


class VectorIndex(Protocol):
    def nearest(self, query: Vector, limit: int) -> list[Scored]: ...


class CatalogStore(Protocol):
    def previous(self) -> tuple[list[str], list[str]] | None: ...

    def save(
        self,
        positions: Mapping[str, Position],
        raw: Mapping[str, dict[str, Any]],
        codes: list[str],
        texts: list[str],
    ) -> None: ...

    def texts(self) -> list[str]: ...


class VectorStore(Protocol):
    def open(self, rows: int, dimension: int) -> Sequence[bool]: ...

    def write(self, start: int, vectors: Sequence[Vector]) -> None: ...

    def checkpoint(self) -> None: ...


class SteSource(Protocol):
    def items(self) -> Iterator[SteItem]: ...


class AnalogsIndex(Protocol):
    def nearest(self, text: str) -> list[SteItem]: ...

    def rebuild(self, items: Sequence[SteItem]) -> None: ...

    def warm(self) -> None: ...


class SessionsRepository(Protocol):
    def get(self, session_id: str) -> Session | None: ...

    def add(self, session: Session) -> None: ...

    def replace(self, session: Session) -> None: ...

    def remove(self, session_id: str) -> None: ...


class DiscoveriesRepository(Protocol):
    def get(self, discovery_id: str) -> Discovery | None: ...

    def add(self, discovery: Discovery) -> None: ...
