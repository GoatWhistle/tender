"""Следующий вопрос диалога: детерминированно, без модели (раздел 10.2 плана).

Порядок: конфликт значений одного поля, затем различение оставшихся позиций, после кода —
недостающие обязательные характеристики. Варианты — только реальные допустимые значения из
схем позиций; полезность различающего вопроса — ожидаемая доля исключённых позиций минус
штрафы за число вариантов и за повтор. Это эвристика, а не вероятность ответа пользователя.

«Не знаю» факта не порождает и выключает вопрос по характеристике до смены контекста: нового
сообщения или ответа на другой вопрос.
"""

from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import Literal

from app.domain.catalog import Characteristic, Position, Value
from app.domain.facts import CheckResult, Fact, normalized
from app.domain.rules import canonical, check_rule, supported

# Доменные константы эвристики, не настройки: подбор весов по замерам — отдельная задача.
OPTION_PENALTY = 0.05  # за каждый вариант сверх двух
REPEAT_PENALTY = 0.3  # вопрос, на который уже ответили «не знаю», после смены контекста

QuestionKind = Literal["conflict", "discriminate", "required"]


@dataclass(frozen=True)
class QuestionOption:
    id: str
    label: str


@dataclass(frozen=True)
class Question:
    """`characteristic` — название характеристики: по нему привязаны факты."""

    question_id: str
    kind: QuestionKind
    characteristic: str
    text: str
    options: tuple[QuestionOption, ...]
    allow_unknown: bool = True


@dataclass(frozen=True)
class DialogTurn:
    """Ответ на вопрос; без `option_id` — «не знаю». `messages` — сколько сообщений было в
    сессии в момент ответа, `revision` — ревизия, созданная ответом, `group` — код группы, по
    которой задан вопрос: после смены группы ответ не применяется."""

    question_id: str
    kind: QuestionKind
    characteristic: str
    revision: int
    messages: int
    option_id: str | None = None
    fact: Fact | None = None
    group: str = ""


@dataclass(frozen=True)
class CommonField:
    characteristic: str
    values: tuple[str, ...]


@dataclass(frozen=True)
class RequiredField:
    characteristic: str  # код характеристики выбранной позиции
    name: str


@dataclass(frozen=True)
class Step:
    """`indistinct` — ни один ответ ни на один вопрос не меняет множество позиций;
    `unanswered` — различающие характеристики, на которые ответили «не знаю»."""

    question: Question | None
    indistinct: bool = False
    unanswered: tuple[str, ...] = ()


def merge(
    parsed: Sequence[Fact], dialog: Sequence[DialogTurn], messages: Sequence[str]
) -> tuple[Fact, ...]:
    """Факты парсера и ответов по порядку событий: ответ замещает факты по тому же полю из
    сообщений до него, значение из более позднего сообщения замещает ответ. `messages` — ID
    сообщений по порядку."""
    order = {m: i for i, m in enumerate(messages)}

    def newer(fact: Fact, turn: DialogTurn) -> bool:
        return fact.source is not None and order.get(fact.source.message_id, -1) >= turn.messages

    facts = list(parsed)
    for turn in dialog:
        if turn.fact is None:
            continue
        name = turn.fact.characteristic_name
        later = False
        for i, fact in enumerate(facts):
            if fact.characteristic_name != name or fact.status == "superseded":
                continue
            if fact.origin == "parser" and newer(fact, turn):
                later = True
            else:
                facts[i] = replace(fact, status="superseded")
        facts.append(replace(turn.fact, status="superseded") if later else turn.fact)
    # Привязанный факт парсера бывает `ambiguous` только из-за противоречия; если противоречащие
    # ему значения замещены, он снова принят.
    conflicting: dict[str, int] = {}
    for fact in facts:
        if fact.status == "ambiguous" and fact.characteristic_name is not None:
            conflicting[fact.characteristic_name] = conflicting.get(fact.characteristic_name, 0) + 1
    return tuple(
        replace(f, status="accepted_from_text")
        if f.status == "ambiguous" and conflicting.get(f.characteristic_name or "") == 1
        else f
        for f in facts
    )


def skipped(dialog: Sequence[DialogTurn], messages: int) -> list[str]:
    """Характеристики с «не знаю» в текущем контексте: после последнего ответа и без новых
    сообщений."""
    names: list[str] = []
    for turn in dialog:
        if turn.fact is not None or turn.messages != messages:
            names = []
        if turn.fact is None and turn.messages == messages and turn.characteristic not in names:
            names.append(turn.characteristic)
    return names


def derive(
    position: Position, facts: Sequence[Fact], *, unconfirmed: frozenset[str] = frozenset()
) -> tuple[tuple[Fact, ...], tuple[RequiredField, ...]]:
    """Для выбранной позиции: обязательные поля с единственным допустимым значением
    заполняются из каталога, остальные без принятого факта — недостающие."""
    known = {f.characteristic_name for f in facts if f.accepted}
    disputed = set(_conflicts(list(facts)))
    derived: list[Fact] = []
    missing: list[RequiredField] = []
    for characteristic in position.characteristics:
        if not characteristic.required or characteristic.name in known:
            continue
        options = _options(characteristic.name, [position], f"catalog:{characteristic.code}")
        if len(options) == 1 and characteristic.name not in disputed | unconfirmed:
            derived.append(replace(options[0][1], origin="catalog", status="derived_from_catalog"))
        else:
            missing.append(RequiredField(characteristic.code, characteristic.name))
    return tuple(derived), tuple(missing)


