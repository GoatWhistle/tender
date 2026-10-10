import asyncio
import json
import sys
import tempfile
import time
from dataclasses import dataclass

from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query

from rag.ktru import value_text
from rag.preprocess import preprocess
from rag.search import Hit, Index, query_vector

MAX_CHARS = 12
MAX_VALUES = 8

SYSTEM_PROMPT = (
    "Ты эксперт по каталогу КТРУ для госзакупок. Тебе дают описание товара от поставщика "
    "и кандидатов из КТРУ, найденных векторным поиском. Оцени, насколько каждый кандидат "
    "подходит под описание: тот же ли это товар по назначению, а не просто похожие слова. "
    "Учитывай название, ОКПД2 и характеристики. Не выдумывай кандидатов, используй только их id."
)

RERANK_SCHEMA = {
    "type": "object",
    "properties": {
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
    "required": ["ranking"],
    "additionalProperties": False,
}


@dataclass(frozen=True, slots=True)
class Ranked:
    hit: Hit
    relevance: int
    reason: str


@dataclass(frozen=True, slots=True)
class RerankResult:
    ranked: list[Ranked]
    result: ResultMessage


def candidate_card(n: int, hit: Hit) -> str:
    p = hit.position
    lines = [
        f"[{n}] {p.name}",
        f"ОКПД2: {p.okpd2} {p.okpd2_name}",
        f"вариантов в группе: {hit.siblings}",
    ]
    for c in p.characteristics[:MAX_CHARS]:
        values = [t for t in (value_text(v) for v in c.values[:MAX_VALUES]) if t]
        more = " …" if len(c.values) > MAX_VALUES else ""
        lines.append(f"- {c.name}: {'; '.join(values)}{more}")
    if len(p.characteristics) > MAX_CHARS:
        lines.append(f"- … ещё {len(p.characteristics) - MAX_CHARS} характеристик")
    return "\n".join(lines)


def build_prompt(description: str, hits: list[Hit]) -> str:
    cards = "\n\n".join(candidate_card(n, h) for n, h in enumerate(hits))
    return (
        f"Описание товара от поставщика:\n{description}\n\n"
        f"Кандидаты КТРУ:\n\n{cards}\n\n"
        "Верни всех кандидатов, отсортированных от самого подходящего к наименее подходящему. "
        "relevance — 0..100, reason — одно короткое предложение."
    )


async def rerank(description: str, hits: list[Hit], model: str = "sonnet") -> RerankResult:
    result: ResultMessage | None = None
    with tempfile.TemporaryDirectory(prefix="rag-agent-") as cwd:
        options = ClaudeAgentOptions(
            model=model,
            effort="low",
            system_prompt=SYSTEM_PROMPT,
            setting_sources=[],
            tools=[],
            cwd=cwd,
            output_format={"type": "json_schema", "schema": RERANK_SCHEMA},
        )
        async for message in query(prompt=build_prompt(description, hits), options=options):
            if isinstance(message, ResultMessage):
                result = message
    if result is None:
        raise RuntimeError("нет ResultMessage")
    if result.is_error or result.structured_output is None:
        raise RuntimeError(result.errors or result.result)
    ranked = []
    seen = set()
    for item in result.structured_output["ranking"]:
        i = item["id"]
        if 0 <= i < len(hits) and i not in seen:
            seen.add(i)
            ranked.append(Ranked(hits[i], item["relevance"], item["reason"]))
    return RerankResult(ranked, result)


def run() -> None:
    raw_text = " ".join(sys.argv[1:]) or "стул офисный на колёсах"
    t0 = time.perf_counter()
    index = Index()
    t1 = time.perf_counter()
    pre = asyncio.run(preprocess(raw_text))
    text = pre.corrected
    tf = time.perf_counter()
    hits = index.search(asyncio.run(query_vector(text)))
    t2 = time.perf_counter()
    out = asyncio.run(rerank(text, hits))
    t3 = time.perf_counter()
    r = out.result
    cost = (r.total_cost_usd or 0) + (pre.result.total_cost_usd or 0)
    print(
        f"load={t1 - t0:.1f}s fix={tf - t1:.1f}s search={t2 - tf:.1f}s rerank={t3 - t2:.1f}s "
        f"cost=${cost:.4f}"
    )
    if pre.fixes:
        print(f"исправлено: {text}")
        for f in pre.fixes:
            print(f"  [{f.kind}] {f.before} → {f.after}")
    for issue in pre.issues:
        print(f"  ! {issue}")
    print()
    before = {id(h): n for n, h in enumerate(hits, 1)}
    for n, rk in enumerate(out.ranked, 1):
        p = rk.hit.position
        print(
            f"{n:2}. {rk.relevance:3} (было {before[id(rk.hit)]:2}, cos {rk.hit.score:.3f}) "
            f"{p.code} {p.name}"
        )
        print(f"     {rk.reason}")
    print(json.dumps({"prompt_chars": len(build_prompt(text, hits))}))
