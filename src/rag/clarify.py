import tempfile
from collections import Counter
from dataclasses import dataclass

from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query

from rag.ktru import value_text
from rag.models import Characteristic, Position

FIXED = "1"

SYSTEM_PROMPT = (
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
    "нельзя; если он просит то, чего нет среди характеристик, так и скажи."
)


@dataclass(frozen=True, slots=True)
class Question:
    name: str
    required: bool
    options: tuple[str, ...]
    counts: tuple[int, ...] = ()
    multiple: bool = False


async def structured(
    prompt: str, system_prompt: str, schema: dict, model: str = "haiku"
) -> dict:
    result: ResultMessage | None = None
    with tempfile.TemporaryDirectory(prefix="rag-agent-") as cwd:
        options = ClaudeAgentOptions(
            model=model,
            system_prompt=system_prompt,
            setting_sources=[],
            tools=[],
            cwd=cwd,
            output_format={"type": "json_schema", "schema": schema},
        )
        async for message in query(prompt=prompt, options=options):
            if isinstance(message, ResultMessage):
                result = message
    if result is None:
        raise RuntimeError("нет ResultMessage")
    if result.is_error or result.structured_output is None:
        raise RuntimeError(result.errors or result.result)
    return result.structured_output


def _fixed(p: Position) -> dict[str, Characteristic]:
    return {c.name: c for c in p.characteristics if c.kind == FIXED}


def _options(p: Position) -> dict[str, frozenset[str]]:
    values = {name: _labels(c) for name, c in _fixed(p).items()}
    if p.units:
        values["Единица поставки"] = frozenset(p.units)
    return values


def _labels(c: Characteristic) -> frozenset[str]:
    return frozenset(t for t in (value_text(v) for v in c.values) if t)


def questions(leaves: list[Position], answers: dict[str, str | None]) -> list[Question]:
    per_leaf = [_options(p) for p in leaves]
    required = {n for p in leaves for n, c in _fixed(p).items() if c.required} | {
        "Единица поставки"
    }
    out = []
    for name in sorted({n for chars in per_leaf for n in chars} - answers.keys()):
        if len({chars.get(name) for chars in per_leaf}) < 2:
            continue
        counts = Counter(label for chars in per_leaf for label in chars.get(name, ()))
        options = sorted(counts)
        out.append(
            Question(
                name,
                name in required,
                tuple(options),
                tuple(counts[o] for o in options),
            )
        )
    out.sort(
        key=lambda q: (
            q.name != "Единица поставки",
            not q.required,
            max(q.counts, default=0),
            q.name,
        )
    )
    return out


def narrow(leaves: list[Position], answers: dict[str, str | None]) -> list[Position]:
    def fits(p: Position) -> bool:
        chars = _options(p)
        return all(
            label is None or name not in chars or label in chars[name]
            for name, label in answers.items()
        )

    return [p for p in leaves if fits(p)]


def build_prompt(text: str, qs: list[Question]) -> str:
    blocks = []
    for i, q in enumerate(qs):
        options = "\n".join(f"  {j}. {o}" for j, o in enumerate(q.options))
        many = " (можно несколько)" if q.multiple else ""
        blocks.append(f"[{i}] {q.name}{many}\n{options}")
    return f"Текст поставщика:\n{text}\n\nХарактеристики:\n\n" + "\n\n".join(blocks)


async def extract(
    text: str, qs: list[Question], model: str = "haiku"
) -> dict[str, tuple[str, ...]]:
    if not qs:
        return {}
    out = {}
    found = await structured(
        build_prompt(text, qs), SYSTEM_PROMPT, EXTRACT_SCHEMA, model
    )
    for item in found["answers"]:
        i = item["id"]
        if not 0 <= i < len(qs):
            continue
        q = qs[i]
        picked = tuple(
            dict.fromkeys(
                q.options[j] for j in item["options"] if 0 <= j < len(q.options)
            )
        )
        if picked and (q.multiple or len(picked) == 1):
            out[q.name] = picked
    return out


async def answer(
    reply: str, qs: list[Question], model: str = "haiku"
) -> tuple[dict[str, tuple[str, ...]], str]:
    properties: dict = {
        f"c{n}": {
            "type": "array",
            "description": q.name,
            "items": {"type": "string", "enum": list(q.options)},
            **({} if q.multiple else {"maxItems": 1}),
        }
        for n, q in enumerate(qs, 1)
    }
    properties["comment"] = {"type": "string"}
    schema = {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }
    blocks = []
    for n, q in enumerate(qs, 1):
        options = "\n".join(f"  {j}. {o}" for j, o in enumerate(q.options, 1))
        many = "можно несколько" if q.multiple else "ровно один"
        blocks.append(f"c{n}: {q.name} ({many})\n{options}")
    prompt = "Характеристики:\n\n" + "\n\n".join(blocks) + f"\n\nОтвет:\n{reply}"
    out = await structured(prompt, ANSWER_PROMPT, schema, model)
    picked = {}
    for n, q in enumerate(qs, 1):
        got = tuple(dict.fromkeys(c for c in out.get(f"c{n}", []) if c in q.options))
        if got and (q.multiple or len(got) == 1):
            picked[q.name] = got
    return picked, out["comment"]
