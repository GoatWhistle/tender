"""Отсев текстов не о товаре: косинус ближайшей группы и вердикт OpenJev по наборам.

Товары — `dev_v1.json`, `ste_holdout_v1.csv`, `smoke_v0.json`; мусор — `junk_v1.json`. Поиск и
вопрос decision-модели — продуктовые (`GroupSearch`, `RELEVANCE`), порог и вероятность —
таблицей по нескольким значениям. Отчёт — `evals/reports/<дата>-out-of-scope.md` и `.json`.
"""

import argparse
import csv
import json
import sys
from contextlib import closing
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from sqlalchemy.orm import Session

from app.adapter.decision import OpenJevDecision
from app.repository.database import create_db_engine
from app.repository.unit_of_work import SqlUnitOfWork
from app.usecase.sessions import RELEVANCE
from main import configured_embeddings, production_usecases
from settings import Settings

DATASETS = ROOT / "evals" / "datasets"
SIMILARITIES = (0.42, 0.44, 0.45, 0.46, 0.48, 0.50)
PROBABILITIES = (0.5, 0.6, 0.7, 0.8)
KINDS = ("product", "outside", "junk")


def cases() -> list[dict[str, str]]:
    rows = []
    for c in json.loads((DATASETS / "dev_v1.json").read_text())["cases"]:
        kind = "product" if c["groups"] else "outside"
        rows.append({"source": "dev_v1", "kind": kind, "text": "\n".join(c["messages"])})
    with (DATASETS / "ste_holdout_v1.csv").open() as f:
        for r in csv.DictReader(f):
            kind = "outside" if r["label"] == "НЕТ" else "product"
            rows.append({"source": "ste_holdout_v1", "kind": kind, "text": r["name"]})
    for c in json.loads((DATASETS / "smoke_v0.json").read_text())["cases"]:
        kind = "outside" if c["gold"] == ["НЕТ"] else "product"
        rows.append({"source": "smoke_v0", "kind": kind, "text": c["text"]})
    for text in json.loads((DATASETS / "junk_v1.json").read_text())["texts"]:
        rows.append({"source": "junk_v1", "kind": "junk", "text": text})
    return rows


def measure(settings: Settings, decision_url: str) -> list[dict[str, Any]]:
    embeddings = configured_embeddings(settings)
    assert embeddings is not None, "нужен --embeddings-url"
    usecases = production_usecases(settings, embeddings=embeddings)
    engine = create_db_engine(settings.database_url)
    with closing(SqlUnitOfWork(Session(engine))) as uow:
        search = usecases.group_search(uow)
        search.build()
    decision = OpenJevDecision(decision_url)
    rows = cases()
    for row in rows:
        result = search.run(row["text"])
        (answer,) = decision.choose(row["text"], [RELEVANCE]).answers
        row["similarity"] = result.similarity
        row["junk"] = answer.probabilities["junk"]
        print(f"{row['kind']:8} {row['similarity']:.3f} {row['junk']:.2f} {row['text'][:60]!r}")
    return rows


def report(rows: list[dict[str, Any]]) -> str:
    def count(kind: str) -> int:
        return sum(r["kind"] == kind for r in rows)

    lines = [
        "# Отсев текстов не о товаре",
        "",
        f"Товары: {count('product')}, вне КТРУ: {count('outside')}, мусор: {count('junk')} "
        "(`dev_v1`, `ste_holdout_v1`, `smoke_v0`, `junk_v1`).",
        "",
        "## Косинус ближайшей группы",
        "",
        "| Порог | Товаров отсеяно | Вне КТРУ отсеяно | Мусора отсеяно |",
        "|---:|---:|---:|---:|",
    ]
    for t in SIMILARITIES:
        below = [sum(r["kind"] == k and r["similarity"] < t for r in rows) for k in KINDS]
        lines.append(f"| {t:.2f} | " + " | ".join(map(str, below)) + " |")
    lines += [
        "",
        "## OpenJev выше порога 0.45",
        "",
        "| P(junk) ≥ | Товаров отсеяно | Вне КТРУ отсеяно | Мусора пропущено |",
        "|---:|---:|---:|---:|",
    ]
    above = [r for r in rows if r["similarity"] >= 0.45]
    for p in PROBABILITIES:
        product, outside = (
            sum(r["kind"] == k and r["junk"] >= p for r in above) for k in KINDS[:2]
        )
        missed = sum(r["kind"] == "junk" and r["junk"] < p for r in above)
        lines.append(f"| {p:.1f} | {product} | {outside} | {missed} |")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--embeddings-url", required=True)
    parser.add_argument("--decision-url", required=True)
    args = parser.parse_args()
    settings = Settings(embeddings_url=args.embeddings_url)
    rows = measure(settings, args.decision_url)
    out = ROOT / "evals" / "reports" / f"{date.today().isoformat()}-out-of-scope"
    out.with_suffix(".json").write_text(json.dumps(rows, ensure_ascii=False, indent=1) + "\n")
    out.with_suffix(".md").write_text(report(rows))
    print(out.with_suffix(".md").read_text())


if __name__ == "__main__":
    main()
