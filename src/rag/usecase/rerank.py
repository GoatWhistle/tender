from rag.domain.inference import Effort, StructuredRequest, Tier
from rag.domain.search import Hit, Ranked, Reranking, exact_match
from rag.usecase.cards import candidate_card
from rag.usecase.interface import LanguageModel

SYSTEM_PROMPT = (
    "Ты эксперт по каталогу КТРУ для госзакупок. Тебе дают описание товара от поставщика "
    "и кандидатов из КТРУ, найденных векторным поиском. Оцени, насколько каждый кандидат "
    "подходит под описание: тот же ли это товар по назначению, а не просто похожие слова. "
    "Учитывай название, ОКПД2 и характеристики. Не выдумывай кандидатов, используй только их id."
)

SCHEMA = {
    "type": "object",
    "properties": {
        "exact_match_id": {"type": ["integer", "null"]},
        "exact_match_reason": {"type": "string"},
        "ranking": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "relevance": {"type": "integer", "minimum": 0, "maximum": 100},
                    "reason": {"type": "string"},
                },
                "required": ["id", "relevance", "reason"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["ranking", "exact_match_id", "exact_match_reason"],
    "additionalProperties": False,
}


def build_prompt(description: str, hits: list[Hit]) -> str:
    cards = "\n\n".join(candidate_card(n, h) for n, h in enumerate(hits))
    return (
        f"Описание товара от поставщика:\n{description}\n\n"
        f"Кандидаты КТРУ:\n\n{cards}\n\n"
        "Верни всех кандидатов, отсортированных от самого подходящего к наименее подходящему. "
        "relevance — 0..100, reason — одно короткое предложение; у неподходящего кандидата "
        "reason объясняет, чем он отличается от описания. "
        "exact_match_id укажи только при полном однозначном совпадении группы с описанием: "
        "назначение и все заявленные свойства подходят, relevance=100, нет другой столь же "
        "подходящей группы и не нужно додумывать различающий признак. Иначе null. "
        "Не выбирай просто лучшего среди неточных совпадений. В exact_match_reason кратко "
        "объясни совпадение для пользователя, либо причину необходимости выбора."
    )


class Reranker:
    def __init__(self, llm: LanguageModel) -> None:
        self._llm = llm

    async def run(self, description: str, hits: list[Hit]) -> Reranking:
        if not hits:
            return Reranking([])
        completion = await self._llm.complete(
            StructuredRequest(
                SYSTEM_PROMPT,
                build_prompt(description, hits),
                SCHEMA,
                Tier.SMART,
                Effort.LOW,
            )
        )
        out = completion.output
        ranked = []
        seen = set()
        for item in out["ranking"]:
            i = item["id"]
            if 0 <= i < len(hits) and i not in seen:
                seen.add(i)
                ranked.append(Ranked(hits[i], item["relevance"], item["reason"]))
        ranked.sort(key=lambda item: item.relevance, reverse=True)
        code = exact_match(ranked, hits, out.get("exact_match_id"))
        return Reranking(
            ranked,
            code,
            out.get("exact_match_reason") if code else None,
            completion.usage,
        )
