from rag.domain.discovery import Discovery
from rag.domain.sessions import Session


class MemorySessions:
    def __init__(self) -> None:
        self._items: dict[str, Session] = {}

    def get(self, session_id: str) -> Session | None:
        return self._items.get(session_id)

    def add(self, session: Session) -> None:
        self._items[session.id] = session

    def replace(self, session: Session) -> None:
        self._items[session.id] = session

    def remove(self, session_id: str) -> None:
        self._items.pop(session_id, None)


class MemoryDiscoveries:
    def __init__(self) -> None:
        self._items: dict[str, Discovery] = {}

    def get(self, discovery_id: str) -> Discovery | None:
        return self._items.get(discovery_id)

    def add(self, discovery: Discovery) -> None:
        self._items[discovery.id] = discovery
