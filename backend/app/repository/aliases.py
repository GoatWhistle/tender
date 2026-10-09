"""Словарь синонимов на SQLite."""

from collections.abc import Iterable

from sqlalchemy import delete, insert, select
from sqlalchemy.orm import Session

from app.domain.aliases import Alias
from app.repository.orm.aliases import GroupAlias


class SqlAliases:
    def __init__(self, session: Session) -> None:
        self._session = session

    def all(self) -> list[Alias]:
        rows = self._session.scalars(
            select(GroupAlias).order_by(GroupAlias.group_code, GroupAlias.alias)
        )
        return [Alias(r.group_code, r.alias, r.source, r.reviewed) for r in rows]

    def replace(self, aliases: Iterable[Alias]) -> None:
        self._session.execute(delete(GroupAlias))
        rows = [
            dict(group_code=a.group_code, alias=a.alias, source=a.source, reviewed=a.reviewed)
            for a in aliases
        ]
        if rows:
            self._session.execute(insert(GroupAlias), rows)
