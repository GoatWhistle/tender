"""Диалог через HTTP API: описание → вопрос → ответ → код, «не знаю» и устаревшие вопросы."""

from collections.abc import Callable
from dataclasses import replace
from decimal import Decimal
from typing import Any

from fastapi.testclient import TestClient

from app.domain.catalog import Characteristic, CharacteristicKind, Group, Position, Value

MATERIAL = "Вид материала столешницы"


def start(client: TestClient, *texts: str) -> tuple[str, dict[str, Any]]:
    sid = client.post("/api/v1/sessions").json()["session_id"]
    state: dict[str, Any] = {}
    for text in texts:
        state = client.post(f"/api/v1/sessions/{sid}/messages", json={"text": text}).json()
    return sid, state


def reply(client: TestClient, sid: str, body: dict[str, Any]) -> Any:
    return client.post(f"/api/v1/sessions/{sid}/answers", json=body)


def choose(client: TestClient, sid: str, state: dict[str, Any], label: str) -> dict[str, Any]:
    question = state["next_question"]
    option = next(o["id"] for o in question["options"] if o["label"] == label)
    response = reply(client, sid, {"question_id": question["question_id"], "option_id": option})
    assert response.status_code == 200, response.json()
    return dict(response.json())


def test_description_question_answer_code(facts_api: TestClient) -> None:
    sid, state = start(facts_api, "стол")
    assert state["status"] == "needs_clarification"
    question = state["next_question"]
    # Ширины вложены (900–1100 внутри 900–1400): спрашивать её бесполезно.
    assert question["kind"] == "discriminate"
    assert question["characteristic"] == MATERIAL
    # Порядок вариантов — по позициям группы в порядке кода, table-large раньше table-small.
    assert [o["label"] for o in question["options"]] == ["ЛДСП", "ДСП"]
    assert question["allow_unknown"] is True
    assert state["card_complete"] is False

    answered = choose(facts_api, sid, state, "ЛДСП")
    assert answered["revision"] == state["revision"] + 1
    assert answered["messages"] == state["messages"]
    assert answered["status"] == "resolved"
    assert [c["code"] for c in answered["candidates"] if not c["excluded"]] == ["table-large"]
    user = next(f for f in answered["facts"] if f["origin"] == "user")
    assert user["status"] == "confirmed_by_user" and user["value"] == "лдсп"
    # Ширина у позиции одна — заполнена из каталога и не спрашивается.
    derived = next(f for f in answered["facts"] if f["status"] == "derived_from_catalog")
    assert derived["characteristic_name"] == "Ширина"
    assert answered["missing_required"] == [] and answered["card_complete"] is True
    assert answered["next_question"] is None
    assert answered["dialog"][0]["option_id"] == question["options"][0]["id"]
    assert facts_api.get(f"/api/v1/sessions/{sid}").json() == answered

    again = reply(
        facts_api,
        sid,
        {"question_id": question["question_id"], "option_id": question["options"][0]["id"]},
    )
    assert again.status_code == 409 and again.json()["code"] == "stale_question"
    assert facts_api.get(f"/api/v1/sessions/{sid}").json()["revision"] == answered["revision"]


def test_unknown_gives_no_fact_and_no_repeat(facts_api: TestClient) -> None:
    sid, state = start(facts_api, "стол")
    question = state["next_question"]
    response = reply(facts_api, sid, {"question_id": question["question_id"], "unknown": True})
    assert response.status_code == 200
    skipped = response.json()
    assert skipped["status"] == "needs_clarification"
    assert skipped["next_question"] is None
    assert skipped["unanswered"] == [MATERIAL]
    assert skipped["facts"] == state["facts"] == []
    assert skipped["dialog"][0]["option_id"] is None and skipped["dialog"][0]["fact"] is None
    # Новое сообщение меняет контекст — вопрос может вернуться.
    more = facts_api.post(f"/api/v1/sessions/{sid}/messages", json={"text": "письменный"}).json()
    assert more["next_question"]["characteristic"] == MATERIAL


def test_answer_supersedes_conflicting_text_values(facts_api: TestClient) -> None:
    sid, state = start(facts_api, "ширина 1000 мм", "ширина 1300 мм")
    question = state["next_question"]
    assert question["kind"] == "conflict" and question["characteristic"] == "Ширина"
    assert [o["label"] for o in question["options"]] == ["1000 мм", "1300 мм"]
    answered = choose(facts_api, sid, state, "1300 мм")
    assert answered["status"] == "resolved"
    assert [f["status"] for f in answered["facts"] if f["characteristic_name"] == "Ширина"] == [
        "superseded",
        "superseded",
        "confirmed_by_user",
    ]
    excluded = next(c for c in answered["candidates"] if c["excluded"])
    assert excluded["code"] == "table-small"
    assert "указано 1300 мм" in excluded["reason"]["text"]


