"""Поиск групп КТРУ по описанию товара: нормализация текста, код КТРУ в тексте, синонимы и
результат поиска с вкладом каждого метода.

Метод и правило замера — `docs/search.md`. Нормализация нужна только для сравнения: исходный
текст описания в ответе не меняется.
"""

import re
from dataclasses import dataclass
from enum import StrEnum

from app.domain.catalog import Position

# Код позиции КТРУ: ОКПД2 и восьмизначный номер. Код ОКПД2 без номера — не код КТРУ.
KTRU_CODE = re.compile(r"(?<![\d.])\d{2}\.\d{2}\.\d{2}\.\d{3}-\d{8}(?!\d)")


def normalize(text: str) -> str:
    """Регистр, пробельные символы подряд и `ё/е` — для сравнения, не для показа."""
    return " ".join(text.lower().replace("ё", "е").split())


def find_ktru_codes(text: str) -> list[str]:
    """Коды КТРУ в тексте по порядку, без повторов."""
    return list(dict.fromkeys(KTRU_CODE.findall(text)))


def phrase_pattern(phrase: str) -> re.Pattern[str]:
    """Шаблон `phrase` целым словом или фразой: «стол» не находится в «столешница»."""
    return re.compile(rf"(?<!\w){re.escape(phrase)}(?!\w)")


def contains_phrase(text: str, phrase: str) -> bool:
    """`phrase` — целое слово или фраза внутри `text`; оба аргумента уже нормализованы."""
    return phrase_pattern(phrase).search(text) is not None


@dataclass(frozen=True)
class Alias:
    """Запись словаря синонимов: бытовое название группы. В поиске — только `reviewed`;
    `source` — откуда запись: `manual`, `smoke_v0`, выгрузки СТЕ."""

    group_code: str
    alias: str
    source: str
    reviewed: bool


class Method(StrEnum):
    """Методы поиска, ранжированные списки которых сливаются RRF."""

    lexical = "lexical"
    vector = "vector"
    alias = "alias"


class FoundBy(StrEnum):
    code = "code"  # код КТРУ из текста
    description = "description"


@dataclass(frozen=True)
class Hit:
    """Строка ранжированного списка метода: ключ документа и скор метода."""

    key: str
    score: float


@dataclass(frozen=True)
class Contribution:
    """Вклад метода в итоговый скор группы: ранг в списке метода (с 1) и слагаемое RRF.
    Метод без попадания — `rank = None`, слагаемое 0."""

    method: Method
    rank: int | None
    score: float


@dataclass(frozen=True)
class GroupMatch:
    """Найденная группа: `score` — сумма слагаемых `methods`."""

    group: Position
    score: float
    methods: tuple[Contribution, ...]
    found_by: FoundBy


@dataclass(frozen=True)
class SearchMessage:
    code: str
    text: str


@dataclass(frozen=True)
class SearchResult:
    groups: tuple[GroupMatch, ...]
    messages: tuple[SearchMessage, ...] = ()
