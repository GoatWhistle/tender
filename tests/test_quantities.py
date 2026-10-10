import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from rag import api, conversation
from rag.models import Characteristic, Position, Value
from rag.quantities import extract_exact, resolve, verify_source
from rag.session import InputError, Session, Stage, _enter_spec, finish, set_values


def position():
    return Position(
        "test",
        "Шкаф",
        "31",
        "Мебель",
        (),
        (),
        False,
        None,
        (
            Characteristic(
                "h",
                "Высота",
                True,
                "2",
                True,
                (
                    Value(
                        unit="Миллиметр",
                        min=1000,
                        min_op="greaterOrEqual",
                        max=1200,
                        max_op="less",
                    ),
                ),
            ),
            Characteristic(
                "d",
                "Глубина",
                True,
                "2",
                False,
                (
                    Value(
                        unit="Миллиметр",
                        min=500,
                        min_op="greaterOrEqual",
                        max=600,
                        max_op="less",
                    ),
                ),
            ),
        ),
    )


class QuantityTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.p = position()
        self.s = Session(
            "шкаф",
            "шкаф",
            [],
            [],
            [],
            [self.p],
            position=self.p,
            group=self.p,
            stage=Stage.SPEC,
        )

    def test_conversion_and_boundaries(self):
        height, depth = self.p.characteristics
        self.assertEqual(resolve(depth, "0,55 м")[0], "550")
        self.assertEqual(resolve(height, "1 м")[0], "1000")
        for raw in ("999", "1200", "1000 кг", "NaN", "1000–1200", "1000 мм extra"):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                resolve(height, raw)
        with self.assertRaises(ValueError):
            resolve(height, "1000", require_unit=True)

    def test_ranges_and_approximations_are_not_exact(self):
        for evidence in ("от 1000 мм до 1200 мм", "примерно 1000 мм", "≥ 1000 мм"):
            with self.subTest(evidence=evidence), self.assertRaises(ValueError):
                verify_source("1000 мм", evidence, evidence)

    def test_physical_dimensions_and_counts(self):
        length = Characteristic(
            "l",
            "Длина",
            True,
            "2",
            False,
            (Value(unit="Миллиметр", max=500, max_op="less"),),
        )
        count = Characteristic(
            "n",
            "Количество",
            True,
            "2",
            False,
            (Value(unit="Штука", min=0, min_op="greaterOrEqual"),),
        )
        for c, raw in ((length, "-1"), (length, "0"), (count, "1,5")):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                resolve(c, raw)
        self.assertEqual(resolve(count, "2", require_unit=True)[0], "2")

    def test_exact_api_and_export(self):
        set_values(self.s, {}, {"Высота": "1000", "Глубина": "550"})
        response = api.view(self.s)
        height = next(c for c in response.characteristics if c.name == "Высота")
        self.assertEqual(height.numeric.exact, "1000")
        self.assertEqual(height.numeric.unit, "мм")
        result = finish(self.s)
        self.assertEqual(result["chosen"]["Глубина"], ["550 мм"])
        self.assertIn("500", result["catalog_values"]["Глубина"][0])

    def test_atomic_validation_clear_and_required(self):
        set_values(self.s, {}, {"Высота": "1000"})
        with self.assertRaises(InputError):
            set_values(self.s, {}, {"Высота": "1100", "Глубина": "999"})
        self.assertEqual(self.s.exact["Высота"], "1000")
        set_values(self.s, {}, {"Высота": ""})
        self.assertEqual(self.s.missing, ["Высота"])
        with self.assertRaises(InputError):
            finish(self.s)
        with self.assertRaises(InputError):
            set_values(self.s, {"Высота": ["≥ 1000 < 1200 Миллиметр"]})

    async def test_initial_extraction_keeps_actual_number(self):
        self.s.context = ["высота 1000 мм, глубина 0,55 м"]
        quantities = {
            "quantities": [
                {"name": "Высота", "quantity": "1000 мм", "evidence": "высота 1000 мм"},
                {"name": "Глубина", "quantity": "0,55 м", "evidence": "глубина 0,55 м"},
            ]
        }
        with (
            patch("rag.session.extract", AsyncMock(return_value={})),
            patch("rag.session.no_new_features", return_value=False),
            patch("rag.quantities.structured", AsyncMock(return_value=quantities)),
        ):
            await _enter_spec(self.s, object(), self.p)
        self.assertEqual(self.s.exact, {"Высота": "1000", "Глубина": "550"})
        self.assertEqual(self.s.missing, [])

    async def test_unconfirmed_numbers_are_not_invented(self):
        quantities = {
            "quantities": [
                {"name": "Высота", "quantity": "1000 мм", "evidence": "высота 1000 мм"}
            ]
        }
        with patch("rag.quantities.structured", AsyncMock(return_value=quantities)):
            self.assertEqual(await extract_exact(self.p, "шкаф высокий"), {})

    async def test_conversation_updates_same_range_and_clears(self):
        set_values(self.s, {}, {"Высота": "1000"})
        label = self.s.chosen["Высота"][0]
        out = {
            "changes": [
                {
                    "name": "Высота",
                    "values": [label],
                    "evidence": "высота 1100 мм",
                    "quantity": "1100 мм",
                }
            ],
            "extras": [],
            "remove_extras": [],
            "clarification": "",
        }
        with patch("rag.conversation.structured", AsyncMock(return_value=out)):
            await conversation.respond(self.s, object(), "высота 1100 мм")
        self.assertEqual(self.s.exact["Высота"], "1100")
        self.assertIn("1000 мм → 1100 мм", self.s.message)
        out["changes"] = [
            {"name": "Высота", "values": [], "evidence": "убери высоту", "quantity": ""}
        ]
        with patch("rag.conversation.structured", AsyncMock(return_value=out)):
            await conversation.respond(self.s, object(), "убери высоту")
        self.assertNotIn("Высота", self.s.exact)
        self.assertEqual(self.s.missing, ["Высота"])

    async def test_patch_route(self):
        api.sessions[self.s.id] = self.s
        api.locks[self.s.id] = asyncio.Lock()
        try:
            result = await api.set_values(
                self.s.id, api.ValuesIn(values={}, exact={"Высота": "1100"})
            )
            self.assertEqual(
                next(
                    c for c in result.characteristics if c.name == "Высота"
                ).numeric.exact,
                "1100",
            )
        finally:
            api.sessions.pop(self.s.id)
            api.locks.pop(self.s.id)
