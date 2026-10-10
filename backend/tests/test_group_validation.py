"""HTTP-регрессии выбора назначения; ответы внешней decision-модели детерминированы."""

from collections.abc import Sequence

import pytest
from fastapi.testclient import TestClient

from app.adapter.facts import DeterministicFactExtractor
from app.adapter.stub import StubDecisionBackend
from app.domain.catalog import Position
from app.domain.inference import ChoiceAnswer, ChoiceBatch, ChoiceQuestion
from app.domain.search import MethodContribution, SearchHit, SearchResult
from composition import build_usecases
from main import create_app, sql_repositories, sync_catalog
from settings import Settings
from tests.group_decision import ConfirmedGroup


class Tables:
    def load(self) -> list[Position]:
        return [
            Position(code, name, "Мебель", "31.01", "Мебель", False, None, (), ())
            for code, name in [
                ("production", "Стол производственный"),
                ("desk", "Стол письменный"),
                ("computer", "Стол компьютерный"),
            ]
        ]


class Search:
    def run(self, description: str, category: str | None = None, limit: int = 10) -> SearchResult:
        return SearchResult(
            description,
            tuple(
                SearchHit(
                    p,
                    MethodContribution.of(i),
                    MethodContribution.of(i),
                    MethodContribution.of(None),
                )
                for i, p in enumerate(Tables().load()[:limit], 1)
            ),
        )


class Decision(StubDecisionBackend):
    def choose(self, context: str, questions: Sequence[ChoiceQuestion]) -> ChoiceBatch:
        answers = []
        for q in questions:
            if q.question_id == "relevance":
                answers.append(
                    ChoiceAnswer(q.question_id, {"product": 1.0, "junk": 0.0}, "product")
                )
            else:
                verdict = "contradicted" if q.question_id == "group:production" else "not_stated"
                if "Исправление назначения" in context:
                    verdict = "supported" if q.question_id == "group:production" else "contradicted"
                elif "Уточнение назначения пользователем: Стол письменный" in context:
                    verdict = "supported" if q.question_id == "group:desk" else "contradicted"
                answers.append(
                    ChoiceAnswer(
                        q.question_id,
                        {
                            v: float(v == verdict)
                            for v in ("supported", "contradicted", "not_stated")
                        },
                        verdict,
                        support_scores={
                            v: float(v == verdict)
                            for v in ("supported", "contradicted", "not_stated")
                        },
                    )
                )
        return ChoiceBatch(tuple(answers), "test")


def test_programmers_table_does_not_select_rag_top_one(settings: Settings) -> None:
    source = Tables()
    sync_catalog(settings, source)
    app = create_app(settings, source)
    app.state.usecases = build_usecases(
        sql_repositories(),
        catalog_source=source,
        searcher=Search(),
        fact_extractor=DeterministicFactExtractor(),
        decision=Decision(),
    )
    with TestClient(app) as client:
        sid = client.post("/api/v1/sessions").json()["session_id"]
        state = client.post(
            f"/api/v1/sessions/{sid}/messages", json={"text": "рабочий стол программистам"}
        ).json()
        assert state["status"] == "needs_clarification"
        assert state["path"] is None
        assert state["candidates"] == []
        assert state["next_question"]["kind"] == "purpose"
        assert [o["label"] for o in state["next_question"]["options"]] == [
            "Стол письменный",
            "Стол компьютерный",
            "Другое",
        ]
        assert len(state["group_checks"]) == 3
        assert client.get(f"/api/v1/sessions/{sid}").json() == state


def test_purpose_answer_rechecks_before_selection(settings: Settings) -> None:
    source = Tables()
    decision = Decision()
    sync_catalog(settings, source)
    app = create_app(settings, source)
    app.state.usecases = build_usecases(
        sql_repositories(),
        catalog_source=source,
        searcher=Search(),
        fact_extractor=DeterministicFactExtractor(),
        decision=decision,
    )
    with TestClient(app) as client:
        sid = client.post("/api/v1/sessions").json()["session_id"]
        base = f"/api/v1/sessions/{sid}"
        state = client.post(base + "/messages", json={"text": "рабочий стол программистам"}).json()
        question = state["next_question"]
        state = client.post(
            base + "/answers",
            json={
                "question_id": question["question_id"],
                "option_id": "desk",
            },
        ).json()
        assert state["path"]["group"]["code"] == "desk"
        assert state["status"] == "resolved"
        assert state["analysis_revision"] == state["revision"] == 2
        assert (
            client.post(
                base + "/answers",
                json={
                    "question_id": question["question_id"],
                    "option_id": "desk",
                },
            ).status_code
            == 409
        )
        state = client.post(
            base + "/messages",
            json={"text": "Исправление назначения: нужен производственный стол для кухни"},
        ).json()
        assert state["path"]["group"]["code"] == "production"
        assert state["analysis_revision"] == 3


