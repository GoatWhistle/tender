"""Быстрый development-бенчмарк обнаружения опечаток через готовый HTTP API."""

import argparse
import hashlib
import json
import math
import statistics
import time
from datetime import UTC, datetime
from pathlib import Path
from urllib.request import ProxyHandler, Request, build_opener

VARIANTS = [
    {
        "id": "ru_short",
        "instructions": "Есть ли в тексте описания товара орфографическая ошибка или опечатка?",
        "options": [
            {
                "id": "typo",
                "criterion": "В тексте есть хотя бы одна орфографическая ошибка или опечатка.",
            },
            {
                "id": "clean",
                "criterion": "В тексте нет орфографических ошибок и опечаток.",
            },
        ],
    },
    {
        "id": "ru_explicit",
        "instructions": "Проверь написание обычных русских слов в описании товара. Опечатка — пропуск, лишняя буква, перестановка букв или неверное написание слова. Бренды, артикулы, сокращения, единицы измерения и допустимое е вместо ё не считай ошибками. Не оценивай правдоподобность характеристик товара.",
        "options": [
            {
                "id": "typo",
                "criterion": "Хотя бы одно обычное русское слово написано с орфографической ошибкой или опечаткой.",
            },
            {
                "id": "clean",
                "criterion": "Обычные русские слова написаны правильно; орфографических ошибок и опечаток нет.",
            },
        ],
    },
]


def routing(rows):
    positives = sum(r["gold"] == "typo" for r in rows)
    results = []
    for threshold in [0.5, 0.4, 0.3, 0.2, 0.1, 0.05]:
        selected = [
            r for r in rows if r["response"]["probabilities"]["typo"] >= threshold
        ]
        caught = sum(r["gold"] == "typo" for r in selected)
        results.append(
            {
                "threshold": threshold,
                "typos_caught": caught,
                "typos_total": positives,
                "typos_missed": positives - caught,
                "recall": caught / positives if positives else 0.0,
                "llm_calls": len(selected),
                "total_texts": len(rows),
                "llm_call_fraction": len(selected) / len(rows),
                "false_alarms": len(selected) - caught,
            }
        )
    return results


def metrics(rows):
    tp = sum(r["gold"] == "typo" and r["prediction"] == "typo" for r in rows)
    tn = sum(r["gold"] == "clean" and r["prediction"] == "clean" for r in rows)
    fp = sum(r["gold"] == "clean" and r["prediction"] == "typo" for r in rows)
    fn = sum(r["gold"] == "typo" and r["prediction"] == "clean" for r in rows)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    pairs = {}
    for row in rows:
        if row["pair_id"]:
            pairs.setdefault(row["pair_id"], []).append(row)
    times = sorted(r["http_ms"] for r in rows)
    return {
        "count": len(rows),
        "correct": tp + tn,
        "accuracy": (tp + tn) / len(rows),
        "tp": tp,
        "tn": tn,
        "fp": fp,
        "fn": fn,
        "precision": precision,
        "recall": recall,
        "f1": 2 * precision * recall / (precision + recall)
        if precision + recall
        else 0.0,
        "false_positive_rate": fp / (fp + tn) if fp + tn else 0.0,
        "pairs_both_correct": sum(all(r["correct"] for r in p) for p in pairs.values()),
        "pair_count": len(pairs),
        "http_p50_ms": statistics.median(times),
        "http_p95_ms": times[math.ceil(0.95 * len(times)) - 1],
    }


