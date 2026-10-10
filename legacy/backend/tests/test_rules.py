from dataclasses import replace
from decimal import Decimal

import pytest

from app.adapter.facts import DeterministicFactExtractor
from app.domain.catalog import Bound, Group, Value
from app.domain.rules import check_rule
from app.domain.sessions import Message


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("ширина 900 мм", "match"),
        ("ширина 1100 мм", "match"),
        ("ширина 1100,00000000001 мм", "mismatch"),
        ("ширина 1 м", "match"),
        ("ширина 100 см", "match"),
        ("ширина 1 кг", "mismatch"),
        ("ширина 1000", "ambiguous"),
        ("ширина 950–1050 мм", "match"),
        ("ширина 1000–1200 мм", "ambiguous"),
        ("ширина 1200–1300 мм", "mismatch"),
        ("1100 мм", "ambiguous"),
        ("лдсп", "mismatch"),
        ("дсп", "match"),
    ],
)
def test_rule_outcomes(table_group: Group, text: str, expected: str) -> None:
    facts, _ = DeterministicFactExtractor().extract((Message("m", text, ""),), table_group)
    assert len(facts) == 1
    assert check_rule(table_group.leaves[0], facts[0]).result == expected


@pytest.mark.parametrize(
    ("values", "text", "expected"),
    [
        (
            (
                Value(
                    "v",
                    min=Decimal(900),
                    min_op=Bound.greater,
                    max=Decimal(1100),
                    max_op=Bound.less,
                    unit_code="003",
                ),
            ),
            "900",
            "mismatch",
        ),
        (
            (Value("v", min=Decimal(900), max=Decimal(1100), max_op=Bound.less, unit_code="003"),),
            "1100",
            "mismatch",
        ),
        (
            tuple(Value(str(n), concrete=Decimal(n), unit_code="003") for n in (90, 180)),
            "135",
            "mismatch",
        ),
        (
            tuple(Value(str(n), concrete=Decimal(n), unit_code="003") for n in (90, 180)),
            "180",
            "match",
        ),
        (
            (
                Value("a", min=Decimal(90), max=Decimal(100), unit_code="003"),
                Value("b", min=Decimal(100), max=Decimal(120), unit_code="003"),
            ),
            "90–120",
            "match",
        ),
        (
            (
                Value("a", min=Decimal(90), max=Decimal(100), max_op=Bound.less, unit_code="003"),
                Value(
                    "b", min=Decimal(100), min_op=Bound.greater, max=Decimal(120), unit_code="003"
                ),
            ),
            "90–120",
            "ambiguous",
        ),
        ((Value("v", concrete=Decimal(100), unit_code="999"),), "100", "unsupported"),
        ((Value("v", text="не менее 100", unit_code="003"),), "100", "unsupported"),
    ],
)
def test_rule_unions_and_unsupported(
    table_group: Group, values: tuple[Value, ...], text: str, expected: str
) -> None:
    position = table_group.leaves[0]
    position = replace(
        position, characteristics=(replace(position.characteristics[0], values=values),)
    )
    facts, _ = DeterministicFactExtractor().extract(
        (Message("m", f"ширина {text} мм", ""),), table_group
    )
    assert check_rule(position, facts[0]).result == expected


def test_mixed_exact_and_range_union(table_group: Group) -> None:
    position = table_group.leaves[0]
    values = (
        Value("point", concrete=Decimal(100), unit_code="003"),
        Value("range", min=Decimal(100), min_op=Bound.greater, max=Decimal(200), unit_code="003"),
    )
    position = replace(
        position, characteristics=(replace(position.characteristics[0], values=values),)
    )
    facts, _ = DeterministicFactExtractor().extract(
        (Message("m", "ширина 100–200 мм", ""),), table_group
    )
    assert check_rule(position, facts[0]).result == "match"


def test_dimensionless_rules_and_missing_characteristic(table_group: Group) -> None:
    position = table_group.leaves[0]
    dimensionless = replace(
        position,
        characteristics=(
            replace(position.characteristics[0], values=(Value("point", concrete=Decimal(100)),)),
        ),
    )
    facts, _ = DeterministicFactExtractor().extract((Message("m", "ширина 100", ""),), table_group)
    assert check_rule(dimensionless, facts[0]).result == "match"
    assert check_rule(replace(position, characteristics=()), facts[0]).result == "not_applicable"
    assert check_rule(dimensionless, replace(facts[0], unit_code="003")).result == "ambiguous"
