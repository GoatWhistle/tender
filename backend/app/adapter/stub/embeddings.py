"""Детерминированные эмбеддинги без модели — реализация порта `Embeddings`.

Хеширование слов: каждое слово текста добавляет ±1 в свою координату, вектор нормируется. Один
и тот же текст — один и тот же вектор; тексты с общими словами ближе, поэтому гибридный поиск
проверяется на заглушке целиком.
"""

import hashlib
import math
import re
from collections.abc import Sequence

from app.adapter.stub.fault import Scripted
from app.domain.inference import EmbeddingBatch, Vector


class StubEmbeddings(Scripted):
    model = "stub-embeddings"

    def __init__(self, dimension: int = 64, revision: str = "stub-1") -> None:
        if dimension < 1:
            raise ValueError(f"размерность заглушки {dimension}, нужна ≥ 1")
        super().__init__(revision)
        self._dimension = dimension
        self.reply: EmbeddingBatch | None = None  # ответ вместо вычисленного, в т.ч. невалидный

    @property
    def dimension(self) -> int:
        return self._dimension

    def embed(self, texts: Sequence[str]) -> EmbeddingBatch:
        self._raise_fault()
        if self.reply is not None:
            return self.reply
        return EmbeddingBatch(vectors=tuple(self._vector(t) for t in texts), revision=self.revision)

    def _vector(self, text: str) -> Vector:
        counts = [0.0] * self._dimension
        # Текст без слов (пустой, из знаков) — одна «пустая» лексема, чтобы вектор не был нулевым.
        for word in re.findall(r"\w+", text.lower()) or [""]:
            digest = hashlib.sha256(word.encode()).digest()
            index = int.from_bytes(digest[:4], "big") % self._dimension
            counts[index] += 1.0 if digest[4] % 2 else -1.0
        if not any(counts):
            # Слова с противоположными знаками в одной координате взаимно погасились.
            counts[0] = 1.0
        norm = math.sqrt(sum(x * x for x in counts))
        return tuple(x / norm for x in counts)
