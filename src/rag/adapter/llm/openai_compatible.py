import json
import ssl
import time
from collections.abc import Mapping
from typing import Any

import aiohttp
import truststore

from rag.domain.errors import ModelFailure
from rag.domain.inference import Completion, StructuredRequest, Tier, Usage

SCHEMA_NAME = "answer"


class OpenAICompatibleModel:
    def __init__(
        self,
        url: str,
        models: Mapping[Tier, str],
        api_key: str | None = None,
        timeout: float = 180,
        reasoning: bool = False,
    ) -> None:
        self._url = url.rstrip("/")
        self._models = dict(models)
        self._headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self._timeout = aiohttp.ClientTimeout(total=timeout)
        self._reasoning = reasoning
        self._ssl = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)

    def _body(self, request: StructuredRequest) -> dict[str, Any]:
        body: dict[str, Any] = {
            "model": self._models[request.tier],
            "messages": [
                {"role": "system", "content": request.system},
                {"role": "user", "content": request.prompt},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": SCHEMA_NAME,
                    "schema": request.schema,
                    "strict": True,
                },
            },
        }
        if self._reasoning and request.effort:
            body["reasoning_effort"] = request.effort.value
        return body

    async def complete(self, request: StructuredRequest) -> Completion:
        start = time.perf_counter()
        try:
            async with (
                aiohttp.ClientSession(timeout=self._timeout) as session,
                session.post(
                    f"{self._url}/chat/completions",
                    json=self._body(request),
                    headers=self._headers,
                    ssl=self._ssl,
                ) as resp,
            ):
                resp.raise_for_status()
                body = await resp.json()
        except (TimeoutError, aiohttp.ClientError) as exc:
            raise ModelFailure(f"ошибка модели: {exc}") from exc
        try:
            choice = body["choices"][0]
            if choice.get("finish_reason") == "length":
                raise ModelFailure("ошибка модели: ответ обрезан по длине")
            output = json.loads(choice["message"]["content"])
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            raise ModelFailure(f"ошибка модели: невалидный ответ: {exc}") from exc
        if not isinstance(output, dict):
            raise ModelFailure("ошибка модели: ответ не JSON-объект")
        usage = body.get("usage") or {}
        return Completion(
            output=output,
            usage=Usage(
                model=body.get("model") or self._models[request.tier],
                duration_ms=int((time.perf_counter() - start) * 1000),
                input_tokens=usage.get("prompt_tokens"),
                output_tokens=usage.get("completion_tokens"),
                cost_usd=usage.get("cost"),
            ),
        )
