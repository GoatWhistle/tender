"""R@1/R@5/R@10 продуктового поиска групп КТРУ на `smoke_v0` — с инструкцией Qwen к запросу и без.

Поиск — тот же сценарий, что за `POST /api/v1/search` (`composition.build_usecases`), на
in-memory хранилищах; справочник — XML организаторов, синонимы — `data/aliases.csv`.

Попадание — в top-k есть группа с названием из `gold`: `smoke_v0` размечен названиями групп
(400 различных), продукт ищет по кодам (432 группы, у части названия совпадают). Кейсы с ответом
«НЕТ» не считаются. Правило замера — `docs/search.md`.

Запуск: cd backend && uv run python ../evals/search/smoke_search.py [--url http://host:8089]
Без `--url` адрес — `EMBEDDINGS_URL` из `.env`. `--stub` — прогон на заглушке эмбеддингов:
проверка скрипта, числа не для отчёта. Печатает таблицу Markdown и промахи top-5.
"""

import argparse
import json
import pathlib
import sys
import time

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "backend"))

from app.adapter.aliases_csv import CsvAliasSource
from app.adapter.embeddings_http import HttpEmbeddings
from app.adapter.ktru_xml import XmlKtruSource
from app.adapter.stub import StubEmbeddings
from app.adapter.tfidf import TfidfLexicalIndex
from app.adapter.vector_numpy import NumpyVectorIndex
from app.repository.memory.aliases import MemoryAliases
from app.repository.memory.catalog import MemoryCatalog
from app.repository.memory.unit_of_work import MemoryStore, MemoryUnitOfWork
from app.usecase.interface import Embeddings
from app.usecase.search import SearchQuery
from composition import Repositories, build_usecases
from settings import Settings

DATASET = REPO / "evals" / "datasets" / "smoke_v0.json"
NONE = "НЕТ"
KS = (1, 5, 10)


def recall(embeddings: Embeddings, settings: Settings, cases: list[dict[str, object]]) -> dict:
    usecases = build_usecases(
        Repositories[MemoryUnitOfWork](
            catalog=lambda uow: MemoryCatalog(uow.store),
            aliases=lambda uow: MemoryAliases(uow.store),
        ),
        catalog_source=XmlKtruSource(settings.ktru_xml_dir),
        alias_source=CsvAliasSource(settings.aliases_csv),
        embeddings=embeddings,
        lexical_index=TfidfLexicalIndex(),
        vector_index=NumpyVectorIndex(),
    )
    uow = MemoryUnitOfWork(MemoryStore())
    groups = len(usecases.catalog_queries(uow).groups()) if usecases.catalog_sync(uow).run() else 0
    search = usecases.group_search(uow)
    started = time.perf_counter()
    search.warm()
    built = time.perf_counter() - started

    hits = dict.fromkeys(KS, 0)
    misses = []
    started = time.perf_counter()
    for case in cases:
        gold = set(case["gold"])  # type: ignore[call-overload]
        names = [m.group.name for m in search.search(SearchQuery(str(case["text"]))).groups]
        for k in KS:
            hits[k] += bool(gold & set(names[:k]))
        if not gold & set(names[:5]):
            misses.append((case["text"], sorted(gold), names[:3]))
    per_query = (time.perf_counter() - started) / len(cases) * 1000
    return {"hits": hits, "misses": misses, "groups": groups, "built": built, "ms": per_query}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url")
    parser.add_argument("--stub", action="store_true")
    args = parser.parse_args()
    settings = Settings()
    cases = [c for c in json.loads(DATASET.read_text())["cases"] if c["gold"] != [NONE]]

    if args.stub:
        runs = {"заглушка эмбеддингов": StubEmbeddings()}
    else:
        url = args.url or settings.embeddings_url
        if not url:
            sys.exit("нет адреса эмбеддингов: --url или EMBEDDINGS_URL в .env")
        model, key = settings.embeddings_model, settings.embeddings_api_key
        runs = {
            "с инструкцией Qwen": HttpEmbeddings(url, model, key),
            "без инструкции": HttpEmbeddings(url, model, key, instruct=False),
        }

    results = {label: recall(e, settings, cases) for label, e in runs.items()}
    n = len(cases)
    print(f"Кейсов: {n}. Групп в продукте: {next(iter(results.values()))['groups']}.\n")
    print("| Запрос | " + " | ".join(f"R@{k}" for k in KS) + " | индекс, с | запрос, мс |")
    print("| --- |" + " ---: |" * (len(KS) + 2))
    for label, r in results.items():
        cells = " | ".join(f"{r['hits'][k]}/{n}" for k in KS)
        print(f"| {label} | {cells} | {r['built']:.1f} | {r['ms']:.0f} |")
    for label, r in results.items():
        print(f"\nПромахи top-5, {label}:")
        for text, gold, top in r["misses"]:
            print(f"- {text[:60]} — нужно {gold}, top-3 {top}")


if __name__ == "__main__":
    main()
