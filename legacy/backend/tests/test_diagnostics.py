from collections.abc import Callable
from dataclasses import replace
from decimal import Decimal
from typing import Any, cast

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.domain.catalog import Bound, Group, Value
from app.domain.diagnostics import SpellingSuggestion
from app.domain.facts import FactSource
from app.domain.sessions import Message


def test_enum_typo_is_saved_without_accepting_correction(facts_api: TestClient) -> None:
    sid = facts_api.post("/api/v1/sessions").json()["session_id"]
    text = "Стол. Вид материала столешницы: ЛДПС."
    response = facts_api.post(f"/api/v1/sessions/{sid}/messages", json={"text": text})
    assert response.status_code == 200
    state = response.json()
    (error,) = state["errors"]
    assert error["kind"] == "typo"
    assert error["suggestion"] == "ЛДСП"
    assert error["source_quote"] == "Вид материала столешницы: ЛДПС"
    assert error["requires_confirmation"] is True
    assert error["rule_ref"]
    assert not any(f["status"] == "accepted_from_text" for f in state["facts"])
    assert state["candidate_counts"]["excluded_by_rules"] == 0
    assert state["messages"][0]["text"] == text
    assert facts_api.get(f"/api/v1/sessions/{sid}").json() == state


def analyze(client: TestClient, text: str) -> dict[str, Any]:
    sid = client.post("/api/v1/sessions").json()["session_id"]
    response = client.post(f"/api/v1/sessions/{sid}/messages", json={"text": text})
    assert response.status_code == 200
    result: dict[str, Any] = response.json()
    return result


def test_unknown_value_and_numeric_group_union(facts_api: TestClient) -> None:
    unknown = analyze(facts_api, "Вид материала столешницы: телепатический")
    assert [e["kind"] for e in unknown["errors"]] == ["value_not_in_catalog"]
    outside = analyze(facts_api, "Ширина 120 см")
    assert outside["candidate_counts"]["excluded_by_rules"] == 1
    assert outside["errors"] == []
    outside = analyze(facts_api, "Ширина 120 мм")
    (error,) = outside["errors"]
    assert error["kind"] == "out_of_range"
    assert error["suggestion"] == "120 см"
    assert "900" in error["explanation"] and "1400" in error["explanation"]
    assert outside["facts"][0]["raw_unit"] == "мм"
    assert outside["messages"][0]["text"] == "Ширина 120 мм"


def test_reviewed_alias_is_normalization_in_component_context(
    group_api: Callable[..., TestClient], table_group: Group
) -> None:
    from dataclasses import replace

    from app.domain.catalog import Value

    leaves = tuple(
        replace(
            p,
            characteristics=(
                replace(
                    p.characteristics[1],
                    name="Материал обивки",
                    values=(Value("leather", text="Искусственная кожа"),),
                ),
            ),
        )
        for p in table_group.leaves
    )
    client = group_api(replace(table_group, leaves=leaves))
    state = analyze(client, "Материал обивки: кожзам")
    assert state["errors"] == []
    (item,) = state["normalizations"]
    assert item["kind"] == "synonym"
    assert item["suggestion"] == "Искусственная кожа"
    assert "B65" in item["alias_source"]
    state = analyze(client, "Материал каркаса: кожзам")
    assert state["normalizations"] == []


def test_unbound_spelling_never_accepts_fact_and_failure_keeps_data(
    group_api: Callable[..., TestClient], table_group: Group
) -> None:
    from app.domain.errors import ModelFailure
    from app.domain.facts import FactSource

    class Spelling:
        failure = False
        invalid = False

        def suggest(self, message: Message) -> tuple[SpellingSuggestion, ...]:
            if self.failure:
                raise ModelFailure()
            start = message.text.index("дреево")
            return (
                SpellingSuggestion(
                    FactSource(message.id, "дреево", start + int(self.invalid), start + 6), "дерево"
                ),
            )

    spelling = Spelling()
    client = group_api(table_group, spelling=spelling)
    text = "🪑 Стол из дреево"
    state = analyze(client, text)
    (item,) = state["errors"]
    assert item["kind"] == "typo"
    assert item["fact_id"] is None and item["rule_ref"] == []
    assert item["source_quote"] == "дреево"
    assert item["source"]["start"] == 10
    assert not state["facts"]
    assert state["candidate_counts"]["excluded_by_rules"] == 0
    assert client.get("/api/v1/sessions/" + state["session_id"]).json() == state
    spelling.invalid = True
    invalid = analyze(client, text)
    assert [e.get("code") for e in invalid["errors"]] == ["spelling_invalid_response"]
    spelling.failure = True
    failed = analyze(client, text + ". Ширина 120 мм")
    assert failed["status"] != "technical_error"
    assert {e.get("kind", e.get("code")) for e in failed["errors"]} == {
        "out_of_range",
        "spelling_failed",
    }
    assert failed["messages"][0]["text"] == text + ". Ширина 120 мм"


