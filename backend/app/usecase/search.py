"""Поиск групп КТРУ по описанию товара (`docs/search.md`).

Три ранжированных списка — лексический (TF-IDF), векторный (эмбеддинги) и совпавшие синонимы —
сливаются reciprocal rank fusion: слагаемое метода `WEIGHTS[метод] / (RRF_K + ранг)`, метод без
попадания даёт 0, итоговый скор — сумма слагаемых. Код КТРУ из текста ставит свою группу первой.

Индекс групп строится один раз на процесс, при старте после загрузки справочника
(`GroupSearch.warm`): справочник, загруженный позже, поиск увидит после перезапуска. Пока
справочник пуст или модель не ответила, индекс не построен и каждый поиск пробует снова.
"""

import re
import threading
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

from app.domain.catalog import Position
from app.domain.errors import CatalogEmpty, ModelFailure
from app.domain.search import (
    Alias,
    Contribution,
    FoundBy,
    GroupMatch,
    Hit,
    Method,
    SearchMessage,
    SearchResult,
    find_ktru_codes,
    normalize,
    phrase_pattern,
)
from app.usecase.interface import (
    AliasRepository,
    CatalogRepository,
    Embeddings,
    LexicalIndex,
    UnitOfWork,
    VectorIndex,
)

RRF_K = 60
# Вес слагаемого метода. Проверенный синоним — курируемое знание, а не похожесть: с весом 1 он
# проигрывает группе, которую нашли и TF-IDF, и вектор (2/61), и не выводит на свою группу даже в
# top-5 (`evals/reports/2026-10-10-search-qwen3-embedding.md`). Вес 2 — наименьший, при котором
# совпавший синоним ставит группу выше.
WEIGHTS = {Method.lexical: 1.0, Method.vector: 1.0, Method.alias: 2.0}
DEFAULT_LIMIT = 10
MAX_LIMIT = 50
# После сбоя модели при сборке индекса следующая попытка — не раньше: запросы не стоят в очереди
# за блокировкой к лежащей модели, а сразу получают ту же ошибку.
RETRY_AFTER = 30.0


@dataclass(frozen=True)
class SearchQuery:
    text: str
    category: str | None = None  # жёсткий фильтр; без него — по всем категориям
    limit: int = DEFAULT_LIMIT


# Тексты документов — как в smoke-замере #5 (`evals/smoke/bench_emb.py`), чтобы сравнение было
# честным.


def lexical_document(group: Position) -> str:
    return normalize(f"{group.name} {group.name} {group.okpd2_name}")


def vector_documents(group: Position) -> tuple[str, str]:
    return group.name, f"{group.name}. {group.okpd2_name}"


def fuse(rankings: Mapping[Method, Sequence[Hit]]) -> dict[str, tuple[Contribution, ...]]:
    """RRF: вклад каждого метода в каждый ключ, попавший хотя бы в один список."""
    ranks = {m: {hit.key: i for i, hit in enumerate(hits, start=1)} for m, hits in rankings.items()}
    keys = sorted({key for by_key in ranks.values() for key in by_key})
    return {key: tuple(_contribution(m, ranks[m].get(key)) for m in rankings) for key in keys}


def _contribution(method: Method, rank: int | None) -> Contribution:
    return Contribution(method, rank, 0.0 if rank is None else WEIGHTS[method] / (RRF_K + rank))


