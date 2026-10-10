"""Реальный smoke eval через POST /api/v1/search; входной датасет не изменяется."""

import argparse
import hashlib
import json
import sqlite3
import sys
import time
from pathlib import Path
from typing import Any

BACKEND = Path(__file__).resolve().parents[2] / "backend"
sys.path.insert(0, str(BACKEND))

from alembic import command
from alembic.config import Config
from build_search_db import save_vectors
from fastapi.testclient import TestClient
from main import configured_embeddings, create_app, sync_catalog
from settings import Settings


def evaluate(
    settings: Settings, cases: list[dict[str, Any]], instruction: str
) -> dict[str, Any]:
    settings = settings.model_copy(update={"embeddings_query_instruction": instruction})
    embeddings = configured_embeddings(settings)
    assert embeddings is not None

    # Реальный сервис для запросов; попытка повторно векторизовать документы ломает прогон.
    class QueryOnly:
        query_calls = 0
        dimension = embeddings.dimension

        def embed_documents(self, texts):
            raise RuntimeError(
                "Готовая база не должна векторизовать документы при старте"
            )

        def embed_queries(self, texts):
            self.query_calls += 1
            return embeddings.embed_queries(texts)

        def health(self):
            return embeddings.health()

    query_only = QueryOnly()
    start = time.perf_counter()
    rows = []
    recalls = {str(k): 0 for k in (1, 5, 10)}
    with TestClient(create_app(settings, embeddings=query_only)) as client:
        groups = client.get("/api/v1/groups").json()
        index_seconds = time.perf_counter() - start
        for case in cases:
            start = time.perf_counter()
            response = client.post(
                "/api/v1/search", json={"description": case["text"], "limit": 10}
            )
            response.raise_for_status()
            result = response.json()
            names = [g["name"] for g in result["groups"]]
            hits = {
                str(k): any(name in case["gold"] for name in names[:k])
                for k in (1, 5, 10)
            }
            positive = case["gold"] != ["НЕТ"]
            if positive:
                for k in recalls:
                    recalls[k] += hits[k]
            rows.append(
                {
                    "text": case["text"],
                    "gold": case["gold"],
                    "positive": positive,
                    "hits": hits,
                    "result": result,
                    "query_ms": (time.perf_counter() - start) * 1000,
                }
            )
    return {
        "instruction": instruction,
        "recall_counts": recalls,
        "positive_cases": sum(row["positive"] for row in rows),
        "total_cases": len(rows),
        "product_groups": len(groups),
        "product_group_names": len({g["name"] for g in groups}),
        "index_seconds": index_seconds,
        "query_embedding_calls": query_only.query_calls,
        "document_embedding_calls": 0,
        "cases": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset", type=Path, default=BACKEND.parent / "evals/datasets/smoke_v0.json"
    )
    parser.add_argument("--ktru-dir", type=Path)
    parser.add_argument(
        "--embeddings-url", required=True, help="Базовый URL, заканчивающийся /v1"
    )
    parser.add_argument("--model", default="qwen-embedding")
    parser.add_argument(
        "--output",
        type=Path,
        default=BACKEND.parent / "evals/reports/group-search.json",
    )
    parser.add_argument(
        "--database", type=Path, default=BACKEND.parent / "var/search-eval.db"
    )
    parser.add_argument(
        "--reuse-database",
        action="store_true",
        help="Использовать готовую базу, без миграций и векторизации документов",
    )
    args = parser.parse_args()
    args.database.parent.mkdir(parents=True, exist_ok=True)
    overrides: dict[str, Any] = {
        "database_url": f"sqlite:///{args.database.resolve()}",
        "embeddings_url": args.embeddings_url,
        "embeddings_model": args.model,
    }
    if args.ktru_dir is not None:
        overrides["ktru_xml_dir"] = args.ktru_dir
    settings = Settings(**overrides)
    if args.reuse_database:
        if not args.database.is_file():
            raise FileNotFoundError(args.database)
    else:
        config = Config(BACKEND / "alembic.ini")
        config.attributes["database_url"] = settings.database_url
        config.attributes["configure_logger"] = False
        command.upgrade(config, "head")
        sync = sync_catalog(settings)
        if sync.invalid_aliases:
            raise RuntimeError("Начальный словарь ссылается на отсутствующие группы")
        save_vectors(settings)
    with sqlite3.connect(
        f"file:{args.database.resolve()}?mode=ro", uri=True
    ) as connection:
        positions = connection.execute("SELECT count(*) FROM positions").fetchone()[0]
        aliases = connection.execute(
            "SELECT count(*) FROM aliases WHERE reviewed"
        ).fetchone()[0]
        documents = connection.execute(
            "SELECT count(*) FROM group_search_vectors"
        ).fetchone()[0]
    dataset = json.loads(args.dataset.read_text(encoding="utf-8"))
    runs = []
    for instruction in (settings.embeddings_query_instruction, ""):
        run = evaluate(settings, dataset["cases"], instruction)
        runs.append(run)
        print(
            f"instruction={bool(instruction)} R@1/5/10="
            f"{run['recall_counts']}/{run['positive_cases']}",
            flush=True,
        )
    report = {
        "dataset": args.dataset.name,
        "dataset_groups": len(dataset["groups"]),
        "model": settings.embeddings_model,
        "revision": settings.embeddings_revision,
        "positions": positions,
        "aliases": aliases,
        "documents": documents,
        "database_sha256": hashlib.sha256(args.database.read_bytes()).hexdigest(),
        "evaluation": "HTTP API; exact gold-name match; no category filter",
        "runs": runs,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    text = [
        "# Smoke: продуктовый поиск групп КТРУ",
        "",
        f"Модель: `{report['model']}`, ревизия `{report['revision']}`.",
        "",
        (
            f"Датасет `{args.dataset.name}`: {report['dataset_groups']} групп по названию; "
            f"продукт: {runs[0]['product_groups']} групп по коду, "
            f"{runs[0]['product_group_names']} названий, {positions} позиций."
        ),
        "",
        "| Режим запросов | R@1 | R@5 | R@10 |",
        "|---|---:|---:|---:|",
    ]
    for run in runs:
        label = "С инструкцией Qwen" if run["instruction"] else "Без инструкции"
        values = " | ".join(
            f"{run['recall_counts'][str(k)]}/{run['positive_cases']}"
            for k in (1, 5, 10)
        )
        text.append(f"| {label} | {values} |")
    text += [
        "",
        "Baseline гибрида из исследования: 30/42/42 из 46; порог R@5 — 42/46.",
        "",
        (
            "Каждый кейс вызывает `POST /api/v1/search` с limit=10 без фильтра категории. "
            "Попадание — точное название из gold среди top-k. Кейсы gold=[НЕТ] исключены "
            "из знаменателя; поиск не реализует отказ от классификации."
        ),
        "",
        (
            f"Словарь: {aliases} проверенных записей. Это development-замер: "
            "часть синонимов взята из известных провалов smoke_v0; независимым holdout он не является."
        ),
        "",
        (
            "Документы построены из реального XML; эмбеддинги получены от работающего GPU-сервиса. "
            "Заглушки, локальные веса и готовые top20/hyb10 датасета не используются. "
            "Исходный датасет не меняется. Подробные ответы API и время запросов — в соседнем JSON."
        ),
        "",
        (
            f"SQLite SHA256: `{report['database_sha256']}`; сохранено {documents} документов. "
            "Каждый запуск запрещает embed_documents; для запросов используется реальный сервис."
        ),
        "",
    ]
    args.output.with_suffix(".md").write_text("\n".join(text), encoding="utf-8")
    return (
        0
        if runs[0]["positive_cases"] == 46 and runs[0]["recall_counts"]["5"] >= 42
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
