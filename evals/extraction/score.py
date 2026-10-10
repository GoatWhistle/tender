"""Абсолютные ошибки, precision/coverage и Wilson CI по ручной разметке ответов."""

import argparse
import json
import math
from pathlib import Path
from typing import Any


def wilson(correct: int, total: int) -> list[float] | None:
    if not total:
        return None
    z = 1.96
    p = correct / total
    denominator = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denominator
    margin = (
        z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denominator
    )
    return [center - margin, center + margin]


def score(report: dict[str, Any], labels: dict[str, Any]) -> dict[str, Any]:
    observations = []
    for row in report["rows"]:
        raw = row["raw_extractions"][-1]["facts"] if row["raw_extractions"] else []
        gold = labels["cases"][row["id"]]
        if len(raw) != len(gold):
            raise ValueError(f"Нужна новая разметка ответа {row['id']}")
        for item, (correct, reason) in zip(raw, gold, strict=True):
            fact = next(
                (
                    f
                    for f in row["state"]["facts"]
                    if f.get("verification")
                    and f["characteristic_name"] == item["attribute_ref"]
                    and f["raw_value"] == item["raw_value"]
                    and f["source"]["message_id"] == item["source_message_id"]
                    and f["source"]["quote"] == item["source_quote"]
                ),
                None,
            )
            verification = fact.get("verification") if fact else None
            observations.append(
                {
                    "case": row["id"],
                    "controlled": row["controlled"],
                    "correct": correct,
                    "reason": reason,
                    "accepted": bool(fact and fact["status"] == "accepted_from_model"),
                    "verified": bool(verification),
                    "verifier_pass": bool(
                        verification
                        and verification["probabilities"].get("supported", 0)
                        >= report["threshold"]
                    ),
                }
            )
    result = {}
    for name, items in (
        ("all", observations),
        ("actual", [o for o in observations if not o["controlled"]]),
        ("controlled", [o for o in observations if o["controlled"]]),
    ):
        correct = sum(o["correct"] for o in items)
        accepted = sum(o["accepted"] for o in items)
        missed = sum(o["accepted"] and not o["correct"] for o in items)
        rejected_good = sum(o["correct"] and not o["accepted"] for o in items)
        verified = [o for o in items if o["verified"]]
        result[name] = {
            "candidates": len(items),
            "correct": correct,
            "incorrect": len(items) - correct,
            "accepted": accepted,
            "missed_errors": missed,
            "correct_not_autoaccepted": rejected_good,
            "precision": (accepted - missed) / accepted if accepted else None,
            "precision_wilson95": wilson(accepted - missed, accepted),
            "coverage": accepted / len(items) if items else None,
            "verified": len(verified),
            "verifier_missed_errors": sum(
                o["verifier_pass"] and not o["correct"] for o in verified
            ),
            "verifier_rejected_correct": sum(
                o["correct"] and not o["verifier_pass"] for o in verified
            ),
        }
    return {"metrics": result, "observations": observations}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("report", type=Path)
    p.add_argument(
        "--labels", type=Path, default=Path(__file__).with_name("adjudication.json")
    )
    args = p.parse_args()
    print(
        json.dumps(
            score(
                json.loads(args.report.read_text()), json.loads(args.labels.read_text())
            ),
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
