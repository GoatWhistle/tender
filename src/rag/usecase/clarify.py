from dataclasses import dataclass

from rag.domain.clarify import Picked, Question, accept
from rag.domain.inference import StructuredRequest, Tier
from rag.usecase.interface import LanguageModel

EXTRACT_PROMPT = (
    "Ты помогаешь определить точную позицию КТРУ по ответам поставщика. Тебе дают текст "
    "поставщика и характеристики с пронумерованными вариантами значений. Для каждой "
    "характеристики выбери вариант, который однозначно следует из текста. Для числовых "
    "диапазонов выбери диапазон, в который попадает указанное значение, с учётом единиц "
    "измерения. У характеристик с пометкой «можно несколько» перечисли все упомянутые "
    "варианты, у остальных — ровно один. Если текст не позволяет выбрать вариант однозначно, "
    "характеристику не включай. Не додумывай значения, которых нет в тексте. "
    "Текст содержит хронологию уточнений: последнее явное исправление заменяет старое. "
    "Учитывай отрицания; просьба удалить значение отменяет его извлечение."
)

EXTRACT_SCHEMA = {
    "type": "object",
    "properties": {
        "answers": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "options": {"type": "array", "items": {"type": "integer"}},
                },
                "required": ["id", "options"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["answers"],
    "additionalProperties": False,
}

ANSWER_PROMPT = (
    "Ты помогаешь описать товар по КТРУ. Человеку показали характеристики товара с вариантами "
    "значений, он ответил свободным текстом. Пойми, какие варианты он имеет в виду: синонимы, "
    "разговорные формы, падежи и опечатки сопоставляй с вариантами по смыслу, числа — с "
    "диапазоном, в который они попадают, с учётом единиц. «Хочу эргономичный» у характеристики "
    "«Эргономичный» с вариантами Да/Нет — это «Да». Если он называет номер варианта, варианты "
    "нумеруются с 1. Характеристики, о которых в ответе ничего нет, оставь пустым массивом; "
    "если ответ противоречит вариантам или человек не знает — тоже пустым. В comment — одно "
    "короткое предложение, обращённое к человеку на «вы»: что выбрано или почему выбрать "
    "нельзя; если он просит то, чего нет среди характеристик, так и скажи. В полях n — точное "
    "число, если человек его назвал, в единицах характеристики (3 кВт при единице «Ватт» — "
    "3000); иначе null."
)


@dataclass(frozen=True, slots=True)
class Answer:
    picked: Picked
    numbers: dict[str, float]
    comment: str


def extract_prompt(text: str, qs: list[Question]) -> str:
    blocks = []
    for i, q in enumerate(qs):
        options = "\n".join(f"  {j}. {o}" for j, o in enumerate(q.options))
        many = " (можно несколько)" if q.multiple else ""
        blocks.append(f"[{i}] {q.name}{many}\n{options}")
    return f"Текст поставщика:\n{text}\n\nХарактеристики:\n\n" + "\n\n".join(blocks)


def answer_schema(qs: list[Question]) -> dict:
    properties: dict = {
        f"c{n}": {
            "type": "array",
            "description": q.name,
            "items": {"type": "string", "enum": list(q.options)},
            **({} if q.multiple else {"maxItems": 1}),
        }
        for n, q in enumerate(qs, 1)
    }
    properties |= {
        f"n{n}": {"type": ["number", "null"], "description": q.name}
        for n, q in enumerate(qs, 1)
        if q.exact
    }
    properties["comment"] = {"type": "string"}
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


def answer_prompt(reply: str, qs: list[Question]) -> str:
    blocks = []
    for n, q in enumerate(qs, 1):
        options = "\n".join(f"  {j}. {o}" for j, o in enumerate(q.options, 1))
        many = "можно несколько" if q.multiple else "ровно один"
        if q.exact:
            many += f"; точное число — n{n}, единица: {q.unit or 'нет'}"
        blocks.append(f"c{n}: {q.name} ({many})\n{options}")
    return "Характеристики:\n\n" + "\n\n".join(blocks) + f"\n\nОтвет:\n{reply}"


class CharacteristicReader:
    def __init__(self, llm: LanguageModel) -> None:
        self._llm = llm

    async def extract(self, text: str, qs: list[Question]) -> Picked:
        if not qs:
            return {}
        completion = await self._llm.complete(
            StructuredRequest(
                EXTRACT_PROMPT, extract_prompt(text, qs), EXTRACT_SCHEMA, Tier.FAST
            )
        )
        out: Picked = {}
        for item in completion.output["answers"]:
            i = item["id"]
            if not 0 <= i < len(qs):
                continue
            q = qs[i]
            values = [q.options[j] for j in item["options"] if 0 <= j < len(q.options)]
            if picked := accept(q, values):
                out[q.name] = picked
        return out

    async def answer(self, reply: str, qs: list[Question]) -> Answer:
        completion = await self._llm.complete(
            StructuredRequest(
                ANSWER_PROMPT, answer_prompt(reply, qs), answer_schema(qs), Tier.FAST
            )
        )
        out = completion.output
        picked = {
            q.name: got
            for n, q in enumerate(qs, 1)
            if (got := accept(q, out.get(f"c{n}", [])))
        }
        numbers = {
            q.name: float(x)
            for n, q in enumerate(qs, 1)
            if q.exact and isinstance(x := out.get(f"n{n}"), int | float)
        }
        return Answer(picked, numbers, out["comment"])
