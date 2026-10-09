from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.adapter.stub import StubEmbeddings
from main import create_app
from settings import Settings
from tests.conftest import TABLE_CODE


def test_search_returns_explained_groups(synced: Settings) -> None:
    with TestClient(create_app(synced, embeddings=StubEmbeddings())) as client:
        response = client.post("/api/v1/search", json={"description": "Стол письменный"})
    assert response.status_code == 200
    result = response.json()
    assert result["description"] == "Стол письменный"
    first = result["groups"][0]
    assert (first["code"], first["category"]) == (TABLE_CODE, "Мебель")
    assert first["methods"]["lexical"]["rank"] == 1
    assert first["methods"]["vector"]["rank"] == 1
    assert first["methods"]["synonym"] == {"rank": None, "contribution": 0.0}
    assert first["score"] == pytest.approx(0.03278688524590164)
    for hit in result["groups"]:
        assert hit["score"] == pytest.approx(
            sum(method["contribution"] for method in hit["methods"].values())
        )


def test_code_promotes_group_of_leaf_and_unknown_code_reports_message(synced: Settings) -> None:
    from tests.conftest import CABINET_CHILDREN, CABINET_CODE

    with TestClient(create_app(synced, embeddings=StubEmbeddings())) as client:
        found = client.post(
            "/api/v1/search", json={"description": f"Стол, КТРУ {CABINET_CHILDREN[0]}"}
        ).json()
        unknown = client.post("/api/v1/search", json={"description": "Стол 99.99.99.999-99999999"})
    assert found["groups"][0]["code"] == CABINET_CODE
    assert found["groups"][0]["found_by"] == "code"
    assert unknown.status_code == 200
    assert unknown.json()["groups"][0]["code"] == TABLE_CODE
    assert "99.99.99.999-99999999" in unknown.json()["messages"][0]


def test_category_is_hard_filter_and_api_limits_input(synced: Settings) -> None:
    with TestClient(create_app(synced, embeddings=StubEmbeddings())) as client:
        result = client.post(
            "/api/v1/search", json={"description": "Стол", "category": "Инструменты", "limit": 1}
        ).json()
        assert [g["category"] for g in result["groups"]] == ["Инструменты"]
        for body in (
            {"description": "Стол", "limit": 51},
            {"description": " "},
            {"description": "Стол", "category": "Неизвестная"},
        ):
            assert client.post("/api/v1/search", json=body).status_code == 422


def test_search_without_model_is_explicitly_unavailable(synced: Settings) -> None:
    with TestClient(create_app(synced)) as client:
        response = client.post("/api/v1/search", json={"description": "Стол"})
        assert response.status_code == 503
        assert response.json()["code"] == "model_not_configured"
        assert client.get("/api/v1/groups").status_code == 200
        assert client.get("/health/live").status_code == 200
        assert client.get("/health/models").json()["model"] == "модель не настроена"


def test_reviewed_alias_recovers_group_without_lexical_hit(
    settings: Settings, tmp_path: Path
) -> None:
    from main import sync_catalog

    aliases = tmp_path / "aliases.csv"
    aliases.write_text(
        "group_code,alias,source,reviewed\n"
        f"{TABLE_CODE},пюпитр,manual,true\n"
        f"{TABLE_CODE},секретер,manual,false\n"
        "99.99.99.999-99999999,ошибка,manual,true\n",
        encoding="utf-8",
    )
    settings = settings.model_copy(update={"aliases_path": aliases})
    report = sync_catalog(settings)
    assert report.aliases == 2
    assert report.invalid_aliases[0].group_code == "99.99.99.999-99999999"
    with TestClient(create_app(settings, embeddings=StubEmbeddings())) as client:
        matched = client.post("/api/v1/search", json={"description": "  ПЮПИТР  "}).json()
        hit = next(g for g in matched["groups"] if g["code"] == TABLE_CODE)
        assert matched["groups"][0]["code"] == TABLE_CODE
        assert hit["methods"]["lexical"]["rank"] is None
        assert hit["methods"]["synonym"]["rank"] == 1
        for description in ("секретер", "пюпитровый"):
            result = client.post("/api/v1/search", json={"description": description}).json()
            assert all(g["methods"]["synonym"]["rank"] is None for g in result["groups"])


