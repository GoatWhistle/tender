"""Контракт сопоставления и подтверждения через HTTP и общую проводку."""

from collections.abc import Iterator, Sequence
from dataclasses import replace
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.adapter.facts import DeterministicFactExtractor
from app.adapter.stub.decision import StubDecisionBackend
from app.domain.catalog import Characteristic, CharacteristicKind, Group, Position, Value
from app.domain.enum_mapping import AutoAcceptance
from app.domain.inference import (
    ChoiceAnswer,
    ChoiceBatch,
    ChoiceQuestion,
    Claim,
    ClaimAnswer,
    ClaimBatch,
    Verdict,
)
from app.domain.search import MethodContribution, SearchHit, SearchResult
from composition import build_usecases
from main import create_app, sql_repositories, sync_catalog
from settings import Settings


class Decision(StubDecisionBackend):
    """Сценарный внешний сервис: конкретные ответы и запись публичных запросов."""

    def __init__(self) -> None:
        super().__init__()
        self.values = {"Сталь"}
        self.score = 0.999
        self.questions: list[tuple[ChoiceQuestion, ...]] = []
        self.batches: list[tuple[Claim, ...]] = []

    def choose(self, context: str, questions: Sequence[ChoiceQuestion]) -> ChoiceBatch:
        self._raise_fault()
        self.questions.append(tuple(questions))
        answers = []
        for q in questions:
            selected = next((o.option_id for o in q.options if o.text in self.values), "unknown")
            probabilities = {
                o.option_id: (
                    self.score
                    if o.option_id == selected
                    else (1 - self.score) / (len(q.options) - 1)
                )
                for o in q.options
            }
            answers.append(ChoiceAnswer(q.question_id, probabilities, selected))
        return self.choice_reply or ChoiceBatch(tuple(answers), self.revision)

    def verify(self, context: str, claims: Sequence[Claim]) -> ClaimBatch:
        self._raise_fault()
        self.batches.append(tuple(claims))
        answers = []
        for c in claims:
            yes = any(c.text.endswith(f"«{v}».") for v in self.values)
            probabilities = {
                Verdict.supported: self.score if yes else 0.001,
                Verdict.contradicted: 0.0,
                Verdict.not_stated: 1 - self.score if yes else 0.999,
            }
            answers.append(ClaimAnswer(c.claim_id, probabilities))
        return self.claim_reply or ClaimBatch(tuple(answers), self.revision)


@pytest.fixture
def decision() -> Decision:
    return Decision()


@pytest.fixture
def enum_group() -> Group:
    root = Position("chairs", "Стул", "Мебель", "", "", True, None, (), ())
    material = Characteristic(
        "m",
        "Материал",
        False,
        True,
        CharacteristicKind.single,
        (Value("steel", text="Сталь"), Value("wood", text="Дерево")),
    )
    return Group(
        root,
        (
            replace(
                root,
                code="steel",
                parent=root.code,
                is_template=False,
                characteristics=(replace(material, values=(material.values[0],)),),
            ),
            replace(
                root,
                code="wood",
                parent=root.code,
                is_template=False,
                characteristics=(replace(material, values=(material.values[1],)),),
            ),
        ),
    )


@pytest.fixture
def enum_policy(request: pytest.FixtureRequest) -> AutoAcceptance:
    return request.param if hasattr(request, "param") else AutoAcceptance()


@pytest.fixture
def enum_api(
    settings: Settings, enum_group: Group, decision: Decision, enum_policy: AutoAcceptance
) -> Iterator[TestClient]:
    class Source:
        def load(self) -> list[Position]:
            return [enum_group.position, *enum_group.leaves]

    class Search:
        def run(
            self, description: str, category: str | None = None, limit: int = 10
        ) -> SearchResult:
            return SearchResult(
                description,
                (
                    SearchHit(
                        enum_group.position,
                        MethodContribution.of(1),
                        MethodContribution.of(None),
                        MethodContribution.of(None),
                    ),
                ),
            )

    source = Source()
    sync_catalog(settings, source)
    app = create_app(settings, source)
    app.state.usecases = build_usecases(
        sql_repositories(),
        catalog_source=source,
        searcher=Search(),
        fact_extractor=DeterministicFactExtractor(),
        decision=decision,
        enum_policy=enum_policy,
    )
    with TestClient(app) as client:
        yield client


