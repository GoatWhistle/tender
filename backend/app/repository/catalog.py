"""Справочник КТРУ на SQLite — реализация порта `CatalogRepository`."""

from collections import defaultdict
from collections.abc import Iterable
from typing import Any

from sqlalchemy import ColumnElement, delete, func, insert, or_, select, true
from sqlalchemy.orm import Session

from app.domain.catalog import Bound, Characteristic, CharacteristicKind, Position, Value
from app.repository.orm.catalog import AllowedValue, CatalogPosition, PositionCharacteristic


class SqlCatalog:
    def __init__(self, session: Session) -> None:
        self._session = session

    def position(self, code: str) -> Position | None:
        found = self._load(CatalogPosition.code == code)
        return found[0] if found else None

    def positions(self, category: str | None = None) -> list[Position]:
        return self._load(_in_category(category))

    def groups(self, category: str | None = None) -> list[Position]:
        # Определение группы — `Position.is_group`: шаблон или позиция без родителя.
        return self._load(
            or_(CatalogPosition.is_template, CatalogPosition.parent.is_(None)),
            _in_category(category),
        )

    def children(self, code: str) -> list[Position]:
        return self._load(CatalogPosition.parent == code)

    def _load(self, *where: ColumnElement[bool]) -> list[Position]:
        # Чтение ядром: справочник — десятки тысяч значений, ORM-объекты на каждое чтение
        # стоят секунды. Три запроса: позиции, их характеристики, значения характеристик.
        codes = select(CatalogPosition.code).where(*where)
        chars = PositionCharacteristic.__table__
        values = AllowedValue.__table__
        by_char: dict[int, list[Value]] = defaultdict(list)
        for v in self._session.execute(
            select(values)
            .join(chars, values.c.characteristic_id == chars.c.id)
            .where(chars.c.position_code.in_(codes))
            .order_by(values.c.characteristic_id, values.c.ordinal)
        ):
            by_char[v.characteristic_id].append(
                Value(
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
            )
        by_position: dict[str, list[Characteristic]] = defaultdict(list)
        for c in self._session.execute(
            select(chars)
            .where(chars.c.position_code.in_(codes))
            .order_by(chars.c.position_code, chars.c.ordinal)
        ):
            by_position[c.position_code].append(
                Characteristic(
                    code=c.code,
                    name=c.name,
                    quantitative=c.quantitative,
                    required=c.required,
                    kind=CharacteristicKind(c.kind),
                    values=tuple(by_char.get(c.id, ())),
                )
            )
        rows = self._session.execute(
            select(CatalogPosition.__table__).where(*where).order_by(CatalogPosition.code)
        )
        return [
            Position(
                code=r.code,
                name=r.name,
                category=r.category,
                okpd2=r.okpd2,
                okpd2_name=r.okpd2_name,
                is_template=r.is_template,
                parent=r.parent,
                units=tuple(r.units),
                rubrics=tuple(r.rubrics),
                characteristics=tuple(by_position.get(r.code, ())),
            )
            for r in rows
        ]

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
                        "kind": c.kind,
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


def _in_category(category: str | None) -> ColumnElement[bool]:
    return CatalogPosition.category == category if category is not None else true()
