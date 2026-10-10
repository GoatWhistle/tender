import tempfile
from dataclasses import dataclass
from math import inf
from typing import Literal

from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query

from rag.clarify import FIXED, Question
from rag.ktru import contains, is_range, value_text
from rag.models import Characteristic, Position, Value
from rag.search import Index

SPREAD = 10

Doubt = Literal["large", "small", "negative"]

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


def _scale(c: Characteristic) -> dict[str, Value]:
    if not c.quantitative or not c.values or len({v.unit for v in c.values}) > 1:
        return {}
    if not all(is_range(v) for v in c.values):
        return {}
    labels = {value_text(v): v for v in c.values}
    return dict(
        sorted(
            labels.items(),
            key=lambda item: (
                -inf if item[1].min is None else item[1].min,
                inf if item[1].max is None else item[1].max,
            ),
        )
    )


def changeable(p: Position) -> list[Question]:
    out = []
    for c in p.characteristics:
        if c.kind == FIXED:
            continue
        multiple = c.kind == "3"
        if scale := _scale(c):
            out.append(
                Question(c.name, c.required, tuple(scale), multiple=multiple, ranges=tuple(scale.values()))
            )
            continue
        options = tuple(dict.fromkeys(t for t in (value_text(v) for v in c.values) if t))
        out.append(Question(c.name, c.required, options, multiple=multiple))
    out.sort(key=lambda q: not q.required)
    return out


def _width(v: Value) -> tuple[float, float, float]:
    low = -inf if v.min is None else v.min
    high = inf if v.max is None else v.max
    return high - low, -low, high


def doubt(q: Question, x: float) -> Doubt | None:
    edges = [e for v in q.ranges for e in (v.min, v.max) if e is not None]
    if not edges:
        return None
    if x < 0 <= min(edges):
        return "negative"
    if max(edges) > 0 and x > SPREAD * max(edges):
        return "large"
    if min(edges) > 0 and 0 < x < min(edges) / SPREAD:
        return "small"
    return None


def match(q: Question, x: float) -> str | None:
    hits = [(label, v) for label, v in zip(q.options, q.ranges) if contains(v, x)]
    if not hits:
        return None
    return min(hits, key=lambda hit: _width(hit[1]))[0]


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
