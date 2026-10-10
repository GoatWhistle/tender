"""Отметка сохранения и текст ввода; история анализа остаётся в сессии."""

from dataclasses import dataclass

from app.domain.sessions import SessionState


@dataclass(frozen=True)
class SavedDraft:
    session_id: str
    saved_revision: int
    input_text: str
    saved_at: str


@dataclass(frozen=True)
class DraftState:
    state: SessionState
    input_text: str = ""
    saved_revision: int | None = None
    saved_at: str | None = None


@dataclass(frozen=True)
class DraftSummary:
    session_id: str
    title: str
    revision: int
    saved_revision: int
    saved_at: str
