"""Загрузка справочника КТРУ из XML-выгрузки ЕИС в компактные структуры."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from lxml import etree

NS = {"oos": "http://zakupki.gov.ru/oos/types/1"}
CATEGORIES = ("Одежда", "Мебель", "Инструменты")

DATA_DIR = Path(__file__).resolve().parents[3] / "data" / "yandex_disk"
XML_DIR = DATA_DIR / "КТРУ" / "xml"


@dataclass
class Value:
    code: str
    text: str | None = None  # качественное значение
    unit: str | None = None  # наименование ОКЕИ
    unit_code: str | None = None
    concrete: float | None = None
    min: float | None = None
    min_op: str | None = None  # greater / greaterOrEqual
    max: float | None = None
    max_op: str | None = None  # less / lessOrEqual

    def contains(self, x: float) -> bool:
        if self.concrete is not None:
            return abs(self.concrete - x) < 1e-9
        if self.min is not None:
            if self.min_op == "greater" and not x > self.min:
                return False
            if self.min_op != "greater" and not x >= self.min:
                return False
        if self.max is not None:
            if self.max_op == "less" and not x < self.max:
                return False
            if self.max_op != "less" and not x <= self.max:
                return False
        return self.min is not None or self.max is not None

    def label(self) -> str:
        if self.text is not None:
            return self.text
        u = f" {self.unit}" if self.unit else ""
        if self.concrete is not None:
            return f"{_fmt(self.concrete)}{u}"
        parts = []
        if self.min is not None:
            parts.append((">" if self.min_op == "greater" else "≥") + " " + _fmt(self.min))
        if self.max is not None:
            parts.append(("<" if self.max_op == "less" else "≤") + " " + _fmt(self.max))
        return " и ".join(parts) + u


@dataclass
class Characteristic:
    code: str
    name: str
    quantitative: bool
    required: bool
    multi: bool  # choiceType=2 — допускается выбор нескольких значений
    values: list[Value] = field(default_factory=list)

    @property
    def units(self) -> list[str]:
        return sorted({v.unit for v in self.values if v.unit})


@dataclass
class Position:
    code: str
    name: str
    category: str
    okpd2: str
    okpd2_name: str
    is_template: bool
    parent: str | None
    units: list[str]
    rubrics: list[str]
    characteristics: list[Characteristic] = field(default_factory=list)

    def char(self, name: str) -> Characteristic | None:
        for c in self.characteristics:
            if c.name == name:
                return c
        return None


def _fmt(x: float) -> str:
    return str(int(x)) if float(x).is_integer() else f"{x:g}"


def _t(el, path: str) -> str | None:
    r = el.find(path, NS)
    return r.text.strip() if r is not None and r.text else None


def _f(s: str | None) -> float | None:
    if s is None:
        return None
    try:
        return float(s.replace(",", "."))
    except ValueError:
        return None


def _parse_value(v) -> Value:
    val = Value(code=_t(v, "oos:valueCode") or "")
    q = _t(v, "oos:qualityDescription")
    if q is not None:
        val.text = q
    val.unit = _t(v, "oos:OKEI/oos:name")
    val.unit_code = _t(v, "oos:OKEI/oos:code")
    val.concrete = _f(_t(v, "oos:valueSet/oos:concreteValue"))
    rng = v.find("oos:rangeSet/oos:valueRange", NS)
    if rng is not None:
        val.min = _f(_t(rng, "oos:min"))
        val.min_op = _t(rng, "oos:minMathNotation")
        val.max = _f(_t(rng, "oos:max"))
        val.max_op = _t(rng, "oos:maxMathNotation")
    return val


def parse_xml(path: Path, category: str) -> list[Position]:
    out = []
    for _, pos in etree.iterparse(str(path), tag=f"{{{NS['oos']}}}position"):
        d = pos.find("oos:data", NS)
        chars = []
        for c in d.findall("oos:characteristics/oos:characteristic", NS):
            if _t(c, "oos:actual") == "false":
                continue
            chars.append(
                Characteristic(
                    code=_t(c, "oos:code") or "",
                    name=_t(c, "oos:name") or "",
                    quantitative=_t(c, "oos:type") == "2",
                    required=_t(c, "oos:isRequired") == "true",
                    multi=_t(c, "oos:choiceType") == "2",
                    values=[_parse_value(v) for v in c.findall("oos:values/oos:value", NS)],
                )
            )
        out.append(
            Position(
                code=_t(d, "oos:code") or "",
                name=_t(d, "oos:name") or "",
                category=category,
                okpd2=_t(d, "oos:OKPD2/oos:code") or "",
                okpd2_name=_t(d, "oos:OKPD2/oos:name") or "",
                is_template=_t(d, "oos:isTemplate") == "true",
                parent=_t(d, "oos:parentPositionInfo/oos:code"),
                units=[e.text for e in d.findall("oos:OKEIs/oos:OKEI/oos:name", NS) if e.text],
                rubrics=[e.text for e in d.findall("oos:rubricators/oos:rubricatorInfo/oos:name", NS) if e.text],
                characteristics=chars,
            )
        )
        pos.clear()
    return out


def load_positions(xml_dir: Path = XML_DIR) -> list[Position]:
    out: list[Position] = []
    for cat in CATEGORIES:
        out.extend(parse_xml(xml_dir / f"{cat}.xml", cat))
    return out


def dump_json(positions: list[Position], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([asdict(p) for p in positions], ensure_ascii=False))


def load_json(path: Path) -> list[Position]:
    out = []
    for p in json.loads(path.read_text()):
        chars = [
            Characteristic(**{**c, "values": [Value(**v) for v in c["values"]]})
            for c in p.pop("characteristics")
        ]
        out.append(Position(**p, characteristics=chars))
    return out
