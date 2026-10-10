"""Факты с происхождением и результат проверки правила позиции."""

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from typing import Literal

from app.domain.catalog import Value


@dataclass(frozen=True)
class FactSource:
    message_id: str
    quote: str
    start: int
    end: int


FactStatus = Literal[
    "accepted_from_text",
    "accepted_from_model",
    "proposed",
    "ambiguous",
    "confirmed_by_user",
    "derived_from_catalog",
    # замещён ответом пользователя по тому же полю: остаётся в истории, в проверках не участвует
    "superseded",
    "deleted",
]
ACCEPTED = frozenset(
    {"accepted_from_text", "accepted_from_model", "confirmed_by_user", "derived_from_catalog"}
)


@dataclass(frozen=True)
class Fact:
    id: str
    field: str | None
    characteristic_name: str | None
    raw_value: str
    raw_unit: str | None
    value: Decimal | tuple[Decimal, Decimal] | str
    unit_code: str | None
    # interval — ответ значением каталога: `value` — его подпись, границы — в `bounds`
    kind: Literal["number", "range", "text", "interval"]
    # у ответа пользователя без цитаты и у значения из каталога источника в тексте нет
    source: FactSource | None
    normalization_rule: str
    origin: Literal["parser", "user", "catalog", "decision"] = "parser"
    status: FactStatus = "accepted_from_text"
    bounds: Value | None = None
    component: str | None = None
    superseded_by: str | None = None

    model_revision: str | None = None
    model_score: float | None = None

    @property
    def accepted(self) -> bool:
        """Факт принят и привязан к характеристике: им можно исключать позиции."""
        return self.status in ACCEPTED and self.characteristic_name is not None


class CheckResult(StrEnum):
    MATCH = "match"
    MISMATCH = "mismatch"
    UNKNOWN = "unknown"
    AMBIGUOUS = "ambiguous"
    NOT_APPLICABLE = "not_applicable"
    UNSUPPORTED = "unsupported"


@dataclass(frozen=True)
class RuleCheck:
    fact_id: str | None
    result: CheckResult


@dataclass(frozen=True)
class ExclusionReason:
    fact_id: str
    characteristic: str
    allowed: str
    given: str
    text: str


def normalized(text: str) -> str:
    return text.lower().replace("ё", "е")


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
