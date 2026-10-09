"""Словарь синонимов групп КТРУ из CSV — реализация порта `AliasSource`.

Формат — `docs/search.md`: заголовок `group_code,alias,source,reviewed`, `reviewed` — `true` или
`false`. Ошибка формата называет строку файла.
"""

import csv
from pathlib import Path

from app.domain.search import Alias

COLUMNS = ["group_code", "alias", "source", "reviewed"]
FLAGS = {"true": True, "false": False}


class CsvAliasSource:
    def __init__(self, path: Path) -> None:
        self._path = path

    def load(self) -> list[Alias]:
        with self._path.open(encoding="utf-8-sig", newline="") as file:
            reader = csv.DictReader(file)
            if reader.fieldnames != COLUMNS:
                raise ValueError(f"{self._path}: заголовок {reader.fieldnames} вместо {COLUMNS}")
            return [self._alias(row, reader.line_num) for row in reader]

    def _alias(self, row: dict[str, str], line: int) -> Alias:
        values = {k: (row.get(k) or "").strip() for k in COLUMNS}
        if not all(values.values()) or None in row:
            raise ValueError(f"{self._path}, строка {line}: нужны ровно поля {COLUMNS}")
        if values["reviewed"] not in FLAGS:
            raise ValueError(
                f"{self._path}, строка {line}: reviewed = {values['reviewed']!r}, нужно true/false"
            )
        return Alias(
            group_code=values["group_code"],
            alias=values["alias"],
            source=values["source"],
            reviewed=FLAGS[values["reviewed"]],
        )
