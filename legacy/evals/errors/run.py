"""HTTP-прогон размеченных диагностик в полном fixture scope; модели заменены заглушками.

cd backend && uv run python ../evals/errors/run.py
Это проверка продуктового сценария, не качество поиска или живой Qwen.
"""

import argparse
import json
import sys
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT))

from alembic import command
from alembic.config import Config
from app.adapter.enum_similarity import DamerauMatcher
from app.adapter.facts import DeterministicFactExtractor
from app.adapter.value_aliases import ReviewedValueAliases
from app.domain.catalog import (
    Bound,
    Characteristic,
    CharacteristicKind,
    Position,
    Value,
)
from app.domain.search import MethodContribution, SearchHit, SearchResult
from composition import build_usecases
from fastapi.testclient import TestClient
from main import create_app, sql_repositories, sync_catalog
from settings import BACKEND_DIR, Settings

from evals.errors.score import score


class FixtureSource:
    def __init__(self, position):
        self.position = position

    def load(self):
        return [self.position]

    def run(self, description, category=None, limit=10):
        return SearchResult(
            description,
            (
                SearchHit(
                    self.position,
                    MethodContribution.of(1),
                    MethodContribution.of(None),
                    MethodContribution.of(None),
                ),
            ),
        )


class EmptySpelling:
    def suggest(self, message):
        return ()


def fixture(dataset, case):
    rule_id = case["rule_id"]
    if rule_id.endswith("_alias"):
        alias = next(a for a in dataset["aliases"] if a["id"] == rule_id)
        # Самостоятельный контекстный fixture из проверенной строки словаря.
        name = {
            "clothes_alias": "Напыление",
            "furniture_alias": "Материал обивки",
            "tools_alias": "Тип инструмента",
        }[rule_id]
        char = Characteristic(
            rule_id,
            name,
            False,
            True,
            CharacteristicKind.single,
            (Value("canonical", text=alias["canonical"]),),
        )
        return Position(
            rule_id, name, case["category"], "", "", False, None, (), (), (char,)
        )
    rule = dataset["rules"][rule_id]
    ch = rule["characteristic"]
    values = []
    for original in ch["values"]:
        v = dict(original)
        for key in ("min", "max", "concrete"):
            if v[key] is not None:
                v[key] = Decimal(str(v[key]))
        for key in ("min_op", "max_op"):
            if v[key] is not None:
                v[key] = Bound(v[key])
        values.append(Value(**v))
    char = Characteristic(
        ch["code"],
        ch["name"],
        ch["quantitative"],
        ch["required"],
        CharacteristicKind.multiple if ch["multi"] else CharacteristicKind.single,
        tuple(values),
    )
    return Position(
        rule["position_code"],
        rule["position_name"],
        rule["category"],
        "",
        "",
        False,
        None,
        (),
        (),
        (char,),
    )


def run(dataset):
    predictions = []
    with TemporaryDirectory() as directory:
        settings = Settings(database_url=f"sqlite:///{directory}/fixture.db")
        config = Config(BACKEND_DIR / "alembic.ini")
        config.attributes["database_url"] = settings.database_url
        config.attributes["configure_logger"] = False
        command.upgrade(config, "head")
        for case in dataset["cases"]:
            if case.get("scope", {}).get("complete", True) is not True:
                raise ValueError("Прогон требует явно полного fixture scope")
            source = FixtureSource(fixture(dataset, case))
            sync_catalog(settings, source)
            app = create_app(settings, source)
            app.state.usecases = build_usecases(
                sql_repositories(),
                catalog_source=source,
                searcher=source,
                fact_extractor=DeterministicFactExtractor(ReviewedValueAliases().all()),
                enum_matcher=DamerauMatcher(),
                value_aliases=ReviewedValueAliases(),
                spelling=EmptySpelling(),
            )
            with TestClient(app) as client:
                sid = client.post("/api/v1/sessions").json()["session_id"]
                response = client.post(
                    f"/api/v1/sessions/{sid}/messages", json={"text": case["text"]}
                )
                response.raise_for_status()
                state = response.json()
                if state["status"] == "technical_error" or any(
                    "code" in e for e in state["errors"]
                ):
                    raise RuntimeError(
                        f"{case['id']}: технический сбой: {state['errors']}"
                    )
                predictions.append(
                    {
                        "id": case["id"],
                        "errors": state["errors"],
                        "normalizations": state["normalizations"],
                    }
                )
    return predictions


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset", type=Path, default=ROOT / "evals/datasets/errors_ru_v1.json"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "evals/reports/2026-10-10-diagnostics-fixture",
    )
    args = parser.parse_args()
    dataset = json.loads(args.dataset.read_text())
    predictions = run(dataset)
    metrics = score(dataset, predictions)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.with_suffix(".jsonl").write_text(
        "".join(json.dumps(p, ensure_ascii=False) + "\n" for p in predictions)
    )
    args.output.with_suffix(".json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2) + "\n"
    )
    lines = [
        "# Диагностики через HTTP API — локальные fixtures",
        "",
        (
            f"{len(dataset['cases'])} синтетических случая из `{args.dataset.name}`. "
            "Правила КТРУ из размеченного снимка; "
            "scope — явно полный fixture, не весь каталог. Поиск фиксирован; орфографический "
            "порт возвращает пустой ответ. Это проверка детерминированного продуктового сценария, "
            "не измерение качества живой модели."
        ),
        "",
        "| Класс | TP | FP | FN | Полнота по случаям | Ложные срабатывания |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for kind, row in metrics["per_kind"].items():
        lines.append(
            f"| {kind} | {row['tp']} | {row['fp']} | {row['fn']} | "
            f"{row['recall']:.1%} | {row['false_positive_rate']:.1%} |"
        )
    lines.extend(
        [
            "",
            (
                "Точные цитаты и полнота отдельных диагностик — в соседнем JSON; "
                "продуктовые ответы — в JSONL. Технический сбой прерывает прогон."
            ),
            "",
            "Команда: `cd backend && uv run python ../evals/errors/run.py`.",
        ]
    )
    args.output.with_suffix(".md").write_text("\n".join(lines) + "\n")
    print(json.dumps(metrics, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
