"""Снимок групп при старте и RRF-поиск без зависимости от библиотек индексов."""

import re
from dataclasses import dataclass, field, replace

from app.domain.aliases import Alias
from app.domain.catalog import Position
from app.domain.errors import CatalogEmpty, ModelFailure, ModelNotConfigured
from app.domain.inference import ModelHealth
from app.domain.search import MethodContribution, SearchHit, SearchResult, normalize
from app.usecase.interface import (
    AliasesRepository,
    CatalogRepository,
    Embeddings,
    LexicalIndex,
    SearchVectorsRepository,
    UnitOfWork,
    VectorIndex,
)


@dataclass
class SearchSnapshot:
    groups: dict[str, Position] = field(default_factory=dict)
    aliases: tuple[Alias, ...] = ()
    failure: ModelFailure | None = None
    positions: dict[str, Position] = field(default_factory=dict)


class GroupSearch:
    def __init__(
        self,
        uow: UnitOfWork,
        catalog: CatalogRepository,
        snapshot: SearchSnapshot,
        lexical: LexicalIndex | None,
        vector: VectorIndex | None,
        embeddings: Embeddings | None,
        aliases: AliasesRepository | None = None,
        saved_vectors: SearchVectorsRepository | None = None,
    ) -> None:
        self._uow = uow
        self._catalog = catalog
        self._snapshot = snapshot
        self._lexical = lexical
        self._vector = vector
        self._embeddings = embeddings
        self._aliases = aliases
        self._saved_vectors = saved_vectors

    def build(self) -> None:
        with self._uow:
            groups = self._catalog.groups()
            self._snapshot.aliases = (
                tuple(a for a in self._aliases.all() if a.reviewed)
                if self._aliases is not None
                else ()
            )
            self._snapshot.positions = {p.code: p for p in self._catalog.positions()}
        self._snapshot.groups = {p.code: p for p in groups}
        if self._embeddings is None or not groups:
            return
        assert self._lexical is not None and self._vector is not None
        try:
            self._lexical.build(groups)
            with self._uow:
                saved = self._saved_vectors.load() if self._saved_vectors is not None else None
            self._vector.build(groups, saved)
        except ModelFailure as exc:
            self._snapshot.failure = exc

    def health(self) -> ModelHealth:
        if self._embeddings is None:
            return ModelHealth("модель не настроена", "", False)
        try:
            health = self._embeddings.health()
        except ModelFailure:
            return ModelHealth("модель недоступна", "", False)
        return ModelHealth(
            health.model,
            health.revision,
            health.ready and bool(self._snapshot.groups) and self._snapshot.failure is None,
        )

    def run(self, description: str, category: str | None = None, limit: int = 10) -> SearchResult:
        if self._embeddings is None:
            raise ModelNotConfigured()
        if self._snapshot.failure is not None:
            raise self._snapshot.failure
        if not self._snapshot.groups:
            raise CatalogEmpty()
        assert self._lexical is not None and self._vector is not None
        text = normalize(description)
        query = self._embeddings.embed_queries([text]).vectors[0]
        lexical = {r.code: i for i, r in enumerate(self._lexical.rank(text, category), 1)}
        vector = {r.code: i for i, r in enumerate(self._vector.rank(query, category), 1)}
        matched = sorted(
            (
                a
                for a in self._snapshot.aliases
                if a.group_code in self._snapshot.groups
                and category in (None, self._snapshot.groups[a.group_code].category)
                and re.search(r"(?<!\w)" + re.escape(normalize(a.alias)) + r"(?!\w)", text)
            ),
            key=lambda a: (-len(normalize(a.alias)), a.group_code, a.alias),
        )
        alias_codes = list(dict.fromkeys(a.group_code for a in matched))
        synonym = {code: i for i, code in enumerate(alias_codes, 1)}
        hits = [
            SearchHit(
                p,
                MethodContribution.of(lexical.get(p.code)),
                MethodContribution.of(vector.get(p.code)),
                MethodContribution.of(synonym.get(p.code)),
            )
            for p in self._snapshot.groups.values()
            if category in (None, p.category)
        ]
        hits.sort(key=lambda h: (-h.score, h.group.code))
        messages: list[str] = []
        exact: list[str] = []
        for code in dict.fromkeys(
            re.findall(r"(?<![\w.-])\d{2}\.\d{2}\.\d{2}\.\d{3}-\d{8}(?![\w.-])", text)
        ):
            position = self._snapshot.positions.get(code)
            if position is None:
                messages.append(f"Код КТРУ {code} не найден; выполнен поиск по описанию")
            elif position.group not in self._snapshot.groups:
                messages.append(f"Группа для кода КТРУ {code} отсутствует в справочнике")
            elif category not in (None, position.category):
                messages.append(f"Код КТРУ {code} вне выбранной категории")
            elif position.group not in exact:
                exact.append(position.group)
        promoted = [
            replace(h, found_by="code") for code in exact for h in hits if h.group.code == code
        ]
        hits = promoted + [h for h in hits if h.group.code not in exact]
        return SearchResult(description, tuple(hits[:limit]), tuple(messages))
