"""Явные изменения фактов и согласование активных утверждений."""

from collections.abc import Sequence
from dataclasses import dataclass, replace
from decimal import Decimal, InvalidOperation
from fractions import Fraction
from typing import Literal
from uuid import uuid4

from app.domain.catalog import CharacteristicKind, Group
from app.domain.errors import InvalidFactEdit
from app.domain.facts import Fact, normalized
from app.domain.sessions import FactEvent
from app.domain.units import UNITS

INACTIVE = {"superseded", "deleted"}


@dataclass(frozen=True)
class FactInput:
    characteristic_name: str
    raw_value: str
    raw_unit: str | None = None
    kind: Literal["number", "range", "text"] = "text"
    component: str | None = None

    def fact(self, group: Group) -> Fact:
        name = self.characteristic_name.strip()
        chars = [c for p in group.leaves for c in p.characteristics if c.name == name]
        if not chars or not self.raw_value.strip():
            raise InvalidFactEdit()
        code = next((c for c, u in UNITS.items() if self.raw_unit in {c, u.symbol}), None)
        if self.raw_unit and code is None:
            raise InvalidFactEdit("Неизвестная единица: используйте символ или код ОКЕИ")
        value: Decimal | tuple[Decimal, Decimal] | str = normalized(self.raw_value.strip())
        try:
            if self.kind == "number":
                value = Decimal(self.raw_value.replace(",", "."))
                if not value.is_finite():
                    raise InvalidFactEdit()
            elif self.kind == "range":
                a, b = self.raw_value.replace(",", ".").split("..")
                low, high = Decimal(a), Decimal(b)
                if not low.is_finite() or not high.is_finite() or low > high:
                    raise InvalidFactEdit()
                value = low, high
        except (ValueError, InvalidOperation) as error:
            raise InvalidFactEdit("Число или диапазон в формате 10..20 не распознан") from error
        if any(c.quantitative != (self.kind != "text") for c in chars):
            raise InvalidFactEdit("Тип значения не соответствует характеристике")
        return Fact(
            str(uuid4()),
            name,
            name,
            self.raw_value.strip(),
            UNITS[code].symbol if code else None,
            value,
            code,
            self.kind,
            None,
            "manual",
            origin="user",
            status="confirmed_by_user",
            component=self.component or None,
        )


def apply_history(
    facts: Sequence[Fact], history: Sequence[FactEvent], group: str
) -> tuple[Fact, ...]:
    result = {f.id: f for f in facts}
    for event in history:
        for fact in event.before:
            if fact.id in result or event.group == group:
                result[fact.id] = fact
        if event.group == group:
            for fact in event.after:
                result[fact.id] = fact
    return tuple(result.values())


def reconcile(facts: Sequence[Fact], group: Group) -> tuple[Fact, ...]:
    """Конфликт только одного поля/компонента, кроме допустимого множества."""
    buckets: dict[tuple[str, str | None], list[Fact]] = {}
    result = list(facts)
    for i, fact in enumerate(result):
        if fact.status in INACTIVE or fact.characteristic_name is None:
            continue
        if fact.status == "ambiguous" and fact.normalization_rule not in {
            "explicit_unverified",
            "correction_needs_binding",
        }:
            fact = replace(
                fact, status="confirmed_by_user" if fact.origin == "user" else "accepted_from_text"
            )
            result[i] = fact
        buckets.setdefault((fact.characteristic_name or "", component_key(fact)), []).append(fact)
    conflicts: set[str] = set()
    for (name, _), values in buckets.items():
        chars = [c for p in group.leaves for c in p.characteristics if c.name == name]
        multiple = chars and all(c.kind == CharacteristicKind.multiple for c in chars)
        keys = {canonical_fact(f) for f in values if f.origin != "catalog"}
        if len(keys) > 1 and not multiple:
            conflicts.update(f.id for f in values)
    return tuple(replace(f, status="ambiguous") if f.id in conflicts else f for f in result)


def canonical_fact(fact: Fact) -> object:
    if isinstance(fact.value, str):
        return fact.kind, normalized(fact.value)
    unit = UNITS.get(fact.unit_code or "")
    values = fact.value if isinstance(fact.value, tuple) else (fact.value, fact.value)
    factor = Fraction(unit.factor) if unit else Fraction(1)
    return unit.dimension if unit else None, tuple(Fraction(v) * factor for v in values)


def component_key(fact: Fact) -> str | None:
    text = normalized(fact.component or fact.characteristic_name or "")
    for stem, name in (
        ("столешниц", "столешница"),
        ("каркас", "каркас"),
        ("ножк", "ножки"),
        ("основан", "основание"),
        ("обивк", "обивка"),
    ):
        if stem in text:
            return name
    return fact.component
