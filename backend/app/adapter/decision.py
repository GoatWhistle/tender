"""HTTP-сервис OpenJev (`services/openjev`) — реализация порта `DecisionBackend`.

Вопрос — `POST /v1/choice`, по запросу на вопрос: сервис сам переиспользует подготовленное
описание при том же `premise`. Утверждения — один `POST /v1/nli` на пакет.
"""

from collections.abc import Sequence
from typing import Any

import httpx

from app.domain.inference import (
    ChoiceAnswer,
    ChoiceBatch,
    ChoiceQuestion,
    Claim,
    ClaimAnswer,
    ClaimBatch,
    ModelHealth,
    Verdict,
)

OPENJEV_MODEL = "openjev"


class OpenJevDecision:
    def __init__(
        self,
        url: str,
        *,
        timeout: float = 60,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._url = url.rstrip("/")
        self._timeout = timeout
        self._transport = transport

    def choose(self, context: str, questions: Sequence[ChoiceQuestion]) -> ChoiceBatch:
        answers: list[ChoiceAnswer] = []
        revision = ""
        for question in questions:
            reply = self._post(
                "/v1/choice",
                {
                    "premise": context,
                    "instructions": question.text,
                    "options": [{"id": o.option_id, "criterion": o.text} for o in question.options],
                },
            )
            revision = reply["model_revision"]
            answers.append(
                ChoiceAnswer(
                    question.question_id,
                    {k: float(v) for k, v in reply["probabilities"].items()},
                    reply["choice"],
                )
            )
        return ChoiceBatch(tuple(answers), revision)

    def verify(self, context: str, claims: Sequence[Claim]) -> ClaimBatch:
        reply = self._post("/v1/nli", {"premise": context, "hypotheses": [c.text for c in claims]})
        answers = tuple(
            ClaimAnswer(
                claim.claim_id,
                {Verdict(k): float(v) for k, v in row["probabilities"].items()},
            )
            for claim, row in zip(claims, reply["results"], strict=True)
        )
        return ClaimBatch(answers, reply["model_revision"])

    def health(self) -> ModelHealth:
        with self._client() as client:
            response = client.get(f"{self._url}/health/ready")
        if response.status_code == 503:
            return ModelHealth(OPENJEV_MODEL, "", False)
        response.raise_for_status()
        body = response.json()
        return ModelHealth(OPENJEV_MODEL, body["model_revision"], body["status"] == "ready")

    def _post(self, path: str, body: dict[str, Any]) -> Any:
        with self._client() as client:
            response = client.post(f"{self._url}{path}", json=body)
        response.raise_for_status()
        return response.json()

    def _client(self) -> httpx.Client:
        return httpx.Client(timeout=self._timeout, transport=self._transport, trust_env=False)
