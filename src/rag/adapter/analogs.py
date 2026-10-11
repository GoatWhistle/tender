import pickle
import threading
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from sklearn.feature_extraction.text import TfidfVectorizer

from rag.domain.suggestions import SteItem

ANALOGS = 300
MIN_SCORE = 0.2


class TfidfAnalogs:
    def __init__(
        self, path: Path, limit: int = ANALOGS, min_score: float = MIN_SCORE
    ) -> None:
        self._path = path
        self._limit = limit
        self._min_score = min_score
        self._loaded: dict[str, Any] | None = None
        self._lock = threading.Lock()

    def _index(self) -> dict[str, Any] | None:
        with self._lock:
            if self._loaded is None and self._path.exists():
                self._loaded = pickle.loads(self._path.read_bytes())
            return self._loaded

    def warm(self) -> None:
        self._index()

    def nearest(self, text: str) -> list[SteItem]:
        ste = self._index()
        if ste is None:
            return []
        scores = (
            (ste["matrix"] @ ste["vectorizer"].transform([text.lower()]).T)
            .toarray()
            .ravel()
        )
        top = [
            i
            for i in scores.argsort()[::-1][: self._limit]
            if scores[i] > self._min_score
        ]
        return [SteItem(*ste["items"][i]) for i in top]

    def rebuild(self, items: Sequence[SteItem]) -> None:
        vectorizer = TfidfVectorizer(
            analyzer="char_wb", ngram_range=(3, 5), min_df=2, max_features=400_000
        )
        matrix = vectorizer.fit_transform(item.title.lower() for item in items)
        rows = [(item.title, item.characteristics) for item in items]
        self._path.write_bytes(
            pickle.dumps({"items": rows, "vectorizer": vectorizer, "matrix": matrix})
        )
        with self._lock:
            self._loaded = None