def markdown(report, dataset_path):
    runs = [run for run in report["runs"] if run["variant"]["id"].startswith("ru_")]
    lines = [
        "# OpenJev 4B: обнаружение опечаток через API",
        "",
        f"Прогон: {report['started_at']}. Ревизия модели: `{report['health']['model_revision']}`.",
        f"Датасет: `{dataset_path}`; SHA256 `{report['dataset_sha256']}`.",
        "",
        (
            "40 вручную размеченных синтетических development-примеров: 20 с опечаткой и 20 без. "
            "16 пар отличаются только написанием слова; ещё 4 ошибки и 4 сложных корректных "
            "примера с брендами, артикулами, сокращениями, единицами и неправдоподобным числом. "
            "Допускается е вместо ё. Пунктуация, стиль и фактическая корректность не оцениваются."
        ),
        "",
        (
            "Формулировки закреплены до прогона. Модель получает только исходный текст, вопрос "
            "и две категории; правильные ответы, ошибочные слова и исправления ей не передаются. "
            "Использован `/v1/choice`, `use_cache:false`, один последовательный клиент и один "
            "прогрев на формулировку. HTTP-время включает SSH-туннель и сеть; это не локальная "
            "GPU-латентность. Вероятности выбора не откалиброваны."
        ),
        "",
        "## Отправка на проверку в LLM: приоритет полноты",
        "",
        (
            "Учитываются только русские вопросы. Основной критерий — не пропускать опечатки; "
            "ложная тревога означает дополнительный вызов LLM. Правило маршрутизации: "
            "передать текст в LLM, если `probabilities.typo >= threshold`. Это анализ сохранённых "
            "ответов API, без повторного inference и без изменения работающего сервиса."
        ),
        "",
        "| Вопрос | Порог | Найдено ошибок | Пропущено | Recall | Вызовов LLM | Ложных тревог |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for run in runs:
        for m in routing(run["rows"]):
            lines.append(
                f"| {run['variant']['id']} | {m['threshold']:.2f} "
                f"| {m['typos_caught']}/{m['typos_total']} | {m['typos_missed']} "
                f"| {m['recall']:.0%} | {m['llm_calls']}/{m['total_texts']} "
                f"({m['llm_call_fraction']:.0%}) | {m['false_alarms']} |"
            )
    short_run = next(run for run in runs if run["variant"]["id"] == "ru_short")
    short_thresholds = {m["threshold"]: m for m in routing(short_run["rows"])}
    low, middle = short_thresholds[0.3], short_thresholds[0.4]
    lines += [
        "",
        (
            f"Короткий русский вопрос при пороге 0.30 нашёл "
            f"{low['typos_caught']}/{low['typos_total']} опечаток этого набора "
            f"и отправляет в LLM {low['llm_calls']}/{low['total_texts']} текстов. "
            f"При пороге 0.40 — {middle['typos_caught']}/{middle['typos_total']} "
            f"и {middle['llm_calls']}/{middle['total_texts']}. "
            "Пороги рассмотрены после получения ответов на том же development-наборе: "
            "это не гарантия такой же полноты на новых текстах."
        ),
        "",
        "## Исходная классификация при выборе максимального score",
        "",
        (
            "Положительный класс — наличие опечатки. TP — найденная ошибка, FN — пропущенная, "
            "FP — ложная тревога на корректном тексте, TN — правильно принятый корректный текст."
        ),
        "",
        "| Вопрос | Верно | Precision | Recall | F1 | TP / TN / FP / FN | Обе стороны пары | HTTP p50 / p95, мс |",
        "| --- | ---: | ---: | ---: | ---: | --- | ---: | ---: |",
    ]
    for run in runs:
        m = run["metrics"]
        lines.append(
            f"| {run['variant']['id']} | {m['correct']}/{m['count']} ({m['accuracy']:.1%}) "
            f"| {m['precision']:.1%} | {m['recall']:.1%} | {m['f1']:.3f} "
            f"| {m['tp']} / {m['tn']} / {m['fp']} / {m['fn']} "
            f"| {m['pairs_both_correct']}/{m['pair_count']} "
            f"| {m['http_p50_ms']:.1f} / {m['http_p95_ms']:.1f} |"
        )
    lines += [
        "",
        "## Все примеры и ответы",
        "",
        (
            "`typo` — ошибка есть; `clean` — ошибка отсутствует. Для пар сохраняется исходный "
            "смысл, поэтому одновременная правильность обеих сторон показывает различение написания."
        ),
        "",
        "| ID | Текст | Разметка / исправление | ru_short | ru_explicit |",
        "| --- | --- | --- | --- | --- |",
    ]
    by_variant = {
        run["variant"]["id"]: {r["id"]: r for r in run["rows"]} for run in runs
    }
    for row in runs[0]["rows"]:
        annotation = row["gold"]
        if row["errors"]:
            annotation += ": " + "; ".join(
                f"{e['wrong']} → {e['correct']}" for e in row["errors"]
            )
        predictions = []
        for variant in VARIANTS:
            prediction = by_variant[variant["id"]][row["id"]]
            mark = "✓" if prediction["correct"] else "✗"
            predictions.append(f"{prediction['prediction']} {mark}")
        lines.append(
            f"| {row['id']} | {row['text']} | {annotation} | "
            + " | ".join(predictions)
            + " |"
        )
    lines += [
        "",
        "## Границы результата",
        "",
        (
            "Это проверка бинарного обнаружения на небольшом наборе, а не подтверждение "
            "готового корректора. OpenJev выбирает класс и не генерирует исправленный текст. "
            "Исходные ошибки/исправления здесь — ручная разметка; локализация ошибки и качество "
            "автоматического исправления не измерены. Русские формулировки и пороги оценены "
            "на одном development-наборе; лучшая метрика не является независимой оценкой. "
            "LLM-корректор этим прогоном не вызывался."
        ),
        "",
        "## Воспроизведение",
        "",
        "```bash",
        (
            "python3 evals/server/bench_typos_api.py --url http://127.0.0.1:8080 "
            "--dataset evals/datasets/typo_detection_ru_v0.json "
            "--out var/openjev-typos-api.json"
        ),
        "```",
        "",
        (
            "Полные HTTP-ответы, вероятности, время каждого запроса и все формулировки сохранены "
            "в соседнем JSON. Готовность API повторно проверена после прогона."
        ),
        "",
    ]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    dataset_bytes = args.dataset.read_bytes()
    cases = json.loads(dataset_bytes)["cases"]
    assert len({c["id"] for c in cases}) == len(cases), "Повторяющиеся ID"
    assert all(c["gold"] in {"typo", "clean"} for c in cases), "Неверный gold"
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
        start = time.perf_counter()
        with opener.open(req, timeout=125) as response:
            body = json.load(response)
        return body, (time.perf_counter() - start) * 1000

    report = {
        "kind": "synthetic_development_typo_detection",
        "started_at": datetime.now(UTC).isoformat(),
        "dataset_sha256": hashlib.sha256(dataset_bytes).hexdigest(),
        "endpoint": "/v1/choice",
        "use_cache": False,
        "health": request("/health/ready")[0],
        "runs": [],
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)

    def save():
        args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")

    save()
    for variant in VARIANTS:

        def classify(text, variant=variant):
            return request(
                "/v1/choice",
                {
                    "premise": text,
                    "use_cache": False,
                    "instructions": variant["instructions"],
                    "options": variant["options"],
                },
            )

        warmup, warmup_ms = classify("Стол деревянный.")
        assert warmup["model_revision"] == report["health"]["model_revision"]
        rows = []
        run = {"variant": variant, "warmup_http_ms": warmup_ms, "rows": rows}
        report["runs"].append(run)
        for case in cases:
            response, elapsed = classify(case["text"])
            assert response["model_revision"] == report["health"]["model_revision"]
            assert response["choice"] in {"typo", "clean"}, response
            rows.append(
                {
                    **case,
                    "prediction": response["choice"],
                    "correct": response["choice"] == case["gold"],
                    "http_ms": elapsed,
                    "response": response,
                }
            )
            if len(rows) % 10 == 0:
                print(f"{variant['id']}: {len(rows)}/{len(cases)}", flush=True)
                save()
        run["metrics"] = metrics(rows)
        save()
        print(
            json.dumps(
                {"variant": variant["id"], **run["metrics"]}, ensure_ascii=False
            ),
            flush=True,
        )
    report["health_after"] = request("/health/ready")[0]
    report["finished_at"] = datetime.now(UTC).isoformat()
    save()
    args.out.with_suffix(".md").write_text(markdown(report, args.dataset.as_posix()))


if __name__ == "__main__":
    main()
