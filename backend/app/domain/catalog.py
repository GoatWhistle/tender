"""Справочник КТРУ: позиции, их характеристики и допустимые значения, группы позиций.

Позиция — официальная запись КТРУ с кодом; характеристика принадлежит позиции: одинаковый код
характеристики в разных позициях не значит одинаковых допустимых значений. Значение —
качественное (текст) или количественное (точное число либо диапазон с открытыми или закрытыми
границами и единицей ОКЕИ). Отсутствующая граница и ноль — разные вещи.

Группа КТРУ — шаблон (`isTemplate`) или позиция без родителя; её конечные позиции — потомки по
`parentPositionInfo`, а группа без потомков — сама себе конечная позиция. Смысл полей XML —
`docs/Словарь данных КТРУ.md`.
"""

from collections.abc import Iterable
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


class CharacteristicKind(StrEnum):
    """Вид характеристики (`kind` в XML ЕИС): меняет ли заказчик значение и сколько выбирает."""

    fixed = "fixed"  # 1 — неизменяемая заказчиком
    single = "single"  # 2 — изменяемая, выбор одного значения
    multiple = "multiple"  # 3 — изменяемая, выбор нескольких значений


@dataclass(frozen=True)
class Characteristic:
    code: str
    name: str
    quantitative: bool
    required: bool
    kind: CharacteristicKind
    values: tuple[Value, ...] = ()

    @property
    def multi(self) -> bool:
        """Допускается выбор нескольких значений."""
        return self.kind == CharacteristicKind.multiple

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

    @property
    def group(self) -> str:
        """Код группы КТРУ: свой, если позиция — группа, иначе родителя."""
        if self.is_template or self.parent is None:
            return self.code
        return self.parent

    @property
    def is_group(self) -> bool:
        return self.group == self.code

    def char(self, name: str) -> Characteristic | None:
        for c in self.characteristics:
            if c.name == name:
                return c
        return None


@dataclass(frozen=True)
class Group:
    """Группа КТРУ и её конечные позиции. Шаблон с потомками конечной позицией не считается."""

    position: Position
    leaves: tuple[Position, ...]

    @classmethod
    def of(cls, position: Position, children: Iterable[Position]) -> "Group":
        """Группа `position` с потомками `children`; без потомков — сама себе конечная позиция."""
        return cls(position, tuple(children) or (position,))


def outside_tree(positions: Iterable[Position]) -> list[Position]:
    """Позиции, чья группа не найдена среди `positions`: родитель отсутствует или сам не группа."""
    positions = list(positions)
    groups = {p.code for p in positions if p.is_group}
    return [p for p in positions if p.group not in groups]


def _fmt(x: float) -> str:
    return str(int(x)) if float(x).is_integer() else f"{x:g}"
