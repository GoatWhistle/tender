import re
from collections import Counter, defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

MIN_SHARE = 0.04
TOP = 25
LIMIT = 6
OVERLAP = 0.5

SKIP = re.compile(
    r"страна|производител|бренд|торгов|модель|артикул|штрих|видео|упаковк|гарант|"
    r"серия|коллекц|комплектац|ндс|цена|ссылк|сертиф|^вид товаров|^вид продукции",
    re.IGNORECASE,
)

type Source = Literal["СТЕ", "ИИ"]


@dataclass(frozen=True, slots=True)
class SteItem:
    title: str
    characteristics: dict[str, str]


@dataclass(frozen=True, slots=True)
class Stat:
    name: str
    share: float
    values: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Suggestion:
    name: str
    unit: str
    options: tuple[str, ...]
    value: str
    evidence: str
    source: Source
    share: float | None
    why: str


def norm(name: str) -> str:
    return re.sub(r"[^а-яёa-z0-9]+", " ", name.lower()).strip()


def stem(name: str) -> frozenset[str]:
    return frozenset(w[:5] for w in norm(name).split() if len(w) > 2)


def similar(a: frozenset[str], b: frozenset[str]) -> bool:
    return bool(a) and len(a & b) / len(a | b) >= OVERLAP


def strip_unit(value: str, unit: str) -> str:
    value = value.strip()
    if unit and value.lower().endswith(unit.lower()):
        value = value[: -len(unit)].strip()
    return value


def summarize(analogs: Sequence[SteItem]) -> list[Stat]:
    if not analogs:
        return []
    count: Counter[str] = Counter()
    values: defaultdict[str, Counter[str]] = defaultdict(Counter)
    label: dict[str, str] = {}
    for item in analogs:
        for name, value in item.characteristics.items():
            if SKIP.search(name):
                continue
            key = norm(name)
            label.setdefault(key, name)
            count[key] += 1
            values[key][value.lower()] += 1
    return [
        Stat(label[k], n / len(analogs), tuple(v for v, _ in values[k].most_common(5)))
        for k, n in count.most_common(TOP)
        if n / len(analogs) >= MIN_SHARE
    ]
