from dataclasses import dataclass

from rag.domain.catalog import SUPPLY_UNIT, Position, value_text

KINDS = {"1": "фиксировано", "2": "выбор одного", "3": "выбор нескольких"}

COMPARE_MIN = 2
COMPARE_MAX = 4


@dataclass(frozen=True, slots=True)
class Row:
    name: str
    values: list[tuple[str, ...] | None]
    differs: bool


def properties(position: Position) -> dict[str, str]:
    values = {
        "Наименование": position.name,
        SUPPLY_UNIT: "; ".join(sorted(position.units)) or "Не указана",
        "ОКПД2": position.okpd2,
    }
    for characteristic in position.characteristics:
        labels = sorted({value_text(v) for v in characteristic.values if value_text(v)})
        mode = KINDS.get(characteristic.kind, characteristic.kind)
        requirement = "обязательно" if characteristic.required else "необязательно"
        values[characteristic.name] = f"{'; '.join(labels)} ({mode}, {requirement})"
    return values


def differences(positions: list[Position]) -> dict[str, dict[str, str]]:
    rows = {position.code: properties(position) for position in positions}
    names = list(dict.fromkeys(name for row in rows.values() for name in row))
    differing = [
        name for name in names if len({row.get(name) for row in rows.values()}) > 1
    ]
    return {
        code: {name: row.get(name, "Не задано в этой позиции") for name in differing}
        for code, row in rows.items()
    }


def display_differences(positions: list[Position]) -> dict[str, dict[str, str]]:
    return {
        code: {name: value for name, value in row.items() if name != "Наименование"}
        for code, row in differences(positions).items()
    }


def indistinguishable(positions: list[Position]) -> bool:
    return not any(differences(positions).values())


def _cells(position: Position) -> dict[str, tuple[str, ...]]:
    return {
        c.name: tuple(dict.fromkeys(value_text(v) for v in c.values if value_text(v)))
        for c in position.characteristics
    }


def characteristic_rows(positions: list[Position]) -> list[Row]:
    per_position = [_cells(position) for position in positions]
    names = list(dict.fromkeys(name for row in per_position for name in row))
    rows = []
    for name in names:
        values = [row.get(name) for row in per_position]
        variants = {tuple(sorted(v)) if v is not None else None for v in values}
        rows.append(Row(name, values, len(variants) > 1))
    return rows


def meta_row(name: str, values: list[tuple[str, ...]]) -> Row:
    return Row(name, list(values), len({tuple(sorted(v)) for v in values}) > 1)
