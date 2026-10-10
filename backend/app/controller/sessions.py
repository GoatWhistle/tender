"""HTTP API сессий анализа."""

from typing import Annotated, Literal

from fastapi import APIRouter, Header
from pydantic import BaseModel, Field, field_validator, model_validator

from app.controller.deps import SessionsDep
from app.controller.errors import error_responses
from app.domain.errors import (
    IdempotencyConflict,
    OptionNotFound,
    SessionNotFound,
    StaleQuestion,
    StaleRevision,
)
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


class AnswerRequest(BaseModel):
    """Выбранный вариант (`option_id`) либо «не знаю» (`unknown: true`) — ровно одно."""

    question_id: str = Field(min_length=1)
    option_id: str | None = Field(default=None, min_length=1)
    unknown: bool = False

    @model_validator(mode="after")
    def one_answer(self) -> "AnswerRequest":
        if (self.option_id is None) != self.unknown:
            raise ValueError("Нужен либо option_id, либо unknown: true")
        return self


@router.post(
    "/{session_id}/answers",
    responses=error_responses(SessionNotFound, StaleQuestion, OptionNotFound),
)
def answer(session_id: str, body: AnswerRequest, sessions: SessionsDep) -> SessionState:
    return sessions.answer(session_id, body.question_id, body.option_id)


class EnumResolutionRequest(BaseModel):
    expected_revision: int = Field(ge=0, strict=True)
    proposal_id: str = Field(min_length=1)
    action: Literal["accept", "choose", "unknown"]
    values: list[str] = Field(default_factory=list, max_length=256)

    @model_validator(mode="after")
    def valid_selection(self) -> "EnumResolutionRequest":
        if self.action == "choose":
            if not self.values or len(set(self.values)) != len(self.values):
                raise ValueError("Нужны различные допустимые значения")
        elif self.values:
            raise ValueError("Значения передаются только для choose")
        return self


@router.post(
    "/{session_id}/enum-resolutions",
    responses=error_responses(SessionNotFound, StaleRevision, OptionNotFound),
)
def resolve_enum(
    session_id: str, body: EnumResolutionRequest, sessions: SessionsDep
) -> SessionState:
    return sessions.resolve_enum(
        session_id, body.expected_revision, body.proposal_id, body.action, body.values
    )
