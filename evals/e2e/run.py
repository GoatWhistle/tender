"""Сквозной замер: набор разработки и holdout реальных СТЕ через HTTP API продукта.

Временная база: миграции → справочник КТРУ → векторы групп → приложение `main.create_app`.
Каждый кейс проходит как у поставщика: `POST /api/v1/sessions`, затем сообщения по одному в
`…/messages`; отдельно — `POST /api/v1/search` по склеенному тексту для R@K. Метрики —
`metrics.py`; отчёт — Markdown и JSON с датой, стендом и абсолютными числами.

Запуск (нужен сервис эмбеддингов, см. docs/search.md):

    cd backend && uv run python ../evals/e2e/run.py --embeddings-url http://127.0.0.1:8001/v1

`--stub-embeddings` — проверка самого прогона без модели: числа поиска не о качестве, отчёт
помечен «заглушка». Классы ошибок и число вопросов до кода считаются, когда продукт начнёт их
отдавать (#17, #15); до этого — «пропущено».
"""

import argparse
import datetime
import json
import pathlib
import platform
import sys
import time
from decimal import Decimal
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT))

from alembic import command
from alembic.config import Config
from app.adapter.stub.embeddings import StubEmbeddings
from app.domain.units import UNITS
from app.usecase.interface import Embeddings
from build_search_db import save_vectors
from fastapi.testclient import TestClient
from main import configured_embeddings, create_app, sync_catalog
from settings import BACKEND_DIR, Settings

from evals.e2e import metrics
from evals.e2e.dataset import HOLDOUT, load_dev, load_holdout, text_of
from evals.errors.score import ERROR_KINDS, score

SKIPPED = "пропущено"


def ok(response: Any) -> Any:
    if response.is_error:
        raise RuntimeError(
            f"{response.request.url} → {response.status_code}: {response.text[:500]}"
        )
    return response.json()


def fact_key(name: str, value: Any, unit: str | None) -> list[str]:
    """Общая нормализация факта: текст — без регистра и `ё`, число — в базовой единице."""
    if isinstance(value, list):
        value = "–".join(str(v) for v in value)
    if isinstance(value, str):
        try:
            number = Decimal(value)
        except ArithmeticError:
            return [name.lower(), value.lower().replace("ё", "е")]
    else:
        number = Decimal(str(value))
    known = UNITS.get(unit or "")
    if known is not None:
        return [
            name.lower(),
            f"{known.dimension}:{(number * known.factor).normalize()}",
        ]
    return [name.lower(), f"{unit or ''}:{number.normalize()}"]


def prepare(settings: Settings, embeddings: Embeddings) -> None:
    config = Config(BACKEND_DIR / "alembic.ini")
    config.attributes["database_url"] = settings.database_url
    config.attributes["configure_logger"] = False
    command.upgrade(config, "head")
    sync_catalog(settings)
    save_vectors(settings, embeddings)


def session(client: TestClient, messages: list[str]) -> dict[str, Any]:
    state: dict[str, Any] = ok(client.post("/api/v1/sessions"))
    for text in messages:
        state = ok(
            client.post(
                f"/api/v1/sessions/{state['session_id']}/messages", json={"text": text}
            )
        )
    return state


def search(client: TestClient, text: str) -> list[str]:
    found = ok(client.post("/api/v1/search", json={"description": text, "limit": 10}))
    return [g["code"] for g in found["groups"]]


def row(
    base: dict[str, Any], state: dict[str, Any], found: list[str]
) -> dict[str, Any]:
    return {
        **base,
        "search": found,
        "status": state["status"],
        "group": (state.get("path") or {}).get("group", {}).get("code"),
        "compatible": [c["code"] for c in state["candidates"] if not c["excluded"]],
        "facts": [
            fact_key(f["characteristic_name"], f["value"], f["unit_code"])
            for f in state["facts"]
            if f["status"] == "accepted_from_text" and f["characteristic_name"]
        ],
        "errors": state["errors"],
        "next_question": state["next_question"],
    }


