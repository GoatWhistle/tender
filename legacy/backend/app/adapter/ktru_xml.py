"""Справочник КТРУ из XML-выгрузки ЕИС — реализация порта `CatalogSource`. lxml импортирует
только этот модуль. Структура XML — `data/yandex_disk/КТРУ/Описание структуры xml с КТРУ.docx`."""

from decimal import Decimal, InvalidOperation
from pathlib import Path

from lxml import etree

from app.domain.catalog import (
    CATEGORIES,
    Bound,
    Characteristic,
    CharacteristicKind,
    Position,
    Value,
)

NS = {"oos": "http://zakupki.gov.ru/oos/types/1"}

KIND = {
    "1": CharacteristicKind.fixed,
    "2": CharacteristicKind.single,
    "3": CharacteristicKind.multiple,
}
# `choiceType` — только для старых выгрузок без `kind`: по описанию структуры он «используется в
# ведении КТРУ, не используется в применении», и в выгрузках организаторов `choiceType=2` стоит
# и у характеристик с выбором одного значения.
CHOICE_TYPE = {
    "1": CharacteristicKind.single,
    "2": CharacteristicKind.multiple,
    "3": CharacteristicKind.fixed,
}


class XmlKtruSource:
    """По файлу `<категория>.xml` на каждую категорию выгрузки в каталоге `xml_dir`. Неактуальные
    характеристики (`actual=false`) пропускаются."""

    def __init__(self, xml_dir: Path) -> None:
        self._xml_dir = xml_dir

    def load(self) -> list[Position]:
        out: list[Position] = []
        for category in CATEGORIES:
            out.extend(parse_xml(self._xml_dir / f"{category}.xml", category))
        return out


def parse_xml(path: Path, category: str) -> list[Position]:
    out = []
    for _, pos in etree.iterparse(str(path), tag=f"{{{NS['oos']}}}position"):
        d = pos.find("oos:data", NS)
        if d is None:
            continue
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
                    kind=_kind(c),
                    values=tuple(_value(v) for v in c.findall("oos:values/oos:value", NS)),
                )
            )
        rubrics = d.findall("oos:rubricators/oos:rubricatorInfo/oos:name", NS)
        out.append(
            Position(
                code=_t(d, "oos:code") or "",
                name=_t(d, "oos:name") or "",
                category=category,
                okpd2=_t(d, "oos:OKPD2/oos:code") or "",
                okpd2_name=_t(d, "oos:OKPD2/oos:name") or "",
                is_template=_t(d, "oos:isTemplate") == "true",
                parent=_t(d, "oos:parentPositionInfo/oos:code"),
                units=tuple(e.text for e in d.findall("oos:OKEIs/oos:OKEI/oos:name", NS) if e.text),
                rubrics=tuple(e.text for e in rubrics if e.text),
                characteristics=tuple(chars),
            )
        )
        pos.clear()
    return out


def _kind(c: etree._Element) -> CharacteristicKind:
    kind = KIND.get(_t(c, "oos:kind") or "")
    if kind is not None:
        return kind
    return CHOICE_TYPE.get(_t(c, "oos:choiceType") or "", CharacteristicKind.single)


def _t(el: etree._Element, path: str) -> str | None:
    r = el.find(path, NS)
    return r.text.strip() if r is not None and r.text else None


def _f(s: str | None) -> Decimal | None:
    if s is None:
        return None
    try:
        return Decimal(s.replace(",", "."))
    except InvalidOperation:
        return None


def _bound(s: str | None) -> Bound | None:
    return Bound(s) if s else None


def _value(v: etree._Element) -> Value:
    rng = v.find("oos:rangeSet/oos:valueRange", NS)
    return Value(
        code=_t(v, "oos:valueCode") or "",
        text=_t(v, "oos:qualityDescription"),
        unit=_t(v, "oos:OKEI/oos:name"),
        unit_code=_t(v, "oos:OKEI/oos:code"),
        concrete=_f(_t(v, "oos:valueSet/oos:concreteValue")),
        min=_f(_t(rng, "oos:min")) if rng is not None else None,
        min_op=_bound(_t(rng, "oos:minMathNotation")) if rng is not None else None,
        max=_f(_t(rng, "oos:max")) if rng is not None else None,
        max_op=_bound(_t(rng, "oos:maxMathNotation")) if rng is not None else None,
    )
