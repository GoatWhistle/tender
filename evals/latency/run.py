"""Latency HTTP API по всем сценариям: справочник, поиск, сессии и правки фактов.

Клиент последовательный (один запрос в полёте), соединение keep-alive — меряется задержка
одного запроса, не пропускная способность. Тексты — первые сообщения кейсов
`evals/datasets/dev_v1.json`; по каждому кейсу проходит сессия: сообщения, ответы на вопросы,
правки фактов, пересчёт, решение по enum-предложению, если оно есть. Только stdlib.

    python3 evals/latency/run.py --url http://127.0.0.1:18089 --out var/latency.json
"""

import argparse
import http.client
import json
import statistics
import time
from collections import defaultdict
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlsplit

DATASET = Path(__file__).resolve().parents[1] / "datasets" / "dev_v1.json"
INACTIVE = {"superseded", "deleted"}


class Client:
    def __init__(self, url: str, timeout: float) -> None:
        parts = urlsplit(url)
        self.host, self.port, self.timeout = parts.hostname or "", parts.port or 80, timeout
        self.conn = http.client.HTTPConnection(self.host, self.port, timeout=timeout)
        self.samples: dict[str, list[tuple[float, int]]] = defaultdict(list)

    def call(self, op: str, method: str, path: str, body: Any = None) -> tuple[int, Any]:
        data = json.dumps(body).encode() if body is not None else None
        headers = {"content-type": "application/json"} if data else {}
        start = time.perf_counter()
        try:
            self.conn.request(method, quote(path, safe="/?=&"), data, headers)
            response = self.conn.getresponse()
            raw = response.read()
            status = response.status
        except (OSError, http.client.HTTPException):
            self.conn.close()
            self.conn = http.client.HTTPConnection(self.host, self.port, timeout=self.timeout)
            raw, status = b"", 0
        elapsed = (time.perf_counter() - start) * 1000
        self.samples[op].append((elapsed, status))
        try:
            return status, json.loads(raw) if raw else None
        except json.JSONDecodeError:
            return status, None


def catalog(c: Client, repeat: int) -> None:
    _, groups = c.call("warmup", "GET", "/api/v1/groups")
    _, positions = c.call("warmup", "GET", "/api/v1/positions?category=Мебель")
    group, position = groups[0]["code"], positions[0]["code"]
    for _ in range(repeat):
        c.call("GET /health/live", "GET", "/health/live")
        c.call("GET /health/ready", "GET", "/health/ready")
        c.call("GET /health/models", "GET", "/health/models")
        c.call("GET /positions", "GET", "/api/v1/positions")
        c.call("GET /positions?category", "GET", "/api/v1/positions?category=Мебель")
        c.call("GET /positions/{code}", "GET", f"/api/v1/positions/{position}")
        c.call("GET /groups", "GET", "/api/v1/groups")
        c.call("GET /groups?category", "GET", "/api/v1/groups?category=Мебель")
        c.call("GET /groups/{code}", "GET", f"/api/v1/groups/{group}")


def search(c: Client, cases: list[dict[str, Any]]) -> None:
    for case in cases:
        text = case["messages"][0]
        c.call("POST /search", "POST", "/api/v1/search", {"description": text})
        c.call(
            "POST /search (category)",
            "POST",
            "/api/v1/search",
            {"description": text, "category": case["category"]},
        )


def editable(state: dict[str, Any]) -> dict[str, Any] | None:
    return next(
        (
            f
            for f in state["facts"]
            if f["status"] not in INACTIVE
            and f.get("characteristic_name")
            and not f.get("requires_binding")
            and not f.get("negated")
            and f.get("normalization_rule") != "correction_needs_binding"
        ),
        None,
    )


