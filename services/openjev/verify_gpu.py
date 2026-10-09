"""Проверка реального HTTP/GPU: качество, новые вопросы, кеш и лимиты."""

import argparse
import json
import time
import urllib.error
import urllib.request
from collections import defaultdict
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8080")
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    def request(path, body=None, method=None, expected=200):
        payload = None if body is None else json.dumps(body, ensure_ascii=False).encode()
        req = urllib.request.Request(
            args.url + path,
            data=payload,
            method=method,
            headers={"Content-Type": "application/json"},
        )
        start = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=180) as response:
                status, raw = response.status, response.read()
        except urllib.error.HTTPError as error:
            status, raw = error.code, error.read()
        assert status == expected, (path, status, expected, raw[:500])
        return (json.loads(raw) if raw else None), (time.perf_counter() - start) * 1000

    health, _ = request("/health/ready")
    assert health["device"] == "cuda" and health["dtype"] == "bfloat16", health
    groups = defaultdict(list)
    for case in json.loads(args.dataset.read_text())["cases"]:
        groups[case["premise"]].append(case)
    rows, replays = [], []
    for premise, cases in groups.items():
        hypotheses = [case["hypothesis"] for case in cases]
        full, full_ms = request(
            "/v1/nli",
            {
                "premise": premise,
                "hypotheses": hypotheses,
                "use_cache": False,
            },
        )
        prepared, prepare_ms = request("/v1/contexts", {"premise": premise})
        context_id = prepared["context"]["id"]
        cached, cached_ms = request(
            "/v1/nli",
            {
                "context_id": context_id,
                "hypotheses": hypotheses,
            },
        )
        assert cached["context"]["reused"] and cached["context"]["id"] == context_id
        for case, a, b in zip(cases, full["results"], cached["results"], strict=True):
            rows.append(
                {
                    "id": case["id"],
                    "gold": case["gold"],
                    "full_label": a["label"],
                    "cached_label": b["label"],
                    "full_probabilities": a["probabilities"],
                    "cached_probabilities": b["probabilities"],
                    "max_probability_delta": max(
                        abs(a["probabilities"][k] - b["probabilities"][k])
                        for k in a["probabilities"]
                    ),
                }
            )
        first = {"context_id": context_id, "hypotheses": [hypotheses[0]]}
        a, _ = request("/v1/nli", first)
        request("/v1/nli", {"context_id": context_id, "hypotheses": [hypotheses[1]]})
        repeated, _ = request("/v1/nli", first)
        assert a["results"] == repeated["results"], "Retained cache was mutated by a new question"
        replays.append(
            {
                "context_id": context_id,
                "A_B_A_equal": True,
                "full_http_ms": full_ms,
                "prepare_http_ms": prepare_ms,
                "cached_http_ms": cached_ms,
            }
        )
        request("/v1/contexts/" + context_id, method="DELETE", expected=204)
        request("/v1/nli", first, expected=404)

    premise = "Стол имеет деревянную столешницу. Каркас металлический. Ящиков нет."
    hypotheses = ["Столешница деревянная.", "У стола есть ящики.", "Высота стола 90 см."]
    first, _ = request("/v1/nli", {"premise": premise, "hypotheses": hypotheses})
    second, _ = request("/v1/nli", {"premise": premise, "hypotheses": ["Каркас металлический."]})
    assert second["context"]["reused"] and first["context"]["id"] == second["context"]["id"]
    assert [r["label"] for r in first["results"]] == ["supported", "contradicted", "not_stated"]
    assert second["results"][0]["label"] == "supported"
    choice, _ = request(
        "/v1/choice",
        {
            "context_id": first["context"]["id"],
            "instructions": "Из какого материала столешница?",
            "options": [
                {"id": "wood", "criterion": "Стекло"},
                {"id": "glass", "criterion": "Дерево"},
            ],
        },
    )
    assert choice["choice"] == "glass", "External IDs leaked into the choice rubric"
    changed, _ = request(
        "/v1/nli",
        {
            "premise": premise.replace("деревянную", "стеклянную"),
            "hypotheses": ["Столешница деревянная."],
        },
    )
    assert changed["context"]["id"] != first["context"]["id"]
    assert changed["results"][0]["label"] == "contradicted"
    for body, status in [
        ({"premise": premise, "hypotheses": ["Факт."] * 33}, 413),
        ({"premise": "слово " * 10000, "hypotheses": ["Факт."]}, 413),
        ({"premise": premise, "context_id": first["context"]["id"], "hypotheses": ["Факт."]}, 422),
    ]:
        request("/v1/nli", body, expected=status)
    ready_after, _ = request("/health/ready")
    summary = {
        "health": health,
        "health_after_errors": ready_after,
        "cases": len(rows),
        "contexts": len(groups),
        "full_correct": sum(r["full_label"] == r["gold"] for r in rows),
        "cached_correct": sum(r["cached_label"] == r["gold"] for r in rows),
        "label_changes": sum(r["full_label"] != r["cached_label"] for r in rows),
        "max_probability_delta": max(r["max_probability_delta"] for r in rows),
        "A_B_A_checks": len(replays),
        "auto_cache_reuse": True,
        "changed_state_new_context": True,
        "deleted_context_rejected": True,
        "external_ids_neutralized": True,
        "limit_errors_preserve_readiness": True,
        "rows": rows,
        "replays": replays,
    }
    assert summary["label_changes"] == 0, summary
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {k: v for k, v in summary.items() if k not in ("rows", "replays")}, ensure_ascii=False
        )
    )


if __name__ == "__main__":
    main()
