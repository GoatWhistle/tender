"""Выбор следующего вопроса: чистые функции над позициями, фактами и историей диалога."""

from dataclasses import replace
from decimal import Decimal

from app.domain.catalog import Characteristic, CharacteristicKind, Position, Value
from app.domain.dialog import (
    DialogTurn,
    Question,
    answer_fact,
    common_fields,
    derive,
    merge,
    next_step,
)
from app.domain.facts import Fact, FactSource
from app.domain.rules import check_rule


def text(name: str, *values: str, required: bool = False) -> Characteristic:
    return Characteristic(
        name,
        name,
        False,
        required,
        CharacteristicKind.single,
        tuple(Value(f"{name}-{v}", text=v) for v in values),
    )


def width(*ranges: tuple[str, str], required: bool = False) -> Characteristic:
    return Characteristic(
        "width",
        "Ширина",
        True,
        required,
        CharacteristicKind.single,
        tuple(
            Value(
                f"w-{low}-{high}", min=Decimal(low), max=Decimal(high), unit="мм", unit_code="003"
            )
            for low, high in ranges
        ),
    )


def pos(code: str, *characteristics: Characteristic) -> Position:
    return Position(code, code, "Мебель", "", "", False, "g", (), (), characteristics)


def parsed(name: str, value: str, start: int = 0) -> Fact:
    return Fact(
        f"m:{start}",
        name,
        name,
        value,
        "мм",
        Decimal(value),
        "003",
        "number",
        FactSource("m", value, start, start + len(value)),
        "decimal_comma; okei",
        status="ambiguous",
    )


def unknown(question: Question, messages: int = 1) -> DialogTurn:
    return DialogTurn(question.question_id, question.kind, question.characteristic, 2, messages)


def answered(question: Question, option: int, positions: list[Position]) -> DialogTurn:
    option_id = question.options[option].id
    fact = answer_fact(question, option_id, positions, ())
    assert fact is not None
    return DialogTurn(
        question.question_id, question.kind, question.characteristic, 2, 1, option_id, fact
    )


SMALL = pos("a", width(("900", "1100"), required=True), text("Материал", "ДСП", required=True))
LARGE = pos("b", width(("900", "1400"), required=True), text("Материал", "ЛДСП", required=True))


def test_question_skips_characteristic_whose_answers_keep_every_position() -> None:
    # Вложенные интервалы ширины: любой ответ оставляет обе позиции, различает только материал.
    step = next_step([SMALL, LARGE], (), (), 1, "q1")
    assert step.question is not None
    assert step.question.kind == "discriminate"
    assert step.question.characteristic == "Материал"
    assert [o.label for o in step.question.options] == ["ДСП", "ЛДСП"]
    assert step.question.allow_unknown


def test_overlapping_intervals_are_offered_as_is_and_keep_several_positions() -> None:
    positions = [
        pos("a", width(("900", "1100"))),
        pos("b", width(("1000", "1400"))),
        pos("c", width(("1500", "2000"))),
    ]
    step = next_step(positions, (), (), 1, "q1")
    assert step.question is not None
    assert [o.label for o in step.question.options] == [
        "≥ 900 и ≤ 1100 мм",
        "≥ 1000 и ≤ 1400 мм",
        "≥ 1500 и ≤ 2000 мм",
    ]
    first = answer_fact(step.question, step.question.options[0].id, positions, ())
    assert first is not None
    assert first.status == "confirmed_by_user" and first.origin == "user"
    kept = [p.code for p in positions if check_rule(p, first).result != "mismatch"]
    assert kept == ["a", "b"]


def test_identical_positions_are_indistinct_without_question() -> None:
    twins = [pos("a", text("Материал", "ДСП")), pos("b", text("Материал", "ДСП"))]
    step = next_step(twins, (), (), 1, "q1")
    assert step.question is None and step.indistinct
    assert [(f.characteristic, f.values) for f in common_fields(twins)] == [("Материал", ("ДСП",))]


