import asyncio
import uuid
from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel

from rag.comparison import display_differences
from rag.preprocess import Preprocessed, preprocess
from rag.rerank import Ranked, rerank
from rag.search import Hit, Index, query_vector
from rag.session import InputError, Session, StageError, switch_group


@dataclass
class Discovery:
    pre: Preprocessed
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    stage: str = "review"
    hits: list[Hit] = field(default_factory=list)
    ranked: list[Ranked] = field(default_factory=list)
    auto_select_code: str | None = None
    auto_select_reason: str | None = None
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


class SearchCandidate(BaseModel):
    id: str
    name: str
    code: str
    okpd2: str
    relevance: int | None = None
    reason: str | None = None
    differences: dict[str, str]


class SearchFix(BaseModel):
    before: str
    after: str
    kind: str


class DiscoveryOut(BaseModel):
    id: str
    stage: Literal["review", "candidates", "ranked"]
    description: str
    corrected: str
    fixes: list[SearchFix]
    issues: list[str]
    candidates: list[SearchCandidate]
    rejected: list[SearchCandidate]
    auto_select_code: str | None
    auto_select_reason: str | None


searches: dict[str, Discovery] = {}


def view(search: Discovery) -> DiscoveryOut:
    positions = (
        [r.hit.position for r in search.ranked[:5]]
        if search.stage == "ranked"
        else [h.position for h in search.hits]
    )
    comparison = display_differences(positions)
    candidates = [
        SearchCandidate(
            id=h.position.code,
            code=h.position.code,
            name=h.position.name,
            okpd2=h.position.okpd2,
            differences=comparison.get(h.position.code, {}),
        )
        for h in search.hits
    ]
    if search.stage == "ranked":
        candidates = [
            SearchCandidate(
                id=r.hit.position.code,
                code=r.hit.position.code,
                name=r.hit.position.name,
                okpd2=r.hit.position.okpd2,
                relevance=r.relevance,
                reason=r.reason,
                differences=comparison.get(r.hit.position.code, {}),
            )
            for r in search.ranked[:5]
        ]
    rejected = [
        SearchCandidate(
            id=r.hit.position.code,
            code=r.hit.position.code,
            name=r.hit.position.name,
            okpd2=r.hit.position.okpd2,
            relevance=r.relevance,
            reason=r.reason,
            differences={},
        )
        for r in (search.ranked[5:] if search.stage == "ranked" else [])
    ]
    return DiscoveryOut(
        id=search.id,
        stage=search.stage,
        description=search.pre.original,
        corrected=search.pre.corrected,
        fixes=[
            SearchFix(before=f.before, after=f.after, kind=f.kind)
            for f in search.pre.fixes
        ],
        issues=search.pre.issues,
        candidates=candidates,
        rejected=rejected,
        auto_select_code=search.auto_select_code,
        auto_select_reason=search.auto_select_reason,
    )


def get(search_id: str) -> Discovery:
    if search_id not in searches:
        raise InputError("поиск не найден, начните заново")
    return searches[search_id]


async def create(text: str) -> Discovery:
    if not text.strip() or len(text) > 4000:
        raise InputError("описание должно содержать от 1 до 4000 символов")
    search = Discovery(await preprocess(text.strip()))
    searches[search.id] = search
    return search


async def retrieve(search: Discovery, index: Index) -> None:
    if search.stage in {"candidates", "ranked"}:
        return
    if search.stage != "review":
        raise StageError("поиск недоступен")
    vector = await query_vector(search.pre.corrected)
    search.hits = await asyncio.to_thread(index.search, vector)
    search.stage = "candidates"


async def rank(search: Discovery) -> None:
    if search.stage == "ranked":
        return
    if search.stage != "candidates":
        raise StageError("сначала получите кандидатов")
    if search.hits:
        result = await rerank(search.pre.corrected, search.hits)
        search.ranked = result.ranked
        if not search.pre.issues:
            search.auto_select_code = result.exact_match_code
            search.auto_select_reason = (
                result.exact_match_reason if result.exact_match_code else None
            )
    search.stage = "ranked"


async def select(
    search: Discovery, index: Index, code: str, automatic: bool = False
) -> Session:
    if search.stage != "ranked":
        raise StageError("дождитесь ранжирования")
    if not any(r.hit.position.code == code for r in search.ranked):
        raise InputError("выберите одну из предложенных групп")
    if automatic and code != search.auto_select_code:
        raise InputError("автоматический выбор этой группы не подтверждён")
    pre = search.pre
    session = Session(
        pre.original, pre.corrected, pre.fixes, pre.issues, search.ranked, []
    )
    await switch_group(session, index, code)
    if automatic:
        session.selection_reason = search.auto_select_reason
    return session
