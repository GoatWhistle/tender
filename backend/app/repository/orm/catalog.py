"""Справочник КТРУ: позиции, характеристики в контексте позиции и их допустимые значения.

Содержимое кладёт синхронизация справочника (`app.usecase.catalog`). Характеристика и значение
привязаны к позиции: одинаковый код характеристики в разных позициях — разные строки.
"""

from decimal import Decimal

from sqlalchemy import JSON, ForeignKey, String
from sqlalchemy.engine import Dialect
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import TypeDecorator

from app.repository.database import Base


class DecimalText(TypeDecorator[Decimal]):
    """SQLite NUMERIC приводит Decimal к float; TEXT сохраняет все цифры."""

    impl = String
    cache_ok = True

    def process_bind_param(self, value: Decimal | None, dialect: Dialect) -> str | None:
        return str(value) if value is not None else None

    def process_result_value(self, value: str | None, dialect: Dialect) -> Decimal | None:
        return Decimal(value) if value is not None else None


class CatalogPosition(Base):
    __tablename__ = "positions"

    code: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str]
    category: Mapped[str] = mapped_column(String(32), index=True)
    okpd2: Mapped[str] = mapped_column(String(32))
    okpd2_name: Mapped[str]
    is_template: Mapped[bool]
    parent: Mapped[str | None] = mapped_column(String(64), index=True)
    units: Mapped[list[str]] = mapped_column(JSON)
    rubrics: Mapped[list[str]] = mapped_column(JSON)

    characteristics: Mapped[list["PositionCharacteristic"]] = relationship(
        order_by="PositionCharacteristic.ordinal", cascade="all, delete-orphan"
    )


class PositionCharacteristic(Base):
    __tablename__ = "position_characteristics"

    id: Mapped[int] = mapped_column(primary_key=True)
    position_code: Mapped[str] = mapped_column(
        ForeignKey("positions.code", ondelete="CASCADE"), index=True
    )
    # Порядок характеристик в выгрузке.
    ordinal: Mapped[int]
    code: Mapped[str] = mapped_column(String(64))
    name: Mapped[str]
    quantitative: Mapped[bool]
    required: Mapped[bool]
    # `CharacteristicKind`
    kind: Mapped[str] = mapped_column(String(16))

    values: Mapped[list["AllowedValue"]] = relationship(
        order_by="AllowedValue.ordinal", cascade="all, delete-orphan"
    )


class AllowedValue(Base):
    __tablename__ = "allowed_values"

    id: Mapped[int] = mapped_column(primary_key=True)
    characteristic_id: Mapped[int] = mapped_column(
        ForeignKey("position_characteristics.id", ondelete="CASCADE"), index=True
    )
    ordinal: Mapped[int]
    code: Mapped[str] = mapped_column(String(64))
    text: Mapped[str | None]
    unit: Mapped[str | None]
    unit_code: Mapped[str | None] = mapped_column(String(16))
    concrete: Mapped[Decimal | None] = mapped_column(DecimalText)
    min: Mapped[Decimal | None] = mapped_column(DecimalText)
    min_op: Mapped[str | None] = mapped_column(String(16))
    max: Mapped[Decimal | None] = mapped_column(DecimalText)
    max_op: Mapped[str | None] = mapped_column(String(16))
