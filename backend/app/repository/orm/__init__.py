"""ORM-модели всех таблиц — только для репозиториев и миграций. Импорт пакета регистрирует все
таблицы в `Base.metadata`: новый модуль с таблицами добавляет импорт сюда."""

from app.repository.orm.catalog import AllowedValue, CatalogPosition, PositionCharacteristic

__all__ = ["AllowedValue", "CatalogPosition", "PositionCharacteristic"]
