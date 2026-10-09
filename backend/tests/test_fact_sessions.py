import pytest
from fastapi.testclient import TestClient

from app.domain.catalog import Group
from settings import Settings


def test_description_narrows_group_and_persists_explanations(facts_api: TestClient) -> None:
    client = facts_api
    sid = client.post("/api/v1/sessions").json()["session_id"]
    url = f"/api/v1/sessions/{sid}"
    text = "стол шириной 1,2 м, столешница лдсп"
    response = client.post(
        url + "/messages", json={"text": text}, headers={"Idempotency-Key": "first"}
    )
    assert response.status_code == 200
    state = response.json()
    assert state["status"] == "resolved"
    assert state["candidate_counts"] == {"in_group": 2, "compatible": 1, "excluded_by_rules": 1}
    assert state["facts"][0]["value"] == "1.2"
    assert state["facts"][0]["unit_code"] == "006"
    excluded = next(c for c in state["candidates"] if c["excluded"])
    matched = next(c for c in state["candidates"] if not c["excluded"])
    assert "не более 1100 мм" in excluded["reason"]["text"]
    assert "указано 1.2 м" in excluded["reason"]["text"]
    assert [c["result"] for c in excluded["checks"]] == ["mismatch", "mismatch"]
    assert matched["matched_facts"] == [f["id"] for f in state["facts"]]
    assert client.get(url).json() == state
    assert (
        client.post(
            url + "/messages", json={"text": text}, headers={"Idempotency-Key": "first"}
        ).json()
        == state
    )


@pytest.mark.parametrize(
    ("text", "status", "compatible"),
    [
        ("стол", "needs_clarification", 2),
        ("стол 1200 мм", "needs_clarification", 2),
        ("стол ширина 2000 мм", "conflict", 0),
        ("стол ширина 1200 мм", "resolved", 1),
        ("стол ширина 1000–1200 мм", "needs_clarification", 2),
    ],
)
def test_statuses_and_count_invariants(
    facts_api: TestClient, text: str, status: str, compatible: int
) -> None:
    sid = facts_api.post("/api/v1/sessions").json()["session_id"]
    state = facts_api.post(f"/api/v1/sessions/{sid}/messages", json={"text": text}).json()
    assert state["status"] == status
    counts = state["candidate_counts"]
    assert counts["compatible"] == compatible
    assert counts["compatible"] + counts["excluded_by_rules"] == counts["in_group"] == 2
    assert len(state["candidates"]) == 2
    if text == "стол":
        assert all(
            c["checks"] == [{"fact_id": None, "result": "unknown"}] for c in state["candidates"]
        )


def test_conflicting_messages_restore_previously_excluded_positions(facts_api: TestClient) -> None:
    sid = facts_api.post("/api/v1/sessions").json()["session_id"]
    url = f"/api/v1/sessions/{sid}"
    first = facts_api.post(url + "/messages", json={"text": "ширина 1200 мм"}).json()
    assert first["candidate_counts"]["compatible"] == 1
    second = facts_api.post(url + "/messages", json={"text": "ширина 1300 мм"}).json()
    assert second["candidate_counts"]["compatible"] == 2
    assert all(f["status"] == "ambiguous" for f in second["facts"])
    assert "противоречивые значения поля Ширина" in second["warnings"]
    assert all(c["reason"] is None for c in second["candidates"])
    assert facts_api.get(url).json() == second


def test_range_is_saved_as_decimal_strings(facts_api: TestClient) -> None:
    sid = facts_api.post("/api/v1/sessions").json()["session_id"]
    url = f"/api/v1/sessions/{sid}"
    state = facts_api.post(url + "/messages", json={"text": "ширина 100–120 см"}).json()
    assert state["facts"][0]["value"] == ["100", "120"]
    assert facts_api.get(url).json() == state


def test_unsupported_rule_blocks_resolution_without_a_fact(
    facts_api: TestClient, settings: "Settings", table_group: "Group"
) -> None:
    from dataclasses import replace
    from decimal import Decimal

    from app.domain.catalog import Position, Value
    from main import sync_catalog

    width = replace(
        table_group.leaves[0].characteristics[0],
        values=(Value("unknown-unit", concrete=Decimal(100), unit_code="999"),),
    )
    leaf = replace(table_group.leaves[0], characteristics=(width,))

    class Source:
        def load(self) -> list[Position]:
            return [table_group.position, leaf]

    sync_catalog(settings, Source())
    sid = facts_api.post("/api/v1/sessions").json()["session_id"]
    state = facts_api.post(f"/api/v1/sessions/{sid}/messages", json={"text": "стол"}).json()
    assert state["status"] == "needs_clarification"
    assert state["candidate_counts"]["compatible"] == 1
    assert any(c["result"] == "unsupported" for c in state["candidates"][0]["checks"])
    assert not state["candidates"][0]["excluded"]
