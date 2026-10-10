"""Проверка свободного экстракта по исходному диалогу через модельные порты."""

import hashlib
import json
import re
from collections.abc import Sequence
from dataclasses import asdict, dataclass, replace
from decimal import Decimal
from typing import Literal

from app.domain.catalog import Group, Position
from app.domain.errors import InvalidExtraction, InvalidFactEdit, ModelFailure
from app.domain.fact_edits import FactInput
from app.domain.facts import Fact, FactSource, Verification
from app.domain.inference import (
    Claim,
    ExtractedFact,
    ExtractionRequest,
    KnownFact,
    SourceMessage,
    TargetAttribute,
    Verdict,
)
from app.domain.sessions import FactEvent, Message
from app.domain.units import UNITS
from app.usecase.interface import DecisionBackend, ModelFactExtractor

PARTS = (
    ("столешниц", "столешница"),
    ("ножк", "ножки"),
    ("каркас", "каркас"),
    ("основан", "основание"),
    ("обивк", "обивка"),
)


@dataclass(frozen=True)
class VerificationPolicy:
    threshold: float = 0.90
    revision: str = "a20448012c213128955ca0c693e7c943865cab77"
    enabled: bool = True


class VerifiedExtractor:
    def __init__(
        self, extractor: ModelFactExtractor, decision: DecisionBackend, policy: VerificationPolicy
    ) -> None:
        self._extractor, self._decision, self._policy = extractor, decision, policy
        self.warnings: list[str] = []

    def run(
        self,
        messages: Sequence[Message],
        facts: Sequence[Fact],
        group: Group,
        remaining: Sequence[Position],
        revision: int,
        history: Sequence[FactEvent] = (),
    ) -> tuple[Fact, ...]:
        self.warnings = []
        correction = explicit_model_correction(messages, facts)
        names = sorted(
            {
                c.name
                for p in remaining
                for c in p.characteristics
                if correction
                or not any(f.accepted and f.characteristic_name == c.name for f in facts)
            }
        )
        request = ExtractionRequest(
            tuple(SourceMessage(m.id, m.text) for m in messages),
            tuple(
                KnownFact(f.characteristic_name or "", f.raw_value, f.raw_unit)
                for f in facts
                if f.accepted
            ),
            tuple(
                TargetAttribute(
                    n,
                    n,
                    tuple(
                        sorted(
                            {
                                v.unit_code
                                for p in remaining
                                for c in p.characteristics
                                if c.name == n
                                for v in c.values
                                if v.unit_code
                            }
                        )
                    ),
                    subject_ref=next(
                        (part for stem, part in PARTS if stem in n.lower()), "product"
                    ),
                )
                for n in names[:64]
            ),
        )
        if not names or not significant_remainder(messages, facts, group):
            return ()
        context = "\n".join(f"[{m.id}] {m.text}" for m in messages)
        context_hash = hashlib.sha256(context.encode()).hexdigest()
        results: dict[str, Fact] = {}
        json_retry = semantic_retry = False
        while True:
            try:
                batch = self._extractor.extract(request)
            except InvalidExtraction:
                if not json_retry:
                    json_retry = True
                    request = replace(
                        request, feedback=(*request.feedback, "Исправь JSON по переданной схеме.")
                    )
                    continue
                self.warnings.append(
                    "Извлечение не удалось: введите значение через редактор фактов."
                )
                break
            except ModelFailure:
                self.warnings.append("Извлекатель недоступен: доступен ручной ввод.")
                break
            contradictions = []
            for item in batch.facts:
                fact = structural_fact(item, messages, group)
                if fact is None:
                    self.warnings.append(
                        "Значение отклонено: проверьте источник и единицу в редакторе."
                    )
                    continue
                source_index = next(
                    i for i, m in enumerate(messages) if m.id == item.source_message_id
                )
                cutoff = max(
                    (
                        event.message_count
                        for event in history
                        if event.group == group.position.code
                        and event.action != "clarification"
                        and any(
                            f.characteristic_name == item.attribute_ref
                            for f in (*event.before, *event.after)
                        )
                    ),
                    default=0,
                )
                if source_index < cutoff:
                    continue
                message = messages[source_index]
                start = message.text.index(item.source_quote)
                identity = hashlib.sha256(
                    json.dumps(asdict(item), ensure_ascii=False, sort_keys=True).encode()
                ).hexdigest()[:24]
                claim = Claim(f"extract:{identity}:{int(semantic_retry)}", atomic_claim(item))
                binding = safe_binding(item, message.text) and not any(
                    item.attribute_ref.lower() in m.text.lower()
                    or re.search(r"\b(?:исправь|вместо|нет)\b", m.text.lower())
                    for m in messages[source_index + 1 :]
                )
                model_revision = None
                score = None
                accepted = False
                verdict = "unavailable"
                probabilities: dict[str, float] = {}
                try:
                    checked = self._decision.verify(context, (claim,))
                    model_revision = checked.revision
                    probabilities = {str(k): v for k, v in checked.answers[0].probabilities.items()}
                    verdict = max(probabilities, key=probabilities.__getitem__)
                    score = probabilities[Verdict.supported]
                    accepted = (
                        binding
                        and self._policy.enabled
                        and checked.revision == self._policy.revision
                        and verdict == Verdict.supported
                        and score >= self._policy.threshold
                    )
                except ModelFailure:
                    self.warnings.append(
                        "Проверка предложения недоступна: подтвердите или исправьте значение."
                    )
                if verdict == Verdict.contradicted:
                    contradictions.append(claim.text)
                results[claim.claim_id] = replace(
                    fact,
                    id=claim.claim_id,
                    origin="decision",
                    status="superseded"
                    if verdict == Verdict.contradicted
                    else "accepted_from_model"
                    if accepted
                    else "proposed",
                    source=FactSource(
                        message.id, item.source_quote, start, start + len(item.source_quote)
                    ),
                    normalization_rule="verified_extraction_v1",
                    model_revision=model_revision,
                    model_score=score,
                    negated=item.negated,
                    uncertain=item.uncertain,
                    requires_binding=not binding,
                    verification=Verification(
                        claim.text,
                        tuple(m.id for m in messages),
                        context_hash,
                        revision,
                        batch.revision,
                        model_revision,
                        verdict,
                        probabilities,
                        binding,
                        threshold=self._policy.threshold,
                    ),
                )
            if contradictions and not semantic_retry:
                semantic_retry = True
                request = replace(
                    request,
                    feedback=tuple(
                        "Проверка обнаружила противоречие; перечитай исходный диалог: " + c
                        for c in contradictions
                    ),
                )
                continue
            break
        return tuple(results.values())


