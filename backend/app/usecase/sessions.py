"""Сессия анализа: история сообщений, идемпотентность и снимки ревизий."""

from collections.abc import Sequence
from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4

from app.domain.catalog import Group, Position
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
from app.domain.errors import (
    CatalogEmpty,
    IdempotencyConflict,
    ModelFailure,
    OptionNotFound,
    SessionNotFound,
    StaleQuestion,
)
from app.domain.facts import CheckResult, Fact, RuleCheck
from app.domain.inference import ChoiceOption, ChoiceQuestion
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
    UnsupportedRule,
)
from app.usecase.interface import (
    CatalogRepository,
    DecisionBackend,
    FactExtractor,
    GroupSearcher,
    SessionsRepository,
    UnitOfWork,
)

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
    выше него `decision` проверяет, описан ли товар. Без `decision` проверяется только порог."""

    def __init__(
        self,
        uow: UnitOfWork,
        sessions: SessionsRepository,
        search: GroupSearcher,
        catalog: CatalogRepository,
        fact_extractor: FactExtractor,
        decision: DecisionBackend | None = None,
        min_similarity: float = 0.0,
    ) -> None:
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
                session_id, previous.revision + 1, messages=messages, dialog=previous.dialog
            )
            try:
                description = "\n".join(m.text for m in messages)
                result = self._search.run(description, category=None, limit=5)
                if not result.groups:
                    raise CatalogEmpty()
                if self._out_of_scope(description, result):
                    state = replace(
                        state,
                        status=SessionStatus.OUT_OF_SCOPE,
                        warnings=(*result.messages, OUT_OF_SCOPE),
                    )
                else:
                    state = self._analyze(_with_alternatives(state, result), self._top(result))
            except (ModelFailure, CatalogEmpty) as error:
                state = _failed(state, error)
            self._sessions.save(Revision(state, key, text))
            return state

    def _top(self, result: SearchResult) -> Group:
        selected = result.groups[0].group
        return Group.of(selected, self._catalog.children(selected.code))

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
            state = replace(previous, revision=revision, dialog=(*previous.dialog, turn))
            try:
                state = self._analyze(state, group, extend=False)
            except ModelFailure as error:
                state = _failed(state, error)
            self._sessions.save(Revision(state))
            return state

    def _analyze(self, state: SessionState, group: Group, *, extend: bool = True) -> SessionState:
        """Факты, кандидаты, статус и следующий вопрос; `extend` — дописать предупреждения
        извлечения (при ответе они уже есть: текст тот же). Ответы по другой группе хранятся в
        истории, но не применяются."""
        selected = group.position
        dialog = tuple(t for t in state.dialog if t.group == selected.code)
        parsed, warnings = self._fact_extractor.extract(state.messages, group)
        facts = merge(parsed, dialog, [m.id for m in state.messages])
        active = [f for f in facts if f.status != "superseded"]
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
            derived, missing = derive(remaining[0], active)
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
        return replace(
            state,
            status=status,
            facts=facts,
            path=NarrowingPath(selected.category, GroupRef(selected.code, selected.name), count),
            candidates=candidates,
            candidate_counts=CandidateCounts(count, len(remaining), count - len(remaining)),
            warnings=(*state.warnings, *warnings) if extend else state.warnings,
            errors=(),
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


def _with_alternatives(state: SessionState, result: SearchResult) -> SessionState:
    return replace(
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


def _failed(state: SessionState, error: ModelFailure | CatalogEmpty) -> SessionState:
    return replace(
        state,
        status=SessionStatus.TECHNICAL_ERROR,
        errors=(AnalysisError(error.code, error.message),),
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
