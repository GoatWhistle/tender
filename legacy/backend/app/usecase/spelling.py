"""Проверка гипотез орфографии; никаких правок исходника или принятых фактов."""

import re

from app.domain.diagnostics import Diagnostic, DiagnosticScope
from app.domain.errors import ModelFailure
from app.domain.sessions import AnalysisError, Message
from app.domain.units import UNITS
from app.usecase.interface import SpellingService


def spelling_diagnostics(
    service: SpellingService,
    message: Message,
) -> tuple[Diagnostic | AnalysisError, ...]:
    try:
        suggestions = service.suggest(message)
    except ModelFailure:
        return (
            AnalysisError(
                "spelling_failed", "Орфографический сервис недоступен; текст проверен не полностью."
            ),
        )
    result: list[Diagnostic | AnalysisError] = []
    invalid = False
    seen: set[tuple[int, int]] = set()
    for item in suggestions:
        source = item.source
        valid = (
            source.message_id == message.id
            and 0 <= source.start < source.end <= len(message.text)
            and message.text[source.start : source.end] == source.quote
        )
        if not valid:
            invalid = True
            continue
        # Консервативный проход: только отдельные строчные русские слова.
        # Числа, единицы, регистровые бренды, артикулы и явно названные марки защищены.
        words = (source.quote, item.replacement)
        left = message.text[: source.start].lower()
        protected = (
            any(not re.fullmatch("[а-яё]{4,}", word) for word in words)
            or any(
                re.fullmatch(u.pattern, word, re.IGNORECASE)
                for u in UNITS.values()
                for word in words
            )
            or bool(re.search(r"(?:бренд|марка|модель|артикул)\s*:?\s*$", left))
            or (source.start > 0 and message.text[source.start - 1].isalnum())
            or (source.end < len(message.text) and message.text[source.end].isalnum())
        )
        if protected or source.quote == item.replacement:
            invalid = True
            continue
        if (source.start, source.end) in seen:
            continue
        seen.add((source.start, source.end))
        result.append(
            Diagnostic(
                "typo",
                None,
                source.quote,
                source,
                (),
                item.replacement,
                (),
                DiagnosticScope(None, (), False),
                True,
                "Орфографическая гипотеза; характеристика и правило КТРУ не установлены.",
                (item.replacement,),
            )
        )
    if invalid:
        result.append(
            AnalysisError(
                "spelling_invalid_response",
                "Часть орфографических предложений не прошла проверку цитат "
                "или защищённых значений; текст проверен не полностью.",
            )
        )
    return tuple(result)
