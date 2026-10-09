"""HTTP API сессий анализа."""

from typing import Annotated

from fastapi import APIRouter, Header
from pydantic import BaseModel, Field, field_validator

from app.controller.deps import SessionsDep
from app.controller.errors import error_responses
from app.domain.errors import IdempotencyConflict, SessionNotFound
from app.domain.sessions import SessionState

router = APIRouter(prefix="/api/v1/sessions", tags=["Сессии"])


@router.post("")
def create(sessions: SessionsDep) -> SessionState:
    return sessions.create()


@router.get("/{session_id}", responses=error_responses(SessionNotFound))
def get(session_id: str, sessions: SessionsDep) -> SessionState:
    return sessions.get(session_id)


class MessageRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4000)

    @field_validator("text")
    @classmethod
    def not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Текст не должен быть пустым")
        return value


@router.post(
    "/{session_id}/messages", responses=error_responses(SessionNotFound, IdempotencyConflict)
)
def message(
    session_id: str,
    body: MessageRequest,
    sessions: SessionsDep,
    idempotency_key: Annotated[str | None, Header()] = None,
) -> SessionState:
    return sessions.message(session_id, body.text, idempotency_key)
