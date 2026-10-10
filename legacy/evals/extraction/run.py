"""Независимый замер extractor/verifier через общую сборку сценариев продукта.

Набор заморожен до прогона; порог не подбирается. Поиск и проверка назначения заменены заранее подтверждённой группой.
"""

import argparse
import hashlib
import json
import math
import statistics
import sys
import time
from collections.abc import Sequence
from dataclasses import asdict, replace
from decimal import Decimal
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.adapter.decision import OpenJevDecision
from app.adapter.extractor import QwenExtractor
from app.adapter.facts import DeterministicFactExtractor
from app.adapter.stub import StubDecisionBackend
from app.domain.catalog import Characteristic, CharacteristicKind, Position, Value
from app.domain.inference import (
    ChoiceAnswer,
    Claim,
    ClaimBatch,
    ExtractedFact,
    Extraction,
    ExtractionRequest,
)
from app.domain.search import MethodContribution, SearchHit, SearchResult
from app.repository.memory.catalog import MemoryCatalog
from app.repository.memory.sessions import MemorySessions
from app.repository.memory.unit_of_work import MemoryStore, MemoryUnitOfWork
from composition import Repositories, build_usecases


class MeasuredDecision(OpenJevDecision):
    def __init__(self, url: str) -> None:
        super().__init__(url)
        self.samples: list[float] = []

    def verify(self, context: str, claims: Sequence[Claim]) -> ClaimBatch:
        start = time.perf_counter()
        try:
            return super().verify(context, claims)
        finally:
            self.samples.append(time.perf_counter() - start)


class MeasuredExtractor(QwenExtractor):
    def __init__(self, url: str, case: dict[str, Any]) -> None:
        super().__init__(url)
        self.case = case
        self.samples: list[float] = []
        self.raw: list[dict[str, Any]] = []

    def extract(self, request: ExtractionRequest) -> Extraction:
        start = time.perf_counter()
        try:
            if "extract" in self.case:
                payload = dict(self.case["extract"])
                index = payload.pop("source_index", len(request.messages) - 1)
                fact = ExtractedFact(
                    source_message_id=request.messages[
                        min(index, len(request.messages) - 1)
                    ].message_id,
                    **payload,
                )
                result = Extraction((fact,), "controlled-corruption-v1")
            else:
                result = super().extract(request)
            self.raw.append(asdict(result))
            return result
        finally:
            self.samples.append(time.perf_counter() - start)


class Source:
    def load(self) -> list[Position]:
        fields = (
            Characteristic(
                "h",
                "Высота",
                True,
                True,
                CharacteristicKind.single,
                (Value("h", unit_code="004", min=Decimal(10), max=Decimal(300)),),
            ),
            *(
                Characteristic(str(i), name, False, False, CharacteristicKind.single)
                for i, name in enumerate(
                    ("Материал столешницы", "Материал ножек", "Цвет")
                )
            ),
        )
        root = Position("table", "Стол", "Мебель", "", "", True, None, (), ())
        return [
            root,
            replace(
                root,
                code="table-a",
                parent=root.code,
                is_template=False,
                characteristics=fields,
            ),
            replace(
                root,
                code="table-b",
                parent=root.code,
                is_template=False,
                characteristics=fields,
            ),
        ]


class Search:
    def run(
        self, description: str, category: str | None = None, limit: int = 10
    ) -> SearchResult:
        return SearchResult(
            description,
            (
                SearchHit(
                    Source().load()[0],
                    MethodContribution.of(1),
                    MethodContribution.of(None),
                    MethodContribution.of(None),
                    found_by="code",
                ),
            ),
        )


def measure(
    case: dict[str, Any], extractor_url: str, decision_url: str
) -> dict[str, Any]:
    store = MemoryStore()
    source = Source()
    MemoryCatalog(store).replace(source.load())
    model, decision = (
        MeasuredExtractor(extractor_url, case),
        MeasuredDecision(decision_url),
    )
    # Здесь назначение задано разметкой; качество выбора групп измеряет evals/groups/.
    group_decision = StubDecisionBackend()
    group_decision.choices["group:table"] = ChoiceAnswer(
        "group:table",
        {"supported": 1.0, "contradicted": 0.0, "not_stated": 0.0},
        "supported",
        support_scores={"supported": 1.0, "contradicted": 0.0, "not_stated": 0.0},
    )
    usecases = build_usecases(
        Repositories(
            catalog=lambda u: MemoryCatalog(store),
            sessions=lambda u: MemorySessions(store),
        ),
        catalog_source=source,
        searcher=Search(),
        fact_extractor=DeterministicFactExtractor(),
        model_extractor=model,
        decision=decision,
        group_decision=group_decision,
    )
    assert usecases.sessions
    sessions = usecases.sessions(MemoryUnitOfWork(store))
    state = sessions.create()
    start = time.perf_counter()
    for text in case["messages"]:
        state = sessions.message(state.session_id, text)
    elapsed = time.perf_counter() - start
    return {
        "id": case["id"],
        "controlled": "extract" in case,
        "expected": case["expected"],
        "raw_extractions": model.raw,
        "state": asdict(state),
        "seconds": elapsed,
        "extractor_seconds": model.samples,
        "verifier_seconds": decision.samples,
    }


def summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    def quantiles(values: list[float]) -> dict[str, float | None]:
        return {
            "p50": statistics.median(values) if values else None,
            "p95": sorted(values)[math.ceil(len(values) * 0.95) - 1]
            if values
            else None,
        }

    return {
        "cases": len(rows),
        "session_seconds": quantiles([r["seconds"] for r in rows]),
        "verifier_call_seconds": quantiles(
            [x for r in rows for x in r["verifier_seconds"]]
        ),
        "added_verifier_seconds_per_case": quantiles(
            [sum(r["verifier_seconds"]) for r in rows]
        ),
        "extractor_call_seconds": quantiles(
            [x for r in rows if not r["controlled"] for x in r["extractor_seconds"]]
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--extractor-url", required=True)
    parser.add_argument("--decision-url", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument(
        "--only", action="append", help="Точный ID для повторной проверки"
    )
    parser.add_argument(
        "--cases", type=Path, default=Path(__file__).with_name("cases.json")
    )
    args = parser.parse_args()
    rows = []
    cases = json.loads(args.cases.read_text())
    args.out.parent.mkdir(parents=True, exist_ok=True)
    for case in cases:
        if args.only and case["id"] not in args.only:
            continue
        row = measure(case, args.extractor_url, args.decision_url)
        rows.append(row)
        print(case["id"], round(row["seconds"], 3), flush=True)
        args.out.write_text(
            json.dumps(
                {
                    "dataset_sha256": hashlib.sha256(
                        args.cases.read_bytes()
                    ).hexdigest(),
                    "threshold": 0.90,
                    "summary": summary(rows),
                    "rows": rows,
                },
                ensure_ascii=False,
                indent=2,
                default=str,
            )
            + "\n"
        )


if __name__ == "__main__":
    main()
