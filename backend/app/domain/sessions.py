"""Сохранённый результат анализа одной ревизии сессии."""

from dataclasses import dataclass
from enum import StrEnum

from app.domain.facts import ExclusionReason, Fact, RuleCheck
from app.domain.search import MethodContribution


class SessionStatus(StrEnum):
    DRAFT = "draft"
    NEEDS_CLARIFICATION = "needs_clarification"
    RESOLVED = "resolved"
    AMBIGUOUS_IN_CATALOG = "ambiguous_in_catalog"
    OUT_OF_SCOPE = "out_of_scope"
    CONFLICT = "conflict"
    TECHNICAL_ERROR = "technical_error"


@dataclass(frozen=True)
class Message:
    id: str
    text: str
    created_at: str


@dataclass(frozen=True)
class GroupRef:
    code: str
    name: str


@dataclass(frozen=True)
class NarrowingPath:
    category: str
    group: GroupRef
    positions: int


@dataclass(frozen=True)
class Alternative:
    code: str
    name: str
    category: str
    score: float
    methods: dict[str, MethodContribution]


@dataclass(frozen=True)
class Candidate:
    code: str
    name: str
    excluded: bool = False
    reason: ExclusionReason | None = None
    matched_facts: tuple[str, ...] = ()
    checks: tuple[RuleCheck, ...] = ()


@dataclass(frozen=True)
class CandidateCounts:
    in_group: int = 0
    compatible: int = 0
    excluded_by_rules: int = 0


@dataclass(frozen=True)
class AnalysisError:
    code: str
    message: str


@dataclass(frozen=True)
class SessionState:
    session_id: str
    revision: int = 0
    status: SessionStatus = SessionStatus.DRAFT
    messages: tuple[Message, ...] = ()
    path: NarrowingPath | None = None
    alternatives: tuple[Alternative, ...] = ()
    candidates: tuple[Candidate, ...] = ()
    candidate_counts: CandidateCounts = CandidateCounts()
    facts: tuple[Fact, ...] = ()
    errors: tuple[AnalysisError, ...] = ()
    warnings: tuple[str, ...] = ()
    next_question: None = None


@dataclass(frozen=True)
class Revision:
    state: SessionState
    idempotency_key: str | None = None
    request_text: str | None = None
