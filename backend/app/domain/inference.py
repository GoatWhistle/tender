"""Запросы к моделям и их ответы: эмбеддинги, decision-модель и извлекатель фактов.

Порты моделей (`app.usecase.interface`) принимают и отдают только эти типы. Модель не принимает
решений сама: её ответ — распределение и предложение, а порог принятия и проверки правил
КТРУ остаются в сценариях. Невалидный ответ модели — технический сбой, а не решение
(`app.domain.errors.ModelFailure`).
"""

from dataclasses import dataclass
from enum import StrEnum

Vector = tuple[float, ...]


@dataclass(frozen=True)
class ModelHealth:
    model: str
    revision: str
    ready: bool


@dataclass(frozen=True)
class EmbeddingBatch:
    """Векторы единичной длины в порядке текстов запроса."""

    vectors: tuple[Vector, ...]
    revision: str


@dataclass(frozen=True)
class ChoiceOption:
    option_id: str
    text: str


@dataclass(frozen=True)
class ChoiceQuestion:
    """Вопрос с выбором одного варианта; `question_id` уникален в пакете."""

    question_id: str
    text: str
    options: tuple[ChoiceOption, ...]

    @property
    def option_ids(self) -> tuple[str, ...]:
        return tuple(o.option_id for o in self.options)


@dataclass(frozen=True)
class ChoiceAnswer:
    """Распределение по вариантам вопроса; `selected = None` — модель отказалась выбирать.
    `truncated` — контекст не поместился целиком."""

    question_id: str
    probabilities: dict[str, float]
    selected: str | None
    truncated: bool = False
    # Независимые NLI-оценки поддержки критериев, до нормализации choice.
    support_scores: dict[str, float] | None = None


@dataclass(frozen=True)
class ChoiceBatch:
    answers: tuple[ChoiceAnswer, ...]
    revision: str


class Verdict(StrEnum):
    """Следует ли утверждение из контекста (раздел 8.5 плана)."""

    supported = "supported"
    contradicted = "contradicted"
    not_stated = "not_stated"


@dataclass(frozen=True)
class Claim:
    """Атомарное утверждение для проверки по контексту; `claim_id` уникален в пакете."""

    claim_id: str
    text: str


@dataclass(frozen=True)
class ClaimAnswer:
    claim_id: str
    probabilities: dict[Verdict, float]
    truncated: bool = False


@dataclass(frozen=True)
class ClaimBatch:
    answers: tuple[ClaimAnswer, ...]
    revision: str


@dataclass(frozen=True)
class SourceMessage:
    message_id: str
    text: str


@dataclass(frozen=True)
class TargetAttribute:
    """Характеристика, значение которой извлекатель может искать; `attribute_ref` —
    внутреннее имя поля, связь с характеристикой КТРУ хранится отдельно."""

    attribute_ref: str
    name: str
    units: tuple[str, ...] = ()


@dataclass(frozen=True)
class KnownFact:
    """Уже принятое значение поля — извлекателю как контекст, не как подсказка ответа."""

    attribute_ref: str
    raw_value: str
    raw_unit: str | None = None


@dataclass(frozen=True)
class ExtractionRequest:
    messages: tuple[SourceMessage, ...]
    accepted: tuple[KnownFact, ...]
    targets: tuple[TargetAttribute, ...]


@dataclass(frozen=True)
class ExtractedFact:
    """Предложение извлекателя (раздел 8.2–8.3 плана): исходное значение и единица как в
    тексте, без нормализации. `subject_ref` — объект или его часть в составном товаре."""

    attribute_ref: str
    raw_value: str
    raw_unit: str | None
    source_quote: str
    source_message_id: str
    negated: bool = False
    uncertain: bool = False
    subject_ref: str | None = None


@dataclass(frozen=True)
class Extraction:
    """Пустой список фактов допустим: извлекатель не обязан заполнять каждое поле."""

    facts: tuple[ExtractedFact, ...]
    revision: str
