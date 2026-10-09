"""Сессии, исходные сообщения и неизменяемые снимки ревизий."""

from typing import Any

from sqlalchemy import JSON, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.repository.database import Base


class AnalysisSession(Base):
    __tablename__ = "analysis_sessions"
    id: Mapped[str] = mapped_column(primary_key=True)


class SessionMessage(Base):
    __tablename__ = "session_messages"
    __table_args__ = (UniqueConstraint("session_id", "revision"),)
    id: Mapped[str] = mapped_column(primary_key=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("analysis_sessions.id"))
    revision: Mapped[int]
    text: Mapped[str]
    created_at: Mapped[str]


class SessionRevision(Base):
    __tablename__ = "session_revisions"
    __table_args__ = (UniqueConstraint("session_id", "idempotency_key"),)
    session_id: Mapped[str] = mapped_column(ForeignKey("analysis_sessions.id"), primary_key=True)
    revision: Mapped[int] = mapped_column(primary_key=True)
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSON)
    idempotency_key: Mapped[str | None]
    request_text: Mapped[str | None]
