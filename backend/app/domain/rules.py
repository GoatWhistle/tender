"""Проверка объединения допустимых значений, без моделей и побочных эффектов."""

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from fractions import Fraction

from app.domain.catalog import Bound, Characteristic, Position, Value
from app.domain.facts import CheckResult, ExclusionReason, Fact, RuleCheck, normalized
from app.domain.units import UNITS


@dataclass(frozen=True)
class _Interval:
    low: Fraction | None
    high: Fraction | None
    low_closed: bool = True
    high_closed: bool = True

    def contains(self, value: Fraction) -> bool:
        return (
            self.low is None or value > self.low or (value == self.low and self.low_closed)
        ) and (self.high is None or value < self.high or (value == self.high and self.high_closed))

    def intersects(self, low: Fraction, high: Fraction) -> bool:
        return (self.low is None or high > self.low or (high == self.low and self.low_closed)) and (
            self.high is None or low < self.high or (low == self.high and self.high_closed)
        )

    def covers(self, other: "_Interval") -> bool:
        low = self.low is None or (
            other.low is not None
            and (
                other.low > self.low
                or (other.low == self.low and (self.low_closed or not other.low_closed))
            )
        )
        high = self.high is None or (
            other.high is not None
            and (
                other.high < self.high
                or (other.high == self.high and (self.high_closed or not other.high_closed))
            )
        )
        return low and high

    def overlaps(self, other: "_Interval") -> bool:
        return not _below(self, other) and not _below(other, self)


def _below(a: _Interval, b: _Interval) -> bool:
    """Интервал `a` целиком левее `b`."""
    return (
        a.high is not None
        and b.low is not None
        and (a.high < b.low or (a.high == b.low and not (a.high_closed and b.low_closed)))
    )


def supported(characteristic: Characteristic) -> bool:
    if not characteristic.values:
        return False
    for value in characteristic.values:
        if not characteristic.quantitative:
            if value.text is None or any(
                n is not None for n in (value.concrete, value.min, value.max)
            ):
                return False
            continue
        if value.unit_code is not None and value.unit_code not in UNITS:
            return False
        if value.text is not None:
            return False
        if any(n is not None and not n.is_finite() for n in (value.concrete, value.min, value.max)):
            return False
        if value.concrete is not None:
            if any(n is not None for n in (value.min, value.max, value.min_op, value.max_op)):
                return False
        elif value.min is None and value.max is None:
            return False
        if value.min_op not in (None, Bound.greater, Bound.greater_or_equal):
            return False
        if value.max_op not in (None, Bound.less, Bound.less_or_equal):
            return False
        if (value.min_op and value.min is None) or (value.max_op and value.max is None):
            return False
        if (
            value.min is not None
            and value.max is not None
            and (
                value.min > value.max
                or (value.min == value.max and not (value.min_inclusive and value.max_inclusive))
            )
        ):
            return False
    return True


def _interval(value: Value) -> _Interval:
    unit = UNITS.get(value.unit_code or "")
    factor = Fraction(unit.factor) if unit else Fraction(1)
    if value.concrete is not None:
        point = Fraction(value.concrete) * factor
        return _Interval(point, point)
    return _Interval(
        Fraction(value.min) * factor if value.min is not None else None,
        Fraction(value.max) * factor if value.max is not None else None,
        value.min_inclusive,
        value.max_inclusive,
    )


def _dimension(unit_code: str | None) -> str | None:
    return UNITS[unit_code].dimension if unit_code else None


def canonical(value: Value) -> object:
    """Ключ равенства допустимых значений разных позиций: текст без регистра и `ё`, число —
    интервал в базовых единицах размерности с включённостью границ."""
    if value.text is not None:
        return "text", normalized(value.text)
    interval = _interval(value)
    return (
        "number",
        _dimension(value.unit_code),
        interval.low,
        interval.high,
        interval.low_closed,
        interval.high_closed,
    )


def _union(intervals: list[_Interval]) -> list[_Interval]:
    intervals.sort(key=lambda i: (i.low is not None, i.low or Fraction(0), not i.low_closed))
    merged: list[_Interval] = []
    for current in intervals:
        if not merged:
            merged.append(current)
            continue
        previous = merged[-1]
        touching = (
            previous.high is None
            or current.low is None
            or previous.high > current.low
            or (previous.high == current.low and (previous.high_closed or current.low_closed))
        )
        if not touching:
            merged.append(current)
        else:
            high = previous.high
            closed = previous.high_closed
            if high is not None:
                if current.high is None or current.high > high:
                    high, closed = current.high, current.high_closed
                elif current.high == high:
                    closed = closed or current.high_closed
            merged[-1] = _Interval(previous.low, high, previous.low_closed, closed)
    return merged


def check_rule(position: Position, fact: Fact) -> RuleCheck:
    return RuleCheck(fact.id, _check(position, fact))