def session(c: Client, case: dict[str, Any]) -> None:
    status, state = c.call("POST /sessions", "POST", "/api/v1/sessions")
    if status != 200:
        return
    url = f"/api/v1/sessions/{state['session_id']}"
    for i, text in enumerate(case["messages"]):
        op = "POST /messages (first)" if i == 0 else "POST /messages (next)"
        status, new = c.call(op, "POST", f"{url}/messages", {"text": text})
        state = new if status == 200 else state
    c.call("GET /sessions/{id}", "GET", url)

    for body in ({"option": True}, {"unknown": True}):
        question = state.get("next_question")
        if not question:
            break
        answer: dict[str, Any] = {"question_id": question["question_id"]}
        if "option" in body and question["options"]:
            answer["option_id"] = question["options"][0]["id"]
            op = "POST /answers (option)"
        else:
            answer["unknown"] = True
            op = "POST /answers (unknown)"
        status, new = c.call(op, "POST", f"{url}/answers", answer)
        state = new if status == 200 else state

    def mutate(op: str, path: str, body: dict[str, Any], method: str = "PATCH") -> bool:
        nonlocal state
        status, new = c.call(op, method, path, {"expected_revision": state["revision"], **body})
        if status == 200:
            state = new
        return status == 200

    fact = editable(state)
    if fact:
        value = {
            "characteristic_name": fact["characteristic_name"],
            "raw_value": fact["raw_value"],
            "raw_unit": fact.get("raw_unit"),
            "kind": fact["kind"],
            "component": fact.get("component"),
        }
        mutate("PATCH /facts confirm", f"{url}/facts/{fact['id']}", {"action": "confirm"})
        fact = editable(state)
        if fact and mutate(
            "PATCH /facts edit", f"{url}/facts/{fact['id']}", {"action": "edit", **value}
        ):
            fact = editable(state)
        if fact and mutate("PATCH /facts delete", f"{url}/facts/{fact['id']}", {"action": "delete"}):
            mutate("PATCH /facts restore", f"{url}/facts/{fact['id']}", {"action": "restore"})
        mutate("POST /facts", f"{url}/facts", {"action": "edit", **value}, method="POST")
    mutate("POST /recalculate", f"{url}/recalculate", {}, method="POST")

    proposal = next(iter(state.get("enum_proposals") or []), None)
    if proposal:
        mutate(
            "POST /enum-resolutions",
            f"{url}/enum-resolutions",
            {"proposal_id": proposal["id"], "action": "accept"},
            method="POST",
        )


def percentile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    k = (len(ordered) - 1) * q
    lo, hi = int(k), min(int(k) + 1, len(ordered) - 1)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (k - lo)


def summary(samples: dict[str, list[tuple[float, int]]]) -> list[dict[str, Any]]:
    rows = []
    for op, items in samples.items():
        if op == "warmup":
            continue
        ok = [ms for ms, status in items if status == 200]
        statuses: dict[str, int] = defaultdict(int)
        for _, status in items:
            statuses[str(status)] += 1
        row: dict[str, Any] = {"op": op, "n": len(items), "ok": len(ok), "statuses": statuses}
        if ok:
            row |= {
                "p50": percentile(ok, 0.5),
                "p90": percentile(ok, 0.9),
                "p95": percentile(ok, 0.95),
                "max": max(ok),
                "mean": statistics.fmean(ok),
            }
        rows.append(row)
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--url", default="http://127.0.0.1:18089")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--repeat", type=int, default=30, help="повторы чтения справочника")
    parser.add_argument("--cases", type=int, default=0, help="0 — все кейсы набора")
    parser.add_argument("--timeout", type=float, default=300)
    args = parser.parse_args()

    cases = json.loads(DATASET.read_text())["cases"]
    cases = cases[: args.cases] if args.cases else cases
    c = Client(args.url, args.timeout)
    started = time.time()
    catalog(c, args.repeat)
    search(c, cases)
    for i, case in enumerate(cases, 1):
        session(c, case)
        print(f"\r{i}/{len(cases)} {case['id']}", end="", flush=True)
    print()

    rows = summary(c.samples)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    raw = {op: items for op, items in c.samples.items()}
    report = {"url": args.url, "started": started, "cases": len(cases), "rows": rows, "raw": raw}
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=1))
    print(f"{'операция':32} {'n':>4} {'ok':>4} {'p50':>9} {'p90':>9} {'p95':>9} {'max':>9}")
    for r in rows:
        if "p50" in r:
            print(
                f"{r['op']:32} {r['n']:>4} {r['ok']:>4} {r['p50']:>9.1f} {r['p90']:>9.1f} "
                f"{r['p95']:>9.1f} {r['max']:>9.1f}"
            )
        else:
            print(f"{r['op']:32} {r['n']:>4} {r['ok']:>4}  {dict(r['statuses'])}")


if __name__ == "__main__":
    main()
