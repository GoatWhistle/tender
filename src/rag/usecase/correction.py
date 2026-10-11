from rag.domain.correction import Corrected, Fix
from rag.domain.inference import StructuredRequest, Tier
from rag.usecase.interface import LanguageModel

SYSTEM_PROMPT = (
    "Ты корректор описаний товаров для госзакупок. Тебе дают описание товара от поставщика. "
    "Исправь опечатки, ошибки раскладки, слитные и разорванные слова, неверные единицы "
    "измерения и явные логические ошибки (например, перепутанные размеры или единицы). "
    "Не добавляй новых фактов, не убирай характеристики, не меняй смысл и числа без явной "
    "причины. Каждую сделанную правку перечисли в fixes. В issues пиши только противоречия, "
    "которые ты НЕ исправил, потому что их нельзя исправить однозначно; исправленное в issues "
    "не повторяй. Если ошибок нет, верни текст без изменений, fixes и issues пустые."
)

SCHEMA = {
    "type": "object",
    "properties": {
        "corrected": {"type": "string"},
        "fixes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "before": {"type": "string"},
                    "after": {"type": "string"},
                    "kind": {
                        "type": "string",
                        "enum": ["typo", "logic", "unit", "other"],
                    },
                },
                "required": ["before", "after", "kind"],
                "additionalProperties": False,
            },
        },
        "issues": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["corrected", "fixes", "issues"],
    "additionalProperties": False,
}


class Corrector:
    def __init__(self, llm: LanguageModel) -> None:
        self._llm = llm

    async def run(self, text: str) -> Corrected:
        completion = await self._llm.complete(
            StructuredRequest(
                SYSTEM_PROMPT, f"Описание товара:\n{text}", SCHEMA, Tier.FAST
            )
        )
        out = completion.output
        return Corrected(
            original=text,
            corrected=out["corrected"].strip() or text,
            fixes=[Fix(**f) for f in out["fixes"]],
            issues=list(out["issues"]),
            usage=completion.usage,
        )
