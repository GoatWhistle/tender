"""HTTP API сессий анализа."""

from typing import Annotated, Literal

from fastapi import APIRouter, Header
from pydantic import BaseModel, Field, field_validator, model_validator

from app.controller.deps import SessionsDep
from app.controller.errors import error_responses
from app.domain.errors import (
    FactNotFound,
    IdempotencyConflict,
    InvalidFactEdit,
    OptionNotFound,
    SessionNotFound,
    StaleQuestion,
    StaleRevision,
)
from app.domain.fact_edits import FactInput
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


class FactValueRequest(BaseModel):
    characteristic_name: str = Field(min_length=1, max_length=300)
    raw_value: str = Field(min_length=1, max_length=1000)
    raw_unit: str | None = Field(default=None, max_length=30)
    kind: Literal["text", "number", "range"] = "text"
    component: str | None = Field(default=None, max_length=200)

    def domain(self) -> FactInput:
        return FactInput(**self.model_dump())


class RevisionRequest(BaseModel):
    expected_revision: int = Field(ge=0)


class FactPatchRequest(RevisionRequest):
    action: Literal["edit", "delete", "confirm", "restore", "split", "accept_suggestion"]
    characteristic_name: str | None = None
    raw_value: str | None = None
    raw_unit: str | None = None
    kind: Literal["text", "number", "range"] = "text"
    component: str | None = None
    related_ids: list[str] = Field(default_factory=list, max_length=100)
    bindings: list[FactValueRequest] = Field(default_factory=list, max_length=100)
    diagnostic_index: int | None = Field(default=None, ge=0)

    def value(self) -> FactInput | None:
        if self.characteristic_name is None or self.raw_value is None:
            return None
        return FactInput(
            self.characteristic_name, self.raw_value, self.raw_unit, self.kind, self.component
        )


@router.patch(
    "/{session_id}/facts/{fact_id}",
    responses=error_responses(SessionNotFound, StaleRevision, FactNotFound, InvalidFactEdit),
)
def patch_fact(
    session_id: str, fact_id: str, body: FactPatchRequest, sessions: SessionsDep
) -> SessionState:
    return sessions.mutate(
        session_id,
        body.expected_revision,
        fact_id,
        body.action,
        body.value(),
        tuple(body.related_ids),
        tuple(b.domain() for b in body.bindings),
        body.diagnostic_index,
    )


@router.post(
    "/{session_id}/facts",
    responses=error_responses(SessionNotFound, StaleRevision, InvalidFactEdit),
)
def create_fact(session_id: str, body: FactPatchRequest, sessions: SessionsDep) -> SessionState:
    return sessions.mutate(
        session_id,
        body.expected_revision,
        None,
        body.action,
        body.value(),
        diagnostic_index=body.diagnostic_index,
    )


@router.post("/{session_id}/recalculate", responses=error_responses(SessionNotFound, StaleRevision))
def recalculate(session_id: str, body: RevisionRequest, sessions: SessionsDep) -> SessionState:
    return sessions.recalculate(session_id, body.expected_revision)
