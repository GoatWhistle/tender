"""Справочник КТРУ: позиции, характеристики в контексте позиции и их допустимые значения.

Содержимое кладёт синхронизация справочника (`app.usecase.catalog`). Характеристика и значение
привязаны к позиции: одинаковый код характеристики в разных позициях — разные строки.
"""

from sqlalchemy import JSON, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.repository.database import Base


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
    concrete: Mapped[float | None] = mapped_column(Float)
    min: Mapped[float | None] = mapped_column(Float)
    min_op: Mapped[str | None] = mapped_column(String(16))
    max: Mapped[float | None] = mapped_column(Float)
    max_op: Mapped[str | None] = mapped_column(String(16))
