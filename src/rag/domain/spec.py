from dataclasses import dataclass
from math import inf
from typing import Literal

from rag.domain.catalog import (
    FIXED,
    MULTIPLE,
    Characteristic,
    Position,
    Value,
    contains,
    is_range,
    value_text,
)
from rag.domain.clarify import Question
from rag.domain.inference import Usage

SPREAD = 10

type Doubt = Literal["large", "small", "negative"]


@dataclass(frozen=True, slots=True)
class Extra:
    name: str
    value: str
    reason: str = ""

    @property
    def complete(self) -> bool:
        return bool(self.name.strip() and self.value.strip())


@dataclass(frozen=True, slots=True)
class Verdict:
    ok: bool
    problems: list[str]
    warnings: list[str]
    fixed: Extra | None
    usage: Usage | None = None


def _scale(c: Characteristic) -> dict[str, Value]:
    if not c.quantitative or not c.values or len({v.unit for v in c.values}) > 1:
        return {}
    if not all(is_range(v) for v in c.values):
        return {}
    labels = {value_text(v): v for v in c.values}
    return dict(
        sorted(
            labels.items(),
            key=lambda item: (
                -inf if item[1].min is None else item[1].min,
                inf if item[1].max is None else item[1].max,
            ),
        )
    )


def changeable(p: Position) -> list[Question]:
    out = []
    for c in p.characteristics:
        if c.kind == FIXED:
            continue
        multiple = c.kind == MULTIPLE
        if scale := _scale(c):
            out.append(
                Question(
                    c.name,
                    c.required,
                    tuple(scale),
                    multiple=multiple,
                    ranges=tuple(scale.values()),
                )
            )
            continue
        options = tuple(
            dict.fromkeys(t for t in (value_text(v) for v in c.values) if t)
        )
        out.append(Question(c.name, c.required, options, multiple=multiple))
    out.sort(key=lambda q: not q.required)
    return out


def _width(v: Value) -> tuple[float, float, float]:
    low = -inf if v.min is None else v.min
    high = inf if v.max is None else v.max
    return high - low, -low, high


def doubt(q: Question, x: float) -> Doubt | None:
    edges = [e for v in q.ranges for e in (v.min, v.max) if e is not None]
    if not edges:
        return None
    if x < 0 <= min(edges):
        return "negative"
    if max(edges) > 0 and x > SPREAD * max(edges):
        return "large"
    if min(edges) > 0 and 0 < x < min(edges) / SPREAD:
        return "small"
    return None


def band(q: Question, x: float) -> str | None:
    hits = [(label, v) for label, v in zip(q.options, q.ranges) if contains(v, x)]
    if not hits:
        return None
    return min(hits, key=lambda hit: _width(hit[1]))[0]
