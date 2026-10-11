class DomainError(Exception):
    code = "domain_error"
    message = "Ошибка запроса"

    def __init__(self, message: str | None = None) -> None:
        if message is not None:
            self.message = message
        super().__init__(self.message)


class InputError(DomainError):
    code = "invalid_input"
    message = "Некорректный запрос"


class StageError(DomainError):
    code = "wrong_stage"
    message = "Действие недоступно на этом этапе"


class NotFound(DomainError):
    code = "not_found"
    message = "Не найдено"


class SessionNotFound(NotFound):
    code = "session_not_found"
    message = "нет такой сессии"


class SearchNotFound(NotFound):
    code = "search_not_found"
    message = "поиск не найден, начните заново"


class PositionNotFound(NotFound):
    code = "position_not_found"
    message = "нет такой позиции КТРУ"


class IndexNotReady(DomainError):
    code = "index_not_ready"
    message = "индекс КТРУ не настроен: задайте RAG_DATA и перезапустите сервис"


class ModelFailure(DomainError):
    code = "model_failure"
    message = "ошибка модели"


class EmbeddingsFailure(ModelFailure):
    code = "embeddings_failure"
    message = "сервис эмбеддингов недоступен"
