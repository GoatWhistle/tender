"""Извлечение свободных фактов через HTTP с внешними моделями-заглушками."""

from collections.abc import Iterator, Sequence
from dataclasses import replace
from decimal import Decimal
from typing import Any, cast

import pytest
from fastapi.testclient import TestClient

from app.adapter.facts import DeterministicFactExtractor
from app.adapter.stub.decision import StubDecisionBackend
from app.adapter.stub.extractor import StubFactExtractor
from app.domain.catalog import Characteristic, CharacteristicKind, Group, Position, Value
from app.domain.errors import InvalidExtraction
from app.domain.inference import (
    Claim,
    ClaimAnswer,
    ClaimBatch,
    ExtractedFact,
    Extraction,
    ExtractionRequest,
    Verdict,
)
from app.domain.search import MethodContribution, SearchHit, SearchResult
from app.usecase.extraction import VerificationPolicy
from composition import build_usecases
from main import create_app, sql_repositories, sync_catalog
from settings import Settings

REVISION = "a20448012c213128955ca0c693e7c943865cab77"


class Extractor(StubFactExtractor):
    def __init__(self) -> None:
        super().__init__()
        self.overrides: dict[str, Any] = {}
        self.outcomes: list[str] = []

    def extract(self, request: ExtractionRequest) -> Extraction:
        self.requests.append(request)
        if self.outcomes:
            outcome = self.outcomes.pop(0)
            if outcome == "json":
                raise InvalidExtraction()
            if outcome == "empty":
                return Extraction((), self.revision)
        message = request.messages[-1]
        return Extraction(
            (
                replace(
                    ExtractedFact("Высота", "75", "см", message.text, message.message_id),
                    **self.overrides,
                ),
            ),
            self.revision,
        )


class Verifier(StubDecisionBackend):
    def __init__(self) -> None:
        super().__init__(REVISION)
        self.score = 0.90
        self.contradicted = False
        self.contexts: list[str] = []

    def verify(self, context: str, claims: Sequence[Claim]) -> ClaimBatch:
        self._raise_fault()
        self.contexts.append(context)
        return ClaimBatch(
            tuple(
                ClaimAnswer(
                    c.claim_id,
                    {
                        Verdict.supported: self.score,
                        Verdict.contradicted: 1 - self.score if self.contradicted else 0.0,
                        Verdict.not_stated: 0.0 if self.contradicted else 1 - self.score,
                    },
                )
                for c in claims
            ),
            self.revision,
        )


@pytest.fixture
def extractor() -> Extractor:
    return Extractor()


@pytest.fixture
def verifier() -> Verifier:
    return Verifier()


@pytest.fixture
def qualitative(request: pytest.FixtureRequest) -> str | None:
    value = getattr(request, "param", None)
    return "Цвет" if value is True else str(value) if value else None