def run(client: TestClient) -> list[dict[str, Any]]:
    rows = []
    for case in load_dev()["cases"]:
        text = text_of(case)
        rows.append(
            row(
                {
                    "id": case["id"],
                    "set": "dev",
                    "category": case["category"],
                    "tags": case["tags"],
                    "text": text,
                    "gold_groups": case["groups"],
                    "gold_codes": case["codes"],
                    "gold_facts": [
                        fact_key(f["characteristic"], f["value"], f.get("unit"))
                        for f in case["facts"]
                    ],
                    "gold_errors": case["errors"],
                },
                session(client, case["messages"]),
                search(client, text),
            )
        )
    for h in load_holdout():
        rows.append(
            row(
                {
                    "id": h.ste_id,
                    "set": "holdout",
                    "category": h.category,
                    "tags": [],
                    "text": h.name,
                    "gold_groups": h.groups,
                    "gold_codes": [],
                    "gold_facts": [],
                    "gold_errors": [],
                },
                session(client, [h.name]),
                search(client, h.name),
            )
        )
    return rows


def diagnostics(rows: list[dict[str, Any]]) -> Any:
    """Классы ошибок — через `evals/errors/score.py`, когда сессия отдаёт диагностики (#17)."""
    if not any("kind" in e for r in rows for e in r["errors"]):
        return SKIPPED
    dev = [r for r in rows if r["set"] == "dev"]
    dataset = {
        "cases": [
            {"id": r["id"], "text": r["text"], "expected": r["gold_errors"]}
            for r in dev
        ]
    }
    predictions = [
        {
            "id": r["id"],
            "errors": [e for e in r["errors"] if e.get("kind") in ERROR_KINDS],
            "normalizations": [e for e in r["errors"] if e.get("kind") == "synonym"],
        }
        for r in dev
    ]
    return score(dataset, predictions)


def fmt(m: Any) -> str:
    if not isinstance(m, dict) or "n" not in m:
        return str(m)
    share = "—" if m["share"] is None else f"{m['share']:.0%}"
    return f"{m['n']}/{m['of']} ({share})"