def atomic_claim(item: ExtractedFact) -> str:
    subject = (
        f" части «{item.subject_ref}»"
        if item.subject_ref and item.subject_ref != "product"
        else " товара"
    )
    negation = "не " if item.negated else ""
    unit = " " + item.raw_unit if item.raw_unit else ""
    return f"Характеристика «{item.attribute_ref}»{subject} — {negation}{item.raw_value}{unit}."


def structural_fact(item: ExtractedFact, messages: Sequence[Message], group: Group) -> Fact | None:
    source = next((m for m in messages if m.id == item.source_message_id), None)
    if source is None or not item.source_quote or item.source_quote not in source.text:
        return None
    chars = [c for p in group.leaves for c in p.characteristics if c.name == item.attribute_ref]
    if not chars or (not chars[0].quantitative and item.raw_unit):
        return None
    kind: Literal["text", "range", "number"] = (
        "text" if not chars[0].quantitative else "range" if ".." in item.raw_value else "number"
    )
    try:
        fact = FactInput(
            item.attribute_ref,
            item.raw_value,
            item.raw_unit,
            kind,
            None if item.subject_ref == "product" else item.subject_ref,
        ).fact(group)
    except InvalidFactEdit:
        return None
    if fact.kind != "text":
        units = {v.unit_code for c in chars for v in c.values if v.unit_code}
        unit = UNITS.get(fact.unit_code or "")
        if units and (
            unit is None
            or any(code not in UNITS or UNITS[code].dimension != unit.dimension for code in units)
        ):
            return None
    # Значение должно быть извлечено, а не вычислено или придумано моделью.
    parts = item.raw_value.split("..") if kind == "range" else [item.raw_value]
    if kind == "text":
        if item.raw_value.strip().lower() not in item.source_quote.lower():
            return None
    else:
        numbers = {
            Decimal(n.replace(",", "."))
            for n in re.findall(r"(?<![\w.])[+-]?\d+(?:[.,]\d+)?(?![\w.])", item.source_quote)
        }
        if any(Decimal(part.strip().replace(",", ".")) not in numbers for part in parts):
            return None
        if (
            item.raw_unit
            and fact.unit_code
            and not re.search(
                r"(?<!\w)(?:" + UNITS[fact.unit_code].pattern + r")(?!\w)",
                item.source_quote.lower(),
            )
        ):
            return None
    return fact


def safe_binding(item: ExtractedFact, source_text: str) -> bool:
    if (
        item.negated
        or item.uncertain
        or re.search(r"\b(?:не|без|нет|примерно|возможно)\b", source_text.lower())
    ):
        return False
    if re.search(r"\b(?:рядом|возле|около|сравнени\w*|комплект\w*)\b", source_text.lower()):
        return False
    # Части разрешены лишь когда само поле явно принадлежит этой части.
    parts = ("столешниц", "ножк", "каркас", "основан", "обивк")
    mentioned = {part for part in parts if part in item.source_quote.lower()}
    named = {part for part in parts if part in item.attribute_ref.lower()}
    if any(part in source_text.lower() for part in parts) and not mentioned:
        return False
    if mentioned and (len(mentioned) != 1 or mentioned != named):
        return False
    if item.subject_ref and item.subject_ref != "product":
        subject = {part for part in parts if part in item.subject_ref.lower()}
        if not subject or subject != named:
            return False
    return True


def significant_remainder(messages: Sequence[Message], facts: Sequence[Fact], group: Group) -> bool:
    for message in messages:
        remainder = message.text.lower()
        for fact in facts:
            if fact.accepted and fact.source and fact.source.message_id == message.id:
                remainder = remainder.replace(fact.source.quote.lower(), " ")
        for word in re.findall(r"[а-яa-z]+", group.position.name.lower()):
            remainder = re.sub(r"\b" + re.escape(word) + r"\b", " ", remainder)
        words = re.findall(r"[а-яa-z]+", remainder)
        if re.search(r"\d", remainder) or any(len(w) > 3 for w in words):
            return True
    return False


def explicit_model_correction(messages: Sequence[Message], facts: Sequence[Fact]) -> bool:
    return bool(
        messages
        and re.fullmatch(r"исправь\s+.+\s+на\s+.+", messages[-1].text.lower().strip())
        and any(
            f.normalization_rule == "correction_needs_binding" and f.status == "ambiguous"
            for f in facts
        )
    )
