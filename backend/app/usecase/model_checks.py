"""Общая проверка ответов моделей — одна на все адаптеры, а не своя в каждом.

Обёртки реализуют те же порты, принимают любую реализацию и пропускают дальше только валидный
ответ, без изменений. Невалидный ответ, исключение и таймаут адаптера — `ModelFailure` с
исходным исключением в `__cause__`: технический сбой не выдаётся за решение (раздел 7.4 плана).
"""

import math
from collections.abc import Callable, Collection, Iterable, Mapping, Sequence

from app.domain.errors import ModelFailure
from app.domain.inference import (
    ChoiceBatch,
    ChoiceQuestion,
    Claim,
    ClaimBatch,
    EmbeddingBatch,
    Extraction,
    ExtractionRequest,
    ModelHealth,
    Verdict,
)
from app.usecase.interface import DecisionBackend, Embeddings, FactExtractor

TOLERANCE = 1e-3


def _call[T](call: Callable[[], T]) -> T:
    """Вызов адаптера вместе с проверкой ответа: ответ не того типа (`None` вместо пакета,
    строка вместо вероятности) — тоже невалидный ответ, а не ошибка кода."""
    try:
        return call()
    except ModelFailure:
        raise
    except Exception as exc:
        raise ModelFailure() from exc


def _invalid(reason: str) -> ModelFailure:
    return ModelFailure(f"Модель вернула невалидный ответ: {reason}")


def _check_ids(answered: Iterable[str], asked: Iterable[str], what: str) -> None:
    """Ровно по одному ответу на каждый заданный ID."""
    got, want = sorted(answered), sorted(asked)
    if got != want:
        raise _invalid(f"{what}: ответы на {got} вместо {want}")


def _check_distribution[K: str](
    probabilities: Mapping[K, float], keys: Collection[K], at: str
) -> None:
    if set(probabilities) != set(keys):
        raise _invalid(f"{at}: распределение по {sorted(probabilities)} вместо {sorted(keys)}")
    values = list(probabilities.values())
    if not all(math.isfinite(p) and p >= 0 for p in values):
        raise _invalid(f"{at}: вероятности {values}")
    if abs(sum(values) - 1) > TOLERANCE:
        raise _invalid(f"{at}: сумма вероятностей {sum(values)}")


class CheckedEmbeddings:
    def __init__(self, inner: Embeddings) -> None:
        self._inner = inner

    @property
    def dimension(self) -> int:
        return _call(lambda: self._inner.dimension)

    def embed_queries(self, texts: Sequence[str]) -> EmbeddingBatch:
        return _call(lambda: self._check(texts, self._inner.embed_queries(texts)))

    def embed_documents(self, texts: Sequence[str]) -> EmbeddingBatch:
        return _call(lambda: self._check(texts, self._inner.embed_documents(texts)))

    def _check(self, texts: Sequence[str], batch: EmbeddingBatch) -> EmbeddingBatch:
        dimension = self._inner.dimension
        if len(batch.vectors) != len(texts):
            raise _invalid(f"{len(batch.vectors)} векторов на {len(texts)} текстов")
        for vector in batch.vectors:
            if len(vector) != dimension:
                raise _invalid(f"вектор размерности {len(vector)} вместо {dimension}")
            if not all(math.isfinite(x) for x in vector):
                raise _invalid("вектор с NaN или бесконечностью")
            if abs(math.sqrt(sum(x * x for x in vector)) - 1) > TOLERANCE:
                raise _invalid("вектор не единичной длины")
        return batch

    def health(self) -> ModelHealth:
        return _call(self._inner.health)


class CheckedDecisionBackend:
    def __init__(self, inner: DecisionBackend) -> None:
        self._inner = inner

    def choose(self, context: str, questions: Sequence[ChoiceQuestion]) -> ChoiceBatch:
        return _call(lambda: self._choose(context, questions))

    def _choose(self, context: str, questions: Sequence[ChoiceQuestion]) -> ChoiceBatch:
        batch = self._inner.choose(context, questions)
        options = {q.question_id: q.option_ids for q in questions}
        _check_ids((a.question_id for a in batch.answers), options, "вопросы")
        for answer in batch.answers:
            at = f"вопрос {answer.question_id}"
            _check_distribution(answer.probabilities, options[answer.question_id], at)
            if answer.selected is not None and answer.selected not in answer.probabilities:
                raise _invalid(f"{at}: выбран неизвестный вариант {answer.selected}")
            if answer.truncated:
                raise _invalid(f"{at}: контекст усечён")
        return batch

    def verify(self, context: str, claims: Sequence[Claim]) -> ClaimBatch:
        return _call(lambda: self._verify(context, claims))

    def _verify(self, context: str, claims: Sequence[Claim]) -> ClaimBatch:
        batch = self._inner.verify(context, claims)
        _check_ids((a.claim_id for a in batch.answers), [c.claim_id for c in claims], "утверждения")
        for answer in batch.answers:
            at = f"утверждение {answer.claim_id}"
            _check_distribution(answer.probabilities, list(Verdict), at)
            if answer.truncated:
                raise _invalid(f"{at}: контекст усечён")
        return batch

    def health(self) -> ModelHealth:
        return _call(self._inner.health)


class CheckedFactExtractor:
    """Только ссылки факта на запрос; цитата в сообщении и единица — проверки сценария
    извлечения."""

    def __init__(self, inner: FactExtractor) -> None:
        self._inner = inner

    def extract(self, request: ExtractionRequest) -> Extraction:
        return _call(lambda: self._extract(request))

    def _extract(self, request: ExtractionRequest) -> Extraction:
        extraction = self._inner.extract(request)
        targets = {t.attribute_ref for t in request.targets}
        messages = {m.message_id for m in request.messages}
        for fact in extraction.facts:
            if fact.attribute_ref not in targets:
                raise _invalid(f"факт о характеристике {fact.attribute_ref} вне запроса")
            if fact.source_message_id not in messages:
                raise _invalid(f"факт из сообщения {fact.source_message_id} вне запроса")
        return extraction

    def health(self) -> ModelHealth:
        return _call(self._inner.health)
