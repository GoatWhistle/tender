"""Сессия анализа: история сообщений, идемпотентность и снимки ревизий."""

from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4

from app.domain.catalog import Group
from app.domain.errors import CatalogEmpty, IdempotencyConflict, ModelFailure, SessionNotFound
from app.domain.search import SearchResult
from app.domain.sessions import (
    Alternative,
    AnalysisError,
    Candidate,
    CandidateCounts,
    GroupRef,
    Message,
    NarrowingPath,
    Revision,
    SessionState,
    SessionStatus,
)
from app.usecase.interface import CatalogRepository, GroupSearcher, SessionsRepository, UnitOfWork


class Sessions:
    def __init__(
        self,
        uow: UnitOfWork,
        sessions: SessionsRepository,
        search: GroupSearcher,
        catalog: CatalogRepository,
    ) -> None:
        self._search = search
        self._catalog = catalog
        self._uow = uow
        self._sessions = sessions

    def create(self) -> SessionState:
        state = SessionState(str(uuid4()))
        with self._uow:
            self._sessions.save(Revision(state))
        return state

    def get(self, session_id: str) -> SessionState:
        with self._uow:
            state = self._sessions.latest(session_id)
            if state is None:
                raise SessionNotFound()
            return state

    def message(self, session_id: str, text: str, key: str | None = None) -> SessionState:
        with self._uow:
            previous = self._sessions.latest(session_id, lock=True)
            if previous is None:
                raise SessionNotFound()
            replay = self._sessions.replay(session_id, key) if key is not None else None
            if replay is not None:
                if replay.request_text != text:
                    raise IdempotencyConflict()
                return replay.state
            messages = (
                *previous.messages,
                Message(str(uuid4()), text, datetime.now(UTC).isoformat()),
            )
            state = SessionState(session_id, previous.revision + 1, messages=messages)
            try:
                result = self._search.run(
                    "\n".join(m.text for m in messages), category=None, limit=5
                )
                state = self._analyze(state, result)
            except (ModelFailure, CatalogEmpty) as error:
                state = replace(
                    state,
                    status=SessionStatus.TECHNICAL_ERROR,
                    errors=(AnalysisError(error.code, error.message),),
                )
            self._sessions.save(Revision(state, key, text))
            return state

    def _analyze(self, state: SessionState, result: SearchResult) -> SessionState:
        if not result.groups:
            raise CatalogEmpty()
        selected = result.groups[0].group
        group = Group.of(selected, self._catalog.children(selected.code))
        candidates = tuple(
            Candidate(p.code, p.name) for p in sorted(group.leaves, key=lambda p: p.code)
        )
        count = len(candidates)
        return replace(
            state,
            status=SessionStatus.RESOLVED if count == 1 else SessionStatus.NEEDS_CLARIFICATION,
            path=NarrowingPath(selected.category, GroupRef(selected.code, selected.name), count),
            candidates=candidates,
            candidate_counts=CandidateCounts(count, count),
            alternatives=tuple(
                Alternative(
                    hit.group.code,
                    hit.group.name,
                    hit.group.category,
                    hit.score,
                    {"lexical": hit.lexical, "vector": hit.vector, "synonym": hit.synonym},
                )
                for hit in result.groups[1:5]
            ),
            warnings=result.messages,
        )
