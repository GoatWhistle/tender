"""Словарь с происхождением и флагом ручной проверки."""

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.repository.database import Base


class GroupAlias(Base):
    __tablename__ = "aliases"

    group_code: Mapped[str] = mapped_column(
        ForeignKey("positions.code", ondelete="CASCADE"), primary_key=True
    )
    alias: Mapped[str] = mapped_column(String(512), primary_key=True)
    source: Mapped[str] = mapped_column(String(512))
    reviewed: Mapped[bool]
