"""SQLite-хранилище снимков; блокировка записи предшествует чтению ревизии."""

from dataclasses import asdict
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.domain.search import MethodContribution
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
from app.repository.orm.sessions import AnalysisSession, SessionMessage, SessionRevision


def decode(data: dict[str, Any]) -> SessionState:
    path = data["path"]
    return SessionState(
        session_id=data["session_id"],
        revision=data["revision"],
        status=SessionStatus(data["status"]),
        messages=tuple(Message(**m) for m in data["messages"]),
        path=NarrowingPath(path["category"], GroupRef(**path["group"]), path["positions"])
        if path
        else None,
        alternatives=tuple(
            Alternative(
                a["code"],
                a["name"],
                a["category"],
                a["score"],
                {k: MethodContribution(**v) for k, v in a["methods"].items()},
            )
            for a in data["alternatives"]
        ),
        candidates=tuple(Candidate(**c) for c in data["candidates"]),
        candidate_counts=CandidateCounts(**data["candidate_counts"]),
        errors=tuple(AnalysisError(**e) for e in data["errors"]),
        warnings=tuple(data["warnings"]),
    )


class SqlSessions:
    def __init__(self, session: Session) -> None:
        self._session = session

    def latest(self, session_id: str, *, lock: bool = False) -> SessionState | None:
        if lock:
            self._session.execute(
                update(AnalysisSession)
                .where(AnalysisSession.id == session_id)
                .values(id=session_id)
            )
        row = self._session.scalar(
            select(SessionRevision)
            .where(SessionRevision.session_id == session_id)
            .order_by(SessionRevision.revision.desc())
            .limit(1)
        )
        return decode(row.snapshot) if row else None

    def replay(self, session_id: str, key: str) -> Revision | None:
        row = self._session.scalar(
            select(SessionRevision).where(
                SessionRevision.session_id == session_id, SessionRevision.idempotency_key == key
            )
        )
        return (
            Revision(decode(row.snapshot), row.idempotency_key, row.request_text) if row else None
        )

    def save(self, revision: Revision) -> None:
        state = revision.state
        if state.revision == 0:
            self._session.add(AnalysisSession(id=state.session_id))
            self._session.flush()
        else:
            message = state.messages[-1]
            self._session.add(
                SessionMessage(
                    id=message.id,
                    session_id=state.session_id,
                    revision=state.revision,
                    text=message.text,
                    created_at=message.created_at,
                )
            )
        self._session.add(
            SessionRevision(
                session_id=state.session_id,
                revision=state.revision,
                snapshot=asdict(state),
                idempotency_key=revision.idempotency_key,
                request_text=revision.request_text,
            )
        )
