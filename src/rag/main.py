import asyncio
import math
import os
import ssl
import sys
import tempfile
import time

import aiohttp
import truststore
from claude_agent_sdk import (
    ClaudeAgentOptions,
    ResultMessage,
    query,
)
from dotenv import load_dotenv

from rag.models import EmbeddingResponse


def cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return dot / norm if norm else 0.0


def cosine_distance(a: list[float], b: list[float]) -> float:
    return 1.0 - cosine_similarity(a, b)


load_dotenv()

URL = os.environ.get("EMBEDDINGS_URL", "https://api.polza.ai/api/v1")
MODEL = os.environ.get("EMBEDDINGS_MODEL", "qwen/qwen3-embedding-8b")
API_KEY = os.environ.get("EMBEDDINGS_API_KEY", "")
SSL_CONTEXT = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)


async def embed(session: aiohttp.ClientSession, texts: list[str]) -> EmbeddingResponse:
    headers = {"Authorization": f"Bearer {API_KEY}"} if API_KEY else {}
    async with session.post(
        f"{URL}/embeddings",
        json={"model": MODEL, "input": texts},
        headers=headers,
        ssl=SSL_CONTEXT,
    ) as resp:
        resp.raise_for_status()
        body = await resp.json()
    return EmbeddingResponse.from_dict(body)


async def main() -> None:
    texts = sys.argv[1:] or [
        "Стул офисный на колёсах, металлический каркас",
        "Савелий",
        "Иван",
        "Амир",
        "Андрей",
        "Азамат",
        "Лох",
    ]
    async with aiohttp.ClientSession() as session:
        resp = await embed(session, texts)
    print(f"model={resp.model} tokens={resp.usage.total_tokens}")
    for item in resp.data:
        vec = item.embedding
        print(
            f"{texts[item.index]!r}: dim={len(vec)} head={[round(x, 4) for x in vec[:5]]}",
            item.index,
            cosine_similarity(vec, resp.data[6].embedding),
        )


HELLO_SCHEMA = {
    "type": "object",
    "properties": {
        "reply": {"type": "string"},
        "language": {"type": "string"},
        "mood": {"type": "string"},
    },
    "required": ["reply", "language"],
    "additionalProperties": False,
}


async def hello():
    result: ResultMessage | None = None
    with tempfile.TemporaryDirectory(prefix="rag-agent-") as cwd:
        options = ClaudeAgentOptions(
            model="haiku",
            effort="medium",
            system_prompt="",
            setting_sources=[],
            tools=[],
            cwd=cwd,
            output_format={"type": "json_schema", "schema": HELLO_SCHEMA},
        )
        start = time.perf_counter()

        async for message in query(prompt="иди нахуй", options=options):
            if isinstance(message, ResultMessage):
                result = message

        if not isinstance(result, ResultMessage):
            return

        print("msg1:", time.perf_counter() - start, result.structured_output)
        print(
            f"sdk={result.duration_ms / 1000:.2f}s ",
            f"api={result.duration_api_ms / 1000:.2f}s turns={result.num_turns}",
        )

        start = time.perf_counter()

        async for message in query(
            prompt="иди нахуй!!!!!!! соси писос", options=options
        ):
            if isinstance(message, ResultMessage):
                result = message

        if not isinstance(result, ResultMessage):
            return

        print("msg2:", time.perf_counter() - start, result.structured_output)
        print(
            f"sdk={result.duration_ms / 1000:.2f}s ",
            f"api={result.duration_api_ms / 1000:.2f}s turns={result.num_turns}",
        )


def run() -> None:
    asyncio.run(main())


def run_hello() -> None:
    start = time.perf_counter()
    asyncio.run(hello())
    wall = time.perf_counter() - start
    print(f"wall={wall:.2f}s")


if __name__ == "__main__":
    run()
