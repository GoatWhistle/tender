"""Decision-модель без модели — реализация порта `DecisionBackend`.

Ответ по ID — из `choices` / `claims`, целиком заданный пакет — из `choice_reply` /
`claim_reply`. Незаданный вопрос получает равномерное распределение и отказ, незаданное
утверждение — `not_stated`: заглушка ничего не знает о контексте.
"""

from collections.abc import Sequence

from app.adapter.stub.fault import Scripted
from app.domain.inference import (
    ChoiceAnswer,
    ChoiceBatch,
    ChoiceQuestion,
    Claim,
    ClaimAnswer,
    ClaimBatch,
    Verdict,
)


class StubDecisionBackend(Scripted):
    model = "stub-decision"

    def __init__(self, revision: str = "stub-1") -> None:
        super().__init__(revision)
        self.choices: dict[str, ChoiceAnswer] = {}
        self.claims: dict[str, ClaimAnswer] = {}
        self.choice_reply: ChoiceBatch | None = None
        self.claim_reply: ClaimBatch | None = None

    def choose(self, context: str, questions: Sequence[ChoiceQuestion]) -> ChoiceBatch:
        self._raise_fault()
        if self.choice_reply is not None:
            return self.choice_reply
        answers = tuple(self.choices.get(q.question_id) or _abstain(q) for q in questions)
        return ChoiceBatch(answers=answers, revision=self.revision)

    def verify(self, context: str, claims: Sequence[Claim]) -> ClaimBatch:
        self._raise_fault()
        if self.claim_reply is not None:
            return self.claim_reply
        answers = tuple(self.claims.get(c.claim_id) or _not_stated(c) for c in claims)
        return ClaimBatch(answers=answers, revision=self.revision)


def _abstain(question: ChoiceQuestion) -> ChoiceAnswer:
    share = 1 / len(question.options) if question.options else 0.0
    probabilities = dict.fromkeys(question.option_ids, share)
    return ChoiceAnswer(question.question_id, probabilities, selected=None)


def _not_stated(claim: Claim) -> ClaimAnswer:
    probabilities = {v: 1.0 if v is Verdict.not_stated else 0.0 for v in Verdict}
    return ClaimAnswer(claim.claim_id, probabilities)