class GroupIndex:
    """Индекс групп процесса: документы групп в лексическом и векторном индексах и проверенные
    синонимы. Строится детерминированно: одинаковые справочник и словарь — одинаковый индекс."""

    def __init__(
        self,
        lexical: LexicalIndex,
        vector: VectorIndex,
        embeddings: Embeddings,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.lexical = lexical
        self.vector = vector
        self.embeddings = embeddings
        self.clock = clock
        self.groups: dict[str, Position] = {}
        # (шаблон нормализованного синонима, его длина, код группы)
        self.aliases: tuple[tuple[re.Pattern[str], int, str], ...] = ()
        self.failure: tuple[float, ModelFailure] | None = None  # последний сбой сборки
        self.lock = threading.Lock()

    @property
    def built(self) -> bool:
        return bool(self.groups)

    def build(self, groups: Sequence[Position], aliases: Sequence[Alias]) -> None:
        groups = sorted(groups, key=lambda g: g.code)
        texts = [(g.code, text) for g in groups for text in vector_documents(g)]
        batch = self.embeddings.embed_documents([text for _, text in texts])
        self.lexical.build({g.code: lexical_document(g) for g in groups})
        self.vector.build([(code, v) for (code, _), v in zip(texts, batch.vectors, strict=True)])
        by_code = {g.code: g for g in groups}
        reviewed = sorted({(normalize(a.alias), a.group_code) for a in aliases if a.reviewed})
        self.aliases = tuple((phrase_pattern(alias), len(alias), code) for alias, code in reviewed)
        self.groups = by_code


class GroupSearch:
    def __init__(
        self,
        uow: UnitOfWork,
        catalog: CatalogRepository,
        aliases: AliasRepository,
        index: GroupIndex,
    ) -> None:
        self._uow = uow
        self._catalog = catalog
        self._aliases = aliases
        self._index = index

    def warm(self) -> None:
        """Строит индекс, если он ещё не построен; пустой справочник — `CatalogEmpty`. Сбой
        модели повторяется без новой попытки, пока не прошло `RETRY_AFTER` секунд."""
        index = self._index
        with index.lock:
            if index.built:
                return
            if index.failure is not None and index.clock() - index.failure[0] < RETRY_AFTER:
                raise index.failure[1]
            with self._uow:
                groups = self._catalog.groups()
                aliases = self._aliases.aliases()
            if not groups:
                raise CatalogEmpty()
            try:
                index.build(groups, aliases)
            except ModelFailure as error:
                index.failure = (index.clock(), error)
                raise
            index.failure = None

    def search(self, query: SearchQuery) -> SearchResult:
        self.warm()
        index = self._index
        allowed = {
            code
            for code, g in index.groups.items()
            if query.category is None or g.category == query.category
        }
        by_code, messages = self._by_code(query, allowed)

        text = normalize(query.text)
        (vector,) = index.embeddings.embed_queries([" ".join(query.text.split())]).vectors
        contributions = fuse(
            {
                Method.lexical: index.lexical.search(text, allowed),
                Method.vector: index.vector.search(vector, allowed),
                Method.alias: self._alias_hits(text, allowed),
            }
        )

        def match(code: str, found_by: FoundBy) -> GroupMatch:
            methods = contributions.get(code) or tuple(_contribution(m, None) for m in Method)
            score = sum(c.score for c in methods)
            return GroupMatch(index.groups[code], score, methods, found_by)

        described = sorted(
            (match(code, FoundBy.description) for code in contributions if code not in by_code),
            key=lambda m: (-m.score, m.group.code),
        )
        found = [match(code, FoundBy.code) for code in by_code] + described
        return SearchResult(tuple(found[: query.limit]), tuple(messages))

    def _by_code(
        self, query: SearchQuery, allowed: set[str]
    ) -> tuple[list[str], list[SearchMessage]]:
        """Группы кодов КТРУ из текста по порядку и сообщения о кодах, которые не дали группу."""
        groups: list[str] = []
        messages: list[SearchMessage] = []
        codes = find_ktru_codes(query.text)
        if not codes:
            return groups, messages
        with self._uow:
            positions = {code: self._catalog.position(code) for code in codes}
        for code, position in positions.items():
            if position is None or position.group not in self._index.groups:
                messages.append(
                    SearchMessage(
                        "ktru_code_not_found",
                        f"Код КТРУ {code} не найден среди групп справочника — поиск по описанию",
                    )
                )
            elif position.group not in allowed:
                messages.append(
                    SearchMessage(
                        "ktru_code_other_category",
                        f"Код КТРУ {code} — из категории «{position.category}», "
                        f"а не «{query.category}»",
                    )
                )
            elif position.group not in groups:
                groups.append(position.group)
        return groups, messages

    def _alias_hits(self, text: str, allowed: set[str]) -> list[Hit]:
        """Группы совпавших синонимов: скор — длина самого длинного, длиннее — выше."""
        best: dict[str, int] = {}
        for pattern, length, code in self._index.aliases:
            if code in allowed and pattern.search(text):
                best[code] = max(best.get(code, 0), length)
        return sorted((Hit(code, n) for code, n in best.items()), key=lambda h: (-h.score, h.key))
