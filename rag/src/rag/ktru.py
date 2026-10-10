import io
import zipfile
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from xml.etree.ElementTree import Element, iterparse

from rag.models import Characteristic, Position, Value

O = "{http://zakupki.gov.ru/oos/types/1}"

OPS = {
    "greater": ">",
    "greaterOrEqual": "≥",
    "less": "<",
    "lessOrEqual": "≤",
}


def _t(el: Element, path: str) -> str | None:
    found = el.find(path)
    if found is None or found.text is None:
        return None
    return found.text.strip()


def _num(s: str | None) -> float | None:
    if s is None:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _value(v: Element) -> Value:
    rng = v.find(f"{O}rangeSet/{O}valueRange")
    concrete = tuple(
        x
        for x in (_num(c.text) for c in v.findall(f"{O}valueSet/{O}concreteValue"))
        if x is not None
    )
    return Value(
        text=_t(v, f"{O}qualityDescription"),
        unit=_t(v, f"{O}OKEI/{O}name"),
        unit_code=_t(v, f"{O}OKEI/{O}code"),
        min=_num(_t(rng, f"{O}min")) if rng is not None else None,
        min_op=_t(rng, f"{O}minMathNotation") if rng is not None else None,
        max=_num(_t(rng, f"{O}max")) if rng is not None else None,
        max_op=_t(rng, f"{O}maxMathNotation") if rng is not None else None,
        concrete=concrete,
    )


def _characteristic(c: Element) -> Characteristic:
    return Characteristic(
        code=_t(c, f"{O}code") or "",
        name=_t(c, f"{O}name") or "",
        quantitative=_t(c, f"{O}type") == "2",
        kind=_t(c, f"{O}kind") or "",
        required=_t(c, f"{O}isRequired") == "true",
        values=tuple(_value(v) for v in c.findall(f"{O}values/{O}value")),
    )


def _position(d: Element) -> Position:
    return Position(
        code=_t(d, f"{O}code") or "",
        name=_t(d, f"{O}name") or "",
        okpd2=_t(d, f"{O}OKPD2/{O}code") or "",
        okpd2_name=_t(d, f"{O}OKPD2/{O}name") or "",
        units=tuple(
            n for n in (_t(u, f"{O}name") for u in d.findall(f"{O}OKEIs/{O}OKEI")) if n
        ),
        rubrics=tuple(
            n
            for n in (
                _t(r, f"{O}name") for r in d.findall(f"{O}rubricators/{O}rubricatorInfo")
            )
            if n
        ),
        is_template=_t(d, f"{O}isTemplate") == "true",
        parent=_t(d, f"{O}parentPositionInfo/{O}code"),
        characteristics=tuple(
            _characteristic(c)
            for c in d.findall(f"{O}characteristics/{O}characteristic")
            if _t(c, f"{O}actual") != "false"
        ),
    )


def to_dict(el: Element) -> Any:
    children = list(el)
    if not children:
        return (el.text or "").strip()
    out: dict[str, Any] = {}
    for c in children:
        key = c.tag.split("}")[-1]
        v = to_dict(c)
        if key not in out:
            out[key] = v
        elif isinstance(out[key], list):
            out[key].append(v)
        else:
            out[key] = [out[key], v]
    return out


def iter_records(zip_path: Path) -> Iterator[tuple[Position, dict[str, Any]]]:
    with zipfile.ZipFile(zip_path) as outer:
        for info in sorted(outer.infolist(), key=lambda i: i.filename):
            if not info.filename.endswith(".zip"):
                continue
            with zipfile.ZipFile(io.BytesIO(outer.read(info))) as inner:
                for xml in inner.infolist():
                    if "_actual_" not in xml.filename:
                        continue
                    with inner.open(xml) as f:
                        for _, el in iterparse(f):
                            if el.tag != f"{O}position":
                                continue
                            d = el.find(f"{O}data")
                            if d is not None and _t(d, f"{O}status") == "ACTIVE":
                                yield _position(d), to_dict(el)
                            el.clear()


def iter_positions(zip_path: Path) -> Iterator[Position]:
    with zipfile.ZipFile(zip_path) as outer:
        for info in sorted(outer.infolist(), key=lambda i: i.filename):
            if not info.filename.endswith(".zip"):
                continue
            with zipfile.ZipFile(io.BytesIO(outer.read(info))) as inner:
                for xml in inner.infolist():
                    if "_actual_" not in xml.filename:
                        continue
                    with inner.open(xml) as f:
                        for _, el in iterparse(f):
                            if el.tag != f"{O}position":
                                continue
                            d = el.find(f"{O}data")
                            if d is not None and _t(d, f"{O}status") == "ACTIVE":
                                yield _position(d)
                            el.clear()


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


def position_text(p: Position) -> str:
    lines = [p.name, f"ОКПД2: {p.okpd2} {p.okpd2_name}"]
    if p.rubrics:
        lines.append("Рубрики: " + "; ".join(p.rubrics))
    for c in p.characteristics:
        values = "; ".join(t for t in (value_text(v) for v in c.values) if t)
        lines.append(f"{c.name}: {values}" if values else c.name)
    return "\n".join(lines)
