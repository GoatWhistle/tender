"""Сохранённый результат анализа одной ревизии сессии."""

from dataclasses import dataclass
from enum import StrEnum

from app.domain.diagnostics import Diagnostic
from app.domain.dialog import CommonField, DialogTurn, Question, RequiredField
from app.domain.enum_mapping import EnumProposal, EnumResolution
from app.domain.facts import ExclusionReason, Fact, RuleCheck
from app.domain.group_validation import GroupCheck
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
    role: str = "group_template"


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
    returned_reason: str | None = None
    role: str = "ktru_position"


@dataclass(frozen=True)
class CandidateCounts:
    in_group: int = 0
    compatible: int = 0
    excluded_by_rules: int = 0


@dataclass(frozen=True)
class UnsupportedRule:
    """Правило совместимой позиции, которое проверка не поддерживает: предупреждение."""

    position: str
    characteristic: str


@dataclass(frozen=True)
class AnalysisError:
    code: str
    message: str


@dataclass(frozen=True)
class FactEvent:
    action: str
    revision: int
    created_at: str
    before: tuple[Fact, ...]
    after: tuple[Fact, ...]
    group: str
    restored_from: str | None = None
    message_count: int = 0


@dataclass(frozen=True)
class CatalogRef:
    position_code: str
    characteristic_code: str
    name: str


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
    errors: tuple[AnalysisError | Diagnostic, ...] = ()
    normalizations: tuple[Diagnostic, ...] = ()
    warnings: tuple[str, ...] = ()
    next_question: Question | None = None
    # история вопросов и ответов, включая «не знаю»: из неё пересчитываются факты ответов
    dialog: tuple[DialogTurn, ...] = ()
    # «код определён» (`resolved`) и «карточка заполнена» — разные вещи
    card_complete: bool = False
    missing_required: tuple[RequiredField, ...] = ()
    common_fields: tuple[CommonField, ...] = ()
    unanswered: tuple[str, ...] = ()
    unsupported_rules: tuple[UnsupportedRule, ...] = ()
    fact_history: tuple[FactEvent, ...] = ()
    results_stale: bool = False
    analysis_revision: int | None = None
    editable_fields: tuple[str, ...] = ()
    catalog_refs: tuple[CatalogRef, ...] = ()

    group_checks: tuple[GroupCheck, ...] = ()
    enum_proposals: tuple[EnumProposal, ...] = ()
    enum_resolutions: tuple[EnumResolution, ...] = ()


@dataclass(frozen=True)
class Revision:
    state: SessionState
    idempotency_key: str | None = None
    request_text: str | None = None
