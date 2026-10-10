"""Явно подтверждённое назначение для тестов последующего сужения/редактирования."""

from collections.abc import Callable, Sequence

from app.adapter.stub import StubDecisionBackend
from app.domain.inference import ChoiceAnswer, ChoiceBatch, ChoiceQuestion


class ConfirmedGroup(StubDecisionBackend):
    def __init__(self, code: str | Callable[[str], str]) -> None:
        super().__init__()
        self.code = code

    def choose(self, context: str, questions: Sequence[ChoiceQuestion]) -> ChoiceBatch:
        code = self.code(context) if callable(self.code) else self.code
        answers = []
        for q in questions:
            if q.question_id == "relevance":
                answers.append(
                    ChoiceAnswer(q.question_id, {"product": 1.0, "junk": 0.0}, "product")
                )
            else:
                verdict = "supported" if q.question_id == f"group:{code}" else "contradicted"
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
        return ChoiceBatch(tuple(answers), "fixture")
