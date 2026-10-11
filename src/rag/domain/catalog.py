from dataclasses import dataclass

FIXED = "1"
SINGLE = "2"
MULTIPLE = "3"

SUPPLY_UNIT = "Единица поставки"

OPS = {
    "greater": ">",
    "greaterOrEqual": "≥",
    "less": "<",
    "lessOrEqual": "≤",
}


@dataclass(frozen=True, slots=True)
class Value:
    text: str | None = None
    unit: str | None = None
    unit_code: str | None = None
    min: float | None = None
    min_op: str | None = None
    max: float | None = None
    max_op: str | None = None
    concrete: tuple[float, ...] = ()


@dataclass(frozen=True, slots=True)
class Characteristic:
    code: str
    name: str
    quantitative: bool
    kind: str
    required: bool
    values: tuple[Value, ...]


@dataclass(frozen=True, slots=True)
class Position:
    code: str
    name: str
    okpd2: str
    okpd2_name: str
    units: tuple[str, ...]
    rubrics: tuple[str, ...]
    is_template: bool
    parent: str | None
    characteristics: tuple[Characteristic, ...]
    no_new_features: bool = False


def _fmt(x: float) -> str:
    return f"{x:g}"


def value_text(v: Value) -> str:
    if v.text:
        return v.text
    parts = []
    if v.min is not None:
        parts.append(f"{OPS.get(v.min_op or '', '≥')} {_fmt(v.min)}")
    if v.max is not None:
        parts.append(f"{OPS.get(v.max_op or '', '≤')} {_fmt(v.max)}")
    if v.concrete:
        parts.append(", ".join(_fmt(c) for c in v.concrete))
    if v.unit:
        parts.append(v.unit)
    return " ".join(parts)


def labels(c: Characteristic) -> tuple[str, ...]:
    return tuple(dict.fromkeys(t for t in (value_text(v) for v in c.values) if t))


def joined(c: Characteristic) -> str:
    return "; ".join(labels(c))


def fixed_values(p: Position) -> dict[str, str]:
    return {
        c.name: "; ".join(value_text(v) for v in c.values)
        for c in p.characteristics
        if c.kind == FIXED
    }


def is_range(v: Value) -> bool:
    return not v.text and not v.concrete and (v.min is not None or v.max is not None)


def contains(v: Value, x: float) -> bool:
    if v.min is not None and (x < v.min or (x == v.min and v.min_op == "greater")):
        return False
    if v.max is not None and (x > v.max or (x == v.max and v.max_op == "less")):
        return False
    return is_range(v)


def position_text(p: Position) -> str:
    lines = [p.name, f"ОКПД2: {p.okpd2} {p.okpd2_name}"]
    if p.rubrics:
        lines.append("Рубрики: " + "; ".join(p.rubrics))
    for c in p.characteristics:
        values = "; ".join(t for t in (value_text(v) for v in c.values) if t)
        lines.append(f"{c.name}: {values}" if values else c.name)
    return "\n".join(lines)
