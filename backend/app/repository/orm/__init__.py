"""ORM-модели всех таблиц — только для репозиториев и миграций. Импорт пакета регистрирует все
таблицы в `Base.metadata`: новый модуль с таблицами добавляет импорт сюда."""

from app.repository.orm.aliases import GroupAlias
from app.repository.orm.catalog import AllowedValue, CatalogPosition, PositionCharacteristic
from app.repository.orm.search_vectors import GroupSearchVector, SearchVectorMetadata

__all__ = [
    "AllowedValue",
    "CatalogPosition",
    "GroupAlias",
    "GroupSearchVector",
    "PositionCharacteristic",
    "SearchVectorMetadata",
]
