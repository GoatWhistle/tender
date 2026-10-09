"""Словарь синонимов на SQLite — реализация порта `AliasRepository`."""

from collections.abc import Iterable

from sqlalchemy import delete, insert, select
from sqlalchemy.orm import Session

from app.domain.search import Alias
from app.repository.orm.aliases import AliasRow


class SqlAliases:
    def __init__(self, session: Session) -> None:
        self._session = session

    def aliases(self) -> list[Alias]:
        rows = self._session.scalars(select(AliasRow).order_by(AliasRow.id))
        return [Alias(r.group_code, r.alias, r.source, r.reviewed) for r in rows]

    def replace(self, aliases: Iterable[Alias]) -> None:
        self._session.execute(delete(AliasRow))
        rows = [
            {
                "group_code": a.group_code,
                "alias": a.alias,
                "source": a.source,
                "reviewed": a.reviewed,
            }
            for a in aliases
        ]
        if rows:
            self._session.execute(insert(AliasRow), rows)