def next_step(
    remaining: Sequence[Position],
    facts: Sequence[Fact],
    dialog: Sequence[DialogTurn],
    messages: int,
    question_id: str,
) -> Step:
    """Следующий вопрос по оставшимся позициям и действующим (не замещённым) фактам."""
    off = skipped(dialog, messages)
    for name, conflicting in _conflicts(facts).items():
        if name not in off:
            return Step(_question(question_id, "conflict", name, _conflict_options(conflicting)))
    known = {f.characteristic_name for f in facts if f.accepted}
    if len(remaining) == 1:
        for characteristic in remaining[0].characteristics:
            name = characteristic.name
            if not characteristic.required or name in known or name in off:
                continue
            options = _options(name, remaining, "")
            if len(options) > 1:
                return Step(_question(question_id, "required", name, [o for o, _ in options]))
        return Step(None)
    repeated = {t.characteristic for t in dialog if t.fact is None}
    best: tuple[float, str, list[QuestionOption]] | None = None
    useful: list[str] = []
    for name in _names(remaining):
        options = _options(name, remaining, "")
        excluded = [
            sum(check_rule(p, fact).result == CheckResult.MISMATCH for p in remaining)
            for _, fact in options
        ]
        if not any(excluded):
            continue
        useful.append(name)
        # известное поле может различать (факт частично внутри интервалов), но не спрашивается
        if name in known or name in off:
            continue
        utility = (
            sum(excluded) / len(excluded) / len(remaining)
            - OPTION_PENALTY * max(0, len(options) - 2)
            - (REPEAT_PENALTY if name in repeated else 0)
        )
        if best is None or utility > best[0]:
            best = utility, name, [o for o, _ in options]
    if best is not None:
        return Step(_question(question_id, "discriminate", best[1], best[2]))
    return Step(None, indistinct=not useful, unanswered=tuple(n for n in useful if n in off))


def answer_fact(
    question: Question,
    option_id: str,
    remaining: Sequence[Position],
    facts: Sequence[Fact],
) -> Fact | None:
    """Факт выбранного варианта. Варианты строятся заново из тех же данных, что и вопрос;
    другой текст варианта значит, что каталог или факты сменились — ответ не применяется."""
    fact_id = f"answer:{question.question_id}"
    if question.kind == "conflict":
        conflicting = _conflicts(facts).get(question.characteristic, [])
        options = [
            (o, replace(f, id=fact_id, origin="user", status="confirmed_by_user"))
            for o, f in zip(_conflict_options(conflicting), conflicting, strict=True)
        ]
    else:
        options = _options(question.characteristic, remaining, fact_id)
    stored = {o.id: o.label for o in question.options}
    for option, fact in options:
        if option.id == option_id and stored.get(option_id) == option.label:
            return fact
    return None


def common_fields(positions: Sequence[Position]) -> tuple[CommonField, ...]:
    """Характеристики с одинаковым набором допустимых значений у всех позиций."""
    fields: list[CommonField] = []
    for name in _names(positions):
        characteristics = [p.char(name) for p in positions]
        if any(c is not None and not supported(c) for c in characteristics):
            continue
        keys = {
            frozenset(canonical(v) for v in c.values) if c is not None else None
            for c in characteristics
        }
        first = characteristics[0]
        if len(keys) == 1 and first is not None and first.values:
            fields.append(CommonField(name, tuple(v.label() for v in first.values)))
    return tuple(fields)


def _names(positions: Sequence[Position]) -> list[str]:
    """Названия характеристик в порядке каталога: по позициям, затем по схеме позиции."""
    return list(dict.fromkeys(c.name for p in positions for c in p.characteristics))


def _options(
    name: str, positions: Sequence[Position], fact_id: str
) -> list[tuple[QuestionOption, Fact]]:
    """Различные допустимые значения характеристики у позиций — как в каталоге, без
    разрезания пересекающихся интервалов."""
    seen: set[object] = set()
    options: list[tuple[QuestionOption, Fact]] = []
    for position in positions:
        characteristic = position.char(name)
        if characteristic is None or not supported(characteristic):
            continue
        for value in characteristic.values:
            key = canonical(value)
            if key in seen:
                continue
            seen.add(key)
            option = QuestionOption(f"o{len(options) + 1}", value.label())
            options.append((option, _fact(fact_id, characteristic, value)))
    return options


def _fact(fact_id: str, characteristic: Characteristic, value: Value) -> Fact:
    label = value.label()
    if value.text is not None:
        return Fact(
            fact_id,
            characteristic.name,
            characteristic.name,
            value.text,
            None,
            normalized(value.text),
            None,
            "text",
            None,
            "catalog_value",
            origin="user",
            status="confirmed_by_user",
        )
    return Fact(
        fact_id,
        characteristic.name,
        characteristic.name,
        label,
        value.unit,
        label,
        None,
        "interval",
        None,
        "catalog_value",
        origin="user",
        status="confirmed_by_user",
        bounds=value,
    )


def _conflicts(facts: Sequence[Fact]) -> dict[str, list[Fact]]:
    """Поля с противоречивыми значениями из текста: парсер помечает их `ambiguous`."""
    by_name: dict[str, list[Fact]] = {}
    for fact in facts:
        if fact.status == "ambiguous" and fact.characteristic_name is not None:
            by_name.setdefault(fact.characteristic_name, []).append(fact)
    return {name: group for name, group in by_name.items() if len(group) > 1}


def _conflict_options(facts: Sequence[Fact]) -> list[QuestionOption]:
    return [
        QuestionOption(f"o{i}", f"{f.raw_value} {f.raw_unit}" if f.raw_unit else f.raw_value)
        for i, f in enumerate(facts, 1)
    ]


def _question(
    question_id: str, kind: QuestionKind, name: str, options: Sequence[QuestionOption]
) -> Question:
    text = (
        f"В описании разные значения «{name}». Какое верное?"
        if kind == "conflict"
        else f"Какое значение «{name}» у товара?"
    )
    return Question(question_id, kind, name, text, tuple(options))
