"""Подключение к SQLite и база ORM-моделей. ORM — только в `app.repository`, модели таблиц —
в `app.repository.orm`."""

import sqlite3
from pathlib import Path
from typing import Any

from sqlalchemy import Engine, MetaData, create_engine, event  # noqa: TID251
from sqlalchemy.engine import make_url
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import ConnectionPoolEntry

# Имена ограничений задаём явно — иначе миграции на разных машинах расходятся.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def create_db_engine(url: str, **kwargs: Any) -> Engine:
    """Движок SQLite, у которого внешние ключи проверяются, а соединение можно отдать потоку
    пула FastAPI. Каталог файла базы создаётся, если его нет."""
    database = make_url(url).database
    if database and database != ":memory:":
        Path(database).parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(url, connect_args={"check_same_thread": False}, **kwargs)

    @event.listens_for(engine, "connect")
    def _foreign_keys(connection: sqlite3.Connection, _: ConnectionPoolEntry) -> None:
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        # WAL: чтение не ждёт записи, фиксация — без fsync журнала на каждую транзакцию.
        # NORMAL в WAL не теряет данных при падении процесса, только при отключении питания.
        if database and database != ":memory:":
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()

    return engine
