from dataclasses import replace
from decimal import Decimal

import pytest

from app.adapter.facts import DeterministicFactExtractor
from app.domain.catalog import Characteristic, CharacteristicKind, Group, Value
from app.domain.sessions import Message


def test_decimal_number_binding_and_original_quote(table_group: Group) -> None:
    text = "🙂 стол ШИРИНОЙ 1,2 м, столешница лдсп"
    facts, warnings = DeterministicFactExtractor().extract((Message("m1", text, ""),), table_group)
    assert warnings == ()
    assert len(facts) == 2
    width, material = facts
    assert width.characteristic_name == "Ширина"
    assert width.value == Decimal("1.2")
    assert width.raw_value == "1,2"
    assert width.unit_code == "006"
    assert width.status == "accepted_from_text"
    assert material.characteristic_name == "Вид материала столешницы"
    assert material.value == "лдсп"
    for fact in facts:
        source = fact.source
        assert source.message_id == "m1"
        assert text[source.start : source.end] == source.quote
    assert width.source.quote == "1,2 м"


@pytest.mark.parametrize("raw", ["100–120", "100-120", "от 100 до 120"])
def test_closed_ranges(table_group: Group, raw: str) -> None:
    facts, warnings = DeterministicFactExtractor().extract(
        (Message("m", f"ширина {raw} см", ""),), table_group
    )
    assert warnings == ()
    assert len(facts) == 1
    assert facts[0].kind == "range"
    assert facts[0].value == (Decimal("100"), Decimal("120"))
    assert facts[0].unit_code == "004"


@pytest.mark.parametrize(
    "text",
    [
        "80×60×75 см",
        "80x60x75",
        "80*60*75",
        "ширина до 120 см",
        "ширина не более 120 см",
        "ширина от 100 см",
        "не ширина 120 см",
        "без лдсп",
        "не из лдсп",
    ],
)
def test_unsafe_fragments_only_warn(table_group: Group, text: str) -> None:
    facts, warnings = DeterministicFactExtractor().extract((Message("m", text, ""),), table_group)
    assert facts == ()
    assert warnings


@pytest.mark.parametrize(
    ("text", "count", "status", "code"),
    [
        ("ширина см", 0, None, None),
        ("ширина 120", 1, "accepted_from_text", None),
        ("120 см", 1, "ambiguous", "004"),
        ("ширина 1.2 метра", 1, "accepted_from_text", "006"),
    ],
)
def test_missing_units_and_fields(
    table_group: Group, text: str, count: int, status: str | None, code: str | None
) -> None:
    facts, _ = DeterministicFactExtractor().extract((Message("m", text, ""),), table_group)
    assert len(facts) == count
    if count:
        assert facts[0].status == status
        assert facts[0].unit_code == code


def with_chars(group: Group, chars: tuple[Characteristic, ...]) -> Group:
    return replace(group, leaves=(replace(group.leaves[0], characteristics=chars),))


def quality(name: str, *texts: str) -> Characteristic:
    return Characteristic(
        name,
        name,
        False,
        True,
        CharacteristicKind.single,
        tuple(Value(str(i), text=t) for i, t in enumerate(texts)),
    )


def test_longest_quality_match_and_excluded_texts(table_group: Group) -> None:
    group = with_chars(
        table_group,
        (quality("Материал", "дерево", "массив дерева", "да", "нет", "50", "не менее 50", "≤± 5"),),
    )
    facts, _ = DeterministicFactExtractor().extract(
        (Message("m", "массив дерева, да нет", ""),), group
    )
    assert len(facts) == 1
    assert facts[0].value == "массив дерева"
    # Числа могут быть найдены как числовые факты, но не как качественные.
    facts, _ = DeterministicFactExtractor().extract((Message("m", "50 ≤± 5", ""),), group)
    assert all(f.kind != "text" for f in facts)


def test_quality_shared_between_fields_is_ambiguous(table_group: Group) -> None:
    group = with_chars(table_group, (quality("Каркас", "ДСП"), quality("Столешница", "ДСП")))
    facts, _ = DeterministicFactExtractor().extract((Message("m", "дсп", ""),), group)
    assert len(facts) == 1
    assert facts[0].status == "ambiguous"
    assert facts[0].characteristic_name is None


def test_numeric_binding_disambiguates_only_exact_concept(table_group: Group) -> None:
    width = table_group.leaves[0].characteristics[0]
    chars = (replace(width, name="Ширина сиденья"), replace(width, name="Ширина спинки"))
    extractor = DeterministicFactExtractor()
    messages = (Message("m", "ширина 120 см", ""),)
    facts, _ = extractor.extract(messages, with_chars(table_group, chars))
    assert facts[0].status == "ambiguous"
    facts, _ = extractor.extract(messages, with_chars(table_group, (*chars, width)))
    assert facts[0].characteristic_name == "Ширина"
    assert facts[0].status == "accepted_from_text"


def test_duplicates_in_equivalent_units_keep_first_quote(table_group: Group) -> None:
    facts, warnings = DeterministicFactExtractor().extract(
        (
            Message("first", "ширина 1,2 м", ""),
            Message("second", "ширина 120 см", ""),
        ),
        table_group,
    )
    assert len(facts) == 1
    assert facts[0].source.message_id == "first"
    assert not warnings


def test_contradictory_messages_are_ambiguous(table_group: Group) -> None:
    facts, warnings = DeterministicFactExtractor().extract(
        (
            Message("first", "ширина 1,2 м", ""),
            Message("second", "ширина 130 см", ""),
        ),
        table_group,
    )
    assert len(facts) == 2
    assert all(f.status == "ambiguous" for f in facts)
    assert "противоречивые значения поля Ширина" in warnings


@pytest.mark.parametrize(
    ("unit", "code"),
    [
        ("мм", "003"),
        ("сантиметров", "004"),
        ("м", "006"),
        ("километр", "008"),
        ('"', "039"),
        ("дюймов", "039"),
        ("граммов", "163"),
        ("кг", "166"),
        ("тонны", "168"),
        ("см³", "111"),
        ("мл", "111"),
        ("дм³", "112"),
        ("литров", "112"),
        ("шт.", "796"),
    ],
)
def test_unit_dictionary(table_group: Group, unit: str, code: str) -> None:
    facts, _ = DeterministicFactExtractor().extract(
        (Message("m", f"ширина 10 {unit}", ""),), table_group
    )
    assert len(facts) == 1
    assert facts[0].unit_code == code
    assert facts[0].raw_unit == unit


def test_unicode_normalization_preserves_coordinates(table_group: Group) -> None:
    group = with_chars(table_group, (quality("Материал", "берёза"),))
    text = "İ🙂 БЕРЕЗА"
    facts, _ = DeterministicFactExtractor().extract((Message("m", text, ""),), group)
    assert facts[0].value == "береза"
    assert facts[0].source.start == 3
    assert facts[0].source.quote == text[3:9] == "БЕРЕЗА"


def test_overlapping_quality_values_keep_longest(table_group: Group) -> None:
    group = with_chars(table_group, (quality("Материал", "дерево", "красное дерево"),))
    facts, _ = DeterministicFactExtractor().extract((Message("m", "красное дерево", ""),), group)
    assert [f.value for f in facts] == ["красное дерево"]


def test_close_precise_values_are_not_deduplicated(table_group: Group) -> None:
    facts, warnings = DeterministicFactExtractor().extract(
        (
            Message("a", "ширина 1.000000000000000000000000000001 м", ""),
            Message("b", "ширина 1.000000000000000000000000000002 м", ""),
        ),
        table_group,
    )
    assert len(facts) == 2
    assert warnings
