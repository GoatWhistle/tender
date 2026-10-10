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


def test_decimal_migration_keeps_populated_catalog(settings: Settings) -> None:
    from decimal import Decimal

    from alembic import command
    from alembic.config import Config
    from sqlalchemy.orm import Session

    from app.adapter.ktru_xml import XmlKtruSource
    from app.repository.catalog import SqlCatalog
    from app.repository.unit_of_work import SqlUnitOfWork
    from settings import BACKEND_DIR
    from tests.conftest import TABLE_CODE

    config = Config(BACKEND_DIR / "alembic.ini")
    config.attributes["database_url"] = settings.database_url
    config.attributes["configure_logger"] = False
    command.downgrade(config, "c7e5cf6c0272")
    engine = create_db_engine(settings.database_url)
    try:
        with Session(engine) as session, SqlUnitOfWork(session):
            SqlCatalog(session).replace(XmlKtruSource(settings.ktru_xml_dir).load())
        command.upgrade(config, "head")
        with Session(engine) as session, SqlUnitOfWork(session):
            catalog = SqlCatalog(session)
            assert catalog.count() == 7
            position = catalog.position(TABLE_CODE)
            assert position is not None
            length = position.char("Длина")
            assert length is not None
            assert isinstance(length.values[0].min, Decimal)
            assert length.values[0].min == Decimal("1")
            assert length.values[0].max == Decimal("2")
    finally:
        engine.dispose()
