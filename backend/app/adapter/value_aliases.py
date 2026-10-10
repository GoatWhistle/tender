"""Только проверенные контекстные записи, источники — выгрузки организаторов."""

from app.domain.diagnostics import ValueAlias


class ReviewedValueAliases:
    def all(self) -> tuple[ValueAlias, ...]:
        return (
            ValueAlias(
                "кожзам",
                "Искусственная кожа",
                "Материал обивки",
                "Мебель",
                "data/yandex_disk/Примеры выгрузок/Мебель.xlsx; sheet1; B65, F65",
            ),
            ValueAlias(
                "х/б напыление",
                "хлопчато-бумажное напыление",
                "Напыление",
                "Одежда",
                "data/yandex_disk/Примеры выгрузок/Одежда.xlsx; sheet1; B1495, F1495",
            ),
            ValueAlias(
                "Дрель-шуруповерт",
                "Шуруповерт",
                "Тип инструмента",
                "Инструменты",
                "data/yandex_disk/Примеры выгрузок/Инструменты.xlsx; sheet1; B2, F2",
                ("аккумулятор", "завинчивание", "сверление"),
            ),
        )
