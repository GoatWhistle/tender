"""Парный HTTP-прогон K=5/10 с реальными retrieval и decision на одном наборе."""

import argparse
import hashlib
import json
import shutil
import statistics
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from main import create_app  # noqa: E402
from settings import Settings  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--decision-url", default="http://127.0.0.1:18080")
    parser.add_argument("--embeddings-url", default="http://127.0.0.1:18083/v1")
    parser.add_argument("--cases", type=Path, default=ROOT / "evals/groups/cases.json")
    parser.add_argument("--output", type=Path, default=ROOT / "var/group-validation.json")
    args = parser.parse_args()
    cases = json.loads(args.cases.read_text())
    database = ROOT / "artifacts/ktru-search.sqlite3"
    report = {
        "threshold": 0.90,
        "dataset_sha256": hashlib.sha256(args.cases.read_bytes()).hexdigest(),
        "database_sha256": hashlib.sha256(database.read_bytes()).hexdigest(),
        "runs": [],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    for k in (5, 10):
        with tempfile.TemporaryDirectory() as directory:
            copy = Path(directory) / "catalog.db"
            shutil.copyfile(database, copy)
            settings = Settings(
                database_url=f"sqlite:///{copy}",
                group_top_k=k,
                decision_url=args.decision_url,
                embeddings_url=args.embeddings_url,
                spelling_url=None,
                search_min_similarity=0,
            )
            cfg = Config(ROOT / "backend/alembic.ini")
            cfg.attributes["database_url"] = settings.database_url
            cfg.attributes["configure_logger"] = False
            command.upgrade(cfg, "head")
            rows = []
            with TestClient(create_app(settings)) as client:
                for case in cases:
                    retrieval = client.post(
                        "/api/v1/search", json={"description": case["text"], "limit": k}
                    )
                    retrieval.raise_for_status()
                    sid = client.post("/api/v1/sessions").json()["session_id"]
                    start = time.perf_counter()
                    response = client.post(
                        f"/api/v1/sessions/{sid}/messages", json={"text": case["text"]}
                    )
                    response.raise_for_status()
                    state = response.json()
                    elapsed = time.perf_counter() - start
                    found = [c["code"] for c in retrieval.json()["groups"]]
                    selected = state["path"]["group"]["code"] if state["path"] else None
                    hit = bool(set(found) & set(case["gold"])) if case["gold"] else None
                    row = {
                        **case,
                        "k": k,
                        "seconds": elapsed,
                        "retrieval_hit": hit,
                        "selected": selected,
                        "wrong_auto": selected is not None and selected not in case["gold"],
                        "status": state["status"],
                        "checks": state["group_checks"],
                        "errors": state["errors"],
                        "next_question": state["next_question"],
                        "retrieval": retrieval.json(),
                    }
                    rows.append(row)
                    print(k, case["id"], state["status"], selected, round(elapsed, 2), flush=True)
                    args.output.write_text(
                        json.dumps({**report, "in_progress": rows}, ensure_ascii=False, indent=2)
                    )
            positives = [r for r in rows if r["retrieval_hit"] is not None]
            summary = {
                "k": k,
                "n": len(rows),
                "retrieval_recall": sum(r["retrieval_hit"] for r in positives) / len(positives),
                "retrieval_misses": [r["id"] for r in positives if not r["retrieval_hit"]],
                "wrong_auto": sum(r["wrong_auto"] for r in rows),
                "jev_wrong_auto_with_gold_retrieved": [
                    r["id"] for r in rows if r["wrong_auto"] and r["retrieval_hit"]
                ],
                "clarifications": sum(r["status"] == "needs_clarification" for r in rows),
                "technical_errors": sum(r["status"] == "technical_error" for r in rows),
                "mean_seconds": statistics.mean(r["seconds"] for r in rows),
            }
            report["runs"].append({"summary": summary, "cases": rows})
            args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