def describe(client: TestClient, text: str = "Материал: стальная") -> tuple[str, dict[str, Any]]:
    sid = client.post("/api/v1/sessions").json()["session_id"]
    url = f"/api/v1/sessions/{sid}"
    response = client.post(url + "/messages", json={"text": text})
    assert response.status_code == 200
    return url, response.json()


def test_synonym_is_proposed_with_source_and_does_not_exclude(
    enum_api: TestClient, decision: Decision
) -> None:
    url, state = describe(enum_api)
    assert state["candidate_counts"]["compatible"] == 2
    fact = next(f for f in state["facts"] if f["origin"] == "decision")
    assert fact["value"] == "сталь"
    assert fact["status"] == "proposed"
    assert fact["source"]["quote"] == "Материал: стальная"
    assert fact["model_revision"] == "stub-1"
    assert state["enum_proposals"][0]["suggested"] == ["Сталь"]
    assert len(decision.questions) == len(decision.batches) == 1
    assert len(decision.questions[0]) == 1
    assert enum_api.get(url).json() == state


def test_accept_recalculates_and_rejects_stale_revision(
    enum_api: TestClient, decision: Decision
) -> None:
    url, first = describe(enum_api)
    proposal = first["enum_proposals"][0]
    body = {"expected_revision": 1, "proposal_id": proposal["id"], "action": "accept"}
    response = enum_api.post(url + "/enum-resolutions", json=body)
    assert response.status_code == 200
    accepted = response.json()
    assert accepted["candidate_counts"]["compatible"] == 1
    assert accepted["revision"] == 2
    assert not accepted["enum_proposals"]
    fact = next(f for f in accepted["facts"] if f["status"] == "confirmed_by_user")
    assert fact["value"] == "сталь"
    assert fact["origin"] == "decision"
    assert fact["source"]["quote"] == "Материал: стальная"
    assert enum_api.get(url).json() == accepted
    assert enum_api.post(url + "/enum-resolutions", json=body).status_code == 409
    assert enum_api.get(url).json() == accepted
    # Повторный анализ с другим ответом модели не теряет подтверждение пользователя.
    decision.values = {"Дерево"}
    again = enum_api.post(url + "/messages", json={"text": "Для офиса"}).json()
    assert again["candidate_counts"]["compatible"] == 1
    assert next(c for c in again["candidates"] if not c["excluded"])["code"] == "steel"
    assert any(f["status"] == "confirmed_by_user" and f["value"] == "сталь" for f in again["facts"])


@pytest.mark.parametrize(
    "action,values,compatible", [("choose", ["Дерево"], 1), ("unknown", [], 2)]
)
def test_other_value_and_unknown(
    enum_api: TestClient, action: str, values: list[str], compatible: int
) -> None:
    url, first = describe(enum_api)
    response = enum_api.post(
        url + "/enum-resolutions",
        json={
            "expected_revision": first["revision"],
            "proposal_id": first["enum_proposals"][0]["id"],
            "action": action,
            "values": values,
        },
    )
    assert response.status_code == 200
    state = response.json()
    assert state["candidate_counts"]["compatible"] == compatible
    assert not state["enum_proposals"]
    if action == "choose":
        assert next(c for c in state["candidates"] if not c["excluded"])["code"] == "wood"
    else:
        assert not any(
            f["status"] in {"confirmed_by_user", "accepted_from_model", "derived_from_catalog"}
            for f in state["facts"]
        )
    assert enum_api.get(url).json() == state


@pytest.mark.parametrize("values", [["Пластик"], ["Сталь", "Дерево"], [], ["Сталь", "Сталь"]])
def test_other_value_must_match_catalog_cardinality(
    enum_api: TestClient, values: list[str]
) -> None:
    url, first = describe(enum_api)
    response = enum_api.post(
        url + "/enum-resolutions",
        json={
            "expected_revision": 1,
            "proposal_id": first["enum_proposals"][0]["id"],
            "action": "choose",
            "values": values,
        },
    )
    assert response.status_code == 422
    assert enum_api.get(url).json() == first