def markdown(report: dict[str, Any]) -> str:
    s = report["summary"]
    dev, holdout = s["dev"], s["holdout"]
    lines = [
        f"# Сквозной замер: набор разработки и holdout СТЕ — {report['date']}",
        "",
        f"Стенд: {report['stand']}.",
        f"Эмбеддинги: `{report['embeddings']}`.",
        (
            f"Наборы: `dev_v1.json` ({dev['cases']} кейсов), "
            f"`{HOLDOUT.name}` ({holdout['cases']} строк); разметка проверена человеком: "
            f"{report['checked']['dev']}/{dev['cases']} кейсов, "
            f"{report['checked']['holdout']}/{holdout['cases']} строк holdout."
        ),
        "",
    ]
    if report["stub"]:
        lines += [
            "**Заглушка эмбеддингов: числа поиска не о качестве, это проверка прогона.**",
            "",
        ]
    if (
        report["checked"]["dev"] < dev["cases"]
        or report["checked"]["holdout"] < holdout["cases"]
    ):
        lines += [
            "**Разметка проверена человеком не полностью — числа предварительные.**",
            "",
        ]
    lines += [
        "| Метрика | Набор разработки | Holdout СТЕ |",
        "|---|---:|---:|",
    ]
    for k in metrics.KS:
        lines.append(
            f"| R@{k} групп | {fmt(dev['recall'][f'R@{k}'])} | {fmt(holdout['recall'][f'R@{k}'])} |"
        )
    lines += [
        f"| «Вне КТРУ» распознано | {fmt(dev['out_of_scope'])} | {fmt(holdout['out_of_scope'])} |",
        f"| Точность выданного кода | {fmt(dev['codes']['accuracy'])} | — |",
        f"| Доля выданных кодов | {fmt(dev['codes']['coverage'])} | — |",
        f"| Правильный код не исключён | {fmt(dev['gold_kept'])} | — |",
        f"| Неоднозначность сохранена | {fmt(dev['ambiguity'])} | — |",
        f"| Факты: точность | {fmt(dev['facts']['precision'])} | — |",
        f"| Факты: полнота | {fmt(dev['facts']['recall'])} | — |",
        f"| Ошибки по классам | {report['diagnostics'] if isinstance(report['diagnostics'], str) else 'см. JSON'} | — |",
        f"| Вопросов до кода | {report['questions']} | — |",
        "",
        "Статусы сессий:",
        f"набор разработки — {dev['statuses']}; holdout — {holdout['statuses']}.",
        "",
        "## По тегам набора разработки",
        "",
        "| Тег | Кейсов | R@1 | Правильный код не исключён |",
        "|---|---:|---:|---:|",
    ]
    for tag, m in dev["by_tag"].items():
        lines.append(
            f"| {tag} | {m['cases']} | {fmt(m['R@1'])} | {fmt(m['gold_kept'])} |"
        )
    lines += [
        "",
        "Пустой знаменатель — «—». «Пропущено» — продукт ещё не отдаёт эти данные.",
        f"Время прогона: {report['seconds']:.0f} с. Построчные результаты — JSON рядом.",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    model = parser.add_mutually_exclusive_group(required=True)
    model.add_argument(
        "--embeddings-url", help="Базовый URL сервиса эмбеддингов, заканчивающийся /v1"
    )
    model.add_argument(
        "--stub-embeddings", action="store_true", help="Заглушка: проверка прогона"
    )
    parser.add_argument("--stand", default=f"{platform.node()}, {platform.system()}")
    parser.add_argument(
        "--database", type=pathlib.Path, default=ROOT / "var" / "e2e-eval.db"
    )
    parser.add_argument("--out", type=pathlib.Path, default=ROOT / "evals" / "reports")
    args = parser.parse_args()

    args.database.parent.mkdir(parents=True, exist_ok=True)
    args.database.unlink(missing_ok=True)
    settings = Settings(database_url=f"sqlite:///{args.database.resolve()}")
    if args.embeddings_url:
        settings = settings.model_copy(update={"embeddings_url": args.embeddings_url})
        embeddings = configured_embeddings(settings)
        assert embeddings is not None
    else:
        stub = StubEmbeddings()
        # Сохранённые векторы сверяются с моделью и ревизией из настроек.
        settings = settings.model_copy(
            update={
                "embeddings_model": stub.model,
                "embeddings_revision": stub.revision,
                "embeddings_dimension": stub.dimension,
            }
        )
        embeddings = stub

    start = time.perf_counter()
    prepare(settings, embeddings)
    with TestClient(create_app(settings, embeddings=embeddings)) as client:
        health = embeddings.health()
        rows = run(client)
    dev = load_dev()["cases"]
    date = datetime.date.today().isoformat()
    report = {
        "date": date,
        "stand": args.stand,
        "stub": bool(args.stub_embeddings),
        "embeddings": f"{health.model} {health.revision}",
        "checked": {
            "dev": sum(c["checked"] for c in dev),
            "holdout": sum(h.checked for h in load_holdout()),
        },
        "seconds": time.perf_counter() - start,
        "summary": metrics.summarize(rows),
        "diagnostics": diagnostics(rows),
        "questions": SKIPPED
        if not any(r["next_question"] for r in rows)
        else "см. #15",
        "rows": rows,
    }
    name = f"{date}-e2e{'-stub' if args.stub_embeddings else ''}"
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / f"{name}.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=1, default=str) + "\n",
        encoding="utf-8",
    )
    (args.out / f"{name}.md").write_text(markdown(report), encoding="utf-8")
    print(markdown(report))


if __name__ == "__main__":
    main()
