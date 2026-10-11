import asyncio
import time
from collections.abc import Callable
from dataclasses import dataclass

from rag.domain.catalog import position_text
from rag.domain.errors import EmbeddingsFailure
from rag.domain.inference import Vector
from rag.usecase.interface import (
    AnalogsIndex,
    CatalogSource,
    CatalogStore,
    Embeddings,
    SteSource,
    VectorStore,
)

PROGRESS_EVERY = 5000
CHECKPOINT_EVERY = 20
RETRIES = 5

type Report = Callable[[str], None]


@dataclass(frozen=True, slots=True)
class ParseReport:
    positions: int
    seconds: float
    changed: bool | None
    median_chars: int
    max_chars: int


class ParseCatalog:
    def __init__(
        self, source: CatalogSource, store: CatalogStore, report: Report
    ) -> None:
        self._source = source
        self._store = store
        self._report = report

    def run(self) -> ParseReport:
        start = time.perf_counter()
        positions = {}
        raw = {}
        for p, record in self._source.records():
            positions[p.code] = p
            raw[p.code] = record
            if len(positions) % PROGRESS_EVERY == 0:
                self._report(
                    f"{len(positions)} позиций, {time.perf_counter() - start:.0f}s"
                )
        codes = list(positions)
        texts = [position_text(positions[c]) for c in codes]
        previous = self._store.previous()
        changed = None if previous is None else previous != (codes, texts)
        self._store.save(positions, raw, codes, texts)
        lens = sorted(len(t) for t in texts)
        return ParseReport(
            len(codes),
            time.perf_counter() - start,
            changed,
            lens[len(lens) // 2] if lens else 0,
            lens[-1] if lens else 0,
        )


class EmbedCatalog:
    def __init__(
        self,
        embeddings: Embeddings,
        catalog: CatalogStore,
        vectors: VectorStore,
        report: Report,
        batch: int,
        concurrency: int,
    ) -> None:
        self._embeddings = embeddings
        self._catalog = catalog
        self._vectors = vectors
        self._report = report
        self._batch = batch
        self._concurrency = concurrency

    async def run(self) -> None:
        texts = self._catalog.texts()
        [probe] = await self._embeddings.embed_documents(texts[:1])
        done = self._vectors.open(len(texts), len(probe))
        batches = [
            range(i, min(i + self._batch, len(texts)))
            for i in range(0, len(texts), self._batch)
            if not all(done[i : i + self._batch])
        ]
        total = len(batches)
        self._report(
            f"dim={len(probe)}, осталось {total} батчей по {self._batch}, "
            f"уже готово {sum(done)}"
        )
        sem = asyncio.Semaphore(self._concurrency)
        start = time.perf_counter()
        finished = 0

        async def embed(rows: range) -> None:
            nonlocal finished
            async with sem:
                vectors = await self._retry(rows, [texts[i] for i in rows])
            self._vectors.write(rows.start, vectors)
            finished += 1
            if finished % CHECKPOINT_EVERY == 0 or finished == total:
                self._vectors.checkpoint()
                rate = finished * self._batch / (time.perf_counter() - start)
                eta = (total - finished) * self._batch / rate
                self._report(
                    f"{finished}/{total} батчей, {rate:.0f} текстов/с, ETA {eta:.0f}s"
                )

        try:
            await asyncio.gather(*(embed(b) for b in batches))
        finally:
            self._vectors.checkpoint()
            await self._embeddings.aclose()

    async def _retry(self, rows: range, texts: list[str]) -> list[Vector]:
        for attempt in range(RETRIES):
            try:
                return await self._embeddings.embed_documents(texts)
            except EmbeddingsFailure as e:
                if attempt == RETRIES - 1:
                    raise
                self._report(f"повтор {rows.start}: {e}")
                await asyncio.sleep(2**attempt)
        raise AssertionError


class BuildAnalogs:
    def __init__(
        self, source: SteSource, analogs: AnalogsIndex, report: Report
    ) -> None:
        self._source = source
        self._analogs = analogs
        self._report = report

    def run(self) -> int:
        start = time.perf_counter()
        items = list(self._source.items())
        self._report(f"{len(items)} СТЕ, {time.perf_counter() - start:.0f}s")
        self._analogs.rebuild(items)
        return len(items)
