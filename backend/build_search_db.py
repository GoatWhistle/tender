"""Собрать переносимую SQLite КТРУ с реальными поисковыми векторами без скачивания весов."""

import argparse
import hashlib
import json
import os
import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy.orm import Session

from app.domain.catalog import CATEGORIES
from app.domain.errors import ModelNotConfigured
from app.domain.search_vectors import SearchVectors
from app.repository.database import create_db_engine
from app.repository.unit_of_work import SqlUnitOfWork
from app.usecase.interface import Embeddings
from main import configured_embeddings, production_usecases, sync_catalog
from settings import BACKEND_DIR, REPO_DIR, Settings


def save_vectors(
    settings: Settings,
    embeddings: Embeddings | None = None,
    provenance: dict[str, str] | None = None,
) -> SearchVectors:
    embeddings = embeddings or configured_embeddings(settings)
    if embeddings is None:
        raise ModelNotConfigured()
    engine = create_db_engine(settings.database_url)
    try:
        usecases = production_usecases(settings, embeddings=embeddings)
        assert usecases.build_search_vectors is not None
        with closing(SqlUnitOfWork(Session(engine))) as uow:
            return usecases.build_search_vectors(uow).run(provenance)
    finally:
        engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=REPO_DIR / "artifacts/ktru-search.sqlite3")
    parser.add_argument("--ktru-dir", type=Path)
    parser.add_argument("--aliases", type=Path)
    parser.add_argument("--embeddings-url", help="Базовый URL сервиса, заканчивающийся /v1")
    args = parser.parse_args()
    settings = Settings()
    overrides = {}
    for argument, setting in (
        (args.ktru_dir, "ktru_xml_dir"),
        (args.aliases, "aliases_path"),
        (args.embeddings_url, "embeddings_url"),
    ):
        if argument is not None:
            overrides[setting] = argument
    settings = settings.model_copy(update=overrides)
    if not settings.embeddings_url:
        raise ModelNotConfigured()
    sources = [settings.ktru_xml_dir / f"{c}.xml" for c in CATEGORIES]
    sources.append(settings.aliases_path)
    provenance = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
    provenance["model_repository"] = settings.embeddings_repository
    provenance["vector_encoding"] = "little-endian-float32"
    provenance["text_normalization"] = "lower-whitespace-yo-v1"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    # Строим рядом и заменяем только после успеха: ошибка сервиса не портит готовый артефакт.
    with tempfile.TemporaryDirectory(prefix="ktru-build-", dir=args.output.parent) as directory:
        database = Path(directory) / "catalog.sqlite3"
        settings = settings.model_copy(update={"database_url": f"sqlite:///{database.resolve()}"})
        config = Config(BACKEND_DIR / "alembic.ini")
        config.attributes.update(database_url=settings.database_url, configure_logger=False)
        command.upgrade(config, "head")
        report = sync_catalog(settings)
        if report.invalid_aliases:
            raise RuntimeError("Словарь содержит ссылки на отсутствующие группы")
        snapshot = save_vectors(settings, provenance=provenance)
        with closing(sqlite3.connect(database)) as connection:
            if connection.execute("PRAGMA integrity_check").fetchone() != ("ok",):
                raise RuntimeError("Повреждена база SQLite")
            if connection.execute("PRAGMA foreign_key_check").fetchall():
                raise RuntimeError("Нарушены связи SQLite")
            connection.execute("PRAGMA journal_mode=DELETE")
            connection.execute("VACUUM")
        os.replace(database, args.output)
    print(
        json.dumps(
            {
                "database": str(args.output),
                "positions": report.positions,
                "aliases": report.aliases,
                "groups": len(snapshot.documents) // 2,
                "documents": len(snapshot.documents),
                "dimension": snapshot.dimension,
                "revision": snapshot.revision,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
