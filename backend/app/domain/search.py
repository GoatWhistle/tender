"""Результаты ранжирования и объяснения гибридного поиска."""

from dataclasses import dataclass

from app.domain.catalog import Position


def normalize(text: str) -> str:
    return " ".join(text.lower().replace("ё", "е").split())


@dataclass(frozen=True)
class RankedGroup:
    code: str
    score: float


@dataclass(frozen=True)
class MethodContribution:
    rank: int | None
    contribution: float

    @classmethod
    def of(cls, rank: int | None) -> "MethodContribution":
        return cls(rank, 0.0 if rank is None else 1 / (60 + rank))


@dataclass(frozen=True)
class SearchHit:
    group: Position
    lexical: MethodContribution
    vector: MethodContribution
    synonym: MethodContribution
    found_by: str = "description"

    @property
    def score(self) -> float:
        return self.lexical.contribution + self.vector.contribution + self.synonym.contribution


@dataclass(frozen=True)
class SearchResult:
    description: str
    groups: tuple[SearchHit, ...]
    messages: tuple[str, ...] = ()
