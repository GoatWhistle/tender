from collections.abc import Sequence
from dataclasses import replace

import pytest

from app.adapter.facts import DeterministicFactExtractor
from app.adapter.ktru_xml import XmlKtruSource
from app.adapter.stub import StubDecisionBackend
from app.domain.inference import (
    ChoiceAnswer,
    ChoiceBatch,
    ChoiceQuestion,
)
from app.domain.search import MethodContribution, SearchResult
from app.domain.sessions import SessionStatus
from app.repository.memory.catalog import MemoryCatalog
from app.repository.memory.sessions import MemorySessions
from app.repository.memory.unit_of_work import MemoryStore, MemoryUnitOfWork
from app.usecase.sessions import OUT_OF_SCOPE, Sessions
from composition import Repositories, build_usecases
from settings import Settings
from tests.conftest import CABINET_CODE, TABLE_CODE
from tests.group_decision import ConfirmedGroup
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
        decision=decision,
        min_similarity=0.45,
    )
    usecases.catalog_sync(uow).run()
    assert usecases.sessions is not None
    return usecases.sessions(uow)


class CountingDecision(StubDecisionBackend):
    calls = 0

    def choose(self, context: str, questions: Sequence[ChoiceQuestion]) -> ChoiceBatch:
        self.calls += any(q.question_id == "relevance" for q in questions)
        if all(q.question_id.startswith("group:") for q in questions):
            return ConfirmedGroup(TABLE_CODE if "\n" in context else CABINET_CODE).choose(
                context, questions
            )
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