def test_multiple_values_survive_as_one_proposal(
    enum_api: TestClient, enum_group: Group, settings: Settings, decision: Decision
) -> None:
    material = replace(
        enum_group.leaves[0].characteristics[0],
        kind=CharacteristicKind.multiple,
        values=(Value("c", text="Хлопок"), Value("p", text="Полиэстер")),
    )

    class Source:
        def load(self) -> list[Position]:
            return [
                enum_group.position,
                replace(enum_group.leaves[0], characteristics=(material,)),
                replace(
                    enum_group.leaves[1],
                    characteristics=(replace(material, values=(material.values[0],)),),
                ),
            ]

    sync_catalog(settings, Source())
    decision.values = {"Хлопок", "Полиэстер"}
    url, first = describe(enum_api, "Материал: хлопок и полиэстер")
    assert first["enum_proposals"][0]["suggested"] == ["Полиэстер", "Хлопок"]
    assert first["candidate_counts"]["compatible"] == 2
    assert not decision.questions  # множественное значение не сжато до одного choose
    response = enum_api.post(
        url + "/enum-resolutions",
        json={
            "expected_revision": 1,
            "proposal_id": first["enum_proposals"][0]["id"],
            "action": "accept",
        },
    )
    assert response.status_code == 200
    state = response.json()
    assert state["candidate_counts"]["compatible"] == 1
    assert {f["value"] for f in state["facts"] if f["status"] == "confirmed_by_user"} == {
        "хлопок",
        "полиэстер",
    }
    assert enum_api.get(url).json() == state


@pytest.mark.parametrize("enum_policy", [AutoAcceptance(0.99, "stub-1")], indirect=True)
@pytest.mark.parametrize(
    "text,score,accepted",
    [
        ("Материал: стальная", 0.999, True),
        ("Материал: стальная", 0.8, False),
        ("Стальная", 0.999, True),
        ("Материал: деревянная столешница и металлические ножки", 0.999, False),
    ],
)
def test_auto_acceptance_requires_threshold_and_binding(
    enum_api: TestClient, decision: Decision, text: str, score: float, accepted: bool
) -> None:
    decision.score = score
    _, state = describe(enum_api, text)
    facts = [f for f in state["facts"] if f["origin"] == "decision"]
    assert facts
    assert (facts[0]["status"] == "accepted_from_model") is accepted
    assert state["candidate_counts"]["compatible"] == (1 if accepted else 2)


def test_unknown_does_not_fill_required_field_from_catalog(
    enum_api: TestClient, settings: Settings, enum_group: Group
) -> None:
    class Source:
        def load(self) -> list[Position]:
            return [enum_group.position, enum_group.leaves[0]]

    sync_catalog(settings, Source())
    url, first = describe(enum_api)
    assert not first["card_complete"]
    state = enum_api.post(
        url + "/enum-resolutions",
        json={
            "expected_revision": 1,
            "proposal_id": first["enum_proposals"][0]["id"],
            "action": "unknown",
        },
    ).json()
    assert not state["card_complete"]
    assert state["missing_required"] == [{"characteristic": "m", "name": "Материал"}]
    assert not state["facts"]


def test_accepted_multiple_excludes_single_choice_even_if_both_values_listed(
    enum_api: TestClient,
    enum_group: Group,
    settings: Settings,
    decision: Decision,
) -> None:
    material = replace(
        enum_group.leaves[0].characteristics[0],
        kind=CharacteristicKind.multiple,
        values=(Value("c", text="Хлопок"), Value("p", text="Полиэстер")),
    )

    class Source:
        def load(self) -> list[Position]:
            return [
                enum_group.position,
                replace(enum_group.leaves[0], characteristics=(material,)),
                replace(
                    enum_group.leaves[1],
                    characteristics=(replace(material, kind=CharacteristicKind.single),),
                ),
            ]

    sync_catalog(settings, Source())
    decision.values = {"Хлопок", "Полиэстер"}
    url, first = describe(enum_api, "Материал: хлопок и полиэстер")
    state = enum_api.post(
        url + "/enum-resolutions",
        json={
            "expected_revision": 1,
            "proposal_id": first["enum_proposals"][0]["id"],
            "action": "accept",
        },
    ).json()
    assert state["candidate_counts"]["compatible"] == 1
    assert (
        next(c for c in state["candidates"] if c["excluded"])["reason"]["characteristic"]
        == "Материал"
    )


