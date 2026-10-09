"""Снимок в SQLite; бинарный формат — little-endian float32, без pickle."""

import struct

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.domain.errors import ModelFailure
from app.domain.search_vectors import SearchDocument, SearchVectors
from app.repository.orm.search_vectors import GroupSearchVector, SearchVectorMetadata


class SqlSearchVectors:
    def __init__(self, session: Session) -> None:
        self._session = session

    def load(self) -> SearchVectors | None:
        metadata = self._session.get(SearchVectorMetadata, 1)
        if metadata is None:
            if self._session.scalar(select(GroupSearchVector).limit(1)) is not None:
                raise ModelFailure("Отсутствуют метаданные векторов; пересоберите базу")
            return None
        rows = list(
            self._session.scalars(
                select(GroupSearchVector).order_by(
                    GroupSearchVector.group_code, GroupSearchVector.ordinal
                )
            )
        )
        try:
            vectors = tuple(struct.unpack(f"<{metadata.dimension}f", row.vector) for row in rows)
        except struct.error as exc:
            raise ModelFailure("Повреждён сохранённый снимок векторов; пересоберите базу") from exc
        return SearchVectors(
            metadata.model,
            metadata.revision,
            metadata.dimension,
            tuple(SearchDocument(row.group_code, row.ordinal, row.text) for row in rows),
            vectors,
            metadata.recipe,
            metadata.normalization,
            metadata.provenance,
        )

    def replace(self, snapshot: SearchVectors | None) -> None:
        self._session.execute(delete(GroupSearchVector))
        self._session.execute(delete(SearchVectorMetadata))
        if snapshot is None:
            return
        self._session.add(
            SearchVectorMetadata(
                id=1,
                model=snapshot.model,
                revision=snapshot.revision,
                dimension=snapshot.dimension,
                recipe=snapshot.recipe,
                normalization=snapshot.normalization,
                provenance=snapshot.provenance,
            )
        )
        self._session.add_all(
            GroupSearchVector(
                group_code=doc.group_code,
                ordinal=doc.ordinal,
                text=doc.text,
                vector=struct.pack(f"<{snapshot.dimension}f", *vector),
            )
            for doc, vector in zip(snapshot.documents, snapshot.vectors, strict=True)
        )
