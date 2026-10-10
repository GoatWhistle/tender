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
