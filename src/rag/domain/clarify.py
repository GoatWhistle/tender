from collections import Counter
from dataclasses import dataclass

from rag.domain.catalog import (
    FIXED,
    SUPPLY_UNIT,
    Characteristic,
    Position,
    Value,
    value_text,
)


@dataclass(frozen=True, slots=True)
class Question:
    name: str
    required: bool
    options: tuple[str, ...]
    counts: tuple[int, ...] = ()
    multiple: bool = False
    ranges: tuple[Value, ...] = ()

    @property
    def exact(self) -> bool:
        return bool(self.ranges) and not self.multiple

    @property
    def unit(self) -> str | None:
        return self.ranges[0].unit if self.ranges else None


type Picked = dict[str, tuple[str, ...]]


def _fixed(p: Position) -> dict[str, Characteristic]:
    return {c.name: c for c in p.characteristics if c.kind == FIXED}


def _labels(c: Characteristic) -> frozenset[str]:
    return frozenset(t for t in (value_text(v) for v in c.values) if t)


def _options(p: Position) -> dict[str, frozenset[str]]:
    values = {name: _labels(c) for name, c in _fixed(p).items()}
    if p.units:
        values[SUPPLY_UNIT] = frozenset(p.units)
    return values


def questions(leaves: list[Position], answers: dict[str, str | None]) -> list[Question]:
    per_leaf = [_options(p) for p in leaves]
    required = {n for p in leaves for n, c in _fixed(p).items() if c.required} | {
        SUPPLY_UNIT
    }
    out = []
    for name in sorted({n for chars in per_leaf for n in chars} - answers.keys()):
        if len({chars.get(name) for chars in per_leaf}) < 2:
            continue
        counts = Counter(label for chars in per_leaf for label in chars.get(name, ()))
        options = sorted(counts)
        out.append(
            Question(
                name,
                name in required,
                tuple(options),
                tuple(counts[o] for o in options),
            )
        )
    out.sort(
        key=lambda q: (
            q.name != SUPPLY_UNIT,
            not q.required,
            max(q.counts, default=0),
            q.name,
        )
    )
    return out


def narrow(leaves: list[Position], answers: dict[str, str | None]) -> list[Position]:
    def fits(p: Position) -> bool:
        chars = _options(p)
        return all(
            label is None or name not in chars or label in chars[name]
            for name, label in answers.items()
        )

    return [p for p in leaves if fits(p)]


def accept(q: Question, values: list[str]) -> tuple[str, ...]:
    picked = tuple(dict.fromkeys(v for v in values if v in q.options))
    return picked if picked and (q.multiple or len(picked) == 1) else ()
