"""Score error diagnostics against labeled Russian descriptions (stdlib only)."""

import argparse
import json
from collections import Counter
from pathlib import Path

ERROR_KINDS = {"typo", "value_not_in_catalog", "out_of_range"}
KINDS = (*sorted(ERROR_KINDS), "synonym")


def ratio(numerator, denominator):
    return numerator / denominator if denominator else None


def indexed(rows):
    result = {}
    for row in rows:
        if not isinstance(row.get("id"), str) or not row["id"]:
            raise ValueError("Each row requires a nonempty id")
        if row["id"] in result:
            raise ValueError(f"Duplicate id: {row['id']}")
        result[row["id"]] = row
    return result


def events(row, field, allowed, text):
    values = row.get(field)
    if not isinstance(values, list):
        raise TypeError(f"{row['id']}: {field} must be a list")
    output = []
    for event in values:
        if event.get("kind") not in allowed:
            raise ValueError(f"{row['id']}: invalid {field} kind")
        quote = event.get("source_quote")
        if not isinstance(quote, str) or not quote or quote not in text:
            raise ValueError(f"{row['id']}: source_quote must occur in source text")
        output.append((event["kind"], quote))
    if len(set(output)) != len(output):
        raise ValueError(f"{row['id']}: duplicate diagnostic")
    return Counter(output)


def score(dataset, predictions):
    gold = indexed(dataset["cases"])
    predicted = indexed(predictions)
    if gold.keys() != predicted.keys():
        raise ValueError("Prediction ids must exactly match dataset ids")
    totals = {kind: Counter(tp=0, fp=0, fn=0, tn=0) for kind in KINDS}
    detail = {kind: Counter(tp=0, fp=0, fn=0) for kind in KINDS}
    clean = alarms = synonym_cases = synonym_errors = corrected = (
        expected_corrections
    ) = 0
    for case_id, case in gold.items():
        row = predicted[case_id]
        expected = events(case, "expected", set(KINDS), case["text"])
        actual = events(row, "errors", ERROR_KINDS, case["text"])
        actual.update(events(row, "normalizations", {"synonym"}, case["text"]))
        for kind in KINDS:
            g = Counter({key: n for key, n in expected.items() if key[0] == kind})
            p = Counter({key: n for key, n in actual.items() if key[0] == kind})
            state = "tp" if g and p else "fn" if g else "fp" if p else "tn"
            totals[kind][state] += 1
            detail[kind]["tp"] += sum((g & p).values())
            detail[kind]["fn"] += sum((g - p).values())
            detail[kind]["fp"] += sum((p - g).values())
        has_error = any(key[0] in ERROR_KINDS for key in expected)
        if not has_error:
            clean += 1
            alarms += bool(row["errors"])
        if any(key[0] == "synonym" for key in expected):
            synonym_cases += 1
            synonym_errors += bool(row["errors"])
        for event in case["expected"]:
            if event["kind"] not in {"typo", "synonym"}:
                continue
            expected_corrections += 1
            corrected += any(
                p["kind"] == event["kind"]
                and p["source_quote"] == event["source_quote"]
                and p.get("suggestion") == event["suggestion"]
                for p in row["errors"] + row["normalizations"]
            )
    per_kind = {}
    for kind, counts in totals.items():
        per_kind[kind] = {
            **counts,
            "recall": ratio(counts["tp"], counts["tp"] + counts["fn"]),
            "false_positive_rate": ratio(counts["fp"], counts["fp"] + counts["tn"]),
            "diagnostics": dict(detail[kind]),
            "diagnostic_recall": ratio(
                detail[kind]["tp"], detail[kind]["tp"] + detail[kind]["fn"]
            ),
        }
    return {
        "cases": len(gold),
        "per_kind": per_kind,
        "clean_cases": clean,
        "false_alarm_cases": alarms,
        "false_alarm_rate": ratio(alarms, clean),
        "synonym_cases": synonym_cases,
        "synonyms_reported_as_errors": synonym_errors,
        "correct_suggestions": corrected,
        "expected_suggestions": expected_corrections,
        "suggestion_accuracy": ratio(corrected, expected_corrections),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset", type=Path, default=Path("evals/datasets/errors_ru_v1.json")
    )
    parser.add_argument(
        "--predictions",
        type=Path,
        required=True,
        help="JSONL: id, errors, normalizations",
    )
    args = parser.parse_args()
    data = json.loads(args.dataset.read_text())
    rows = [
        json.loads(line)
        for line in args.predictions.read_text().splitlines()
        if line.strip()
    ]
    print(json.dumps(score(data, rows), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
