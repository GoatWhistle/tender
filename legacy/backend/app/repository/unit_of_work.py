"""Единица работы над SQLite — реализация портов `UnitOfWork` и `RequestUnitOfWork`."""

from types import TracebackType
from typing import Self

from sqlalchemy.orm import Session


class SqlUnitOfWork:
    """Одна сессия на запрос, транзакция заканчивается с блоком `with`. `commit` и `rollback`
    сессии в бэкенде — только здесь. Наружу из репозиториев уходят доменные значения, а не
    строки сессии."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self._open = False

    def __enter__(self) -> Self:
        if self._open:
            raise RuntimeError("единица работы уже открыта")
        self._open = True
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self._open = False
        if exc_type is not None:
            self.session.rollback()
            return
        try:
            self.session.commit()
        except BaseException:
            self.session.rollback()
            raise

    def close(self) -> None:
        self.session.close()
