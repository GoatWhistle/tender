from rag.ktru import value_text
from rag.models import Position


def properties(position: Position) -> dict[str, str]:
    values = {
        "Наименование": position.name,
        "Единица поставки": "; ".join(sorted(position.units)) or "Не указана",
        "ОКПД2": position.okpd2,
    }
    kinds = {"1": "фиксировано", "2": "выбор одного", "3": "выбор нескольких"}
    for characteristic in position.characteristics:
        labels = sorted(
            {value_text(value) for value in characteristic.values if value_text(value)}
        )
        mode = kinds.get(characteristic.kind, characteristic.kind)
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


def cells(position: Position) -> dict[str, tuple[str, ...]]:
    return {
        c.name: tuple(dict.fromkeys(value_text(v) for v in c.values if value_text(v)))
        for c in position.characteristics
    }


def characteristic_rows(
    positions: list[Position],
) -> list[tuple[str, list[tuple[str, ...] | None], bool]]:
    per_position = [cells(position) for position in positions]
    names = list(dict.fromkeys(name for row in per_position for name in row))
    rows = []
    for name in names:
        values = [row.get(name) for row in per_position]
        variants = {tuple(sorted(v)) if v is not None else None for v in values}
        rows.append((name, values, len(variants) > 1))
    return rows


def match(code: str, lowered: str, needle: str) -> int | None:
    if code == needle:
        return 0
    if code.startswith(needle):
        return 1
    if lowered.startswith(needle):
        return 2
    if all(token in lowered for token in needle.split()):
        return 3
    return None
