import json
import pickle
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from rag.domain.catalog import Position
from rag.domain.errors import IndexNotReady
from rag.domain.inference import Vector


@dataclass(frozen=True, slots=True)
class IndexFiles:
    root: Path

    @property
    def ktru_zip(self) -> Path:
        return self.root / "ktru.zip"

    @property
    def positions(self) -> Path:
        return self.root / "positions.pkl"

    @property
    def raw(self) -> Path:
        return self.root / "raw.pkl"

    @property
    def codes(self) -> Path:
        return self.root / "codes.json"

    @property
    def texts(self) -> Path:
        return self.root / "texts.json"

    @property
    def vectors(self) -> Path:
        return self.root / "vectors.npy"

    @property
    def vectors_f32(self) -> Path:
        return self.root / "vectors.f32.npy"

    @property
    def done(self) -> Path:
        return self.root / "vectors.done.npy"

    @property
    def ste(self) -> Path:
        return self.root / "ste.pkl"

    @property
    def ste_source(self) -> Path:
        return self.root / "ste"

    @property
    def ready(self) -> bool:
        return all(p.exists() for p in (self.codes, self.positions, self.vectors))


class FileCatalog:
    def __init__(self, files: IndexFiles) -> None:
        with files.positions.open("rb") as f:
            self._positions: dict[str, Position] = pickle.load(f)
        self._children: dict[str, list[str]] = {}
        for p in self._positions.values():
            if p.parent:
                self._children.setdefault(p.parent, []).append(p.code)
        self._names = [(p.code, p.name.lower()) for p in self._positions.values()]

    @property
    def ready(self) -> bool:
        return True

    def positions(self) -> Mapping[str, Position]:
        return self._positions

    def position(self, code: str) -> Position | None:
        return self._positions.get(code)

    def leaves(self, p: Position) -> list[Position]:
        group = p.parent if p.parent in self._positions else p.code
        kids = sorted(self._children.get(group, []))
        return [self._positions[c] for c in kids] or [self._positions[group]]

    def names(self) -> Sequence[tuple[str, str]]:
        return self._names


class MissingCatalog:
    @property
    def ready(self) -> bool:
        return False

    def positions(self) -> Mapping[str, Position]:
        raise IndexNotReady()

    def position(self, code: str) -> Position | None:
        raise IndexNotReady()

    def leaves(self, p: Position) -> list[Position]:
        raise IndexNotReady()

    def names(self) -> Sequence[tuple[str, str]]:
        raise IndexNotReady()


class FileCatalogStore:
    def __init__(self, files: IndexFiles) -> None:
        self._files = files

    def previous(self) -> tuple[list[str], list[str]] | None:
        if not self._files.codes.exists() or not self._files.texts.exists():
            return None
        return json.loads(self._files.codes.read_text()), json.loads(
            self._files.texts.read_text()
        )

    def save(
        self,
        positions: Mapping[str, Position],
        raw: Mapping[str, dict[str, Any]],
        codes: list[str],
        texts: list[str],
    ) -> None:
        self._files.root.mkdir(parents=True, exist_ok=True)
        with self._files.positions.open("wb") as f:
            pickle.dump(dict(positions), f, protocol=pickle.HIGHEST_PROTOCOL)
        with self._files.raw.open("wb") as f:
            pickle.dump(dict(raw), f, protocol=pickle.HIGHEST_PROTOCOL)
        self._files.codes.write_text(json.dumps(codes, ensure_ascii=False))
        self._files.texts.write_text(json.dumps(texts, ensure_ascii=False))

    def texts(self) -> list[str]:
        return json.loads(self._files.texts.read_text())


class NpyVectorStore:
    def __init__(self, files: IndexFiles) -> None:
        self._files = files
        self._vectors: np.ndarray | None = None
        self._done: np.ndarray | None = None

    def open(self, rows: int, dimension: int) -> Sequence[bool]:
        if self._files.vectors.exists() and self._files.done.exists():
            vectors = np.load(self._files.vectors, mmap_mode="r+")
            done = np.load(self._files.done)
            if vectors.shape != (rows, dimension):
                raise RuntimeError(
                    f"vectors.npy {vectors.shape} != {(rows, dimension)}"
                )
        else:
            vectors = np.lib.format.open_memmap(
                self._files.vectors,
                mode="w+",
                dtype=np.float16,
                shape=(rows, dimension),
            )
            done = np.zeros(rows, dtype=bool)
        self._vectors, self._done = vectors, done
        return done.tolist()

    def write(self, start: int, vectors: Sequence[Vector]) -> None:
        assert self._vectors is not None and self._done is not None
        self._vectors[start : start + len(vectors)] = np.asarray(
            vectors, dtype=np.float32
        )
        self._done[start : start + len(vectors)] = True

    def checkpoint(self) -> None:
        if self._vectors is None or self._done is None:
            return
        self._vectors.flush()
        np.save(self._files.done, self._done)
