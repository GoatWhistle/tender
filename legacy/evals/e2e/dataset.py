"""Наборы сквозного замера: загрузка и проверка по справочнику КТРУ.

`dev_v1.json` — 60 кейсов разработки, `ste_holdout_v1.csv` — holdout реальных СТЕ; формат —
`evals/datasets/README.md`. Проверка ловит то, что разметчик проверить глазами не успеет:
группы и коды существуют и связаны, среди групп нет обобщённых позиций уровня ОКПД2,
характеристики и значения есть у допустимых позиций,
`out_of_range` действительно вне правил, а набор кодов совпадает с позициями, которым не
противоречат размеченные факты.

Запуск: cd backend && uv run python ../evals/e2e/dataset.py — печатает проблемы и
предупреждения; код возврата 1, если есть проблемы.
"""

import csv
import json
import pathlib
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[2]
DATASETS = ROOT / "evals" / "datasets"
DEV = DATASETS / "dev_v1.json"
HOLDOUT = DATASETS / "ste_holdout_v1.csv"
NONE = "НЕТ"

KINDS = {"typo", "value_not_in_catalog", "out_of_range", "synonym"}
TAGS = {
    "complete",
    "incomplete",
    "same_name",
    "paraphrase",
    "negation",
    "typo",
    "synonym",
    "units",
    "correction",
    "out_of_scope",
    "out_of_range",
    "value_not_in_catalog",
}


@dataclass
class HoldoutRow:
    ste_id: str
    category: str
    name: str
    groups: list[str]  # пусто — «НЕТ»
    checked: bool
    raw: dict[str, str] = field(repr=False)


def text_of(case: dict[str, Any]) -> str:
    """Текст сессии так, как его видит поиск: сообщения через перевод строки."""
    return "\n".join(case["messages"])


def load_dev(path: pathlib.Path = DEV) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return data


def load_holdout(path: pathlib.Path = HOLDOUT) -> list[HoldoutRow]:
    with path.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    return [
        HoldoutRow(
            ste_id=r["ste_id"],
            category=r["category"],
            name=r["name"],
            groups=[]
            if r["label"].strip() == NONE
            else [c.strip() for c in r["label"].split(";") if c.strip()],
            checked=r["checked"].strip().lower() in {"да", "yes", "true", "1"},
            raw=r,
        )
        for r in rows
    ]


class Catalog:
    """Позиции КТРУ и дерево групп — правила домена продукта (`Position.is_group`, `Group.of`)."""

    def __init__(self, positions: list[Any]) -> None:
        from app.domain.catalog import Group

        self.positions = {p.code: p for p in positions}
        children: dict[str, list[Any]] = defaultdict(list)
        for p in positions:
            if p.parent is not None:
                children[p.parent].append(p)
        self.groups = {
            p.code: Group.of(p, children[p.code]) for p in positions if p.is_group
        }
        # Обобщённая позиция уровня ОКПД2: без потомков и характеристик — заполнять по ней
        # нечего, подходящей группой в разметке не считается.
        self.generic = {
            code
            for code, g in self.groups.items()
            if g.leaves == (g.position,) and not g.position.characteristics
        }

    @classmethod
    def load(cls) -> "Catalog":
        sys.path.insert(0, str(ROOT / "backend"))
        from app.adapter.ktru_xml import XmlKtruSource
        from settings import Settings

        return cls(XmlKtruSource(Settings().ktru_xml_dir).load())


def base(value: float, unit: str | None) -> tuple[str | None, Decimal]:
    """Число в базовой единице своей размерности; неизвестная единица — как есть."""
    from app.domain.units import UNITS

    known = UNITS.get(unit or "")
    if known is None:
        return unit, Decimal(str(value))
    return known.dimension, Decimal(str(value)) * known.factor


def admits(characteristic: Any, value: Any, unit: str | None) -> bool:
    """Значение факта допустимо характеристикой: текст — среди значений, число — в правиле."""
    if isinstance(value, str):
        return any(v.label().lower() == value.lower() for v in characteristic.values)
    dimension, amount = base(value, unit)
    for v in characteristic.values:
        v_dimension, factor = base(1, v.unit_code)
        if v_dimension != dimension and v.unit_code is not None:
            continue
        if v.contains(float(amount / factor)):
            return True
    return False


