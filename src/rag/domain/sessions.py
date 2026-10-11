import uuid
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Literal

from rag.domain.catalog import Position, fixed_values
from rag.domain.clarify import Question, narrow, questions
from rag.domain.comparison import indistinguishable
from rag.domain.correction import Corrected, Fix
from rag.domain.errors import InputError, StageError
from rag.domain.search import Ranked
from rag.domain.spec import Doubt, Extra, band, changeable, doubt

SHORTLIST = 5
HISTORY = 12

AUTO_SELECTED = "Характеристики и единицы оставшихся позиций совпадают. Сервис выбрал код автоматически."
NOTHING_FITS = "ни одна позиция группы не подходит под ответы"
LEFT_TO_PICK = (
    "Остались различия в параметрах позиций. Они показаны ниже для сравнения."
)


class Stage(StrEnum):
    CLARIFY = "clarify"
    PICK = "pick"
    SPEC = "spec"
    DONE = "done"
    FAILED = "failed"


class Origin(StrEnum):
    DESCRIPTION = "description"
    ASSISTANT = "assistant"
    MANUAL = "manual"


@dataclass(frozen=True, slots=True)
class ChatMessage:
    role: Literal["user", "assistant"]
    text: str
    id: str = field(default_factory=lambda: uuid.uuid4().hex)


@dataclass(frozen=True, slots=True)
class Step:
    stage: Stage
    position: Position | None = None
    message: str | None = None
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class Outcome:
    code: str
    name: str
    okpd2: str
    okpd2_name: str
    fixed: dict[str, str]
    chosen: dict[str, list[str]]
    entered: dict[str, float]
    doubts: dict[str, Doubt]
    extras: list[Extra]


@dataclass
class Session:
    description: str
    corrected: str
    fixes: list[Fix]
    issues: list[str]
    ranked: list[Ranked]
    leaves: list[Position] = field(default_factory=list)
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    stage: Stage = Stage.CLARIFY
    answers: dict[str, str | None] = field(default_factory=dict)
    from_description: dict[str, str] = field(default_factory=dict)
    context: list[str] = field(default_factory=list)
    group: Position | None = None
    position: Position | None = None
    chosen: dict[str, tuple[str, ...]] = field(default_factory=dict)
    origins: dict[str, Origin] = field(default_factory=dict)
    numbers: dict[str, float] = field(default_factory=dict)
    extras: list[Extra] = field(default_factory=list)
    extras_allowed: bool = True
    message: str | None = None
    selection_reason: str | None = None
    messages: list[ChatMessage] = field(default_factory=list)

    @classmethod
    def of(cls, corrected: Corrected, ranked: list[Ranked]) -> "Session":
        return cls(
            corrected.original,
            corrected.corrected,
            list(corrected.fixes),
            list(corrected.issues),
            ranked,
        )

    @property
    def editing(self) -> bool:
        return self.stage in (Stage.SPEC, Stage.DONE)

    @property
    def shortlist(self) -> list[Ranked]:
        return self.ranked[:SHORTLIST]

    @property
    def question(self) -> Question | None:
        if self.stage != Stage.CLARIFY:
            return None
        qs = questions(self.leaves, self.answers)
        return qs[0] if qs else None

    @property
    def characteristics(self) -> list[Question]:
        return changeable(self.position) if self.position else []

    @property
    def missing(self) -> list[str]:
        return [
            q.name
            for q in self.characteristics
            if q.required and q.name not in self.chosen
        ]

    @property
    def entered(self) -> dict[str, float]:
        qs = {q.name: q for q in self.characteristics}
        return {
            name: x
            for name, x in self.numbers.items()
            if name in qs and self.chosen.get(name) == (band(qs[name], x),)
        }

    @property
    def doubts(self) -> dict[str, Doubt]:
        qs = {q.name: q for q in self.characteristics}
        found = {name: doubt(qs[name], x) for name, x in self.entered.items()}
        return {name: code for name, code in found.items() if code}

    def expect(self, *stages: Stage) -> None:
        if self.stage not in stages:
            raise StageError(
                f"этап {self.stage}, а действие доступно на: {', '.join(stages)}"
            )

    def characteristic(self, name: str) -> Question:
        q = next((q for q in self.characteristics if q.name == name), None)
        if q is None:
            raise InputError(f"у позиции нет изменяемой характеристики «{name}»")
        return q

    def ranked_group(self, code: str) -> Position:
        rk = next((rk for rk in self.ranked if rk.hit.position.code == code), None)
        if rk is None:
            raise InputError(f"{code} нет среди групп поиска")
        return rk.hit.position

    def leaf(self, code: str) -> Position:
        p = next((p for p in self.leaves if p.code == code), None)
        if p is None:
            raise InputError(f"{code} нет среди оставшихся позиций")
        return p

    def enter_group(self, group: Position, leaves: list[Position]) -> None:
        self.selection_reason = None
        self.group = group
        self.leaves = leaves
        self.context = [self.corrected]
        self.position = None
        self.chosen = {}
        self.origins = {}
        self.numbers = {}
        self.extras = []

    def enter_spec(self, position: Position) -> None:
        self.position = position
        self.leaves = [position]
        self.stage = Stage.SPEC
        self.extras_allowed = not position.no_new_features
        self.chosen = {}
        self.origins = {}
        self.numbers = {}

    def fill_from_description(self, found: dict[str, tuple[str, ...]]) -> None:
        self.chosen = dict(found)
        self.origins = dict.fromkeys(found, Origin.DESCRIPTION)

    def set_values(self, values: dict[str, tuple[str, ...]], origin: Origin) -> None:
        for name, labels in values.items():
            if labels:
                self.chosen[name] = labels
                self.origins[name] = origin
            else:
                self.chosen.pop(name, None)
                self.origins.pop(name, None)

    def clear_number(self, name: str) -> None:
        self.chosen.pop(name, None)
        self.origins.pop(name, None)
        self.numbers.pop(name, None)

    def remember(self, user: str, assistant: str) -> None:
        self.messages.extend(
            [ChatMessage("user", user), ChatMessage("assistant", assistant)]
        )

    def finish(self) -> Outcome:
        self.expect(Stage.SPEC, Stage.DONE)
        if self.missing:
            raise InputError(f"не выбраны обязательные: {', '.join(self.missing)}")
        self.stage = Stage.DONE
        self.message = None
        return self.outcome()

    def outcome(self) -> Outcome:
        p = self.position
        if p is None:
            raise StageError("позиция ещё не определена")
        return Outcome(
            code=p.code,
            name=p.name,
            okpd2=p.okpd2,
            okpd2_name=p.okpd2_name,
            fixed=fixed_values(p),
            chosen={n: list(v) for n, v in self.chosen.items()},
            entered=self.entered,
            doubts=self.doubts,
            extras=list(self.extras),
        )


def next_step(
    leaves: list[Position], answers: dict[str, str | None]
) -> tuple[list[Position], Step]:
    leaves = narrow(leaves, answers)
    if not leaves:
        return leaves, Step(Stage.FAILED, message=NOTHING_FITS)
    if len(leaves) == 1:
        return leaves, Step(Stage.SPEC, leaves[0])
    if indistinguishable(leaves) and len({p.no_new_features for p in leaves}) == 1:
        return leaves, Step(
            Stage.SPEC, min(leaves, key=lambda p: p.code), reason=AUTO_SELECTED
        )
    if not questions(leaves, answers):
        return leaves, Step(Stage.PICK, message=LEFT_TO_PICK)
    return leaves, Step(Stage.CLARIFY)
