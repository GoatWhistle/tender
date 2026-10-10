"""Сессия анализа: история сообщений, идемпотентность и снимки ревизий."""

from collections.abc import Sequence
from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4

from app.domain.catalog import Group, Position
from app.domain.diagnostics import Diagnostic
from app.domain.dialog import (
    CommonField,
    DialogTurn,
    RequiredField,
    answer_fact,
    common_fields,
    derive,
    merge,
    next_step,
)
from app.domain.enum_mapping import EnumProposal, EnumResolution, enum_fields
from app.domain.errors import (
    CatalogEmpty,
    IdempotencyConflict,
    ModelFailure,
    OptionNotFound,
    SessionNotFound,
    StaleQuestion,
    StaleRevision,
)
from app.domain.facts import CheckResult, Fact, RuleCheck, normalized
from app.domain.rules import check_rule, explain, selection_conflict, supported
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
    UnsupportedRule,
)
from app.usecase.diagnostics import Diagnostics
from app.usecase.enum_mapping import EnumMapper
from app.usecase.interface import (
    CatalogRepository,
    FactExtractor,
    GroupSearcher,
    SessionsRepository,
    SpellingService,
    UnitOfWork,
)
from app.usecase.spelling import spelling_diagnostics


class Sessions:
    def __init__(
        self,
        uow: UnitOfWork,
        sessions: SessionsRepository,
        search: GroupSearcher,
        catalog: CatalogRepository,
        fact_extractor: FactExtractor,
        enum_mapper: EnumMapper | None = None,
        diagnostics: Diagnostics | None = None,
        spelling: SpellingService | None = None,
    ) -> None:
        self._enum_mapper = enum_mapper
        self._spelling = spelling
        self._diagnostics = diagnostics
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
            state = SessionState(
                session_id,
                previous.revision + 1,
                messages=messages,
                dialog=previous.dialog,
                enum_resolutions=previous.enum_resolutions,
                errors=tuple(
                    e
                    for e in previous.errors
                    if (isinstance(e, Diagnostic) and not e.rule_ref)
                    or (isinstance(e, AnalysisError) and e.code.startswith("spelling_"))
                ),
            )
            if self._spelling is not None:
                state = replace(
                    state,
                    errors=(*state.errors, *spelling_diagnostics(self._spelling, messages[-1])),
                )
            try:
                result = self._search.run(
                    "\n".join(m.text for m in messages), category=None, limit=5
                )
                if not result.groups:
                    raise CatalogEmpty()
                state = replace(
                    state,
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
                    warnings=result.messages,
                )
                selected = result.groups[0].group
                state = self._analyze(state, self._group(selected))
            except (ModelFailure, CatalogEmpty) as error:
                state = _failed(state, error)
            self._sessions.save(Revision(state, key, text))
            return state

    def answer(self, session_id: str, question_id: str, option_id: str | None) -> SessionState:
        """Ответ на вопрос последней ревизии: новая ревизия с полным пересчётом без поиска —
        группа та же, текст не менялся."""
        with self._uow:
            previous = self._sessions.latest(session_id, lock=True)
            if previous is None:
                raise SessionNotFound()
            question = previous.next_question
            if question is None or question.question_id != question_id or previous.path is None:
                raise StaleQuestion()
            code = previous.path.group.code
            selected = self._catalog.position(code)
            if selected is None:
                raise CatalogEmpty()
            group = self._group(selected)
            fact = None
            if option_id is not None:
                if option_id not in {o.id for o in question.options}:
                    raise OptionNotFound()
                compatible = {c.code for c in previous.candidates if not c.excluded}
                fact = answer_fact(
                    question,
                    option_id,
                    [p for p in group.leaves if p.code in compatible],
                    [f for f in previous.facts if f.status != "superseded"],
                )
                if fact is None:
                    raise StaleQuestion()
            revision = previous.revision + 1
            turn = DialogTurn(
                question_id,
                question.kind,
                question.characteristic,
                revision,
                len(previous.messages),
                option_id,
                fact,
                code,
            )
            state = replace(previous, revision=revision, dialog=(*previous.dialog, turn))
            try:
                state = self._analyze(state, group, extend=False)
            except ModelFailure as error:
                state = _failed(state, error)
            self._sessions.save(Revision(state))
            return state

    def resolve_enum(
        self,
        session_id: str,
        expected_revision: int,
        proposal_id: str,
        action: str,
        values: Sequence[str] = (),
    ) -> SessionState:
        with self._uow:
            previous = self._sessions.latest(session_id, lock=True)
            if previous is None:
                raise SessionNotFound()
            if previous.revision != expected_revision or previous.path is None:
                raise StaleRevision()
            proposal = next((p for p in previous.enum_proposals if p.id == proposal_id), None)
            if proposal is None:
                raise StaleRevision()
            chosen = proposal.suggested if action == "accept" else tuple(values)
            if action == "unknown":
                chosen = ()
            elif not any(s.permits(chosen) for s in proposal.selections):
                raise OptionNotFound("Выберите допустимое сочетание значений каталога")
            code = previous.path.group.code
            selected = self._catalog.position(code)
            if selected is None:
                raise CatalogEmpty()
            group = self._group(selected)
            # Каталог мог обновиться после показа предложения.
            field = next(
                (f for f in enum_fields(group.leaves) if f.name == proposal.characteristic), None
            )
            if chosen and (field is None or not field.permits(chosen)):
                raise OptionNotFound()
            revision = previous.revision + 1
            confirmed: list[Fact] = []
            for i, value in enumerate(chosen):
                source = next(
                    (
                        f
                        for f in previous.facts
                        if f.characteristic_name == proposal.characteristic
                        and f.value == value.lower().replace("ё", "е")
                        and f.origin == "decision"
                    ),
                    None,
                )
                if action == "accept" and source is not None:
                    fact = replace(
                        source, id=f"enum-answer:{revision}:{i}", status="confirmed_by_user"
                    )
                else:
                    fact = Fact(
                        f"enum-answer:{revision}:{i}",
                        proposal.characteristic,
                        proposal.characteristic,
                        value,
                        None,
                        value.lower().replace("ё", "е"),
                        None,
                        "text",
                        None,
                        "catalog_value",
                        origin="user",
                        status="confirmed_by_user",
                    )
                confirmed.append(fact)
            resolution = EnumResolution(
                proposal.id,
                proposal.characteristic,
                code,
                revision,
                len(previous.messages),
                tuple(confirmed),
            )
            state = replace(
                previous,
                revision=revision,
                enum_resolutions=(*previous.enum_resolutions, resolution),
            )
            state = self._analyze(state, group, extend=False)
            self._sessions.save(Revision(state))
            return state

    def _group(self, selected: Position) -> Group:
        group = Group.of(selected, self._catalog.children(selected.code))
        if self._enum_mapper is None:
            return group
        names = {normalized(f.name).strip(): f.name for f in enum_fields(group.leaves)}
        return replace(
            group,
            leaves=tuple(
                replace(
                    p,
                    characteristics=tuple(
                        replace(c, name=names.get(normalized(c.name).strip(), c.name))
                        for c in p.characteristics
                    ),
                )
                for p in group.leaves
            ),
        )

    def _analyze(self, state: SessionState, group: Group, *, extend: bool = True) -> SessionState:
        """Факты, кандидаты, статус и следующий вопрос; `extend` — дописать предупреждения
        извлечения (при ответе они уже есть: текст тот же). Ответы по другой группе хранятся в
        истории, но не применяются."""
        selected = group.position
        dialog = tuple(t for t in state.dialog if t.group == selected.code)
        parsed, warnings = self._fact_extractor.extract(state.messages, group)
        # Качественные поля обрабатываются совместно, чтобы точный парсер не выбрал
        # одну часть многозначного или неоднозначного описания раньше decision-проверки.
        enum_names = {f.name for f in enum_fields(group.leaves)} if self._enum_mapper else set()
        parsed = tuple(
            f
            for f in parsed
            if f.characteristic_name not in enum_names
            or (
                self._diagnostics is not None
                and f.normalization_rule == "explicit_unverified"
                and not f.accepted
            )
        )
        facts = merge(parsed, dialog, [m.id for m in state.messages])
        resolutions = {
            r.characteristic: r
            for r in state.enum_resolutions
            if r.group == selected.code
            and not any(
                t.characteristic == r.characteristic and t.revision > r.revision for t in dialog
            )
        }
        locked = {
            name for name, r in resolutions.items() if r.facts or r.messages == len(state.messages)
        }
        facts = tuple(
            replace(f, status="superseded") if f.characteristic_name in locked else f for f in facts
        )
        facts = (*facts, *(f for r in resolutions.values() for f in r.facts))
        active = [f for f in facts if f.status != "superseded"]
        leaves = sorted(group.leaves, key=lambda p: p.code)
        candidates = tuple(_candidate(p, active) for p in leaves)
        remaining = [p for p, c in zip(leaves, candidates, strict=True) if not c.excluded]
        proposals: tuple[EnumProposal, ...] = ()
        if self._enum_mapper is not None:
            skip = locked | {
                f.characteristic_name for f in facts if f.accepted and f.characteristic_name
            }
            if extend:
                mapped, proposals = self._enum_mapper.map(
                    state.messages, remaining, state.revision, skip
                )
            else:
                mapped = tuple(
                    f
                    for f in state.facts
                    if f.origin == "decision"
                    and f.status in {"proposed", "accepted_from_model"}
                    and f.characteristic_name not in skip
                )
                proposals = tuple(p for p in state.enum_proposals if p.characteristic not in skip)
            facts = (*facts, *mapped)
            active = [f for f in facts if f.status != "superseded"]
            candidates = tuple(_candidate(p, active) for p in leaves)
            remaining = [p for p, c in zip(leaves, candidates, strict=True) if not c.excluded]
        dialog = (
            *dialog,
            *(
                DialogTurn(
                    r.proposal_id,
                    "required",
                    r.characteristic,
                    r.revision,
                    r.messages,
                    group=r.group,
                )
                for r in resolutions.values()
                if not r.facts
            ),
        )
        dialog = tuple(sorted(dialog, key=lambda t: t.revision))
        count = len(candidates)
        question_id = f"q{state.revision}"
        messages = len(state.messages)
        missing: tuple[RequiredField, ...] = ()
        common: tuple[CommonField, ...] = ()
        unanswered: tuple[str, ...] = ()
        question = None
        if not remaining:
            status = SessionStatus.CONFLICT
        elif len(remaining) == 1:
            status = SessionStatus.RESOLVED
            unconfirmed = frozenset(p.characteristic for p in proposals) | frozenset(
                name for name, r in resolutions.items() if not r.facts and name in locked
            )
            derived, missing = derive(remaining[0], active, unconfirmed=unconfirmed)
            facts = (*facts, *derived)
            question = next_step(
                remaining, (*active, *derived), dialog, messages, question_id
            ).question
        else:
            step = next_step(remaining, active, dialog, messages, question_id)
            question, unanswered = step.question, step.unanswered
            if step.indistinct and question is None:
                status = SessionStatus.AMBIGUOUS_IN_CATALOG
                common = common_fields(remaining)
            else:
                status = SessionStatus.NEEDS_CLARIFICATION
        if question is not None and any(
            p.characteristic == question.characteristic for p in proposals
        ):
            question = None
        diagnostics = (
            self._diagnostics.run(facts, group, state.messages) if self._diagnostics else ()
        )
        return replace(
            state,
            status=status,
            facts=facts,
            enum_proposals=proposals,
            path=NarrowingPath(selected.category, GroupRef(selected.code, selected.name), count),
            candidates=candidates,
            candidate_counts=CandidateCounts(count, len(remaining), count - len(remaining)),
            warnings=(*state.warnings, *warnings) if extend else state.warnings,
            errors=(
                *tuple(d for d in diagnostics if d.kind != "synonym"),
                *tuple(
                    e
                    for e in state.errors
                    if (isinstance(e, AnalysisError) and e.code.startswith("spelling_"))
                    or (
                        isinstance(e, Diagnostic)
                        and not e.rule_ref
                        and not any(
                            d.source.message_id == e.source.message_id
                            and d.source.start < e.source.end
                            and e.source.start < d.source.end
                            for d in diagnostics
                        )
                        and not any(
                            f.accepted
                            and f.source is not None
                            and f.source.message_id == e.source.message_id
                            and f.source.start < e.source.end
                            and e.source.start < f.source.end
                            for f in facts
                        )
                    )
                ),
            ),
            normalizations=tuple(d for d in diagnostics if d.kind == "synonym"),
            next_question=question,
            card_complete=status == SessionStatus.RESOLVED and not missing,
            missing_required=missing,
            common_fields=common,
            unanswered=unanswered,
            unsupported_rules=tuple(
                UnsupportedRule(p.code, c.name)
                for p in remaining
                for c in p.characteristics
                if not supported(c)
            ),
        )


def _failed(state: SessionState, error: ModelFailure | CatalogEmpty) -> SessionState:
    return replace(
        state,
        status=SessionStatus.TECHNICAL_ERROR,
        errors=(AnalysisError(error.code, error.message), *state.errors),
        next_question=None,
    )


def _candidate(position: Position, facts: Sequence[Fact]) -> Candidate:
    checks = [check_rule(position, fact) for fact in facts]
    reason = next(
        (
            explain(position, fact)
            for fact, check in zip(facts, checks, strict=True)
            if check.result == CheckResult.MISMATCH and fact.accepted
        ),
        None,
    )
    combination = selection_conflict(position, facts)
    if combination is not None:
        reason = combination
        checks.append(RuleCheck(combination.fact_id, CheckResult.MISMATCH))
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
