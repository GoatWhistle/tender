"""Сохранённый снимок документов групп и его совместимость с моделью."""

from collections.abc import Sequence
from dataclasses import dataclass, field

from app.domain.catalog import Position
from app.domain.inference import Vector
from app.domain.search import normalize

DOCUMENT_RECIPE = "group-name-and-okpd2-v1"
NORMALIZATION = "L2"


@dataclass(frozen=True)
class SearchDocument:
    group_code: str
    ordinal: int
    text: str


def group_documents(groups: Sequence[Position]) -> tuple[SearchDocument, ...]:
    return tuple(
        SearchDocument(p.code, ordinal, normalize(text))
        for p in sorted(groups, key=lambda p: p.code)
        for ordinal, text in enumerate((p.name, f"{p.name}. {p.okpd2_name}"))
    )


@dataclass(frozen=True)
class SearchVectors:
    model: str
    revision: str
    dimension: int
    documents: tuple[SearchDocument, ...]
    vectors: tuple[Vector, ...]
    recipe: str = DOCUMENT_RECIPE
    normalization: str = NORMALIZATION
    provenance: dict[str, str] = field(default_factory=dict)
