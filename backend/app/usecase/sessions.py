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
    QuestionOption,
    RequiredField,
    answer_fact,
    common_fields,
    derive,
    merge,
    next_step,
)
from app.domain.drafts import DraftState, DraftSummary, SavedDraft
from app.domain.enum_mapping import EnumProposal, EnumResolution, enum_fields
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
from app.domain.exports import CardExport, export_card
from app.domain.fact_edits import INACTIVE, FactInput, apply_history, reconcile
from app.domain.facts import CheckResult, Fact, FactSource, RuleCheck, component_key, normalized
from app.domain.group_validation import GroupPolicy
from app.domain.inference import ChoiceOption, ChoiceQuestion, Verdict
from app.domain.rules import check_rule, explain, selection_conflict, supported
from app.domain.search import SearchResult
from app.domain.sessions import (
    Alternative,
    AnalysisError,
    Candidate,
    CandidateCounts,
    CatalogRef,
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
from app.usecase.enum_mapping import EnumMapper
from app.usecase.extraction import VerifiedExtractor, explicit_model_correction
from app.usecase.group_validation import verify_groups
from app.usecase.interface import (
    CatalogRepository,
    DecisionBackend,
    FactExtractor,
    GroupSearcher,
    SessionsRepository,
    SpellingService,
    UnitOfWork,
)
from app.usecase.spelling import spelling_diagnostics

# Вопрос decision-модели, описан ли товар: ближайшая группа есть у любой строки, и косинус
# мусора доходит до косинуса настоящих товаров (evals/reports/2026-10-10-out-of-scope.md).
RELEVANCE = ChoiceQuestion(
    "relevance",
    "Что это за текст?",
    (
        ChoiceOption("product", "Описание товара или изделия"),
        ChoiceOption("junk", "Бессмысленный набор символов или текст не о товаре"),
    ),
)
JUNK_PROBABILITY = 0.5
OUT_OF_SCOPE = "Описание не похоже на товар: опишите, что это, из чего и какого размера"


class Sessions:
    """`min_similarity` — косинус ближайшей группы, ниже которого текст сразу вне справочника;
    выше него `decision` проверяет, описан ли товар. Для выбора назначения модель обязательна."""

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
        verified_extractor: VerifiedExtractor | None = None,
        decision: DecisionBackend | None = None,
        min_similarity: float = 0.0,
        group_top_k: int = 10,
    ) -> None:
        if group_top_k not in (5, 10):
            raise ValueError("group_top_k должен быть 5 или 10")
        self._group_top_k = group_top_k
        self._group_policy = GroupPolicy()

        self._verified_extractor = verified_extractor
        self._enum_mapper = enum_mapper
        self._spelling = spelling
        self._diagnostics = diagnostics
        self._decision = decision
        self._min_similarity = min_similarity
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

    def save_draft(self, session_id: str, expected_revision: int, input_text: str) -> DraftState:
        with self._uow:
            state = self._current(session_id, expected_revision)
            draft = SavedDraft(
                session_id, state.revision, input_text, datetime.now(UTC).isoformat()
            )
            self._sessions.save_draft(draft)
            return DraftState(state, draft.input_text, draft.saved_revision, draft.saved_at)

    def open_draft(self, session_id: str) -> DraftState:
        with self._uow:
            state = self._sessions.latest(session_id)
            if state is None:
                raise SessionNotFound()
            draft = self._sessions.draft(session_id)
            return (
                DraftState(state, draft.input_text, draft.saved_revision, draft.saved_at)
                if draft
                else DraftState(state)
            )

    def drafts(self) -> list[DraftSummary]:
        with self._uow:
            result = []
            for draft in self._sessions.drafts():
                state = self._sessions.latest(draft.session_id)
                if state is not None:
                    title = state.messages[0].text if state.messages else draft.input_text
                    result.append(
                        DraftSummary(
                            state.session_id,
                            title[:120] or "Без описания",
                            state.revision,
                            draft.saved_revision,
                            draft.saved_at,
                        )
                    )
            return result

    def export(self, session_id: str, expected_revision: int | None = None) -> CardExport:
        state = self.get(session_id)
        if expected_revision is not None and state.revision != expected_revision:
            raise StaleRevision()
        return export_card(state)

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
                fact_history=previous.fact_history,
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
                state = self._select_group(state, previous)
            except (ModelFailure, CatalogEmpty) as error:
                state = _failed(state, error)
            self._sessions.save(Revision(state, key, text))
            return state

    def _select_group(self, state: SessionState, previous: SessionState) -> SessionState:
        # Сохраняем исходные сообщения и ответы о назначении в порядке событий.
        parts = []
        for count, message in enumerate(state.messages, 1):
            parts.append(message.text)
            parts.extend(
                t.clarification
                for t in state.dialog
                if t.kind == "purpose" and t.messages == count and t.clarification is not None
            )
        description = "\n".join(parts)
        result = self._search.run(description, category=None, limit=self._group_top_k)
        # Порт поиска возвращает группы; защищаемся и от дублей/дочерних позиций адаптера.
        hits = []
        seen: set[str] = set()
        for hit in result.groups:
            code = hit.group.group
            if code in seen:
                continue
            selected = self._catalog.position(code)
            if selected is None or not selected.is_group:
                raise ModelFailure("Поиск вернул неизвестную группу")
            seen.add(code)
            hits.append(replace(hit, group=selected))
            if len(hits) == self._group_top_k:
                break
        result = replace(result, groups=tuple(hits))
        state = replace(
            state,
            path=None,
            candidates=(),
            candidate_counts=CandidateCounts(),
            facts=(),
            alternatives=(),
            group_checks=(),
            next_question=None,
            enum_proposals=(),
            missing_required=(),
            common_fields=(),
            unanswered=(),
            unsupported_rules=(),
            editable_fields=(),
            normalizations=(),
            card_complete=False,
            errors=tuple(
                e
                for e in state.errors
                if (isinstance(e, Diagnostic) and not e.rule_ref)
                or (isinstance(e, AnalysisError) and e.code.startswith("spelling_"))
            ),
            warnings=result.messages,
        )
        if not hits:
            return self._purpose_question(state)
        if self._out_of_scope(description, result):
            return replace(
                state,
                status=SessionStatus.OUT_OF_SCOPE,
                results_stale=False,
                analysis_revision=state.revision,
                warnings=(*result.messages, OUT_OF_SCOPE),
            )
        groups = tuple(self._catalog_group(h.group) for h in hits)
        checks = verify_groups(
            self._decision, description, groups, state.revision, self._group_policy
        )
        latest_purpose = next((t for t in reversed(state.dialog) if t.kind == "purpose"), None)
        clarified_code = (
            latest_purpose.option_id
            if latest_purpose is not None and latest_purpose.messages == len(state.messages)
            else None
        )
        selected_code = self._group_policy.select(checks, clarified_code)
        state = replace(state, group_checks=checks)
        # Пять лучших проверенных альтернатив: соответствие, затем исходный retrieval-ранг.
        rank = {Verdict.supported: 0, Verdict.not_stated: 1, Verdict.contradicted: 2}
        ordered = sorted(zip(hits, checks, strict=True), key=lambda pair: rank[pair[1].verdict])
        state = replace(
            state,
            alternatives=tuple(
                Alternative(
                    h.group.code,
                    h.group.name,
                    h.group.category,
                    h.score,
                    {"lexical": h.lexical, "vector": h.vector, "synonym": h.synonym},
                )
                for h, _ in ordered
                if h.group.code != selected_code
            )[:5],
        )
        if selected_code is None:
            return self._purpose_question(state)
        group = next(g for g in groups if g.position.code == selected_code)
        state = self._correct_text(state, previous, group)
        return self._analyze(state, group)

    def _purpose_question(self, state: SessionState) -> SessionState:
        possible = [c for c in state.group_checks if c.verdict != Verdict.contradicted]
        return replace(
            state,
            status=SessionStatus.NEEDS_CLARIFICATION,
            results_stale=False,
            analysis_revision=state.revision,
            next_question=Question(
                f"purpose:{state.revision}",
                "purpose",
                "Назначение",
                "Для какого назначения нужен товар? Выберите подходящее или уточните в сообщении.",
                (
                    *tuple(QuestionOption(c.code, c.name) for c in possible),
                    QuestionOption("other", "Другое"),
                ),
            ),
        )

    def _answer_purpose(
        self,
        previous: SessionState,
        question: Question,
        option_id: str | None,
    ) -> SessionState:
        if option_id is not None and option_id not in {o.id for o in question.options}:
            raise OptionNotFound()
        clarification = next((o.label for o in question.options if o.id == option_id), None)
        if option_id == "other":
            clarification = "Другое назначение; предложенные варианты не подходят"
        elif clarification is not None:
            clarification = "Уточнение назначения пользователем: " + clarification
        turn = DialogTurn(
            question.question_id,
            "purpose",
            "Назначение",
            previous.revision + 1,
            len(previous.messages),
            option_id,
            clarification=clarification,
        )
        state = replace(previous, revision=previous.revision + 1, dialog=(*previous.dialog, turn))
        if option_id is None or option_id == "other":
            # Без нового назначения повторять тот же вопрос/проверку бессмысленно.
            state = replace(
                state,
                next_question=None,
                analysis_revision=state.revision,
                warnings=(*state.warnings, "Опишите назначение товара в сообщении"),
            )
        else:
            try:
                state = self._select_group(state, previous)
            except (ModelFailure, CatalogEmpty) as error:
                state = _failed(
                    replace(
                        state,
                        path=None,
                        candidates=(),
                        candidate_counts=CandidateCounts(),
                        group_checks=(),
                        alternatives=(),
                    ),
                    error,
                )
        self._sessions.save(Revision(state))
        return state

    def _out_of_scope(self, description: str, result: SearchResult) -> bool:
        """Найденное по коду КТРУ или проверенному синониму в справочнике заведомо есть."""
        top = result.groups[0]
        if top.found_by == "code" or top.synonym.rank is not None:
            return False
        if result.similarity is not None and result.similarity < self._min_similarity:
            return True
        if self._decision is None:
            return False
        (answer,) = self._decision.choose(description, [RELEVANCE]).answers
        return answer.probabilities["junk"] >= JUNK_PROBABILITY

    def answer(self, session_id: str, question_id: str, option_id: str | None) -> SessionState:
        """Ответ на вопрос последней ревизии: новая ревизия с полным пересчётом без поиска —
        группа та же, текст не менялся."""
        with self._uow:
            previous = self._sessions.latest(session_id, lock=True)
            if previous is None:
                raise SessionNotFound()
            question = previous.next_question
            if (
                question is not None
                and question.question_id == question_id
                and question.kind == "purpose"
            ):
                return self._answer_purpose(previous, question, option_id)
            if question is None or question.question_id != question_id or previous.path is None:
                raise StaleQuestion()
            code = previous.path.group.code
            selected = self._catalog.position(code)
            if selected is None:
                raise CatalogEmpty()
            group = self._catalog_group(selected)
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
            if fact is not None:
                targets = tuple(
                    f
                    for f in previous.facts
                    if f.status not in INACTIVE
                    and f.characteristic_name == fact.characteristic_name
                    and component_key(f) == component_key(fact)
                )
                state = _record_change(state, "confirm", targets, (fact,), code)
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
            message_count=len(state.messages),
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
            message_count=len(state.messages),
        )
        return replace(state, fact_history=(*state.fact_history, event))

    def _group(self, state: SessionState) -> Group:
        selected = self._catalog.position(state.path.group.code) if state.path else None
        if selected is None:
            raise CatalogEmpty()
        return self._catalog_group(selected)

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
                    replace(b.fact(group, f), source=f.source)
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
                    or old.requires_binding
                    or old.negated
                ):
                    raise InvalidFactEdit(
                        "Сначала укажите характеристику и часть товара в редакторе"
                    )
                after = (
                    replace(
                        old,
                        id=str(uuid4()),
                        status="confirmed_by_user",
                        origin="decision" if old.origin == "decision" else "user",
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
                after = (replace(value.fact(group, old), source=source),)
            else:
                raise InvalidFactEdit()
            state = _record_change(
                replace(previous, revision=previous.revision + 1),
                action,
                targets,
                after,
                group.position.code,
                restored_from=old.id if action == "restore" and old else None,
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
                if state.path is None:
                    state = self._select_group(state, previous)
                else:
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

    def resolve_enum(
        self,
        session_id: str,
        expected_revision: int,
        proposal_id: str,
        action: str,
        values: Sequence[str] = (),
    ) -> SessionState:
        with self._uow:
            previous = self._current(session_id, expected_revision)
            if previous.path is None:
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
            group = self._catalog_group(selected)
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
            targets = tuple(
                f
                for f in previous.facts
                if f.status not in INACTIVE and f.characteristic_name == proposal.characteristic
            )
            if chosen:
                state = _record_change(state, "confirm", targets, tuple(confirmed), code)
            try:
                state = self._analyze(state, group, extend=False)
            except ModelFailure as error:
                state = _failed(state, error)
            self._sessions.save(Revision(state))
            return state

    def _catalog_group(self, selected: Position) -> Group:
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
        extracted = [self._fact_extractor.extract((message,), group) for message in state.messages]
        parsed = tuple(f for facts, _ in extracted for f in facts)
        warnings = tuple(dict.fromkeys(w for _, items in extracted for w in items))
        # Качественные поля обрабатываются совместно, чтобы точный парсер не выбрал
        # одну часть многозначного или неоднозначного описания раньше decision-проверки.
        enum_names = {f.name for f in enum_fields(group.leaves)} if self._enum_mapper else set()
        order = {m.id: i for i, m in enumerate(state.messages)}
        cutoffs = {
            f.characteristic_name: event.message_count
            for event in state.fact_history
            if event.group == selected.code
            for f in (*event.before, *event.after)
        }
        parsed = tuple(
            f
            for f in parsed
            if f.characteristic_name not in enum_names
            or (
                f.characteristic_name in cutoffs
                and f.source is not None
                and order.get(f.source.message_id, -1) >= cutoffs[f.characteristic_name]
            )
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
            replace(f, status="superseded")
            if f.characteristic_name in locked
            and (
                f.source is None
                or order.get(f.source.message_id, -1) < resolutions[f.characteristic_name].messages
            )
            else f
            for f in facts
        )
        facts = (*facts, *(f for r in resolutions.values() for f in r.facts))
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
                    and f.verification is None
                    and f.status in {"proposed", "accepted_from_model"}
                    and f.characteristic_name not in skip
                )
                proposals = tuple(p for p in state.enum_proposals if p.characteristic not in skip)
            facts = reconcile(
                apply_history((*facts, *mapped), state.fact_history, selected.code), group
            )
            active = [f for f in facts if f.status not in INACTIVE]
            candidates = tuple(_candidate(p, active) for p in leaves)
            remaining = [p for p, c in zip(leaves, candidates, strict=True) if not c.excluded]
        if self._verified_extractor is not None:
            generated = (
                self._verified_extractor.run(
                    state.messages, facts, group, remaining, state.revision, state.fact_history
                )
                if extend
                else tuple(
                    f for f in state.facts if f.normalization_rule == "verified_extraction_v1"
                )
            )
            if extend and explicit_model_correction(state.messages, facts):
                for new in generated:
                    if (
                        not new.accepted
                        or new.source is None
                        or new.source.message_id != state.messages[-1].id
                    ):
                        continue
                    targets = [
                        f
                        for f in facts
                        if f.accepted
                        and f.characteristic_name == new.characteristic_name
                        and component_key(f) == component_key(new)
                    ]
                    if len(targets) == 1:
                        pending = [
                            f
                            for f in facts
                            if f.status == "ambiguous"
                            and f.normalization_rule == "correction_needs_binding"
                            and f.source
                            and f.source.message_id == new.source.message_id
                        ]
                        state = _record_change(
                            state, "text_correction", (*targets, *pending), (new,), selected.code
                        )
            warnings = (*warnings, *self._verified_extractor.warnings)
            facts = reconcile(
                apply_history((*facts, *generated), state.fact_history, selected.code), group
            )
            active = [f for f in facts if f.status not in INACTIVE]
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
            suppressed = {f.characteristic_name for f in facts if f.status == "deleted"}
            unconfirmed = (
                frozenset(
                    f.characteristic_name
                    for f in active
                    if f.status == "proposed" and f.characteristic_name
                )
                | frozenset(p.characteristic for p in proposals)
                | frozenset(
                    name for name, r in resolutions.items() if not r.facts and name in locked
                )
            )
            derived, missing = derive(
                remaining[0], active, suppressed=suppressed, unconfirmed=unconfirmed
            )
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
        if (
            question is not None
            and question.kind != "conflict"
            and any(p.characteristic == question.characteristic for p in proposals)
        ):
            question = None
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
            editable_fields=tuple(
                sorted({c.name for p in group.leaves for c in p.characteristics})
            ),
            facts=facts,
            enum_proposals=proposals,
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
            catalog_refs=tuple(
                CatalogRef(p.code, c.code, c.name) for p in group.leaves for c in p.characteristics
            ),
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


def _record_change(
    state: SessionState,
    action: str,
    targets: Sequence[Fact],
    after: tuple[Fact, ...],
    group: str,
    *,
    restored_from: str | None = None,
) -> SessionState:
    """Одна история для ответов, модельных предложений и ручного редактора."""
    before = tuple(
        replace(
            f,
            status="deleted" if action == "delete" else "superseded",
            superseded_by=after[i].id if action == "split" else after[0].id if after else None,
        )
        for i, f in enumerate(targets)
    )
    event = FactEvent(
        action,
        state.revision,
        datetime.now(UTC).isoformat(),
        before,
        after,
        group,
        restored_from=restored_from,
        message_count=len(state.messages),
    )
    return replace(
        state,
        facts=apply_history(state.facts, (event,), group),
        fact_history=(*state.fact_history, event),
        results_stale=True,
        card_complete=False,
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
