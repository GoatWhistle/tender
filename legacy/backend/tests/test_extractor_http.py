"""Публичный HTTP-контракт strict Qwen без GPU и сети."""

import json

import httpx
import pytest

from app.adapter.extractor import QwenExtractor
from app.domain.errors import InvalidExtraction, ModelFailure
from app.domain.inference import ExtractionRequest, SourceMessage, TargetAttribute

REVISION = "c202236235762e1c871ad0ccb60c8ee5ba337b9a"


def test_strict_schema_pins_targets_and_preserves_source() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/health/ready":
            return httpx.Response(200, json={"status": "ready", "revision": REVISION})
        assert request.url.path == "/v1/chat/completions"
        body = json.loads(request.content)
        assert body["model"] == "qwen-extractor"
        spec = body["response_format"]["json_schema"]
        assert spec["strict"] is True
        item = spec["schema"]["properties"]["facts"]["items"]
        assert item["additionalProperties"] is False
        assert item["properties"]["attribute_ref"]["enum"] == ["Высота"]
        assert set(item["required"]) == set(item["properties"])
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {
                            "content": json.dumps(
                                {
                                    "facts": [
                                        {
                                            "attribute_ref": "Высота",
                                            "raw_value": "75",
                                            "raw_unit": "см",
                                            "source_quote": "75 см",
                                            "source_message_id": "m1",
                                            "negated": False,
                                            "uncertain": False,
                                            "subject_ref": None,
                                        }
                                    ]
                                }
                            )
                        },
                    }
                ]
            },
        )

    adapter = QwenExtractor("http://qwen", transport=httpx.MockTransport(handle))
    result = adapter.extract(
        ExtractionRequest(
            (SourceMessage("m1", "75 см"),), (), (TargetAttribute("Высота", "Высота"),)
        )
    )
    assert result.revision == REVISION
    assert result.facts[0].raw_value == "75"


@pytest.mark.parametrize(
    "content,finish",
    [
        ('{"facts":[]}', "length"),
        ('{"facts":[],"facts":[]}', "stop"),
        ('{"facts":[{"raw_value":3}]}', "stop"),
        ("broken", "stop"),
    ],
)
def test_malformed_completion_is_explicitly_retryable(content: str, finish: str) -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/health/ready":
            return httpx.Response(200, json={"status": "ready", "revision": REVISION})
        return httpx.Response(
            200, json={"choices": [{"finish_reason": finish, "message": {"content": content}}]}
        )

    adapter = QwenExtractor("http://qwen", transport=httpx.MockTransport(handle))
    with pytest.raises(InvalidExtraction):
        adapter.extract(
            ExtractionRequest(
                (SourceMessage("m1", "75 см"),), (), (TargetAttribute("Высота", "Высота"),)
            )
        )


def test_other_qwen_revision_is_not_used() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/health/ready"
        return httpx.Response(200, json={"status": "ready", "revision": "wrong"})

    adapter = QwenExtractor("http://qwen", transport=httpx.MockTransport(handle))
    with pytest.raises(ModelFailure):
        adapter.extract(
            ExtractionRequest(
                (SourceMessage("m1", "75 см"),), (), (TargetAttribute("Высота", "Высота"),)
            )
        )