def test_answer_errors(facts_api: TestClient) -> None:
    sid, state = start(facts_api, "стол")
    question_id = state["next_question"]["question_id"]
    for body in [
        {"question_id": question_id, "option_id": "missing"},
        {"question_id": question_id},
        {"question_id": question_id, "option_id": "o1", "unknown": True},
    ]:
        response = reply(facts_api, sid, body)
        assert response.status_code == 422
    assert facts_api.get(f"/api/v1/sessions/{sid}").json() == state
    missing = reply(facts_api, "missing", {"question_id": question_id, "unknown": True})
    assert missing.status_code == 404 and missing.json()["code"] == "session_not_found"
    stale = reply(facts_api, sid, {"question_id": "q0", "unknown": True})
    assert stale.status_code == 409 and stale.json()["code"] == "stale_question"
    draft = facts_api.post("/api/v1/sessions").json()["session_id"]
    assert reply(facts_api, draft, {"question_id": "q0", "unknown": True}).status_code == 409


def test_indistinct_positions_are_ambiguous_in_catalog(
    group_api: Callable[[Group], TestClient], table_group: Group
) -> None:
    twin = table_group.leaves[1]
    group = replace(table_group, leaves=(twin, replace(twin, code="table-twin")))
    _, state = start(group_api(group), "стол")
    assert state["status"] == "ambiguous_in_catalog"
    assert state["next_question"] is None
    assert state["common_fields"] == [
        {"characteristic": "Ширина", "values": ["≥ 900 и ≤ 1400 мм"]},
        {"characteristic": MATERIAL, "values": ["ЛДСП"]},
    ]
    assert state["candidate_counts"]["compatible"] == 2


def test_numeric_interval_answer_and_required_fields_survive_snapshot(
    group_api: Callable[[Group], TestClient], table_group: Group
) -> None:
    def leaf(code: str, low: str, high: str) -> Position:
        base = table_group.leaves[0]
        width = replace(
            base.characteristics[0],
            values=(Value("w", min=Decimal(low), max=Decimal(high), unit="мм", unit_code="003"),),
        )
        color = Characteristic(
            "color",
            "Цвет",
            False,
            True,
            CharacteristicKind.single,
            (Value("white", text="белый"), Value("black", text="чёрный")),
        )
        material = replace(base.characteristics[1], values=(Value("m", text="ЛДСП"),))
        return replace(base, code=code, characteristics=(width, material, color))

    group = replace(
        table_group, leaves=(leaf("narrow", "900", "1100"), leaf("wide", "1200", "1400"))
    )
    client = group_api(group)
    sid, state = start(client, "стол")
    assert state["next_question"]["characteristic"] == "Ширина"
    resolved = choose(client, sid, state, "≥ 1200 и ≤ 1400 мм")
    assert resolved["status"] == "resolved"
    assert resolved["candidates"][0]["reason"]["given"] == "≥ 1200 и ≤ 1400 мм"
    assert resolved["card_complete"] is False
    assert resolved["missing_required"] == [{"characteristic": "color", "name": "Цвет"}]
    required = resolved["next_question"]
    assert required["kind"] == "required" and required["characteristic"] == "Цвет"
    skipped = reply(client, sid, {"question_id": required["question_id"], "unknown": True}).json()
    assert skipped["status"] == "resolved" and skipped["next_question"] is None
    assert skipped["missing_required"] == resolved["missing_required"]
    assert client.get(f"/api/v1/sessions/{sid}").json() == skipped


def test_later_description_conflicts_with_answer(facts_api: TestClient) -> None:
    sid, state = start(facts_api, "стол")
    answered = choose(facts_api, sid, state, "ЛДСП")
    assert [c["code"] for c in answered["candidates"] if not c["excluded"]] == ["table-large"]
    url = f"/api/v1/sessions/{sid}/messages"
    corrected = facts_api.post(url, json={"text": "столешница дсп"}).json()
    assert corrected["status"] == "conflict"
    assert corrected["candidate_counts"]["compatible"] == 2
    assert corrected["next_question"]["kind"] == "conflict"
    answer = next(f for f in corrected["facts"] if f["origin"] == "user")
    assert answer["status"] == "ambiguous"
