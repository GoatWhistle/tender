"""Лексический поиск TF-IDF на символьных n-граммах — реализация порта `LexicalIndex`.

Параметры — как в smoke-замере (`evals/smoke/bench_emb.py`): `char_wb` 3–5, `sublinear_tf`.
Скор — косинус: векторы TF-IDF scikit-learn нормированы по L2.
"""

from collections.abc import Collection, Mapping
from typing import Any

from sklearn.feature_extraction.text import TfidfVectorizer

from app.domain.search import Hit


class TfidfLexicalIndex:
    def __init__(self) -> None:
        self._keys: list[str] = []
        self._vectorizer: Any = None
        self._matrix: Any = None

    def build(self, documents: Mapping[str, str]) -> None:
        keys = sorted(documents)
        vectorizer = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True)
        self._matrix = vectorizer.fit_transform([documents[k] for k in keys]) if keys else None
        self._vectorizer, self._keys = vectorizer, keys

    def search(self, query: str, keys: Collection[str] | None = None) -> list[Hit]:
        if self._matrix is None:
            return []
        scores = (self._vectorizer.transform([query]) @ self._matrix.T).toarray()[0]
        hits = [
            Hit(key, float(score))
            for key, score in zip(self._keys, scores, strict=True)
            if score > 0 and (keys is None or key in keys)
        ]
        return sorted(hits, key=lambda h: (-h.score, h.key))
