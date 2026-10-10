"""ORM-модели всех таблиц — только для репозиториев и миграций. Импорт пакета регистрирует все
таблицы в `Base.metadata`: новый модуль с таблицами добавляет импорт сюда."""

from app.repository.orm.aliases import GroupAlias
from app.repository.orm.catalog import AllowedValue, CatalogPosition, PositionCharacteristic
from app.repository.orm.search_vectors import GroupSearchVector, SearchVectorMetadata
from app.repository.orm.sessions import AnalysisSession, SessionMessage, SessionRevision

__all__ = [
    "AllowedValue",
    "AnalysisSession",
    "CatalogPosition",
    "GroupAlias",
    "GroupSearchVector",
    "PositionCharacteristic",
    "SearchVectorMetadata",
    "SessionMessage",
    "SessionRevision",
]
