from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.adapter.ktru_xml import XmlKtruSource
from app.domain.errors import ModelFailure
from app.domain.search import MethodContribution, SearchHit, SearchResult
from composition import build_usecases
from main import create_app, sql_repositories
from settings import Settings
from tests.conftest import CABINET_CHILDREN, CABINET_CODE, ROBE_CODE, TABLE_CODE


def test_create_and_read_session(client: TestClient) -> None:
    response = client.post("/api/v1/sessions")
    assert response.status_code == 200
    state = response.json()
    assert state["status"] == "draft"
    assert state["revision"] == 0
    assert state["messages"] == []
    assert state["path"] is None
    assert state["candidate_counts"] == {"in_group": 0, "compatible": 0, "excluded_by_rules": 0}
    assert client.get("/api/v1/sessions/" + state["session_id"]).json() == state


def test_search_failure_is_saved_and_replayed(client: TestClient) -> None:
    sid = client.post("/api/v1/sessions").json()["session_id"]
    url = f"/api/v1/sessions/{sid}/messages"
    result = client.post(url, json={"text": " шкаф "}, headers={"Idempotency-Key": "first"})
    assert result.status_code == 200
    state = result.json()
    assert state["status"] == "technical_error"
    assert state["errors"][0]["code"] == "model_not_configured"
    assert state["messages"][0]["text"] == " шкаф "
    assert state["revision"] == 1
    assert (
        client.post(url, json={"text": " шкаф "}, headers={"Idempotency-Key": "first"}).json()
        == state
    )
    assert (
        client.post(url, json={"text": "стол"}, headers={"Idempotency-Key": "first"}).status_code
        == 409
    )
    assert client.get(f"/api/v1/sessions/{sid}").json() == state


class SearchStub:
    def __init__(self, settings: Settings) -> None:
        self.groups = {p.code: p for p in XmlKtruSource(settings.ktru_xml_dir).load() if p.is_group}
        self.queries: list[str] = []
        self.failure = False

    def run(self, description: str, category: str | None = None, limit: int = 10) -> SearchResult:
        assert category is None
        self.queries.append(description)
        if self.failure:
            raise ModelFailure()
        code = TABLE_CODE if "\n" in description else CABINET_CODE
        groups = [self.groups[code], *(p for p in self.groups.values() if p.code != code)]
        return SearchResult(
            description,
            tuple(
                SearchHit(
                    p,
                    MethodContribution.of(i),
                    MethodContribution.of(i),
                    MethodContribution.of(None),
                )
                for i, p in enumerate(groups[:limit], 1)
            ),
            ("Предупреждение поиска",),
        )


@pytest.fixture
def search_api(synced: Settings) -> Iterator[tuple[TestClient, SearchStub]]:
    search = SearchStub(synced)
    app = create_app(synced)
    app.state.usecases = build_usecases(
        sql_repositories(), catalog_source=XmlKtruSource(synced.ktru_xml_dir), searcher=search
    )
    with TestClient(app) as client:
        yield client, search


def test_messages_narrow_group_and_keep_history(search_api: tuple[TestClient, SearchStub]) -> None:
    client, search = search_api
    sid = client.post("/api/v1/sessions").json()["session_id"]
    url = f"/api/v1/sessions/{sid}/messages"
    first = client.post(url, json={"text": " шкаф "}, headers={"Idempotency-Key": "one"}).json()
    assert first["status"] == "needs_clarification"
    assert first["path"] == {
        "category": "Мебель",
        "group": {"code": CABINET_CODE, "name": "Шкаф для одежды"},
        "positions": 2,
    }
    assert [c["code"] for c in first["candidates"]] == CABINET_CHILDREN
    assert all(c["excluded"] is False for c in first["candidates"])
    assert first["candidate_counts"] == {"in_group": 2, "compatible": 2, "excluded_by_rules": 0}
    assert first["warnings"] == ["Предупреждение поиска"]
    assert 0 < len(first["alternatives"]) <= 4
    assert first["alternatives"][0]["code"] == ROBE_CODE
    assert first["alternatives"][0]["methods"]["lexical"]["rank"] == 2
    assert first["facts"] == [] and first["next_question"] is None
    second = client.post(url, json={"text": "точнее стол"}).json()
    assert second["status"] == "resolved"
    assert second["revision"] == 2
    assert second["path"]["positions"] == len(second["candidates"]) == 1
    assert second["path"]["group"]["code"] == TABLE_CODE
    assert second["messages"][0] == first["messages"][0]
    assert search.queries == [" шкаф ", " шкаф \nточнее стол"]
    assert (
        client.post(url, json={"text": " шкаф "}, headers={"Idempotency-Key": "one"}).json()
        == first
    )
    assert client.get(f"/api/v1/sessions/{sid}").json() == second
    assert len(search.queries) == 2


@pytest.mark.parametrize("text", ["", " \n\t ", "я" * 4001])
def test_invalid_text_does_not_create_revision(client: TestClient, text: str) -> None:
    state = client.post("/api/v1/sessions").json()
    url = "/api/v1/sessions/" + state["session_id"]
    assert client.post(url + "/messages", json={"text": text}).status_code == 422
    assert client.get(url).json() == state


