"""OpenAI-совместимый сервис эмбеддингов: инструкция только запросам, нормализация векторов."""

import math
from collections.abc import Iterator, Sequence
from contextlib import contextmanager

import httpx

from app.domain.inference import EmbeddingBatch, ModelHealth, Vector

QWEN_INSTRUCTION = "Given a product description, retrieve the matching product group"
QWEN_REVISION = "97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3"


class OpenAIEmbeddings:
    def __init__(
        self,
        url: str,
        *,
        model: str,
        api_key: str | None = None,
        dimension: int = 1024,
        revision: str = QWEN_REVISION,
        query_instruction: str = QWEN_INSTRUCTION,
        batch_size: int = 32,
        timeout: float = 120,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        if dimension < 1 or batch_size < 1:
            raise ValueError("Размерность и размер пакета должны быть положительными")
        self._url = url.rstrip("/")
        self._model = model
        self._headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self._dimension = dimension
        self._revision = revision
        self._instruction = query_instruction
        self._batch_size = batch_size
        self._http = httpx.Client(timeout=timeout, transport=transport, trust_env=False)

    @contextmanager
    def _client(self) -> Iterator[httpx.Client]:
        # Один клиент на адаптер: создание httpx.Client — десятки миллисекунд (SSL-контекст),
        # а соединение с сервисом модели переиспользуется между вызовами. Клиент потокобезопасен.
        yield self._http

    @property
    def dimension(self) -> int:
        return self._dimension

    def embed_queries(self, texts: Sequence[str]) -> EmbeddingBatch:
        queries = [
            f"Instruct: {self._instruction}\nQuery: {text}" if self._instruction else text
            for text in texts
        ]
        return self._embed(queries)

    def embed_documents(self, texts: Sequence[str]) -> EmbeddingBatch:
        return self._embed(texts)

    def _embed(self, texts: Sequence[str]) -> EmbeddingBatch:
        vectors: list[Vector] = []
        with self._client() as client:
            for start in range(0, len(texts), self._batch_size):
                batch = list(texts[start : start + self._batch_size])
                response = client.post(
                    f"{self._url}/embeddings",
                    headers=self._headers,
                    json={"model": self._model, "input": batch, "encoding_format": "float"},
                )
                response.raise_for_status()
                rows = sorted(response.json()["data"], key=lambda r: r["index"])
                if [r["index"] for r in rows] != list(range(len(batch))):
                    raise ValueError("Неверные индексы в ответе сервиса эмбеддингов")
                for row in rows:
                    vector = tuple(float(x) for x in row["embedding"])
                    norm = math.sqrt(sum(x * x for x in vector))
                    if norm == 0 or not math.isfinite(norm):
                        raise ValueError("Невалидный вектор сервиса эмбеддингов")
                    vectors.append(tuple(x / norm for x in vector))
        return EmbeddingBatch(tuple(vectors), self._revision)

    def health(self) -> ModelHealth:
        with self._client() as client:
            response = client.get(f"{self._url}/models", headers=self._headers, timeout=10)
            response.raise_for_status()
            ready = any(row["id"] == self._model for row in response.json()["data"])
        return ModelHealth(self._model, self._revision, ready)