@pytest.mark.parametrize("k", [5, 10])
def test_every_distinct_top_k_group_is_checked(settings: Settings, k: int) -> None:
    class Many(Tables):
        def load(self) -> list[Position]:
            return [
                Position(str(i), f"Группа {i}", "Мебель", "", "", False, None, (), ())
                for i in range(12)
            ]

    class Retrieval(Search):
        def run(
            self, description: str, category: str | None = None, limit: int = 10
        ) -> SearchResult:
            assert limit == k
            return SearchResult(
                description,
                tuple(
                    SearchHit(
                        p,
                        MethodContribution.of(i),
                        MethodContribution.of(i),
                        MethodContribution.of(None),
                    )
                    for i, p in enumerate(Many().load()[:limit], 1)
                ),
            )

    source = Many()
    sync_catalog(settings, source)
    app = create_app(settings, source)
    app.state.usecases = build_usecases(
        sql_repositories(),
        catalog_source=source,
        searcher=Retrieval(),
        fact_extractor=DeterministicFactExtractor(),
        decision=ConfirmedGroup(str(k - 1)),
        group_top_k=k,
    )
    with TestClient(app) as client:
        sid = client.post("/api/v1/sessions").json()["session_id"]
        state = client.post(f"/api/v1/sessions/{sid}/messages", json={"text": "стол"}).json()
        assert len(state["group_checks"]) == k
        assert len({c["code"] for c in state["group_checks"]}) == k
        assert state["path"]["group"]["code"] == str(k - 1)
        assert len(state["alternatives"]) == min(5, k - 1)


@pytest.mark.parametrize(
    "mode", ["unknown", "rejected", "relative_only", "partial", "invalid_id", "failure", "missing"]
)
def test_unconfirmed_candidates_never_resolve_and_error_can_retry(
    settings: Settings, mode: str
) -> None:
    class One(Tables):
        def load(self) -> list[Position]:
            return Tables().load()[:1]

    class Retrieval(Search):
        def run(
            self, description: str, category: str | None = None, limit: int = 10
        ) -> SearchResult:
            result = super().run(description, category, limit)
            from dataclasses import replace

            return replace(result, groups=result.groups[:1])

    class GroupReply(StubDecisionBackend):
        def choose(self, context: str, questions: Sequence[ChoiceQuestion]) -> ChoiceBatch:
            if questions[0].question_id == "relevance":
                return ChoiceBatch(
                    (ChoiceAnswer("relevance", {"product": 1.0, "junk": 0.0}, "product"),), "test"
                )
            return super().choose(context, questions)

    decision = GroupReply()
    decision.choices["relevance"] = ChoiceAnswer(
        "relevance", {"product": 1.0, "junk": 0.0}, "product"
    )
    verdict = "contradicted" if mode == "rejected" else "not_stated"
    decision.choices["group:production"] = ChoiceAnswer(
        "group:production",
        {v: float(v == verdict) for v in ("supported", "contradicted", "not_stated")},
        verdict,
        support_scores={
            v: float(v == verdict) for v in ("supported", "contradicted", "not_stated")
        },
    )
    if mode == "relative_only":
        decision.choices["group:production"] = ChoiceAnswer(
            "group:production",
            {"supported": 1.0, "contradicted": 0.0, "not_stated": 0.0},
            "supported",
            support_scores={"supported": 0.001, "contradicted": 0.0, "not_stated": 0.0},
        )
    if mode == "partial":
        decision.choice_reply = ChoiceBatch((), "test")
    if mode == "invalid_id":
        decision.choice_reply = ChoiceBatch(
            (ChoiceAnswer("foreign", {"product": 1.0, "junk": 0.0}, "product"),), "test"
        )
    if mode == "failure":
        decision.fail()
    source = One()
    sync_catalog(settings, source)
    app = create_app(settings, source)

    def wire(model: StubDecisionBackend | None) -> None:
        app.state.usecases = build_usecases(
            sql_repositories(),
            catalog_source=source,
            searcher=Retrieval(),
            fact_extractor=DeterministicFactExtractor(),
            decision=model,
        )

    wire(None if mode == "missing" else decision)
    with TestClient(app) as client:
        sid = client.post("/api/v1/sessions").json()["session_id"]
        base = f"/api/v1/sessions/{sid}"
        state = client.post(base + "/messages", json={"text": "стол"}).json()
        assert state["path"] is None
        assert state["card_complete"] is False
        if mode in ("unknown", "rejected", "relative_only"):
            assert state["status"] == "needs_clarification"
            assert state["next_question"]["kind"] == "purpose"
        else:
            assert state["status"] == "technical_error"
            assert state["errors"]
            wire(ConfirmedGroup("production"))
            state = client.post(base + "/recalculate", json={"expected_revision": 1}).json()
            assert state["status"] == "resolved"
            assert state["analysis_revision"] == 2
            assert state["results_stale"] is False
            assert state["errors"] == []


