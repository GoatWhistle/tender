"""Сессия анализа: история сообщений, идемпотентность и снимки ревизий."""

import re
from collections.abc import Sequence
from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4

from app.domain.catalog import Group, Position
from app.domain.diagnostics import Diagnostic
from app.domain.dialog import (
    CommonField,
    DialogTurn,
    Question,
    RequiredField,
    answer_fact,
    common_fields,
    derive,
    merge,
    next_step,
)
from app.domain.errors import (
    CatalogEmpty,
    FactNotFound,
    IdempotencyConflict,
    InvalidFactEdit,
    ModelFailure,
    OptionNotFound,
    SessionNotFound,
    StaleQuestion,
    StaleRevision,
)
from app.domain.fact_edits import INACTIVE, FactInput, apply_history, component_key, reconcile
from app.domain.facts import CheckResult, Fact, FactSource, RuleCheck
from app.domain.rules import check_rule, explain, supported
from app.domain.sessions import (
    Alternative,
    AnalysisError,
    Candidate,
    CandidateCounts,
    FactEvent,
    GroupRef,
    Message,
    NarrowingPath,
    Revision,
    SessionState,
    SessionStatus,
    UnsupportedRule,
)
from app.usecase.diagnostics import Diagnostics
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
        diagnostics: Diagnostics | None = None,
        spelling: SpellingService | None = None,
    ) -> None:
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
                fact_history=previous.fact_history,
                facts=previous.facts,
                candidates=previous.candidates,
                path=previous.path,
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
                group = Group.of(selected, self._catalog.children(selected.code))
                state = self._correct_text(state, previous, group)
                state = self._analyze(state, group)
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
            group = Group.of(selected, self._catalog.children(code))
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
            history = previous.fact_history
            if fact is not None:
                before = tuple(
                    replace(f, status="superseded", superseded_by=fact.id)
                    for f in previous.facts
                    if f.status not in INACTIVE
                    and f.characteristic_name == fact.characteristic_name
                    and component_key(f) == component_key(fact)
                )
                history = (
                    *history,
                    FactEvent(
                        "confirm", revision, datetime.now(UTC).isoformat(), before, (fact,), code
                    ),
                )
            state = replace(
                previous, revision=revision, dialog=(*previous.dialog, turn), fact_history=history
            )
            try:
                state = self._analyze(state, group, extend=False)
            except ModelFailure as error:
                state = _failed(state, error)
            self._sessions.save(Revision(state))
            return state

    def _correct_text(
        self, state: SessionState, previous: SessionState, group: Group
    ) -> SessionState:
        text = state.messages[-1].text.lower().strip()
        command = re.fullmatch(r"исправь\s+.+\s+на\s+.+", text)
        negation = re.fullmatch(r"нет,?\s+не\s+([^,]+),\s*(.+)", text)
        if not command and not negation:
            return state
        parsed, _ = self._fact_extractor.extract((state.messages[-1],), group)
        if len(parsed) != 1 or parsed[0].characteristic_name is None:
            return self._unclear_correction(state, group, parsed)
        new = parsed[0]
        targets = [
            f
            for f in previous.facts
            if f.status not in INACTIVE
            and f.origin != "catalog"
            and f.characteristic_name == new.characteristic_name
        ]
        if len(targets) != 1 or (negation and targets[0].raw_value.lower() != negation[1].strip()):
            return self._unclear_correction(state, group, parsed)
        old = targets[0]
        new = replace(new, status="confirmed_by_user", origin="user", component=old.component)
        event = FactEvent(
            "text_correction",
            state.revision,
            datetime.now(UTC).isoformat(),
            (replace(old, status="superseded", superseded_by=new.id),),
            (new,),
            group.position.code,
        )
        return replace(state, fact_history=(*state.fact_history, event))

    def _unclear_correction(
        self, state: SessionState, group: Group, parsed: Sequence[Fact]
    ) -> SessionState:
        message = state.messages[-1]
        pending = tuple(
            replace(f, status="ambiguous", normalization_rule="correction_needs_binding")
            for f in parsed
        )
        if not pending:
            pending = (
                Fact(
                    str(uuid4()),
                    None,
                    None,
                    message.text,
                    None,
                    message.text,
                    None,
                    "text",
                    FactSource(message.id, message.text, 0, len(message.text)),
                    "correction_needs_binding",
                    status="ambiguous",
                ),
            )
        event = FactEvent(
            "clarification",
            state.revision,
            datetime.now(UTC).isoformat(),
            (),
            pending,
            group.position.code,
        )
        return replace(state, fact_history=(*state.fact_history, event))

    def _group(self, state: SessionState) -> Group:
        selected = self._catalog.position(state.path.group.code) if state.path else None
        if selected is None:
            raise CatalogEmpty()
        return Group.of(selected, self._catalog.children(selected.code))

    def _current(self, session_id: str, expected_revision: int) -> SessionState:
        state = self._sessions.latest(session_id, lock=True)
        if state is None:
            raise SessionNotFound()
        if state.revision != expected_revision:
            raise StaleRevision()
        return state

    def mutate(
        self,
        session_id: str,
        expected_revision: int,
        fact_id: str | None,
        action: str,
        value: FactInput | None = None,
        related_ids: tuple[str, ...] = (),
        bindings: tuple[FactInput, ...] = (),
        diagnostic_index: int | None = None,
    ) -> SessionState:
        with self._uow:
            previous = self._current(session_id, expected_revision)
            group = self._group(previous)
            old = next((f for f in previous.facts if f.id == fact_id), None)
            if fact_id is not None and old is None:
                raise FactNotFound()
            if old and action != "restore" and old.status in INACTIVE:
                raise FactNotFound()
            source = old.source if old else None
            if action == "accept_suggestion":
                diagnostics = [
                    e
                    for e in (*previous.errors, *previous.normalizations)
                    if isinstance(e, Diagnostic)
                ]
                if diagnostic_index is None or not 0 <= diagnostic_index < len(diagnostics):
                    raise InvalidFactEdit("Предложение не найдено")
                diagnostic = diagnostics[diagnostic_index]
                if diagnostic.fact_id != fact_id or value is None:
                    raise InvalidFactEdit("Укажите характеристику и часть товара для предложения")
                proposed = diagnostic.suggestion
                if proposed is None:
                    raise InvalidFactEdit("Выберите значение через редактор факта")
                rendered = (
                    f"{value.raw_value} {value.raw_unit}" if value.raw_unit else value.raw_value
                )
                if rendered.lower() != proposed.lower():
                    raise InvalidFactEdit("Значение не совпадает с предложением")
                source = diagnostic.source
            targets = [old] if old else []
            if related_ids:
                related = [
                    f for f in previous.facts if f.id in related_ids and f.status not in INACTIVE
                ]
                if len(related) != len(set(related_ids)):
                    raise FactNotFound()
                targets = list({f.id: f for f in (*targets, *related)}.values())
            if action == "split":
                if (
                    len(targets) < 2
                    or len(bindings) != len(targets)
                    or any(not b.component for b in bindings)
                ):
                    raise InvalidFactEdit("Укажите часть товара для каждого спорного значения")
                after = tuple(
                    replace(b.fact(group), source=f.source)
                    for b, f in zip(bindings, targets, strict=True)
                )
            elif action == "delete":
                if not targets:
                    raise FactNotFound()
                after = ()
            elif action in {"confirm", "restore"}:
                if old is None:
                    raise FactNotFound()
                if (
                    old.characteristic_name is None
                    or old.normalization_rule == "correction_needs_binding"
                ):
                    raise InvalidFactEdit(
                        "Сначала укажите характеристику и часть товара в редакторе"
                    )
                after = (
                    replace(
                        old,
                        id=str(uuid4()),
                        status="confirmed_by_user",
                        origin="user",
                        superseded_by=None,
                    ),
                )
                # Восстановление заменяет актуальный конец цепочки, история остаётся.
                if action == "restore":
                    by_id = {f.id: f for f in previous.facts}
                    chain: set[str] = set()
                    cursor = old
                    while cursor.superseded_by and cursor.superseded_by not in chain:
                        chain.add(cursor.superseded_by)
                        successor = by_id.get(cursor.superseded_by)
                        if successor is None:
                            break
                        cursor = successor
                    targets = [
                        f
                        for f in previous.facts
                        if f.status not in INACTIVE
                        and (
                            f.id in chain
                            or (
                                f.characteristic_name == old.characteristic_name
                                and component_key(f) == component_key(old)
                            )
                        )
                    ]
            elif action in {"edit", "accept_suggestion"} and value is not None:
                after = (replace(value.fact(group), source=source),)
            else:
                raise InvalidFactEdit()
            before = tuple(
                replace(
                    f,
                    status="deleted" if not after else "superseded",
                    superseded_by=after[i].id
                    if action == "split"
                    else after[0].id
                    if after
                    else None,
                )
                for i, f in enumerate(targets)
            )
            revision = previous.revision + 1
            event = FactEvent(
                action,
                revision,
                datetime.now(UTC).isoformat(),
                before,
                after,
                group.position.code,
                restored_from=old.id if action == "restore" and old else None,
            )
            state = replace(
                previous,
                revision=revision,
                facts=apply_history(previous.facts, (event,), group.position.code),
                fact_history=(*previous.fact_history, event),
                results_stale=True,
                card_complete=False,
            )
            try:
                state = self._analyze(state, group, extend=False)
            except ModelFailure as error:
                state = _failed(state, error)
            self._sessions.save(Revision(state))
            return state

    def recalculate(self, session_id: str, expected_revision: int) -> SessionState:
        with self._uow:
            previous = self._current(session_id, expected_revision)
            state = replace(previous, revision=previous.revision + 1)
            try:
                state = self._analyze(state, self._group(state), extend=False)
                state = replace(
                    state,
                    candidates=tuple(
                        replace(
                            c,
                            returned_reason=next(
                                (
                                    old.returned_reason
                                    for old in previous.candidates
                                    if old.code == c.code
                                ),
                                None,
                            )
                            or c.returned_reason,
                        )
                        for c in state.candidates
                    ),
                )
            except (ModelFailure, CatalogEmpty) as error:
                state = _failed(state, error)
            self._sessions.save(Revision(state))
            return state

    def _analyze(self, state: SessionState, group: Group, *, extend: bool = True) -> SessionState:
        """Факты, кандидаты, статус и следующий вопрос; `extend` — дописать предупреждения
        извлечения (при ответе они уже есть: текст тот же). Ответы по другой группе хранятся в
        истории, но не применяются."""
        selected = group.position
        dialog = tuple(t for t in state.dialog if t.group == selected.code)
        extracted = [self._fact_extractor.extract((message,), group) for message in state.messages]
        parsed = tuple(f for facts, _ in extracted for f in facts)
        warnings = tuple(dict.fromkeys(w for _, items in extracted for w in items))
        facts = merge(parsed, dialog, [m.id for m in state.messages])
        facts = reconcile(apply_history(facts, state.fact_history, selected.code), group)
        active = [f for f in facts if f.status not in INACTIVE]
        conflict_names = {
            f.characteristic_name
            for f in active
            if f.status == "ambiguous"
            and f.normalization_rule != "explicit_unverified"
            and f.characteristic_name is not None
        }
        warnings = tuple(w for w in warnings if not w.startswith("противоречивые значения поля"))
        warnings = (
            *warnings,
            *(f"противоречивые значения поля {name}" for name in sorted(conflict_names) if name),
        )
        leaves = sorted(group.leaves, key=lambda p: p.code)
        candidates = tuple(_candidate(p, active) for p in leaves)
        remaining = [p for p, c in zip(leaves, candidates, strict=True) if not c.excluded]
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
            suppressed = {f.characteristic_name for f in facts if f.status == "deleted"}
            derived, missing = derive(remaining[0], active, suppressed=suppressed)
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
        pending_correction = next(
            (f for f in active if f.normalization_rule == "correction_needs_binding"), None
        )
        if pending_correction is not None:
            question = Question(
                question_id,
                "conflict",
                pending_correction.characteristic_name or "Характеристика",
                "Уточните исправление: укажите характеристику и часть товара в редакторе факта",
                (),
                False,
            )
        if question is not None and question.kind == "conflict":
            status = SessionStatus.CONFLICT
        old_candidates = {c.code: c for c in state.candidates}
        same_group = state.path is not None and state.path.group.code == selected.code
        candidates = tuple(
            replace(
                c,
                returned_reason=(
                    "Позиция возвращена после изменения фактов: "
                    "прежнее ограничение больше не исключает её"
                    if same_group
                    and c.code in old_candidates
                    and old_candidates[c.code].excluded
                    and not c.excluded
                    else None
                ),
            )
            for c in candidates
        )
        diagnostics = (
            self._diagnostics.run(facts, group, state.messages) if self._diagnostics else ()
        )
        return replace(
            state,
            status=status,
            results_stale=False,
            analysis_revision=state.revision,
            facts=facts,
            path=NarrowingPath(selected.category, GroupRef(selected.code, selected.name), count),
            candidates=candidates,
            candidate_counts=CandidateCounts(count, len(remaining), count - len(remaining)),
            warnings=tuple(
                dict.fromkeys(
                    (
                        *(
                            w
                            for w in state.warnings
                            if not w.startswith("противоречивые значения поля")
                        ),
                        *warnings,
                    )
                )
            ),
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
        results_stale=True,
        card_complete=False,
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
