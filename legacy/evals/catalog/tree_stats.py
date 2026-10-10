"""Статистика дерева КТРУ по категориям: группы, конечные позиции на группу, группы без потомков.

Группы и конечные позиции — по правилам домена (`Position.is_group`, `Group.of`,
`outside_tree`), источник — XML выгрузок. Запуск: cd backend && uv run python
../evals/catalog/tree_stats.py — печатает таблицу Markdown для `docs/Словарь данных КТРУ.md`.
"""

import pathlib
import statistics
import sys
from collections import defaultdict

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "backend"))

from app.adapter.ktru_xml import XmlKtruSource
from app.domain.catalog import (
    CATEGORIES,
    CharacteristicKind,
    Group,
    Position,
    outside_tree,
)
from settings import Settings

# Диапазоны числа конечных позиций на группу; 1 — группа без потомков.
BUCKETS = [("1", 1, 1), ("2–5", 2, 5), ("6–20", 6, 20), ("21+", 21, None)]


def main() -> None:
    positions = XmlKtruSource(Settings().ktru_xml_dir).load()
    children: dict[str, list[Position]] = defaultdict(list)
    for p in positions:
        if p.parent is not None:
            children[p.parent].append(p)

    head = ["Категория", "Позиций", "Групп", "Без потомков (шаблонов)", "Медиана", "Макс."]
    head += [f"{label} поз." for label, _, _ in BUCKETS]
    print("| " + " | ".join(head) + " |")
    print("|" + " --- |" * len(head))
    for category in CATEGORIES:
        mine = [p for p in positions if p.category == category]
        groups = [Group.of(p, children[p.code]) for p in mine if p.is_group]
        leaves = [len(g.leaves) for g in groups]
        alone = [g for g in groups if g.leaves == (g.position,)]
        row = [
            category,
            str(len(mine)),
            str(len(groups)),
            f"{len(alone)} ({sum(g.position.is_template for g in alone)})",
            f"{statistics.median(leaves):g}",
            str(max(leaves)),
        ]
        row += [
            str(sum(lo <= n and (hi is None or n <= hi) for n in leaves)) for _, lo, hi in BUCKETS
        ]
        print("| " + " | ".join(row) + " |")
    print(f"\nВне дерева групп: {len(outside_tree(positions))} позиций.\n")

    # Характеристики по виду: всего / из них с одним допустимым значением.
    head = ["Категория", "Позиции"] + [k.value for k in CharacteristicKind]
    print("| " + " | ".join(head) + " |")
    print("|" + " --- |" * len(head))
    for category in CATEGORIES:
        for label, template in (("шаблоны", True), ("не шаблоны", False)):
            chars = [
                c
                for p in positions
                if p.category == category and p.is_template == template
                for c in p.characteristics
            ]
            cells = []
            for kind in CharacteristicKind:
                mine = [c for c in chars if c.kind == kind]
                cells.append(f"{len(mine)} / {sum(len(c.values) == 1 for c in mine)}")
            print("| " + " | ".join([category, label, *cells]) + " |")


if __name__ == "__main__":
    main()
