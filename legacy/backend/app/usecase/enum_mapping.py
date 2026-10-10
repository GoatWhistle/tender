"""Пакетное сопоставление по порту DecisionBackend; модели не выбирают часть товара."""

import re
from collections.abc import Sequence
from dataclasses import replace

from app.domain.catalog import Position
from app.domain.enum_mapping import (
    AutoAcceptance,
    EnumProposal,
    enum_fields,
    unambiguous_enum_binding,
)
from app.domain.facts import Fact, FactSource, normalized
from app.domain.inference import ChoiceOption, ChoiceQuestion, Claim, Verdict
from app.domain.sessions import Message
from app.usecase.interface import DecisionBackend


class EnumMapper:
    def __init__(self, decision: DecisionBackend, policy: AutoAcceptance) -> None:
        self._decision = decision
        self._policy = policy

    def map(
        self,
        messages: Sequence[Message],
        positions: Sequence[Position],
        revision: int,
        skip: set[str],
    ) -> tuple[tuple[Fact, ...], tuple[EnumProposal, ...]]:
        fields = [f for f in enum_fields(positions) if f.name not in skip]
        if not fields:
            return (), ()
        facts: list[Fact] = []
        by_field: dict[str, list[tuple[str, Fact, float, bool]]] = {}
        for message in messages:
            if not fields:
                break
            questions = [
                ChoiceQuestion(
                    f"q{i}",
                    (
                        f"Какое значение характеристики «{field.name}» явно указано у товара? "
                        "Если не указано, выберите «не указано»."
                    ),
                    (
                        *tuple(ChoiceOption(f"v{j}", v) for j, v in enumerate(field.values)),
                        ChoiceOption("unknown", "не указано"),
                    ),
                )
                for i, field in enumerate(fields)
                if not field.multiple
            ]
            choices = self._decision.choose(message.text, questions) if questions else None
            claims = [
                Claim(
                    f"f{i}:v{j}",
                    f"У описанного товара характеристика «{field.name}» имеет значение «{value}».",
                )
                for i, field in enumerate(fields)
                for j, value in enumerate(field.values)
            ]
            verified = self._decision.verify(message.text, claims)
            answers = {a.claim_id: a for a in verified.answers}
            selected = {a.question_id: a for a in choices.answers} if choices else {}
            for i, field in enumerate(fields):
                for j, value in enumerate(field.values):
                    answer = answers[f"f{i}:v{j}"]
                    # Проверяем все значения и для одиночного выбора: choose не должен скрывать
                    # второе явно указанное значение в недопустимом сочетании.
                    if (
                        max(answer.probabilities, key=answer.probabilities.__getitem__)
                        != Verdict.supported
                    ):
                        continue
                    if re.search(r"\b(?:не|без|нет)\b", normalized(message.text)):
                        continue  # консервативно: отрицание не становится положительным фактом
                    score = answer.probabilities[Verdict.supported]
                    choice = selected.get(f"q{i}")
                    if choice is not None:
                        if choice.selected in (None, "unknown"):
                            continue
                        if choices is not None and choices.revision != verified.revision:
                            from app.domain.errors import ModelFailure

                            raise ModelFailure("Ревизия decision-модели сменилась внутри анализа")
                        score = min(score, choice.probabilities.get(f"v{j}", 0.0))
                    # Повторные сообщения могут исправлять предыдущие: до отдельного
                    # разрешения противоречий их модельные значения требуют подтверждения.
                    binding = len(messages) == 1 and unambiguous_enum_binding(
                        message.text, field, value, fields
                    )
                    fact = Fact(
                        f"decision:{message.id}:{i}:{j}",
                        field.name,
                        field.name,
                        message.text,
                        None,
                        normalized(value),
                        None,
                        "text",
                        FactSource(message.id, message.text, 0, len(message.text)),
                        "enum_decision_v2",
                        origin="decision",
                        status="proposed",
                        model_revision=verified.revision,
                        model_score=score,
                    )
                    by_field.setdefault(field.name, []).append((value, fact, score, binding))
        proposals: list[EnumProposal] = []
        for field in fields:
            entries = by_field.get(field.name, [])
            if not entries:
                continue
            values = tuple(dict.fromkeys(v for v, *_ in entries))
            permitted = field.permits(values)
            auto = permitted and all(
                self._policy.accepts(score, fact.model_revision or "", unambiguous=binding)
                for _, fact, score, binding in entries
            )
            facts.extend(
                replace(fact, status="accepted_from_model") if auto else fact
                for _, fact, _, _ in entries
            )
            if not auto:
                reason = (
                    "Уточните значение: это сочетание не допускается каталогом."
                    if not permitted
                    else "Подтвердите значение и его привязку к характеристике товара."
                )
                proposals.append(
                    EnumProposal(
                        f"enum:{revision}:{len(proposals)}",
                        field.name,
                        values,
                        field.values,
                        field.selections,
                        reason,
                    )
                )
        return tuple(facts), tuple(proposals)
