import json
from pathlib import Path

import numpy as np

from rag.domain.errors import IndexNotReady
from rag.domain.inference import Vector
from rag.domain.search import Scored

BLOCK = 4096


class NumpyVectorIndex:
    def __init__(
        self, vectors: Path, codes: Path, f32_cache: Path | None = None
    ) -> None:
        self._vectors = np.load(vectors, mmap_mode="r", allow_pickle=False)
        if (
            f32_cache is not None
            and f32_cache.exists()
            and f32_cache.stat().st_mtime >= vectors.stat().st_mtime
        ):
            try:
                cached = np.load(f32_cache, mmap_mode="r", allow_pickle=False)
                if cached.shape == self._vectors.shape and cached.dtype == np.float32:
                    self._vectors = cached
            except (OSError, ValueError):
                pass
        self._codes: list[str] = json.loads(codes.read_text())
        if len(self._codes) != len(self._vectors):
            raise IndexNotReady(
                f"codes.json {len(self._codes)} != vectors.npy {len(self._vectors)}"
            )

    def nearest(self, query: Vector, limit: int) -> list[Scored]:
        q = np.asarray(query, dtype=np.float32)
        q /= np.linalg.norm(q)
        scores = np.empty(len(self._vectors), dtype=np.float32)
        for start in range(0, len(self._vectors), BLOCK):
            block = self._vectors[start : start + BLOCK].astype(np.float32, copy=False)
            scores[start : start + len(block)] = block @ q
        limit = min(limit, len(scores) - 1)
        top = np.argpartition(-scores, limit)[:limit]
        top = top[np.argsort(-scores[top])]
        return [Scored(int(i), self._codes[i], float(scores[i])) for i in top]


class MissingVectorIndex:
    def nearest(self, query: Vector, limit: int) -> list[Scored]:
        raise IndexNotReady()