@pytest.mark.parametrize("answer", [None, "other"])
def test_unknown_purpose_never_forces_group_and_waits_for_message(
    settings: Settings, answer: str | None
) -> None:
    source = Tables()
    sync_catalog(settings, source)
    app = create_app(settings, source)
    app.state.usecases = build_usecases(
        sql_repositories(),
        catalog_source=source,
        searcher=Search(),
        fact_extractor=DeterministicFactExtractor(),
        decision=Decision(),
    )
    with TestClient(app) as client:
        sid = client.post("/api/v1/sessions").json()["session_id"]
        base = f"/api/v1/sessions/{sid}"
        state = client.post(base + "/messages", json={"text": "стол программистам"}).json()
        body = {
            "question_id": state["next_question"]["question_id"],
            **({"unknown": True} if answer is None else {"option_id": answer}),
        }
        state = client.post(base + "/answers", json=body).json()
        assert state["status"] == "needs_clarification"
        assert state["path"] is None and state["next_question"] is None
        assert client.get(base).json() == state


@pytest.mark.parametrize("empty", [True, False])
def test_empty_search_clarifies_and_duplicate_children_are_not_groups(
    settings: Settings, empty: bool
) -> None:
    from dataclasses import replace

    class Source(Tables):
        def load(self) -> list[Position]:
            root = replace(Tables().load()[0], is_template=True)
            return [root, replace(root, code="child", is_template=False, parent=root.code)]

    class Retrieval(Search):
        def run(
            self, description: str, category: str | None = None, limit: int = 10
        ) -> SearchResult:
            return SearchResult(
                description,
                ()
                if empty
                else tuple(
                    SearchHit(
                        p,
                        MethodContribution.of(1),
                        MethodContribution.of(None),
                        MethodContribution.of(None),
                    )
                    for p in [*Source().load(), Source().load()[0]]
                ),
            )

    source = Source()
    sync_catalog(settings, source)
    app = create_app(settings, source)
    app.state.usecases = build_usecases(
        sql_repositories(),
        catalog_source=source,
        searcher=Retrieval(),
        fact_extractor=DeterministicFactExtractor(),
        decision=ConfirmedGroup("production"),
    )
    with TestClient(app) as client:
        sid = client.post("/api/v1/sessions").json()["session_id"]
        state = client.post(
            f"/api/v1/sessions/{sid}/messages", json={"text": "производственный стол"}
        ).json()
        if empty:
            assert state["status"] == "needs_clarification"
            assert state["next_question"]["kind"] == "purpose"
            assert state["path"] is None
        else:
            assert [c["code"] for c in state["group_checks"]] == ["production"]
            assert state["path"]["group"] == {
                "code": "production",
                "name": "Стол производственный",
                "role": "group_template",
            }
            assert state["candidates"][0]["code"] == "child"
            assert state["candidates"][0]["role"] == "ktru_position"


def test_explicit_purpose_resolves_ambiguity_only_when_model_supports_it(
    settings: Settings,
) -> None:
    class Several(ConfirmedGroup):
        def choose(self, context: str, questions: Sequence[ChoiceQuestion]) -> ChoiceBatch:
            from dataclasses import replace

            batch = super().choose(context, questions)
            return replace(
                batch,
                answers=tuple(
                    replace(
                        a,
                        selected="not_stated",
                        probabilities={"supported": 0.0, "contradicted": 0.0, "not_stated": 1.0},
                        support_scores={"supported": 0.0, "contradicted": 0.0, "not_stated": 1.0},
                    )
                    if a.question_id == "group:computer"
                    else a
                    for a in batch.answers
                ),
            )

    source = Tables()
    sync_catalog(settings, source)
    app = create_app(settings, source)
    app.state.usecases = build_usecases(
        sql_repositories(),
        catalog_source=source,
        searcher=Search(),
        fact_extractor=DeterministicFactExtractor(),
        decision=Several("desk"),
    )
    with TestClient(app) as client:
        sid = client.post("/api/v1/sessions").json()["session_id"]
        base = f"/api/v1/sessions/{sid}"
        state = client.post(base + "/messages", json={"text": "стол для работы"}).json()
        assert state["path"] is None
        state = client.post(
            base + "/answers",
            json={"question_id": state["next_question"]["question_id"], "option_id": "desk"},
        ).json()
        assert state["path"]["group"]["code"] == "desk"
