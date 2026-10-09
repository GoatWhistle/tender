"""Векторный поиск полным перебором по матрице — реализация порта `VectorIndex`.

Векторы единичной длины, поэтому косинус — скалярное произведение. Скор ключа — максимум по его
векторам. Справочник — сотни групп: перебор быстрее, чем построение ANN-индекса.
"""

from collections.abc import Collection, Sequence

import numpy as np

from app.domain.inference import Vector
from app.domain.search import Hit


class NumpyVectorIndex:
    def __init__(self) -> None:
        self._keys: list[str] = []
        self._owners = np.zeros(0, dtype=np.intp)  # номер ключа для каждой строки матрицы
        self._matrix = np.zeros((0, 0), dtype=np.float32)

    def build(self, documents: Sequence[tuple[str, Vector]]) -> None:
        ordered = sorted(documents, key=lambda d: d[0])  # устойчиво: порядок векторов ключа тот же
        self._keys = sorted({key for key, _ in ordered})
        index = {key: i for i, key in enumerate(self._keys)}
        self._owners = np.array([index[key] for key, _ in ordered], dtype=np.intp)
        dimension = len(ordered[0][1]) if ordered else 0
        self._matrix = np.array([v for _, v in ordered], dtype=np.float32).reshape(
            len(ordered), dimension
        )

    def search(self, query: Vector, keys: Collection[str] | None = None) -> list[Hit]:
        if not self._keys:
            return []
        cosines = self._matrix @ np.asarray(query, dtype=np.float32)
        best = np.full(len(self._keys), -np.inf, dtype=np.float32)
        np.maximum.at(best, self._owners, cosines)
        hits = [
            Hit(key, float(score))
            for key, score in zip(self._keys, best, strict=True)
            if keys is None or key in keys
        ]
        return sorted(hits, key=lambda h: (-h.score, h.key))
