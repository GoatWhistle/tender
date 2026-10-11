import ssl
from collections.abc import Sequence
from typing import Any

import aiohttp
import numpy as np
import truststore

from rag.domain.errors import EmbeddingsFailure
from rag.domain.inference import Vector


class OpenAIEmbeddings:
    def __init__(
        self,
        url: str,
        model: str,
        api_key: str | None = None,
        query_instruction: str | None = None,
        timeout: float = 600,
    ) -> None:
        self._url = url.rstrip("/")
        self._model = model
        self._headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self._instruction = query_instruction
        self._timeout = aiohttp.ClientTimeout(total=timeout)
        self._ssl = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        self._session: aiohttp.ClientSession | None = None

    def _client(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=self._timeout)
        return self._session

    async def _embed(self, texts: Sequence[str]) -> list[Vector]:
        try:
            async with self._client().post(
                f"{self._url}/embeddings",
                json={"model": self._model, "input": list(texts)},
                headers=self._headers,
                ssl=self._ssl,
            ) as resp:
                resp.raise_for_status()
                body: dict[str, Any] = await resp.json()
        except (TimeoutError, aiohttp.ClientError) as exc:
            raise EmbeddingsFailure(f"сервис эмбеддингов недоступен: {exc}") from exc
        out: list[Vector] = [()] * len(texts)
        for item in body["data"]:
            v = np.asarray(item["embedding"], dtype=np.float32)
            out[item["index"]] = (v / np.linalg.norm(v)).tolist()
        return out

    async def embed_queries(self, texts: Sequence[str]) -> list[Vector]:
        if self._instruction:
            texts = [f"Instruct: {self._instruction}\nQuery: {t}" for t in texts]
        return await self._embed(texts)

    async def embed_documents(self, texts: Sequence[str]) -> list[Vector]:
        return await self._embed(texts)

    async def aclose(self) -> None:
        if self._session is not None:
            await self._session.close()
