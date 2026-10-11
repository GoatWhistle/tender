from dataclasses import asdict
from typing import Literal

from pydantic import BaseModel, Field

from rag.domain.catalog import Position, Value, fixed_values, value_text
from rag.domain.clarify import Question
from rag.domain.comparison import Row, display_differences
from rag.domain.correction import Fix
from rag.domain.discovery import Discovery, DiscoveryStage
from rag.domain.search import Ranked
from rag.domain.sessions import Origin, Outcome, Session, Stage
from rag.domain.spec import Doubt, Extra, Verdict
from rag.domain.suggestions import Suggestion
from rag.usecase.catalog import Comparison


class FixOut(BaseModel):
    before: str
    after: str
    kind: str

    @classmethod
    def of(cls, f: Fix) -> "FixOut":
        return cls(before=f.before, after=f.after, kind=f.kind)


class GroupOut(BaseModel):
    code: str
    name: str
    okpd2: str
    relevance: int
    reason: str

    @classmethod
    def of(cls, rk: Ranked) -> "GroupOut":
        p = rk.hit.position
        return cls(
            code=p.code,
            name=p.name,
            okpd2=p.okpd2,
            relevance=rk.relevance,
            reason=rk.reason,
        )


class QuestionOut(BaseModel):
    name: str
    required: bool
    multiple: bool
    options: list[str]
    counts: list[int]

    @classmethod
    def of(cls, q: Question) -> "QuestionOut":
        return cls(
            name=q.name,
            required=q.required,
            multiple=q.multiple,
            options=list(q.options),
            counts=list(q.counts),
        )


class CandidateOut(BaseModel):
    code: str
    name: str
    differences: dict[str, str]


class PositionOut(BaseModel):
    code: str
    name: str
    okpd2: str
    okpd2_name: str
    fixed: dict[str, str]

    @classmethod
    def of(cls, p: Position) -> "PositionOut":
        return cls(
            code=p.code,
            name=p.name,
            okpd2=p.okpd2,
            okpd2_name=p.okpd2_name,
            fixed=fixed_values(p),
        )


class BandOut(BaseModel):
    option: str
    min: float | None
    min_inclusive: bool
    max: float | None
    max_inclusive: bool

    @classmethod
    def of(cls, label: str, v: Value) -> "BandOut":
        return cls(
            option=label,
            min=v.min,
            min_inclusive=v.min_op != "greater",
            max=v.max,
            max_inclusive=v.max_op != "less",
        )


class CharacteristicOut(BaseModel):
    name: str
    required: bool
    multiple: bool
    options: list[str]
    values: list[str]
    origin: Origin | None = Field(
        None,
        description="откуда значение: описание поставщика, помощник или ручной выбор",
    )
    unit: str | None = None
    bands: list[BandOut] = Field(
        [], description="числовые диапазоны КТРУ по возрастанию, по одному на вариант"
    )
    number: float | None = Field(
        None,
        description="введённое число, если оно ещё соответствует выбранному диапазону",
    )
    warning: Doubt | None = Field(
        None,
        description="число допустимо по КТРУ, но сомнительно: large — больше крайней границы "
        "в 10 раз, small — меньше в 10 раз, negative — отрицательное при неотрицательных границах",
    )

    @classmethod
    def of(
        cls,
        s: Session,
        q: Question,
        entered: dict[str, float],
        doubts: dict[str, Doubt],
    ) -> "CharacteristicOut":
        return cls(
            name=q.name,
            required=q.required,
            multiple=q.multiple,
            options=list(q.options),
            values=list(s.chosen.get(q.name, ())),
            origin=s.origins.get(q.name) if q.name in s.chosen else None,
            unit=q.unit,
            bands=[BandOut.of(label, v) for label, v in zip(q.options, q.ranges)],
            number=entered.get(q.name),
            warning=doubts.get(q.name),
        )


class ExtraIn(BaseModel):
    name: str
    value: str
    reason: str = ""

    @classmethod
    def of(cls, e: Extra) -> "ExtraIn":
        return cls(name=e.name, value=e.value, reason=e.reason)

    def to_domain(self) -> Extra:
        return Extra(self.name, self.value, self.reason)


