import json
from typing import Any

import httpx
import pytest

from app.adapter.embeddings import OpenAIEmbeddings
from app.domain.errors import ModelFailure
from composition import checked_embeddings


def test_embedding_adapter_instructs_only_queries_and_orders_normalized_vectors() -> None:
    requests: list[dict[str, Any]] = []

    def respond(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        requests.append(body)
        return httpx.Response(
            200,
            json={"data": [{"index": 1, "embedding": [0, 5]}, {"index": 0, "embedding": [3, 4]}]},
        )

    adapter = checked_embeddings(
        OpenAIEmbeddings(
            "http://model/v1", model="test", dimension=2, transport=httpx.MockTransport(respond)
        )
    )
    assert adapter.embed_queries(["Стол", "Топор"]).vectors == ((0.6, 0.8), (0.0, 1.0))
    assert adapter.embed_documents(["Стол", "Топор"]).vectors == ((0.6, 0.8), (0.0, 1.0))
    assert requests[0]["input"][0] == (
        "Instruct: Given a product description, retrieve the matching product group\nQuery: Стол"
    )
    assert requests[1]["input"] == ["Стол", "Топор"]


@pytest.mark.parametrize(
    "data", [[], [{"index": 0, "embedding": [0, 0]}], [{"index": 1, "embedding": [1, 0]}]]
)
def test_bad_embedding_response_is_technical_failure(data: list[dict[str, Any]]) -> None:
    adapter = checked_embeddings(
        OpenAIEmbeddings(
            "http://model/v1",
            model="test",
            dimension=2,
            transport=httpx.MockTransport(lambda _: httpx.Response(200, json={"data": data})),
        )
    )
    with pytest.raises(ModelFailure):
        adapter.embed_queries(["a"])