def test_missing_session(client: TestClient) -> None:
    for response in [
        client.get("/api/v1/sessions/missing"),
        client.post("/api/v1/sessions/missing/messages", json={"text": "стол"}),
    ]:
        assert response.status_code == 404
        assert response.json()["code"] == "session_not_found"


def test_failed_search_can_be_retried_with_new_message(
    search_api: tuple[TestClient, SearchStub],
) -> None:
    client, search = search_api
    sid = client.post("/api/v1/sessions").json()["session_id"]
    url = f"/api/v1/sessions/{sid}/messages"
    search.failure = True
    failed = client.post(url, json={"text": "стол"}, headers={"Idempotency-Key": "failure"}).json()
    search.failure = False
    assert failed["status"] == "technical_error"
    assert (
        client.post(url, json={"text": "стол"}, headers={"Idempotency-Key": "failure"}).json()
        == failed
    )
    recovered = client.post(url, json={"text": "письменный"}).json()
    assert recovered["status"] == "resolved"
    assert recovered["revision"] == 2
    assert recovered["errors"] == []
    assert search.queries == ["стол", "стол\nписьменный"]


def test_memory_scenario(settings: Settings) -> None:
    from app.domain.errors import IdempotencyConflict
    from app.repository.memory.catalog import MemoryCatalog
    from app.repository.memory.sessions import MemorySessions
    from app.repository.memory.unit_of_work import MemoryStore, MemoryUnitOfWork

    store = MemoryStore()
    uow = MemoryUnitOfWork(store)
    source = XmlKtruSource(settings.ktru_xml_dir)
    from composition import Repositories

    usecases = build_usecases(
        Repositories[MemoryUnitOfWork](
            catalog=lambda u: MemoryCatalog(u.store), sessions=lambda u: MemorySessions(u.store)
        ),
        catalog_source=source,
        searcher=SearchStub(settings),
    )
    usecases.catalog_sync(uow).run()
    assert usecases.sessions is not None
    sessions = usecases.sessions(uow)
    initial = sessions.create()
    first = sessions.message(initial.session_id, "шкаф", "one")
    assert first.status == "needs_clarification"
    assert first.candidate_counts.in_group == 2
    assert sessions.message(initial.session_id, "шкаф", "one") == first
    with pytest.raises(IdempotencyConflict):
        sessions.message(initial.session_id, "стол", "one")
    second = sessions.message(initial.session_id, "точнее стол")
    assert second.revision == 2
    assert second.status == "resolved"
    assert sessions.get(initial.session_id) == second


def test_concurrent_messages_get_distinct_revisions(
    search_api: tuple[TestClient, SearchStub],
) -> None:
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    client, _ = search_api
    sid = client.post("/api/v1/sessions").json()["session_id"]
    url = f"/api/v1/sessions/{sid}/messages"
    barrier = Barrier(2)

    def send(text: str) -> int:
        barrier.wait(timeout=5)
        response = client.post(url, json={"text": text})
        assert response.status_code == 200
        return int(response.json()["revision"])

    with ThreadPoolExecutor(max_workers=2) as pool:
        revisions = list(pool.map(send, ["шкаф", "стол"]))
    assert sorted(revisions) == [1, 2]
    assert len(client.get(f"/api/v1/sessions/{sid}").json()["messages"]) == 2


def test_concurrent_same_key_creates_one_message(search_api: tuple[TestClient, SearchStub]) -> None:
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    client, search = search_api
    sid = client.post("/api/v1/sessions").json()["session_id"]
    url = f"/api/v1/sessions/{sid}/messages"
    barrier = Barrier(2)

    def send(_: int) -> str:
        barrier.wait(timeout=5)
        response = client.post(url, json={"text": "шкаф"}, headers={"Idempotency-Key": "shared"})
        assert response.status_code == 200
        return str(response.text)

    with ThreadPoolExecutor(max_workers=2) as pool:
        states = list(pool.map(send, range(2)))
    assert states[0] == states[1]
    assert search.queries == ["шкаф"]
    assert client.get(f"/api/v1/sessions/{sid}").json()["revision"] == 1


def test_snapshot_survives_application_restart(synced: Settings) -> None:
    search = SearchStub(synced)
    app = create_app(synced)
    app.state.usecases = build_usecases(
        sql_repositories(), catalog_source=XmlKtruSource(synced.ktru_xml_dir), searcher=search
    )
    with TestClient(app) as client:
        sid = client.post("/api/v1/sessions").json()["session_id"]
        url = f"/api/v1/sessions/{sid}"
        saved = client.post(
            url + "/messages", json={"text": "шкаф"}, headers={"Idempotency-Key": "persist"}
        ).json()
    with TestClient(create_app(synced)) as restarted:
        assert restarted.get(url).json() == saved
        assert (
            restarted.post(
                url + "/messages", json={"text": "шкаф"}, headers={"Idempotency-Key": "persist"}
            ).json()
            == saved
        )


def test_key_is_scoped_to_session(client: TestClient) -> None:
    ids = [client.post("/api/v1/sessions").json()["session_id"] for _ in range(2)]
    for sid, text in zip(ids, ["стол", "шкаф"], strict=True):
        response = client.post(
            f"/api/v1/sessions/{sid}/messages",
            json={"text": text},
            headers={"Idempotency-Key": "same"},
        )
        assert response.status_code == 200
        assert response.json()["revision"] == 1
