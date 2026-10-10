import tempfile
from dataclasses import dataclass

from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query

from rag.clarify import FIXED, Question
from rag.ktru import value_text
from rag.models import Position
from rag.search import Index

KINDS = {"1": "неизменяемая", "2": "выбор одного значения", "3": "выбор нескольких значений"}

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

VALIDATE_SCHEMA = {
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


@dataclass(frozen=True, slots=True)
class Extra:
    name: str
    value: str
    reason: str


@dataclass(frozen=True, slots=True)
class Verdict:
    ok: bool
    problems: list[str]
    warnings: list[str]
    fixed: Extra | None
    result: ResultMessage


def changeable(p: Position) -> list[Question]:
    out = []
    for c in p.characteristics:
        if c.kind == FIXED:
            continue
        options = tuple(dict.fromkeys(t for t in (value_text(v) for v in c.values) if t))
        out.append(Question(c.name, c.required, options, multiple=c.kind == "3"))
    out.sort(key=lambda q: not q.required)
    return out


def no_new_features(index: Index, p: Position) -> bool:
    return index.raw[p.code]["data"].get("noNewFeatures") == "true"


def card(p: Position, chosen: dict[str, tuple[str, ...]], extras: list[Extra]) -> str:
    lines = [f"Позиция КТРУ: {p.code} {p.name}", f"ОКПД2: {p.okpd2} {p.okpd2_name}", "Характеристики КТРУ:"]
    for c in p.characteristics:
        values = "; ".join(t for t in (value_text(v) for v in c.values) if t)
        picked = chosen.get(c.name)
        now = f"; выбрано: {'; '.join(picked)}" if picked else ""
        lines.append(f"- {c.name} ({KINDS.get(c.kind, c.kind)}): {values}{now}")
    if not p.characteristics:
        lines.append("- нет")
    if extras:
        lines.append("Уже добавлены заказчиком:")
        lines.extend(f"- {e.name}: {e.value} (обоснование: {e.reason})" for e in extras)
    return "\n".join(lines)


async def validate(
    p: Position,
    chosen: dict[str, tuple[str, ...]],
    extras: list[Extra],
    new: Extra,
    model: str = "sonnet",
) -> Verdict:
    prompt = (
        f"{card(p, chosen, extras)}\n\nНовая характеристика:\n"
        f"Название: {new.name}\nЗначение: {new.value}\nОбоснование: {new.reason or 'не указано'}"
    )
    result: ResultMessage | None = None
    with tempfile.TemporaryDirectory(prefix="rag-agent-") as cwd:
        options = ClaudeAgentOptions(
            model=model,
            effort="low",
            system_prompt=SYSTEM_PROMPT,
            setting_sources=[],
            tools=[],
            cwd=cwd,
            output_format={"type": "json_schema", "schema": VALIDATE_SCHEMA},
        )
        async for message in query(prompt=prompt, options=options):
            if isinstance(message, ResultMessage):
                result = message
    if result is None:
        raise RuntimeError("нет ResultMessage")
    if result.is_error or result.structured_output is None:
        raise RuntimeError(result.errors or result.result)
    out = result.structured_output
    fixed = None
    ok = out["ok"] and not out["problems"]
    if not ok and out["fixed_name"].strip() and out["fixed_value"].strip():
        fixed = Extra(out["fixed_name"].strip(), out["fixed_value"].strip(), new.reason)
    return Verdict(ok, list(out["problems"]), list(out["warnings"]), fixed, result)
