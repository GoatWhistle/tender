"""Проверка русского LLM-корректора через существующий strict JSON API."""

import argparse
import hashlib
import json
import math
import re
import statistics
import time
from datetime import UTC, datetime
from http.client import RemoteDisconnected
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, Request, build_opener

SYSTEM = """Проверь только орфографию и опечатки в русском описании товара.
Исправляй только явно неправильно написанные обычные слова. Не перефразируй текст,
не меняй регистр, пунктуацию и пробелы вне исправляемого слова. Не добавляй сведений.
Сохраняй числа, единицы измерения, размеры, бренды, артикулы и сокращения дословно.
Не исправляй неправдоподобные характеристики: это другая задача.
Написание е вместо ё допустимо и не требует исправления.
Если ошибок нет, corrected_text должен дословно совпадать с исходным текстом,
а errors должен быть пустым списком. Иначе верни минимальные замены ошибочных слов
в errors: original — точный фрагмент исходного текста, replacement — исправление.
corrected_text должен получаться только применением перечисленных замен.
Верни только JSON по заданной схеме, без объяснений."""

SCHEMA = {
    "type": "object",
    "properties": {
        "corrected_text": {"type": "string"},
        "errors": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "original": {"type": "string"},
                    "replacement": {"type": "string"},
                },
                "required": ["original", "replacement"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["corrected_text", "errors"],
    "additionalProperties": False,
}


def protected_tokens(text):
    return re.findall(
        r"\d+(?:[.,]\d+)?|[A-Za-z][A-Za-z0-9-]*|\b(?:мм|см|Вт|В|кг|литров|метров|ЛДСП)\b",
        text,
    )


def assess(case, response):
    expected = case["text"]
    for error in case["errors"]:
        expected = expected.replace(error["wrong"], error["correct"])
    row = {**case, "expected_text": expected, "response": response}
    row.update(
        {
            "schema_valid": False,
            "contract_consistent": False,
            "detected": False,
            "exact_text_correct": False,
            "gold_replacements_exact": False,
            "protected_unchanged": False,
            "corrected_text": None,
            "predicted_errors": None,
        }
    )
    try:
        choice = response["choices"][0]
        if choice["finish_reason"] != "stop":
            raise ValueError(f"Незавершённая генерация: {choice['finish_reason']}")
        value = json.loads(choice["message"]["content"])
        if not isinstance(value, dict) or set(value) != {"corrected_text", "errors"}:
            raise ValueError("Неверные поля JSON")
        corrected, errors = value["corrected_text"], value["errors"]
        if not isinstance(corrected, str) or not isinstance(errors, list):
            raise TypeError("Неверные типы JSON")
        for error in errors:
            if (
                not isinstance(error, dict)
                or set(error) != {"original", "replacement"}
                or not all(isinstance(x, str) for x in error.values())
            ):
                raise ValueError("Неверная схема замены")
        row["schema_valid"] = True
        row["corrected_text"] = corrected
        row["predicted_errors"] = errors
        row["detected"] = bool(errors)
        applied = case["text"]
        consistent = True
        for error in errors:
            original, replacement = error["original"], error["replacement"]
            if not original or original == replacement or original not in applied:
                consistent = False
                break
            applied = applied.replace(original, replacement, 1)
        row["contract_consistent"] = consistent and applied == corrected
        row["exact_text_correct"] = corrected == expected
        expected_replacements = sorted(
            (e["wrong"], e["correct"]) for e in case["errors"]
        )
        actual_replacements = sorted((e["original"], e["replacement"]) for e in errors)
        row["gold_replacements_exact"] = actual_replacements == expected_replacements
        row["protected_unchanged"] = protected_tokens(corrected) == protected_tokens(
            case["text"]
        )
        row["error"] = None
    except (KeyError, IndexError, TypeError, ValueError) as error:
        row["error"] = str(error)
    return row


def summarize(rows):
    positive = [r for r in rows if r["gold"] == "typo"]
    clean = [r for r in rows if r["gold"] == "clean"]
    tp = sum(r["schema_valid"] and r["detected"] for r in positive)
    fp = sum(r["schema_valid"] and r["detected"] for r in clean)
    times = sorted(r["http_ms"] for r in rows)
    return {
        "cases": len(rows),
        "typo_cases": len(positive),
        "clean_cases": len(clean),
        "schema_valid": sum(r["schema_valid"] for r in rows),
        "contract_consistent": sum(r["contract_consistent"] for r in rows),
        "typos_detected": tp,
        "typos_missed_or_failed": len(positive) - tp,
        "detection_recall": tp / len(positive),
        "false_alarms": fp,
        "typo_texts_corrected_exactly": sum(r["exact_text_correct"] for r in positive),
        "typo_texts_unchanged": sum(r["corrected_text"] == r["text"] for r in positive),
        "typo_texts_changed_without_error_list": sum(
            r["schema_valid"] and r["corrected_text"] != r["text"] and not r["detected"]
            for r in positive
        ),
        "typo_texts_changed_incorrectly": sum(
            r["schema_valid"]
            and r["corrected_text"] != r["text"]
            and not r["exact_text_correct"]
            for r in positive
        ),
        "typo_replacements_match_gold": sum(
            r["gold_replacements_exact"] for r in positive
        ),
        "clean_texts_unchanged": sum(r["exact_text_correct"] for r in clean),
        "clean_texts_accepted_unchanged": sum(
            r["exact_text_correct"] and not r["detected"] for r in clean
        ),
        "all_texts_exact": sum(r["exact_text_correct"] for r in rows),
        "protected_tokens_unchanged": sum(r["protected_unchanged"] for r in rows),
        "http_p50_ms": statistics.median(times),
        "http_p95_ms": times[math.ceil(0.95 * len(times)) - 1],
    }


def markdown(report, dataset):
    m = report["metrics"]
    lines = [
        "# Qwen: русские опечатки, валидация и минимальное исправление",
        "",
        f"Прогон: {report['started_at']}. Модель API: `{report['model']}`.",
        f"Readiness: `{json.dumps(report['health'], ensure_ascii=False)}`.",
        f"Датасет: `{dataset}`; SHA256 `{report['dataset_sha256']}`.",
        "",
        (
            "Те же 40 синтетических development-примеров, что в проверке OpenJev: 20 с ошибкой "
            "и 20 без. Каждый текст сразу отправлен в LLM. Разметка и ожидаемое исправление "
            "не передаются модели. Вопрос и JSON Schema закреплены до прогона. "
            "Русский system prompt требует минимальных исправлений и дословного сохранения "
            "корректного текста, чисел, единиц, брендов и артикулов; е вместо ё допускается."
        ),
        "",
        "## Результат",
        "",
        (
            "Обнаружением считается непустой список `errors`. Исправление текста измеряется "
            "отдельно: LLM может изменить текст, но забыть заполнить список ошибок."
        ),
        "",
        "| Метрика | Результат |",
        "| --- | ---: |",
        f"| Обнаружено ошибок | {m['typos_detected']}/{m['typo_cases']} ({m['detection_recall']:.1%}) |",
        f"| Текст с ошибкой исправлен точно по разметке | {m['typo_texts_corrected_exactly']}/{m['typo_cases']} |",
        f"| Ошибка осталась без изменения | {m['typo_texts_unchanged']}/{m['typo_cases']} |",
        f"| Текст с ошибкой изменён неверно | {m['typo_texts_changed_incorrectly']}/{m['typo_cases']} |",
        f"| Текст изменён, но список ошибок пуст | {m['typo_texts_changed_without_error_list']}/{m['typo_cases']} |",
        f"| Замены совпали с разметкой | {m['typo_replacements_match_gold']}/{m['typo_cases']} |",
        f"| Корректный текст остался дословно неизменным | {m['clean_texts_unchanged']}/{m['clean_cases']} |",
        f"| Корректный текст неизменен и список ошибок пуст | {m['clean_texts_accepted_unchanged']}/{m['clean_cases']} |",
        f"| Ложных тревог | {m['false_alarms']}/{m['clean_cases']} |",
        f"| JSON валиден | {m['schema_valid']}/{m['cases']} |",
        f"| Текст совпадает с применением заявленных замен | {m['contract_consistent']}/{m['cases']} |",
        f"| Защищённые числовые/латинские токены и единицы сохранены | {m['protected_tokens_unchanged']}/{m['cases']} |",
        f"| Все итоговые тексты точно соответствуют разметке | {m['all_texts_exact']}/{m['cases']} |",
        f"| HTTP p50 / p95 | {m['http_p50_ms']:.1f} / {m['http_p95_ms']:.1f} мс |",
        "",
        "## Все примеры",
        "",
        "| ID | Вход | Ожидаемое исправление | Ответ LLM | Список замен | Точно |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in report["rows"]:
        value = (
            row["corrected_text"]
            if row["corrected_text"] is not None
            else row.get("error", "Ошибка")
        )
        edits = json.dumps(row["predicted_errors"], ensure_ascii=False)
        mark = "✓" if row["exact_text_correct"] else "✗"
        cells = [row["id"], row["text"], row["expected_text"], value, edits, mark]
        lines.append(
            "| "
            + " | ".join(c.replace("|", "\\|").replace("\n", " ") for c in cells)
            + " |"
        )
    lines += [
        "",
        "## Границы и воспроизведение",
        "",
        (
            "Это небольшой синтетический набор: результат не гарантирует такое же качество "
            "на реальных данных. Локализация засчитывается только при точном совпадении замен "
            "с ручной разметкой. HTTP-время включает SSH и сеть, один прогрев исключён из "
            "статистики. Проверка защищённых токенов — текстовое сравнение, не полный "
            "семантический валидатор. Полные исходные ответы и usage сохранены в JSON."
        ),
        (
            f"Во время прогона было {len(report.get('transport_failures', []))} сбоев доступа к API. "
            "Эти запросы повторены после readiness; сбои сохранены отдельно в `transport_failures`. "
            "Ошибки самих ответов модели не перепроверялись и не исключались из метрик."
        ),
        "",
        "```bash",
        (
            "python3 evals/server/bench_llm_typos_api.py --url http://127.0.0.1:18084 "
            "--dataset evals/datasets/typo_detection_ru_v0.json --out var/llm-typos-api.json"
        ),
        "```",
        "",
    ]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--model", default="qwen-extractor")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    opener = build_opener(ProxyHandler({}))

    def request(path, payload=None):
        data = (
            None
            if payload is None
            else json.dumps(payload, ensure_ascii=False).encode()
        )
        req = Request(
            args.url.rstrip("/") + path,
            data=data,
            headers={"Content-Type": "application/json"},
        )
        started = time.perf_counter()
        with opener.open(req, timeout=125) as response:
            result = json.load(response)
        return result, (time.perf_counter() - started) * 1000

    config = {
        "model": args.model,
        "temperature": 0,
        "max_tokens": 512,
        "stream": False,
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "typo_validation",
                "strict": True,
                "schema": SCHEMA,
            },
        },
    }

    def correct(text):
        return request(
            "/v1/chat/completions",
            {
                **config,
                "messages": [
                    {"role": "system", "content": SYSTEM},
                    {
                        "role": "user",
                        "content": json.dumps({"text": text}, ensure_ascii=False),
                    },
                ],
            },
        )

    dataset_bytes = args.dataset.read_bytes()
    cases = json.loads(dataset_bytes)["cases"]
    assert len({c["id"] for c in cases}) == len(cases)
    report = {
        "kind": "synthetic_development_llm_typo_correction",
        "started_at": datetime.now(UTC).isoformat(),
        "model": args.model,
        "dataset_sha256": hashlib.sha256(dataset_bytes).hexdigest(),
        "health": request("/health/ready")[0],
        "system_prompt": SYSTEM,
        "request_config": config,
        "rows": [],
    }
    if args.resume:
        prior = json.loads(args.out.read_text())
        assert prior["dataset_sha256"] == report["dataset_sha256"]
        assert prior["request_config"] == config and prior["system_prompt"] == SYSTEM
        assert prior["health"]["revision"] == report["health"]["revision"]
        prior.setdefault("resumes", []).append(
            {
                "at": report["started_at"],
                "health": report["health"],
            }
        )
        failed = [
            r
            for r in prior["rows"]
            if r.get(
                "transport_failed",
                not r["response"] and r.get("error", "").startswith("HTTP 503"),
            )
        ]
        prior.setdefault("transport_failures", []).extend(failed)
        failed_ids = {r["id"] for r in failed}
        prior["rows"] = [r for r in prior["rows"] if r["id"] not in failed_ids]
        report = prior
    warmup_response, warmup_ms = correct("Стол деревянный.")
    report.setdefault("warmup_response", warmup_response)
    report.setdefault("warmup_http_ms", warmup_ms)
    warmup = assess(
        {"text": "Стол деревянный.", "errors": [], "gold": "clean"},
        warmup_response,
    )
    assert warmup["schema_valid"], warmup["error"]
    args.out.parent.mkdir(parents=True, exist_ok=True)

    def save():
        args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")

    save()
    done = {r["id"] for r in report["rows"]}
    for case in cases:
        if case["id"] in done:
            continue
        start = time.perf_counter()
        try:
            response, elapsed = correct(case["text"])
            row = assess(case, response)
        except (HTTPError, URLError, RemoteDisconnected, OSError) as error:
            elapsed = (time.perf_counter() - start) * 1000
            row = assess(case, {})
            row["error"] = (
                f"HTTP {error.code}: {error.read().decode()[:2000]}"
                if isinstance(error, HTTPError)
                else str(error)
            )
            row["transport_failed"] = not isinstance(
                error, HTTPError
            ) or error.code in {429, 503, 504}
        row["http_ms"] = elapsed
        report["rows"].append(row)
        save()
        if len(report["rows"]) % 5 == 0:
            print(
                f"{len(report['rows'])}/{len(cases)}: exact={sum(r['exact_text_correct'] for r in report['rows'])}",
                flush=True,
            )
    report["metrics"] = summarize(report["rows"])
    report["health_after"] = request("/health/ready")[0]
    report["finished_at"] = datetime.now(UTC).isoformat()
    save()
    args.out.with_suffix(".md").write_text(markdown(report, args.dataset.as_posix()))
    print(json.dumps(report["metrics"], ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
