from fastapi.testclient import TestClient

from main import create_app
from settings import Settings


def test_save_draft_preserves_state_and_input_across_restart(
    facts_api: TestClient, settings: Settings
) -> None:
    client = facts_api
    sid = client.post("/api/v1/sessions").json()["session_id"]
    url = f"/api/v1/sessions/{sid}"
    state = client.post(url + "/messages", json={"text": "Стол ширина 100 см"}).json()
    width = state["facts"][0]["id"]
    state = client.patch(
        url + "/facts/" + width, json={"action": "delete", "expected_revision": state["revision"]}
    ).json()
    assert state["fact_history"]
    payload = {"expected_revision": state["revision"], "input_text": "  ещё не отправлено\n"}
    for _ in range(2):
        response = client.put(url + "/draft", json=payload)
        assert response.status_code == 200
        assert response.json()["state"] == state
        assert response.json()["input_text"] == payload["input_text"]
    with TestClient(create_app(settings)) as restarted:
        drafts = restarted.get("/api/v1/sessions/drafts").json()
        assert len(drafts) == 1
        assert drafts[0]["session_id"] == sid
        assert drafts[0]["saved_revision"] == state["revision"]
        reopened = restarted.get(url + "/draft").json()
        assert reopened["state"] == state
        assert reopened["input_text"] == payload["input_text"]
        assert restarted.get(url).json() == state
    continued = client.patch(
        url + "/facts/" + width, json={"action": "restore", "expected_revision": state["revision"]}
    )
    assert continued.status_code == 200
    assert continued.json()["revision"] == state["revision"] + 1
    # Старое окно не перезаписывает сохранённый ввод и не откатывает сессию.
    assert client.put(url + "/draft", json=payload).status_code == 409
    reopened = client.get(url + "/draft").json()
    assert reopened["state"] == continued.json()
    assert reopened["saved_revision"] == state["revision"]
    assert reopened["input_text"] == payload["input_text"]
    assert (
        client.patch(
            url + "/facts/" + width,
            json={"action": "delete", "expected_revision": state["revision"]},
        ).status_code
        == 409
    )


def test_draft_and_export_unknown_session_and_unsubmitted_text(client: TestClient) -> None:
    assert client.get("/api/v1/sessions/drafts").json() == []
    base = "/api/v1/sessions/unknown"
    assert client.get(base + "/draft").status_code == 404
    assert (
        client.put(base + "/draft", json={"expected_revision": 0, "input_text": "text"}).status_code
        == 404
    )
    assert client.post(base + "/export").status_code == 404
    created = client.post("/api/v1/sessions").json()
    base = "/api/v1/sessions/" + created["session_id"]
    assert client.get(base + "/draft").json()["saved_at"] is None
    response = client.put(
        base + "/draft", json={"expected_revision": 0, "input_text": "только ввод"}
    )
    assert response.status_code == 200
    assert response.json()["state"] == created
    assert client.get(base).json()["messages"] == []
    assert client.get(base).json()["facts"] == []
    assert client.post(base + "/export").json()["document_kind"] == "draft"
    assert (
        client.put(base + "/draft", json={"expected_revision": -1, "input_text": ""}).status_code
        == 422
    )
    assert (
        client.put(
            base + "/draft", json={"expected_revision": 0, "input_text": "я" * 100001}
        ).status_code
        == 422
    )
    assert client.get(base + "/draft").json()["input_text"] == "только ввод"