@pytest.fixture
def extraction_api(
    settings: Settings,
    extractor: Extractor,
    verifier: Verifier,
    request: pytest.FixtureRequest,
    qualitative: str | None,
) -> Iterator[TestClient]:
    root = Position("tables", "Стол", "Мебель", "", "", True, None, (), ())
    height = Characteristic(
        "h",
        "Высота",
        True,
        True,
        CharacteristicKind.single,
        (Value("v", concrete=Decimal("75"), unit_code="004"),),
    )
    if qualitative:
        height = Characteristic("text", qualitative, False, True, CharacteristicKind.single)
    group = Group(
        root,
        (
            replace(
                root, code="low", parent=root.code, is_template=False, characteristics=(height,)
            ),
            replace(
                root,
                code="high",
                parent=root.code,
                is_template=False,
                characteristics=(
                    replace(
                        height,
                        values=()
                        if qualitative
                        else (Value("v2", concrete=Decimal("90"), unit_code="004"),),
                    ),
                ),
            ),
        ),
    )

    class Source:
        def load(self) -> list[Position]:
            return [group.position, *group.leaves]

    class Search:
        def run(
            self, description: str, category: str | None = None, limit: int = 10
        ) -> SearchResult:
            return SearchResult(
                description,
                (
                    SearchHit(
                        group.position,
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
        decision=verifier,
        model_extractor=extractor,
        verification_policy=getattr(request, "param", VerificationPolicy()),
    )
    with TestClient(app) as client:
        yield client


def message(api: TestClient, text: str) -> dict[str, Any]:
    sid = api.post("/api/v1/sessions").json()["session_id"]
    response = api.post(f"/api/v1/sessions/{sid}/messages", json={"text": text})
    assert response.status_code == 200, response.text
    return cast(dict[str, Any], response.json())


def test_verified_free_value_is_accepted_at_threshold(
    extraction_api: TestClient, extractor: Extractor
) -> None:
    state = message(extraction_api, "Стол от пола до верха 75 см")
    facts = [f for f in state["facts"] if f["normalization_rule"] == "verified_extraction_v1"]
    assert len(facts) == 1
    assert facts[0]["status"] == "accepted_from_model"
    assert state["candidate_counts"]["compatible"] == 1
    assert [t.attribute_ref for t in extractor.requests[0].targets] == ["Высота"]


@pytest.mark.parametrize(
    "overrides",
    [
        {"source_quote": "несуществующая цитата"},
        {"raw_unit": "кг"},
        {"raw_value": "NaN"},
        {"raw_value": "90"},
        {"negated": True},
        {"uncertain": True},
        {"subject_ref": "ножки"},
    ],
)
def test_structurally_unsafe_extract_never_excludes_positions(
    extraction_api: TestClient, extractor: Extractor, overrides: dict[str, Any]
) -> None:
    extractor.overrides = overrides
    state = message(extraction_api, "Стол от пола до верха 75 см")
    assert not any(f["status"] == "accepted_from_model" for f in state["facts"])
    assert state["candidate_counts"]["compatible"] == 2


@pytest.mark.parametrize("text", ["Стол", "Стол высота 75 см"])
def test_no_model_call_without_significant_remainder(
    extraction_api: TestClient, extractor: Extractor, text: str
) -> None:
    message(extraction_api, text)
    assert extractor.requests == []


@pytest.mark.parametrize("score", [0.899, 0.0])
def test_low_support_is_only_a_proposal(
    extraction_api: TestClient, verifier: Verifier, score: float
) -> None:
    verifier.score = score
    state = message(extraction_api, "Стол от пола до верха 75 см")
    assert any(f["status"] == "proposed" for f in state["facts"])
    assert state["candidate_counts"]["compatible"] == 2


def test_verifier_failure_preserves_proposal_and_draft(
    extraction_api: TestClient, verifier: Verifier
) -> None:
    verifier.time_out()
    state = message(extraction_api, "Стол от пола до верха 75 см")
    assert any(f["status"] == "proposed" for f in state["facts"])
    assert state["messages"][-1]["text"] == "Стол от пола до верха 75 см"
    assert state["candidate_counts"]["compatible"] == 2


def test_json_and_semantic_retry_have_separate_finite_budgets(
    extraction_api: TestClient, extractor: Extractor, verifier: Verifier
) -> None:
    extractor.outcomes = ["json", "ok", "ok"]
    verifier.score, verifier.contradicted = 0.01, True
    state = message(extraction_api, "Стол от пола до верха 75 см")
    assert len(extractor.requests) == 3
    assert len(verifier.contexts) == 2
    assert not any(f["status"] == "accepted_from_model" for f in state["facts"])
    assert state["candidate_counts"]["compatible"] == 2


def test_verification_evidence_survives_reload(extraction_api: TestClient) -> None:
    state = message(extraction_api, "Стол от пола до верха 75 см")
    loaded = extraction_api.get(f"/api/v1/sessions/{state['session_id']}").json()
    fact = next(f for f in loaded["facts"] if f["normalization_rule"] == "verified_extraction_v1")
    evidence = fact["verification"]
    assert evidence["session_revision"] == state["revision"]
    assert evidence["model_revision"] == REVISION
    assert evidence["verdict"] == "supported"
    assert evidence["message_ids"] == [state["messages"][0]["id"]]
    assert len(evidence["context_hash"]) == 64


def test_manual_edit_and_deleted_fact_survive_later_analysis(
    extraction_api: TestClient, extractor: Extractor
) -> None:
    state = message(extraction_api, "Стол от пола до верха 75 см")
    sid = state["session_id"]
    fact = next(f for f in state["facts"] if f["normalization_rule"] == "verified_extraction_v1")
    response = extraction_api.patch(
        f"/api/v1/sessions/{sid}/facts/{fact['id']}",
        json={"expected_revision": state["revision"], "action": "delete"},
    )
    assert response.status_code == 200, response.text
    extractor.overrides = {"source_message_id": state["messages"][0]["id"], "source_quote": "75 см"}
    later = extraction_api.post(
        f"/api/v1/sessions/{sid}/messages", json={"text": "Стол нужен завтра"}
    ).json()
    assert not any(f["status"] == "accepted_from_model" for f in later["facts"])
    assert later["candidate_counts"]["compatible"] == 2


def test_negated_proposal_cannot_be_confirmed_as_positive(
    extraction_api: TestClient, extractor: Extractor
) -> None:
    extractor.overrides = {"negated": True}
    state = message(extraction_api, "Стол от пола до верха не 75 см")
    fact = next(f for f in state["facts"] if f["normalization_rule"] == "verified_extraction_v1")
    response = extraction_api.patch(
        f"/api/v1/sessions/{state['session_id']}/facts/{fact['id']}",
        json={"expected_revision": state["revision"], "action": "confirm"},
    )
    assert response.status_code == 422


@pytest.mark.parametrize(
    "extraction_api",
    [VerificationPolicy(enabled=False), VerificationPolicy(revision="other")],
    indirect=True,
)
def test_disabled_or_unpinned_verifier_only_proposes(extraction_api: TestClient) -> None:
    state = message(extraction_api, "Стол от пола до верха 75 см")
    assert any(f["status"] == "proposed" for f in state["facts"])
    assert state["candidate_counts"]["compatible"] == 2


def test_two_invalid_json_responses_leave_manual_entry_available(
    extraction_api: TestClient, extractor: Extractor
) -> None:
    extractor.outcomes = ["json", "json", "ok"]
    state = message(extraction_api, "Стол от пола до верха 75 см")
    assert len(extractor.requests) == 2
    assert state["warnings"]
    response = extraction_api.post(
        f"/api/v1/sessions/{state['session_id']}/facts",
        json={
            "expected_revision": state["revision"],
            "action": "edit",
            "characteristic_name": "Высота",
            "raw_value": "75",
            "raw_unit": "см",
            "kind": "number",
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["candidate_counts"]["compatible"] == 1


def test_multiple_messages_can_auto_accept_current_source(extraction_api: TestClient) -> None:
    state = message(extraction_api, "Стол")
    response = extraction_api.post(
        f"/api/v1/sessions/{state['session_id']}/messages", json={"text": "От пола до верха 75 см"}
    )
    assert response.status_code == 200
    assert any(f["status"] == "accepted_from_model" for f in response.json()["facts"])


def test_positive_extract_cannot_lose_negation(extraction_api: TestClient) -> None:
    state = message(extraction_api, "Стол от пола до верха не 75 см")
    assert not any(f["status"] == "accepted_from_model" for f in state["facts"])


def test_value_must_be_whole_number_in_source(extraction_api: TestClient) -> None:
    state = message(extraction_api, "Стол от пола до верха 175 см")
    assert not any(f["status"] == "accepted_from_model" for f in state["facts"])


def test_short_quote_cannot_hide_negation(extraction_api: TestClient, extractor: Extractor) -> None:
    extractor.overrides = {"source_quote": "75 см"}
    state = message(extraction_api, "Стол от пола до верха не 75 см")
    assert not any(f["status"] == "accepted_from_model" for f in state["facts"])


def test_nearby_product_does_not_supply_target_property(
    extraction_api: TestClient, extractor: Extractor
) -> None:
    extractor.overrides = {"source_quote": "75 см"}
    state = message(extraction_api, "Стол стоит рядом со шкафом: от пола до верха 75 см")
    assert not any(f["status"] == "accepted_from_model" for f in state["facts"])


@pytest.mark.parametrize("qualitative", [True], indirect=True)
def test_free_text_does_not_gain_invented_dimension(
    extraction_api: TestClient, extractor: Extractor
) -> None:
    extractor.overrides = {"attribute_ref": "Цвет", "raw_value": "оранжевый", "raw_unit": "см"}
    state = message(extraction_api, "Стол окрашен в оранжевый цвет")
    assert not any(f["status"] == "accepted_from_model" for f in state["facts"])


def test_explicit_long_correction_uses_common_history(
    extraction_api: TestClient, extractor: Extractor
) -> None:
    state = message(extraction_api, "Стол от пола до верха 75 см")
    fact = next(f for f in state["facts"] if f["normalization_rule"] == "verified_extraction_v1")
    url = f"/api/v1/sessions/{state['session_id']}"
    confirmed = extraction_api.patch(
        f"{url}/facts/{fact['id']}",
        json={"expected_revision": state["revision"], "action": "confirm"},
    )
    assert confirmed.status_code == 200
    extractor.overrides = {"raw_value": "90"}
    corrected = extraction_api.post(
        f"{url}/messages", json={"text": "исправь расстояние от пола до верха на 90 см"}
    ).json()
    assert any(
        f["raw_value"] == "90" and f["status"] == "accepted_from_model" for f in corrected["facts"]
    )
    assert not any(
        f["raw_value"] == "75" and f["status"] in {"accepted_from_model", "confirmed_by_user"}
        for f in corrected["facts"]
    )
    assert corrected["fact_history"][-1]["action"] == "text_correction"


@pytest.mark.parametrize("qualitative", ["Материал столешницы"], indirect=True)
def test_short_quote_cannot_transfer_property_between_parts(
    extraction_api: TestClient, extractor: Extractor
) -> None:
    extractor.overrides = {
        "attribute_ref": "Материал столешницы",
        "raw_value": "металла",
        "raw_unit": None,
        "source_quote": "металла",
        "subject_ref": "столешница",
    }
    state = message(extraction_api, "Стол: ножки из металла, столешница из дерева")
    assert not any(f["status"] == "accepted_from_model" for f in state["facts"])


def test_product_subject_uses_whole_product_binding(
    extraction_api: TestClient, extractor: Extractor
) -> None:
    extractor.overrides = {"subject_ref": "product"}
    state = message(extraction_api, "Стол от пола до верха 75 см")
    fact = next(f for f in state["facts"] if f["normalization_rule"] == "verified_extraction_v1")
    assert fact["component"] is None
    assert fact["status"] == "accepted_from_model"


@pytest.mark.parametrize("qualitative", [True], indirect=True)
def test_free_proposal_uses_revisioned_editor_and_preserves_confirmation(
    extraction_api: TestClient, extractor: Extractor, verifier: Verifier
) -> None:
    extractor.overrides = {"attribute_ref": "Цвет", "raw_value": "оранжевый", "raw_unit": None}
    verifier.score = 0.89
    state = message(extraction_api, "Стол окрашен в оранжевый цвет")
    fact = next(f for f in state["facts"] if f["normalization_rule"] == "verified_extraction_v1")
    assert fact["status"] == "proposed"
    url = f"/api/v1/sessions/{state['session_id']}"
    mutation = {
        "expected_revision": state["revision"],
        "action": "edit",
        "characteristic_name": "Цвет",
        "raw_value": "бирюзовый",
        "kind": "text",
    }
    edited = extraction_api.patch(f"{url}/facts/{fact['id']}", json=mutation)
    assert edited.status_code == 200, edited.text
    assert edited.json()["fact_history"][-1]["after"][0]["raw_value"] == "бирюзовый"
    assert extraction_api.patch(f"{url}/facts/{fact['id']}", json=mutation).status_code == 409
    later = extraction_api.post(
        f"{url}/messages", json={"text": "Упаковка оранжевого цвета"}
    ).json()
    assert any(
        f["raw_value"] == "бирюзовый" and f["status"] == "confirmed_by_user" for f in later["facts"]
    )


def test_empty_extraction_is_a_valid_result(
    extraction_api: TestClient, extractor: Extractor, verifier: Verifier
) -> None:
    extractor.outcomes = ["empty"]
    state = message(extraction_api, "Стол от пола до верха 75 см")
    assert state["candidate_counts"]["compatible"] == 2
    assert not any(f["normalization_rule"] == "verified_extraction_v1" for f in state["facts"])
    assert verifier.contexts == []
