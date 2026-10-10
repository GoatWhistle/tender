import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from rag import api
from rag.models import Position
from rag.session import InputError, Session, Stage, StageError


class MessageReviewTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.position = Position(
            "test", "Шкаф", "31", "Мебель", (), (), False, None, ()
        )
        self.session = Session("шкаф", "шкаф", [], [], [], [self.position])
        self.session.group = self.position
        self.session.position = self.position
        self.session.stage = Stage.SPEC
        self.session.chosen = {"Высота": ("1000 мм",)}
        api.sessions[self.session.id] = self.session
        import asyncio

        api.locks[self.session.id] = asyncio.Lock()
        self.request = SimpleNamespace(
            app=SimpleNamespace(state=SimpleNamespace(index=object()))
        )

    def tearDown(self):
        api.sessions.pop(self.session.id)
        api.locks.pop(self.session.id)

    async def prepare(self, issues=None):
        result = {
            "corrected": "высота 1100 мм",
            "fixes": [{"before": "м", "after": "мм", "kind": "unit"}],
            "issues": issues or [],
        }
        with (
            patch("rag.message_review.structured", AsyncMock(return_value=result)),
            patch("rag.conversation.respond", AsyncMock()) as respond,
        ):
            response = await api.message(
                self.session.id, api.TextIn(text="высота 1100 м"), self.request
            )
            respond.assert_not_awaited()
        self.assertEqual(self.session.chosen, {"Высота": ("1000 мм",)})
        self.assertEqual(response.message_review.corrected, "высота 1100 мм")
        return response.message_review.id

    async def test_corrections_require_confirmation(self):
        review_id = await self.prepare()
        with patch("rag.conversation.respond", AsyncMock()) as respond:
            response = await api.confirm_message(
                self.session.id, review_id, self.request
            )
            respond.assert_awaited_once_with(
                self.session, self.request.app.state.index, "высота 1100 мм"
            )
        self.assertIsNone(response.message_review)

    async def test_unresolved_issues_block_application(self):
        review_id = await self.prepare(["Уточните единицу высоты."])
        with patch("rag.conversation.respond", AsyncMock()) as respond:
            with self.assertRaises(InputError):
                await api.confirm_message(self.session.id, review_id, self.request)
            respond.assert_not_awaited()

    async def test_changed_card_requires_new_review(self):
        review_id = await self.prepare()
        self.session.chosen["Высота"] = ("1200 мм",)
        with self.assertRaises(StageError):
            await api.confirm_message(self.session.id, review_id, self.request)

    async def test_clean_addition_is_applied(self):
        result = {"corrected": "высота 1100 мм", "fixes": [], "issues": []}
        with (
            patch("rag.message_review.structured", AsyncMock(return_value=result)),
            patch("rag.conversation.respond", AsyncMock()) as respond,
        ):
            response = await api.message(
                self.session.id, api.TextIn(text=result["corrected"]), self.request
            )
            respond.assert_awaited_once()
        self.assertIsNone(response.message_review)

    async def test_empty_message_does_not_call_model(self):
        with patch("rag.message_review.structured", AsyncMock()) as model:
            with self.assertRaises(InputError):
                await api.message(self.session.id, api.TextIn(text="  "), self.request)
            model.assert_not_awaited()
