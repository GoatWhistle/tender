"""Документы, компактные float32-векторы и метаданные одного снимка."""

from sqlalchemy import JSON, ForeignKey, LargeBinary, String
from sqlalchemy.orm import Mapped, mapped_column

from app.repository.database import Base


class SearchVectorMetadata(Base):
    __tablename__ = "search_vector_metadata"

    id: Mapped[int] = mapped_column(primary_key=True)
    model: Mapped[str]
    revision: Mapped[str]
    dimension: Mapped[int]
    recipe: Mapped[str]
    normalization: Mapped[str]
    provenance: Mapped[dict[str, str]] = mapped_column(JSON)


class GroupSearchVector(Base):
    __tablename__ = "group_search_vectors"

    group_code: Mapped[str] = mapped_column(
        String(64), ForeignKey("positions.code", ondelete="CASCADE"), primary_key=True
    )
    ordinal: Mapped[int] = mapped_column(primary_key=True)
    text: Mapped[str]
    vector: Mapped[bytes] = mapped_column(LargeBinary)
