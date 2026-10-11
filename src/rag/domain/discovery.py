import uuid
from dataclasses import dataclass, field
from enum import StrEnum

from rag.domain.catalog import Position
from rag.domain.correction import Corrected
from rag.domain.errors import InputError, StageError
from rag.domain.search import Hit, Ranked, Reranking
from rag.domain.sessions import SHORTLIST


class DiscoveryStage(StrEnum):
    REVIEW = "review"
    CANDIDATES = "candidates"
    RANKED = "ranked"


@dataclass
class Discovery:
    corrected: Corrected
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    stage: DiscoveryStage = DiscoveryStage.REVIEW
    hits: list[Hit] = field(default_factory=list)
    ranked: list[Ranked] = field(default_factory=list)
    auto_select_code: str | None = None
    auto_select_reason: str | None = None

    @property
    def shortlist(self) -> list[Ranked]:
        return self.ranked[:SHORTLIST] if self.stage == DiscoveryStage.RANKED else []

    @property
    def rejected(self) -> list[Ranked]:
        return self.ranked[SHORTLIST:] if self.stage == DiscoveryStage.RANKED else []

    @property
    def shown(self) -> list[Position]:
        if self.stage == DiscoveryStage.RANKED:
            return [r.hit.position for r in self.shortlist]
        return [h.position for h in self.hits]

    def found(self, hits: list[Hit]) -> None:
        self.hits = hits
        self.stage = DiscoveryStage.CANDIDATES

    def rank(self, reranking: Reranking) -> None:
        self.ranked = reranking.ranked
        if not self.corrected.issues and reranking.exact_match_code:
            self.auto_select_code = reranking.exact_match_code
            self.auto_select_reason = reranking.exact_match_reason
        self.stage = DiscoveryStage.RANKED

    def check_selection(self, code: str, automatic: bool) -> None:
        if self.stage != DiscoveryStage.RANKED:
            raise StageError("дождитесь ранжирования")
        if not any(r.hit.position.code == code for r in self.ranked):
            raise InputError("выберите одну из предложенных групп")
        if automatic and code != self.auto_select_code:
            raise InputError("автоматический выбор этой группы не подтверждён")
