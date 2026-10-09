"""Детерминированный разбор только явно указанных значений характеристик группы."""

import re
from collections.abc import Sequence
from dataclasses import replace
from decimal import Decimal
from fractions import Fraction

from app.domain.catalog import Group
from app.domain.facts import Fact, FactSource, normalized
from app.domain.sessions import Message
from app.domain.units import CONCEPTS, UNITS

_NUMBER = r"[+-]?\d+(?:[.,]\d+)?"
_UNIT = "|".join(f"(?P<u{code}>{unit.pattern})" for code, unit in UNITS.items())
_NUMERIC = re.compile(
    rf"(?<![\w.,])(?P<value>(?:от\s+)?(?P<first>{_NUMBER})"
    rf"(?:\s*(?:[-–]|до)\s*(?P<second>{_NUMBER}))?)"
    rf"(?:\s*(?P<unit>{_UNIT})(?!\w))?",
    re.IGNORECASE,
)
_DIMENSIONS = re.compile(rf"{_NUMBER}(?:\s*[×xх*]\s*{_NUMBER})+", re.IGNORECASE)


def _unsafe(text: str, start: int, raw: str) -> str | None:
    left = re.findall(r"\w+", normalized(text[:start]))[-2:]
    if any(word in {"не", "без"} for word in left):
        return "фрагмент с отрицанием не разобран"
    if (left and left[-1] in {"до", "от", "более", "менее"}) or (
        normalized(raw).startswith("от ") and "до" not in normalized(raw)
    ):
        return "полуоткрытый диапазон не разобран"
    return None


def _binding(text: str, start: int, names: set[str]) -> tuple[str | None, str | None]:
    words = re.findall(r"\w+", normalized(text[:start]))[-3:]
    for word in reversed(words):
        for concept, stems in CONCEPTS.items():
            if any(word.startswith(stem) for stem in stems):
                candidates = sorted(n for n in names if normalized(n).startswith(stems))
                if len(candidates) == 1:
                    return concept, candidates[0]
                exact = [n for n in candidates if normalized(n) == concept]
                return concept, exact[0] if len(exact) == 1 else None
    return None, None


class DeterministicFactExtractor:
    def extract(
        self, messages: Sequence[Message], group: Group
    ) -> tuple[tuple[Fact, ...], tuple[str, ...]]:
        names = {c.name for p in group.leaves for c in p.characteristics if c.quantitative}
        texts: dict[str, set[str]] = {}
        for position in group.leaves:
            for characteristic in position.characteristics:
                if not characteristic.quantitative:
                    for allowed in characteristic.values:
                        if allowed.text:
                            value = normalized(allowed.text)
                            if value not in {"да", "нет"} and not re.search(r"\d", value):
                                texts.setdefault(value, set()).add(characteristic.name)
        facts: list[Fact] = []
        warnings: list[str] = []
        for message in messages:
            text = normalized(message.text)
            dimensions = [m.span() for m in _DIMENSIONS.finditer(message.text)]
            if dimensions:
                warnings.append("размеры через × без порядка полей")
            for match in _NUMERIC.finditer(message.text):
                if any(a < match.end() and match.start() < b for a, b in dimensions):
                    continue
                warning = _unsafe(message.text, match.start(), match.group("value"))
                if warning:
                    warnings.append(warning)
                    continue
                first = Decimal(match.group("first").replace(",", "."))
                second = (
                    Decimal(match.group("second").replace(",", "."))
                    if match.group("second")
                    else None
                )
                if second is not None and first > second:
                    warnings.append("обратный диапазон не разобран")
                    continue
                concept, name = _binding(message.text, match.start(), names)
                code = next((c for c in UNITS if match.group("u" + c)), None)
                start, end = match.span()
                facts.append(
                    Fact(
                        f"{message.id}:{start}:{end}",
                        concept,
                        name,
                        message.text[match.start("value") : match.end("value")],
                        message.text[match.start("unit") : match.end("unit")] if code else None,
                        first if second is None else (first, second),
                        code,
                        "number" if second is None else "range",
                        FactSource(message.id, message.text[start:end], start, end),
                        "decimal_comma; okei" if code else "decimal_comma; unit_unspecified",
                        status="accepted_from_text" if name else "ambiguous",
                    )
                )
            occupied: list[tuple[int, int]] = []
            # Нормализация Unicode может менять длину (например, İ.lower()).
            offsets = [i for i, char in enumerate(message.text) for _ in normalized(char)]
            for value in sorted(texts, key=lambda v: (-len(v), v)):
                fields = texts[value]
                for match in re.finditer(r"(?<!\w)" + re.escape(value) + r"(?!\w)", text):
                    start, end = offsets[match.start()], offsets[match.end() - 1] + 1
                    if any(a < end and start < b for a, b in occupied):
                        continue
                    occupied.append((start, end))
                    warning = _unsafe(message.text, start, match.group())
                    if warning:
                        warnings.append(warning)
                        continue
                    name = next(iter(fields)) if len(fields) == 1 else None
                    facts.append(
                        Fact(
                            f"{message.id}:{start}:{end}",
                            name,
                            name,
                            message.text[start:end],
                            None,
                            value,
                            None,
                            "text",
                            FactSource(message.id, message.text[start:end], start, end),
                            "lower; ё→е",
                            status="accepted_from_text" if name else "ambiguous",
                        )
                    )
        order = {m.id: i for i, m in enumerate(messages)}
        facts.sort(key=lambda f: (order[f.source.message_id], f.source.start))
        unique: list[Fact] = []
        seen: dict[str, set[object]] = {}
        for fact in facts:
            name = fact.characteristic_name
            if name is not None:
                key = _canonical(fact)
                if key in seen.setdefault(name, set()):
                    continue
                seen[name].add(key)
            unique.append(fact)
        conflicts = {name for name, values in seen.items() if len(values) > 1}
        warnings.extend(f"противоречивые значения поля {name}" for name in sorted(conflicts))
        return tuple(
            replace(f, status="ambiguous") if f.characteristic_name in conflicts else f
            for f in unique
        ), tuple(dict.fromkeys(warnings))


def _canonical(fact: Fact) -> object:
    if isinstance(fact.value, str):
        return fact.kind, fact.value
    unit = UNITS.get(fact.unit_code or "")
    values = fact.value if isinstance(fact.value, tuple) else (fact.value, fact.value)
    factor = Fraction(unit.factor) if unit else Fraction(1)
    return unit.dimension if unit else None, tuple(Fraction(v) * factor for v in values)
