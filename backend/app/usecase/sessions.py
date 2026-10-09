"""Сессия анализа: история сообщений, идемпотентность и снимки ревизий."""

from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4

from app.domain.catalog import Group, Position
from app.domain.errors import CatalogEmpty, IdempotencyConflict, ModelFailure, SessionNotFound
from app.domain.facts import CheckResult, Fact, RuleCheck
from app.domain.rules import check_rule, explain, supported
from app.domain.search import SearchResult
from app.domain.sessions import (
    Alternative,
    AnalysisError,
    Candidate,
    CandidateCounts,
    GroupRef,
    Message,
    NarrowingPath,
    Revision,
    SessionState,
    SessionStatus,
)
from app.usecase.interface import (
    CatalogRepository,
    FactExtractor,
    GroupSearcher,
    SessionsRepository,
    UnitOfWork,
)


class Sessions:
    def __init__(
        self,
        uow: UnitOfWork,
        sessions: SessionsRepository,
        search: GroupSearcher,
        catalog: CatalogRepository,
        fact_extractor: FactExtractor,
    ) -> None:
        self._fact_extractor = fact_extractor
        self._search = search
        self._catalog = catalog
        self._uow = uow
        self._sessions = sessions

    def create(self) -> SessionState:
        state = SessionState(str(uuid4()))
        with self._uow:
            self._sessions.save(Revision(state))
        return state

    def get(self, session_id: str) -> SessionState:
        with self._uow:
            state = self._sessions.latest(session_id)
            if state is None:
                raise SessionNotFound()
            return state

    def message(self, session_id: str, text: str, key: str | None = None) -> SessionState:
        with self._uow:
            previous = self._sessions.latest(session_id, lock=True)
            if previous is None:
                raise SessionNotFound()
            replay = self._sessions.replay(session_id, key) if key is not None else None
            if replay is not None:
                if replay.request_text != text:
                    raise IdempotencyConflict()
                return replay.state
            messages = (
                *previous.messages,
                Message(str(uuid4()), text, datetime.now(UTC).isoformat()),
            )
            state = SessionState(session_id, previous.revision + 1, messages=messages)
            try:
                result = self._search.run(
                    "\n".join(m.text for m in messages), category=None, limit=5
                )
                state = self._analyze(state, result)
            except (ModelFailure, CatalogEmpty) as error:
                state = replace(
                    state,
                    status=SessionStatus.TECHNICAL_ERROR,
                    errors=(AnalysisError(error.code, error.message),),
                )
            self._sessions.save(Revision(state, key, text))
            return state

    def _analyze(self, state: SessionState, result: SearchResult) -> SessionState:
        if not result.groups:
            raise CatalogEmpty()
        selected = result.groups[0].group
        group = Group.of(selected, self._catalog.children(selected.code))
        facts, warnings = self._fact_extractor.extract(state.messages, group)
        candidates = tuple(_candidate(p, facts) for p in sorted(group.leaves, key=lambda p: p.code))
        compatible = [c for c in candidates if not c.excluded]
        status = SessionStatus.NEEDS_CLARIFICATION
        if not compatible:
            status = SessionStatus.CONFLICT
        elif len(compatible) == 1 and not any(
            c.result == CheckResult.UNSUPPORTED for c in compatible[0].checks
        ):
            status = SessionStatus.RESOLVED
        count = len(candidates)
        return replace(
            state,
            status=status,
            facts=facts,
            path=NarrowingPath(selected.category, GroupRef(selected.code, selected.name), count),
            candidates=candidates,
            candidate_counts=CandidateCounts(count, len(compatible), count - len(compatible)),
            alternatives=tuple(
                Alternative(
                    hit.group.code,
                    hit.group.name,
                    hit.group.category,
                    hit.score,
                    {"lexical": hit.lexical, "vector": hit.vector, "synonym": hit.synonym},
                )
                for hit in result.groups[1:5]
            ),
            warnings=(*result.messages, *warnings),
        )


def _candidate(position: Position, facts: tuple[Fact, ...]) -> Candidate:
    checks = [check_rule(position, fact) for fact in facts]
    reason = next(
        (
            explain(position, fact)
            for fact, check in zip(facts, checks, strict=True)
            if check.result == CheckResult.MISMATCH and fact.status == "accepted_from_text"
        ),
        None,
    )
    # Неподдержанное правило блокирует автоподтверждение даже без факта по этому полю.
    if any(not supported(c) for c in position.characteristics):
        checks.append(RuleCheck(None, CheckResult.UNSUPPORTED))
    if not any(position.char(f.characteristic_name or "") for f in facts):
        checks.append(RuleCheck(None, CheckResult.UNKNOWN))
    return Candidate(
        position.code,
        position.name,
        reason is not None,
        reason,
        tuple(c.fact_id for c in checks if c.result == CheckResult.MATCH and c.fact_id is not None),
        tuple(checks),
    )
