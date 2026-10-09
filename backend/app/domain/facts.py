"""Факты с происхождением и результат проверки правила позиции."""

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from typing import Literal


@dataclass(frozen=True)
class FactSource:
    message_id: str
    quote: str
    start: int
    end: int


@dataclass(frozen=True)
class Fact:
    id: str
    field: str | None
    characteristic_name: str | None
    raw_value: str
    raw_unit: str | None
    value: Decimal | tuple[Decimal, Decimal] | str
    unit_code: str | None
    kind: Literal["number", "range", "text"]
    source: FactSource
    normalization_rule: str
    origin: Literal["parser"] = "parser"
    status: Literal["accepted_from_text", "ambiguous"] = "accepted_from_text"


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
