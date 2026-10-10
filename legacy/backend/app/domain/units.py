"""Поддержанные единицы ОКЕИ и понятия количественных характеристик."""

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class Unit:
    dimension: str
    factor: Decimal
    symbol: str
    pattern: str


UNITS = {
    "003": Unit("length", Decimal("0.001"), "мм", r"мм|миллиметр\w*"),
    "004": Unit("length", Decimal("0.01"), "см", r"см|сантиметр\w*"),
    "006": Unit("length", Decimal("1"), "м", r"м|метр\w*"),
    "008": Unit("length", Decimal("1000"), "км", r"км|километр\w*"),
    "039": Unit("length", Decimal("0.0254"), "дюйм", r'"|дюйм\w*'),
    "163": Unit("mass", Decimal("0.001"), "г", r"г|грамм\w*"),
    "166": Unit("mass", Decimal("1"), "кг", r"кг|килограмм\w*"),
    "168": Unit("mass", Decimal("1000"), "т", r"т|тонн\w*"),
    "111": Unit("volume", Decimal("0.001"), "мл", r"мл|см³|миллилитр\w*"),
    "112": Unit("volume", Decimal("1"), "л", r"л|дм³|литр\w*"),
    "796": Unit("count", Decimal("1"), "шт", r"шт\.?|штук\w*"),
}

CONCEPTS = {
    "ширина": ("ширин",),
    "длина": ("длин",),
    "высота": ("высот",),
    "глубина": ("глубин",),
    "толщина": ("толщин",),
    "диаметр": ("диаметр",),
    "масса": ("масс", "вес"),
    "объем": ("объем",),
    "рост": ("рост",),
    "количество": ("количеств",),
}
