"""Заменяемый порт inference; сценарии не импортируют Torch или код модели."""

from collections.abc import Sequence
from typing import Protocol


class PreparedContext(Protocol):
    @property
    def prefix_ids(self) -> tuple[int, ...]: ...

    @property
    def bytes_size(self) -> int: ...

    def release(self) -> None: ...


class Runtime(Protocol):
    @property
    def identity(self) -> str: ...

    def prefix_ids(self, premise: str) -> tuple[int, ...]: ...

    def encode(self, premise: str, hypotheses: Sequence[str]) -> list[list[int]]: ...

    def prepare(self, prefix_ids: Sequence[int]) -> PreparedContext: ...

    def predict(
        self, prepared: PreparedContext | None, sequences: Sequence[Sequence[int]]
    ) -> list[list[float]]: ...

    def close(self) -> None: ...
