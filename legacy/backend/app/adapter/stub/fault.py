"""Управляемый сбой заглушки: исключение бросается на каждом вызове, пока тест его не снимет
(`fault = None`). Таймаут — тоже исключение, без ожидания."""

from app.domain.inference import ModelHealth


class Scripted:
    model = "stub"

    def __init__(self, revision: str = "stub-1") -> None:
        self.revision = revision
        self.ready = True
        self.fault: Exception | None = None

    def fail(self, error: Exception | None = None) -> None:
        self.fault = error or ConnectionError("заглушка: сбой модели")

    def time_out(self) -> None:
        self.fault = TimeoutError("заглушка: таймаут модели")

    def _raise_fault(self) -> None:
        if self.fault is not None:
            raise self.fault

    def health(self) -> ModelHealth:
        self._raise_fault()
        return ModelHealth(model=self.model, revision=self.revision, ready=self.ready)
