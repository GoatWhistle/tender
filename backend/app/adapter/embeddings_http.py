"""Эмбеддинги по OpenAI-совместимому HTTP API (`POST /v1/embeddings`) — реализация порта
`Embeddings`. Модель — `Qwen/Qwen3-Embedding-0.6B` за отдельным сервисом; адрес и ключ — в
`.env` (`EMBEDDINGS_URL`, `EMBEDDINGS_API_KEY`, `EMBEDDINGS_MODEL`).

Запросу адаптер добавляет инструкцию Qwen, документу — нет. Векторы нормирует адаптер: так
требует порт, а сервис может отдавать их ненормированными. Без адреса точка сборки берёт
`UnconfiguredEmbeddings` — заглушкой модель не подменяется.
"""

import json
import math
import urllib.request
from collections.abc import Sequence
from typing import Any

from app.domain.errors import ModelNotConfigured
from app.domain.inference import EmbeddingBatch, ModelHealth, Vector

QWEN_QUERY_TASK = "Given a product description, retrieve the matching product group"
BATCH = 64
TIMEOUT = 60.0


def qwen_query(text: str, task: str = QWEN_QUERY_TASK) -> str:
    return f"Instruct: {task}\nQuery: {text}"


class HttpEmbeddings:
    """`url` — адрес сервиса без пути (`http://host:8089`); `instruct = False` — запрос без
    инструкции, для замера."""

    def __init__(
        self, url: str, model: str, api_key: str | None = None, *, instruct: bool = True
    ) -> None:
        self._url = url.rstrip("/")
        self._model = model
        self._api_key = api_key
        self._instruct = instruct
        self._dimension: int | None = None

    @property
    def dimension(self) -> int:
        """Размерность — по первому ответу сервиса; до него — пробный запрос."""
        if self._dimension is None:
            self.embed_documents(["размерность"])
        assert self._dimension is not None
        return self._dimension

    def embed_queries(self, texts: Sequence[str]) -> EmbeddingBatch:
        return self._embed([qwen_query(t) for t in texts] if self._instruct else list(texts))

    def embed_documents(self, texts: Sequence[str]) -> EmbeddingBatch:
        return self._embed(list(texts))

    def health(self) -> ModelHealth:
        body = self._request("GET", "/v1/models")
        served = [m.get("id") for m in body.get("data", [])]
        ready = self._model in served
        detail = "" if ready else f"сервис отдаёт {served}, нужна {self._model}"
        return ModelHealth(model=self._model, revision=self._model, ready=ready, detail=detail)

    def _embed(self, texts: list[str]) -> EmbeddingBatch:
        vectors: list[Vector] = []
        revision = self._model
        for start in range(0, len(texts), BATCH):
            chunk = texts[start : start + BATCH]
            body = self._request("POST", "/v1/embeddings", {"model": self._model, "input": chunk})
            rows = sorted(body["data"], key=lambda d: d["index"])
            vectors.extend(_unit([float(x) for x in row["embedding"]]) for row in rows)
            revision = body.get("model") or revision
        if vectors and self._dimension is None:
            self._dimension = len(vectors[0])
        return EmbeddingBatch(vectors=tuple(vectors), revision=revision)

    def _request(self, method: str, path: str, payload: object = None) -> dict[str, Any]:
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        data = None if payload is None else json.dumps(payload).encode()
        request = urllib.request.Request(self._url + path, data, headers, method=method)
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            body: dict[str, Any] = json.load(response)
        return body


def _unit(vector: list[float]) -> Vector:
    norm = math.sqrt(sum(x * x for x in vector))
    if not math.isfinite(norm) or norm == 0:
        raise ValueError(f"вектор нормы {norm} не нормировать")
    return tuple(x / norm for x in vector)


class UnconfiguredEmbeddings:
    """Модель эмбеддингов без адреса: каждый вызов — `ModelNotConfigured`, здоровье — не готова."""

    model = "embeddings"
    reason = "Модель эмбеддингов не настроена: задайте EMBEDDINGS_URL"

    @property
    def dimension(self) -> int:
        raise ModelNotConfigured(self.reason)

    def embed_queries(self, texts: Sequence[str]) -> EmbeddingBatch:
        raise ModelNotConfigured(self.reason)

    def embed_documents(self, texts: Sequence[str]) -> EmbeddingBatch:
        raise ModelNotConfigured(self.reason)

    def health(self) -> ModelHealth:
        return ModelHealth(model=self.model, revision="", ready=False, detail="модель не настроена")
