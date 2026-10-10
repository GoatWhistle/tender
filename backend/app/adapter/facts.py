"""Детерминированный разбор только явно указанных значений характеристик группы."""

import re
from collections.abc import Sequence
from dataclasses import replace
from decimal import Decimal
from fractions import Fraction

from app.domain.catalog import Group
from app.domain.diagnostics import ValueAlias
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
    left = re.findall(r"\w+", normalized(re.split(r"[,.;]", text[:start])[-1]))[-2:]
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


_COMPONENTS = {
    "столешниц": "столешница",
    "каркас": "каркас",
    "ножк": "ножки",
    "основан": "основание",
    "обивк": "обивка",
}


def _component(text: str, start: int, end: int) -> str | None:
    left = re.split(r"[,.;\n]", text[:start])[-1]
    right = re.split(r"[,.;\n]", text[end:])[0]
    names = {name for stem, name in _COMPONENTS.items() if stem in normalized(left + " " + right)}
    return next(iter(names)) if len(names) == 1 else None


class DeterministicFactExtractor:
    def __init__(self, aliases: Sequence[ValueAlias] = ()) -> None:
        self._aliases = aliases

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
                prefix = message.text[: match.start()]
                clause = re.split(r"[.;\n]", prefix)[-1]
                explicit = next(
                    (n for n in names if normalized(clause.strip()) == normalized(n) + ":"), None
                )
                if ":" in clause:
                    concept, name = explicit, explicit
                code = next((c for c in UNITS if match.group("u" + c)), None)
                start, end = match.span()
                if explicit is not None:
                    start = len(prefix) - len(clause.lstrip())
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
            # Явное поле связывается только по полному имени. Неизвестное значение —
            # гипотеза для диагностики, не основание исключать позиции.
            enum_names = {
                c.name for p in group.leaves for c in p.characteristics if not c.quantitative
            }
            for name in sorted(enum_names, key=lambda n: (-len(n), n)):
                pattern = r"(?<!\w)" + re.escape(name) + r"\s*:\s*(?P<value>[^.;\n]+)"
                for match in re.finditer(pattern, message.text, re.IGNORECASE):
                    prefix = re.split(r"[.;\n]", message.text[: match.start()])[-1]
                    if prefix.strip():
                        continue
                    raw = match.group("value").strip()
                    start, end = (
                        match.start(),
                        match.start("value") + len(match.group("value").rstrip()),
                    )
                    occupied.append((start, end))
                    if not raw or re.search(r"\b(?:не|без)\b", normalized(raw)):
                        warnings.append("фрагмент с отрицанием не разобран")
                        continue
                    exact = normalized(raw) in texts and name in texts[normalized(raw)]
                    facts.append(
                        Fact(
                            f"{message.id}:{start}:{end}",
                            name,
                            name,
                            raw,
                            None,
                            normalized(raw),
                            None,
                            "text",
                            FactSource(message.id, message.text[start:end], start, end),
                            "explicit_field" if exact else "explicit_unverified",
                            status="accepted_from_text" if exact else "ambiguous",
                        )
                    )
            for alias in self._aliases:
                if alias.category != group.position.category or not all(
                    word in text for word in alias.context
                ):
                    continue
                if alias.characteristic not in texts.get(normalized(alias.canonical), set()):
                    continue
                for match in re.finditer(
                    r"(?<!\w)" + re.escape(alias.alias) + r"(?!\w)", message.text, re.IGNORECASE
                ):
                    start, end = match.span()
                    clause = re.split(r"[.;\n]", message.text[:start])[-1]
                    wrong_component = any(
                        stem in normalized(clause) and stem not in normalized(alias.characteristic)
                        for stem in ("каркас", "столешниц", "основан", "основ", "обив", "напыл")
                    )
                    if (
                        wrong_component
                        or ":" in clause
                        or _unsafe(message.text, start, match.group())
                    ):
                        continue
                    if any(a < end and start < b for a, b in occupied):
                        continue
                    occupied.append((start, end))
                    facts.append(
                        Fact(
                            f"{message.id}:{start}:{end}",
                            alias.characteristic,
                            alias.characteristic,
                            match.group(),
                            None,
                            normalized(match.group()),
                            None,
                            "text",
                            FactSource(message.id, match.group(), start, end),
                            "explicit_unverified",
                            status="ambiguous",
                        )
                    )
            # Нормализация Unicode может менять длину (например, İ.lower()).
            offsets = [i for i, char in enumerate(message.text) for _ in normalized(char)]
            for value in sorted(texts, key=lambda v: (-len(v), v)):
                fields = texts[value]
                for match in re.finditer(r"(?<!\w)" + re.escape(value) + r"(?!\w)", text):
                    start, end = offsets[match.start()], offsets[match.end() - 1] + 1
                    if any(a < end and start < b for a, b in occupied):
                        continue
                    occupied.append((start, end))
                    clause = re.split(r"[.;\n]", message.text[:start])[-1]
                    if ":" in clause:
                        continue
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
        by_id = {m.id: m.text for m in messages}
        facts = [
            replace(
                f, component=_component(by_id[f.source.message_id], f.source.start, f.source.end)
            )
            if f.source is not None
            else f
            for f in facts
        ]
        order = {m.id: i for i, m in enumerate(messages)}

        def place(fact: Fact) -> tuple[int, int]:
            assert fact.source is not None, "у факта парсера всегда есть цитата"
            return order[fact.source.message_id], fact.source.start

        facts.sort(key=place)
        unique: list[Fact] = []
        seen: dict[tuple[str, str | None], set[object]] = {}
        for fact in facts:
            name = fact.characteristic_name
            if name is not None:
                key = _canonical(fact)
                if key in seen.setdefault((name, fact.component), set()):
                    continue
                seen[(name, fact.component)].add(key)
            unique.append(fact)
        conflicts = {key for key, values in seen.items() if len(values) > 1}
        warnings.extend(
            f"противоречивые значения поля {name}" for name in sorted({key[0] for key in conflicts})
        )
        return tuple(
            replace(f, status="ambiguous")
            if (f.characteristic_name, f.component) in conflicts
            else f
            for f in unique
        ), tuple(dict.fromkeys(warnings))


def _canonical(fact: Fact) -> object:
    if isinstance(fact.value, str):
        return fact.kind, fact.value
    unit = UNITS.get(fact.unit_code or "")
    values = fact.value if isinstance(fact.value, tuple) else (fact.value, fact.value)
    factor = Fraction(unit.factor) if unit else Fraction(1)
    return unit.dimension if unit else None, tuple(Fraction(v) * factor for v in values)
