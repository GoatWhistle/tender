"""JSON-снимок справочника КТРУ (`var/ktru.json`) — реализация порта `CatalogSource` и запись
снимка. Снимок собирает `build_var.py`, читают скрипты замеров `evals/`: XML парсится долго."""

import json
from dataclasses import asdict
from decimal import Decimal
from pathlib import Path
from typing import Any

from app.domain.catalog import Bound, Characteristic, CharacteristicKind, Position, Value


class JsonKtruSource:
    def __init__(self, path: Path) -> None:
        self._path = path

    def load(self) -> list[Position]:
        return [
            _position(p)
            for p in json.loads(self._path.read_text(encoding="utf-8"), parse_float=Decimal)
        ]


def dump_json(positions: list[Position], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps([asdict(p) for p in positions], ensure_ascii=False, default=str),
        encoding="utf-8",
    )


def _value(v: dict[str, Any]) -> Value:
    v = dict(v)
    for key in ("concrete", "min", "max"):
        if v.get(key) is not None:
            v[key] = Decimal(str(v[key]))
    min_op, max_op = v.pop("min_op"), v.pop("max_op")
    return Value(
        **v,
        min_op=Bound(min_op) if min_op else None,
        max_op=Bound(max_op) if max_op else None,
    )


def _position(p: dict[str, Any]) -> Position:
    chars = tuple(
        Characteristic(
            **{
                **c,
                "kind": CharacteristicKind(c["kind"]),
                "values": tuple(_value(v) for v in c["values"]),
            }
        )
        for c in p.pop("characteristics")
    )
    return Position(
        **{**p, "units": tuple(p["units"]), "rubrics": tuple(p["rubrics"])},
        characteristics=chars,
    )
