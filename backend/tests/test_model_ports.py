"""Порты моделей за общей проверкой ответа: заглушки из `app.adapter.stub` подключаются через
проводку `composition`, как in-memory хранилища. Невалидный ответ, сбой и таймаут адаптера —
`ModelFailure`, валидный ответ проходит без изменений."""

import math
from collections.abc import Callable

import pytest

from app.adapter.stub import StubDecisionBackend, StubEmbeddings, StubFactExtractor
from app.adapter.stub.fault import Scripted
from app.controller.errors import status_of
from app.domain.errors import ModelFailure
from app.domain.inference import (
    ChoiceAnswer,
    ChoiceBatch,
    ChoiceOption,
    ChoiceQuestion,
    Claim,
    ClaimAnswer,
    ClaimBatch,
    EmbeddingBatch,
    ExtractedFact,
    ExtractionRequest,
    KnownFact,
    SourceMessage,
    TargetAttribute,
    Verdict,
)
from composition import checked_decision, checked_embeddings, checked_extractor

MATERIAL = ChoiceQuestion(
    "q-material",
    "Материал столешницы",
    (ChoiceOption("v-ldsp", "ЛДСП"), ChoiceOption("v-wood", "Массив дерева")),
)
WOOD = ChoiceAnswer("q-material", {"v-ldsp": 0.1, "v-wood": 0.9}, selected="v-wood")
LEGS = Claim("c-legs", "Ножки стола металлические")
LEGS_OK = ClaimAnswer(
    "c-legs", {Verdict.supported: 0.95, Verdict.contradicted: 0.02, Verdict.not_stated: 0.03}
)
MESSAGE = SourceMessage("m-1", "Стол с металлическими ножками, ширина 120 см")
WIDTH = TargetAttribute("width", "Ширина", ("см", "мм"))
REQUEST = ExtractionRequest(
    messages=(MESSAGE,), accepted=(KnownFact("material", "дерево"),), targets=(WIDTH,)
)
WIDTH_FACT = ExtractedFact("width", "120", "см", "ширина 120 см", "m-1")


def norm(vector: tuple[float, ...]) -> float:
    return math.sqrt(sum(x * x for x in vector))


# --- эмбеддинги


def test_stub_embeddings_are_deterministic_and_normalized() -> None:
    embeddings = checked_embeddings(StubEmbeddings(dimension=16))
    texts = ["Стол письменный", "Топор", "", "Стол письменный"]

    first = embeddings.embed_documents(texts)
    second = embeddings.embed_documents(texts)

    assert first == second
    assert len(first.vectors) == len(texts)
    assert all(len(v) == 16 and abs(norm(v) - 1) < 1e-9 for v in first.vectors)
    assert first.vectors[0] == first.vectors[3]
    assert first.vectors[0] != first.vectors[1]
    assert embeddings.embed_queries(texts) == first


def test_stub_embeddings_bring_shared_words_closer() -> None:
    """Гибридный поиск проверяется на заглушке целиком: общие слова — ближе векторы."""
    query, near, far = (
        StubEmbeddings().embed_documents(["стол письменный", "письменный стол", "топор"]).vectors
    )

    def cos(a: tuple[float, ...], b: tuple[float, ...]) -> float:
        return sum(x * y for x, y in zip(a, b, strict=True))

    assert cos(query, near) > cos(query, far)


EMBED = ["embed_queries", "embed_documents"]


@pytest.mark.parametrize("call", EMBED)
def test_valid_embeddings_pass_unchanged(call: str) -> None:
    stub = StubEmbeddings(dimension=2)
    stub.reply = EmbeddingBatch(vectors=((0.6, 0.8),), revision="r1")

    assert getattr(checked_embeddings(stub), call)(["a"]) is stub.reply


@pytest.mark.parametrize("call", EMBED)
@pytest.mark.parametrize(
    "vectors",
    [
        pytest.param((), id="векторов меньше текстов"),
        pytest.param(((1.0, 0.0), (0.0, 1.0)), id="векторов больше текстов"),
        pytest.param(((1.0, 0.0, 0.0),), id="чужая размерность"),
        pytest.param(((math.nan, 1.0),), id="NaN"),
        pytest.param(((3.0, 4.0),), id="не нормирован"),
    ],
)
def test_invalid_embeddings_are_model_failure(
    vectors: tuple[tuple[float, ...], ...], call: str
) -> None:
    stub = StubEmbeddings(dimension=2)
    stub.reply = EmbeddingBatch(vectors=vectors, revision="r1")

    with pytest.raises(ModelFailure):
        getattr(checked_embeddings(stub), call)(["a"])


