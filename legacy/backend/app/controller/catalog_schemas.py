"""Схемы справочника КТРУ в API."""

from decimal import Decimal

from pydantic import BaseModel

from app.domain.catalog import Characteristic, CharacteristicKind, Group, Position, Value


class ValueOut(BaseModel):
    code: str
    label: str
    text: str | None
    unit: str | None
    concrete: Decimal | None
    min: Decimal | None
    min_inclusive: bool | None
    max: Decimal | None
    max_inclusive: bool | None

    @classmethod
    def of(cls, v: Value) -> "ValueOut":
        return cls(
            code=v.code,
            label=v.label(),
            text=v.text,
            unit=v.unit,
            concrete=v.concrete,
            min=v.min,
            min_inclusive=None if v.min is None else v.min_inclusive,
            max=v.max,
            max_inclusive=None if v.max is None else v.max_inclusive,
        )


class CharacteristicOut(BaseModel):
    code: str
    name: str
    quantitative: bool
    required: bool
    kind: CharacteristicKind
    multi: bool
    values: list[ValueOut]

    @classmethod
    def of(cls, c: Characteristic) -> "CharacteristicOut":
        return cls(
            code=c.code,
            name=c.name,
            quantitative=c.quantitative,
            required=c.required,
            kind=c.kind,
            multi=c.multi,
            values=[ValueOut.of(v) for v in c.values],
        )


class PositionSummary(BaseModel):
    code: str
    name: str
    category: str
    okpd2: str
    is_template: bool
    group: str

    @classmethod
    def of(cls, p: Position) -> "PositionSummary":
        return cls(
            code=p.code,
            name=p.name,
            category=p.category,
            okpd2=p.okpd2,
            is_template=p.is_template,
            group=p.group,
        )


class PositionOut(PositionSummary):
    okpd2_name: str
    parent: str | None
    units: list[str]
    rubrics: list[str]
    characteristics: list[CharacteristicOut]

    @classmethod
    def of(cls, p: Position) -> "PositionOut":
        return cls(
            code=p.code,
            name=p.name,
            category=p.category,
            okpd2=p.okpd2,
            okpd2_name=p.okpd2_name,
            is_template=p.is_template,
            group=p.group,
            parent=p.parent,
            units=list(p.units),
            rubrics=list(p.rubrics),
            characteristics=[CharacteristicOut.of(c) for c in p.characteristics],
        )


class GroupOut(BaseModel):
    position: PositionSummary
    # Потомки группы; у группы без потомков — она сама.
    leaves: list[PositionSummary]

    @classmethod
    def of(cls, g: Group) -> "GroupOut":
        return cls(
            position=PositionSummary.of(g.position),
            leaves=[PositionSummary.of(p) for p in g.leaves],
        )