def _check(position: Position, fact: Fact) -> CheckResult:
    if fact.status == "ambiguous" or fact.characteristic_name is None:
        return CheckResult.AMBIGUOUS
    characteristic = position.char(fact.characteristic_name)
    if characteristic is None:
        return CheckResult.NOT_APPLICABLE
    if not supported(characteristic):
        return CheckResult.UNSUPPORTED
    if fact.kind == "text":
        if characteristic.quantitative or not isinstance(fact.value, str):
            return CheckResult.UNSUPPORTED
        return (
            CheckResult.MATCH
            if any(normalized(v.text or "") == fact.value for v in characteristic.values)
            else CheckResult.MISMATCH
        )
    if not characteristic.quantitative:
        return CheckResult.UNSUPPORTED
    if fact.kind == "interval":
        return _check_interval(characteristic, fact.bounds)
    if isinstance(fact.value, str):
        return CheckResult.UNSUPPORTED
    unit = UNITS.get(fact.unit_code or "")
    if fact.unit_code is not None and unit is None:
        return CheckResult.UNSUPPORTED
    if any((v.unit_code is None) != (fact.unit_code is None) for v in characteristic.values):
        return CheckResult.AMBIGUOUS
    intervals = [
        _interval(v)
        for v in characteristic.values
        if _dimension(v.unit_code) == (unit.dimension if unit else None)
    ]
    # Fraction даёт точное сравнение Decimal после пересчёта, независимо от decimal context.
    factor = Fraction(unit.factor) if unit else Fraction(1)
    values = fact.value if isinstance(fact.value, tuple) else (fact.value, fact.value)
    low, high = (Fraction(v) * factor for v in values)
    if any(i.contains(low) and i.contains(high) for i in _union(intervals)):
        return CheckResult.MATCH
    if any(i.intersects(low, high) for i in intervals):
        return CheckResult.AMBIGUOUS
    return CheckResult.MISMATCH


def _check_interval(characteristic: Characteristic, bounds: Value | None) -> CheckResult:
    """Значение каталога как ответ: внутри объединения допустимых — `match`, частично —
    `ambiguous`."""
    if bounds is None or (bounds.unit_code is not None and bounds.unit_code not in UNITS):
        return CheckResult.UNSUPPORTED
    if any((v.unit_code is None) != (bounds.unit_code is None) for v in characteristic.values):
        return CheckResult.AMBIGUOUS
    target = _interval(bounds)
    dimension = _dimension(bounds.unit_code)
    intervals = [
        _interval(v) for v in characteristic.values if _dimension(v.unit_code) == dimension
    ]
    if any(i.covers(target) for i in _union(intervals)):
        return CheckResult.MATCH
    if any(i.overlaps(target) for i in intervals):
        return CheckResult.AMBIGUOUS
    return CheckResult.MISMATCH


def _number(value: Decimal) -> str:
    text = format(value, "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def _allowed(value: Value) -> str:
    if value.text is not None:
        return normalized(value.text)
    unit = value.unit or (UNITS[value.unit_code].symbol if value.unit_code in UNITS else "")
    if value.concrete is not None:
        text = _number(value.concrete)
    else:
        parts: list[str] = []
        if value.min is not None:
            parts.append(("не менее " if value.min_inclusive else "более ") + _number(value.min))
        if value.max is not None:
            parts.append(("не более " if value.max_inclusive else "менее ") + _number(value.max))
        text = " и ".join(parts)
    return f"{text} {unit}".strip()


def explain(position: Position, fact: Fact) -> ExclusionReason:
    characteristic = position.char(fact.characteristic_name or "")
    if characteristic is None:
        raise ValueError("Объяснение возможно только для характеристики позиции")
    allowed = "; ".join(_allowed(v) for v in characteristic.values)
    if isinstance(fact.value, str):
        given = fact.value
    elif isinstance(fact.value, tuple):
        given = "–".join(_number(v) for v in fact.value)
    else:
        given = _number(fact.value)
    if fact.unit_code in UNITS:
        given += " " + UNITS[fact.unit_code].symbol
    return ExclusionReason(
        fact.id,
        characteristic.name,
        allowed,
        given,
        f"для этой позиции {normalized(characteristic.name)}: {allowed}; указано {given}",
    )


def selection_conflict(position: Position, facts: Sequence[Fact]) -> ExclusionReason | None:
    """Принятые значения совместно должны соблюдать множественность характеристики."""
    for characteristic in position.characteristics:
        if characteristic.quantitative or characteristic.multi:
            continue
        selected = [
            f
            for f in facts
            if f.accepted and f.characteristic_name == characteristic.name and f.kind == "text"
        ]
        values = list(dict.fromkeys(str(f.value) for f in selected))
        if len(values) > 1:
            given = ", ".join(values)
            return ExclusionReason(
                selected[0].id,
                characteristic.name,
                "одно значение",
                given,
                f"«{characteristic.name}» допускает одно значение, указано: {given}",
            )
    return None
