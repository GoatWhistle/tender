"""DecisionBackend поверх API services/openjev; общая валидация — в composition.

У сервиса один choice на HTTP-запрос, NLI — пакет до 32 утверждений. Адаптер сохраняет
пакетный контракт порта и проверяет ревизию/порядок всех частей до возврата результата.
"""

import threading
from collections import OrderedDict
from collections.abc import Callable, Hashable, Iterator, Sequence
from contextlib import contextmanager
from dataclasses import replace
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
from app.usecase.interface import DecisionBackend


class OpenJevDecision:
    def __init__(
        self,
        base_url: str,
        *,
        timeout: float = 120,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._url = base_url.rstrip("/")
        self._http = httpx.Client(base_url=self._url, timeout=timeout, transport=transport)

    @contextmanager
    def _client(self) -> Iterator[httpx.Client]:
        # Один клиент на адаптер: создание httpx.Client — десятки миллисекунд (SSL-контекст),
        # а соединение с сервисом модели переиспользуется между вызовами. Клиент потокобезопасен.
        yield self._http

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


class CachedDecision:
    """Ответы decision-модели по паре «контекст — вопрос» из памяти процесса.

    Сессия повторяет одни и те же вопросы с тем же контекстом: пересчёт после правки фактов
    заново проверяет группы и enum-поля по неизменным сообщениям. Модель закреплена ревизией,
    поэтому ответ на тот же вход переиспользуется; в модель уходят только промахи одним пакетом.
    Ответы разных ревизий в один пакет не смешиваются — тогда кеш сбрасывается.
    """

    def __init__(self, inner: DecisionBackend, size: int = 4096) -> None:
        self._inner = inner
        self._size = size
        self._entries: OrderedDict[Hashable, tuple[str, Any]] = OrderedDict()
        self._lock = threading.Lock()

    def choose(self, context: str, questions: Sequence[ChoiceQuestion]) -> ChoiceBatch:
        def key(q: ChoiceQuestion) -> Hashable:
            return ("choice", context, q.text, q.options)

        def fetch(missing: Sequence[ChoiceQuestion]) -> tuple[list[ChoiceAnswer], str]:
            batch = self._inner.choose(context, missing)
            return list(batch.answers), batch.revision

        answers, revision = self._cached(questions, key, fetch)
        return ChoiceBatch(
            tuple(
                replace(a, question_id=q.question_id)
                for q, a in zip(questions, answers, strict=True)
            ),
            revision,
        )

    def verify(self, context: str, claims: Sequence[Claim]) -> ClaimBatch:
        def key(c: Claim) -> Hashable:
            return ("verify", context, c.text)

        def fetch(missing: Sequence[Claim]) -> tuple[list[ClaimAnswer], str]:
            batch = self._inner.verify(context, missing)
            return list(batch.answers), batch.revision

        answers, revision = self._cached(claims, key, fetch)
        return ClaimBatch(
            tuple(replace(a, claim_id=c.claim_id) for c, a in zip(claims, answers, strict=True)),
            revision,
        )

    def health(self) -> ModelHealth:
        return self._inner.health()

    def _cached[T, A](
        self,
        items: Sequence[T],
        key: Callable[[T], Hashable],
        fetch: Callable[[Sequence[T]], tuple[list[A], str]],
    ) -> tuple[list[A], str]:
        if not items:
            return fetch(items)
        keys = [key(i) for i in items]
        with self._lock:
            found = {k: self._entries[k] for k in keys if k in self._entries}
            for k in found:
                self._entries.move_to_end(k)
        missing = [i for i, k in zip(items, keys, strict=True) if k not in found]
        revisions = {r for r, _ in found.values()}
        if missing:
            fresh, revision = fetch(missing)
            if len(fresh) != len(missing):
                # Состав проверяет общая проверка ответов; здесь только не кешируем мусор.
                return fresh, revision
            if revisions - {revision}:
                # Модель сменила ревизию: старые ответы не смешиваем с новыми.
                with self._lock:
                    self._entries.clear()
                return self._cached(items, key, fetch)
            revisions.add(revision)
            with self._lock:
                for i, answer in zip(missing, fresh, strict=True):
                    self._entries[key(i)] = (revision, answer)
                while len(self._entries) > self._size:
                    self._entries.popitem(last=False)
            found |= {key(i): (revision, a) for i, a in zip(missing, fresh, strict=True)}
        return [found[k][1] for k in keys], next(iter(revisions))


def _revision(data: dict[str, Any]) -> str:
    revision = data["model_revision"]
    if not isinstance(revision, str) or not revision:
        raise ModelFailure("OpenJev не сообщил ревизию модели")
    return revision


def _single_revision(revisions: set[str]) -> str:
    if len(revisions) != 1:
        raise ModelFailure("OpenJev сменил ревизию внутри пакета")
    return next(iter(revisions))
