"""Предложения enum-значений, допустимость сочетаний и политика автопринятия."""

import re
from collections.abc import Sequence
from dataclasses import dataclass

from app.domain.catalog import Position
from app.domain.facts import Fact, normalized


@dataclass(frozen=True)
class EnumSelection:
    values: tuple[str, ...]
    multiple: bool

    def permits(self, values: Sequence[str]) -> bool:
        return (
            bool(values) and (self.multiple or len(values) == 1) and set(values) <= set(self.values)
        )


@dataclass(frozen=True)
class EnumField:
    name: str
    selections: tuple[EnumSelection, ...]

    @property
    def values(self) -> tuple[str, ...]:
        return tuple(sorted({v for s in self.selections for v in s.values}))

    @property
    def multiple(self) -> bool:
        return any(s.multiple for s in self.selections)

    def permits(self, values: Sequence[str]) -> bool:
        return any(s.permits(values) for s in self.selections)


@dataclass(frozen=True)
class EnumProposal:
    id: str
    characteristic: str
    suggested: tuple[str, ...]
    options: tuple[str, ...]
    selections: tuple[EnumSelection, ...]
    reason: str


@dataclass(frozen=True)
class EnumResolution:
    proposal_id: str
    characteristic: str
    group: str
    revision: int
    messages: int
    facts: tuple[Fact, ...] = ()  # пусто — «не знаю»


@dataclass(frozen=True)
class AutoAcceptance:
    """Политика для конкретной ревизии и версии алгоритма; по умолчанию выключена.

    Точка сборки задаёт продуктовый порог; общая проводка по умолчанию оставляет его
    выключенным. Число от модели не является вероятностью правильности привязки.
    """

    threshold: float | None = None
    model_revision: str | None = None

    def accepts(self, score: float, revision: str, *, unambiguous: bool) -> bool:
        return (
            unambiguous
            and self.threshold is not None
            and 0 <= self.threshold <= 1
            and revision == self.model_revision
            and score >= self.threshold
        )


def enum_fields(positions: Sequence[Position]) -> tuple[EnumField, ...]:
    # Код характеристики локален позиции; имя и набор значений определяют общий вопрос.
    names: dict[str, str] = {}
    selections: dict[str, list[EnumSelection]] = {}
    for position in positions:
        for c in position.characteristics:
            if c.quantitative or not c.values or any(v.text is None for v in c.values):
                continue
            key = normalized(c.name).strip()
            names.setdefault(key, c.name)
            selection = EnumSelection(tuple(sorted({v.text for v in c.values if v.text})), c.multi)
            if selection not in selections.setdefault(key, []):
                selections[key].append(selection)
    return tuple(EnumField(names[key], tuple(value)) for key, value in selections.items())


# Части товара нужны для запрета переноса материала детали в общее поле «Материал».
# Список не классифицирует товары и не выбирает значение вместо модели.
_PARTS = (
    "каркас",
    "столешниц",
    "ножк",
    "ручк",
    "рукоят",
    "подошв",
    "верх",
    "подклад",
    "обивк",
    "спинк",
    "сиден",
    "опор",
    "лезви",
    "корпус",
    "наконечн",
)
_GENERIC = {
    "тип",
    "вид",
    "материал",
    "наличие",
    "характеристика",
    "товар",
    "изделие",
    "признак",
    "конструктивные",
    "особенности",
    "да",
    "нет",
    "для",
    "из",
    "на",
    "от",
}


def _stems(text: str) -> tuple[str, ...]:

    return tuple(
        re.sub(
            r"(?:ого|ому|ыми|ими|ая|яя|ое|ее|ые|ие|ый|ий|ой|ей|ом|ем|ов|ам|ах|а|я|ы|и|е|у|о|ь)$",
            "",
            w,
        )
        for w in re.findall(r"[а-яa-z]+", normalized(text))
        if w not in _GENERIC and len(w) > 2
    )


def _mentioned(value: str, fragment: str) -> bool:
    wanted, words = _stems(value), _stems(fragment)
    return bool(wanted) and all(
        any(
            len(stem) >= 3 and (word.startswith(stem) or stem.startswith(word))
            for word in words
            if len(word) >= 3
        )
        for stem in wanted
    )


def unambiguous_enum_binding(
    text: str, field: EnumField, value: str, fields: Sequence[EnumField]
) -> bool:
    """Явное имя/содержательное слово поля либо уникальное значение без чужой части товара.

    Это консервативная лексическая проверка привязки, не оценка вероятности. Модель проверяет
    само значение; её оценка не отменяет запрет переноса между частями товара.
    """

    field_parts = {p for p in _PARTS if p in normalized(field.name)}
    for fragment in re.split(r"[,;\n.!?]", normalized(text)):
        parts = {p for p in _PARTS if p in fragment}
        if parts and (not field_parts or not parts <= field_parts):
            continue
        named = normalized(field.name) in fragment or any(
            _mentioned(word, fragment) for word in _stems(field.name)
        )
        owners = [f for f in fields if any(_mentioned(v, fragment) for v in f.values)]
        unique_value = (
            _mentioned(value, fragment) and len(owners) == 1 and owners[0].name == field.name
        )
        if named or unique_value:
            return True
    return False
