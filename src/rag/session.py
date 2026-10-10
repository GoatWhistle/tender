import uuid
from dataclasses import asdict, dataclass, field
from enum import StrEnum

from rag.clarify import FIXED, Question, answer, extract, narrow, questions
from rag.comparison import differences
from rag.ktru import value_text
from rag.models import Position
from rag.preprocess import Fix, preprocess
from rag.rerank import Ranked, rerank
from rag.search import Index, query_vector
from rag.spec import Extra, Verdict, changeable, no_new_features, validate


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


class StageError(Exception):
    pass


class InputError(Exception):
    pass


@dataclass
class Session:
    description: str
    corrected: str
    fixes: list[Fix]
    issues: list[str]
    ranked: list[Ranked]
    leaves: list[Position]
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    stage: Stage = Stage.CLARIFY
    answers: dict[str, str | None] = field(default_factory=dict)
    from_description: dict[str, str] = field(default_factory=dict)
    context: list[str] = field(default_factory=list)
    group: Position | None = None
    position: Position | None = None
    chosen: dict[str, tuple[str, ...]] = field(default_factory=dict)
    origins: dict[str, Origin] = field(default_factory=dict)
    extras: list[Extra] = field(default_factory=list)
    extras_allowed: bool = True
    message: str | None = None
    selection_reason: str | None = None
    messages: list[dict[str, str]] = field(default_factory=list)

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

    def result(self) -> dict:
        p = self.position
        if p is None:
            raise StageError("позиция ещё не определена")
        return {
            "code": p.code,
            "name": p.name,
            "okpd2": p.okpd2,
            "okpd2_name": p.okpd2_name,
            "fixed": {
                c.name: "; ".join(value_text(v) for v in c.values)
                for c in p.characteristics
                if c.kind == FIXED
            },
            "chosen": {n: list(v) for n, v in self.chosen.items()},
            "extras": [asdict(e) for e in self.extras],
        }


def _expect(s: Session, *stages: Stage) -> None:
    if s.stage not in stages:
        raise StageError(f"этап {s.stage}, а действие доступно на: {', '.join(stages)}")


async def _advance(s: Session, index: Index) -> None:
    s.leaves = narrow(s.leaves, s.answers)
    if not s.leaves:
        s.stage = Stage.FAILED
        s.message = "ни одна позиция группы не подходит под ответы"
    elif len(s.leaves) == 1:
        await _enter_spec(s, index, s.leaves[0])
    elif (
        not any(differences(s.leaves).values())
        and len({no_new_features(index, p) for p in s.leaves}) == 1
    ):
        selected = min(s.leaves, key=lambda p: p.code)
        s.selection_reason = "Характеристики и единицы оставшихся позиций совпадают. Сервис выбрал код автоматически."
        await _enter_spec(s, index, selected)
    elif not questions(s.leaves, s.answers):
        s.stage = Stage.PICK
        s.message = (
            "Остались различия в параметрах позиций. Они показаны ниже для сравнения."
        )
    else:
        s.stage = Stage.CLARIFY


async def _enter_spec(s: Session, index: Index, p: Position) -> None:
    s.position = p
    s.leaves = [p]
    s.stage = Stage.SPEC
    s.extras_allowed = not no_new_features(index, p)
    s.chosen = dict(await extract("\n".join(s.context), s.characteristics))
    s.origins = dict.fromkeys(s.chosen, Origin.DESCRIPTION)


async def start(index: Index, text: str) -> Session:
    if not text.strip():
        raise InputError("пустое описание")
    pre = await preprocess(text)
    hits = index.search(await query_vector(pre.corrected))
    ranked = (await rerank(pre.corrected, hits)).ranked
    if not ranked:
        raise InputError("поиск ничего не нашёл")
    s = Session(text, pre.corrected, pre.fixes, pre.issues, ranked, [])
    await _enter_group(s, index, ranked[0].hit.position)
    return s


async def _enter_group(s: Session, index: Index, p: Position) -> None:
    s.selection_reason = None
    s.group = p
    s.leaves = index.leaves(p)
    s.context = [s.corrected]
    s.position = None
    s.chosen = {}
    s.origins = {}
    s.extras = []
    found = await extract(s.corrected, questions(s.leaves, {}))
    s.from_description = {n: v[0] for n, v in found.items()}
    s.answers = dict(s.from_description)
    await _advance(s, index)