class ChatMessageOut(BaseModel):
    id: str
    role: str
    text: str


class SessionOut(BaseModel):
    messages: list[ChatMessageOut]
    id: str
    stage: Stage
    description: str
    corrected: str
    fixes: list[FixOut]
    issues: list[str]
    groups: list[GroupOut] = Field(description="группы после ранжирования")
    group: str = Field(description="код группы, по которой идёт уточнение")
    answers: dict[str, str | None]
    candidates: list[CandidateOut]
    question: QuestionOut | None
    position: PositionOut | None
    characteristics: list[CharacteristicOut]
    extras: list[ExtraIn]
    extras_allowed: bool
    missing: list[str]
    message: str | None
    selection_reason: str | None

    @classmethod
    def of(cls, s: Session) -> "SessionOut":
        entered = s.entered
        doubts = s.doubts
        comparison = display_differences(s.leaves)
        return cls(
            messages=[
                ChatMessageOut(id=m.id, role=m.role, text=m.text) for m in s.messages
            ],
            id=s.id,
            stage=s.stage,
            description=s.description,
            corrected=s.corrected,
            fixes=[FixOut.of(f) for f in s.fixes],
            issues=s.issues,
            groups=[GroupOut.of(rk) for rk in s.shortlist],
            group=s.group.code if s.group else "",
            answers=s.answers,
            candidates=[
                CandidateOut(code=c.code, name=c.name, differences=comparison[c.code])
                for c in s.leaves
            ],
            question=QuestionOut.of(q) if (q := s.question) else None,
            position=PositionOut.of(s.position) if s.position else None,
            characteristics=[
                CharacteristicOut.of(s, q, entered, doubts) for q in s.characteristics
            ],
            extras=[ExtraIn.of(e) for e in s.extras],
            extras_allowed=s.extras_allowed,
            missing=s.missing,
            message=s.message,
            selection_reason=s.selection_reason,
        )


class OutcomeOut(BaseModel):
    code: str
    name: str
    okpd2: str
    okpd2_name: str
    fixed: dict[str, str]
    chosen: dict[str, list[str]]
    entered: dict[str, float]
    doubts: dict[str, Doubt]
    extras: list[ExtraIn]

    @classmethod
    def of(cls, o: Outcome) -> "OutcomeOut":
        return cls(**(asdict(o) | {"extras": [ExtraIn.of(e) for e in o.extras]}))


class SuggestionOut(BaseModel):
    name: str
    unit: str = Field(description="единица измерения или пустая строка")
    options: list[str] = Field(description="типичные значения без единицы")
    value: str = Field(description="значение из описания поставщика или пустая строка")
    evidence: str = Field(description="дословная цитата из описания для value")
    source: str = Field(
        description="СТЕ — по аналогам из каталога СТЕ, ИИ — по знаниям модели"
    )
    share: float | None = Field(description="доля аналогов СТЕ с этой характеристикой")
    why: str

    @classmethod
    def of(cls, x: Suggestion) -> "SuggestionOut":
        return cls(**(asdict(x) | {"options": list(x.options)}))


class SuggestionsOut(BaseModel):
    code: str
    items: list[SuggestionOut]


class VerdictOut(BaseModel):
    accepted: bool
    problems: list[str]
    warnings: list[str]
    fixed: ExtraIn | None
    session: SessionOut

    @classmethod
    def of(cls, verdict: Verdict, s: Session) -> "VerdictOut":
        return cls(
            accepted=verdict.ok,
            problems=verdict.problems,
            warnings=verdict.warnings,
            fixed=ExtraIn.of(verdict.fixed) if verdict.fixed else None,
            session=SessionOut.of(s),
        )


class StartIn(BaseModel):
    description: str


class AnswerIn(BaseModel):
    option: int | None = Field(None, description="номер варианта с 1; 0 — не знаю")
    text: str | None = Field(
        None, description="ответ свободным текстом, разбирает быстрая модель"
    )


class PickIn(BaseModel):
    code: str


class GroupIn(BaseModel):
    automatic: bool = False
    code: str = Field(description="код из groups")


class ValuesIn(BaseModel):
    values: dict[str, list[str]] = Field(
        description="характеристика → варианты; [] — сбросить"
    )


