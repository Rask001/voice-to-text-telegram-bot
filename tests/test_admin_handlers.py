import asyncio
import unittest
from types import SimpleNamespace

from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage

from app.config import Settings
from app.handlers.admin import AdminStates, admin_help, cancel_admin_mode


class FakeMessage:
    def __init__(self, user_id: int, username: str | None = None) -> None:
        self.from_user = SimpleNamespace(id=user_id, username=username)
        self.answers = []

    async def answer(self, text: str, reply_markup=None):
        self.answers.append({"text": text, "reply_markup": reply_markup})


class AdminHandlerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.settings = Settings(
            telegram_bot_token="test-token",
            openai_api_key="test-key",
            owner_telegram_id=1,
        )

    def test_non_owner_cannot_call_admin_help(self) -> None:
        message = FakeMessage(user_id=2)

        asyncio.run(admin_help(message, self.settings))

        self.assertEqual(message.answers[0]["text"], "Команда доступна только владельцу бота.")

    def test_owner_can_call_admin_help(self) -> None:
        message = FakeMessage(user_id=1)

        asyncio.run(admin_help(message, self.settings))

        self.assertIn("Админ-команды", message.answers[0]["text"])
        self.assertIn("/admin_backup", message.answers[0]["text"])

    def test_cancel_clears_admin_state(self) -> None:
        storage = MemoryStorage()
        state = FSMContext(
            storage=storage,
            key=StorageKey(bot_id=1, chat_id=1, user_id=1),
        )
        message = FakeMessage(user_id=1)

        async def run_case() -> None:
            await state.set_state(AdminStates.waiting_for_start_text)
            await cancel_admin_mode(message, state, self.settings)

        asyncio.run(run_case())

        self.assertIsNone(asyncio.run(state.get_state()))
        self.assertEqual(message.answers[0]["text"], "Действие отменено.")


if __name__ == "__main__":
    unittest.main()