@pytest.mark.parametrize(
    ("allowed", "raw", "kind"),
    [
        ("ДСП", "ДПС", "value_not_in_catalog"),
        ("ЛДСП", "ЛДПС", "typo"),
        ("бумажка", "бумжка", "typo"),
        ("бумажка", "бумжк", "value_not_in_catalog"),
        ("бумажный", "бумжны", "typo"),
        ("бумажный", "бмжны", "value_not_in_catalog"),
    ],
)
def test_enum_length_thresholds(
    group_api: Callable[..., TestClient], table_group: Group, allowed: str, raw: str, kind: str
) -> None:
    group = enum_group(table_group, (allowed,))
    state = analyze(group_api(group), "Материал: " + raw)
    assert [e["kind"] for e in state["errors"]] == [kind]


def enum_group(group: Group, values: tuple[str, ...]) -> Group:
    leaf = group.leaves[0]
    char = replace(
        leaf.characteristics[1],
        name="Материал",
        values=tuple(Value(str(i), text=v) for i, v in enumerate(values)),
    )
    return replace(group, leaves=(replace(leaf, characteristics=(char,)),))


def test_multiple_candidates_and_incomplete_rules(
    group_api: Callable[..., TestClient], table_group: Group
) -> None:
    group = enum_group(table_group, ("рама", "вата"))
    state = analyze(group_api(group), "Материал: рата")
    (item,) = state["errors"]
    assert set(item["candidates"]) == {"рама", "вата"}
    assert item["suggestion"] is None
    # У второй позиции нет проверенного правила — отсутствия не доказали.
    group = replace(
        group, leaves=(*group.leaves, replace(table_group.leaves[1], characteristics=()))
    )
    assert analyze(group_api(group), "Материал: телепатический")["errors"] == []
    bad = replace(group.leaves[0].characteristics[0], values=())
    group = replace(group, leaves=(replace(group.leaves[0], characteristics=(bad,)),))
    assert analyze(group_api(group), "Материал: телепатический")["errors"] == []


@pytest.mark.parametrize(
    "text",
    [
        "Не Материал: дерево",
        "Материал: не дерево",
        "Неизвестный материал: дерево",
        "Материал каркаса: дерево",
    ],
)
def test_unknown_or_negated_field_does_not_bind(
    group_api: Callable[..., TestClient], table_group: Group, text: str
) -> None:
    state = analyze(group_api(enum_group(table_group, ("дерево",))), text)
    assert state["errors"] == []
    assert not any(f["status"] == "accepted_from_text" for f in state["facts"])
    assert state["candidate_counts"]["excluded_by_rules"] == 0


@pytest.mark.parametrize(
    ("text", "error"),
    [
        ("Ширина: 900 мм", False),
        ("Ширина: 1000 мм", True),
        ("Ширина: 1100 мм", False),
        ("Ширина: 1200 мм", False),
        ("Ширина: 1201 мм", True),
        ("Ширина: 1500 мм", False),
        ("Ширина: 1500 кг", True),
    ],
)
def test_numeric_union_open_boundaries_and_discrete_values(
    group_api: Callable[..., TestClient], table_group: Group, text: str, error: bool
) -> None:
    char = replace(
        table_group.leaves[0].characteristics[0],
        values=(
            Value("a", min=Decimal("900"), max=Decimal("1000"), max_op=Bound.less, unit_code="003"),
            Value("b", min=Decimal("1100"), max=Decimal("1200"), unit_code="003"),
            Value("c", concrete=Decimal("1500"), unit_code="003"),
        ),
    )
    group = replace(table_group, leaves=(replace(table_group.leaves[0], characteristics=(char,)),))
    state = analyze(group_api(group), text)
    assert bool(state["errors"]) is error
    if error:
        (item,) = state["errors"]
        assert item["kind"] == "out_of_range"
        assert "менее 1000" in item["explanation"]
        if "кг" in text:
            assert item["suggestion"] is None


