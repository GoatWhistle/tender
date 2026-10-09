"""Адаптер OpenAI-совместимых эмбеддингов против поддельного сервиса на 127.0.0.1: без внешней
сети и без модели. Сервис отвечает ненормированными векторами, как бывает у настоящих."""

import json
import math
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

import pytest

from app.adapter.embeddings_http import (
    BATCH,
    HttpEmbeddings,
    UnconfiguredEmbeddings,
    qwen_query,
)
from app.domain.errors import ModelFailure, ModelNotConfigured
from composition import checked_embeddings

MODEL = "Qwen/Qwen3-Embedding-0.6B"


class FakeService:
    def __init__(self) -> None:
        self.requests: list[tuple[str, dict[str, str], Any]] = []
        self.models = [MODEL]


@pytest.fixture
def service() -> Iterator[tuple[str, FakeService]]:
    fake = FakeService()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_: object) -> None:
            pass

        def _reply(self, body: object) -> None:
            data = json.dumps(body).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self) -> None:
            fake.requests.append((self.path, dict(self.headers), None))
            self._reply({"data": [{"id": m} for m in fake.models]})

        def do_POST(self) -> None:
            payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            fake.requests.append((self.path, dict(self.headers), payload))
            # Вектор текста — (длина, 1, 0): ненормированный; ответ — в обратном порядке индексов.
            rows = [
                {"index": i, "embedding": [len(t), 1.0, 0.0]}
                for i, t in enumerate(payload["input"])
            ]
            self._reply({"data": rows[::-1], "model": payload["model"]})

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}/", fake
    server.shutdown()
    server.server_close()


def test_queries_get_qwen_instruction_and_documents_do_not(
    service: tuple[str, FakeService],
) -> None:
    url, fake = service
    embeddings = checked_embeddings(HttpEmbeddings(url, MODEL, api_key="secret"))

    embeddings.embed_queries(["болгарка"])
    embeddings.embed_documents(["Шлифмашина"])

    (path, headers, query), (_, _, document) = fake.requests
    assert path == "/v1/embeddings"
    assert headers["Authorization"] == "Bearer secret"
    assert query == {"model": MODEL, "input": [qwen_query("болгарка")]}
    assert qwen_query("болгарка").endswith("\nQuery: болгарка")
    assert document == {"model": MODEL, "input": ["Шлифмашина"]}


def test_vectors_are_normalized_in_text_order_and_batched(
    service: tuple[str, FakeService],
) -> None:
    url, fake = service
    texts = ["a" * (i + 1) for i in range(BATCH + 1)]

    batch = checked_embeddings(HttpEmbeddings(url, MODEL)).embed_documents(texts)

    assert len(fake.requests) == 2
    assert batch.revision == MODEL
    for text, vector in zip(texts, batch.vectors, strict=True):
        n = len(text)
        assert vector == pytest.approx((n / math.hypot(n, 1), 1 / math.hypot(n, 1), 0.0))


def test_query_without_instruction_for_evals(service: tuple[str, FakeService]) -> None:
    url, fake = service

    HttpEmbeddings(url, MODEL, instruct=False).embed_queries(["болгарка"])

    assert fake.requests[0][2]["input"] == ["болгарка"]


def test_health_checks_served_model(service: tuple[str, FakeService]) -> None:
    url, fake = service
    embeddings = HttpEmbeddings(url, MODEL)

    assert embeddings.health().ready
    fake.models = ["other"]
    assert not embeddings.health().ready


def test_unreachable_service_is_model_failure() -> None:
    embeddings = checked_embeddings(HttpEmbeddings("http://127.0.0.1:9", MODEL))

    with pytest.raises(ModelFailure) as caught:
        embeddings.embed_queries(["стол"])
    assert caught.value.code == "technical_error"


def test_unconfigured_embeddings_say_so() -> None:
    embeddings = checked_embeddings(UnconfiguredEmbeddings())

    with pytest.raises(ModelNotConfigured) as caught:
        embeddings.embed_queries(["стол"])
    assert caught.value.code == "model_not_configured"
    health = embeddings.health()
    assert (health.ready, health.detail) == (False, "модель не настроена")
