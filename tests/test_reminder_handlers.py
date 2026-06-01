import asyncio
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup

from app.config import Settings
from app.db import create_session_factory
from app.handlers.reminders import ReminderCreation, reminder_text_received
from app.models import Reminder


class FakeMessage:
    def __init__(self, text: str) -> None:
        self.text = text
        self.from_user = SimpleNamespace(id=123, username="tester")
        self.answers = []

    async def answer(self, text: str, reply_markup=None):
        self.answers.append({"text": text, "reply_markup": reply_markup})


class ReminderHandlerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        db_path = Path(self.tmpdir.name) / "handler_reminders.db"
        self.settings = Settings(
            telegram_bot_token="test-token",
            openai_api_key="test-key",
            database_url=f"sqlite:///{db_path}",
        )
        self.session_factory = create_session_factory(self.settings)
        self.storage = MemoryStorage()
        self.state = FSMContext(
            storage=self.storage,
            key=StorageKey(bot_id=1, chat_id=123, user_id=123),
        )

    def tearDown(self) -> None:
        bind = self.session_factory.kw.get("bind")
        if bind is not None:
            bind.dispose()
        self.tmpdir.cleanup()

    def test_text_with_time_creates_reminder_without_time_menu(self) -> None:
        message = FakeMessage("позвонить Соне в 21:21")

        asyncio.run(
            reminder_text_received(
                message,
                self.state,
                self.settings,
                self.session_factory,
            )
        )

        self.assertEqual(len(message.answers), 1)
        self.assertIn("✅", message.answers[0]["text"])
        self.assertNotIn("Когда напомнить?", message.answers[0]["text"])
        self.assertNotIsInstance(message.answers[0]["reply_markup"], InlineKeyboardMarkup)

        with self.session_factory() as session:
            reminder = session.query(Reminder).one()
            self.assertEqual(reminder.task_text, "позвонить Соне")

    def test_relative_text_creates_reminder_without_time_menu(self) -> None:
        message = FakeMessage("через минуту проверить бота")

        asyncio.run(
            reminder_text_received(
                message,
                self.state,
                self.settings,
                self.session_factory,
            )
        )

        self.assertEqual(len(message.answers), 1)
        self.assertIn("✅", message.answers[0]["text"])
        self.assertNotIn("Когда напомнить?", message.answers[0]["text"])

        with self.session_factory() as session:
            reminder = session.query(Reminder).one()
            self.assertEqual(reminder.task_text, "проверить бота")

    def test_text_without_time_shows_time_menu(self) -> None:
        message = FakeMessage("позвонить Соне")

        asyncio.run(
            reminder_text_received(
                message,
                self.state,
                self.settings,
                self.session_factory,
            )
        )

        self.assertEqual(len(message.answers), 1)
        self.assertIn("Когда напомнить?", message.answers[0]["text"])
        self.assertIsInstance(message.answers[0]["reply_markup"], InlineKeyboardMarkup)
        self.assertEqual(asyncio.run(self.state.get_state()), ReminderCreation.waiting_for_time)

        with self.session_factory() as session:
            self.assertEqual(session.query(Reminder).count(), 0)

    def test_time_without_task_asks_for_task(self) -> None:
        message = FakeMessage("через 10 минут")

        asyncio.run(
            reminder_text_received(
                message,
                self.state,
                self.settings,
                self.session_factory,
            )
        )

        self.assertEqual(len(message.answers), 1)
        self.assertEqual(message.answers[0]["text"], "Что напомнить?")
        self.assertEqual(
            asyncio.run(self.state.get_state()),
            ReminderCreation.waiting_for_task_after_time,
        )

        with self.session_factory() as session:
            self.assertEqual(session.query(Reminder).count(), 0)


if __name__ == "__main__":
    unittest.main()
