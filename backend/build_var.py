"""Офлайн-сборка артефактов для замеров: снимок КТРУ (JSON), частотный словарь и образцы СТЕ.

Запуск: `cd backend && uv run python build_var.py`. Результат — каталог `var/` в корне репо.
"""

import json
import re
import sys
from collections import Counter
from collections.abc import Iterator

import openpyxl

from app.adapter.ktru_json import dump_json
from app.adapter.ktru_xml import XmlKtruSource
from app.domain.catalog import CATEGORIES
from settings import STE_XLSX_DIR, VAR_DIR, Settings

WORD = re.compile(r"[а-яё]+|[a-z]+", re.I)


def ste_rows(limit: int | None = None) -> Iterator[tuple[str, str, str]]:
    """Наименования и характеристики реальных СТЕ из выгрузок организаторов."""
    for cat in CATEGORIES:
        wb = openpyxl.load_workbook(STE_XLSX_DIR / f"{cat}.xlsx", read_only=True)
        ws = wb.worksheets[0]
        for i, row in enumerate(ws.iter_rows(min_row=2, values_only=True)):
            if limit and i >= limit:
                break
            if row[1]:
                yield cat, str(row[1]), str(row[5] or "")
        wb.close()


def main() -> None:
    VAR_DIR.mkdir(exist_ok=True)
    positions = XmlKtruSource(Settings().ktru_xml_dir).load()
    dump_json(positions, VAR_DIR / "ktru.json")
    print(f"КТРУ: {len(positions)} позиций", file=sys.stderr)

    freq: Counter[str] = Counter()
    # Слова справочника КТРУ весят больше — это эталонная лексика.
    for p in positions:
        texts = [p.name, p.okpd2_name]
        for c in p.characteristics:
            texts.append(c.name)
            texts.extend(v.text for v in c.values if v.text)
            texts.extend(v.unit for v in c.values if v.unit)
        for t in texts:
            for w in WORD.findall(t.lower().replace("ё", "е")):
                freq[w] += 20

    samples: dict[str, list[str]] = {c: [] for c in CATEGORIES}
    for cat, name, chars in ste_rows():
        for w in WORD.findall(f"{name} {chars}".lower().replace("ё", "е")):
            freq[w] += 1
        if len(samples[cat]) < 3000:
            samples[cat].append(name)
    (VAR_DIR / "vocab.json").write_text(
        json.dumps(dict(freq.most_common()), ensure_ascii=False), encoding="utf-8"
    )
    (VAR_DIR / "ste_samples.json").write_text(
        json.dumps(samples, ensure_ascii=False, indent=0), encoding="utf-8"
    )
    print(f"Словарь: {len(freq)} слов", file=sys.stderr)


if __name__ == "__main__":
    main()
