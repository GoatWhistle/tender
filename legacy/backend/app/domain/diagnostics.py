"""Диагностика сохраняет исходник; предложения не являются принятыми фактами."""

from dataclasses import dataclass
from typing import Literal

from app.domain.catalog import Characteristic, Group, Position
from app.domain.facts import Fact, FactSource
from app.domain.rules import explain


@dataclass(frozen=True)
class DiagnosticScope:
    group_code: str | None
    position_codes: tuple[str, ...]
    complete: bool


@dataclass(frozen=True)
class RuleRef:
    position_code: str
    characteristic_code: str
    characteristic_name: str
    value_codes: tuple[str, ...]


DiagnosticKind = Literal["typo", "value_not_in_catalog", "out_of_range", "synonym"]


@dataclass(frozen=True)
class Diagnostic:
    kind: DiagnosticKind
    fact_id: str | None
    source_quote: str
    source: FactSource
    expected: tuple[str, ...]
    suggestion: str | None
    rule_ref: tuple[RuleRef, ...]
    scope: DiagnosticScope
    requires_confirmation: bool
    explanation: str
    candidates: tuple[str, ...] = ()
    alias_source: str | None = None


@dataclass(frozen=True)
class SpellingSuggestion:
    source: FactSource
    replacement: str


@dataclass(frozen=True)
class ValueAlias:
    alias: str
    canonical: str
    characteristic: str
    category: str
    source: str
    context: tuple[str, ...] = ()


def close_enum(raw: str, value: str, distance: int) -> bool:
    length = max(len(raw), len(value))
    return (
        (length <= 3 and distance == 0)
        or (4 <= length <= 7 and distance <= 1)
        or (length >= 8 and distance <= 2 and distance / length <= 0.25)
    )


def explain_diagnostic(
    kind: DiagnosticKind,
    fact: Fact,
    group: Group,
    rules: list[tuple[Position, Characteristic]],
    suggestion: str | None,
    candidates: tuple[str, ...],
) -> Diagnostic:
    assert fact.source is not None
    allowed = tuple(dict.fromkeys(explain(p, fact).allowed for p, _ in rules))
    refs = tuple(RuleRef(p.code, c.code, c.name, tuple(v.code for v in c.values)) for p, c in rules)
    return Diagnostic(
        kind=kind,
        fact_id=fact.id,
        source_quote=fact.source.quote,
        source=fact.source,
        expected=allowed,
        suggestion=suggestion,
        rule_ref=refs,
        scope=DiagnosticScope(group.position.code, tuple(p.code for p in group.leaves), True),
        requires_confirmation=True,
        explanation=(
            f"В группе допустимо: {'; '.join(allowed)}; указано {explain(rules[0][0], fact).given}"
        ),
        candidates=candidates,
    )