async def switch_group(s: Session, index: Index, code: str) -> None:
    _expect(s, Stage.CLARIFY, Stage.PICK, Stage.SPEC, Stage.FAILED)
    rk = next((rk for rk in s.ranked if rk.hit.position.code == code), None)
    if rk is None:
        raise InputError(f"{code} нет среди групп поиска")
    s.message = None
    await _enter_group(s, index, rk.hit.position)


async def reply(s: Session, index: Index, text: str) -> None:
    _expect(s, Stage.CLARIFY)
    q = s.question
    if q is None:
        raise StageError("вопросов нет")
    got, s.message = await answer(text, questions(s.leaves, s.answers))
    if got:
        s.answers.update({name: values[0] for name, values in got.items()})
        s.context.append(text)
        await _advance(s, index)


async def choose(s: Session, index: Index, option: int | None) -> None:
    _expect(s, Stage.CLARIFY)
    q = s.question
    if q is None:
        raise StageError("вопросов нет")
    if option is not None and not 1 <= option <= len(q.options):
        raise InputError(f"номер варианта от 1 до {len(q.options)}")
    s.answers[q.name] = q.options[option - 1] if option else None
    if option:
        s.context.append(f"{q.name}: {q.options[option - 1]}")
    s.message = None
    await _advance(s, index)


async def pick(s: Session, index: Index, code: str) -> None:
    _expect(s, Stage.CLARIFY, Stage.PICK)
    p = next((p for p in s.leaves if p.code == code), None)
    if p is None:
        raise InputError(f"{code} нет среди оставшихся позиций")
    s.message = None
    await _enter_spec(s, index, p)


def set_values(s: Session, values: dict[str, list[str]]) -> None:
    _expect(s, Stage.SPEC)
    qs = {q.name: q for q in s.characteristics}
    for name, labels in values.items():
        q = qs.get(name)
        if q is None:
            raise InputError(f"у позиции нет изменяемой характеристики «{name}»")
        if bad := [label for label in labels if label not in q.options]:
            raise InputError(f"«{name}»: нет вариантов {bad}")
        if not q.multiple and len(labels) > 1:
            raise InputError(f"«{name}»: нужен один вариант")
    for name, labels in values.items():
        if labels:
            s.chosen[name] = tuple(dict.fromkeys(labels))
            s.origins[name] = Origin.MANUAL
        else:
            s.chosen.pop(name, None)
            s.origins.pop(name, None)
    s.message = None


async def describe(s: Session, text: str, name: str | None = None) -> None:
    _expect(s, Stage.SPEC)
    qs = s.characteristics
    if name is not None:
        qs = [q for q in qs if q.name == name]
        if not qs:
            raise InputError(f"у позиции нет изменяемой характеристики «{name}»")
    got, s.message = await answer(text, qs)
    s.chosen.update(got)
    s.origins.update(dict.fromkeys(got, Origin.ASSISTANT))


async def add_extra(s: Session, extra: Extra) -> Verdict:
    _expect(s, Stage.SPEC)
    if not s.extras_allowed:
        raise InputError(
            "КТРУ запрещает дополнительные характеристики для этой позиции (noNewFeatures)"
        )
    if not extra.name.strip() or not extra.value.strip():
        raise InputError("нужны название и значение")
    verdict = await validate(s.position, s.chosen, s.extras, extra)
    if verdict.ok:
        s.extras.append(extra)
    s.message = None
    return verdict


def remove_extra(s: Session, n: int) -> None:
    _expect(s, Stage.SPEC)
    if not 0 <= n < len(s.extras):
        raise InputError(f"нет своей характеристики с номером {n}")
    s.extras.pop(n)


def finish(s: Session) -> dict:
    _expect(s, Stage.SPEC, Stage.DONE)
    if s.missing:
        raise InputError(f"не выбраны обязательные: {', '.join(s.missing)}")
    s.stage = Stage.DONE
    s.message = None
    return s.result()