class NumberIn(BaseModel):
    name: str
    value: float | None = Field(description="число в единице КТРУ; null — сбросить")


class TextIn(BaseModel):
    text: str
    name: str | None = Field(
        None, description="только эта характеристика; без него — все"
    )


class SearchCandidate(BaseModel):
    id: str
    name: str
    code: str
    okpd2: str
    relevance: int | None = None
    reason: str | None = None
    differences: dict[str, str]

    @classmethod
    def of(
        cls, p: Position, differences: dict[str, str], ranked: Ranked | None = None
    ) -> "SearchCandidate":
        return cls(
            id=p.code,
            code=p.code,
            name=p.name,
            okpd2=p.okpd2,
            relevance=ranked.relevance if ranked else None,
            reason=ranked.reason if ranked else None,
            differences=differences,
        )


class DiscoveryOut(BaseModel):
    id: str
    stage: DiscoveryStage
    description: str
    corrected: str
    fixes: list[FixOut]
    issues: list[str]
    candidates: list[SearchCandidate]
    rejected: list[SearchCandidate]
    auto_select_code: str | None
    auto_select_reason: str | None

    @classmethod
    def of(cls, d: Discovery) -> "DiscoveryOut":
        comparison = display_differences(d.shown)
        if d.stage == DiscoveryStage.RANKED:
            candidates = [
                SearchCandidate.of(
                    r.hit.position, comparison.get(r.hit.position.code, {}), r
                )
                for r in d.shortlist
            ]
        else:
            candidates = [
                SearchCandidate.of(h.position, comparison.get(h.position.code, {}))
                for h in d.hits
            ]
        return cls(
            id=d.id,
            stage=d.stage,
            description=d.corrected.original,
            corrected=d.corrected.corrected,
            fixes=[FixOut.of(f) for f in d.corrected.fixes],
            issues=d.corrected.issues,
            candidates=candidates,
            rejected=[SearchCandidate.of(r.hit.position, {}, r) for r in d.rejected],
            auto_select_code=d.auto_select_code,
            auto_select_reason=d.auto_select_reason,
        )


class CatalogCharacteristic(BaseModel):
    code: str
    name: str
    kind: str
    required: bool
    values: list[str]


class CatalogPosition(BaseModel):
    code: str
    name: str
    okpd2: str
    okpd2_name: str
    units: list[str]
    rubrics: list[str]
    characteristics: list[CatalogCharacteristic]

    @classmethod
    def of(cls, p: Position) -> "CatalogPosition":
        return cls(
            code=p.code,
            name=p.name,
            okpd2=p.okpd2,
            okpd2_name=p.okpd2_name,
            units=list(p.units),
            rubrics=list(p.rubrics),
            characteristics=[
                CatalogCharacteristic(
                    code=c.code,
                    name=c.name,
                    kind=c.kind,
                    required=c.required,
                    values=[value_text(v) for v in c.values],
                )
                for c in p.characteristics
            ],
        )


class CatalogFound(BaseModel):
    code: str
    name: str
    okpd2: str
    okpd2_name: str

    @classmethod
    def of(cls, p: Position) -> "CatalogFound":
        return cls(code=p.code, name=p.name, okpd2=p.okpd2, okpd2_name=p.okpd2_name)


class ComparisonRow(BaseModel):
    field: Literal["okpd2", "units", "characteristic"]
    name: str | None = None
    values: list[list[str] | None]
    differs: bool

    @classmethod
    def of(
        cls, field: Literal["okpd2", "units", "characteristic"], row: Row
    ) -> "ComparisonRow":
        return cls(
            field=field,
            name=row.name if field == "characteristic" else None,
            values=[list(v) if v is not None else None for v in row.values],
            differs=row.differs,
        )


class CatalogComparison(BaseModel):
    positions: list[CatalogFound]
    rows: list[ComparisonRow]

    @classmethod
    def of(cls, c: Comparison) -> "CatalogComparison":
        return cls(
            positions=[CatalogFound.of(p) for p in c.positions],
            rows=[
                ComparisonRow.of("okpd2", c.okpd2),
                ComparisonRow.of("units", c.units),
                *(ComparisonRow.of("characteristic", row) for row in c.characteristics),
            ],
        )
