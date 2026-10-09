"""TF-IDF char_wb 3–5 и полный перебор по матрице; библиотеки скрыты за портами."""

from collections.abc import Sequence
from typing import Any

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

from app.domain.catalog import Position
from app.domain.errors import ModelFailure
from app.domain.inference import Vector
from app.domain.search import RankedGroup, normalize
from app.domain.search_vectors import (
    DOCUMENT_RECIPE,
    NORMALIZATION,
    SearchVectors,
    group_documents,
)
from app.usecase.interface import Embeddings


class TfidfIndex:
    def build(self, groups: Sequence[Position]) -> None:
        self._groups = sorted(groups, key=lambda p: p.code)
        self._vectorizer = TfidfVectorizer(
            analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True
        )
        self._matrix: Any = None
        if self._groups:
            self._matrix = self._vectorizer.fit_transform(
                [normalize(f"{p.name} {p.name} {p.okpd2_name}") for p in self._groups]
            )

    def rank(self, description: str, category: str | None = None) -> list[RankedGroup]:
        if self._matrix is None:
            return []
        scores = (self._vectorizer.transform([description]) @ self._matrix.T).toarray()[0]
        return sorted(
            [
                RankedGroup(p.code, float(s))
                for p, s in zip(self._groups, scores, strict=True)
                if s > 0 and category in (None, p.category)
            ],
            key=lambda r: (-r.score, r.code),
        )


class MatrixIndex:
    def __init__(self, embeddings: Embeddings, *, model: str, revision: str) -> None:
        self._embeddings = embeddings
        self._model = model
        self._revision = revision

    def build(self, groups: Sequence[Position], saved: SearchVectors | None = None) -> None:
        self._groups = sorted(groups, key=lambda p: p.code)
        documents = group_documents(self._groups)
        if saved is None:
            vectors = self._embeddings.embed_documents([doc.text for doc in documents]).vectors
        else:
            if (
                saved.model != self._model
                or saved.revision != self._revision
                or saved.dimension != self._embeddings.dimension
                or saved.recipe != DOCUMENT_RECIPE
                or saved.normalization != NORMALIZATION
                or saved.documents != documents
                or len(saved.vectors) != len(documents)
                or any(len(v) != saved.dimension for v in saved.vectors)
            ):
                raise ModelFailure("Сохранённые векторы несовместимы; пересоберите базу")
            vectors = saved.vectors
        matrix = np.asarray(vectors, dtype=np.float32)
        if not np.isfinite(matrix).all() or not np.allclose(
            np.linalg.norm(matrix, axis=1), 1, atol=1e-3
        ):
            raise ModelFailure("Сохранённые векторы повреждены; пересоберите базу")
        self._matrix = matrix.reshape((len(self._groups), 2, self._embeddings.dimension))

    def rank(self, query: Vector, category: str | None = None) -> list[RankedGroup]:
        scores = (self._matrix @ np.asarray(query, dtype=np.float32)).max(axis=1)
        return sorted(
            [
                RankedGroup(p.code, float(s))
                for p, s in zip(self._groups, scores, strict=True)
                if category in (None, p.category)
            ],
            key=lambda r: (-r.score, r.code),
        )