# --- decision: выбор из вариантов


def test_valid_choice_passes_unchanged() -> None:
    stub = StubDecisionBackend()
    stub.choices["q-material"] = WOOD

    batch = checked_decision(stub).choose("Стол из массива дуба", [MATERIAL])

    assert batch.answers == (WOOD,)
    assert batch.revision == stub.revision


def test_unscripted_question_gets_uniform_abstention() -> None:
    batch = checked_decision(StubDecisionBackend()).choose("", [MATERIAL])

    assert batch.answers == (ChoiceAnswer("q-material", {"v-ldsp": 0.5, "v-wood": 0.5}, None),)


@pytest.mark.parametrize(
    "answers",
    [
        pytest.param((ChoiceAnswer("q-other", {"v-wood": 1.0}, "v-wood"),), id="чужой question_id"),
        pytest.param((), id="нет ответа на вопрос"),
        pytest.param((WOOD, WOOD), id="два ответа на вопрос"),
        pytest.param(
            (ChoiceAnswer("q-material", {"v-ldsp": 0.1, "v-glass": 0.9}, "v-glass"),),
            id="чужой option_id в распределении",
        ),
        pytest.param(
            (ChoiceAnswer("q-material", {"v-ldsp": 0.1, "v-wood": 0.9}, "v-glass"),),
            id="чужой выбранный вариант",
        ),
        pytest.param(
            (ChoiceAnswer("q-material", {"v-ldsp": math.nan, "v-wood": 0.9}, None),), id="NaN"
        ),
        pytest.param(
            (ChoiceAnswer("q-material", {"v-ldsp": -0.1, "v-wood": 1.1}, None),),
            id="отрицательная вероятность",
        ),
        pytest.param(
            (ChoiceAnswer("q-material", {"v-ldsp": 0.2, "v-wood": 0.9}, None),), id="сумма не 1"
        ),
        pytest.param(
            (ChoiceAnswer("q-material", {"v-wood": 1.0}, "v-wood"),), id="вариант без вероятности"
        ),
        pytest.param(
            (ChoiceAnswer("q-material", {"v-ldsp": 0.1, "v-wood": 0.9}, "v-wood", True),),
            id="усечённый контекст",
        ),
    ],
)
def test_invalid_choice_is_model_failure(answers: tuple[ChoiceAnswer, ...]) -> None:
    stub = StubDecisionBackend()
    stub.choice_reply = ChoiceBatch(answers=answers, revision="r1")

    with pytest.raises(ModelFailure):
        checked_decision(stub).choose("", [MATERIAL])


def test_sum_within_tolerance_passes() -> None:
    stub = StubDecisionBackend()
    stub.choices["q-material"] = ChoiceAnswer(
        "q-material", {"v-ldsp": 0.1, "v-wood": 0.9005}, "v-wood"
    )

    checked_decision(stub).choose("", [MATERIAL])


# --- decision: проверка утверждений


def test_valid_verification_passes_unchanged() -> None:
    stub = StubDecisionBackend()
    stub.claims["c-legs"] = LEGS_OK

    batch = checked_decision(stub).verify(MESSAGE.text, [LEGS])

    assert batch.answers == (LEGS_OK,)


def test_unscripted_claim_is_not_stated() -> None:
    (answer,) = checked_decision(StubDecisionBackend()).verify("", [LEGS]).answers

    assert answer.probabilities[Verdict.not_stated] == 1.0


@pytest.mark.parametrize(
    "answers",
    [
        pytest.param((ClaimAnswer("c-other", LEGS_OK.probabilities),), id="чужой claim_id"),
        pytest.param((), id="нет ответа на утверждение"),
        pytest.param(
            (ClaimAnswer("c-legs", {Verdict.supported: 1.0}),), id="вердикт без вероятности"
        ),
        pytest.param(
            (
                ClaimAnswer(
                    "c-legs",
                    {Verdict.supported: math.nan, Verdict.contradicted: 0, Verdict.not_stated: 1},
                ),
            ),
            id="NaN",
        ),
        pytest.param(
            (
                ClaimAnswer(
                    "c-legs",
                    {Verdict.supported: 0.5, Verdict.contradicted: 0.5, Verdict.not_stated: 0.5},
                ),
            ),
            id="сумма не 1",
        ),
        pytest.param((ClaimAnswer("c-legs", LEGS_OK.probabilities, True),), id="усечённый"),
    ],
)
def test_invalid_verification_is_model_failure(answers: tuple[ClaimAnswer, ...]) -> None:
    stub = StubDecisionBackend()
    stub.claim_reply = ClaimBatch(answers=answers, revision="r1")

    with pytest.raises(ModelFailure):
        checked_decision(stub).verify("", [LEGS])


