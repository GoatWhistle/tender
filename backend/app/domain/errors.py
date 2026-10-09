"""Доменные ошибки: `code` — стабильный ключ для клиента, `message` — по-русски. HTTP-статус
назначает `app.controller.errors`, домен его не знает."""


class DomainError(Exception):
    code = "domain_error"
    message = "Ошибка запроса"

    def __init__(self, message: str | None = None) -> None:
        if message is not None:
            self.message = message
        super().__init__(self.message)


class PositionNotFound(DomainError):
    code = "position_not_found"
    message = "Позиция КТРУ не найдена"


class CatalogEmpty(DomainError):
    code = "catalog_empty"
    message = "Справочник КТРУ не загружен"