def check_dev(data: dict[str, Any], catalog: Catalog) -> tuple[list[str], list[str]]:
    from app.domain.catalog import CATEGORIES

    problems: list[str] = []
    warnings: list[str] = []
    seen: set[str] = set()
    for case in data["cases"]:
        cid = case["id"]

        def bad(message: str, cid: str = cid) -> None:
            problems.append(f"{cid}: {message}")

        if cid in seen:
            bad("повторный id")
        seen.add(cid)
        if case["category"] not in CATEGORIES:
            bad(f"неизвестная категория {case['category']}")
        if not case["messages"] or not all(m.strip() for m in case["messages"]):
            bad("пустое сообщение")
        if unknown := set(case["tags"]) - TAGS:
            bad(f"неизвестные теги {sorted(unknown)}")
        text = text_of(case)

        if not case["groups"] and (
            case["codes"] or case["facts"] or "out_of_scope" not in case["tags"]
        ):
            bad("кейс без групп — только out_of_scope без кодов и фактов")
        leaves: dict[str, Any] = {}
        for g in case["groups"]:
            if g not in catalog.groups:
                bad(f"{g} — не группа КТРУ")
                continue
            if g in catalog.generic:
                bad(f"{g} — обобщённая позиция без характеристик")
            leaves.update({p.code: p for p in catalog.groups[g].leaves})
        for code in case["codes"]:
            if code not in leaves:
                bad(f"{code} — не конечная позиция размеченных групп")
        codes = [leaves[c] for c in case["codes"] if c in leaves]

        kinds = {e["kind"] for e in case["errors"]}
        for error in case["errors"]:
            if error["kind"] not in KINDS:
                bad(f"неизвестный класс ошибки {error['kind']}")
            if not error["source_quote"] or error["source_quote"] not in text:
                bad(f"цитаты «{error['source_quote']}» нет в тексте")
            if error["kind"] in {"typo", "synonym"} and not error.get("suggestion"):
                bad(f"{error['kind']} без suggestion")

        for fact in case["facts"]:
            name, value, unit = fact["characteristic"], fact["value"], fact.get("unit")
            chars = [p.char(name) for p in codes if p.char(name) is not None]
            if not chars:
                bad(f"характеристики «{name}» нет у допустимых позиций")
            elif not any(admits(c, value, unit) for c in chars):
                if isinstance(value, str) or "out_of_range" not in kinds:
                    bad(
                        f"«{name}» = {value} {unit or ''}: значения нет у допустимых позиций"
                    )
            elif "out_of_range" in kinds and not isinstance(value, str):
                warnings.append(
                    f"{cid}: «{name}» = {value} допустимо, а размечен out_of_range"
                )

        # Позиции группы, которым не противоречит ни один размеченный факт.
        if case["groups"] and not kinds & {"out_of_range", "value_not_in_catalog"}:
            consistent = sorted(
                code
                for code, p in leaves.items()
                if all(
                    p.char(f["characteristic"]) is None
                    or admits(p.char(f["characteristic"]), f["value"], f.get("unit"))
                    for f in case["facts"]
                )
            )
            if consistent != sorted(case["codes"]):
                warnings.append(
                    f"{cid}: по фактам допустимы {consistent}, размечено {sorted(case['codes'])}"
                )
        if "out_of_range" in kinds:
            for fact in case["facts"]:
                if isinstance(fact["value"], str):
                    continue
                group_chars = [
                    p.char(fact["characteristic"])
                    for p in leaves.values()
                    if p.char(fact["characteristic"]) is not None
                ]
                if any(admits(c, fact["value"], fact.get("unit")) for c in group_chars):
                    warnings.append(
                        f"{cid}: {fact['characteristic']} = {fact['value']} есть у соседней "
                        "позиции группы — это «не подходит этой позиции», а не ошибка ввода"
                    )
    if len(data["cases"]) != 60:
        problems.append(f"кейсов {len(data['cases'])}, нужно 60")
    per_category = defaultdict(int)
    for case in data["cases"]:
        per_category[case["category"]] += 1
    if set(per_category.values()) != {20}:
        problems.append(f"по категориям {dict(per_category)}, нужно по 20")
    return problems, warnings


def check_holdout(rows: list[HoldoutRow], catalog: Catalog) -> list[str]:
    problems = []
    ids = [r.ste_id for r in rows]
    if len(set(ids)) != len(ids):
        problems.append("holdout: повторные ID СТЕ")
    listed = (
        HOLDOUT.with_name(f"{HOLDOUT.stem}_ids.txt").read_text(encoding="utf-8").split()
    )
    if sorted(listed) != sorted(ids):
        problems.append("holdout: список ID не совпадает с таблицей")
    for r in rows:
        if not r.groups and r.raw["label"].strip() != NONE:
            problems.append(f"holdout {r.ste_id}: пустая разметка")
        for g in r.groups:
            if g not in catalog.groups:
                problems.append(f"holdout {r.ste_id}: {g} — не группа КТРУ")
            elif g in catalog.generic:
                problems.append(
                    f"holdout {r.ste_id}: {g} — обобщённая позиция без характеристик"
                )
    return problems


def main() -> int:
    catalog = Catalog.load()
    data = load_dev()
    problems, warnings = check_dev(data, catalog)
    rows = load_holdout()
    problems += check_holdout(rows, catalog)
    for w in warnings:
        print(f"предупреждение: {w}")
    for p in problems:
        print(f"проблема: {p}")
    checked = sum(c["checked"] for c in data["cases"]) + sum(r.checked for r in rows)
    print(
        f"{len(data['cases'])} кейсов, {len(rows)} строк holdout; проверено человеком {checked}; "
        f"проблем {len(problems)}, предупреждений {len(warnings)}"
    )
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
