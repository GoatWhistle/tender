import json
import time
from dataclasses import asdict

from rag.domain.catalog import value_text
from rag.domain.inference import total_cost
from rag.usecase.correction import Corrector
from rag.usecase.indexing import ParseReport
from rag.usecase.rerank import Reranker, build_prompt
from rag.usecase.search import PositionSearch


def print_parse(report: ParseReport) -> None:
    if report.changed is not None:
        print(
            "ВНИМАНИЕ: коды или тексты изменились"
            if report.changed
            else "коды и тексты совпадают со старыми"
        )
    print(
        f"готово: {report.positions} позиций за {report.seconds:.0f}s, "
        f"длина текста p50={report.median_chars} max={report.max_chars} символов"
    )


async def fix(corrector: Corrector, text: str) -> None:
    t0 = time.perf_counter()
    corrected = await corrector.run(text)
    usage = corrected.usage
    sdk = f" model={usage.duration_ms / 1000:.1f}s" if usage else ""
    print(f"{time.perf_counter() - t0:.1f}s{sdk} cost=${total_cost(usage):.4f}")
    print(
        json.dumps(
            {
                "original": corrected.original,
                "corrected": corrected.corrected,
                "fixes": [asdict(f) for f in corrected.fixes],
                "issues": corrected.issues,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


async def search(positions: PositionSearch, text: str) -> None:
    t0 = time.perf_counter()
    hits = await positions.semantic(text)
    print(f"search={time.perf_counter() - t0:.2f}s\n")
    for n, h in enumerate(hits, 1):
        p = h.position
        print(
            f"{n:2}. {h.score:.3f} [{h.row}] {p.code} {p.name} (вариантов: {h.siblings})"
        )
        print(f"    ОКПД2 {p.okpd2} {p.okpd2_name}")
        for c in p.characteristics:
            if c.required:
                values = "; ".join(
                    t for t in (value_text(v) for v in c.values[:5]) if t
                )
                print(f"    * {c.name}: {values}")


async def rerank(
    corrector: Corrector, positions: PositionSearch, reranker: Reranker, raw: str
) -> None:
    t0 = time.perf_counter()
    corrected = await corrector.run(raw)
    text = corrected.corrected
    t1 = time.perf_counter()
    hits = await positions.semantic(text)
    t2 = time.perf_counter()
    out = await reranker.run(text, hits)
    t3 = time.perf_counter()
    print(
        f"fix={t1 - t0:.1f}s search={t2 - t1:.1f}s rerank={t3 - t2:.1f}s "
        f"cost=${total_cost(corrected.usage, out.usage):.4f}"
    )
    if corrected.fixes:
        print(f"исправлено: {text}")
        for f in corrected.fixes:
            print(f"  [{f.kind}] {f.before} → {f.after}")
    for issue in corrected.issues:
        print(f"  ! {issue}")
    print()
    before = {id(h): n for n, h in enumerate(hits, 1)}
    for n, rk in enumerate(out.ranked, 1):
        p = rk.hit.position
        print(
            f"{n:2}. {rk.relevance:3} (было {before[id(rk.hit)]:2}, cos {rk.hit.score:.3f}) "
            f"{p.code} {p.name}"
        )
        print(f"     {rk.reason}")
    print(json.dumps({"prompt_chars": len(build_prompt(text, hits))}))
