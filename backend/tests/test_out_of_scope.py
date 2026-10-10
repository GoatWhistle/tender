import json
from collections.abc import Sequence
from dataclasses import replace
from typing import Any

import httpx
import pytest

from app.adapter.decision import OpenJevDecision
from app.adapter.facts import DeterministicFactExtractor
from app.adapter.ktru_xml import XmlKtruSource
from app.adapter.stub import StubDecisionBackend
from app.domain.inference import (
    ChoiceAnswer,
    ChoiceBatch,
    ChoiceOption,
    ChoiceQuestion,
    Claim,
    Verdict,
)
from app.domain.search import MethodContribution, SearchResult
from app.domain.sessions import SessionStatus
from app.repository.memory.catalog import MemoryCatalog
from app.repository.memory.sessions import MemorySessions
from app.repository.memory.unit_of_work import MemoryStore, MemoryUnitOfWork
from app.usecase.sessions import OUT_OF_SCOPE, Sessions
from composition import Repositories, build_usecases, checked_decision
from settings import Settings
from tests.test_sessions import SearchStub


class SimilarSearch(SearchStub):
    """Поиск с заданным косинусом ближайшей группы и, по желанию, находкой по синониму."""

    def __init__(self, settings: Settings, similarity: float, *, synonym: bool = False) -> None:
        super().__init__(settings)
        self.similarity = similarity
        self.synonym = synonym

    def run(self, description: str, category: str | None = None, limit: int = 10) -> SearchResult:
        result = super().run(description, category, limit)
        top, *rest = result.groups
        if self.synonym:
            top = replace(top, synonym=MethodContribution.of(1))
        return replace(result, groups=(top, *rest), similarity=self.similarity)


def scenario(
    settings: Settings, search: SearchStub, decision: StubDecisionBackend | None = None
) -> Sessions:
    uow = MemoryUnitOfWork(MemoryStore())
    usecases = build_usecases(
        Repositories[MemoryUnitOfWork](
            catalog=lambda u: MemoryCatalog(u.store), sessions=lambda u: MemorySessions(u.store)
        ),
        catalog_source=XmlKtruSource(settings.ktru_xml_dir),
        searcher=search,
        fact_extractor=DeterministicFactExtractor(),
        decision=checked_decision(decision) if decision is not None else None,
        min_similarity=0.45,
    )
    usecases.catalog_sync(uow).run()
    assert usecases.sessions is not None
    return usecases.sessions(uow)


class CountingDecision(StubDecisionBackend):
    calls = 0

    def choose(self, context: str, questions: Sequence[ChoiceQuestion]) -> ChoiceBatch:
        self.calls += 1
        return super().choose(context, questions)


def junk(probability: float) -> CountingDecision:
    decision = CountingDecision()
    decision.choices["relevance"] = ChoiceAnswer(
        "relevance",
        {"product": 1 - probability, "junk": probability},
        "junk" if probability >= 0.5 else "product",
    )
    return decision


def test_below_threshold_is_out_of_scope_without_decision(settings: Settings) -> None:
    decision = junk(0.0)
    sessions = scenario(settings, SimilarSearch(settings, 0.44), decision)
    state = sessions.message(sessions.create().session_id, "lkjfsjklsafljkjlksa")
    assert state.status == SessionStatus.OUT_OF_SCOPE
    assert state.path is None and state.candidates == () and state.alternatives == ()
    assert state.warnings == ("Предупреждение поиска", OUT_OF_SCOPE)
    assert decision.calls == 0


@pytest.mark.parametrize(("probability", "status"), [(0.9, "out_of_scope"), (0.2, "resolved")])
def test_decision_judges_text_above_threshold(
    settings: Settings, probability: float, status: str
) -> None:
    decision = junk(probability)
    sessions = scenario(settings, SimilarSearch(settings, 0.6), decision)
    sid = sessions.create().session_id
    sessions.message(sid, "шкаф")
    state = sessions.message(sid, "точнее стол")
    assert state.status == status
    assert decision.calls == 2


def test_synonym_hit_skips_both_checks(settings: Settings) -> None:
    decision = junk(1.0)
    sessions = scenario(settings, SimilarSearch(settings, 0.1, synonym=True), decision)
    state = sessions.message(sessions.create().session_id, "шкаф")
    assert state.status == SessionStatus.AMBIGUOUS_IN_CATALOG
    assert decision.calls == 0


def test_decision_failure_is_technical_error(settings: Settings) -> None:
    decision = junk(0.0)
    decision.fail()
    sessions = scenario(settings, SimilarSearch(settings, 0.6), decision)
    state = sessions.message(sessions.create().session_id, "шкаф")
    assert state.status == SessionStatus.TECHNICAL_ERROR


def test_openjev_adapter_maps_choice_and_nli() -> None:
    requests: list[tuple[str, dict[str, Any]]] = []

    def respond(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        requests.append((request.url.path, body))
        if request.url.path == "/v1/choice":
            return httpx.Response(
                200,
                json={"choice": "b", "probabilities": {"a": 0.3, "b": 0.7}, "model_revision": "r"},
            )
        return httpx.Response(
            200,
            json={
                "results": [
                    {"probabilities": {"supported": 0.8, "contradicted": 0.1, "not_stated": 0.1}}
                ],
                "model_revision": "r",
            },
        )

    adapter = checked_decision(
        OpenJevDecision("http://jev/", transport=httpx.MockTransport(respond))
    )
    question = ChoiceQuestion(
        "q", "Что это?", (ChoiceOption("a", "Стол"), ChoiceOption("b", "Шкаф"))
    )
    (answer,) = adapter.choose("шкаф", [question]).answers
    assert answer.selected == "b" and answer.probabilities == {"a": 0.3, "b": 0.7}
    (claim,) = adapter.verify("шкаф", [Claim("c", "Это шкаф.")]).answers
    assert claim.probabilities[Verdict.supported] == 0.8
    assert requests[0] == (
        "/v1/choice",
        {
            "premise": "шкаф",
            "instructions": "Что это?",
            "options": [{"id": "a", "criterion": "Стол"}, {"id": "b", "criterion": "Шкаф"}],
        },
    )
    assert requests[1] == ("/v1/nli", {"premise": "шкаф", "hypotheses": ["Это шкаф."]})
