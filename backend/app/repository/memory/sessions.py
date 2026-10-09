"""Хранилище снимков для сценарных тестов с откатом через MemoryUnitOfWork."""

from copy import deepcopy
from typing import cast

from app.domain.sessions import Revision, SessionState
from app.repository.memory.unit_of_work import MemoryStore


class MemorySessions:
    def __init__(self, store: MemoryStore) -> None:
        self._store = store

    def latest(self, session_id: str, *, lock: bool = False) -> SessionState | None:
        revisions = [
            cast(Revision, value)
            for value in self._store.collection("session_revisions").values()
            if cast(Revision, value).state.session_id == session_id
        ]
        if not revisions:
            return None
        return deepcopy(max(revisions, key=lambda r: r.state.revision).state)

    def replay(self, session_id: str, key: str) -> Revision | None:
        for value in self._store.collection("session_revisions").values():
            revision = cast(Revision, value)
            if revision.state.session_id == session_id and revision.idempotency_key == key:
                return deepcopy(revision)
        return None

    def save(self, revision: Revision) -> None:
        state = revision.state
        records = self._store.collection("session_revisions")
        key = (state.session_id, state.revision)
        if key in records or (
            revision.idempotency_key is not None
            and self.replay(state.session_id, revision.idempotency_key) is not None
        ):
            raise ValueError("Ревизия или ключ уже существует")
        records[key] = deepcopy(revision)
