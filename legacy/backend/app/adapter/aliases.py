"""Начальный словарь синонимов из CSV; отсутствие файла означает пустой словарь."""

import csv
from pathlib import Path

from app.domain.aliases import Alias
from app.domain.search import normalize


class CsvAliasesSource:
    def __init__(self, path: Path) -> None:
        self._path = path

    def load(self) -> list[Alias]:
        if not self._path.exists():
            return []
        aliases: dict[tuple[str, str], Alias] = {}
        with self._path.open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            if reader.fieldnames != ["group_code", "alias", "source", "reviewed"]:
                raise ValueError("Ожидались столбцы group_code,alias,source,reviewed")
            for row in reader:
                text = normalize(row["alias"])
                reviewed = row["reviewed"].strip().lower()
                source = row["source"].strip()
                code = row["group_code"].strip()
                if not text or not source or not code or reviewed not in ("true", "false"):
                    raise ValueError(f"Невалидная запись словаря в строке {reader.line_num}")
                alias = Alias(code, text, source, reviewed == "true")
                key = (code, text)
                if key in aliases:
                    raise ValueError(f"Повтор записи словаря в строке {reader.line_num}")
                aliases[key] = alias
        return [aliases[key] for key in sorted(aliases)]
