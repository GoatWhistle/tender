"""Калибровка enum-сопоставления на dev_v1 и отдельная проверка замороженного holdout.

Запуск из корня: backend/.venv/bin/python evals/enum/run.py --url URL --out PATH.
Проверяет HTTP-сценарий продукта на SQLite; группу задаёт разметка, поиск не измеряется.
"""

import argparse
import hashlib
import json
import math
import statistics
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from alembic import command
from alembic.config import Config
from app.adapter.decision import OpenJevDecision
from app.adapter.facts import DeterministicFactExtractor
from app.adapter.ktru_xml import XmlKtruSource
from app.domain.catalog import (
    Characteristic,
    CharacteristicKind,
    Group,
    Position,
    Value,
)
from app.domain.enum_mapping import AutoAcceptance
from app.domain.search import MethodContribution, SearchHit, SearchResult
from composition import build_usecases, checked_decision
from fastapi.testclient import TestClient
from main import create_app, sql_repositories, sync_catalog
from settings import Settings


class Source:
    def __init__(self, group: Group) -> None:
        self.group = group

    def load(self) -> list[Position]:
        return list(
            {p.code: p for p in (self.group.position, *self.group.leaves)}.values()
        )


class Search:
    def __init__(self, group: Group) -> None:
        self.group = group

    def run(
        self, description: str, category: str | None = None, limit: int = 10
    ) -> SearchResult:
        return SearchResult(
            description,
            (
                SearchHit(
                    self.group.position,
                    MethodContribution.of(1),
                    MethodContribution.of(None),
                    MethodContribution.of(None),
                ),
            ),
        )


def fixture(case: dict[str, Any]) -> Group:
    fields = tuple(
        Characteristic(
            str(i),
            f["name"],
            False,
            True,
            CharacteristicKind.multiple
            if f.get("multiple")
            else CharacteristicKind.single,
            tuple(Value(str(j), text=v) for j, v in enumerate(f["values"])),
        )
        for i, f in enumerate(case["fields"])
    )
    position = Position(
        "holdout", "Товар", "Мебель", "", "", False, None, (), (), fields
    )
    return Group.of(position, ())


def measure(
    case: dict[str, Any], group: Group, model: OpenJevDecision, revision: str
) -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as tmp:
        settings = Settings(
            database_url=f"sqlite:///{tmp}/eval.db",
            decision_url=None,
            aliases_path=Path(tmp) / "absent.csv",
        )
        config = Config(ROOT / "backend/alembic.ini")
        config.attributes.update(
            database_url=settings.database_url, configure_logger=False
        )
        command.upgrade(config, "head")
        source = Source(group)
        sync_catalog(settings, source)
        app = create_app(settings, source)
        app.state.usecases = build_usecases(
            sql_repositories(),
            catalog_source=source,
            searcher=Search(group),
            fact_extractor=DeterministicFactExtractor(),
            decision=model,
            enum_policy=AutoAcceptance(0, revision),
        )  # только измерение кандидатов на порог
        with TestClient(app) as client:
            state = client.post("/api/v1/sessions").json()
            started = time.perf_counter()
            for message in case["messages"]:
                state = client.post(
                    f"/api/v1/sessions/{state['session_id']}/messages",
                    json={"text": message},
                ).json()
            duration = time.perf_counter() - started
    gold = {
        (
            f["characteristic"].lower().replace("ё", "е"),
            f["value"].lower().replace("ё", "е"),
        )
        for f in case["facts"]
        if isinstance(f["value"], str)
    }
    actual = {}
    for f in state["facts"]:
        if f["origin"] == "decision" and f["status"] != "superseded":
            key = (f["characteristic_name"].lower().replace("ё", "е"), f["value"])
            actual[key] = {
                "field": key[0],
                "value": key[1],
                "correct": key in gold,
                "eligible": f["status"] == "accepted_from_model",
                "score": f["model_score"],
            }
    return {
        "id": case["id"],
        "latency_seconds": duration,
        "errors": state["errors"],
        "gold": sorted(gold),
        "predictions": list(actual.values()),
        "exact": set(actual) == gold,
        "messages": case["messages"],
    }


def summary(rows: list[dict[str, Any]], threshold: float | None) -> dict[str, Any]:
    predictions = [p for row in rows for p in row["predictions"]]
    accepted = []
    for row in rows:
        for field in {p["field"] for p in row["predictions"]}:
            values = [p for p in row["predictions"] if p["field"] == field]
            if threshold is not None and all(
                p["eligible"] and p["score"] >= threshold for p in values
            ):
                accepted.extend(values)
    correct = sum(p["correct"] for p in accepted)
    n = len(accepted)
    # Односторонняя точная нижняя граница 95% для случая без ошибок.
    lower = 0.05 ** (1 / n) if n and correct == n else 0.0
    durations = sorted(row["latency_seconds"] for row in rows)
    return {
        "cases": len(rows),
        "technical_errors": sum(bool(r["errors"]) for r in rows),
        "exact_cases": sum(r["exact"] for r in rows),
        "predictions": len(predictions),
        "correct_predictions": sum(p["correct"] for p in predictions),
        "gold_values": sum(len(r["gold"]) for r in rows),
        "accepted": n,
        "correct_accepted": correct,
        "precision_lower_95": lower,
        "auto_coverage_of_predictions": n / len(predictions) if predictions else 0,
        "latency_p50_seconds": statistics.median(durations) if durations else None,
        "latency_p95_seconds": durations[math.ceil(len(durations) * 0.95) - 1]
        if durations
        else None,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument(
        "--holdout", type=Path, default=ROOT / "evals/datasets/enum_holdout_v2.json"
    )
    parser.add_argument("--threshold", type=float, default=0.90)
    args = parser.parse_args()
    model = OpenJevDecision(args.url)
    health = checked_decision(model).health()
    dev_path = ROOT / "evals/datasets/dev_v1.json"
    holdout_path = args.holdout
    catalog = XmlKtruSource(Settings().ktru_xml_dir).load()
    by_code = {p.code: p for p in catalog}
    report: dict[str, Any] = {
        "model_revision": health.revision,
        "url": args.url,
        "algorithm": "enum_decision_v2",
        "policy_source": "Порог 0.90 выбран пользователем для более частого автопринятия",
        "dataset_sha256": {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in (dev_path, holdout_path)
        },
        "dev": [],
        "holdout": [],
        "auto_acceptance_enabled": True,
        "vram": None,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)

    def save() -> None:
        args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")

    for case in json.loads(dev_path.read_text())["cases"]:
        if not case["groups"]:
            continue
        root = by_code[case["groups"][0]]
        group = Group.of(root, [p for p in catalog if p.parent == root.code])
        report["dev"].append(measure(case, group, model, health.revision))
        save()
        print("dev", case["id"], flush=True)
    grid = [0.5, 0.8, 0.9, 0.95, 0.99, 0.995, 0.999]
    report["calibration"] = [
        {"threshold": t, **summary(report["dev"], t)} for t in grid
    ]
    # Новый продуктовый профиль согласован до запуска новой независимой выборки.
    threshold = args.threshold
    report["selected_threshold"] = threshold
    save()
    for case in json.loads(holdout_path.read_text())["cases"]:
        report["holdout"].append(measure(case, fixture(case), model, health.revision))
        save()
        print("holdout", case["id"], flush=True)
    report["dev_summary"] = summary(report["dev"], threshold)
    report["holdout_summary"] = summary(report["holdout"], threshold)
    save()


if __name__ == "__main__":
    main()
