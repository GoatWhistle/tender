"""Справочник КТРУ на SQLite — реализация порта `CatalogRepository`."""

from collections.abc import Iterable
from typing import Any

from sqlalchemy import delete, func, insert, select
from sqlalchemy.orm import Session, selectinload

from app.domain.catalog import Bound, Characteristic, Position, Value
from app.repository.orm.catalog import AllowedValue, CatalogPosition, PositionCharacteristic

_LOAD = selectinload(CatalogPosition.characteristics).selectinload(PositionCharacteristic.values)


class SqlCatalog:
    def __init__(self, session: Session) -> None:
        self._session = session

    def position(self, code: str) -> Position | None:
        row = self._session.scalar(
            select(CatalogPosition).where(CatalogPosition.code == code).options(_LOAD)
        )
        return _position(row) if row is not None else None

    def positions(self, category: str | None = None) -> list[Position]:
        query = select(CatalogPosition).options(_LOAD).order_by(CatalogPosition.code)
        if category is not None:
            query = query.where(CatalogPosition.category == category)
        return [_position(r) for r in self._session.scalars(query)]

    def count(self) -> int:
        return self._session.scalar(select(func.count()).select_from(CatalogPosition)) or 0

    def replace(self, positions: Iterable[Position]) -> None:
        # Пакетная вставка ядром: справочник — десятки тысяч значений, ORM-объекты здесь дороги.
        self._session.execute(delete(AllowedValue))
        self._session.execute(delete(PositionCharacteristic))
        self._session.execute(delete(CatalogPosition))
        rows: list[dict[str, Any]] = []
        chars: list[dict[str, Any]] = []
        values: list[dict[str, Any]] = []
        for p in positions:
            rows.append(
                {
                    "code": p.code,
                    "name": p.name,
                    "category": p.category,
                    "okpd2": p.okpd2,
                    "okpd2_name": p.okpd2_name,
                    "is_template": p.is_template,
                    "parent": p.parent,
                    "units": list(p.units),
                    "rubrics": list(p.rubrics),
                }
            )
            for i, c in enumerate(p.characteristics):
                char_id = len(chars) + 1
                chars.append(
                    {
                        "id": char_id,
                        "position_code": p.code,
                        "ordinal": i,
                        "code": c.code,
                        "name": c.name,
                        "quantitative": c.quantitative,
                        "required": c.required,
                        "multi": c.multi,
                    }
                )
                values.extend(
                    {
                        "characteristic_id": char_id,
                        "ordinal": j,
                        "code": v.code,
                        "text": v.text,
                        "unit": v.unit,
                        "unit_code": v.unit_code,
                        "concrete": v.concrete,
                        "min": v.min,
                        "min_op": v.min_op,
                        "max": v.max,
                        "max_op": v.max_op,
                    }
                    for j, v in enumerate(c.values)
                )
        for table, batch in (
            (CatalogPosition, rows),
            (PositionCharacteristic, chars),
            (AllowedValue, values),
        ):
            if batch:
                self._session.execute(insert(table), batch)


def _value(v: AllowedValue) -> Value:
    return Value(
        code=v.code,
        text=v.text,
        unit=v.unit,
        unit_code=v.unit_code,
        concrete=v.concrete,
        min=v.min,
        min_op=Bound(v.min_op) if v.min_op else None,
        max=v.max,
        max_op=Bound(v.max_op) if v.max_op else None,
    )


def _position(row: CatalogPosition) -> Position:
    return Position(
        code=row.code,
        name=row.name,
        category=row.category,
        okpd2=row.okpd2,
        okpd2_name=row.okpd2_name,
        is_template=row.is_template,
        parent=row.parent,
        units=tuple(row.units),
        rubrics=tuple(row.rubrics),
        characteristics=tuple(
            Characteristic(
                code=c.code,
                name=c.name,
                quantitative=c.quantitative,
                required=c.required,
                multi=c.multi,
                values=tuple(_value(v) for v in c.values),
            )
            for c in row.characteristics
        ),
    )