def test_equal_utility_follows_catalog_order() -> None:
    positions = [
        pos("a", text("Цвет", "белый"), text("Материал", "ДСП")),
        pos("b", text("Цвет", "чёрный"), text("Материал", "ЛДСП")),
    ]
    step = next_step(positions, (), (), 1, "q1")
    assert step.question is not None and step.question.characteristic == "Цвет"


def test_more_options_are_penalized() -> None:
    # Без штрафа равны (каждый ответ исключает 2 из 3) и выиграл бы цвет — он раньше в каталоге;
    # у цвета четыре варианта против трёх у материала.
    positions = [
        pos("a", text("Цвет", "белый", "серый"), text("Материал", "ДСП")),
        pos("b", text("Цвет", "чёрный"), text("Материал", "ЛДСП")),
        pos("c", text("Цвет", "синий"), text("Материал", "МДФ")),
    ]
    step = next_step(positions, (), (), 1, "q1")
    assert step.question is not None and step.question.characteristic == "Материал"


def test_unknown_is_not_repeated_until_context_changes() -> None:
    positions = [
        pos("a", text("Цвет", "белый"), text("Материал", "ДСП")),
        pos("b", text("Цвет", "чёрный"), text("Материал", "ЛДСП")),
    ]
    first = next_step(positions, (), (), 1, "q1").question
    assert first is not None and first.characteristic == "Цвет"
    second = next_step(positions, (), (unknown(first),), 1, "q2").question
    assert second is not None and second.characteristic == "Материал"
    both = (unknown(first), unknown(second))
    stuck = next_step(positions, (), both, 1, "q3")
    assert stuck.question is None and not stuck.indistinct
    assert stuck.unanswered == ("Цвет", "Материал")
    # Новое сообщение — новый контекст: вопрос возвращается.
    again = next_step(positions, (), both, 2, "q4").question
    assert again is not None and again.characteristic == "Цвет"


def test_repeat_after_context_change_is_penalized() -> None:
    # Цвет и материал равны по полезности (0.5); после «не знаю» по цвету и смены контекста
    # штраф за повтор отдаёт вопрос материалу.
    positions = [
        pos(code, text("Цвет", color), text("Материал", material))
        for code, color, material in [
            ("a", "белый", "ДСП"),
            ("b", "белый", "ДСП"),
            ("c", "чёрный", "ДСП"),
            ("d", "чёрный", "ЛДСП"),
        ]
    ]
    first = next_step(positions, (), (), 1, "q1").question
    assert first is not None and first.characteristic == "Цвет"
    again = next_step(positions, (), (unknown(first),), 2, "q2").question
    assert again is not None and again.characteristic == "Материал"


def test_answer_to_other_question_changes_context() -> None:
    positions = [
        pos("a", text("Цвет", "белый"), text("Материал", "ДСП"), text("Ножки", "4")),
        pos("b", text("Цвет", "белый"), text("Материал", "ЛДСП"), text("Ножки", "3")),
        pos("c", text("Цвет", "чёрный"), text("Материал", "ДСП"), text("Ножки", "4")),
    ]
    color = next_step(positions, (), (), 1, "q1").question
    assert color is not None
    material = next_step(positions, (), (unknown(color),), 1, "q2").question
    assert material is not None and material.characteristic != color.characteristic
    turn = answered(material, 0, positions)
    assert turn.fact is not None
    left = [p for p in positions if check_rule(p, turn.fact).result != "mismatch"]
    step = next_step(left, (turn.fact,), (unknown(color), turn), 1, "q3")
    assert step.question is not None and step.question.characteristic == color.characteristic


def test_conflict_comes_first_with_values_from_text() -> None:
    facts = (parsed("Ширина", "1000", 0), parsed("Ширина", "1300", 10))
    step = next_step([SMALL, LARGE], facts, (), 1, "q1")
    assert step.question is not None
    assert step.question.kind == "conflict" and step.question.characteristic == "Ширина"
    assert [o.label for o in step.question.options] == ["1000 мм", "1300 мм"]
    fact = answer_fact(step.question, step.question.options[1].id, [SMALL, LARGE], facts)
    assert fact is not None and fact.value == Decimal("1300")
    assert fact.status == "confirmed_by_user" and fact.source == facts[1].source
    turn = DialogTurn("q1", "conflict", "Ширина", 2, 1, step.question.options[1].id, fact)
    merged = merge(facts, (turn,), ["m"])
    assert [f.status for f in merged] == ["superseded", "superseded", "confirmed_by_user"]


