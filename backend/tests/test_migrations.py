from alembic.autogenerate import compare_metadata
from alembic.runtime.migration import MigrationContext

import app.repository.orm  # noqa: F401 — регистрирует все таблицы в Base.metadata
from app.repository.database import Base, create_db_engine
from settings import Settings


def test_models_match_migrations(settings: Settings) -> None:
    """Схема после `alembic upgrade head` совпадает с ORM: модель без миграции роняет тест."""
    engine = create_db_engine(settings.database_url)
    with engine.connect() as connection:
        diff = compare_metadata(MigrationContext.configure(connection), Base.metadata)
    engine.dispose()

    assert diff == []