def test_saved_database_search_restarts_without_document_embedding(synced: Settings) -> None:
    from collections.abc import Sequence

    from app.domain.inference import EmbeddingBatch
    from build_search_db import save_vectors

    settings = synced.model_copy(
        update={"embeddings_model": "stub-embeddings", "embeddings_revision": "stub-1"}
    )
    save_vectors(settings, StubEmbeddings())

    class QueryOnly(StubEmbeddings):
        def embed_documents(self, texts: Sequence[str]) -> EmbeddingBatch:
            raise RuntimeError("Документы уже сохранены; сервис обрабатывает только запросы")

    for _ in range(2):
        with TestClient(create_app(settings, embeddings=QueryOnly())) as client:
            response = client.post("/api/v1/search", json={"description": "Стол письменный"})
            assert response.status_code == 200
            assert response.json()["groups"][0]["code"] == TABLE_CODE


@pytest.mark.parametrize("damage", ["revision", "missing-document", "not-normalized"])
def test_incompatible_saved_vectors_are_unavailable(synced: Settings, damage: str) -> None:
    from contextlib import closing
    from dataclasses import replace

    from sqlalchemy.orm import Session

    from app.repository.database import create_db_engine
    from app.repository.search_vectors import SqlSearchVectors
    from app.repository.unit_of_work import SqlUnitOfWork
    from build_search_db import save_vectors

    settings = synced.model_copy(
        update={"embeddings_model": "stub-embeddings", "embeddings_revision": "stub-1"}
    )
    snapshot = save_vectors(settings, StubEmbeddings())
    broken = replace(snapshot, revision="other-revision")
    if damage == "missing-document":
        broken = snapshot
        broken = replace(broken, documents=broken.documents[:-1], vectors=broken.vectors[:-1])
    elif damage == "not-normalized":
        broken = replace(snapshot, vectors=((0.0,) * snapshot.dimension, *snapshot.vectors[1:]))
    engine = create_db_engine(settings.database_url)
    try:
        with closing(SqlUnitOfWork(Session(engine))) as uow, uow:
            SqlSearchVectors(uow.session).replace(broken)
    finally:
        engine.dispose()
    with TestClient(create_app(settings, embeddings=StubEmbeddings())) as client:
        response = client.post("/api/v1/search", json={"description": "Стол"})
        assert response.status_code == 503
        assert "пересоберите" in response.json()["message"]
        assert client.get("/health/models").json()["ready"] is False
        assert client.get("/api/v1/groups").status_code == 200


def test_catalog_resync_invalidates_saved_vectors(synced: Settings) -> None:
    from collections.abc import Sequence

    from app.domain.inference import EmbeddingBatch
    from build_search_db import save_vectors
    from main import sync_catalog

    settings = synced.model_copy(
        update={"embeddings_model": "stub-embeddings", "embeddings_revision": "stub-1"}
    )
    save_vectors(settings, StubEmbeddings())
    sync_catalog(settings)

    class QueryOnly(StubEmbeddings):
        def embed_documents(self, texts: Sequence[str]) -> EmbeddingBatch:
            raise RuntimeError("После синхронизации нужен новый снимок")

    with TestClient(create_app(settings, embeddings=QueryOnly())) as client:
        assert client.post("/api/v1/search", json={"description": "Стол"}).status_code == 503
    save_vectors(settings, StubEmbeddings())
    with TestClient(create_app(settings, embeddings=QueryOnly())) as client:
        response = client.post("/api/v1/search", json={"description": "Стол"})
        assert response.status_code == 200
        assert response.json()["groups"][0]["code"] == TABLE_CODE
