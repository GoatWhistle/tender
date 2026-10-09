"""Словарь синонимов групп КТРУ: все записи `data/aliases.csv`, и непроверенные.

Содержимое кладёт синхронизация справочника (`app.usecase.catalog`). Внешнего ключа на группу
нет: справочник заменяется целиком, а синоним несуществующей группы виден в отчёте синхронизации.
"""

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.repository.database import Base


class AliasRow(Base):
    __tablename__ = "aliases"

    id: Mapped[int] = mapped_column(primary_key=True)
    group_code: Mapped[str] = mapped_column(String(64), index=True)
    alias: Mapped[str]
    source: Mapped[str] = mapped_column(String(32))
    reviewed: Mapped[bool]