def test_unknown_does_not_immediately_repeat_the_same_question(enum_api: TestClient) -> None:
    url, first = describe(enum_api)
    assert first["next_question"] is None  # действия предложения уже спрашивают это поле
    state = enum_api.post(
        url + "/enum-resolutions",
        json={
            "expected_revision": 1,
            "proposal_id": first["enum_proposals"][0]["id"],
            "action": "unknown",
        },
    ).json()
    assert state["next_question"] is None
    assert "Материал" in state["unanswered"]


@pytest.mark.parametrize("failure", ["timeout", "exception", "invalid"])
def test_decision_failure_preserves_draft(
    enum_api: TestClient, decision: Decision, failure: str
) -> None:
    if failure == "timeout":
        decision.time_out()
    elif failure == "exception":
        decision.fail()
    else:
        decision.choice_reply = ChoiceBatch((), "broken")
    url, state = describe(enum_api)
    assert state["status"] == "technical_error"
    assert state["messages"][0]["text"] == "Материал: стальная"
    assert state["errors"][0]["code"] == "technical_error"
    assert state["revision"] == 1
    assert enum_api.get(url).json() == state


@pytest.mark.parametrize(
    "text,values", [("не деревянный", {"Дерево"}), ("материал не указан", set()), ("стул", set())]
)
def test_negation_and_not_stated_create_no_model_fact(
    enum_api: TestClient, decision: Decision, text: str, values: set[str]
) -> None:
    decision.values = values
    _, state = describe(enum_api, text)
    assert not state["enum_proposals"]
    assert not any(f["origin"] == "decision" for f in state["facts"])
    assert not state["errors"]
    assert state["candidate_counts"]["compatible"] == 2


def test_single_choice_never_silently_drops_second_value(
    enum_api: TestClient, decision: Decision
) -> None:
    decision.values = {"Сталь", "Дерево"}
    url, state = describe(enum_api, "Материал: сталь и дерево")
    assert set(state["enum_proposals"][0]["suggested"]) == {"Сталь", "Дерево"}
    assert state["candidate_counts"]["compatible"] == 2
    response = enum_api.post(
        url + "/enum-resolutions",
        json={
            "expected_revision": 1,
            "proposal_id": state["enum_proposals"][0]["id"],
            "action": "accept",
        },
    )
    assert response.status_code == 422
    assert enum_api.get(url).json() == state


@pytest.mark.parametrize("enum_policy", [AutoAcceptance(0.99, "another-revision")], indirect=True)
def test_calibration_does_not_transfer_to_another_model_revision(enum_api: TestClient) -> None:
    _, state = describe(enum_api)
    assert state["candidate_counts"]["compatible"] == 2
    assert all(f["status"] == "proposed" for f in state["facts"])


def test_equivalent_field_names_share_result_and_keep_binding(
    enum_api: TestClient,
    enum_group: Group,
    settings: Settings,
    decision: Decision,
) -> None:
    class Source:
        def load(self) -> list[Position]:
            lower = replace(enum_group.leaves[1].characteristics[0], name="материал")
            return [
                enum_group.position,
                enum_group.leaves[0],
                replace(enum_group.leaves[1], characteristics=(lower,)),
            ]

    sync_catalog(settings, Source())
    url, first = describe(enum_api)
    assert len(decision.questions[0]) == 1
    state = enum_api.post(
        url + "/enum-resolutions",
        json={
            "expected_revision": 1,
            "proposal_id": first["enum_proposals"][0]["id"],
            "action": "accept",
        },
    ).json()
    assert state["candidate_counts"]["compatible"] == 1


@pytest.mark.parametrize("enum_policy", [AutoAcceptance(0.90, "stub-1")], indirect=True)
def test_free_synonym_can_be_auto_accepted_when_value_has_one_field(
    enum_api: TestClient, decision: Decision
) -> None:
    decision.score = 0.92
    _, state = describe(enum_api, "Стул из стали")
    assert state["candidate_counts"]["compatible"] == 1
    assert any(f["status"] == "accepted_from_model" for f in state["facts"])
