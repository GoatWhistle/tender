from rag.domain.catalog import Position
from rag.domain.inference import Effort, StructuredRequest, Tier
from rag.domain.spec import Extra, Verdict
from rag.usecase.cards import card
from rag.usecase.interface import LanguageModel

SYSTEM_PROMPT = (
    "Ты проверяешь карточку товара на портале поставщиков. Поставщик выбрал позицию КТРУ и "
    "добавляет характеристику своего товара, которой нет в КТРУ (п. 5 Правил использования "
    "КТРУ, ПП РФ № 145). Характеристика описывает конкретный товар поставщика, поэтому одно "
    "конкретное значение — норма. Отклоняй (ok=false) только если характеристика:\n"
    "- дублирует или переименовывает характеристику КТРУ — её надо менять в КТРУ, а не "
    "добавлять;\n"
    "- противоречит неизменяемым или выбранным значениям КТРУ или другим добавленным "
    "характеристикам;\n"
    "- указывает товарный знак, модель, производителя или страну происхождения (ст. 33 "
    "44-ФЗ);\n"
    "- не относится к этому товару или его назначению;\n"
    "- субъективна и не проверяется при приёмке («качественный», «современный», «удобный»);\n"
    "- имеет физически неправдоподобное значение или неверную единицу измерения.\n"
    "Обоснование необязательно: пустое или «так сказал поставщик» — не причина отклонять. "
    "Если КТРУ не задаёт характеристик, дублировать и противоречить нечему. Не отклоняй за "
    "нетипичность или неполноту формулировки. В warnings — не больше двух коротких "
    "практических советов по уточнению названия или значения, без слов об обосновании и "
    "конкуренции; если советовать нечего, пустой массив. В problems — только причины "
    "отклонения из списка. "
    "Если характеристику можно исправить, предложи исправленные название и значение в "
    "fixed_name и fixed_value, иначе оставь их пустыми. Не придумывай значение, которого нет "
    "во вводе: исправлять можно только название, единицу или запись. Если всё корректно, "
    "ok=true, problems "
    "пустой."
)

SCHEMA = {
    "type": "object",
    "properties": {
        "ok": {"type": "boolean"},
        "problems": {"type": "array", "items": {"type": "string"}},
        "warnings": {"type": "array", "items": {"type": "string"}},
        "fixed_name": {"type": "string"},
        "fixed_value": {"type": "string"},
    },
    "required": ["ok", "problems", "warnings", "fixed_name", "fixed_value"],
    "additionalProperties": False,
}


def build_prompt(
    p: Position, chosen: dict[str, tuple[str, ...]], extras: list[Extra], new: Extra
) -> str:
    return (
        f"{card(p, chosen, extras)}\n\nНовая характеристика:\n"
        f"Название: {new.name}\nЗначение: {new.value}\nОбоснование: {new.reason or 'не указано'}"
    )


class ExtraValidator:
    def __init__(self, llm: LanguageModel) -> None:
        self._llm = llm

    async def run(
        self,
        p: Position,
        chosen: dict[str, tuple[str, ...]],
        extras: list[Extra],
        new: Extra,
    ) -> Verdict:
        completion = await self._llm.complete(
            StructuredRequest(
                SYSTEM_PROMPT,
                build_prompt(p, chosen, extras, new),
                SCHEMA,
                Tier.SMART,
                Effort.LOW,
            )
        )
        out = completion.output
        ok = out["ok"] and not out["problems"]
        fixed = None
        if not ok:
            candidate = Extra(
                out["fixed_name"].strip(), out["fixed_value"].strip(), new.reason
            )
            fixed = candidate if candidate.complete else None
        return Verdict(
            ok, list(out["problems"]), list(out["warnings"]), fixed, completion.usage
        )
