"""Проверка полной группы, независимо от сужения кандидатов."""

from collections.abc import Sequence
from dataclasses import replace

from app.domain.catalog import Group
from app.domain.diagnostics import Diagnostic, close_enum, explain_diagnostic
from app.domain.facts import CheckResult, Fact, normalized
from app.domain.rules import check_rule, supported
from app.domain.sessions import Message
from app.domain.units import UNITS
from app.usecase.interface import EnumMatcher, ValueAliases


class Diagnostics:
    def __init__(self, matcher: EnumMatcher, aliases: ValueAliases | None = None) -> None:
        self._matcher = matcher
        self._aliases = aliases.all() if aliases else ()

    def run(
        self, facts: Sequence[Fact], group: Group, messages: Sequence[Message] = ()
    ) -> tuple[Diagnostic, ...]:
        output: list[Diagnostic] = []
        if any(p.is_template for p in group.leaves):
            return ()
        for fact in facts:
            if (
                fact.source is None
                or fact.characteristic_name is None
                or fact.status == "superseded"
            ):
                continue
            rules = [(p, p.char(fact.characteristic_name)) for p in group.leaves]
            # Полнота поля: отсутствие или неподдержанное правило хотя бы в одной
            # позиции запрещает доказательство отсутствия во всей группе.
            if not rules or any(c is None or not supported(c) for _, c in rules):
                continue
            known = [(p, c) for p, c in rules if c is not None]
            if fact.kind == "text":
                if any(c.quantitative for _, c in known):
                    continue
                values = sorted({v.text for _, c in known for v in c.values if v.text})
                if any(normalized(v) == fact.value for v in values):
                    continue
                if fact.normalization_rule not in {"explicit_field", "explicit_unverified"}:
                    continue
                aliases = [
                    a
                    for a in self._aliases
                    if normalized(a.alias) == normalized(fact.raw_value)
                    and a.characteristic == fact.characteristic_name
                    and a.category == group.position.category
                    and any(normalized(a.canonical) == normalized(v) for v in values)
                    and all(
                        word
                        in normalized(
                            next((m.text for m in messages if m.id == fact.source.message_id), "")
                        )
                        for word in a.context
                    )
                ]
                if len(aliases) == 1:
                    alias = aliases[0]
                    item = explain_diagnostic("synonym", fact, group, known, alias.canonical, ())
                    output.append(
                        replace(
                            item,
                            requires_confirmation=False,
                            alias_source=alias.source,
                            explanation=f"Проверенный синоним для {alias.characteristic}: "
                            f"{alias.alias} → {alias.canonical}. Источник: {alias.source}",
                        )
                    )
                    continue
                ranked = self._matcher.rank(fact.raw_value, values)
                close = tuple(
                    v for v, distance in ranked if close_enum(fact.raw_value, v, distance)
                )
                output.append(
                    explain_diagnostic(
                        "typo" if close else "value_not_in_catalog",
                        fact,
                        group,
                        known,
                        close[0] if len(close) == 1 else None,
                        close or tuple(v for v, _ in ranked[:3]),
                    )
                )
            elif fact.accepted:
                checks = [check_rule(p, fact).result for p, _ in known]
                if all(c == CheckResult.MISMATCH for c in checks):
                    units = []
                    if fact.kind == "number" and fact.unit_code in {"003", "004", "006"}:
                        for code in ("003", "004", "006"):
                            if code != fact.unit_code and any(
                                check_rule(p, replace(fact, unit_code=code)).result
                                == CheckResult.MATCH
                                for p, _ in known
                            ):
                                units.append(f"{fact.raw_value} {UNITS[code].symbol}")
                    output.append(
                        explain_diagnostic(
                            "out_of_range",
                            fact,
                            group,
                            known,
                            units[0] if len(units) == 1 else None,
                            tuple(units),
                        )
                    )
        return tuple(output)
