"""Wire-контракт существующего GPU-сервиса за публичным DecisionBackend."""

import json

import httpx

from app.adapter.decision import OpenJevDecision
from app.domain.inference import ChoiceOption, ChoiceQuestion, Claim, Verdict
from composition import checked_decision


def test_openjev_maps_choice_and_batched_nli() -> None:
    requests: list[str] = []

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(request.url.path)
        body = json.loads(request.content)
        if request.url.path == "/v1/choice":
            assert body["premise"] == "стальная"
            assert body["options"] == [
                {"id": "s", "criterion": "Сталь"},
                {"id": "u", "criterion": "не указано"},
            ]
            return httpx.Response(
                200,
                json={
                    "choice": "s",
                    "probabilities": {"s": 0.99, "u": 0.01},
                    "model_revision": "rev",
                },
            )
        assert body["hypotheses"] == ["Материал — сталь", "Материал — дерево"]
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "hypothesis": h,
                        "probabilities": {
                            "supported": 0.99,
                            "contradicted": 0.0,
                            "not_stated": 0.01,
                        },
                    }
                    for h in body["hypotheses"]
                ],
                "model_revision": "rev",
            },
        )

    model = checked_decision(
        OpenJevDecision("http://openjev", transport=httpx.MockTransport(handle))
    )
    choices = model.choose(
        "стальная",
        [
            ChoiceQuestion(
                "q1", "Материал?", (ChoiceOption("s", "Сталь"), ChoiceOption("u", "не указано"))
            )
        ],
    )
    assert choices.answers[0].selected == "s"
    assert choices.revision == "rev"
    claims = model.verify(
        "стальная", [Claim("c1", "Материал — сталь"), Claim("c2", "Материал — дерево")]
    )
    assert [a.claim_id for a in claims.answers] == ["c1", "c2"]
    assert claims.answers[0].probabilities[Verdict.supported] == 0.99
    assert requests == ["/v1/choice", "/v1/nli"]


def test_choice_preserves_absolute_support_separately_from_relative_scores() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choice": "yes",
                "probabilities": {"yes": 0.99, "no": 0.01},
                "support_probabilities": {"yes": 0.0099, "no": 0.0001},
                "model_revision": "rev",
            },
        )

    model = checked_decision(
        OpenJevDecision("http://openjev", transport=httpx.MockTransport(handle))
    )
    batch = model.choose(
        "стол",
        [
            ChoiceQuestion(
                "group", "Подходит?", (ChoiceOption("yes", "Да"), ChoiceOption("no", "Нет"))
            )
        ],
    )
    assert batch.answers[0].probabilities["yes"] == 0.99
    assert batch.answers[0].support_scores == {"yes": 0.0099, "no": 0.0001}