# --- извлекатель


def test_valid_extraction_passes_unchanged() -> None:
    stub = StubFactExtractor()
    stub.facts = [WIDTH_FACT]

    extraction = checked_extractor(stub).extract(REQUEST)

    assert extraction.facts == (WIDTH_FACT,)
    assert stub.requests == [REQUEST]


def test_empty_extraction_is_valid() -> None:
    assert checked_extractor(StubFactExtractor()).extract(REQUEST).facts == ()


@pytest.mark.parametrize(
    "fact",
    [
        pytest.param(
            ExtractedFact("height", "75", "см", "ширина 120 см", "m-1"), id="чужой attribute_ref"
        ),
        pytest.param(
            ExtractedFact("width", "120", "см", "ширина 120 см", "m-9"),
            id="чужой source_message_id",
        ),
    ],
)
def test_invalid_extraction_is_model_failure(fact: ExtractedFact) -> None:
    stub = StubFactExtractor()
    stub.facts = [fact]

    with pytest.raises(ModelFailure):
        checked_extractor(stub).extract(REQUEST)


# --- сбой и таймаут адаптера, здоровье


def call_embed_queries() -> tuple[Scripted, Callable[[], object]]:
    stub = StubEmbeddings()
    return stub, lambda: checked_embeddings(stub).embed_queries(["a"])


def call_embed_documents() -> tuple[Scripted, Callable[[], object]]:
    stub = StubEmbeddings()
    return stub, lambda: checked_embeddings(stub).embed_documents(["a"])


def call_choose() -> tuple[Scripted, Callable[[], object]]:
    stub = StubDecisionBackend()
    return stub, lambda: checked_decision(stub).choose("", [MATERIAL])


def call_verify() -> tuple[Scripted, Callable[[], object]]:
    stub = StubDecisionBackend()
    return stub, lambda: checked_decision(stub).verify("", [LEGS])


def call_extract() -> tuple[Scripted, Callable[[], object]]:
    stub = StubFactExtractor()
    return stub, lambda: checked_extractor(stub).extract(REQUEST)


CALLS = [call_embed_queries, call_embed_documents, call_choose, call_verify, call_extract]


@pytest.mark.parametrize("make", CALLS)
def test_adapter_failure_is_model_failure(
    make: Callable[[], tuple[Scripted, Callable[[], object]]],
) -> None:
    stub, call = make()
    cause = ConnectionError("model worker недоступен")
    stub.fail(cause)

    with pytest.raises(ModelFailure) as caught:
        call()
    assert caught.value.__cause__ is cause
    assert caught.value.code == "technical_error"


@pytest.mark.parametrize("make", CALLS)
def test_adapter_timeout_is_model_failure(
    make: Callable[[], tuple[Scripted, Callable[[], object]]],
) -> None:
    stub, call = make()
    stub.time_out()

    with pytest.raises(ModelFailure) as caught:
        call()
    assert isinstance(caught.value.__cause__, TimeoutError)


def test_model_failure_is_service_unavailable() -> None:
    assert status_of(ModelFailure) == 503


def test_health_reports_model_revision_and_readiness() -> None:
    stub = StubDecisionBackend()
    stub.ready = False

    health = checked_decision(stub).health()

    assert (health.model, health.revision, health.ready) == ("stub-decision", stub.revision, False)
    assert checked_embeddings(StubEmbeddings()).health().ready
    assert checked_extractor(StubFactExtractor()).health().ready


def test_malformed_answer_is_model_failure() -> None:
    """Ответ не того типа — невалидный ответ модели, а не ошибка кода (500)."""
    malformed: dict[str, float] = {"v-ldsp": "0.1", "v-wood": 0.9}  # type: ignore[dict-item]
    stub = StubDecisionBackend()
    stub.choices["q-material"] = ChoiceAnswer("q-material", malformed, None)

    with pytest.raises(ModelFailure) as caught:
        checked_decision(stub).choose("", [MATERIAL])
    assert isinstance(caught.value.__cause__, TypeError)