def test_value_in_previously_excluded_position_is_not_absent(facts_api: TestClient) -> None:
    sid = facts_api.post("/api/v1/sessions").json()["session_id"]
    url = f"/api/v1/sessions/{sid}/messages"
    facts_api.post(url, json={"text": "Вид материала столешницы: ДСП"})
    state = facts_api.post(url, json={"text": "Ширина 1300 мм"}).json()
    assert state["status"] == "conflict"
    assert state["errors"] == []


def test_single_catalog_value_does_not_silently_replace_typo(
    group_api: Callable[..., TestClient],
    table_group: Group,
) -> None:
    state = analyze(group_api(enum_group(table_group, ("дерево",))), "Материал: дреево")
    assert state["errors"][0]["kind"] == "typo"
    assert not any(
        f["status"] in {"accepted_from_text", "derived_from_catalog"} for f in state["facts"]
    )
    assert state["card_complete"] is False


def test_spelling_replay_and_dialog_do_not_recheck_text(
    group_api: Callable[..., TestClient],
    table_group: Group,
) -> None:
    class Once:
        used = False

        def suggest(self, message: Message) -> tuple[SpellingSuggestion, ...]:
            if self.used:
                raise AssertionError("Орфография уже проверена для этого сообщения")
            self.used = True
            return (SpellingSuggestion(FactSource(message.id, "дреево", 8, 14), "дерево"),)

    client = group_api(table_group, spelling=Once())
    sid = client.post("/api/v1/sessions").json()["session_id"]
    url = f"/api/v1/sessions/{sid}"
    headers = {"Idempotency-Key": "first"}
    state = client.post(url + "/messages", json={"text": "Стол из дреево"}, headers=headers).json()
    assert state["errors"][0]["kind"] == "typo"
    assert (
        client.post(url + "/messages", json={"text": "Стол из дреево"}, headers=headers).json()
        == state
    )
    question = state["next_question"]
    answered = client.post(
        url + "/answers", json={"question_id": question["question_id"], "unknown": True}
    ).json()
    assert answered["errors"] == state["errors"]
    assert answered["messages"] == state["messages"]
    assert client.get(url).json() == answered


def test_http_reads_legacy_snapshot_without_normalizations(facts_api: TestClient) -> None:
    from sqlalchemy import select
    from sqlalchemy.orm import Session

    from app.repository.orm.sessions import SessionRevision

    state = facts_api.post("/api/v1/sessions").json()
    # Подготовка снимка предыдущей версии приложения; проверяем только публичное чтение.
    with Session(cast(FastAPI, facts_api.app).state.engine) as session:
        row = session.scalar(
            select(SessionRevision).where(SessionRevision.session_id == state["session_id"])
        )
        assert row is not None
        snapshot = dict(row.snapshot)
        snapshot.pop("normalizations")
        row.snapshot = snapshot
        session.commit()
    assert facts_api.get("/api/v1/sessions/" + state["session_id"]).json() == state


@pytest.mark.parametrize(("start", "end"), [(-100, -90), (100, 106), (8, 80), (9, 14)])
def test_invalid_spelling_offsets_never_break_analysis(
    group_api: Callable[..., TestClient],
    table_group: Group,
    start: int,
    end: int,
) -> None:
    class InvalidSpelling:
        def suggest(self, message: Message) -> tuple[SpellingSuggestion, ...]:
            return (SpellingSuggestion(FactSource(message.id, "дреево", start, end), "дерево"),)

    state = analyze(group_api(table_group, spelling=InvalidSpelling()), "Стол из дреево")
    assert state["errors"][0]["code"] == "spelling_invalid_response"
    assert state["status"] != "technical_error"
