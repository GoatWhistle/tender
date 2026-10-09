"""Построение сохранённого снимка через проверенный порт эмбеддингов."""

from app.domain.errors import CatalogEmpty, ModelFailure
from app.domain.search_vectors import SearchVectors, group_documents
from app.usecase.interface import (
    CatalogRepository,
    Embeddings,
    SearchVectorsRepository,
    UnitOfWork,
)


class BuildSearchVectors:
    def __init__(
        self,
        uow: UnitOfWork,
        catalog: CatalogRepository,
        repository: SearchVectorsRepository,
        embeddings: Embeddings,
    ) -> None:
        self._uow = uow
        self._catalog = catalog
        self._repository = repository
        self._embeddings = embeddings

    def run(self, provenance: dict[str, str] | None = None) -> SearchVectors:
        with self._uow:
            documents = group_documents(self._catalog.groups())
        if not documents:
            raise CatalogEmpty()
        health = self._embeddings.health()
        if not health.ready:
            raise ModelFailure()
        batch = self._embeddings.embed_documents([doc.text for doc in documents])
        if batch.revision != health.revision:
            raise ModelFailure("Ревизия модели изменилась при построении снимка")
        snapshot = SearchVectors(
            health.model,
            batch.revision,
            self._embeddings.dimension,
            documents,
            batch.vectors,
            provenance=provenance or {},
        )
        with self._uow:
            if documents != group_documents(self._catalog.groups()):
                raise ModelFailure("Справочник изменился при построении снимка")
            self._repository.replace(snapshot)
        return snapshot