def test_required_fields_after_code() -> None:
    chosen = pos(
        "a",
        width(("900", "1100"), required=True),
        text("Материал", "ДСП", "ЛДСП", required=True),
        text("Цвет", "белый", "чёрный"),
    )
    derived, missing = derive(chosen, ())
    assert [(f.characteristic_name, f.status, f.origin) for f in derived] == [
        ("Ширина", "derived_from_catalog", "catalog")
    ]
    assert [(m.characteristic, m.name) for m in missing] == [("Материал", "Материал")]
    step = next_step([chosen], derived, (), 1, "q1")
    assert step.question is not None
    assert step.question.kind == "required" and step.question.characteristic == "Материал"
    skipped = next_step([chosen], derived, (unknown(step.question),), 1, "q2")
    assert skipped.question is None


def test_option_from_stale_catalog_is_not_resolved() -> None:
    step = next_step([SMALL, LARGE], (), (), 1, "q1")
    assert step.question is not None
    changed = replace(step.question, options=(replace(step.question.options[0], label="Другое"),))
    assert answer_fact(changed, changed.options[0].id, [SMALL, LARGE], ()) is None
    assert answer_fact(step.question, "missing", [SMALL, LARGE], ()) is None


def test_later_message_keeps_answer_for_conflict_check() -> None:
    old, new = parsed("Ширина", "1000", 0), parsed("Ширина", "1300", 10)
    old = replace(old, source=FactSource("m1", "1000", 0, 4))
    new = replace(new, source=FactSource("m2", "1300", 10, 14))
    answer = replace(old, id="answer:q1", origin="user", status="confirmed_by_user")
    turn = DialogTurn("q1", "conflict", "Ширина", 2, 1, "o1", answer)
    merged = merge((old, new), (turn,), ["m1", "m2"])
    assert [(f.origin, f.status) for f in merged] == [
        ("parser", "superseded"),
        ("parser", "accepted_from_text"),
        ("user", "confirmed_by_user"),
    ]


def test_unsupported_characteristic_is_not_a_common_field() -> None:
    odd = Characteristic(
        "odd",
        "Вес",
        True,
        False,
        CharacteristicKind.single,
        (Value("x", concrete=Decimal(1), unit_code="999"),),
    )
    twins = [pos("a", odd, text("Материал", "ДСП")), pos("b", odd, text("Материал", "ДСП"))]
    assert [f.characteristic for f in common_fields(twins)] == ["Материал"]
    assert next_step(twins, (), (), 1, "q1").indistinct


def test_known_field_that_still_discriminates_is_not_indistinct() -> None:
    # Диапазон из текста задевает оба интервала — обе позиции остаются, но каталог их различает.
    positions = [pos("a", width(("100", "140"))), pos("b", width(("150", "200")))]
    fact = replace(parsed("Ширина", "150"), status="accepted_from_text")
    fact = replace(fact, kind="range", value=(Decimal("130"), Decimal("160")))
    assert {check_rule(p, fact).result for p in positions} == {"ambiguous"}
    step = next_step(positions, (fact,), (), 1, "q1")
    assert step.question is None and not step.indistinct and step.unanswered == ()


def test_disputed_required_field_is_not_derived() -> None:
    chosen = pos("a", width(("900", "1100"), required=True))
    facts = (parsed("Ширина", "1000", 0), parsed("Ширина", "1050", 10))
    derived, missing = derive(chosen, facts)
    assert derived == () and [m.name for m in missing] == ["Ширина"]
    step = next_step([chosen], facts, (), 1, "q1")
    assert step.question is not None and step.question.kind == "conflict"
