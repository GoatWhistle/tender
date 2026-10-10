import asyncio
import json
import sys
import tempfile
import time
from dataclasses import asdict, dataclass

from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query

SYSTEM_PROMPT = (
    "Ты корректор описаний товаров для госзакупок. Тебе дают описание товара от поставщика. "
    "Исправь опечатки, ошибки раскладки, слитные и разорванные слова, неверные единицы "
    "измерения и явные логические ошибки (например, перепутанные размеры или единицы). "
    "Не добавляй новых фактов, не убирай характеристики, не меняй смысл и числа без явной "
    "причины. Каждую сделанную правку перечисли в fixes. В issues пиши только противоречия, "
    "которые ты НЕ исправил, потому что их нельзя исправить однозначно; исправленное в issues "
    "не повторяй. Если ошибок нет, верни текст без изменений, fixes и issues пустые."
)

PREPROCESS_SCHEMA = {
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


@dataclass(frozen=True, slots=True)
class Fix:
    before: str
    after: str
    kind: str


@dataclass(frozen=True, slots=True)
class Preprocessed:
    original: str
    corrected: str
    fixes: list[Fix]
    issues: list[str]
    result: ResultMessage


async def preprocess(text: str, model: str = "haiku") -> Preprocessed:
    result: ResultMessage | None = None
    with tempfile.TemporaryDirectory(prefix="rag-agent-") as cwd:
        options = ClaudeAgentOptions(
            model=model,
            system_prompt=SYSTEM_PROMPT,
            setting_sources=[],
            tools=[],
            cwd=cwd,
            output_format={"type": "json_schema", "schema": PREPROCESS_SCHEMA},
        )
        async for message in query(prompt=f"Описание товара:\n{text}", options=options):
            if isinstance(message, ResultMessage):
                result = message
    if result is None:
        raise RuntimeError("нет ResultMessage")
    if result.is_error or result.structured_output is None:
        raise RuntimeError(result.errors or result.result)
    out = result.structured_output
    return Preprocessed(
        original=text,
        corrected=out["corrected"].strip() or text,
        fixes=[Fix(**f) for f in out["fixes"]],
        issues=list(out["issues"]),
        result=result,
    )


def run() -> None:
    text = (
        " ".join(sys.argv[1:])
        or "стул офисный на колесиках, высота сидения 45 метров, обивка экокожка"
    )
    t0 = time.perf_counter()
    p = asyncio.run(preprocess(text))
    r = p.result
    print(
        f"{time.perf_counter() - t0:.1f}s sdk={r.duration_ms / 1000:.1f}s "
        f"turns={r.num_turns} cost=${r.total_cost_usd or 0:.4f}"
    )
    print(
        json.dumps(
            {
                "original": p.original,
                "corrected": p.corrected,
                "fixes": [asdict(f) for f in p.fixes],
                "issues": p.issues,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
