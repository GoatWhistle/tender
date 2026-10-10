import asyncio
import json
import os
import pickle
import sys
import time
from pathlib import Path

import aiohttp
import numpy as np

from rag.ktru import iter_records, position_text
from rag.main import embed

DATA = Path(os.environ.get("RAG_DATA", "data"))
ZIP = DATA / "ktru.zip"
POSITIONS = DATA / "positions.pkl"
CODES = DATA / "codes.json"
TEXTS = DATA / "texts.json"
RAW = DATA / "raw.pkl"
VECTORS = DATA / "vectors.npy"
VECTORS_F32 = DATA / "vectors.f32.npy"
DONE = DATA / "vectors.done.npy"

BATCH = int(os.environ.get("EMBED_BATCH", "32"))
CONCURRENCY = int(os.environ.get("EMBED_CONCURRENCY", "8"))


def parse() -> None:
    start = time.perf_counter()
    positions = {}
    raw = {}
    for p, r in iter_records(ZIP):
        positions[p.code] = p
        raw[p.code] = r
        if len(positions) % 5000 == 0:
            print(f"{len(positions)} позиций, {time.perf_counter() - start:.0f}s", flush=True)
    codes = list(positions)
    texts = [position_text(positions[c]) for c in codes]
    if CODES.exists() and TEXTS.exists():
        same = json.loads(CODES.read_text()) == codes and json.loads(TEXTS.read_text()) == texts
        print("коды и тексты совпадают со старыми" if same else "ВНИМАНИЕ: коды или тексты изменились")
    with POSITIONS.open("wb") as f:
        pickle.dump(positions, f, protocol=pickle.HIGHEST_PROTOCOL)
    with RAW.open("wb") as f:
        pickle.dump(raw, f, protocol=pickle.HIGHEST_PROTOCOL)
    CODES.write_text(json.dumps(codes, ensure_ascii=False))
    TEXTS.write_text(json.dumps(texts, ensure_ascii=False))
    lens = sorted(len(t) for t in texts)
    print(
        f"готово: {len(codes)} позиций за {time.perf_counter() - start:.0f}s, "
        f"длина текста p50={lens[len(lens) // 2]} max={lens[-1]} символов"
    )


async def _embed_all(texts: list[str]) -> None:
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=600)) as session:
        probe = await embed(session, texts[:1])
        dim = len(probe.data[0].embedding)
        if VECTORS.exists() and DONE.exists():
            vectors = np.load(VECTORS, mmap_mode="r+")
            done = np.load(DONE)
            if vectors.shape != (len(texts), dim):
                raise RuntimeError(f"vectors.npy {vectors.shape} != {(len(texts), dim)}")
        else:
            vectors = np.lib.format.open_memmap(
                VECTORS, mode="w+", dtype=np.float16, shape=(len(texts), dim)
            )
            done = np.zeros(len(texts), dtype=bool)
        batches = [
            range(i, min(i + BATCH, len(texts)))
            for i in range(0, len(texts), BATCH)
            if not done[i : i + BATCH].all()
        ]
        total = len(batches)
        print(f"dim={dim}, осталось {total} батчей по {BATCH}, уже готово {int(done.sum())}")
        sem = asyncio.Semaphore(CONCURRENCY)
        start = time.perf_counter()
        finished = 0

        async def run(rows: range) -> None:
            nonlocal finished
            async with sem:
                for attempt in range(5):
                    try:
                        resp = await embed(session, [texts[i] for i in rows])
                        break
                    except (TimeoutError, aiohttp.ClientError) as e:
                        if attempt == 4:
                            raise
                        print(f"повтор {rows.start}: {e}", file=sys.stderr)
                        await asyncio.sleep(2**attempt)
            for item in resp.data:
                v = np.asarray(item.embedding, dtype=np.float32)
                vectors[rows.start + item.index] = v / np.linalg.norm(v)
            done[rows.start : rows.stop] = True
            finished += 1
            if finished % 20 == 0 or finished == total:
                vectors.flush()
                np.save(DONE, done)
                rate = finished * BATCH / (time.perf_counter() - start)
                eta = (total - finished) * BATCH / rate
                print(f"{finished}/{total} батчей, {rate:.0f} текстов/с, ETA {eta:.0f}s", flush=True)

        try:
            await asyncio.gather(*(run(b) for b in batches))
        finally:
            vectors.flush()
            np.save(DONE, done)


def embed_index() -> None:
    texts = json.loads(TEXTS.read_text())
    asyncio.run(_embed_all(texts))
    print(f"готово: {VECTORS}")
