"""DecisionBackend поверх API services/openjev; общая валидация — в composition.

У сервиса один choice на HTTP-запрос, NLI — пакет до 32 утверждений. Адаптер сохраняет
пакетный контракт порта и проверяет ревизию/порядок всех частей до возврата результата.
"""

from collections.abc import Sequence
from typing import Any

import httpx

from app.domain.errors import ModelFailure
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


class OpenJevDecision:
    def __init__(
        self,
        base_url: str,
        *,
        timeout: float = 120,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._url = base_url.rstrip("/")
        self._timeout = timeout
        self._transport = transport

    def _client(self) -> httpx.Client:
        return httpx.Client(base_url=self._url, timeout=self._timeout, transport=self._transport)

    def choose(self, context: str, questions: Sequence[ChoiceQuestion]) -> ChoiceBatch:
        answers = []
        revisions: set[str] = set()
        with self._client() as client:
            for question in questions:
                response = client.post(
                    "/v1/choice",
                    json={
                        "premise": context,
                        "instructions": question.text,
                        "options": [
                            {"id": o.option_id, "criterion": o.text} for o in question.options
                        ],
                    },
                )
                response.raise_for_status()
                data = response.json()
                revisions.add(_revision(data))
                answers.append(
                    ChoiceAnswer(
                        question.question_id,
                        data["probabilities"],
                        data["choice"],
                        support_scores=data.get("support_probabilities"),
                    )
                )
        return ChoiceBatch(tuple(answers), _single_revision(revisions))

    def verify(self, context: str, claims: Sequence[Claim]) -> ClaimBatch:
        answers = []
        revisions: set[str] = set()
        with self._client() as client:
            for start in range(0, len(claims), 32):
                chunk = claims[start : start + 32]
                response = client.post(
                    "/v1/nli", json={"premise": context, "hypotheses": [c.text for c in chunk]}
                )
                response.raise_for_status()
                data = response.json()
                revisions.add(_revision(data))
                results = data["results"]
                if [r["hypothesis"] for r in results] != [c.text for c in chunk]:
                    raise ModelFailure("OpenJev вернул другой состав утверждений")
                for claim, result in zip(chunk, results, strict=True):
                    answers.append(
                        ClaimAnswer(
                            claim.claim_id,
                            {Verdict(k): v for k, v in result["probabilities"].items()},
                        )
                    )
        return ClaimBatch(tuple(answers), _single_revision(revisions))

    def health(self) -> ModelHealth:
        with self._client() as client:
            response = client.get("/health/ready")
            response.raise_for_status()
            data = response.json()
        return ModelHealth("OpenJev-4B-v5", _revision(data), data["status"] == "ready")


def _revision(data: dict[str, Any]) -> str:
    revision = data["model_revision"]
    if not isinstance(revision, str) or not revision:
        raise ModelFailure("OpenJev не сообщил ревизию модели")
    return revision


def _single_revision(revisions: set[str]) -> str:
    if len(revisions) != 1:
        raise ModelFailure("OpenJev сменил ревизию внутри пакета")
    return next(iter(revisions))
