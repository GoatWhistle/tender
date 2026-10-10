"""Holdout реальных СТЕ: случайная выборка из выгрузок организаторов с подсказками для разметки.

По каждой категории — строки Лист1 с непустым наименованием; дубли по нормализованному
наименованию отбрасываются (остаётся первая строка), затем `random.Random(seed).sample`.
К строке — top-5 групп лексического поиска продукта (TF-IDF без эмбеддингов): это подсказка
разметчику, а не разметка. Колонки `label`, `checked`, `note` заполняет человек; формат —
`evals/datasets/README.md`.

Запуск: cd backend && uv run python ../evals/e2e/sample_holdout.py
Пишет `ste_holdout_v1.csv` и `ste_holdout_v1_ids.txt` в `evals/datasets/`; существующую
разметку не перетирает — для новой выборки задайте другие `--seed` и `--out`.
"""

import argparse
import csv
import pathlib
import random
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

import openpyxl
from app.adapter.ktru_xml import XmlKtruSource
from app.adapter.search import TfidfIndex
from app.domain.catalog import CATEGORIES
from app.domain.search import normalize
from settings import STE_XLSX_DIR, Settings

FIELDS = ["ste_id", "category", "name", "characteristics"]
FIELDS += [f"hint_{i}" for i in range(1, 6)] + ["label", "checked", "note"]


def rows(category: str) -> list[tuple[str, str, str]]:
    """(ID СТЕ, наименование, характеристики) без пустых наименований и дублей."""
    workbook = openpyxl.load_workbook(STE_XLSX_DIR / f"{category}.xlsx", read_only=True)
    seen: set[str] = set()
    out = []
    for row in workbook["Лист1"].iter_rows(min_row=2, values_only=True):
        name = str(row[1] or "").strip()
        key = normalize(name)
        if not name or key in seen:
            continue
        seen.add(key)
        out.append((str(row[0]), name, str(row[5] or "").strip()))
    workbook.close()
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=20261010)
    parser.add_argument("--per-category", type=int, default=20)
    parser.add_argument("--out", default="ste_holdout_v1")
    args = parser.parse_args()
    target = ROOT / "evals" / "datasets" / f"{args.out}.csv"
    if target.exists():
        raise SystemExit(f"{target} уже есть: разметку не перетираю")

    groups = [p for p in XmlKtruSource(Settings().ktru_xml_dir).load() if p.is_group]
    index = TfidfIndex()
    index.build(groups)
    names = {g.code: f"{g.code} — {g.name} ({g.category})" for g in groups}

    sample = []
    for category in CATEGORIES:
        population = rows(category)
        picked = random.Random(f"{args.seed}:{category}").sample(
            population, args.per_category
        )
        print(f"{category}: {len(population)} уникальных наименований", file=sys.stderr)
        for ste_id, name, chars in picked:
            hints = [names[r.code] for r in index.rank(normalize(name))[:5]]
            hints += [""] * (5 - len(hints))
            sample.append([ste_id, category, name, chars[:300], *hints, "", "", ""])

    with target.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(FIELDS)
        writer.writerows(sample)
    ids = target.with_name(f"{args.out}_ids.txt")
    ids.write_text("".join(f"{row[0]}\n" for row in sample), encoding="utf-8")
    print(f"{len(sample)} строк → {target.name}, {ids.name}", file=sys.stderr)


if __name__ == "__main__":
    main()
