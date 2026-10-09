"""Справочник КТРУ: позиции, их характеристики и допустимые значения.

Позиция — официальная запись КТРУ с кодом; характеристика принадлежит позиции: одинаковый код
характеристики в разных позициях не значит одинаковых допустимых значений. Значение —
качественное (текст) или количественное (точное число либо диапазон с открытыми или закрытыми
границами и единицей ОКЕИ). Отсутствующая граница и ноль — разные вещи.
"""

from dataclasses import dataclass
from enum import StrEnum

# Категории выгрузки организаторов: по одному XML КТРУ и одной выгрузке СТЕ на категорию.
CATEGORIES = ("Одежда", "Мебель", "Инструменты")


class Bound(StrEnum):
    """Нотация границы диапазона, как в XML ЕИС."""

    greater = "greater"
    greater_or_equal = "greaterOrEqual"
    less = "less"
    less_or_equal = "lessOrEqual"


@dataclass(frozen=True)
class Value:
    code: str
    text: str | None = None  # качественное значение
    unit: str | None = None  # наименование ОКЕИ
    unit_code: str | None = None
    concrete: float | None = None
    min: float | None = None
    min_op: Bound | None = None
    max: float | None = None
    max_op: Bound | None = None

    @property
    def min_inclusive(self) -> bool:
        """Нижняя граница закрытая; граница без нотации — закрытая."""
        return self.min_op != Bound.greater

    @property
    def max_inclusive(self) -> bool:
        return self.max_op != Bound.less

    def contains(self, x: float) -> bool:
        """Число `x` допустимо этим значением."""
        if self.concrete is not None:
            return abs(self.concrete - x) < 1e-9
        if self.min is not None and not (x >= self.min if self.min_inclusive else x > self.min):
            return False
        if self.max is not None and not (x <= self.max if self.max_inclusive else x < self.max):
            return False
        return self.min is not None or self.max is not None

    def label(self) -> str:
        if self.text is not None:
            return self.text
        u = f" {self.unit}" if self.unit else ""
        if self.concrete is not None:
            return f"{_fmt(self.concrete)}{u}"
        parts = []
        if self.min is not None:
            parts.append(("≥" if self.min_inclusive else ">") + " " + _fmt(self.min))
        if self.max is not None:
            parts.append(("≤" if self.max_inclusive else "<") + " " + _fmt(self.max))
        return " и ".join(parts) + u


@dataclass(frozen=True)
class Characteristic:
    code: str
    name: str
    quantitative: bool
    required: bool
    multi: bool  # choiceType=2 — допускается выбор нескольких значений
    values: tuple[Value, ...] = ()

    @property
    def units(self) -> list[str]:
        return sorted({v.unit for v in self.values if v.unit})


@dataclass(frozen=True)
class Position:
    code: str
    name: str
    category: str
    okpd2: str
    okpd2_name: str
    is_template: bool
    parent: str | None
    units: tuple[str, ...]
    rubrics: tuple[str, ...]
    characteristics: tuple[Characteristic, ...] = ()

    def char(self, name: str) -> Characteristic | None:
        for c in self.characteristics:
            if c.name == name:
                return c
        return None


def _fmt(x: float) -> str:
    return str(int(x)) if float(x).is_integer() else f"{x:g}"
