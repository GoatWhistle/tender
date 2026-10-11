import asyncio
from typing import Any

from rag.domain.catalog import Position
from rag.domain.inference import Effort, StructuredRequest, Tier
from rag.domain.suggestions import (
    LIMIT,
    Stat,
    Suggestion,
    norm,
    similar,
    stem,
    strip_unit,
    summarize,
)
from rag.usecase.cards import card
from rag.usecase.interface import AnalogsIndex, LanguageModel

TITLES = 12

SYSTEM_PROMPT = (
    "Ты помогаешь заполнить карточку товара для госзакупки по 44-ФЗ. Предложи до 6 "
    "дополнительных характеристик, которых нет в КТРУ и которые нужны, чтобы описать "
    "конкретный товар и проверить его при приёмке (п. 5 Правил использования КТРУ, ПП РФ № 145).\n"
    "Источники:\n"
    "- аналоги — характеристики похожих товаров каталога СТЕ с долей товаров, где они указаны. "
    "Сначала реши, тот же ли это вид товара по назначению (analogs_relevant). Если аналоги — "
    "другой товар (например, строительный инструмент вместо медицинского), не бери их;\n"
    "- собственные знания о товаре, если аналоги не подходят или их мало.\n"
    "Правила для характеристики:\n"
    "- не дублирует и не переименовывает характеристику КТРУ и не повторяет название позиции;\n"
    "- объективна и проверяется при приёмке: измерение, материал, наличие, конструкция;\n"
    "- без товарного знака, модели, производителя, страны, артикула, упаковки (ст. 33 44-ФЗ);\n"
    "- важна заказчику: влияет на назначение, безопасность, совместимость или срок службы. "
    "Цвет и декор — только если они функциональны;\n"
    "- название в стиле КТРУ: существительное с уточнением, без значения и единицы в названии; "
    "синонимы аналогов склей в одно название.\n"
    "value — значение для этого товара только из описания поставщика, без единицы измерения; "
    "evidence — дословная цитата из описания. Если в описании значения нет, value и evidence — "
    "пустые строки, не угадывай. options — до 6 типичных значений без единицы (из аналогов или "
    "общие), unit — единица измерения или пустая строка. source: «СТЕ», если взята из аналогов, "
    "иначе «ИИ». why — одно короткое предложение, зачем она заказчику. Сортируй по важности."
)

SCHEMA = {
    "type": "object",
    "properties": {
        "analogs_relevant": {"type": "boolean"},
        "analogs_comment": {"type": "string"},
        "characteristics": {
            "type": "array",
            "maxItems": LIMIT,
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "unit": {"type": "string"},
                    "options": {"type": "array", "items": {"type": "string"}},
                    "value": {"type": "string"},
                    "evidence": {"type": "string"},
                    "source": {"type": "string", "enum": ["СТЕ", "ИИ"]},
                    "why": {"type": "string"},
                },
                "required": [
                    "name",
                    "unit",
                    "options",
                    "value",
                    "evidence",
                    "source",
                    "why",
                ],
                "additionalProperties": False,
            },
        },
    },
    "required": ["analogs_relevant", "analogs_comment", "characteristics"],
    "additionalProperties": False,
}


def build_prompt(
    p: Position, description: str, titles: list[str], stats: list[Stat]
) -> str:
    lines = [card(p, {}, []), "", f"Описание поставщика:\n{description}", ""]
    if titles:
        lines.append(f"Аналоги СТЕ ({len(titles)} шт.), примеры названий:")
        lines.extend(f"- {t}" for t in titles[:TITLES])
        lines.append("Характеристики аналогов (доля товаров: примеры значений):")
        lines.extend(
            f"- {s.name} ({s.share:.0%}): {'; '.join(s.values)}" for s in stats
        )
    else:
        lines.append("Аналогов СТЕ не найдено.")
    return "\n".join(lines)


def clean(
    p: Position, description: str, out: dict[str, Any], stats: list[Stat]
) -> list[Suggestion]:
    taken = {norm(c.name) for c in p.characteristics} | {norm(p.name)}
    known = [(stem(s.name), s.share) for s in stats] if out["analogs_relevant"] else []
    found = []
    for c in out["characteristics"]:
        name, unit = c["name"].strip(), c["unit"].strip()
        if not name or norm(name) in taken:
            continue
        taken.add(norm(name))
        own = stem(name)
        share = max((s for k, s in known if similar(own, k)), default=None)
        value, evidence = c["value"], c["evidence"].strip()
        if not evidence or evidence.lower() not in description.lower():
            value = evidence = ""
        from_ste = share is not None and c["source"] == "СТЕ"
        found.append(
            Suggestion(
                name=name,
                unit=unit,
                options=tuple(
                    dict.fromkeys(
                        o for o in (strip_unit(o, unit) for o in c["options"]) if o
                    )
                ),
                value=strip_unit(value, unit),
                evidence=evidence,
                source="СТЕ" if from_ste else "ИИ",
                share=share if c["source"] == "СТЕ" else None,
                why=c["why"].strip(),
            )
        )
    return found


class Suggester:
    def __init__(self, llm: LanguageModel, analogs: AnalogsIndex) -> None:
        self._llm = llm
        self._analogs = analogs

    async def run(self, p: Position, description: str) -> list[Suggestion]:
        items = await asyncio.to_thread(
            self._analogs.nearest, f"{p.name} {description}"
        )
        stats = summarize(items)
        titles = [item.title for item in items]
        completion = await self._llm.complete(
            StructuredRequest(
                SYSTEM_PROMPT,
                build_prompt(p, description, titles, stats),
                SCHEMA,
                Tier.SMART,
                Effort.LOW,
            )
        )
        return clean(p, description, completion.output, stats)
