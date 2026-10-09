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


class GroupNotFound(DomainError):
    code = "group_not_found"
    message = "Группа КТРУ не найдена"


class ModelFailure(DomainError):
    """Модель не ответила, ответила с ошибкой или невалидно: это технический сбой, а не
    решение. Исходное исключение адаптера — в `__cause__`."""

    code = "technical_error"
    message = "Модель недоступна или вернула невалидный ответ"


class ModelNotConfigured(ModelFailure):
    """Адрес модели не задан: точка сборки не подменяет её заглушкой."""

    code = "model_not_configured"
    message = "Модель не настроена"
